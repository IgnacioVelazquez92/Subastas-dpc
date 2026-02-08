# app/ui/column_manager.py
"""
Gestión de visibilidad y orden de columnas.

Responsabilidad única: Dialog de columnas + persistencia de configuración.
"""

from __future__ import annotations

import json
import tkinter as tk
import customtkinter as ctk
from tkinter import ttk, messagebox

from app.ui.table_manager import TableConfig


class ColumnManager:
    """Gestiona visibilidad, orden y persistencia de columnas."""
    
    def __init__(self, tree: ttk.Treeview, db_runtime, table_config: TableConfig):
        """
        Args:
            tree: Treeview a controlar
            db_runtime: AppRuntime para persistencia
            table_config: Configuración estática de columnas
        """
        self.tree = tree
        self.db_runtime = db_runtime
        self.config = table_config
    
    def load_visible_columns(self, default_cols: list[str]) -> None:
        """Carga columnas visibles desde persistencia o usa defaults."""
        raw = self.db_runtime.get_ui_config(key="visible_columns")
        
        if not raw:
            self.tree.configure(displaycolumns=tuple(default_cols))
            self.save_visible_columns(default_cols)
            return
        
        try:
            cols = json.loads(raw)
        except Exception:
            return
        
        if cols:
            valid = [c for c in cols if c in self.config.columns]
            if valid:
                self.tree.configure(displaycolumns=tuple(valid))
                return
        
        # Fallback a defaults si config guardada es inválida
        self.tree.configure(displaycolumns=tuple(default_cols))
        self.save_visible_columns(default_cols)
    
    def save_visible_columns(self, cols: list[str]) -> None:
        """Persiste columnas visibles en DB."""
        self.db_runtime.set_ui_config(
            key="visible_columns",
            value=json.dumps(cols)
        )
    
    def get_visible_columns(self) -> list[str]:
        """Retorna lista de columnas actualmente visibles."""
        current = self.tree.cget("displaycolumns")
        if not current or current == ("#all",):
            return list(self.config.columns)
        return list(current)
    
    def set_visible_columns(self, cols: list[str]) -> None:
        """Cambia columnas visibles."""
        self.tree.configure(displaycolumns=tuple(cols))
        self.save_visible_columns(cols)
    
    def show_dialog(self, parent_window: ctk.CTk) -> None:
        """Abre diálogo de configuración de columnas."""
        win = ctk.CTkToplevel(parent_window)
        win.title("Columnas")
        win.geometry("520x420")
        
        body = ctk.CTkFrame(win)
        body.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Panel izquierdo: columnas visibles
        left = ctk.CTkFrame(body)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        ctk.CTkLabel(left, text="Visibles (orden)").pack(anchor="w")
        list_visible = tk.Listbox(left, selectmode="browse")
        list_visible.pack(fill="both", expand=True)
        
        # Panel derecho: columnas ocultas
        right = ctk.CTkFrame(body)
        right.pack(side="right", fill="both", expand=True, padx=(6, 0))
        ctk.CTkLabel(right, text="Ocultas").pack(anchor="w")
        list_hidden = tk.Listbox(right, selectmode="browse")
        list_hidden.pack(fill="both", expand=True)
        
        # Llenar listas iniciales
        current = self.get_visible_columns()
        current_list = list(current)
        hidden_list = [c for c in self.config.columns if c not in current_list]
        
        for c in current_list:
            label = self.config.column_labels.get(c, c)
            list_visible.insert("end", label)
        
        for c in hidden_list:
            label = self.config.column_labels.get(c, c)
            list_hidden.insert("end", label)
        
        # Helpers
        def label_to_col(label: str) -> str:
            for k, v in self.config.column_labels.items():
                if v == label:
                    return k
            return label
        
        def move_selected(src: tk.Listbox, dst: tk.Listbox):
            sel = src.curselection()
            if not sel:
                return
            idx = sel[0]
            label = src.get(idx)
            src.delete(idx)
            dst.insert("end", label)
        
        def move_up():
            sel = list_visible.curselection()
            if not sel or sel[0] <= 0:
                return
            idx = sel[0]
            label = list_visible.get(idx)
            list_visible.delete(idx)
            list_visible.insert(idx - 1, label)
            list_visible.selection_set(idx - 1)
        
        def move_down():
            sel = list_visible.curselection()
            if not sel or sel[0] >= list_visible.size() - 1:
                return
            idx = sel[0]
            label = list_visible.get(idx)
            list_visible.delete(idx)
            list_visible.insert(idx + 1, label)
            list_visible.selection_set(idx + 1)
        
        # Botones de operaciones
        btns = ctk.CTkFrame(win)
        btns.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkButton(
            btns, text="Agregar",
            command=lambda: move_selected(list_hidden, list_visible)
        ).pack(side="left", padx=4)
        
        ctk.CTkButton(
            btns, text="Quitar",
            command=lambda: move_selected(list_visible, list_hidden)
        ).pack(side="left", padx=4)
        
        ctk.CTkButton(btns, text="Subir", command=move_up).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="Bajar", command=move_down).pack(side="left", padx=6)
        
        # Botones finales
        def apply_changes():
            labels = list(list_visible.get(0, "end"))
            if not labels:
                messagebox.showwarning(
                    "Atención",
                    "Debe quedar al menos una columna visible."
                )
                return
            cols = [label_to_col(l) for l in labels]
            self.set_visible_columns(cols)
            win.destroy()
        
        ctk.CTkButton(btns, text="Aplicar", command=apply_changes).pack(side="right", padx=6)
        ctk.CTkButton(btns, text="Cerrar", command=win.destroy).pack(side="right", padx=6)
