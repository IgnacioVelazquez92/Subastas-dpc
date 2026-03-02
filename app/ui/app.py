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
from app.core.events import Event, EventType
from app.core.alert_engine import RowStyle
from app.models.domain import UIRow
from app.ui.table_manager import TableManager
from app.ui.column_manager import ColumnManager
from app.ui.event_handler import EventProcessor
from app.ui.row_editor import RowEditorDialog
from app.ui.logger_widget import LoggerWidget
from app.ui.formatters import DisplayValues
from app.ui.led_indicator import HTTPStatusLED, OfferChangeLED
from app.ui.views.info_view import InfoWindow


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

        # MEJORA VISUAL: Sistema de zoom global
        self.zoom_level = 1.0  # 1.0 = 100%, 1.1 = 110%, etc.
        self.base_font_sizes = {}  # Para restaurar tamaños originales
        
        # Componentes especializados
        self.rows: dict[str, UIRow] = {}  # Cache de renglones
        
        # Managers (se crean en _build_ui)
        self.table_mgr: Optional[TableManager] = None
        self.col_mgr: Optional[ColumnManager] = None
        self.event_processor: Optional[EventProcessor] = None
        self.logger: Optional[LoggerWidget] = None
        
        # LEDs de estado
        self.http_led: Optional[HTTPStatusLED] = None
        self.offer_led: Optional[OfferChangeLED] = None
        
        self.lbl_status: Optional[ctk.CTkLabel] = None

        # Filtros de tabla
        self.filter_with_cost = tk.BooleanVar(value=False)
        self.filter_tracked = tk.BooleanVar(value=False)
        self.filter_viable_only = tk.BooleanVar(value=False)
        self.filter_my_offers = tk.BooleanVar(value=False)   # Solo renglones donde oferta_mia=True
        self.filter_not_offered = tk.BooleanVar(value=False) # Solo renglones donde oferta_mia=False
        self.filter_search_text = tk.StringVar(value="")
        self.filter_search_text.trace_add("write", lambda *_: self._on_filter_changed())
        self.intensive_monitoring = tk.BooleanVar(value=True)
        self.http_monitor_mode = tk.BooleanVar(value=False)
        self._row_led_timers: dict[str, str] = {}
        # Treeview no siempre renderiza bien emojis de color; usar glifos robustos.
        self._row_led_default = "○"
        self._row_led_pulse = "◉"
        self._row_led_ok = "●"
        self._row_led_warn = "◐"
        self._row_led_error = "✖"
        self.lbl_monitor_mode_hint: Optional[ctk.CTkLabel] = None

        self._build_ui()

        # Bindings para zoom (Ctrl++ y Ctrl+-)
        self.bind("<Control-plus>", lambda e: self._zoom_in())
        self.bind("<Control-equal>", lambda e: self._zoom_in())  # Windows alt para +
        self.bind("<Control-minus>", lambda e: self._zoom_out())
        self.bind("<Control-0>", lambda e: self._zoom_reset())
        
        # Poll de eventos desde engine
        self.after(100, self._poll_events)

    # -------------------------
    # UI Building
    # -------------------------
    def _build_ui(self):
        """Construye estructura principal y crea managers."""
        # Contenedor principal con scroll vertical para soportar zoom.
        root_body = ctk.CTkFrame(self, fg_color="transparent")
        root_body.pack(fill="both", expand=True)

        self.main_canvas = tk.Canvas(root_body, highlightthickness=0)
        self.main_canvas.pack(side="left", fill="both", expand=True)

        self.main_vscroll = ttk.Scrollbar(root_body, orient="vertical", command=self.main_canvas.yview)
        self.main_vscroll.pack(side="right", fill="y")
        self.main_canvas.configure(yscrollcommand=self.main_vscroll.set)

        self.main_content = ctk.CTkFrame(self.main_canvas, fg_color="transparent")
        self.main_content_id = self.main_canvas.create_window((0, 0), window=self.main_content, anchor="nw")

        self.main_content.bind("<Configure>", self._on_main_content_configure)
        self.main_canvas.bind("<Configure>", self._on_main_canvas_configure)
        self.main_canvas.bind_all("<MouseWheel>", self._on_main_mousewheel)

        # Panel superior con botones principales y LEDs
        top = ctk.CTkFrame(self.main_content)
        top.pack(fill="x", padx=10, pady=10)

        # Botones principales (control)
        control_frame = ctk.CTkFrame(top, fg_color="transparent")
        control_frame.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            control_frame,
            text="▶️  Abrir navegador",
            command=self.on_start_browser,
            width=140,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            control_frame,
            text="📸 Capturar actual",
            command=self.on_capture_current,
            width=140,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            control_frame,
            text="📋 Editar renglón",
            command=self.on_edit_row,
            width=120,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            control_frame,
            text="⏹️  Detener",
            command=self.on_stop,
            width=100,
        ).pack(side="left", padx=4)

        # Menu de Opciones
        ctk.CTkButton(
            control_frame,
            text="⚙️  Opciones",
            command=self._show_options_menu,
            width=120,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            control_frame,
            text="ℹ️  Info",
            command=self._show_info,
            width=80,
        ).pack(side="left", padx=4)

        ctk.CTkSwitch(
            control_frame,
            text="Supervisión intensiva",
            variable=self.intensive_monitoring,
            command=self._on_toggle_intensive_monitoring,
        ).pack(side="left", padx=8)

        ctk.CTkSwitch(
            control_frame,
            text="⚡ HTTP Monitor",
            variable=self.http_monitor_mode,
            command=self._on_toggle_http_monitor,
        ).pack(side="left", padx=8)

        self.lbl_monitor_mode_hint = ctk.CTkLabel(
            control_frame,
            text="Cadencia LED: -",
            font=ctk.CTkFont(size=10),
            text_color="#666666",
        )
        self.lbl_monitor_mode_hint.pack(side="left", padx=8)

        # LEDs de estado
        leds_frame = ctk.CTkFrame(top, fg_color="transparent")
        leds_frame.pack(side="right")

        self.http_led = HTTPStatusLED(leds_frame)
        self.http_led.pack(side="left", padx=8)

        self.offer_led = OfferChangeLED(leds_frame)
        self.offer_led.pack(side="left", padx=8)

        # Status label
        self.lbl_status = ctk.CTkLabel(
            leds_frame,
            text="RUNNING",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#1309A2",
        )
        self.lbl_status.pack(side="right", padx=12)

        # Barra de filtros (debajo de los controles principales)
        filter_bar = ctk.CTkFrame(self.main_content)
        filter_bar.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(
            filter_bar,
            text="Filtros:",
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(side="left", padx=(6, 10))

        ctk.CTkSwitch(
            filter_bar,
            text="Solo con costo",
            variable=self.filter_with_cost,
            command=self._on_filter_changed,
        ).pack(side="left", padx=6)

        ctk.CTkSwitch(
            filter_bar,
            text="Solo seguimiento",
            variable=self.filter_tracked,
            command=self._on_filter_changed,
        ).pack(side="left", padx=6)

        ctk.CTkSwitch(
            filter_bar,
            text="Solo en carrera",
            variable=self.filter_viable_only,
            command=self._on_filter_changed,
        ).pack(side="left", padx=6)

        ctk.CTkSwitch(
            filter_bar,
            text="Solo mis ofertas",
            variable=self.filter_my_offers,
            command=self._on_filter_changed,
        ).pack(side="left", padx=6)

        ctk.CTkSwitch(
            filter_bar,
            text="Sin mis ofertas",
            variable=self.filter_not_offered,
            command=self._on_filter_changed,
        ).pack(side="left", padx=6)

        ctk.CTkEntry(
            filter_bar,
            textvariable=self.filter_search_text,
            placeholder_text="Buscar descripcion o renglon (ej: renglon 2)",
            width=330,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            filter_bar,
            text="Mostrar todo",
            width=110,
            command=self._reset_filters,
        ).pack(side="right", padx=6)

        # ── Panel: Mi ID Proveedor ──────────────────────────────────────────────
        prov_bar = ctk.CTkFrame(self.main_content)
        prov_bar.pack(fill="x", padx=10, pady=(0, 6))

        ctk.CTkLabel(
            prov_bar,
            text="Mi ID Proveedor:",
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(side="left", padx=(6, 4))

        self._mi_id_prov_var = tk.StringVar(value="")
        self._mi_id_prov_entry = ctk.CTkEntry(
            prov_bar,
            textvariable=self._mi_id_prov_var,
            placeholder_text="Ej: 30707010  (variable por subasta)",
            width=240,
        )
        self._mi_id_prov_entry.pack(side="left", padx=4)
        self._mi_id_prov_entry.bind("<Return>", lambda _e: self._save_mi_id_proveedor())

        ctk.CTkButton(
            prov_bar,
            text="Guardar",
            width=80,
            command=self._save_mi_id_proveedor,
        ).pack(side="left", padx=4)

        self._lbl_mi_prov_status = ctk.CTkLabel(
            prov_bar,
            text="",
            font=ctk.CTkFont(size=10),
            text_color="#888888",
        )
        self._lbl_mi_prov_status.pack(side="left", padx=8)

        ctk.CTkLabel(
            prov_bar,
            text="ℹ️  Renglones con tu oferta: ",
            font=ctk.CTkFont(size=10),
            text_color="#5B9BD5",
        ).pack(side="left", padx=(16, 0))

        self._lbl_my_offer_count = ctk.CTkLabel(
            prov_bar,
            text="0",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#5B9BD5",
        )
        self._lbl_my_offer_count.pack(side="left")
        # ───────────────────────────────────────────────────────────────────────

        # Panel central: tabla
        body = ctk.CTkFrame(self.main_content)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Obtener configuración de tabla para crear treeview con columnas
        table_config = TableManager.get_default_config()
        
        # Crear tabla con columnas correctas
        self.tree = ttk.Treeview(
            body,
            columns=table_config.columns,
            show="headings",
            height=16,
            selectmode="browse",
        )
        self.tree.pack(side="top", fill="both", expand=True)
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

        # Logger mejorado
        self.logger = LoggerWidget(self.main_content, height=8)

        # Event processor con referencia a LEDs
        self.event_processor = EventProcessor(
            table_mgr=self.table_mgr,
            rows_cache=self.rows,
            status_label_setter=self._set_status,
            logger=self.logger.log,
            audio_bell_fn=self.bell,
        )
        # Registrar callbacks para LEDs
        self.event_processor.on_offer_changed = self.offer_led.on_offer_changed
        self.event_processor.on_http_event = self.http_led.on_http_status
        self.event_processor.on_row_http_event = self._on_row_http_event

        # Cargar columnas guardadas (REFACTORED: usar nombres nuevos)
        default_cols = [
            "led", "id_subasta", "item", "desc", "unidad_medida", "cantidad", "marca",
            "obs_usuario", "conv_usd", "costo_unit_usd", "costo_total_usd",
            "costo_unit_ars", "costo_total_ars", "renta_minima",
            "precio_unit_aceptable", "precio_total_aceptable",
            "precio_referencia", "precio_ref_unitario", "renta_referencia",
            "mejor_oferta", "oferta_para_mejorar",
            "precio_unit_mejora", "renta_para_mejorar", "obs_cambio",
        ]
        self.col_mgr.load_visible_columns(default_cols)
        self._on_toggle_intensive_monitoring()
        self._update_monitor_mode_hint()

        # Cargar mi_id_proveedor guardado
        self.after(200, self._load_mi_id_proveedor)
        # Actualizar contador periódico
        self.after(3000, self._tick_my_offer_count)

    def _on_main_content_configure(self, _event=None) -> None:
        if hasattr(self, "main_canvas"):
            self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

    def _on_main_canvas_configure(self, event) -> None:
        if hasattr(self, "main_content_id"):
            self.main_canvas.itemconfigure(self.main_content_id, width=event.width)

    def _on_main_mousewheel(self, event) -> None:
        # Scroll vertical general de la ventana principal.
        try:
            # Si el foco está dentro de la tabla o logger, respetar su scroll nativo.
            widget = event.widget
            if self._is_descendant(widget, getattr(self, "tree", None)):
                return
            if self._is_descendant(widget, getattr(self.logger, "text_widget", None)):
                return
            self.main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    @staticmethod
    def _is_descendant(widget, ancestor) -> bool:
        if widget is None or ancestor is None:
            return False
        current = widget
        while current is not None:
            if current == ancestor:
                return True
            current = getattr(current, "master", None)
        return False


    def _show_options_menu(self) -> None:
        """Abre un menú popup con las opciones adicionales."""
        # Crear un menú contextual
        menu = tk.Menu(self, tearoff=False, bg="#2B2B2B", fg="#FFFFFF")

        menu.add_command(label="🔄 Actualizar", command=self.on_refresh_ui)
        menu.add_command(label="📊 Columnas", command=self.on_columns)
        menu.add_separator()
        menu.add_command(label="Cabecera +", command=self._increase_header_height)
        menu.add_command(label="Cabecera -", command=self._decrease_header_height)
        menu.add_command(label="Cabecera reset", command=self._reset_header_height)
        menu.add_separator()
        menu.add_command(label="📥 Importar Excel", command=self.on_import_excel)
        menu.add_command(label="📤 Exportar Excel", command=self.on_export_excel)
        menu.add_separator()
        menu.add_command(label="🗑️  Liberar espacio", command=self.on_cleanup)

        # Mostrar menú en la posición del mouse
        menu.post(self.winfo_pointerx(), self.winfo_pointery())

    def _show_info(self) -> None:
        """Abre la ventana de información y actualizaciones."""
        InfoWindow(self)

    def _increase_header_height(self) -> None:
        if not self.table_mgr:
            return
        value = self.table_mgr.adjust_header_height(8)
        self.logger.log(f"Cabecera tabla: {value}px")

    def _decrease_header_height(self) -> None:
        if not self.table_mgr:
            return
        value = self.table_mgr.adjust_header_height(-8)
        self.logger.log(f"Cabecera tabla: {value}px")

    def _reset_header_height(self) -> None:
        if not self.table_mgr:
            return
        value = self.table_mgr.set_header_height(TableManager.HEADER_HEIGHT_PX)
        self.logger.log(f"Cabecera tabla: {value}px (reset)")

    
    def _set_status(self, text: str) -> None:
        """Actualiza etiqueta de status."""
        if self.lbl_status:
            self.lbl_status.configure(text=text)

    def _render_row_preserving_style(self, row: UIRow) -> None:
        if not self.table_mgr:
            return
        iid = self.table_mgr.iids.get(row.id_renglon)
        if not iid:
            return
        tags = self.tree.item(iid, "tags")
        style = tags[0] if tags else RowStyle.NORMAL.value
        row_values = DisplayValues.build_row_values(row)
        self.table_mgr.render_row(row.id_renglon, row_values, style)

    def _set_row_led_symbol(self, row: UIRow, symbol: str) -> None:
        new_value = symbol
        if row.update_led == new_value:
            return
        row.update_led = new_value
        self._render_row_preserving_style(row)

    def _cancel_row_led_timer(self, rid: str) -> None:
        timer_id = self._row_led_timers.pop(rid, None)
        if timer_id:
            try:
                self.after_cancel(timer_id)
            except Exception:
                pass

    def _schedule_row_led_settle(self, rid: str, symbol: str, delay_ms: int = 180) -> None:
        self._cancel_row_led_timer(rid)

        def _settle():
            self._row_led_timers.pop(rid, None)
            row = self.rows.get(rid)
            if row is None:
                return
            self._set_row_led_symbol(row, symbol)

        self._row_led_timers[rid] = self.after(delay_ms, _settle)

    def _clear_all_leds(self) -> None:
        for rid in list(self._row_led_timers.keys()):
            self._cancel_row_led_timer(rid)
        for row in self.rows.values():
            self._set_row_led_symbol(row, self._row_led_default)

    def _on_row_http_event(self, rid: str, status_code: int, error_kind: str = "") -> None:
        row = self.rows.get(str(rid))
        if row is None:
            return

        kind = str(error_kind or "").lower()
        if int(status_code) == 200:
            target_symbol = self._row_led_ok
        elif int(status_code) == 0 or kind == "timeout":
            target_symbol = self._row_led_warn
        else:
            target_symbol = self._row_led_error

        self._set_row_led_symbol(row, self._row_led_pulse)
        self._schedule_row_led_settle(row.id_renglon, target_symbol, delay_ms=320)

    def _update_monitor_mode_hint(self) -> None:
        if not self.lbl_monitor_mode_hint:
            return
        total_rows = max(0, len(self.rows))
        poll_base = max(1.0, float(getattr(self.handles.runtime, "poll_seconds", 1.0)))
        intensive = bool(self.intensive_monitoring.get())

        if total_rows == 0:
            text = "Cadencia LED: sin renglones capturados"
        elif intensive:
            text = f"INTENSIVA: {total_rows} renglones/ciclo, cada ~{poll_base:.1f}s"
        else:
            if total_rows == 1:
                text = f"SUEÑO: 1 renglón/ciclo, cada ~{poll_base:.1f}s (igual a intensiva)"
            else:
                per_row = poll_base * total_rows
                text = f"SUEÑO: 1 renglón/ciclo (~{poll_base:.1f}s). Cada renglón ~{per_row:.1f}s"
        self.lbl_monitor_mode_hint.configure(text=text)

    # -------------------------
    # Event Loop
    # -------------------------
    def _poll_events(self):
        """Obtiene eventos de engine y los procesa."""
        had_updates = False
        processed = 0
        max_events_per_tick = 200
        has_pending = False
        try:
            while processed < max_events_per_tick:
                ev: Event = self.engine_out_q.get_nowait()
                processed += 1
                if ev.type in (EventType.SNAPSHOT, EventType.UPDATE):
                    had_updates = True
                self.event_processor.process_event(ev)
        except Empty:
            pass

        if had_updates:
            self._apply_filters()
            self._update_monitor_mode_hint()

        has_pending = processed >= max_events_per_tick
        self.after(20 if has_pending else 100, self._poll_events)

    def _on_filter_changed(self) -> None:
        """Callback de UI para aplicar filtros en la tabla."""
        self._apply_filters()

    def _reset_filters(self) -> None:
        """Resetea todos los filtros y muestra todas las filas."""
        self.filter_with_cost.set(False)
        self.filter_tracked.set(False)
        self.filter_viable_only.set(False)
        self.filter_my_offers.set(False)
        self.filter_not_offered.set(False)
        self.filter_search_text.set("")
        self._apply_filters()

    @staticmethod
    def _build_search_haystack(row: UIRow) -> str:
        """Texto combinado para buscar por descripcion e identificador de renglon."""
        rid = str(row.id_renglon or "").strip()
        normalized_rid = rid.lstrip("#")
        desc = str(row.desc or "").strip()
        parts = [
            desc,
            rid,
            normalized_rid,
            f"renglon {normalized_rid}",
            f"renglon #{normalized_rid}",
            f"reglon {normalized_rid}",
            f"reglon #{normalized_rid}",
        ]
        return " ".join(part.lower() for part in parts if part)

    def _apply_filters(self) -> None:
        """Aplica filtros sobre la tabla según estado actual de UI."""
        if not self.table_mgr:
            return

        search_term = self.filter_search_text.get().strip().lower()

        def predicate(row: UIRow) -> bool:
            if self.filter_tracked.get() and not row.seguir:
                return False
            if self.filter_with_cost.get() and not (row.costo_unit_ars or row.costo_total_ars):
                return False
            
            # 🔥 Filtro "Solo en carrera": ocultar renglones fuera de umbral
            if self.filter_viable_only.get():
                if row.renta_minima is not None and row.renta_para_mejorar is not None:
                    if float(row.renta_para_mejorar) < float(row.renta_minima):
                        return False

            # 🔵 Filtro "Solo mis ofertas": mostrar solo renglones donde soy el mejor
            if self.filter_my_offers.get() and not row.oferta_mia:
                return False

            # ⬜ Filtro "Sin mis ofertas": mostrar solo renglones donde NO soy el mejor
            if self.filter_not_offered.get() and row.oferta_mia:
                return False

            if search_term and search_term not in self._build_search_haystack(row):
                return False
            return True

        self.table_mgr.apply_filter(self.rows, predicate)

    # -------------------------
    # Mi ID Proveedor
    # -------------------------
    def _load_mi_id_proveedor(self) -> None:
        """Carga el mi_id_proveedor guardado desde la BD al iniciar."""
        try:
            value = self.handles.runtime.get_mi_id_proveedor()
            if value:
                self._mi_id_prov_var.set(value)
                self._lbl_mi_prov_status.configure(
                    text=f"Activo: {value}",
                    text_color="#5B9BD5",
                )
        except Exception:
            pass

    def _save_mi_id_proveedor(self) -> None:
        """Guarda el mi_id_proveedor ingresado y actualiza el engine."""
        value = self._mi_id_prov_var.get().strip()
        try:
            self.handles.runtime.set_mi_id_proveedor(value if value else None)
            if value:
                self._lbl_mi_prov_status.configure(
                    text=f"✓ Guardado: {value}",
                    text_color="#5B9BD5",
                )
                if self.logger:
                    self.logger.log(f"🔵 Mi ID Proveedor actualizado → {value}")
            else:
                self._lbl_mi_prov_status.configure(
                    text="Borrado (sin ID activo)",
                    text_color="#888888",
                )
                if self.logger:
                    self.logger.log("🔵 Mi ID Proveedor eliminado.")
        except Exception as e:
            self._lbl_mi_prov_status.configure(
                text=f"Error: {e}",
                text_color="#FF4444",
            )

    def _tick_my_offer_count(self) -> None:
        """Actualiza el contador de renglones donde tengo la mejor oferta."""
        try:
            count = sum(1 for row in self.rows.values() if row.oferta_mia)
            if hasattr(self, "_lbl_my_offer_count"):
                self._lbl_my_offer_count.configure(text=str(count))
        except Exception:
            pass
        self.after(3000, self._tick_my_offer_count)


    def on_columns(self) -> None:
        """Abre diálogo de visibilidad de columnas."""
        self.col_mgr.show_dialog(self)

    def on_capture_current(self) -> None:
        """Envia comando al collector para capturar estado actual."""
        self.collector_cmd_q.put({"cmd": "capture_current"})
        self.logger.log("📸 Captura de subasta actual solicitada...")

    def _on_toggle_intensive_monitoring(self) -> None:
        """Activa/desactiva monitoreo intensivo en caliente."""
        enabled = bool(self.intensive_monitoring.get())
        self.handles.runtime.set_intensive_monitoring(enabled=enabled)
        self._clear_all_leds()
        self._update_monitor_mode_hint()
        if self.logger:
            mode_txt = "INTENSIVA" if enabled else "SUEÑO"
            self.logger.log(f"Modo de supervisión: {mode_txt}")

    def _on_toggle_http_monitor(self) -> None:
        """Activa/desactiva HttpMonitor (httpx directo) en caliente."""
        enabled = bool(self.http_monitor_mode.get())
        self.handles.runtime.set_http_monitor_mode(enabled=enabled)
        if self.logger:
            if enabled:
                self.logger.log(
                    "⚡ HTTP Monitor ACTIVADO — próximo 'Capturar actual' usará httpx directo "
                    "(latencia 0.2–2s). Playwright queda abierto para navegación."
                )
            else:
                self.logger.log(
                    "HTTP Monitor desactivado — próximo 'Capturar actual' usará Playwright (Chromium)."
                )

    def on_refresh_ui(self) -> None:
        """Refresca la UI leyendo datos actuales desde la BD."""
        self._refresh_rows_from_db()
        self.logger.log("🔄 UI actualizada desde BD.")

    def _refresh_rows_from_db(self) -> None:
        """Actualiza filas de la UI con datos persistidos en BD."""
        if not self.table_mgr:
            return

        db = self.handles.runtime.db
        for row in self.rows.values():
            if row.renglon_pk is None:
                continue

            excel = db.get_renglon_excel(renglon_id=row.renglon_pk)
            if excel:
                row.unidad_medida = excel.get("unidad_medida")
                row.cantidad = excel.get("cantidad")
                row.marca = excel.get("marca")
                row.obs_usuario = excel.get("obs_usuario")
                row.conv_usd = excel.get("conv_usd")
                row.costo_unit_usd = excel.get("costo_unit_usd")
                row.costo_total_usd = excel.get("costo_total_usd")
                row.costo_unit_ars = excel.get("costo_unit_ars")
                row.costo_total_ars = excel.get("costo_total_ars")
                row.renta_minima = excel.get("renta_minima")
                row.precio_referencia = excel.get("precio_referencia")
                row.precio_ref_unitario = excel.get("precio_ref_unitario")
                row.renta_referencia = excel.get("renta_referencia")
                row.precio_unit_aceptable = excel.get("precio_unit_aceptable")
                row.precio_total_aceptable = excel.get("precio_total_aceptable")
                row.precio_unit_mejora = excel.get("precio_unit_mejora")
                row.renta_para_mejorar = excel.get("renta_para_mejorar")
                row.oferta_para_mejorar = excel.get("oferta_para_mejorar")
                row.obs_cambio = excel.get("obs_cambio")

            cfg = db.get_renglon_config(renglon_id=row.renglon_pk)
            if cfg:
                row.seguir = bool(cfg.get("seguir"))
                row.oferta_mia = bool(cfg.get("oferta_mia"))

            row_values = DisplayValues.build_row_values(row)
            self.table_mgr.render_row(row.id_renglon, row_values, RowStyle.NORMAL.value)

        self._apply_filters()

    def on_stop(self) -> None:
        """Pausa supervision sin cerrar la aplicacion."""
        self.handles.runtime.stop_collector()
        self.logger.log("Supervision pausada. Reanuda con 'Abrir navegador' y luego 'Capturar actual'.")

    def on_start_browser(self) -> None:
        """Inicia collector según el modo (agnóstico a PLAYWRIGHT/MOCK)."""
        try:
            self.handles.runtime.start_collector()
            self.logger.log(f"✅ Collector iniciado en modo {self.handles.mode}.")
        except Exception as e:
            messagebox.showerror("❌ Error", f"No se pudo iniciar collector: {e}")

    def on_edit_row(self) -> None:
        """Abre diálogo de edición para renglón seleccionado."""
        rid = self.table_mgr.get_selected_row_id()
        if not rid:
            messagebox.showwarning("⚠️  Atención", "Seleccioná un renglón de la tabla para editar.")
            return
        
        row = self.rows.get(rid)
        if not row:
            messagebox.showwarning("⚠️  Atención", "Renglón no encontrado en memoria.")
            return
        
        dialog = RowEditorDialog(self, row, self.handles.runtime, self.table_mgr)
        dialog.show()

    def on_cleanup(self) -> None:
        """Abre diálogo de limpieza de datos con tema LIGHT."""
        # Crear diálogo profesional
        dialog = ctk.CTkToplevel(self)
        dialog.title("🗑️  Liberar Espacio")
        dialog.geometry("480x420")
        dialog.resizable(False, False)
        
        # Hacer que la ventana sea siempre sobre la principal
        dialog.transient(self)
        
        # Centrar en pantalla
        dialog.update_idletasks()
        parent_x = self.winfo_x()
        parent_y = self.winfo_y()
        parent_w = self.winfo_width()
        parent_h = self.winfo_height()
        
        x = parent_x + (parent_w - 480) // 2
        y = parent_y + (parent_h - 420) // 2
        dialog.geometry(f"480x420+{x}+{y}")

        # Header con tema LIGHT
        header = ctk.CTkFrame(dialog, fg_color="#F5F5F5", corner_radius=0)
        header.pack(fill="x", padx=0, pady=0)

        ctk.CTkLabel(
            header,
            text="🗑️  Liberar Espacio",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#1A1A1A",
        ).pack(anchor="w", padx=20, pady=(15, 5))

        ctk.CTkLabel(
            header,
            text="Selecciona qué datos deseas limpiar",
            font=ctk.CTkFont(size=10),
            text_color="#666666",
        ).pack(anchor="w", padx=20, pady=(0, 15))

        # Separator
        sep = ctk.CTkFrame(header, height=1, fg_color="#E0E0E0")
        sep.pack(fill="x")

        # Opciones - LIGHT bg
        frame = ctk.CTkFrame(dialog, fg_color="#FFFFFF")
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Opción 1: Solo logs
        btn1 = ctk.CTkButton(
            frame,
            text="📋 Limpiar Solo Logs",
            command=lambda: self._do_cleanup("logs", dialog),
            fg_color="#FFA500",
            hover_color="#FFB84D",
            text_color="#FFFFFF",
            height=44,
        )
        btn1.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            frame,
            text="Borra solo los registros de logs.",
            font=ctk.CTkFont(size=9),
            text_color="#555555",
        ).pack(anchor="w", pady=(0, 12))

        # Opción 2: Logs + datos
        btn2 = ctk.CTkButton(
            frame,
            text="📊 Limpiar Logs + Subastas + Costos",
            command=lambda: self._do_cleanup("states", dialog),
            fg_color="#F44336",
            hover_color="#EF5350",
            text_color="#FFFFFF",
            height=44,
        )
        btn2.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            frame,
            text="Borra logs, historial de subastas y datos de costos.",
            font=ctk.CTkFont(size=9),
            text_color="#555555",
        ).pack(anchor="w", pady=(0, 12))

        # Opción 3: Reset total
        btn3 = ctk.CTkButton(
            frame,
            text="🔄 Reset Total",
            command=lambda: self._do_cleanup("all", dialog),
            fg_color="#D32F2F",
            hover_color="#E53935",
            text_color="#FFFFFF",
            height=44,
        )
        btn3.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            frame,
            text="⚠️  Borra TODA la configuración, UI incluida. NO SE PUEDE DESHACER.",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#D32F2F",
        ).pack(anchor="w", pady=(0, 12))

        # Footer
        footer = ctk.CTkFrame(dialog, fg_color="#F5F5F5", corner_radius=0)
        footer.pack(fill="x", padx=0, pady=0)

        sep2 = ctk.CTkFrame(footer, height=1, fg_color="#E0E0E0")
        sep2.pack(fill="x")

        btns = ctk.CTkFrame(footer, fg_color="#F5F5F5")
        btns.pack(fill="x", padx=20, pady=15)

        ctk.CTkButton(
            btns,
            text="❌ Cancelar",
            command=dialog.destroy,
            fg_color="#E0E0E0",
            hover_color="#D0D0D0",
            text_color="#1A1A1A",
            width=150,
        ).pack(side="right", padx=6)

    def _do_cleanup(self, mode: str, dialog) -> None:
        """Ejecuta limpieza con confirmación adicional."""
        if mode == "all":
            if not messagebox.askyesno(
                "⚠️  ADVERTENCIA",
                "¿REALMENTE deseas hacer un RESET TOTAL?\nNo se puede deshacer.",
            ):
                return

        try:
            self.handles.runtime.cleanup_data(mode=mode)

            if mode == "logs":
                self.logger.log("🗑️  Logs limpiados exitosamente.")
                messagebox.showinfo("✅ Éxito", "Logs limpiados.")
            elif mode == "states":
                self.table_mgr.clear()
                self.rows.clear()
                self.logger.log("🗑️  Logs, subastas y costos limpiados exitosamente.")
                messagebox.showinfo("✅ Éxito", "Datos limpiados. Tabla vaciada.")
            elif mode == "all":
                self.table_mgr.clear()
                self.rows.clear()
                self.logger.log("🔄 Reset total realizado.")
                messagebox.showinfo("✅ Éxito", "Reset total completado. Reinicia la aplicación.")

            dialog.destroy()
        except Exception as e:
            messagebox.showerror("❌ Error", f"No se pudo limpiar: {e}")

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
            self.logger.log(f"📤 Excel exportado: {path}")
            messagebox.showinfo("✅ Éxito", f"Archivo exportado:\n{path}")
        except Exception as e:
            messagebox.showerror("❌ Error", f"No se pudo exportar Excel:\n{e}")

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
            self.logger.log(f"📥 Excel importado: {updated} filas actualizadas")
            
            # Refrescar UI con datos persistidos (inmediato)
            self._refresh_rows_from_db()
            
            # Forzar captura inmediata para refrescar UI con datos del collector
            self.collector_cmd_q.put({"cmd": "capture_current"})
            
            messagebox.showinfo("✅ Éxito", f"Se importaron {updated} filas correctamente.\n\nActualizando datos...")
        except Exception as e:
            messagebox.showerror("❌ Error", f"No se pudo importar Excel:\n{e}")
    # -------------------------
    # Zoom / Escalado Visual
    # -------------------------
    def _zoom_in(self) -> None:
        """Aumenta el zoom de la UI (Ctrl+Plus)."""
        self.zoom_level = min(self.zoom_level + 0.1, 2.0)  # Max 200%
        self._apply_zoom()
        self.logger.log(f"🔍 Zoom: {int(self.zoom_level * 100)}%")
    
    def _zoom_out(self) -> None:
        """Disminuye el zoom de la UI (Ctrl+Minus)."""
        self.zoom_level = max(self.zoom_level - 0.1, 0.8)  # Min 80%
        self._apply_zoom()
        self.logger.log(f"🔍 Zoom: {int(self.zoom_level * 100)}%")
    
    def _zoom_reset(self) -> None:
        """Resetea el zoom a 100% (Ctrl+0)."""
        self.zoom_level = 1.0
        self._apply_zoom()
        self.logger.log("🔍 Zoom: 100% (resetado)")
    
    def _apply_zoom(self) -> None:
        """
        Aplica el zoom a todos los elementos escalables.
        
        Reescala:
        - Fuentes de labels, botones, etc.
        - Tamaño de filas en treeview
        - Padding y espacios
        """
        # Recalcular tamaño de fuente base
        base_size = 11
        new_size = max(8, int(base_size * self.zoom_level))
        
        # Actualizar fuentes en componentes principales
        try:
            # Fuente de tabla
            if self.table_mgr and self.table_mgr.tree:
                self.table_mgr.apply_zoom_style(self.zoom_level)
            
            # Fuente de logger
            if self.logger and hasattr(self.logger, 'text_widget'):
                self.logger.text_widget.configure(font=("Courier New", new_size))
            
            # Actualizar labels de status
            if self.lbl_status:
                self.lbl_status.configure(font=("Segoe UI", new_size))
            
            # Log de cambio de zoom
        except Exception as e:
            # Silenciosamente fallar si hay problemas con fuentes
            pass
