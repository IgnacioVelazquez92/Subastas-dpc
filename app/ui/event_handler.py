# app/ui/event_handler.py
"""
Procesamiento de eventos desde Engine hacia UI.

Responsabilidad única: Convertir eventos del motor en cambios de estado de tabla.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from app.core.events import Event, EventType
from app.core.alert_engine import RowStyle, SoundCue
from app.ui.table_manager import TableManager
from app.ui.formatters import DisplayValues, DataFormatter
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
        
        # Callbacks para LEDs (se asignan después en app.py)
        self.on_offer_changed = None  # Callback para LED de ofertas
        self.on_http_event = None  # Callback para LED HTTP (status_code)
    
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
            return
        
        if ev.type == EventType.HTTP_ERROR:
            payload = ev.payload or {}
            status = (
                payload.get("http_status")
                or payload.get("status_code")
                or payload.get("status")
            )
            self.log(f"🔴 Error HTTP {status}: {ev.message}")
            # Disparar LED de HTTP con código de error
            try:
                if callable(self.on_http_event):
                    self.on_http_event(int(status) if status is not None else 0)
            except Exception:
                pass
            return

        if ev.type == EventType.HEARTBEAT:
            # Evitar spam en logs operativos.
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
            self.rows_cache[rid] = UIRow(id_renglon=rid, desc=desc)
    
    def _handle_update(self, ev: Event) -> None:
        """Maneja evento UPDATE: crea o actualiza una fila."""
        payload = ev.payload or {}
        rid = payload.get("id_renglon")
        
        if not rid:
            return
        
        rid = str(rid)
        
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
            # Log inteligente de cambios
            if not is_new and old_mejor_txt != row.mejor_oferta_txt and row.mejor_oferta_txt:
                # Log detallado del cambio con timestamp Playwright y local.
                pw_ts = str(payload.get("hora_ultima_oferta") or "").strip()
                local_ts = local_update_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                delta_txt = self._compute_offer_delta_txt(playwright_time=pw_ts, local_dt=local_update_dt)
                self.log(
                    f"📊 [{rid}] {row.desc}: {old_mejor_txt} → {row.mejor_oferta_txt} | "
                    f"playwright={pw_ts or '-'} | local={local_ts} | delta={delta_txt}"
                )
                # Disparar LED de cambios de oferta (será implementado en app.py)
                try:
                    if hasattr(self, 'on_offer_changed'):
                        self.on_offer_changed()
                except Exception:
                    pass
            
            # Aplicar decoraciones (estilo, sonido, etc.)
            style = self._apply_event_decorations(row, payload, ev)
            
            # Renderizar
            row_values = DisplayValues.build_row_values(row)
            self.table_mgr.render_row(rid, row_values, style)

    def _row_render_signature(self, row: UIRow) -> tuple:
        """Firma compacta de campos visibles para detectar cambios de render."""
        return (
            row.desc,
            row.unidad_medida,
            row.cantidad,
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
            getattr(row, "oferta_min_txt", None),
            row.obs_cambio,
            row.seguir,
            row.oferta_mia,
            getattr(row, "oferta_mia_auto", False),
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
        if "mejor_id_proveedor" in payload:
            row.mejor_id_proveedor = payload.get("mejor_id_proveedor")
    
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

        # OUTBID → sonido WAV de alerta + log específico
        if outbid:
            try:
                play_outbid_alert()
            except Exception:
                try:
                    self.bell()
                except Exception:
                    pass
            self.log(
                f"🔔 [{row.id_renglon}] ¡OFERTA SUPERADA! "
                f"(nuevo proveedor: {payload.get('mejor_id_proveedor', '?')})"
            )
            return style

        # Reproducir sonido genérico si corresponde
        if sound != SoundCue.NONE.value and highlight:
            try:
                self.bell()
            except Exception:
                pass

        return style

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
