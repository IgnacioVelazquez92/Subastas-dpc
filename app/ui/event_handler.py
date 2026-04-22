# app/ui/event_handler.py
"""
Procesamiento de eventos desde Engine hacia UI.

Responsabilidad única: Convertir eventos del motor en cambios de estado de tabla.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from app.core.events import Event, EventType
from app.core.alert_engine import RowStyle, SoundCue
from app.ui.table_manager import TableManager
from app.ui.formatters import DisplayValues
from app.models.domain import UIRow
from app.utils.audio import play_outbid_alert


class EventProcessor:
    """Procesa eventos de Engine y actualiza tabla y UI."""
    
    def __init__(
        self,
        table_mgr: TableManager,
        rows_cache: dict[str, UIRow],
        status_label_setter,
        logger,
        audio_bell_fn,
        my_provider_ids_getter=None,
        provider_label_resolver=None,
    ):
        """
        Args:
            table_mgr: TableManager para actualizar tabla
            rows_cache: Dict compartido de UIRow por id_renglon
            status_label_setter: Función para setear status label (fn(text))
            logger: Logger widget para log (fn(msg))
            audio_bell_fn: Función para reproducir sonido de alerta (fn())
        """
        self.table_mgr = table_mgr
        self.rows_cache = rows_cache
        self.set_status = status_label_setter
        self.log = logger
        self.bell = audio_bell_fn
        self.get_my_provider_ids = my_provider_ids_getter
        self.resolve_provider_label = provider_label_resolver
        # Audio habilitado por defecto; se puede desactivar con MONITOR_ENABLE_SOUND=0
        self.sound_enabled = str(os.getenv("MONITOR_ENABLE_SOUND", "1")).strip().lower() in {
            "1", "true", "yes", "on"
        }
        self._outbid_blink_tokens: dict[str, int] = {}
        self._outbid_blink_jobs: dict[str, list[str]] = {}
        self._outbid_blink_seq = 0
        
        # Callbacks para LEDs (se asignan después en app.py)
        self.on_offer_changed = None  # Callback para LED de ofertas
        self.on_http_event = None  # Callback para LED HTTP (status_code)
        self.on_row_http_event = None  # Callback para LED por renglón
    
    def process_event(self, ev: Event) -> None:
        """Procesa un evento del motor."""
        # Despachar por tipo
        if ev.type == EventType.START:
            self.set_status("RUNNING")
            self.log("▶️  Sistema iniciado - recopilando datos...")
            return
        
        if ev.type == EventType.STOP:
            self.set_status("STOPPED")
            self.log("⏹️  Sistema detenido")
            return
        
        if ev.type == EventType.END:
            self.set_status("ENDED")
            self.log("✅ Proceso finalizado")
            return
        
        if ev.type == EventType.SNAPSHOT:
            # SNAPSHOT implica una petición exitosa (200 OK)
            try:
                if callable(self.on_http_event):
                    self.on_http_event(200)  # Implica éxito
            except Exception:
                pass
            self._handle_snapshot(ev)
            return
        
        if ev.type == EventType.UPDATE:
            # UPDATE también implica una petición exitosa
            try:
                if callable(self.on_http_event):
                    self.on_http_event(200)  # Implica éxito
            except Exception:
                pass
            self._handle_update(ev)
            try:
                payload = ev.payload or {}
                rid = payload.get("id_renglon")
                status = payload.get("http_status", 200)
                if callable(self.on_row_http_event) and rid is not None:
                    self.on_row_http_event(str(rid), int(status), "ok")
            except Exception:
                pass
            return
        
        if ev.type == EventType.HTTP_ERROR:
            payload = ev.payload or {}
            status = payload.get("http_status")
            if status is None:
                status = payload.get("status_code")
            if status is None:
                status = payload.get("status")
            self.log(f"🔴 Error HTTP {status}: {ev.message}")
            # Disparar LED de HTTP con código de error
            try:
                if callable(self.on_http_event):
                    self.on_http_event(int(status) if status is not None else 0)
            except Exception:
                pass
            try:
                rid = payload.get("id_renglon")
                if callable(self.on_row_http_event) and rid is not None:
                    self.on_row_http_event(
                        str(rid),
                        int(status) if status is not None else 0,
                        str(payload.get("error_kind") or ""),
                    )
            except Exception:
                pass
            return

        if ev.type == EventType.EXCEPTION:
            payload = ev.payload or {}
            rid = payload.get("id_renglon")
            msg = str(ev.message or "").lower()
            if callable(self.on_row_http_event) and rid is not None and "timeout" in msg:
                try:
                    self.on_row_http_event(str(rid), 0, "timeout")
                except Exception:
                    pass
            return

        if ev.type == EventType.HEARTBEAT:
            # Evitar spam en logs operativos de la app.
            return
        
        # Otros eventos (HEARTBEAT, DEBUG) se ignoran en logs
    
    def _handle_snapshot(self, ev: Event) -> None:
        """Maneja evento SNAPSHOT: reconstruye tabla desde cero."""
        payload = ev.payload or {}
        items = payload.get("renglones") or []
        self.table_mgr.rebuild_from_snapshot(items)
        self.rows_cache.clear()

        # Rehidratar cache para evitar duplicados en el primer UPDATE
        for item in items:
            rid = str(item.get("value") or "")
            if not rid:
                continue
            desc = str(item.get("text") or "")
            self.rows_cache[rid] = UIRow(
                id_renglon=rid,
                desc=desc,
                cantidad=item.get("cantidad"),
                items_por_renglon=item.get("items_por_renglon"),
            )
    
    def _handle_update(self, ev: Event) -> None:
        """Maneja evento UPDATE: crea o actualiza una fila."""
        payload = ev.payload or {}
        rid = payload.get("id_renglon")
        
        if not rid:
            return
        
        rid = str(rid)
        self._cancel_outbid_blink(rid)
        
        # Obtener o crear fila
        row = self.rows_cache.get(rid)
        is_new = False
        old_mejor_txt = None
        old_render_sig = None
        local_update_dt = datetime.now()
        
        if not row:
            row = UIRow(
                id_renglon=rid,
                desc=str(payload.get("desc") or "")
            )
            self.rows_cache[rid] = row
            if rid not in self.table_mgr.iids:
                self.table_mgr.insert_row(rid, row.desc)
            is_new = True
        else:
            # Rastrear cambios para logs mejorados
            old_mejor_txt = row.mejor_oferta_txt
            old_render_sig = self._row_render_signature(row)
        
        # Actualizar campos desde payload
        self._update_row_from_payload(row, payload, ev)
        
        # Determinar si renderizar:
        # - cambios del collector (payload.changed)
        # - cambios en campos mostrados (usuario/calculados), aunque no cambie la oferta
        new_render_sig = self._row_render_signature(row)
        data_changed = (old_render_sig is not None and old_render_sig != new_render_sig)
        should_render = is_new or bool(payload.get("changed")) or data_changed
        
        if should_render:
            if bool(payload.get("changed")):
                try:
                    if callable(self.on_offer_changed):
                        self.on_offer_changed()
                except Exception:
                    pass
            # Log inteligente de cambios
            if not is_new and old_mejor_txt != row.mejor_oferta_txt and row.mejor_oferta_txt:
                # Log detallado del cambio con timestamp Playwright y local.
                pw_ts = str(payload.get("hora_ultima_oferta") or "").strip()
                local_ts = local_update_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                delta_txt = self._compute_offer_delta_txt(playwright_time=pw_ts, local_dt=local_update_dt)
                prov_id = payload.get("mejor_id_proveedor")
                prov_alias = str(payload.get("mejor_proveedor_txt") or "").strip()
                prov_id_txt = str(prov_id).strip() if prov_id is not None and str(prov_id).strip() else ""
                resolved_provider = self._resolve_provider_label(prov_id)
                if resolved_provider != "-" and resolved_provider != prov_id_txt:
                    prov_txt = resolved_provider
                elif prov_alias and prov_id_txt:
                    prov_txt = f"{prov_alias} (id={prov_id_txt})"
                else:
                    prov_txt = prov_alias or prov_id_txt or "-"
                self.log(
                    f"📊 [{rid}] {row.desc}: {old_mejor_txt} → {row.mejor_oferta_txt} | "
                    f"prov={prov_txt} | playwright={pw_ts or '-'} | local={local_ts} | delta={delta_txt}"
                )
            
            # Aplicar decoraciones (estilo, sonido, etc.)
            style = self._apply_event_decorations(row, payload, ev)
            
            # Renderizar
            row_values = DisplayValues.build_row_values(row)
            self.table_mgr.render_row(rid, row_values, style)
            if bool(payload.get("outbid", False)):
                self._start_outbid_blink(rid=rid, row_values=row_values, final_style=style)

    def _row_render_signature(self, row: UIRow) -> tuple:
        """Firma compacta de campos visibles para detectar cambios de render."""
        return (
            row.desc,
            row.unidad_medida,
            row.cantidad,
            row.items_por_renglon,
            row.marca,
            row.obs_usuario,
            row.conv_usd,
            row.costo_unit_usd,
            row.costo_total_usd,
            row.costo_unit_ars,
            row.costo_total_ars,
            row.renta_minima,
            row.precio_referencia,
            row.precio_ref_unitario,
            row.renta_referencia,
            row.precio_unit_aceptable,
            row.precio_total_aceptable,
            row.precio_unit_mejora,
            row.renta_para_mejorar,
            row.oferta_para_mejorar,
            row.mejor_oferta_txt,
            getattr(row, "ultimo_oferente_txt", None),
            getattr(row, "oferta_min_txt", None),
            row.obs_cambio,
            row.seguir,
            row.oferta_mia,
            getattr(row, "oferta_mia_auto", False),
            getattr(row, "oferta_mia_slot", None),
            getattr(row, "mejor_id_proveedor", None),
        )
    
    def _update_row_from_payload(self, row: UIRow, payload: dict, ev: Event) -> None:
        """Copia datos de payload a UIRow."""
        # IDs y metadata
        if payload.get("id_cot") is not None:
            row.id_subasta = str(payload.get("id_cot"))
        if ev.subasta_id is not None:
            row.subasta_id = ev.subasta_id
        if ev.renglon_id is not None:
            row.renglon_pk = ev.renglon_id
        
        # Descripción
        row.desc = str(payload.get("desc") or row.desc)
        
        # Campos de oferta
        row.mejor_oferta_txt = payload.get("mejor_oferta_txt")
        row.oferta_min_txt = payload.get("oferta_min_txt")
        
        # OBS / CAMBIO: usar texto provisto por backend (hora real de oferta)
        msg = str(payload.get("mensaje") or "")
        obs_cambio = payload.get("obs_cambio")
        if obs_cambio:
            row.obs_cambio = str(obs_cambio)
        elif msg:
            row.obs_cambio = msg
        
        # Datos técnicos (REFACTORED)
        row.unidad_medida = payload.get("unidad_medida")
        row.cantidad = payload.get("cantidad")
        row.items_por_renglon = payload.get("items_por_renglon")
        row.marca = payload.get("marca")
        row.obs_usuario = payload.get("obs_usuario")
        row.conv_usd = payload.get("conv_usd")
        row.costo_unit_usd = payload.get("costo_unit_usd")
        row.costo_total_usd = payload.get("costo_total_usd")
        row.costo_unit_ars = payload.get("costo_unit_ars")
        row.costo_total_ars = payload.get("costo_total_ars")
        row.renta_minima = payload.get("renta_minima")
        
        # Cálculos derivados (REFACTORED)
        row.precio_referencia = payload.get("precio_referencia")
        row.precio_ref_unitario = payload.get("precio_ref_unitario")
        row.renta_referencia = payload.get("renta_referencia")
        row.precio_unit_aceptable = payload.get("precio_unit_aceptable")
        row.precio_total_aceptable = payload.get("precio_total_aceptable")
        row.precio_unit_mejora = payload.get("precio_unit_mejora")
        row.renta_para_mejorar = payload.get("renta_para_mejorar")
        row.oferta_para_mejorar = payload.get("oferta_para_mejorar")
        
        # Flags
        row.seguir = bool(payload.get("seguir", row.seguir))
        row.oferta_mia = bool(payload.get("oferta_mia", row.oferta_mia))
        row.oferta_mia_auto = bool(payload.get("oferta_mia_auto", row.oferta_mia_auto))
        matched_slot = payload.get("matched_my_provider_slot")
        if matched_slot in (1, 2, 3):
            row.oferta_mia_slot = int(matched_slot)
        if "mejor_id_proveedor" in payload:
            row.mejor_id_proveedor = payload.get("mejor_id_proveedor")
        if "mejor_proveedor_txt" in payload:
            row.mejor_proveedor_txt = payload.get("mejor_proveedor_txt")
        row.ultimo_oferente_txt = self._build_provider_display(
            provider_id=row.mejor_id_proveedor,
            provider_txt=row.mejor_proveedor_txt,
        )
        if self._matches_my_provider(row.mejor_id_proveedor):
            row.oferta_mia_auto = True
            row.oferta_mia = True
            if row.oferta_mia_slot not in (1, 2, 3):
                row.oferta_mia_slot = self._resolve_my_provider_slot(row.mejor_id_proveedor)
        else:
            row.oferta_mia_slot = None

    def _get_my_provider_ids(self) -> set[str]:
        if not callable(self.get_my_provider_ids):
            return set()
        try:
            value = self.get_my_provider_ids()
        except Exception:
            return set()
        if value is None:
            return set()
        if isinstance(value, str):
            normalized = str(value).strip()
            return {normalized} if normalized else set()
        try:
            return {str(item).strip() for item in value if str(item).strip()}
        except Exception:
            return set()

    def _matches_my_provider(self, provider_id: object) -> bool:
        my_provider_ids = self._get_my_provider_ids()
        best_provider_id = str(provider_id or "").strip()
        return bool(my_provider_ids and best_provider_id and best_provider_id in my_provider_ids)

    def _resolve_my_provider_slot(self, provider_id: object) -> int | None:
        raw = str(provider_id or "").strip()
        if not raw or not callable(self.get_my_provider_ids):
            return None
        try:
            values = self.get_my_provider_ids() or ()
        except Exception:
            return None
        if isinstance(values, str):
            ordered_ids = [str(values).strip()] if str(values).strip() else []
        else:
            ordered_ids = [str(item).strip() for item in values if str(item).strip()]
        for idx, provider in enumerate(ordered_ids, start=1):
            if provider == raw:
                return idx
        return None

    def _resolve_provider_label(self, provider_id: object) -> str:
        raw = str(provider_id or "").strip()
        if not raw:
            return "-"
        if callable(self.resolve_provider_label):
            try:
                resolved = str(self.resolve_provider_label(raw) or "").strip()
                if resolved:
                    return resolved
            except Exception:
                pass
        return raw

    def _build_provider_display(self, *, provider_id: object, provider_txt: object) -> str:
        raw_id = str(provider_id or "").strip()
        portal_txt = str(provider_txt or "").strip()
        resolved = self._resolve_provider_label(provider_id)
        if resolved and resolved != "-" and resolved != raw_id:
            return resolved
        if portal_txt and raw_id:
            return f"{portal_txt} (id={raw_id})"
        return portal_txt or raw_id or ""
    
    def _apply_event_decorations(self, row: UIRow, payload: dict, ev: Event) -> str:
        """
        Aplica decoraciones visuales/sonoras.
        
        Returns:
            style (RowStyle) a usar para renderizar
        """
        style = payload.get("alert_style") or RowStyle.NORMAL.value
        sound = payload.get("sound") or SoundCue.NONE.value
        highlight = bool(payload.get("highlight", False))
        outbid = bool(payload.get("outbid", False))
        if self._matches_my_provider(getattr(row, "mejor_id_proveedor", None)) and not outbid:
            style = self._resolve_my_offer_style(row).value

        # OUTBID → sonido WAV de alerta + log específico
        if outbid:
            new_provider = self._resolve_provider_label(payload.get("mejor_id_proveedor"))
            my_provider = self._resolve_provider_label(payload.get("outbid_my_provider_id"))
            if self.sound_enabled:
                try:
                    play_outbid_alert()
                except Exception:
                    pass
                # Fallback explícito: asegurar señal audible aunque falle el backend de audio.
                try:
                    self.bell()
                except Exception:
                    pass
            self.log(
                f"🔔 [{row.id_renglon}] ¡OFERTA SUPERADA! "
                f"(mi ID: {my_provider} -> nuevo proveedor: {new_provider})"
            )
            return style

        # Reproducir sonido genérico si corresponde
        if self.sound_enabled and sound != SoundCue.NONE.value and highlight:
            try:
                self.bell()
            except Exception:
                pass

        return style

    @staticmethod
    def _resolve_my_offer_style(row: UIRow) -> RowStyle:
        slot = getattr(row, "oferta_mia_slot", None)
        if slot == 1:
            return RowStyle.MY_OFFER_1
        if slot == 2:
            return RowStyle.MY_OFFER_2
        if slot == 3:
            return RowStyle.MY_OFFER_3
        return RowStyle.MY_OFFER

    def _cancel_outbid_blink(self, rid: str) -> None:
        jobs = self._outbid_blink_jobs.pop(rid, [])
        for job_id in jobs:
            try:
                self.table_mgr.tree.after_cancel(job_id)
            except Exception:
                pass
        self._outbid_blink_tokens.pop(rid, None)

    def _start_outbid_blink(self, *, rid: str, row_values: tuple[str, ...], final_style: str) -> None:
        """
        Parpadeo visual para OUTBID:
        alterna naranja/estilo-final y termina SIEMPRE en estilo-final.
        """
        self._cancel_outbid_blink(rid)
        self._outbid_blink_seq += 1
        token = self._outbid_blink_seq
        self._outbid_blink_tokens[rid] = token
        self._outbid_blink_jobs[rid] = []

        sequence = [
            RowStyle.OUTBID.value,
            final_style,
            RowStyle.OUTBID.value,
            final_style,
        ]
        step_ms = 220

        last_idx = len(sequence) - 1
        for idx, style in enumerate(sequence):
            delay_ms = idx * step_ms

            def _apply_style(s=style, t=token, is_last=(idx == last_idx)):
                if self._outbid_blink_tokens.get(rid) != t:
                    return
                self.table_mgr.render_row(rid, row_values, s)
                if is_last:
                    self._outbid_blink_tokens.pop(rid, None)
                    self._outbid_blink_jobs.pop(rid, None)

            if delay_ms == 0:
                _apply_style()
            else:
                try:
                    job = self.table_mgr.tree.after(delay_ms, _apply_style)
                    self._outbid_blink_jobs[rid].append(job)
                except Exception:
                    pass

    @staticmethod
    def _compute_offer_delta_txt(*, playwright_time: str, local_dt: datetime) -> str:
        """
        Calcula delta aproximado entre hora de Playwright (HH:MM[:SS]) y hora local.
        Si no se puede parsear, devuelve '-'.
        """
        if not playwright_time:
            return "-"
        # Intentar parseo directo ISO/fecha completa primero.
        try:
            pw_dt_full = datetime.fromisoformat(playwright_time)
            return f"{(local_dt - pw_dt_full).total_seconds():.3f}s"
        except Exception:
            pass
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                t = datetime.strptime(playwright_time, fmt).time()
                pw_dt = datetime.combine(local_dt.date(), t)
                delta = (local_dt - pw_dt).total_seconds()
                if delta < -3600:
                    pw_dt = pw_dt - timedelta(days=1)
                    delta = (local_dt - pw_dt).total_seconds()
                return f"{delta:.3f}s"
            except Exception:
                continue
        return "-"
