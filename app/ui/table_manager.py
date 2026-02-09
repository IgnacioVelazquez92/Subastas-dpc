# app/ui/table_manager.py
"""
Gestión de tabla Treeview.

Responsabilidad única: Crear, actualizar, renderizar la tabla sin tocar lógica de eventos.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass
from typing import Optional

# Asegúrate de que estos imports coincidan con tu estructura de carpetas
from app.core.alert_engine import RowStyle
from app.ui.formatters import DisplayValues, DataFormatter


class Tooltip:
    """Tooltip simple para mostrar texto al pasar mouse sobre headers (Clase auxiliar)."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0
        self.widget.bind("<Enter>", self.showtip, add="+")
        self.widget.bind("<Leave>", self.hidetip, add="+")

    def showtip(self, event=None):
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, background="#ffffe0", relief="solid", borderwidth=1, font=("Segoe UI", 9))
        label.pack(ipadx=3, ipady=2)

    def hidetip(self, event=None):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()


@dataclass(frozen=True)
class TableConfig:
    """Configuración estática de tabla (nombres, anchos, estilos)."""
    
    columns: tuple[str, ...] = (
        # IDs y básicos (Playwright)
        "id_subasta", "item", "desc", "cantidad",
        # Metadata usuario
        "unidad_medida", "marca", "obs_usuario",
        # Costos (bidireccionales)
        "conv_usd", "costo_unit_usd", "costo_total_usd",
        "costo_unit_ars", "costo_total_ars",
        # Rentabilidad mínima aceptable
        "renta_minima", "precio_unit_aceptable", "precio_total_aceptable",
        # Referencia de subasta
        "precio_referencia", "precio_ref_unitario", "renta_referencia",
        # Mejora en subasta
        "mejor_oferta", "oferta_para_mejorar",
        "precio_unit_mejora", "renta_para_mejorar",
        # Observaciones
        "obs_cambio",
    )
    
    column_labels: dict[str, str] = None  # Nombres CORTOS para headers
    column_tooltips: dict[str, str] = None  # Nombres COMPLETOS para tooltips
    column_widths: dict[str, int] = None
    
    def __post_init__(self):
        # BEST PRACTICE: Headers en 2 líneas (con \n)
        if self.column_labels is None:
            object.__setattr__(self, 'column_labels', {
                "id_subasta": "ID\nSUBASTA",
                "item": "Item",
                "desc": "Descripción",
                "cantidad": "Cantidad",
                "unidad_medida": "Unidad\nMedida",
                "marca": "Marca",
                "obs_usuario": "Obs\nUsuario",
                "conv_usd": "Conv\nUSD",
                "costo_unit_usd": "Costo Unit\nUSD",
                "costo_total_usd": "Costo Total\nUSD",
                "costo_unit_ars": "Costo Unit\nARS",
                "costo_total_ars": "Costo Total\nARS",
                "renta_minima": "Renta\nMín %",
                "precio_unit_aceptable": "P. Unit\nAceptable",
                "precio_total_aceptable": "P. Total\nAceptable",
                "precio_referencia": "P.\nReferencia",
                "precio_ref_unitario": "P. Referencia\nUnitario",
                "renta_referencia": "Renta\nReferencia %",
                "mejor_oferta": "Mejor\nOferta",
                "oferta_para_mejorar": "Oferta a\nMejorar",
                "precio_unit_mejora": "P. Unit a \nMejorar",
                "renta_para_mejorar": "Renta a \nMejorar %",
                "obs_cambio": "Obs /\nCambio",
            })
        
        # Tooltips: nombres COMPLETOS
        if self.column_tooltips is None:
            object.__setattr__(self, 'column_tooltips', {
                "id_subasta": "ID SUBASTA",
                "item": "ITEM",
                "desc": "DESCRIPCION",
                "cantidad": "CANTIDAD",
                "unidad_medida": "UNIDAD DE MEDIDA",
                "marca": "MARCA",
                "obs_usuario": "OBS USUARIO",
                "conv_usd": "CONVERSIÓN USD",
                "costo_unit_usd": "COSTO UNIT USD",
                "costo_total_usd": "COSTO TOTAL USD",
                "costo_unit_ars": "COSTO UNIT ARS",
                "costo_total_ars": "COSTO TOTAL ARS",
                "renta_minima": "RENTA MINIMA ACEPTABLE",
                "precio_unit_aceptable": "PRECIO UNIT ACEPTABLE",
                "precio_total_aceptable": "PRECIO TOTAL ACEPTABLE",
                "precio_referencia": "PRECIO DE REFERENCIA",
                "precio_ref_unitario": "PRECIO DE REFERENCIA UNITARIO",
                "renta_referencia": "RENTA REFERENCIA",
                "mejor_oferta": "MEJOR OFERTA ACTUAL",
                "oferta_para_mejorar": "OFERTA PARA MEJORAR",
                "precio_unit_mejora": "PRECIO UNITARIO MEJORA",
                "renta_para_mejorar": "RENTA PARA MEJORAR",
                "obs_cambio": "OBS / CAMBIO",
            })
        
        if self.column_widths is None:
            object.__setattr__(self, 'column_widths', {
                "id_subasta": 110,
                "item": 90,
                "desc": 260,
                "cantidad": 90,
                "unidad_medida": 130,
                "marca": 120,
                "obs_usuario": 200,
                "conv_usd": 120,
                "costo_unit_usd": 130,
                "costo_total_usd": 130,
                "costo_unit_ars": 130,
                "costo_total_ars": 130,
                "renta_minima": 110,
                "precio_unit_aceptable": 150,
                "precio_total_aceptable": 150,
                "precio_referencia": 140,
                "precio_ref_unitario": 140,
                "renta_referencia": 110,
                "mejor_oferta": 140,
                "oferta_para_mejorar": 150,
                "precio_unit_mejora": 140,
                "renta_para_mejorar": 110,
                "obs_cambio": 220,
            })


