# app/ui/table_manager.py
"""
Gestión de tabla Treeview.

Responsabilidad única: Crear, actualizar, renderizar la tabla sin tocar lógica de eventos.
"""

from __future__ import annotations

import tkinter as tk
import time
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
        "led",
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
                "led": "LED",
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
                "led": "ACTIVIDAD RENGLON",
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
                "led": 42,
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
    
    TREE_STYLE = "Monitor.Treeview"
    HEADING_STYLE = "Monitor.Treeview.Heading"
    ROW_HEIGHT = 30
    HEADER_HEIGHT_PX = 68
    TOOLTIP_CELL_WRAP_PX = 380
    TOOLTIP_CELL_MAX_WIDTH_PX = 420
    TOOLTIP_HEADING_WRAP_PX = 240
    TOOLTIP_HEADING_MAX_WIDTH_PX = 280
    TOOLTIP_MARGIN_PX = 12
    TOOLTIP_POLL_MS = 120

    def __init__(self, tree: ttk.Treeview):
        self.tree = tree
        self.config = TableConfig()
        self._zoom_level = 1.0
        self._header_height_px = self.HEADER_HEIGHT_PX
        
        # Cache local para rápido acceso: id_renglon -> iid (tree internal id)
        self.iids: dict[str, str] = {}
        
        # Variables internas para tooltips y ordenamiento
        self._current_tooltip = None
        self._tooltip_col = None
        self._tooltip_target: tuple[str, str] | None = None
        self._tooltip_shown_at = 0.0
        self._tooltip_poll_job = None
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
        self._apply_style()
        self.tree.configure(style=self.TREE_STYLE)

        # Primero, establecer las columnas en el treeview
        self.tree.configure(columns=self.config.columns)
        
        # Configurar cada columna
        for col in self.config.columns:
            label = self.config.column_labels.get(col, col)
            width = self.config.column_widths.get(col, 120)
            
            self.tree.heading(col, text=label)
            # Evita que Tk "compense" el ancho entre columnas vecinas.
            # Si el ancho total supera el viewport, se usa el scroll horizontal.
            self.tree.column(col, width=width, minwidth=40, anchor="w", stretch=False)
        
        # Asociar tooltips con la tabla
        self._setup_column_tooltips()
        self._start_tooltip_polling()
        self._setup_selection_behavior()
        self._setup_sorting_bindings()
        
        # --- CONFIGURACIÓN DE COLORES ESTILO EXCEL ---
        self.tree.tag_configure(RowStyle.NORMAL.value, background="", foreground="")
        self.tree.tag_configure(RowStyle.TRACKED.value, background="#e7f1ff", foreground="")
        
        # Éxito (Verde Excel)
        self.tree.tag_configure(RowStyle.SUCCESS.value, background="#C6EFCE", foreground="#006100")
        # Alerta (Amarillo Excel)
        self.tree.tag_configure(RowStyle.WARNING.value, background="#FFEB9C", foreground="#9C6500")
        # Error (Rojo Excel)
        self.tree.tag_configure(RowStyle.DANGER.value, background="#FFC7CE", foreground="#9C0006")
        # Oferta propia vigente (Azul institucional #5B9BD5 → fondo, texto blanco)
        self.tree.tag_configure(RowStyle.MY_OFFER.value, background="#5B9BD5", foreground="#FFFFFF")
        # Oferta propia superada (Naranja alerta)
        self.tree.tag_configure(RowStyle.OUTBID.value, background="#FF8C00", foreground="#FFFFFF")
    
    def _setup_column_tooltips(self) -> None:
        """Configura event binding para mostrar tooltips de columnas dinámicamente."""
        self.tree.bind("<Motion>", self._on_tree_motion, add="+")
        self.tree.bind("<Leave>", self._on_tree_leave, add="+")
        self.tree.bind("<MouseWheel>", lambda _e: self._hide_current_tooltip(), add="+")
        self.tree.bind("<ButtonPress>", lambda _e: self._hide_current_tooltip(), add="+")

    def _compute_header_padding(self, *, zoom_level: float) -> tuple[int, int, int, int]:
        """Calcula padding vertical de header a partir de altura manual objetivo."""
        font_size = max(8, int(10 * zoom_level))
        target_height = int(self._header_height_px * zoom_level)
        vertical_padding = max(6, int((target_height - font_size - 2) / 2))
        return (6, vertical_padding, 6, vertical_padding)

    def _apply_style(self) -> None:
        """Aplica estilo de tabla/cabecera con zoom y altura de header actual."""
        style = ttk.Style()
        font_size = max(8, int(11 * self._zoom_level))
        row_height = max(26, int(self.ROW_HEIGHT * self._zoom_level))
        header_padding = self._compute_header_padding(zoom_level=self._zoom_level)
        style.configure(self.TREE_STYLE, font=("Segoe UI", font_size), rowheight=row_height)
        style.configure(
            self.HEADING_STYLE,
            font=("Segoe UI", max(9, int(10 * self._zoom_level)), "bold"),
            padding=header_padding,
        )

    def set_header_height(self, height_px: int) -> int:
        """Define altura de cabecera en px y reaplica estilo."""
        self._header_height_px = max(36, min(int(height_px), 180))
        self._apply_style()
        return self._header_height_px

    def adjust_header_height(self, delta_px: int) -> int:
        """Ajuste incremental de altura de cabecera."""
        return self.set_header_height(self._header_height_px + int(delta_px))

    def apply_zoom_style(self, zoom_level: float) -> None:
        """Reaplica estilo de tabla y cabeceras acorde al zoom de la app."""
        self._zoom_level = max(0.8, float(zoom_level))
        self._apply_style()

    def _setup_selection_behavior(self) -> None:
        """Permite deseleccionar con click en fila ya seleccionada o en área vacía."""
        self.tree.bind("<Button-1>", self._on_left_click_toggle_selection, add="+")
        self.tree.bind("<Escape>", lambda _e: self.clear_selection(), add="+")

    def _setup_sorting_bindings(self) -> None:
        """Bindings para sorting en columnas clave."""
        self.tree.heading("item", command=lambda: self._sort_by_column("item", numeric=True))
        self.tree.heading("desc", command=lambda: self._sort_by_column("desc", numeric=False))
        self.tree.heading(
            "renta_para_mejorar",
            command=lambda: self._sort_by_column("renta_para_mejorar", numeric=True),
        )

    def _on_left_click_toggle_selection(self, event):
        region = self.tree.identify_region(event.x, event.y)
        iid = self.tree.identify_row(event.y)
        selected = set(self.tree.selection())

        if region in ("cell", "tree") and iid:
            if iid in selected:
                self.tree.after_idle(self.clear_selection)
                return "break"
            return None

        if region == "nothing":
            self.tree.after_idle(self.clear_selection)
        return None
    
    def _on_tree_motion(self, event):
        """Muestra tooltip contextual al mover mouse por headers o celdas."""
        region = self.tree.identify_region(event.x, event.y)
        if region == "heading":
            self._show_heading_tooltip(event)
            return
        if region in ("cell", "tree"):
            self._show_cell_tooltip(event)
            return
        self._hide_current_tooltip()

    def _resolve_column_key(self, col_id: str) -> str | None:
        """Mapea '#N' al nombre real de columna visible."""
        if not col_id:
            return None
        if not str(col_id).startswith("#"):
            return str(col_id)
        try:
            col_idx = int(str(col_id).replace("#", "")) - 1
            display_cols = self.tree.cget("displaycolumns")
            if isinstance(display_cols, str):
                display_cols = tuple(display_cols.split())
            if display_cols in ("#all", ("#all",)):
                if 0 <= col_idx < len(self.config.columns):
                    return self.config.columns[col_idx]
                return None
            if 0 <= col_idx < len(display_cols):
                return display_cols[col_idx]
            return None
        except (ValueError, IndexError):
            return None

    def _show_heading_tooltip(self, event) -> None:
        col = self._resolve_column_key(self.tree.identify_column(event.x))
        if not col:
            self._hide_current_tooltip()
            return
        target = ("heading", col)
        if self._current_tooltip and self._tooltip_target == target:
            return
        text = self.config.column_tooltips.get(col, col)
        x = self.tree.winfo_rootx() + event.x + 12
        y = self.tree.winfo_rooty() + self.ROW_HEIGHT + 8
        self._show_tooltip(
            text=text,
            x=x,
            y=y,
            wraplength=self.TOOLTIP_HEADING_WRAP_PX,
            max_width=self.TOOLTIP_HEADING_MAX_WIDTH_PX,
            target=target,
            col=col,
        )

    def _show_heading_tooltip_at(self, x: int, y: int) -> None:
        col = self._resolve_column_key(self.tree.identify_column(x))
        if not col:
            self._hide_current_tooltip()
            return
        target = ("heading", col)
        if self._current_tooltip and self._tooltip_target == target:
            return
        text = self.config.column_tooltips.get(col, col)
        x_root = self.tree.winfo_rootx() + x + 12
        y_root = self.tree.winfo_rooty() + self.ROW_HEIGHT + 8
        self._show_tooltip(
            text=text,
            x=x_root,
            y=y_root,
            wraplength=self.TOOLTIP_HEADING_WRAP_PX,
            max_width=self.TOOLTIP_HEADING_MAX_WIDTH_PX,
            target=target,
            col=col,
        )

    def _show_cell_tooltip(self, event) -> None:
        iid = self.tree.identify_row(event.y)
        col = self._resolve_column_key(self.tree.identify_column(event.x))
        if not iid or not col:
            self._hide_current_tooltip()
            return

        raw = self.tree.set(iid, col)
        text = str(raw or "").strip()
        if not text:
            self._hide_current_tooltip()
            return

        target = (iid, col)
        if self._current_tooltip and self._tooltip_target == target:
            return

        x = self.tree.winfo_rootx() + event.x + 14
        y = self.tree.winfo_rooty() + event.y + 18
        self._show_tooltip(
            text=text,
            x=x,
            y=y,
            wraplength=self.TOOLTIP_CELL_WRAP_PX,
            max_width=self.TOOLTIP_CELL_MAX_WIDTH_PX,
            target=target,
            col=col,
        )

    def _show_cell_tooltip_at(self, x: int, y: int) -> None:
        iid = self.tree.identify_row(y)
        col = self._resolve_column_key(self.tree.identify_column(x))
        if not iid or not col:
            self._hide_current_tooltip()
            return

        raw = self.tree.set(iid, col)
        text = str(raw or "").strip()
        if not text:
            self._hide_current_tooltip()
            return

        target = (iid, col)
        if self._current_tooltip and self._tooltip_target == target:
            return

        x_root = self.tree.winfo_rootx() + x + 14
        y_root = self.tree.winfo_rooty() + y + 18
        self._show_tooltip(
            text=text,
            x=x_root,
            y=y_root,
            wraplength=self.TOOLTIP_CELL_WRAP_PX,
            max_width=self.TOOLTIP_CELL_MAX_WIDTH_PX,
            target=target,
            col=col,
        )

    def _show_tooltip(
        self,
        *,
        text: str,
        x: int,
        y: int,
        wraplength: int,
        max_width: int,
        target: tuple[str, str],
        col: str | None = None,
    ) -> None:
        self._hide_current_tooltip()
        self._tooltip_target = target
        self._tooltip_col = col

        self._current_tooltip = tk.Toplevel(self.tree)
        self._current_tooltip.wm_overrideredirect(True)
        try:
            self._current_tooltip.wm_attributes("-topmost", True)
        except Exception:
            pass
        self._current_tooltip.wm_geometry(f"+{x}+{y}")
        self._current_tooltip.lift()
        self._tooltip_shown_at = time.monotonic()

        label = tk.Label(
            self._current_tooltip,
            text=text,
            background="#fffacd",
            foreground="#000000",
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 9),
            justify="left",
            anchor="w",
            padx=6,
            pady=4,
            wraplength=wraplength,
        )
        label.pack()
        self._current_tooltip.update_idletasks()

        # Limitar ancho visible y forzar multilínea cuando el texto es largo.
        if max_width > 0 and label.winfo_reqwidth() > max_width:
            label.configure(wraplength=max(80, max_width - 16))
            self._current_tooltip.update_idletasks()

        # En multi-monitor, winfo_screenwidth/height puede referir al monitor primario.
        # Clamp contra la ventana toplevel actual para que el tooltip quede en el mismo monitor.
        tip_w = self._current_tooltip.winfo_reqwidth()
        tip_h = self._current_tooltip.winfo_reqheight()
        margin = self.TOOLTIP_MARGIN_PX

        root = self.tree.winfo_toplevel()
        root_x = root.winfo_rootx()
        root_y = root.winfo_rooty()
        root_w = root.winfo_width()
        root_h = root.winfo_height()

        min_x = root_x + margin
        max_x = max(min_x, root_x + root_w - tip_w - margin)
        min_y = root_y + margin
        max_y = max(min_y, root_y + root_h - tip_h - margin)

        pos_x = min(max(min_x, x), max_x)
        pos_y = min(max(min_y, y), max_y)
        self._current_tooltip.wm_geometry(f"+{pos_x}+{pos_y}")
    
    def _on_tree_leave(self, event):
        """Oculta tooltip cuando el mouse sale de la tabla."""
        # Evitar cierre inmediato por eventos Leave espurios al crear tooltip.
        if (time.monotonic() - self._tooltip_shown_at) < 0.15:
            return
        if self._current_tooltip:
            try:
                x_root = int(getattr(event, "x_root", -1))
                y_root = int(getattr(event, "y_root", -1))
                tx = self._current_tooltip.winfo_rootx()
                ty = self._current_tooltip.winfo_rooty()
                tw = self._current_tooltip.winfo_width()
                th = self._current_tooltip.winfo_height()
                if tx <= x_root <= (tx + tw) and ty <= y_root <= (ty + th):
                    return
            except Exception:
                pass
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
            self._tooltip_target = None

    def _is_descendant(self, widget, ancestor) -> bool:
        current = widget
        while current is not None:
            if current == ancestor:
                return True
            current = getattr(current, "master", None)
        return False

    def _start_tooltip_polling(self) -> None:
        if self._tooltip_poll_job is not None:
            return
        self._tooltip_poll_job = self.tree.after(self.TOOLTIP_POLL_MS, self._poll_tooltip)

    def _poll_tooltip(self) -> None:
        self._tooltip_poll_job = None
        try:
            x_root = self.tree.winfo_pointerx()
            y_root = self.tree.winfo_pointery()
            widget_under = self.tree.winfo_containing(x_root, y_root)

            # Si el puntero no esta sobre la tabla ni el tooltip, ocultar.
            if not self._is_descendant(widget_under, self.tree):
                if self._current_tooltip and self._is_descendant(widget_under, self._current_tooltip):
                    pass
                else:
                    self._hide_current_tooltip()
            else:
                x = x_root - self.tree.winfo_rootx()
                y = y_root - self.tree.winfo_rooty()
                region = self.tree.identify_region(x, y)
                if region == "heading":
                    self._show_heading_tooltip_at(x, y)
                elif region in ("cell", "tree"):
                    self._show_cell_tooltip_at(x, y)
                else:
                    self._hide_current_tooltip()
        except Exception:
            pass
        finally:
            self._tooltip_poll_job = self.tree.after(self.TOOLTIP_POLL_MS, self._poll_tooltip)
    
    def clear(self) -> None:
        """Limpia toda la tabla."""
        self.tree.delete(*self.tree.get_children())
        self.iids.clear()

    def clear_selection(self) -> None:
        """Quita cualquier selección activa de la tabla."""
        sel = self.tree.selection()
        if sel:
            self.tree.selection_remove(sel)
        self.tree.focus("")
    
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
            "",  # led
            "",  # id_subasta
            id_renglon,
            desc,
        ) + ("",) * (len(self.config.columns) - 4)
        
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
        try:
            item_idx = self.config.columns.index("item")
        except ValueError:
            item_idx = 1
        if len(values) <= item_idx:
            return None
        return values[item_idx]
    
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
