# app/ui/row_editor.py
"""
Diálogo de edición de renglón + cálculos de fórmulas.

Responsabilidades:
- RowCalculator: Lógica pura de cálculos (sin side effects)
- RowEditorDialog: UI del diálogo y flujo de edición
"""

from __future__ import annotations

import tkinter as tk
import customtkinter as ctk
from tkinter import ttk, messagebox

from app.models.domain import UIRow
from app.core.alert_engine import AlertEngine
from app.ui.formatters import DataFormatter
from app.ui.table_manager import TableManager


class RowCalculator:
    """Encapsula lógica de cálculos de fórmulas."""
    
    @staticmethod
    def safe_div(a: float | None, b: float | None) -> float | None:
        """División segura: retorna None si division by zero o nums inválidos."""
        if a is None or b is None or b == 0:
            return None
        return a / b
    
    @staticmethod
    def safe_mul(a: float | None, b: float | None) -> float | None:
        """Multiplicación segura."""
        if a is None or b is None:
            return None
        return a * b
    
    @staticmethod
    def calculate_costo_usd(
        costo_unit_ars: float,
        conv_usd: float
    ) -> float | None:
        """Costo en USD = Costo Unit ARS / Conversión."""
        return RowCalculator.safe_div(costo_unit_ars, conv_usd)
    
    @staticmethod
    def calculate_costo_total_ars(
        cantidad: float,
        costo_unit_ars: float
    ) -> float | None:
        """Costo Total ARS = Cantidad × Costo Unit ARS."""
        return RowCalculator.safe_mul(cantidad, costo_unit_ars)
    
    @staticmethod
    def calculate_precio_unit_aceptable(
        renta_minima: float,
        costo_unit_ars: float
    ) -> float | None:
        """Precio Unit Aceptable = (1 + Renta Mínima) × Costo Unit ARS.
        
        renta_minima es fracción (0.1 = 10%, 0.3 = 30%)
        """
        if renta_minima is None or costo_unit_ars is None:
            return None
        return (1.0 + renta_minima) * costo_unit_ars
    
    @staticmethod
    def calculate_precio_total_aceptable(
        cantidad: float,
        precio_unit_aceptable: float
    ) -> float | None:
        """Precio Total Aceptable = Cantidad × Precio Unit Aceptable."""
        return RowCalculator.safe_mul(cantidad, precio_unit_aceptable)
    
    @staticmethod
    def calculate_renta_referencia(
        precio_ref: float,
        costo_unit_ars: float
    ) -> float | None:
        """Renta Referencia = (Precio Ref / Costo Unit ARS) - 1."""
        result = RowCalculator.safe_div(precio_ref, costo_unit_ars)
        if result is None:
            return None
        return result - 1.0
    
    @staticmethod
    def calculate_precio_unit_mejora(
        oferta_para_mejorar: float,
        cantidad: float
    ) -> float | None:
        """Precio Unit Mejora = Oferta Para Mejorar / Cantidad."""
        return RowCalculator.safe_div(oferta_para_mejorar, cantidad)
    
    @staticmethod
    def calculate_renta_para_mejorar(
        precio_unit_mejora: float,
        costo_unit_ars: float
    ) -> float | None:
        """Renta Para Mejorar = (Precio Unit Mejora / Costo Unit ARS) - 1."""
        result = RowCalculator.safe_div(precio_unit_mejora, costo_unit_ars)
        if result is None:
            return None
        return result - 1.0


