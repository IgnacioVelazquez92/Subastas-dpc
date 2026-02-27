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
        self.base_poll_seconds = 1.0
        self.alert_engine = AlertEngine()
        self.security = SecurityPolicy()

        # caches
        self.subasta_id_by_id_cot: dict[str, int] = {}
        self.renglon_pk_by_keys: dict[tuple[int, str], int] = {}

        # mi_id_proveedor por subasta (cargado bajo demanda)
        self._mi_id_proveedor_cache: dict[int, str | None] = {}
        # Estado previo de oferta_mia_auto por renglón PK (para detectar outbid)
        self._prev_oferta_mia_auto: dict[int, bool] = {}

        # estado operativo para seguridad
        self.subasta_err_streak: dict[int, int] = {}
        self.subasta_last_ok_at: dict[int, Optional[str]] = {}
        self.subasta_last_error_at: dict[int, Optional[datetime]] = {}

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

    def set_base_poll_seconds(self, seconds: float) -> None:
        self.base_poll_seconds = max(0.2, float(seconds))

    def refresh_mi_id_proveedor(self, subasta_id: int) -> None:
        """Invalida cache de mi_id_proveedor para que se recargue desde DB en el siguiente tick."""
        self._mi_id_proveedor_cache.pop(subasta_id, None)


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

    def _resolve_costo_final(
        self,
        *,
        costo_unit_ars: float | None,
        costo_total_ars: float | None,
        cantidad: float | None,
        should_log: bool = False,
    ) -> tuple[float | None, float | None]:
        """
        Resuelve la bidirecionaldad entre COSTO UNITARIO y COSTO TOTAL ARS.
        
        Reglas:
        1. Si ambos están presentes: priorizar TOTAL (como valor autorizado)
           y recalcular UNITARIO = TOTAL / cantidad
        2. Si solo UNITARIO: calcular TOTAL = UNITARIO * cantidad
        3. Si solo TOTAL: calcular UNITARIO = TOTAL / cantidad
        4. Si ninguno: retornar (None, None)
        
        Retorna: (costo_unit_ars, costo_total_ars)
        """
        if should_log:
            print(f"\n[CALC] _resolve_costo_final:")
            print(f"  INPUT: unit_ars={costo_unit_ars}, total_ars={costo_total_ars}, cant={cantidad}")
        
        # Si ambos están presentes: priorizar TOTAL
        if costo_total_ars is not None and costo_unit_ars is not None:
            # Recalcular unitario desde total (si cantidad existe)
            if cantidad not in (None, 0):
                try:
                    unit = float(costo_total_ars) / float(cantidad)
                    if should_log:
                        print(f"  AMBOS PRESENTES -> Priorizar TOTAL: unit={unit:.2f}, total={costo_total_ars:.2f}")
                    return (unit, float(costo_total_ars))
                except Exception:
                    if should_log:
                        print(f"  AMBOS PRESENTES (sin recalc): unit={costo_unit_ars:.2f}, total={costo_total_ars:.2f}")
                    return (float(costo_unit_ars), float(costo_total_ars))
            if should_log:
                print(f"  AMBOS PRESENTES (cant=0): unit={costo_unit_ars:.2f}, total={costo_total_ars:.2f}")
            return (float(costo_unit_ars), float(costo_total_ars))
        
        # Si solo TOTAL: calcular UNITARIO
        if costo_total_ars is not None and costo_unit_ars is None:
            unit = self._safe_div(costo_total_ars, cantidad)
            if should_log:
                print(f"  SOLO TOTAL -> Calcular unit: unit={unit}, total={costo_total_ars:.2f}")
            return (unit, float(costo_total_ars) if costo_total_ars is not None else None)
        
        # Si solo UNITARIO: calcular TOTAL
        if costo_unit_ars is not None and costo_total_ars is None:
            total = self._safe_mul(costo_unit_ars, cantidad)
            if should_log:
                print(f"  SOLO UNIT -> Calcular total: unit={costo_unit_ars:.2f}, total={total}")
            return (float(costo_unit_ars) if costo_unit_ars is not None else None, total)
        
        # Si ninguno
        if should_log:
            print(f"  NINGUNO -> (None, None)")
        return (None, None)

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
            precio_ref_total = r.get("precio_referencia")  # TOTAL (Presupuesto Oficial)
            precio_ref_unit = r.get("precio_ref_unitario")  # UNITARIO (Precio de referencia)
            presupuesto_ref = r.get("presupuesto")

            # Fallback de compatibilidad: si no vino TOTAL en el campo principal, usar presupuesto.
            if precio_ref_total is None:
                precio_ref_total = presupuesto_ref

            # Resolver unitario de referencia de forma consistente por renglón:
            # priorizar presupuesto/cantidad y dejar precio_referencia como fallback.
            precio_ref_unit = self._resolve_precio_ref_unitario(
                cantidad=cantidad,
                precio_referencia=precio_ref_unit,
                presupuesto=precio_ref_total,
            )

            if (
                cantidad is not None
                or precio_ref_total is not None
                or precio_ref_unit is not None
                or presupuesto_ref is not None
            ):
                existing = self.db.get_renglon_excel(renglon_id=pk) or {}
                self.db.upsert_renglon_excel(
                    renglon_id=pk,
                    unidad_medida=existing.get("unidad_medida"),
                    cantidad=existing.get("cantidad") if cantidad is None else cantidad,
                    marca=existing.get("marca"),
                    # REFACTORED columns
                    obs_usuario=existing.get("obs_usuario"),
                    conv_usd=existing.get("conv_usd"),
                    costo_unit_usd=existing.get("costo_unit_usd"),
                    costo_total_usd=existing.get("costo_total_usd"),
                    costo_unit_ars=existing.get("costo_unit_ars"),
                    costo_total_ars=existing.get("costo_total_ars"),
                    renta_minima=existing.get("renta_minima"),
                    precio_referencia=(
                        existing.get("precio_referencia")
                        if precio_ref_total is None
                        else precio_ref_total  # Guardar TOTAL
                    ),
                    precio_ref_unitario=(
                        existing.get("precio_ref_unitario")
                        if precio_ref_unit is None
                        else precio_ref_unit  # Guardar UNITARIO (Playwright o fallback)
                    ),
                    renta_referencia=existing.get("renta_referencia"),
                    precio_unit_aceptable=existing.get("precio_unit_aceptable"),
                    precio_total_aceptable=existing.get("precio_total_aceptable"),
                    precio_unit_mejora=existing.get("precio_unit_mejora"),
                    renta_para_mejorar=existing.get("renta_para_mejorar"),
                    oferta_para_mejorar=existing.get("oferta_para_mejorar"),
                    mejor_oferta_txt=existing.get("mejor_oferta_txt"),
                    obs_cambio=existing.get("obs_cambio"),
                    precio_referencia_subasta=None,  # Campo legacy, deprecado
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
        hora_ultima_oferta = payload.get("hora_ultima_oferta")
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
        self.subasta_last_error_at[subasta_id] = None
        self.db.set_subasta_estado(
            subasta_id=subasta_id,
            estado="RUNNING",
            last_ok_at=ts,
            last_http_code=http_status,
            err_streak=0,
        )

        # Recuperar cadencia base tras volver a recibir datos válidos.
        if self.current_poll_seconds > self.base_poll_seconds:
            self.current_poll_seconds = float(self.base_poll_seconds)
            if self.control_q is not None:
                self.control_q.put({"action": "BACKOFF", "seconds": float(self.base_poll_seconds)})

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
        obs_usuario = None
        conv_usd = None
        costo_unit_usd = None
        costo_total_usd = None
        costo_unit_ars = None
        costo_total_ars = None
        renta_minima = None
        precio_referencia = None  # TOTAL de subasta
        precio_ref_unitario = None  # Calculado: precio_referencia / cantidad
        renta_referencia = None
        precio_unit_aceptable = None
        precio_total_aceptable = None
        precio_unit_mejora = None
        renta_para_mejorar = None
        oferta_para_mejorar = None
        mejor_oferta_txt_val = None
        obs_cambio = None

        if excel:
            unidad_medida = excel.get("unidad_medida")
            cantidad = excel.get("cantidad")
            marca = excel.get("marca")
            obs_usuario = excel.get("obs_usuario")
            # 🔥 Leer de columna NUEVA primero, fallback a LEGACY
            conv_usd = excel.get("conv_usd") or excel.get("conversion_usd")
            costo_unit_usd = excel.get("costo_unit_usd")
            costo_total_usd = excel.get("costo_total_usd")
            costo_unit_ars = excel.get("costo_unit_ars")
            costo_total_ars = excel.get("costo_total_ars")
            renta_minima = excel.get("renta_minima")
            precio_referencia = excel.get("precio_referencia")  # TOTAL
            precio_ref_unitario = excel.get("precio_ref_unitario")  # UNITARIO
            renta_referencia = excel.get("renta_referencia")
            precio_unit_aceptable = excel.get("precio_unit_aceptable")
            precio_total_aceptable = excel.get("precio_total_aceptable")
            precio_unit_mejora = excel.get("precio_unit_mejora")
            renta_para_mejorar = excel.get("renta_para_mejorar")
            oferta_para_mejorar = excel.get("oferta_para_mejorar")
            mejor_oferta_txt_val = excel.get("mejor_oferta_txt")
            obs_cambio = excel.get("obs_cambio")

        # REFACTORING: Resolver bidirecionaldad de costos ARS
        # Definir costo_subtotal antes de usar should_log
        costo_subtotal = None
        # Logs de cálculo desactivados por defecto para evitar ruido en consola.
        should_log = False
        
        if should_log:
            print(f"\n{'='*60}")
            print(f"[UPDATE] Renglón: {rid} - 🔄 CAMBIO DETECTADO")
            print(f"{'='*60}")
        
        costo_unit_ars, costo_total_ars = self._resolve_costo_final(
            costo_unit_ars=costo_unit_ars,
            costo_total_ars=costo_total_ars,
            cantidad=cantidad,
            should_log=should_log,
        )
        
        # 🔥 Recalcular costos USD basándose en ARS y conversión
        usd_recalculado = False
        if conv_usd and conv_usd > 0:
            if costo_unit_ars:
                costo_unit_usd = float(costo_unit_ars) / float(conv_usd)
                usd_recalculado = True
            if costo_total_ars:
                costo_total_usd = float(costo_total_ars) / float(conv_usd)
                usd_recalculado = True
            if should_log:
                print(f"\n[CALC] Costos en USD (recalculados):")
                print(f"  costo_unit_usd = {costo_unit_ars} / {conv_usd} = {costo_unit_usd}")
                print(f"  costo_total_usd = {costo_total_ars} / {conv_usd} = {costo_total_usd}")
            
            # 🔥 CRÍTICO: Guardar USD recalculados en la BD
            if usd_recalculado:
                if should_log:
                    print(f"\n[PERSIST] 💾 Guardando costos USD a base de datos:")
                    print(f"  renglon_id={renglon_pk}")
                    print(f"  conv_usd={conv_usd} (conversión USD)")
                    print(f"  costo_unit_usd={costo_unit_usd}")
                    print(f"  costo_total_usd={costo_total_usd}")
                
                # Leer datos existentes para no sobreescribir otros campos
                existing = excel or {}
                self.db.upsert_renglon_excel(
                    renglon_id=renglon_pk,
                    unidad_medida=existing.get("unidad_medida"),
                    cantidad=existing.get("cantidad"),
                    marca=existing.get("marca"),
                    obs_usuario=existing.get("obs_usuario"),
                    conv_usd=conv_usd,  # Guardar en columna NUEVA
                    conversion_usd=conv_usd,  # Guardar en columna LEGACY
                    costo_unit_ars=costo_unit_ars,
                    costo_total_ars=costo_total_ars,
                    renta_minima=existing.get("renta_minima"),
                    costo_unit_usd=costo_unit_usd,
                    costo_total_usd=costo_total_usd,
                    precio_referencia=existing.get("precio_referencia"),
                    precio_referencia_subasta=existing.get("precio_referencia_subasta"),
                    updated_at=now_iso(),
                )
                
                if should_log:
                    print(f"  ✅ Costos USD guardados en BD (columnas: conv_usd + conversion_usd)")

        # REFACTORING: Actualizar cálculos con nuevos nombres de campos
        if should_log:
            print(f"\n[CALC] Precio aceptable ((1 + renta_minima) * costo):")
            print(f"  renta_minima={renta_minima} (fracción: 0.1=10%, 0.3=30%)")
        
        # Cálculos de precio aceptable (si hay datos, siempre recalcular para evitar valores stale)
        # renta_minima ahora es fracción (0.1 = 10%), entonces: precio = costo * (1 + renta_minima)
        if renta_minima is not None:
            precio_unit_aceptable = self._safe_mul((1.0 + renta_minima), costo_unit_ars)
            if should_log:
                print(f"  precio_unit_aceptable = (1 + {renta_minima}) * {costo_unit_ars} = {precio_unit_aceptable}")
            precio_total_aceptable = self._safe_mul((1.0 + renta_minima), costo_total_ars)
            if should_log:
                print(f"  precio_total_aceptable = (1 + {renta_minima}) * {costo_total_ars} = {precio_total_aceptable}")
        elif should_log:
            print(f"  precio_unit_aceptable (sin datos) = {precio_unit_aceptable}")
            print(f"  precio_total_aceptable (sin datos) = {precio_total_aceptable}")

        # Precio referencia unitario: usar el de Playwright/BD y solo derivar si falta.
        if should_log:
            print(f"\n[CALC] Precio referencia unitario:")
        if precio_ref_unitario is None and precio_referencia is not None:
            # precio_referencia es TOTAL, dividir por cantidad para obtener UNITARIO
            precio_ref_unitario = self._safe_div(precio_referencia, cantidad)
            if should_log:
                print(f"  precio_ref_unitario (derivado) = {precio_referencia} / {cantidad} = {precio_ref_unitario}")
        elif should_log:
            if precio_ref_unitario is not None:
                print(f"  precio_ref_unitario (existente) = {precio_ref_unitario}")
            else:
                print(f"  precio_ref_unitario (sin datos) = {precio_ref_unitario}")

        # Rentabilidad sobre referencia
        if should_log:
            print(f"\n[CALC] Rentabilidad referencia:")
        # Regla: priorizar comparación TOTAL vs TOTAL (más robusta), fallback UNIT vs UNIT.
        if precio_referencia is not None and costo_total_ars not in (None, 0):
            renta_referencia = (float(precio_referencia) / float(costo_total_ars)) - 1.0
            if should_log:
                print(f"  renta_referencia (TOTAL) = ({precio_referencia} / {costo_total_ars}) - 1 = {renta_referencia:.2%}")
        elif precio_ref_unitario is not None and costo_unit_ars not in (None, 0):
            renta_referencia = (float(precio_ref_unitario) / float(costo_unit_ars)) - 1.0
            if should_log:
                print(f"  renta_referencia (UNIT) = ({precio_ref_unitario} / {costo_unit_ars}) - 1 = {renta_referencia:.2%}")
        elif should_log:
            print(f"  renta_referencia (sin datos) = {renta_referencia}")

        # Precio unitario para mejorar (si no está en la BD)
        if should_log:
            print(f"\n[CALC] Precio para mejorar:")
        precio_unit_mejora = self._safe_div(oferta_min_val, cantidad)
        if should_log:
            print(f"  precio_unit_mejora = {oferta_min_val} / {cantidad} = {precio_unit_mejora}")

        # Rentabilidad para mejorar (basada en precio unitario para mejorar)
        if should_log:
            print(f"\n[CALC] Rentabilidad para mejorar:")
        if precio_unit_mejora is not None and costo_unit_ars not in (None, 0):
            renta_para_mejorar = (float(precio_unit_mejora) / float(costo_unit_ars)) - 1.0
            if should_log:
                print(f"  renta_para_mejorar = ({precio_unit_mejora} / {costo_unit_ars}) - 1 = {renta_para_mejorar:.2%}")
        elif should_log:
            print(f"  renta_para_mejorar (sin datos) = {renta_para_mejorar}")
        
        # 🔥 oferta_para_mejorar = oferta mínima actual (es la que hay que superar)
        oferta_para_mejorar = oferta_min_val
        if should_log:
            print(f"\n[CALC] Oferta para mejorar:")
            print(f"  oferta_para_mejorar = {oferta_para_mejorar} (oferta mínima actual)")

        cfg = self.db.get_renglon_config(renglon_id=renglon_pk)
        seguir = False
        oferta_mia = False
        utilidad_min_pct = self.config.utilidad_min_pct_default
        ocultar_bajo_umbral = self.config.ocultar_bajo_umbral_default

        if cfg:
            costo_subtotal = cfg.get("costo_subtotal")
            seguir = bool(cfg.get("seguir"))
            oferta_mia = bool(cfg.get("oferta_mia"))
            # 🔥 NO sobrescribir utilidad_min_pct desde config si viene de renta_minima
            if renta_minima is None:
                utilidad_min_pct = float(cfg.get("utilidad_min_pct", utilidad_min_pct))
            ocultar_bajo_umbral = bool(cfg.get("ocultar_bajo_umbral", ocultar_bajo_umbral))

        # ---------------------------------------------------------------
        # AUTO-DETECCIÓN: mi_id_proveedor
        # ---------------------------------------------------------------
        mejor_id_proveedor = payload.get("mejor_id_proveedor")

        # Cargar mi_id_proveedor desde cache (o DB si no está cacheado)
        if subasta_id not in self._mi_id_proveedor_cache:
            self._mi_id_proveedor_cache[subasta_id] = self.db.get_mi_id_proveedor(subasta_id=subasta_id)
        mi_id_prov = self._mi_id_proveedor_cache.get(subasta_id)

        # Determinar si la mejor oferta es nuestra
        oferta_mia_auto = bool(
            mejor_id_proveedor is not None
            and mi_id_prov is not None
            and str(mejor_id_proveedor).strip() == str(mi_id_prov).strip()
        )

        # Auto-merge: si detectamos automáticamente, también marcar oferta_mia
        if oferta_mia_auto:
            oferta_mia = True

        # Detectar OUTBID: estábamos vigentes y ahora no (cambio real en mejor oferta)
        prev_mia_auto = self._prev_oferta_mia_auto.get(renglon_pk, False)
        outbid = bool(prev_mia_auto and not oferta_mia_auto and changed and mi_id_prov is not None)
        self._prev_oferta_mia_auto[renglon_pk] = oferta_mia_auto
        # ---------------------------------------------------------------

        
        # 🔥 CRÍTICO: Derivar utilidad_min_pct de renta_minima (PRIORIDAD sobre config)
        if renta_minima is not None:
            # renta_minima = 0.15 → utilidad_min_pct = 15.0%
            utilidad_min_pct = renta_minima * 100.0
            if should_log:
                print(f"\n[CONFIG] Umbral de alerta derivado de RENTA MÍNIMA:")
                print(f"  renta_minima={renta_minima:.2f} (fracción) → utilidad_min_pct={utilidad_min_pct:.2f}%")

        base_cost = costo_subtotal
        if base_cost is None:
            # oferta_min_val viene como TOTAL, así que priorizamos costo TOTAL.
            if costo_total_ars is not None:
                base_cost = costo_total_ars
            elif costo_unit_ars is not None and cantidad not in (None, 0):
                base_cost = self._safe_mul(costo_unit_ars, cantidad)
            elif costo_unit_ars is not None:
                base_cost = costo_unit_ars

        if should_log:
            print(f"\n[CALC] Utilidad porcentual (CRÍTICO para coloración):")
            print(
                f"  base_cost = {base_cost} "
                f"(costo_subtotal={costo_subtotal}, costo_total_ars={costo_total_ars}, costo_unit_ars={costo_unit_ars})"
            )
            print(f"  oferta_min_val = {oferta_min_val}")
        
        utilidad_pct = None
        if base_cost is not None and base_cost > 0 and oferta_min_val is not None:
            utilidad_pct = ((float(oferta_min_val) - float(base_cost)) / float(base_cost)) * 100.0
            if should_log:
                print(f"  utilidad_pct = (({oferta_min_val} - {base_cost}) / {base_cost}) * 100 = {utilidad_pct:.2f}%")
        elif should_log:
            print(f"  utilidad_pct = None (falta base_cost o oferta)")

        # 🔥 Usar renta_para_mejorar como base de color si existe
        utilidad_para_alerta = utilidad_pct
        if renta_para_mejorar is not None:
            utilidad_para_alerta = float(renta_para_mejorar) * 100.0
            if should_log:
                print(f"  utilidad_para_alerta (renta_para_mejorar) = {utilidad_para_alerta:.2f}%")

        tracked = bool(seguir or (base_cost is not None))

        if should_log:
            print(f"\n[DECISION] AlertEngine.decide:")
            print(f"  tracked={tracked}, oferta_mia={oferta_mia}, oferta_mia_auto={oferta_mia_auto}, outbid={outbid}")
            if utilidad_para_alerta is not None:
                print(f"  utilidad_pct={utilidad_para_alerta:.2f}%, utilidad_min_pct={utilidad_min_pct:.2f}%")
            else:
                print(f"  utilidad_pct=None (sin datos), utilidad_min_pct={utilidad_min_pct:.2f}%")
            print(f"  ocultar_bajo_umbral={ocultar_bajo_umbral}, changed={changed}")

        # Log de evento OUTBID (auditoría)
        if outbid:
            self.db.insert_evento(
                nivel="WARN",
                tipo="OUTBID",
                mensaje=f"OUTBID: renglón {rid} — tu oferta fue superada (mejor_id={mejor_id_proveedor})",
                subasta_id=subasta_id,
                renglon_id=renglon_pk,
            )

        decision: AlertDecision = self.alert_engine.decide(
            tracked=tracked,
            oferta_mia=oferta_mia,
            oferta_mia_auto=oferta_mia_auto,
            outbid=outbid,
            utilidad_pct=utilidad_para_alerta,
            utilidad_min_pct=utilidad_min_pct,
            ocultar_bajo_umbral=ocultar_bajo_umbral,
            changed=bool(changed),
            http_status=http_status,
            mensaje=mensaje,
        )

        if should_log:
            print(f"  RESULTADO: style={decision.style.value}, hide={decision.hide}, highlight={decision.highlight}")
            print(f"  mensaje='{decision.message}'")
            print(f"{'='*60}\n")

        existing = excel or {}
        obs_cambio_texto = existing.get("obs_cambio")
        if hora_ultima_oferta:
            obs_cambio_texto = f"Ultima oferta: {hora_ultima_oferta}"
        elif mensaje:
            obs_cambio_texto = mensaje

        # Persistir campos de cálculo para que la UI los vea también en refresh desde BD.
        self.db.upsert_renglon_excel(
            renglon_id=renglon_pk,
            unidad_medida=unidad_medida,
            cantidad=cantidad,
            marca=marca,
            obs_usuario=obs_usuario,
            conv_usd=conv_usd,
            conversion_usd=conv_usd,
            costo_unit_usd=costo_unit_usd,
            costo_total_usd=costo_total_usd,
            costo_unit_ars=costo_unit_ars,
            costo_total_ars=costo_total_ars,
            renta_minima=renta_minima,
            precio_referencia=precio_referencia,
            precio_ref_unitario=precio_ref_unitario,
            renta_referencia=renta_referencia,
            precio_unit_aceptable=precio_unit_aceptable,
            precio_total_aceptable=precio_total_aceptable,
            precio_unit_mejora=precio_unit_mejora,
            renta_para_mejorar=renta_para_mejorar,
            oferta_para_mejorar=oferta_para_mejorar,
            mejor_oferta_txt=mejor_txt,
            obs_cambio=obs_cambio_texto,
            precio_referencia_subasta=existing.get("precio_referencia_subasta"),
            updated_at=now_iso(),
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
                    "obs_usuario": obs_usuario,
                    "conv_usd": conv_usd,
                    "costo_unit_usd": costo_unit_usd,
                    "costo_total_usd": costo_total_usd,
                    "costo_unit_ars": costo_unit_ars,
                    "costo_total_ars": costo_total_ars,
                    "renta_minima": renta_minima,
                    "precio_referencia": precio_referencia,
                    "precio_ref_unitario": precio_ref_unitario,
                    "renta_referencia": renta_referencia,
                    "precio_unit_aceptable": precio_unit_aceptable,
                    "precio_total_aceptable": precio_total_aceptable,
                    "precio_unit_mejora": precio_unit_mejora,
                    "renta_para_mejorar": renta_para_mejorar,
                    "oferta_para_mejorar": oferta_para_mejorar,
                    "mejor_oferta_txt": mejor_txt,  # 🔥 USAR VALOR DEL ESTADO, NO DE BD EXCEL
                    "obs_cambio": obs_cambio_texto,
                    "hora_ultima_oferta": hora_ultima_oferta,
                    "utilidad_pct": utilidad_pct,
                    "seguir": bool(seguir),
                    "oferta_mia": bool(oferta_mia),
                    "oferta_mia_auto": bool(oferta_mia_auto),
                    "outbid": bool(outbid),
                    "mejor_id_proveedor": mejor_id_proveedor,
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
        now_dt = datetime.now()
        last_err_dt = self.subasta_last_error_at.get(subasta_id)
        # Evitar escalar streak por múltiples errores del mismo ciclo/lote.
        # Contamos un nuevo "paso" de error solo si pasó una ventana mínima.
        error_window_seconds = 1.5
        if last_err_dt and (now_dt - last_err_dt).total_seconds() < error_window_seconds:
            streak = prev
        else:
            streak = prev + 1
            self.subasta_last_error_at[subasta_id] = now_dt
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

        detail = f"HTTP={http_status} streak={streak} -> {decision.action.value} ({decision.message})"
        if decision.action == SecurityAction.BACKOFF and decision.new_poll_seconds:
            detail = (
                f"{detail} poll={self.current_poll_seconds:.2f}s"
                f"→{float(decision.new_poll_seconds):.2f}s"
            )

        self.emit_ui(
            warn(
                EventType.HTTP_ERROR,
                detail,
                payload={
                    "http_status": http_status,
                    "id_cot": id_cot,
                    "streak": streak,
                },
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
