# app/ui/event_handler.py
"""
Procesamiento de eventos desde Engine hacia UI.

Responsabilidad única: Convertir eventos del motor en cambios de estado de tabla.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.core.events import Event, EventType
from app.core.alert_engine import RowStyle, SoundCue
from app.ui.table_manager import TableManager
from app.ui.formatters import DisplayValues, DataFormatter
from app.models.domain import UIRow


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
    
    def process_event(self, ev: Event) -> None:
        """Procesa un evento del motor."""
        # Log del evento
        self.log(f"[{ev.level}] {ev.type}: {ev.message}")
        
        # Despachar por tipo
        if ev.type == EventType.START:
            self.set_status("RUNNING")
            return
        
        if ev.type == EventType.STOP:
            self.set_status("STOPPED")
            return
        
        if ev.type == EventType.END:
            self.set_status("ENDED")
            return
        
        if ev.type == EventType.SNAPSHOT:
            self._handle_snapshot(ev)
            return
        
        if ev.type == EventType.UPDATE:
            self._handle_update(ev)
            return
        
        # Otros eventos (HEARTBEAT, HTTP_ERROR) se logean pero no cambian tabla
    
    def _handle_snapshot(self, ev: Event) -> None:
        """Maneja evento SNAPSHOT: reconstruye tabla desde cero."""
        payload = ev.payload or {}
        items = payload.get("renglones") or []
        self.table_mgr.rebuild_from_snapshot(items)
        self.rows_cache.clear()
    
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
        
        if not row:
            row = UIRow(
                id_renglon=rid,
                desc=str(payload.get("desc") or "")
            )
            self.rows_cache[rid] = row
            self.table_mgr.insert_row(rid, row.desc)
            is_new = True
        
        # Actualizar campos desde payload
        self._update_row_from_payload(row, payload, ev)
        
        # Determinar si renderizar
        should_render = is_new or bool(payload.get("changed", False))
        
        if should_render:
            # Aplicar decoraciones (estilo, sonido, etc.)
            style = self._apply_event_decorations(row, payload, ev)
            
            # Renderizar
            row_values = DisplayValues.build_row_values(row)
            self.table_mgr.render_row(rid, row_values, style)
    
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
        row.mejor_txt = payload.get("mejor_oferta_txt")
        row.oferta_min_txt = payload.get("oferta_min_txt")
        row.precio_ref_subasta = payload.get("precio_referencia_subasta")
        
        # Mensaje con timestamp si hay cambio
        msg = str(payload.get("mensaje") or "")
        changed = bool(payload.get("changed", False))
        if changed:
            ts = datetime.now().strftime("%H:%M:%S")
            row.obs_det = f"{msg} | cambio {ts}" if msg else f"Cambio detectado | {ts}"
        else:
            row.obs_det = msg or row.obs_det
        
        # Datos técnicos
        row.unidad_medida = payload.get("unidad_medida")
        row.cantidad = payload.get("cantidad")
        row.marca = payload.get("marca")
        row.observaciones = payload.get("observaciones")
        row.conversion_usd = payload.get("conversion_usd")
        row.costo_usd = payload.get("costo_usd")
        row.costo_final_pesos = payload.get("costo_final_pesos")
        row.renta = payload.get("renta")
        
        # Cálculos derivados
        row.subtotal_para_mejorar = payload.get("subtotal_para_mejorar")
        row.subtotal_costo_pesos = payload.get("subtotal_costo_pesos")
        row.p_unit_minimo = payload.get("p_unit_minimo")
        row.subtotal = payload.get("subtotal")
        row.renta_ref = payload.get("renta_ref")
        row.p_unit_mejora = payload.get("p_unit_mejora")
        row.dif_unit = payload.get("dif_unit")
        row.renta_dpc = payload.get("renta_dpc")
        
        # Flags
        row.seguir = bool(payload.get("seguir", row.seguir))
        row.oferta_mia = bool(payload.get("oferta_mia", row.oferta_mia))
    
    def _apply_event_decorations(self, row: UIRow, payload: dict, ev: Event) -> str:
        """
        Aplica decoraciones visuales/sonoras.
        
        Returns:
            style (RowStyle) a usar para renderizar
        """
        style = payload.get("alert_style") or RowStyle.NORMAL.value
        sound = payload.get("sound") or SoundCue.NONE.value
        highlight = bool(payload.get("highlight", False))
        
        # Reproducir sonido si corresponde
        if sound != SoundCue.NONE.value and highlight:
            try:
                self.bell()
            except Exception:
                pass
        
        return style