class TableManager:
    """Gestiona la tabla Treeview: estructura, inserción, renderizado."""
    
    # Altura definida para que quepan 2 líneas de texto en el header
    ROW_HEIGHT = 45 

    def __init__(self, tree: ttk.Treeview):
        self.tree = tree
        self.config = TableConfig()
        
        # Cache local para rápido acceso: id_renglon -> iid (tree internal id)
        self.iids: dict[str, str] = {}
        
        # Variables internas para tooltips y ordenamiento
        self._current_tooltip = None
        self._tooltip_col = None
        self._sort_state: dict[str, bool] = {}
        self._detached: set[str] = set()
        # Para "renta_para_mejorar" queremos empezar con orden descendente
        self._sort_state["renta_para_mejorar"] = True
    
    @staticmethod
    def get_default_config() -> TableConfig:
        """Retorna la configuración por defecto de tabla."""
        return TableConfig()
    
    def initialize(self) -> None:
        """Configura estructura inicial de la tabla con estilos corregidos."""
        
        # --- CORRECCIÓN DE ALTURA DE FILAS Y ENCABEZADOS ---
        style = ttk.Style()
        # Esto aumenta la altura de TODAS las filas (incluyendo headers implícitamente en muchos temas)
        # permitiendo que el \n se vea correctamente.
        style.configure("Treeview", rowheight=self.ROW_HEIGHT) 
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), padding=(5, 5, 5, 25))

        # Primero, establecer las columnas en el treeview
        self.tree.configure(columns=self.config.columns)
        
        # Configurar cada columna
        for col in self.config.columns:
            label = self.config.column_labels.get(col, col)
            width = self.config.column_widths.get(col, 120)
            
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor="w")
        
        # Asociar tooltips con la tabla
        self._setup_column_tooltips()
        
        # --- CONFIGURACIÓN DE COLORES ESTILO EXCEL ---
        self.tree.tag_configure(RowStyle.NORMAL.value, background="", foreground="")
        self.tree.tag_configure(RowStyle.TRACKED.value, background="#e7f1ff", foreground="")
        
        # Éxito (Verde Excel)
        self.tree.tag_configure(RowStyle.SUCCESS.value, background="#C6EFCE", foreground="#006100")
        # Alerta (Amarillo Excel)
        self.tree.tag_configure(RowStyle.WARNING.value, background="#FFEB9C", foreground="#9C6500")
        # Error (Rojo Excel)
        self.tree.tag_configure(RowStyle.DANGER.value, background="#FFC7CE", foreground="#9C0006")
    
    def _setup_column_tooltips(self) -> None:
        """Configura event binding para mostrar tooltips de columnas dinámicamente."""
        self.tree.bind("<Motion>", self._on_tree_motion, add="+")
        self.tree.bind("<Leave>", self._on_tree_leave, add="+")
    
    def _on_tree_motion(self, event):
        """Detecta cuando el mouse entra a una columna y muestra tooltip."""
        # Verificar que estamos en la región de headers
        region = self.tree.identify_region(event.x, event.y)
        if region != "heading":
            self._hide_current_tooltip()
            return
        
        # CRÍTICO: Obtener el nombre de columna directamente desde el heading identificado
        # Esto funciona CORRECTAMENTE incluso con columnas ocultas/reordenadas
        col_id = self.tree.identify_column(event.x)
        if not col_id:
            self._hide_current_tooltip()
            return
        
        # col_id viene como '#1', '#2', etc.
        # Necesitamos obtener el nombre real de la columna desde displaycolumns
        try:
            col_idx = int(col_id.replace('#', '')) - 1
            # displaycolumns puede ser la lista de columnas visibles en orden actual
            display_cols = self.tree.cget('displaycolumns')
            if display_cols == '#all':
                # Todas las columnas visibles en orden original
                if 0 <= col_idx < len(self.config.columns):
                    col = self.config.columns[col_idx]
                else:
                    return
            else:
                # Hay un subconjunto/reorden de columnas
                if 0 <= col_idx < len(display_cols):
                    col = display_cols[col_idx]
                else:
                    return
        except (ValueError, IndexError):
            return
        
        # Si ya mostramos tooltip de esta columna, no hacer nada
        if self._tooltip_col == col and self._current_tooltip:
            return
        
        # Ocultar tooltip anterior sí existe
        self._hide_current_tooltip()
        
        # Obtener descripción completa de la columna
        full_name = self.config.column_tooltips.get(col, col)
        short_name = self.config.column_labels.get(col, col)
        
        # Crear tooltip
        self._tooltip_col = col
        x = self.tree.winfo_rootx() + event.x
        y = self.tree.winfo_rooty() + self.ROW_HEIGHT + 5
        
        self._current_tooltip = tk.Toplevel(self.tree)
        self._current_tooltip.wm_overrideredirect(True)
        self._current_tooltip.wm_geometry(f"+{x}+{y}")
        
        # Label con fondo amarillo claro (Tooltip estándar)
        label = tk.Label(
            self._current_tooltip,
            text=full_name,
            background="#fffacd",
            foreground="#000000",
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 9),
            padx=5,
            pady=3,
            wraplength=200
        )
        label.pack()
    
    def _on_tree_leave(self, event):
        """Oculta tooltip cuando el mouse sale de la tabla."""
        self._hide_current_tooltip()
    
    def _hide_current_tooltip(self):
        """Oculta el tooltip actual si existe."""
        if self._current_tooltip:
            try:
                self._current_tooltip.destroy()
            except:
                pass
            self._current_tooltip = None
            self._tooltip_col = None
        
        # Bindings para sorting en columnas clave (se refrescan para asegurar binding)
        self.tree.heading("item", command=lambda: self._sort_by_column("item", numeric=True))
        self.tree.heading("desc", command=lambda: self._sort_by_column("desc", numeric=False))
        self.tree.heading(
            "renta_para_mejorar",
            command=lambda: self._sort_by_column("renta_para_mejorar", numeric=True),
        )
    
    def clear(self) -> None:
        """Limpia toda la tabla."""
        self.tree.delete(*self.tree.get_children())
        self.iids.clear()
    
    def rebuild_from_snapshot(self, items: list[dict]) -> None:
        """Reconstruye tabla desde un snapshot."""
        self.clear()
        for item in items:
            rid = str(item.get("value") or "")
            desc = str(item.get("text") or "")
            if not rid:
                continue
            self.insert_row(rid, desc)
    
    def insert_row(self, id_renglon: str, desc: str) -> str:
        """Inserta fila nueva en tabla."""
        initial_values = (
            "",  # id_subasta
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
        """Actualiza renderizado de una fila."""
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
        """Retorna id_renglon de la fila seleccionada o None."""
        sel = self.tree.selection()
        if not sel:
            return None
        iid = sel[0]
        values = self.tree.item(iid, "values")
        if len(values) < 2:
            return None
        return values[1]
    
    def get_config(self) -> TableConfig:
        """Retorna configuración estática de tabla."""
        return self.config
    
    def _sort_by_column(self, col: str, *, numeric: bool) -> None:
        """Ordena tabla por columna."""
        data = []
        for iid in self.tree.get_children(""):
            value = self.tree.set(iid, col)
            data.append((value, iid))
        
        reverse = self._sort_state.get(col, False)
        self._sort_state[col] = not reverse
        
        def sort_key(item):
            val = item[0]
            if numeric:
                return self._parse_sort_numeric(val)
            return str(val).lower()
        
        data.sort(key=sort_key, reverse=reverse)
        
        for idx, (_, iid) in enumerate(data):
            self.tree.move(iid, "", idx)

    def _parse_sort_numeric(self, value: str) -> float:
        """Convierte valores formateados ($, %, separadores) a float para sort."""
        if value is None:
            return float("-inf")
        raw = str(value).strip()
        if not raw:
            return float("-inf")
        # Limpiar simbolos comunes antes de parsear
        raw = raw.replace("%", "").replace("$", "")
        raw = raw.replace("ARS", "").replace("USD", "").strip()
        parsed = DataFormatter.parse_float(raw)
        if parsed is None:
            return float("-inf")
        return float(parsed)

    def apply_filter(self, rows_cache: dict[str, object], predicate) -> None:
        """Aplica filtro a filas usando detach/reattach para ocultar/mostrar."""
        for rid, iid in self.iids.items():
            row = rows_cache.get(rid)
            if row is None:
                continue
            show = False
            try:
                show = bool(predicate(row))
            except Exception:
                show = True

            if show:
                if rid in self._detached:
                    self.tree.reattach(iid, "", "end")
                    self._detached.discard(rid)
            else:
                if rid not in self._detached:
                    self.tree.detach(iid)
                    self._detached.add(rid)