class RowEditorDialog:
    """Diálogo para editar datos de un renglón."""
    
    def __init__(
        self,
        parent: ctk.CTk,
        row: UIRow,
        db_runtime,
        table_mgr: TableManager,
    ):
        """
        Args:
            parent: Ventana padre
            row: UIRow a editar
            db_runtime: AppRuntime para persistencia
            table_mgr: TableManager para re-renderizar después
        """
        self.parent = parent
        self.row = row
        self.db_runtime = db_runtime
        self.table_mgr = table_mgr
        self.win = None
        self.entries: dict[str, tk.Widget] = {}
        self.entry_vars: dict[str, tk.StringVar] = {}
        self.money_fields = {"costo_unit_ars", "costo_total_ars"}
        self._money_format_guard = False
        self.alert_engine = AlertEngine()
        self.fmt = DataFormatter
        self.calc = RowCalculator
    
    def show(self) -> None:
        """Abre el diálogo modal."""
        if not self.row.renglon_pk:
            messagebox.showwarning("Atención", "El renglón todavía no está listo.")
            return
        
        self._build_dialog()
    
    def _build_dialog(self) -> None:
        """Construye diálogo con tema LIGHT y mejor UX."""
        self.win = ctk.CTkToplevel(self.parent)
        self.win.title(f"Editar: {self.row.desc}")
        self.win.geometry("600x700")
        self.win.resizable(True, True)
        
        # Hacer que la ventana sea siempre sobre la principal
        self.win.transient(self.parent)
        
        # Centrar en pantalla relative a la ventana principal
        self.win.update_idletasks()
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_w = self.parent.winfo_width()
        parent_h = self.parent.winfo_height()
        
        x = parent_x + (parent_w - 600) // 2
        y = parent_y + (parent_h - 700) // 2
        self.win.geometry(f"600x700+{x}+{y}")
        
        # Body principal - TEMA CLARO
        body = ctk.CTkFrame(self.win, fg_color="#FFFFFF")
        body.pack(fill="both", expand=True)
        
        # Header
        header = ctk.CTkFrame(body, fg_color="#F5F5F5", corner_radius=0)
        header.pack(fill="x", padx=0, pady=0)
        
        ctk.CTkLabel(
            header,
            text=f"📋 {self.row.desc}",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#1A1A1A",
        ).pack(anchor="w", padx=20, pady=(15, 5))
        
        ctk.CTkLabel(
            header,
            text=f"ID: {self.row.id_renglon} • Qty: {self.row.cantidad or 'N/A'}",
            font=ctk.CTkFont(size=10),
            text_color="#666666",
        ).pack(anchor="w", padx=20, pady=(0, 15))
        
        # Separator
        sep = ctk.CTkFrame(header, height=1, fg_color="#DDDDDD")
        sep.pack(fill="x")
        
        # Canvas con scroll
        canvas = tk.Canvas(
            body,
            highlightthickness=0,
            bg="#FFFFFF",
            relief="flat",
            borderwidth=0,
        )
        canvas.pack(side="left", fill="both", expand=True)
        
        scroll = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        scroll.pack(side="right", fill="y")
        canvas.configure(yscrollcommand=scroll.set)
        
        frame = ctk.CTkFrame(canvas, fg_color="#FFFFFF")
        frame_id = canvas.create_window((0, 0), window=frame, anchor="nw")
        
        def on_frame_config(_ev=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            if canvas.winfo_width() > 1:
                canvas.itemconfig(frame_id, width=canvas.winfo_width())
        
        frame.bind("<Configure>", on_frame_config)
        
        # Cargar config
        cfg = self.db_runtime.get_renglon_config(renglon_id=self.row.renglon_pk) or {}
        
        # Secciones de campos
        self._build_section(frame, "Datos Generales")
        self._add_entry(frame, "Unidad de medida", "unidad_medida", self.row.unidad_medida)
        self._add_entry(frame, "Marca", "marca", self.row.marca)
        
        self._build_section(frame, "Observaciones Usuario")
        ctk.CTkLabel(
            frame,
            text="Observaciones Usuario",
            text_color="#1A1A1A",
            font=ctk.CTkFont(size=10, weight="bold"),
        ).pack(anchor="w", padx=20, pady=(15, 8))
        
        txt_obs = tk.Text(
            frame,
            height=4,
            bg="#F9F9F9",
            fg="#1A1A1A",
            insertbackground="#1A1A1A",
            font=("Segoe UI", 10),
            relief="solid",
            borderwidth=1,
        )
        txt_obs.pack(fill="x", padx=20, pady=(0, 15))
        if self.row.obs_usuario:
            txt_obs.insert("1.0", self.row.obs_usuario)
        self.entries["obs_usuario"] = txt_obs
        
        self._build_section(frame, "Costos & Conversión")
        self._add_entry(
            frame,
            "Conversión USD",
            "conv_usd",
            self.row.conv_usd,
            help="$ pesos por 1 USD",
        )
        self._add_entry(
            frame,
            "Costo Unit ARS",
            "costo_unit_ars",
            self.row.costo_unit_ars,
            help="Costo unitario en pesos argentinos",
        )
        self._add_entry(
            frame,
            "Costo Total ARS",
            "costo_total_ars",
            self.row.costo_total_ars,
            help="Costo total en pesos argentinos",
        )
        
        self._build_section(frame, "Rentabilidad")
        
        # Mostrar renta_minima como fraccion (0-1) para evitar ambiguedad
        renta_display = None
        if self.row.renta_minima is not None:
            renta_display = f"{self.row.renta_minima:.2f}"
        
        self._add_entry(
            frame,
            "Renta Mínima (0 a 1)",
            "renta_minima",
            renta_display,
            help="🔢 Ingrese un valor entre 0 y 1 (ej: 0.30 para 30%, 0.15 para 15%).",
        )
        
        self._build_section(frame, "Control de Seguimiento")
        
        # 🔥 Checkbox para marcar "Seguir este renglón"
        check_frame = ctk.CTkFrame(frame, fg_color="transparent")
        check_frame.pack(fill="x", padx=20, pady=(8, 15))
        
        self.check_seguir = tk.BooleanVar(value=bool(cfg.get("seguir", False)))
        ctk.CTkCheckBox(
            check_frame,
            text="✅ Seguir este renglón (activa alertas)",
            variable=self.check_seguir,
            onvalue=True,
            offvalue=False,
            text_color="#1A1A1A",
            fg_color="#4CAF50",
            checkmark_color="#FFFFFF",
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=0, pady=6)
        
        ctk.CTkLabel(
            check_frame,
            text="💡 Al activar, recibirás notificaciones cuando cambie el precio o la oferta.",
            font=ctk.CTkFont(size=9),
            text_color="#999999",
        ).pack(anchor="w", pady=(4, 0))
        
        # Botones - Footer
        footer = ctk.CTkFrame(self.win, fg_color="#F5F5F5", corner_radius=0)
        footer.pack(fill="x", padx=20, pady=(12, 15))
        
        btns_left = ctk.CTkFrame(footer, fg_color="transparent")
        btns_left.pack(side="left")
        
        ctk.CTkButton(
            btns_left,
            text="✅ Guardar",
            command=self._save,
            fg_color="#4CAF50",
            hover_color="#45a049",
            text_color="#FFFFFF",
            width=120,
            height=36,
        ).pack(side="left", padx=6)
        
        ctk.CTkButton(
            btns_left,
            text="❌ Cancelar",
            command=self.win.destroy,
            fg_color="#E0E0E0",
            hover_color="#D0D0D0",
            text_color="#1A1A1A",
            width=120,
            height=36,
        ).pack(side="left", padx=6)
    
    def _build_section(self, parent, title: str) -> None:
        """Crea un separador/sección con tema claro."""
        sep = ctk.CTkFrame(parent, height=1, fg_color="#E0E0E0")
        sep.pack(fill="x", padx=20, pady=(16, 10))
        
        ctk.CTkLabel(
            parent,
            text=title,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#1A7F00",
        ).pack(anchor="w", padx=20, pady=(0, 8))
    
    def _add_entry(
        self,
        parent,
        label: str,
        key: str,
        value: str | float | None = None,
        help: str = "",
        required: bool = False,
    ) -> None:
        """Crea label + entry field con tema claro."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=(0, 12))
        
        label_text = f"{label}" + (" *" if required else "")
        ctk.CTkLabel(
            frame,
            text=label_text,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#333333" if not required else "#FF7043",
        ).pack(anchor="w")
        
        var = tk.StringVar()
        ent = ctk.CTkEntry(
            frame,
            textvariable=var,
            height=36,
            font=ctk.CTkFont(size=11),
            fg_color="#F9F9F9",
            text_color="#1A1A1A",
            border_color="#CCCCCC",
            border_width=1,
        )
        ent.pack(fill="x", pady=(6, 0))
        self.entry_vars[key] = var
        if value is not None:
            if key in self.money_fields:
                parsed_value = self.fmt.parse_float(str(value))
                if parsed_value is not None:
                    var.set(self._format_money_for_edit(parsed_value))
                else:
                    var.set(str(value))
            else:
                var.set(str(value))

        if key in self.money_fields:
            self._bind_money_entry(ent, key)
        self.entries[key] = ent
        
        if help:
            ctk.CTkLabel(
                frame,
                text=f"💡 {help}",
                font=ctk.CTkFont(size=9),
                text_color="#999999",
            ).pack(anchor="w", pady=(4, 0))

    def _bind_money_entry(self, entry: ctk.CTkEntry, key: str) -> None:
        """Formatea campos de dinero en vivo para evitar errores con ceros."""
        entry.bind("<KeyRelease>", lambda _e, k=key: self._on_money_key_release(k), add="+")
        entry.bind("<FocusOut>", lambda _e, k=key: self._on_money_focus_out(k), add="+")

    def _on_money_key_release(self, key: str) -> None:
        if self._money_format_guard:
            return
        var = self.entry_vars.get(key)
        if not var:
            return
        current = var.get()
        formatted = self._format_money_for_edit_input(current)
        if formatted != current:
            self._money_format_guard = True
            var.set(formatted)
            self.entries[key].icursor("end")
            self._money_format_guard = False

    def _on_money_focus_out(self, key: str) -> None:
        if self._money_format_guard:
            return
        var = self.entry_vars.get(key)
        if not var:
            return
        parsed = self.fmt.parse_float(var.get())
        if parsed is None:
            return
        self._money_format_guard = True
        var.set(self._format_money_for_edit(parsed))
        self._money_format_guard = False

    @staticmethod
    def _group_thousands(digits: str) -> str:
        if not digits:
            return ""
        chunks = []
        while digits:
            chunks.append(digits[-3:])
            digits = digits[:-3]
        return ".".join(reversed(chunks))

    def _format_money_for_edit_input(self, raw: str) -> str:
        """Formato editable: separador de miles con '.' y decimal opcional con ','."""
        if raw is None:
            return ""
        s = str(raw).strip()
        if not s:
            return ""

        filtered = "".join(ch for ch in s if ch.isdigit() or ch in ",.")
        if not filtered:
            return ""

        last_comma = filtered.rfind(",")
        last_dot = filtered.rfind(".")
        sep_pos = max(last_comma, last_dot)

        decimal_part = ""
        if sep_pos != -1 and (len(filtered) - sep_pos - 1) <= 2:
            integer_digits = "".join(ch for ch in filtered[:sep_pos] if ch.isdigit())
            decimal_part = "".join(ch for ch in filtered[sep_pos + 1 :] if ch.isdigit())[:2]
        else:
            integer_digits = "".join(ch for ch in filtered if ch.isdigit())

        integer_fmt = self._group_thousands(integer_digits)
        if decimal_part:
            return f"{integer_fmt},{decimal_part}"
        return integer_fmt

    def _format_money_for_edit(self, value: float) -> str:
        money = self.fmt.format_money(value)
        return money.replace("$ ", "")
    
    def _save(self) -> None:
        """Guarda los cambios con validación mejorada."""
        # Parsear valores
        unidad_medida = self.entries["unidad_medida"].get().strip() or None
        marca = self.entries["marca"].get().strip() or None
        obs_usuario = self.entries["obs_usuario"].get("1.0", "end").strip() or None
        conv_usd = self.fmt.parse_float(self.entries["conv_usd"].get())
        costo_unit_ars = self.fmt.parse_float(self.entries["costo_unit_ars"].get())
        costo_total_ars = self.fmt.parse_float(self.entries["costo_total_ars"].get())
        
        # Renta minima en fraccion (0-1)
        renta_minima_input = self.fmt.parse_float(self.entries["renta_minima"].get())
        renta_minima = None
        utilidad_min_pct = None  # Se deriva de renta_minima (mismo valor)

        if renta_minima_input is not None:
            renta_minima = renta_minima_input
            utilidad_min_pct = renta_minima_input * 100
        
        # Validaciones con mensajes claros
        if costo_unit_ars is None and costo_total_ars is None:
            messagebox.showerror(
                "❌ Validación",
                "Debe ingresar al menos COSTO UNIT ARS o COSTO TOTAL ARS.",
            )
            return
        
        if costo_unit_ars is not None and costo_unit_ars <= 0:
            messagebox.showerror(
                "❌ Validación",
                "COSTO UNIT ARS debe ser mayor a 0.",
            )
            return
        
        if costo_total_ars is not None and costo_total_ars <= 0:
            messagebox.showerror(
                "❌ Validación",
                "COSTO TOTAL ARS debe ser mayor a 0.",
            )
            return
        
        if renta_minima is not None and renta_minima < 0:
            messagebox.showerror(
                "❌ Validación",
                f"RENTA MINIMA debe ser al menos 0.0 (0% utilidad).\n\nValor recibido: {renta_minima:.2f}\n\n💡 Ingrese un numero entre 0 y 1 (ej: 0.30 para 30%)",
            )
            return
        if renta_minima is not None and renta_minima > 1:
            messagebox.showerror(
                "❌ Validación",
                f"RENTA MINIMA debe estar entre 0 y 1 (ej: 0.30 para 30%).\n\nValor recibido: {renta_minima:.2f}",
            )
            return
        
        if conv_usd is not None and conv_usd <= 0:
            messagebox.showwarning(
                "⚠️  Advertencia",
                "CONVERSIÓN USD debe ser > 0 para cálculos correctos.",
            )
        
        # Guardar en DB
        seguir = self.check_seguir.get()
        # Persistir siempre el estado de seguimiento (incluye desmarcar).
        self.db_runtime.update_renglon_config(
            renglon_id=self.row.renglon_pk,
            utilidad_min_pct=utilidad_min_pct,
            seguir=seguir,
        )
        
        # 🔥 Recalcular campos derivados ANTES de guardar (para incluir USD)
        self._recalculate_derived_fields(
            conv_usd, costo_unit_ars, costo_total_ars, renta_minima
        )
        
        # Obtener USD recalculados de self.row
        costo_unit_usd = self.row.costo_unit_usd
        costo_total_usd = self.row.costo_total_usd
        
        self.db_runtime.update_renglon_excel(
            renglon_id=self.row.renglon_pk,
            unidad_medida=unidad_medida,
            marca=marca,
            obs_usuario=obs_usuario,
            conversion_usd=conv_usd,
            costo_unit_ars=costo_unit_ars,
            costo_total_ars=costo_total_ars,
            costo_unit_usd=costo_unit_usd,
            costo_total_usd=costo_total_usd,
            renta_minima=renta_minima,
        )
        
        # 🎯 LOGGING: Mostrar lo que se guardó
        print(f"\n{'='*60}")
        print(f"[USUARIO] Editó renglón: {self.row.id_renglon} - {self.row.desc[:50]}")
        print(f"{'='*60}")
        print(f"[GUARDADO EN BD]:")
        if costo_unit_ars:
            print(f"  costo_unit_ars = {costo_unit_ars:,.2f}")
        if costo_total_ars:
            print(f"  costo_total_ars = {costo_total_ars:,.2f}")
        if costo_unit_usd:
            print(f"  costo_unit_usd = {costo_unit_usd:,.2f}")
        if costo_total_usd:
            print(f"  costo_total_usd = {costo_total_usd:,.2f}")
        if renta_minima:
            # Mostrar tanto el valor interno como el % legible
            pct = (renta_minima - 1.0) * 100 if renta_minima >= 1 else renta_minima * 100
            print(f"  renta_minima = {renta_minima:.2f} (equivale a {pct:.0f}% utilidad)")
        if conv_usd:
            print(f"  conv_usd = {conv_usd:,.2f}")
        print(f"{'='*60}\n")
        
        # Actualizar row en cache
        self.row.unidad_medida = unidad_medida
        self.row.marca = marca
        self.row.obs_usuario = obs_usuario
        self.row.conv_usd = conv_usd
        self.row.costo_unit_ars = costo_unit_ars
        self.row.costo_total_ars = costo_total_ars
        self.row.renta_minima = renta_minima
        self.row.seguir = bool(seguir)
        
        # Aplicar color inmediatamente (sin esperar próximo UPDATE del collector)
        style = self._resolve_row_style_after_edit()
        from app.ui.formatters import DisplayValues
        row_values = DisplayValues.build_row_values(self.row)
        self.table_mgr.render_row(self.row.id_renglon, row_values, style)
        try:
            # Forzar reevaluacion de filtros del parent (e.g. "Solo seguimiento")
            if hasattr(self.parent, "_apply_filters"):
                self.parent._apply_filters()
        except Exception:
            pass
        
        messagebox.showinfo("✅ Éxito", f"Se guardaron los cambios a {self.row.desc}")
        self.win.destroy()

    def _resolve_row_style_after_edit(self) -> str:
        """Replica lógica de alertas para colorear fila al instante tras edición."""
        cfg = self.db_runtime.get_renglon_config(renglon_id=self.row.renglon_pk) or {}
        tracked = bool(self.row.seguir or self.row.costo_unit_ars)
        oferta_mia = bool(cfg.get("oferta_mia", False))
        utilidad_min_pct = (
            float(self.row.renta_minima) * 100.0
            if self.row.renta_minima is not None
            else float(cfg.get("utilidad_min_pct", 10.0))
        )

        utilidad_pct = None
        if self.row.renta_para_mejorar is not None:
            utilidad_pct = float(self.row.renta_para_mejorar) * 100.0

        decision = self.alert_engine.decide(
            tracked=tracked,
            oferta_mia=oferta_mia,
            utilidad_pct=utilidad_pct,
            utilidad_min_pct=utilidad_min_pct,
            ocultar_bajo_umbral=bool(cfg.get("ocultar_bajo_umbral", False)),
            changed=False,
            http_status=200,
            mensaje="",
        )
        return decision.style.value
    
    def _recalculate_derived_fields(
        self,
        conv_usd: float | None,
        costo_unit_ars: float | None,
        costo_total_ars: float | None,
        renta_minima: float | None,
    ) -> None:
        """Recalcula e actualiza campos derivados en row."""
        # Resolver bidirecionaldad costo unit <-> total
        if costo_total_ars and self.row.cantidad:
            costo_unit_ars = costo_total_ars / self.row.cantidad
        elif costo_unit_ars and self.row.cantidad:
            costo_total_ars = costo_unit_ars * self.row.cantidad
        
        # 🔥 Costo USD (UNITARIO y TOTAL)
        if conv_usd not in (None, 0):
            if costo_unit_ars:
                self.row.costo_unit_usd = costo_unit_ars / conv_usd
            if costo_total_ars:
                self.row.costo_total_usd = costo_total_ars / conv_usd
        
        # Precio Unit Aceptable
        self.row.precio_unit_aceptable = self.calc.calculate_precio_unit_aceptable(
            renta_minima, costo_unit_ars
        ) if renta_minima and costo_unit_ars else None
        
        # Precio Total Aceptable
        self.row.precio_total_aceptable = self.calc.calculate_precio_total_aceptable(
            self.row.cantidad, self.row.precio_unit_aceptable
        ) if self.row.cantidad and self.row.precio_unit_aceptable else None
        
        # Renta Referencia
        self.row.renta_referencia = self.calc.calculate_renta_referencia(
            self.row.precio_ref_unitario, costo_unit_ars
        ) if self.row.precio_ref_unitario and costo_unit_ars else None
        
        # Precio Unit Mejora
        self.row.precio_unit_mejora = self.calc.calculate_precio_unit_mejora(
            self.row.oferta_para_mejorar, self.row.cantidad
        ) if self.row.oferta_para_mejorar and self.row.cantidad else None
        
        # Renta Para Mejorar
        self.row.renta_para_mejorar = self.calc.calculate_renta_para_mejorar(
            self.row.precio_unit_mejora, costo_unit_ars
        ) if self.row.precio_unit_mejora and costo_unit_ars else None
