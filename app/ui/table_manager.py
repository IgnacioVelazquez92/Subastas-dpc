# app/ui/table_manager.py
"""
Gestión de tabla Treeview.

Responsabilidad única: Crear, actualizar, renderizar la tabla sin tocar lógica de eventos.
"""

from __future__ import annotations

from tkinter import ttk
from dataclasses import dataclass
from typing import Optional

from app.core.alert_engine import RowStyle
from app.ui.formatters import DisplayValues


@dataclass(frozen=True)
class TableConfig:
    """Configuración estática de tabla (nombres, anchos, estilos)."""
    
    columns: tuple[str, ...] = (
        "id_subasta", "item", "desc", "unidad", "cantidad", "marca", "obs",
        "conv_usd", "costo_usd", "costo_final", "subtotal_costo",
        "renta", "p_unit_min", "subtotal", "renta_ref", "p_unit_mejora",
        "precio_ref_subasta", "mejor", "subtotal_mejorar", "dif_unit",
        "renta_dpc", "obs_det",
    )
    
    column_labels: dict[str, str] = None
    column_widths: dict[str, int] = None
    
    def __post_init__(self):
        # Inicializar defaults si no se proporcionan
        if self.column_labels is None:
            object.__setattr__(self, 'column_labels', {
                "id_subasta": "ID SUBASTA",
                "item": "ITEM",
                "desc": "DESCRIPCION",
                "mejor": "Mejor oferta",
                "precio_ref_subasta": "Precio ref. (subasta)",
                "obs_det": "Obs / Cambio",
                "unidad": "UNIDAD DE MEDIDA",
                "cantidad": "CANTIDAD",
                "marca": "MARCA",
                "obs": "Observaciones",
                "conv_usd": "CONVERSIÓN USD",
                "costo_usd": "COSTO USD",
                "costo_final": "COSTO FINAL PESOS",
                "subtotal_costo": "SUBTOTAL COSTO PESOS",
                "renta": "RENTA",
                "p_unit_min": "P.UNIT MINIMO",
                "subtotal": "SUBTOTAL",
                "renta_ref": "RENTA/ REF",
                "p_unit_mejora": "P. UNIT MEJORA",
                "subtotal_mejorar": "SUBTOTAL PARA MEJORAR",
                "dif_unit": "dif unit",
                "renta_dpc": "Renta DPC",
            })
        
        if self.column_widths is None:
            object.__setattr__(self, 'column_widths', {
                "id_subasta": 110, "item": 90, "desc": 260, "mejor": 140,
                "precio_ref_subasta": 140, "obs_det": 220, "unidad": 130,
                "cantidad": 90, "marca": 120, "obs": 200, "conv_usd": 120,
                "costo_usd": 110, "costo_final": 130, "subtotal_costo": 140,
                "renta": 90, "p_unit_min": 120, "subtotal": 120, "renta_ref": 100,
                "p_unit_mejora": 120, "subtotal_mejorar": 150, "dif_unit": 100,
                "renta_dpc": 100,
            })


