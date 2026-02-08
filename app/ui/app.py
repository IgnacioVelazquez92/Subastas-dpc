# app/ui/app.py
"""
UI principal (CustomTkinter) - orquestador de componentes.

Arquitectura:
- App: Orquestador principal
- TableManager: Gestión de Treeview
- ColumnManager: Diálogos de columnas
- EventProcessor: Procesamiento de eventos del motor
- RowEditorDialog: Diálogo de edición
- LoggerWidget: Widget de logs
- DataFormatter: Formateo de datos
"""

from __future__ import annotations

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from queue import Empty
from typing import Optional

from app.core.app_runtime import RuntimeHandles
from app.core.events import Event
from app.models.domain import UIRow
from app.ui.table_manager import TableManager
from app.ui.column_manager import ColumnManager
from app.ui.event_handler import EventProcessor
from app.ui.row_editor import RowEditorDialog
from app.ui.logger_widget import LoggerWidget
from app.ui.formatters import DisplayValues


class App(ctk.CTk):
    """Orquestador principal de UI. Delega responsabilidades a managers especializados."""
    
    def __init__(self, *, handles: RuntimeHandles):
        super().__init__()

        ctk.set_appearance_mode("System")
        self.title(f"Monitor de Subastas - {handles.mode}")
        self.geometry("1480x820")

        self.handles = handles
        self.engine_out_q = handles.engine_out_q
        self.collector_cmd_q = handles.collector_cmd_q

        # Componentes especializados
        self.rows: dict[str, UIRow] = {}  # Cache de renglones
        
        # Managers (se crean en _build_ui)
        self.table_mgr: Optional[TableManager] = None
        self.col_mgr: Optional[ColumnManager] = None
        self.event_processor: Optional[EventProcessor] = None
        self.logger: Optional[LoggerWidget] = None
        
        self.lbl_status: Optional[ctk.CTkLabel] = None

        self._build_ui()

        # Poll de eventos desde engine
        self.after(100, self._poll_events)

    # -------------------------
    # UI Building
    # -------------------------
    def _build_ui(self):
        """Construye estructura principal y crea managers."""
        # Panel superior con botones
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=10, pady=10)

        ctk.CTkButton(top, text="Abrir navegador", command=self.on_start_browser).pack(side="left")
        ctk.CTkButton(top, text="Capturar subasta actual", command=self.on_capture_current).pack(side="left", padx=8)
        ctk.CTkButton(top, text="Detener", command=self.on_stop).pack(side="left", padx=8)
        ctk.CTkButton(top, text="Importar Excel", command=self.on_import_excel).pack(side="left", padx=8)
        ctk.CTkButton(top, text="Exportar Excel", command=self.on_export_excel).pack(side="left", padx=8)
        ctk.CTkButton(top, text="Editar registro", command=self.on_edit_row).pack(side="left", padx=8)
        ctk.CTkButton(top, text="Columnas", command=self.on_columns).pack(side="left", padx=8)
        ctk.CTkButton(top, text="Liberar espacio", command=self.on_cleanup).pack(side="left", padx=8)

        self.lbl_status = ctk.CTkLabel(top, text="RUNNING", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_status.pack(side="right")

        # Panel central: tabla
        body = ctk.CTkFrame(self)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.tree = ttk.Treeview(body, columns=(), show="headings", height=16)
        self.tree.pack(side="top", fill="both", expand=True)

        yscroll = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        yscroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=yscroll.set)

        xscroll = ttk.Scrollbar(body, orient="horizontal", command=self.tree.xview)
        xscroll.pack(side="bottom", fill="x")
        self.tree.configure(xscrollcommand=xscroll.set)

        # Crear managers
        self.table_mgr = TableManager(self.tree)
        self.table_mgr.initialize()
        
        self.col_mgr = ColumnManager(self.tree, self.handles.runtime, self.table_mgr.config)
        
        # Logger
        self.logger = LoggerWidget(self, height=8)
        
        # Event processor
        self.event_processor = EventProcessor(
            table_mgr=self.table_mgr,
            rows_cache=self.rows,
            status_label_setter=self._set_status,
            logger=self.logger.log,
            audio_bell_fn=self.bell,
        )
        
        # Cargar columnas guardadas
        default_cols = [
            "id_subasta", "item", "desc", "unidad", "cantidad", "marca", "obs",
            "conv_usd", "costo_usd", "costo_final", "subtotal_costo",
            "renta", "p_unit_min", "subtotal", "renta_ref", "p_unit_mejora",
            "precio_ref_subasta", "mejor", "subtotal_mejorar", "dif_unit",
            "renta_dpc", "obs_det",
        ]
        self.col_mgr.load_visible_columns(default_cols)
    
    def _set_status(self, text: str) -> None:
        """Actualiza etiqueta de status."""
        if self.lbl_status:
            self.lbl_status.configure(text=text)

    # -------------------------
    # Event Loop
    # -------------------------
    def _poll_events(self):
        """Obtiene eventos de engine y los procesa."""
        try:
            while True:
                ev: Event = self.engine_out_q.get_nowait()
                self.event_processor.process_event(ev)
        except Empty:
            pass

        self.after(100, self._poll_events)

    # -------------------------
    # User Actions
    # -------------------------
    def on_columns(self) -> None:
        """Abre diálogo de visibilidad de columnas."""
        self.col_mgr.show_dialog(self)

    def on_capture_current(self) -> None:
        """Envia comando al collector para capturar estado actual."""
        self.collector_cmd_q.put({"cmd": "capture_current"})
        self.logger.log("CMD: capture_current enviado al collector (si es Playwright, capturará).")

    def on_stop(self) -> None:
        """Detiene la aplicación."""
        self.handles.runtime.stop()

    def on_start_browser(self) -> None:
        """Inicia collector Playwright si está disponible."""
        if self.handles.mode != "PLAYWRIGHT":
            self.logger.log("Modo actual no es PLAYWRIGHT.")
            return
        try:
            self.handles.runtime.start_collector()
            self.logger.log("Collector Playwright iniciado por usuario.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir navegador: {e}")

    def on_edit_row(self) -> None:
        """Abre diálogo de edición para renglón seleccionado."""
        rid = self.table_mgr.get_selected_row_id()
        if not rid:
            messagebox.showwarning("Atención", "Seleccioná un renglón.")
            return
        
        row = self.rows.get(rid)
        if not row:
            messagebox.showwarning("Atención", "Renglón no encontrado.")
            return
        
        dialog = RowEditorDialog(self, row, self.handles.runtime, self.table_mgr)
        dialog.show()

    def on_cleanup(self) -> None:
        """Abre diálogo de limpieza de datos."""
        choice = messagebox.askyesnocancel(
            "Liberar espacio",
            "Sí = solo logs\nTodo = logs + subastas + costos\nCancelar = no hacer nada",
        )
        if choice is None:
            return
        
        if choice is True:
            try:
                self.handles.runtime.cleanup_data(mode="logs")
                self.logger.log("Logs limpiados.")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudieron limpiar logs: {e}")
            return

        # Limpiar estados (logs + subastas + costos)
        try:
            self.handles.runtime.cleanup_data(mode="states")
            self.table_mgr.clear()  # Limpiar tabla también
            self.rows.clear()
            self.logger.log("Logs, subastas y costos limpiados.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo limpiar datos: {e}")
            return

        reset = messagebox.askyesno(
            "Reset total",
            "¿Querés borrar también la configuración de la UI?",
        )
        if reset:
            try:
                self.handles.runtime.cleanup_data(mode="all")
                self.logger.log("Reset total realizado.")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo hacer reset total: {e}")

    def on_export_excel(self) -> None:
        """Abre diálogo para exportar datos a Excel."""
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            title="Exportar Excel",
        )
        if not path:
            return
        try:
            self.handles.runtime.export_excel(out_path=path)
            self.logger.log(f"Excel exportado: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar Excel: {e}")

    def on_import_excel(self) -> None:
        """Abre diálogo para importar datos desde Excel."""
        path = filedialog.askopenfilename(
            filetypes=[("Excel", "*.xlsx")],
            title="Importar Excel",
        )
        if not path:
            return
        try:
            updated = self.handles.runtime.import_excel(file_path=path)
            self.logger.log(f"Excel importado: {updated} filas actualizadas")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo importar Excel: {e}")
