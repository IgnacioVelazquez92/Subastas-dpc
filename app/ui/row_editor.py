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
from app.core.alert_engine import RowStyle
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
        costo_final_pesos: float,
        conversion_usd: float
    ) -> float | None:
        """Costo en USD = Costo Final / Conversión."""
        return RowCalculator.safe_div(costo_final_pesos, conversion_usd)
    
    @staticmethod
    def calculate_subtotal_costo(
        cantidad: float,
        costo_final_pesos: float
    ) -> float | None:
        """Subtotal costo = Cantidad × Costo Final."""
        return RowCalculator.safe_mul(cantidad, costo_final_pesos)
    
    @staticmethod
    def calculate_p_unit_minimo(
        renta: float,
        costo_final_pesos: float
    ) -> float | None:
        """P. Unit Mínimo = Renta × Costo Final."""
        return RowCalculator.safe_mul(renta, costo_final_pesos)
    
    @staticmethod
    def calculate_subtotal(
        cantidad: float,
        p_unit_minimo: float
    ) -> float | None:
        """Subtotal = Cantidad × P. Unit Mínimo."""
        return RowCalculator.safe_mul(cantidad, p_unit_minimo)
    
    @staticmethod
    def calculate_renta_ref(
        precio_ref: float,
        costo_final_pesos: float
    ) -> float | None:
        """Renta Ref = (Precio Ref / Costo Final) - 1."""
        result = RowCalculator.safe_div(precio_ref, costo_final_pesos)
        if result is None:
            return None
        return result - 1.0
    
    @staticmethod
    def calculate_p_unit_mejora(
        subtotal_mejorar: float,
        cantidad: float
    ) -> float | None:
        """P. Unit Mejora = Subtotal Mejorar / Cantidad."""
        return RowCalculator.safe_div(subtotal_mejorar, cantidad)
    
    @staticmethod
    def calculate_dif_unit(
        p_unit_mejora: float,
        costo_final_pesos: float
    ) -> float | None:
        """Dif Unit = P. Unit Mejora - Costo Final Pesos."""
        if p_unit_mejora is None or costo_final_pesos is None:
            return None
        return p_unit_mejora - costo_final_pesos
    
    @staticmethod
    def calculate_renta_dpc(
        p_unit_mejora: float,
        costo_final_pesos: float
    ) -> float | None:
        """Renta DPC = (P. Unit Mejora / Costo Final) - 1."""
        result = RowCalculator.safe_div(p_unit_mejora, costo_final_pesos)
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
        self.fmt = DataFormatter
        self.calc = RowCalculator
    
    def show(self) -> None:
        """Abre el diálogo modal."""
        if not self.row.renglon_pk:
            messagebox.showwarning("Atención", "El renglón todavía no está listo.")
            return
        
        self._build_dialog()
    
    def _build_dialog(self) -> None:
        """Construye estructura del diálogo."""
        self.win = ctk.CTkToplevel(self.parent)
        self.win.title(f"Editar renglón {self.row.id_renglon}")
        self.win.geometry("520x520")
        
        # Canvas con scroll
        canvas = tk.Canvas(self.win, highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        
        scroll = ttk.Scrollbar(self.win, orient="vertical", command=canvas.yview)
        scroll.pack(side="right", fill="y")
        canvas.configure(yscrollcommand=scroll.set)
        
        frame = ctk.CTkFrame(canvas)
        frame_id = canvas.create_window((0, 0), window=frame, anchor="nw")
        
        def on_frame_config(_ev=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(frame_id, width=canvas.winfo_width())
        
        frame.bind("<Configure>", on_frame_config)
        
        # Cargar config
        cfg = self.db_runtime.get_renglon_config(renglon_id=self.row.renglon_pk) or {}
        
        # Campos
        self._add_entry(frame, "Unidad de medida", "unidad_medida", self.row.unidad_medida)
        
        qty_txt = "" if self.row.cantidad is None else str(self.row.cantidad)
        ctk.CTkLabel(frame, text=f"Cantidad (subasta): {qty_txt}").pack(anchor="w")
        
        self._add_entry(frame, "Marca", "marca", self.row.marca)
        
        ctk.CTkLabel(frame, text="Observaciones").pack(anchor="w")
        txt_obs = tk.Text(frame, height=4)
        txt_obs.pack(fill="x", pady=(0, 6))
        if self.row.observaciones:
            txt_obs.insert("1.0", self.row.observaciones)
        self.entries["observaciones"] = txt_obs
        
        self._add_entry(frame, "Conversión USD", "conversion_usd", self.row.conversion_usd)
        self._add_entry(frame, "Costo final pesos", "costo_final_pesos", self.row.costo_final_pesos)
        self._add_entry(frame, "Renta", "renta", self.row.renta)
        
        utilidad_min_pct = cfg.get("utilidad_min_pct", "")
        self._add_entry(frame, "Utilidad min %", "utilidad_min_pct", utilidad_min_pct)
        
        # Botones
        btns = ctk.CTkFrame(self.win)
        btns.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkButton(btns, text="Guardar", command=self._save).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="Cancelar", command=self.win.destroy).pack(side="right", padx=6)
    
    def _add_entry(
        self,
        parent,
        label: str,
        key: str,
        value: str | float | None = None
    ) -> None:
        """Crea label + entry field."""
        ctk.CTkLabel(parent, text=label).pack(anchor="w")
        ent = ctk.CTkEntry(parent)
        ent.pack(fill="x", pady=(0, 6))
        if value is not None:
            ent.insert(0, str(value))
        self.entries[key] = ent
    
    def _save(self) -> None:
        """Guarda los cambios."""
        # Parsear valores
        unidad_medida = self.entries["unidad_medida"].get().strip() or None
        marca = self.entries["marca"].get().strip() or None
        observaciones = self.entries["observaciones"].get("1.0", "end").strip() or None
        conversion_usd = self.fmt.parse_float(self.entries["conversion_usd"].get())
        costo_final_pesos = self.fmt.parse_float(self.entries["costo_final_pesos"].get())
        renta = self.fmt.parse_float(self.entries["renta"].get())
        utilidad_min_pct = self.fmt.parse_float(self.entries["utilidad_min_pct"].get())
        
        # Validaciones
        if costo_final_pesos is None or costo_final_pesos <= 0:
            messagebox.showwarning("Atención", "COSTO FINAL PESOS debe ser > 0.")
            return
        
        if renta is not None and renta < 0:
            messagebox.showwarning("Atención", "RENTA no puede ser negativa.")
            return
        
        # Guardar en DB
        if utilidad_min_pct is not None:
            self.db_runtime.update_renglon_config(
                renglon_id=self.row.renglon_pk,
                utilidad_min_pct=utilidad_min_pct,
            )
        
        self.db_runtime.update_renglon_excel(
            renglon_id=self.row.renglon_pk,
            unidad_medida=unidad_medida,
            marca=marca,
            observaciones=observaciones,
            conversion_usd=conversion_usd,
            costo_final_pesos=costo_final_pesos,
            renta=renta,
        )
        
        # Recalcular campos derivados
        self._recalculate_derived_fields(
            conversion_usd, costo_final_pesos, renta
        )
        
        # Actualizar row en cache
        self.row.unidad_medida = unidad_medida
        self.row.marca = marca
        self.row.observaciones = observaciones
        self.row.conversion_usd = conversion_usd
        self.row.costo_final_pesos = costo_final_pesos
        self.row.renta = renta
        
        # Renderizar
        style = RowStyle.TRACKED.value if self.row.seguir else RowStyle.NORMAL.value
        from app.ui.formatters import DisplayValues
        row_values = DisplayValues.build_row_values(self.row)
        self.table_mgr.render_row(self.row.id_renglon, row_values, style)
        
        self.win.destroy()
    
    def _recalculate_derived_fields(
        self,
        conversion_usd: float | None,
        costo_final_pesos: float | None,
        renta: float | None,
    ) -> None:
        """Recalcula e actualiza campos derivados en row."""
        # Costo USD
        self.row.costo_usd = self.calc.calculate_costo_usd(
            costo_final_pesos, conversion_usd
        ) if conversion_usd not in (None, 0) and costo_final_pesos else None
        
        # Subtotal costo
        self.row.subtotal_costo_pesos = self.calc.calculate_subtotal_costo(
            self.row.cantidad, costo_final_pesos
        ) if self.row.cantidad and costo_final_pesos else None
        
        # P. Unit Mínimo
        self.row.p_unit_minimo = self.calc.calculate_p_unit_minimo(
            renta, costo_final_pesos
        ) if renta and costo_final_pesos else None
        
        # Subtotal
        self.row.subtotal = self.calc.calculate_subtotal(
            self.row.cantidad, self.row.p_unit_minimo
        ) if self.row.cantidad and self.row.p_unit_minimo else None
        
        # Renta Ref
        self.row.renta_ref = self.calc.calculate_renta_ref(
            self.row.precio_ref_subasta, costo_final_pesos
        ) if self.row.precio_ref_subasta and costo_final_pesos else None
        
        # P. Unit Mejora
        self.row.p_unit_mejora = self.calc.calculate_p_unit_mejora(
            self.row.subtotal_para_mejorar, self.row.cantidad
        ) if self.row.subtotal_para_mejorar and self.row.cantidad else None
        
        # Dif Unit
        self.row.dif_unit = self.calc.calculate_dif_unit(
            self.row.p_unit_mejora, costo_final_pesos
        ) if self.row.p_unit_mejora and costo_final_pesos else None
        
        # Renta DPC
        self.row.renta_dpc = self.calc.calculate_renta_dpc(
            self.row.p_unit_mejora, costo_final_pesos
        ) if self.row.p_unit_mejora and costo_final_pesos else None
