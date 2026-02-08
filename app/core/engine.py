# app/core/engine.py
"""
Runtime central del sistema (Engine).

Rol:
- Consumir eventos del Collector (Mock o Playwright).
- Persistir estado en SQLite (mínimo operativo).
- Aplicar reglas de seguridad (SecurityPolicy).
- Aplicar decisiones de alertas (AlertEngine).
- Emitir eventos "procesados" hacia la UI.

Mejora clave:
- Observabilidad sin spam:
  - Log inmediato si hay CAMBIO / ERROR / END
  - Log agregado cada N segundos con conteos (updates, changed, http_error, end)
"""

from __future__ import annotations

from dataclasses import dataclass
from queue import Queue, Empty
from typing import Optional
from datetime import datetime, timedelta

from app.core.events import Event, EventType, info, warn
from app.core.alert_engine import AlertEngine, AlertDecision
from app.core.security import SecurityPolicy, SecurityAction
from app.db.database import Database
from app.utils.time import now_iso


@dataclass
class EngineConfig:
    utilidad_min_pct_default: float = 10.0
    ocultar_bajo_umbral_default: bool = False

    # Observabilidad
    agg_window_seconds: int = 30


class Engine:
    def __init__(
        self,
        *,
        db: Database,
        in_q: Queue,
        out_q: Queue,
        control_q: Queue | None = None,
        config: EngineConfig | None = None,
    ):
        self.db = db
        self.in_q = in_q
        self.out_q = out_q
        self.control_q = control_q

        self.config = config or EngineConfig()
        self.current_poll_seconds = 1.0
        self.alert_engine = AlertEngine()
        self.security = SecurityPolicy()

        # caches
        self.subasta_id_by_id_cot: dict[str, int] = {}
        self.renglon_pk_by_keys: dict[tuple[int, str], int] = {}

        # estado operativo para seguridad
        self.subasta_err_streak: dict[int, int] = {}
        self.subasta_last_ok_at: dict[int, Optional[str]] = {}

        # firmas por renglón (para detectar cambios)
        self.last_sig_by_renglon_pk: dict[int, str] = {}

        # anti-spam: END por subasta+renglon
        self._ended_keys: set[tuple[int, int]] = set()
        self._stop_sent_subastas: set[int] = set()

        # agregación de logs
        self._agg_last_emit: Optional[datetime] = None
        self._agg_counts = {"updates": 0, "changed": 0, "http_error": 0, "end": 0}

    # -------------------------
    # API
    # -------------------------
    def emit_ui(self, ev: Event) -> None:
        self.out_q.put(ev)

    def set_current_poll_seconds(self, seconds: float) -> None:
        self.current_poll_seconds = max(0.2, float(seconds))

    def run_once(self, timeout: float = 0.05) -> None:
        try:
            ev: Event = self.in_q.get(timeout=timeout)
        except Empty:
            self._maybe_emit_aggregated_log()
            return

        self._handle(ev)
        self._maybe_emit_aggregated_log()

    @staticmethod
    def _safe_mul(a: float | None, b: float | None) -> float | None:
        if a is None or b is None:
            return None
        try:
            return float(a) * float(b)
        except Exception:
            return None

    @staticmethod
    def _safe_div(a: float | None, b: float | None) -> float | None:
        if a is None or b in (None, 0):
            return None
        try:
            return float(a) / float(b)
        except Exception:
            return None

    def _resolve_precio_ref_unitario(
        self,
        *,
        cantidad: float | None,
        precio_referencia: float | None,
        presupuesto: float | None,
    ) -> float | None:
        """
        Regla unificada para referencia por unidad:
        - Si hay presupuesto oficial y cantidad: usar presupuesto/cantidad.
        - Si no, fallback al precio de referencia recibido.
        """
        unit_from_presupuesto = self._safe_div(presupuesto, cantidad)
        if unit_from_presupuesto is not None:
            return unit_from_presupuesto
        if precio_referencia is None:
            return None
        try:
            return float(precio_referencia)
        except Exception:
            return None

    # -------------------------
    # Handler central
    # -------------------------
    def _handle(self, ev: Event) -> None:
        self._persist_event(ev)

        if ev.type == EventType.SNAPSHOT:
            self._handle_snapshot(ev)
            self.emit_ui(ev)
            return

        if ev.type == EventType.UPDATE:
            self._handle_update(ev)
            return

        if ev.type == EventType.HTTP_ERROR:
            self._handle_http_error(ev)
            return

        if ev.type == EventType.END:
            self._handle_end(ev)
            return

        self.emit_ui(ev)

    # -------------------------
    # Persistencia de eventos (observabilidad)
    # -------------------------
    def _persist_event(self, ev: Event) -> None:
        try:
            self.db.insert_evento(
                nivel=str(ev.level.value),
                tipo=str(ev.type.value),
                mensaje=ev.message,
                subasta_id=ev.subasta_id,
                renglon_id=ev.renglon_id,
            )
        except Exception:
            pass

    # -------------------------
    # SNAPSHOT
    # -------------------------
    def _handle_snapshot(self, ev: Event) -> None:
        payload = ev.payload or {}
        id_cot = payload.get("id_cot")
        subasta_url = payload.get("subasta_url") or ""
        margen = payload.get("margen") or ""
        renglones = payload.get("renglones") or []

        if not id_cot:
            self.emit_ui(warn(EventType.EXCEPTION, "SNAPSHOT inválido: falta id_cot"))
            return

        subasta_id = self.db.upsert_subasta(id_cot=str(id_cot), url=str(subasta_url))
        self.subasta_id_by_id_cot[str(id_cot)] = subasta_id

        for r in renglones:
            rid = str(r.get("value") or "")
            desc = str(r.get("text") or "").strip()
            if not rid:
                continue

            pk = self.db.upsert_renglon(
                subasta_id=subasta_id,
                id_renglon=rid,
                descripcion=desc,
                margen_minimo=margen,
            )
            self.renglon_pk_by_keys[(subasta_id, rid)] = pk

            # Si la subasta trae cantidad/precio_ref, los guardamos como "del sistema"
            cantidad = r.get("cantidad")
            precio_ref_subasta_raw = r.get("precio_referencia")
            presupuesto_ref = r.get("presupuesto")
            precio_ref_subasta = self._resolve_precio_ref_unitario(
                cantidad=cantidad,
                precio_referencia=precio_ref_subasta_raw,
                presupuesto=presupuesto_ref,
            )

            if cantidad is not None or precio_ref_subasta is not None:
                existing = self.db.get_renglon_excel(renglon_id=pk) or {}
                self.db.upsert_renglon_excel(
                    renglon_id=pk,
                    unidad_medida=existing.get("unidad_medida"),
                    cantidad=existing.get("cantidad") if cantidad is None else cantidad,
                    marca=existing.get("marca"),
                    observaciones=existing.get("observaciones"),
                    conversion_usd=existing.get("conversion_usd"),
                    costo_usd=existing.get("costo_usd"),
                    costo_final_pesos=existing.get("costo_final_pesos"),
                    renta=existing.get("renta"),
                    precio_referencia=existing.get("precio_referencia"),
                    precio_referencia_subasta=(
                        existing.get("precio_referencia_subasta")
                        if precio_ref_subasta is None
                        else precio_ref_subasta
                    ),
                    updated_at=now_iso(),
                )

        self.db.set_subasta_estado(subasta_id=subasta_id, estado="RUNNING", last_ok_at=None, err_streak=0)
        self.subasta_err_streak[subasta_id] = 0
        self.subasta_last_ok_at[subasta_id] = None

        self.emit_ui(
            info(
                EventType.HEARTBEAT,
                f"SNAPSHOT aplicado (subasta_id={subasta_id}, renglones={len(renglones)})",
            )
        )

    # -------------------------
    # UPDATE
    # -------------------------
    def _handle_update(self, ev: Event) -> None:
        payload = ev.payload or {}
        rid = payload.get("id_renglon")
        id_cot = payload.get("id_cot")

        if not rid:
            self.emit_ui(warn(EventType.EXCEPTION, "UPDATE inválido: falta id_renglon"))
            return

        subasta_id = None
        if id_cot and str(id_cot) in self.subasta_id_by_id_cot:
            subasta_id = self.subasta_id_by_id_cot[str(id_cot)]
        elif len(self.subasta_id_by_id_cot) == 1:
            subasta_id = next(iter(self.subasta_id_by_id_cot.values()))

        if not subasta_id:
            self._agg_counts["updates"] += 1
            return

        key = (subasta_id, str(rid))
        renglon_pk = self.renglon_pk_by_keys.get(key)
        if not renglon_pk:
            desc = str(payload.get("desc") or "Renglón sin descripción").strip()
            renglon_pk = self.db.upsert_renglon(
                subasta_id=subasta_id,
                id_renglon=str(rid),
                descripcion=desc,
                margen_minimo=None,
            )
            self.renglon_pk_by_keys[key] = renglon_pk

        mejor_txt = payload.get("mejor_oferta_txt") or ""
        oferta_min_txt = payload.get("oferta_min_txt") or ""
        presupuesto_txt = payload.get("presupuesto_txt") or ""
        mensaje = payload.get("mensaje") or ""
        http_status = int(payload.get("http_status", 200))

        mejor_val = payload.get("mejor_oferta_val")
        oferta_min_val = payload.get("oferta_min_val")
        presupuesto_val = payload.get("presupuesto_val")

        ts = now_iso()
        self.db.upsert_renglon_estado(
            renglon_id=renglon_pk,
            mejor_txt=mejor_txt,
            oferta_min_txt=oferta_min_txt,
            presupuesto_txt=presupuesto_txt,
            mejor=mejor_val,
            oferta_min=oferta_min_val,
            presupuesto=presupuesto_val,
            mensaje=mensaje,
            updated_at=ts,
        )

        self.subasta_last_ok_at[subasta_id] = ts
        self.subasta_err_streak[subasta_id] = 0
        self.db.set_subasta_estado(
            subasta_id=subasta_id,
            estado="RUNNING",
            last_ok_at=ts,
            last_http_code=http_status,
            err_streak=0,
        )

        sig = f"{mejor_txt}|{oferta_min_txt}|{mensaje}"
        changed = self.last_sig_by_renglon_pk.get(renglon_pk) != sig
        self.last_sig_by_renglon_pk[renglon_pk] = sig

        self._agg_counts["updates"] += 1
        if changed:
            self._agg_counts["changed"] += 1

        excel = self.db.get_renglon_excel(renglon_id=renglon_pk)

        unidad_medida = None
        cantidad = None
        marca = None
        observaciones = None
        conversion_usd = None
        costo_usd = None
        costo_final_pesos = None
        renta = None
        precio_referencia_subasta = None  # <-- CORRECCIÓN: sí se carga desde DB

        if excel:
            unidad_medida = excel.get("unidad_medida")
            cantidad = excel.get("cantidad")
            marca = excel.get("marca")
            observaciones = excel.get("observaciones")
            conversion_usd = excel.get("conversion_usd")
            costo_usd = excel.get("costo_usd")
            costo_final_pesos = excel.get("costo_final_pesos")
            renta = excel.get("renta")
            precio_referencia_subasta = excel.get("precio_referencia_subasta")  # <-- FIX

        costo_usd_calc = None
        if conversion_usd not in (None, 0) and costo_final_pesos is not None:
            try:
                costo_usd_calc = float(costo_final_pesos) / float(conversion_usd)
            except Exception:
                costo_usd_calc = None

        subtotal_para_mejorar = oferta_min_val
        subtotal_costo_pesos = self._safe_mul(cantidad, costo_final_pesos)
        p_unit_minimo = self._safe_mul(renta, costo_final_pesos)
        subtotal = self._safe_mul(cantidad, p_unit_minimo)

        precio_ref_unit = self._resolve_precio_ref_unitario(
            cantidad=cantidad,
            precio_referencia=precio_referencia_subasta,
            presupuesto=presupuesto_val,
        )

        renta_ref = None
        if precio_ref_unit is not None and costo_final_pesos not in (None, 0):
            renta_ref = (float(precio_ref_unit) / float(costo_final_pesos)) - 1.0

        p_unit_mejora = self._safe_div(subtotal_para_mejorar, cantidad)

        dif_unit = None
        if p_unit_mejora is not None and costo_final_pesos is not None:
            dif_unit = float(p_unit_mejora) - float(costo_final_pesos)

        renta_dpc = None
        if p_unit_mejora is not None and costo_final_pesos not in (None, 0):
            renta_dpc = (float(p_unit_mejora) / float(costo_final_pesos)) - 1.0

        cfg = self.db.get_renglon_config(renglon_id=renglon_pk)
        costo_subtotal = None
        seguir = False
        oferta_mia = False
        utilidad_min_pct = self.config.utilidad_min_pct_default
        ocultar_bajo_umbral = self.config.ocultar_bajo_umbral_default

        if cfg:
            costo_subtotal = cfg.get("costo_subtotal")
            seguir = bool(cfg.get("seguir"))
            oferta_mia = bool(cfg.get("oferta_mia"))
            utilidad_min_pct = float(cfg.get("utilidad_min_pct", utilidad_min_pct))
            ocultar_bajo_umbral = bool(cfg.get("ocultar_bajo_umbral", ocultar_bajo_umbral))

        base_cost = costo_subtotal
        if base_cost is None and costo_final_pesos is not None:
            base_cost = costo_final_pesos

        utilidad_pct = None
        if base_cost is not None and base_cost > 0 and oferta_min_val is not None:
            utilidad_pct = ((float(oferta_min_val) - float(base_cost)) / float(base_cost)) * 100.0

        tracked = bool(seguir or (base_cost is not None))

        decision: AlertDecision = self.alert_engine.decide(
            tracked=tracked,
            oferta_mia=oferta_mia,
            utilidad_pct=utilidad_pct,
            utilidad_min_pct=utilidad_min_pct,
            ocultar_bajo_umbral=ocultar_bajo_umbral,
            changed=bool(changed),
            http_status=http_status,
            mensaje=mensaje,
        )

        if changed:
            self.emit_ui(info(EventType.HEARTBEAT, f"CAMBIO rid={rid} mejor={mejor_txt} min={oferta_min_txt}"))

        self.emit_ui(
            info(
                EventType.UPDATE,
                ev.message,
                subasta_id=subasta_id,
                renglon_id=renglon_pk,
                payload={
                    **payload,
                    "changed": bool(changed),
                    "costo_subtotal": costo_subtotal,
                    "unidad_medida": unidad_medida,
                    "cantidad": cantidad,
                    "marca": marca,
                    "observaciones": observaciones,
                    "conversion_usd": conversion_usd,
                    "costo_usd": costo_usd_calc if costo_usd_calc is not None else costo_usd,
                    "costo_final_pesos": costo_final_pesos,
                    "renta": renta,
                    "precio_referencia_subasta": precio_ref_unit,
                    "subtotal_para_mejorar": subtotal_para_mejorar,
                    "subtotal_costo_pesos": subtotal_costo_pesos,
                    "p_unit_minimo": p_unit_minimo,
                    "subtotal": subtotal,
                    "renta_ref": renta_ref,
                    "p_unit_mejora": p_unit_mejora,
                    "dif_unit": dif_unit,
                    "renta_dpc": renta_dpc,
                    "utilidad_pct": utilidad_pct,
                    "seguir": bool(seguir),
                    "oferta_mia": bool(oferta_mia),
                    "utilidad_min_pct": utilidad_min_pct,
                    "ocultar_bajo_umbral": bool(ocultar_bajo_umbral),
                    "alert_style": decision.style.value,
                    "sound": decision.play_sound.value,
                    "highlight": decision.highlight,
                    "hide": decision.hide,
                    "decision_msg": decision.message,
                },
            )
        )

        if "finalizada" in str(mensaje).lower():
            self._handle_end(
                info(
                    EventType.END,
                    "Subasta finalizada detectada por mensaje",
                    subasta_id=subasta_id,
                    payload={"id_renglon": rid},
                )
            )

    # -------------------------
    # HTTP_ERROR
    # -------------------------
    def _handle_http_error(self, ev: Event) -> None:
        payload = ev.payload or {}
        http_status = int(payload.get("http_status", 500))
        id_cot = payload.get("id_cot")

        self._agg_counts["http_error"] += 1

        subasta_id = None
        if id_cot and str(id_cot) in self.subasta_id_by_id_cot:
            subasta_id = self.subasta_id_by_id_cot[str(id_cot)]
        elif len(self.subasta_id_by_id_cot) == 1:
            subasta_id = next(iter(self.subasta_id_by_id_cot.values()))

        if not subasta_id:
            self.emit_ui(ev)
            return

        prev = int(self.subasta_err_streak.get(subasta_id, 0))
        streak = prev + 1
        self.subasta_err_streak[subasta_id] = streak
        last_ok_at = self.subasta_last_ok_at.get(subasta_id)

        self.db.set_subasta_estado(
            subasta_id=subasta_id,
            estado="ERROR",
            last_ok_at=last_ok_at,
            last_http_code=http_status,
            err_streak=streak,
        )

        decision = self.security.evaluate(
            current_poll_seconds=self.current_poll_seconds,
            err_streak=streak,
            last_ok_at=last_ok_at,
            http_status=http_status,
            mensaje=str(ev.message),
        )

        self.emit_ui(
            warn(
                EventType.HTTP_ERROR,
                f"HTTP={http_status} streak={streak} -> {decision.action.value} ({decision.message})",
            )
        )

        if decision.action == SecurityAction.BACKOFF and decision.new_poll_seconds:
            if decision.new_poll_seconds > self.current_poll_seconds:
                self.current_poll_seconds = float(decision.new_poll_seconds)
                if self.control_q is not None:
                    self.control_q.put({"action": "BACKOFF", "seconds": float(decision.new_poll_seconds)})

        if decision.action == SecurityAction.STOP:
            self.db.set_subasta_estado(subasta_id=subasta_id, estado="ENDED", ended_at=now_iso())
            self.emit_ui(
                info(
                    EventType.END,
                    "Corte por seguridad",
                    payload={
                        "reason": decision.message,
                        "id_cot": id_cot,
                        "id_renglon": payload.get("id_renglon"),
                    },
                )
            )
            if subasta_id not in self._stop_sent_subastas and self.control_q is not None:
                self._stop_sent_subastas.add(subasta_id)
                self.control_q.put({"action": "STOP", "reason": decision.message})
            return

        self.emit_ui(ev)

    # -------------------------
    # END
    # -------------------------
    def _handle_end(self, ev: Event) -> None:
        payload = ev.payload or {}
        id_cot = payload.get("id_cot")
        rid = payload.get("id_renglon")

        self._agg_counts["end"] += 1

        subasta_id = None
        if id_cot and str(id_cot) in self.subasta_id_by_id_cot:
            subasta_id = self.subasta_id_by_id_cot[str(id_cot)]
        elif len(self.subasta_id_by_id_cot) == 1:
            subasta_id = next(iter(self.subasta_id_by_id_cot.values()))

        if not subasta_id:
            self.emit_ui(ev)
            return

        key = (subasta_id, int(hash(str(rid)) & 0x7FFFFFFF))
        if key in self._ended_keys:
            return
        self._ended_keys.add(key)

        self.db.set_subasta_estado(subasta_id=subasta_id, estado="ENDED", ended_at=now_iso())

        self.emit_ui(info(EventType.END, f"Subasta marcada ENDED (subasta_id={subasta_id})"))
        self.emit_ui(ev)

    # -------------------------
    # Agregación de logs (cada N segundos)
    # -------------------------
    def _maybe_emit_aggregated_log(self) -> None:
        total = sum(self._agg_counts.values())
        if total <= 0:
            return

        now = datetime.now()
        if self._agg_last_emit is None:
            self._agg_last_emit = now
            return

        if (now - self._agg_last_emit) < timedelta(seconds=int(self.config.agg_window_seconds)):
            return

        msg = (
            f"Resumen {self.config.agg_window_seconds}s | "
            f"updates={self._agg_counts['updates']} | "
            f"changed={self._agg_counts['changed']} | "
            f"http_error={self._agg_counts['http_error']} | "
            f"end={self._agg_counts['end']}"
        )
        self.emit_ui(info(EventType.HEARTBEAT, msg))

        self._agg_counts = {"updates": 0, "changed": 0, "http_error": 0, "end": 0}
        self._agg_last_emit = now