class TableManager:
    """Gestiona la tabla Treeview: estructura, inserción, renderizado."""
    
    def __init__(self, tree: ttk.Treeview):
        self.tree = tree
        self.config = TableConfig()
        
        # Cache local para rápido acceso: id_renglon -> iid (tree internal id)
        self.iids: dict[str, str] = {}
        
    def initialize(self) -> None:
        """Configura estructura inicial de la tabla."""
        # Configurar columnas
        for col in self.config.columns:
            label = self.config.column_labels.get(col, col)
            width = self.config.column_widths.get(col, 120)
            
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor="w")
        
        # Configurar estilos de filas
        self.tree.tag_configure(RowStyle.NORMAL.value, background="")
        self.tree.tag_configure(RowStyle.TRACKED.value, background="#e7f1ff")
        self.tree.tag_configure(RowStyle.WARNING.value, background="#fff3cd")
        self.tree.tag_configure(RowStyle.DANGER.value, background="#f8d7da")
        self.tree.tag_configure(RowStyle.SUCCESS.value, background="#d1e7dd")
        
        # Bindings para sorting en columnas clave
        self.tree.heading("item", command=lambda: self._sort_by_column("item", numeric=True))
        self.tree.heading("desc", command=lambda: self._sort_by_column("desc", numeric=False))
        
        # Estado de sorting (alternancia ascendente/descendente)
        self._sort_state: dict[str, bool] = {}
    
    def clear(self) -> None:
        """Limpia toda la tabla."""
        self.tree.delete(*self.tree.get_children())
        self.iids.clear()
    
    def rebuild_from_snapshot(self, items: list[dict]) -> None:
        """
        Reconstruye tabla desde un snapshot (inicio de sesión).
        
        Args:
            items: List de dicts con 'value' (id_renglon) y 'text' (descripción)
        """
        self.clear()
        
        for item in items:
            rid = str(item.get("value") or "")
            desc = str(item.get("text") or "")
            
            if not rid:
                continue
            
            self.insert_row(rid, desc)
    
    def insert_row(self, id_renglon: str, desc: str) -> str:
        """
        Inserta fila nueva en tabla.
        
        Returns:
            iid (internal tree id) para referencia posterior
        """
        # Valores iniciales: id_subasta vacío, id_renglon, desc truncado, resto vacío
        initial_values = (
            "",  # id_subasta (se llena luego desde evento)
            id_renglon,
            desc[:80] if len(desc) > 80 else desc,
        ) + ("",) * (len(self.config.columns) - 3)
        
        iid = self.tree.insert(
            "",
            "end",
            values=initial_values,
            tags=(RowStyle.NORMAL.value,),
        )
        
        self.iids[id_renglon] = iid
        return iid
    
    def render_row(self, id_renglon: str, row_values: tuple[str, ...], style: str) -> None:
        """
        Actualiza renderizado de una fila.
        
        Args:
            id_renglon: Identificador de renglón
            row_values: Tupla de strings (de DisplayValues.build_row_values)
            style: Estilo de la fila (RowStyle.*)
        """
        iid = self.iids.get(id_renglon)
        if not iid:
            return
        
        self.tree.item(iid, values=row_values, tags=(style,))
    
    def remove_row(self, id_renglon: str) -> None:
        """Elimina una fila por id_renglon."""
        iid = self.iids.get(id_renglon)
        if iid:
            self.tree.delete(iid)
            del self.iids[id_renglon]
    
    def get_selected_row_id(self) -> Optional[str]:
        """
        Retorna id_renglon de la fila seleccionada o None.
        """
        sel = self.tree.selection()
        if not sel:
            return None
        
        iid = sel[0]
        values = self.tree.item(iid, "values")
        if len(values) < 2:
            return None
        
        return values[1]  # id_renglon está en posición 1
    
    def get_config(self) -> TableConfig:
        """Retorna configuración estática de tabla."""
        return self.config
    
    def _sort_by_column(self, col: str, *, numeric: bool) -> None:
        """
        Ordena tabla por columna.
        
        Args:
            col: Nombre de columna
            numeric: Si True, ordena numéricamente; si False, por string
        """
        data = []
        for iid in self.tree.get_children(""):
            value = self.tree.set(iid, col)
            data.append((value, iid))
        
        # Alternar ascendente/descendente
        reverse = self._sort_state.get(col, False)
        self._sort_state[col] = not reverse
        
        def sort_key(item):
            val = item[0]
            if numeric:
                try:
                    return float(val)
                except Exception:
                    return 0.0
            return str(val).lower()
        
        data.sort(key=sort_key, reverse=reverse)
        
        # Re-ordenar items en tree
        for idx, (_, iid) in enumerate(data):
            self.tree.move(iid, "", idx)
