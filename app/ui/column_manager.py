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
                if "led" in self.config.columns and "led" not in valid:
                    valid = ["led"] + valid
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
        """Abre diálogo de configuración de columnas con tema LIGHT."""
        win = ctk.CTkToplevel(parent_window)
        win.title("Configurar Columnas")
        win.geometry("600x480")
        
        # Hacer que la ventana sea siempre sobre la principal
        win.transient(parent_window)
        
        # Centrar en pantalla
        win.update_idletasks()
        parent_x = parent_window.winfo_x()
        parent_y = parent_window.winfo_y()
        parent_w = parent_window.winfo_width()
        parent_h = parent_window.winfo_height()
        
        x = parent_x + (parent_w - 900) // 2
        y = parent_y + (parent_h - 480) // 2
        win.geometry(f"900x480+{x}+{y}")
        
        # Header
        header = ctk.CTkFrame(win, fg_color="#F5F5F5", corner_radius=0)
        header.pack(fill="x", padx=0, pady=0)
        
        ctk.CTkLabel(
            header,
            text="📊 Configurar Columnas",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#1A1A1A",
        ).pack(anchor="w", padx=20, pady=(15, 5))
        
        ctk.CTkLabel(
            header,
            text="Selecciona qué columnas deseas ver en la tabla",
            font=ctk.CTkFont(size=10),
            text_color="#666666",
        ).pack(anchor="w", padx=20, pady=(0, 15))
        
        sep = ctk.CTkFrame(header, height=1, fg_color="#E0E0E0")
        sep.pack(fill="x")
        
        # Body con tema LIGHT
        body = ctk.CTkFrame(win, fg_color="#FFFFFF")
        body.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Panel izquierdo: columnas visibles
        left = ctk.CTkFrame(body, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        ctk.CTkLabel(
            left,
            text="✅ Columnas Visibles",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#1A7F00",
        ).pack(anchor="w", pady=(0, 8))
        list_visible = tk.Listbox(
            left,
            selectmode="browse",
            bg="#F9F9F9",
            fg="#1A1A1A",
            selectbackground="#4CAF50",
            selectforeground="#FFFFFF",
            font=("Segoe UI", 10),
            relief="solid",
            borderwidth=1,
        )
        list_visible.pack(fill="both", expand=True)
        
        # Panel derecho: columnas ocultas
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.pack(side="right", fill="both", expand=True, padx=(10, 0))
        ctk.CTkLabel(
            right,
            text="⭕ Columnas Ocultas",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#C62828",
        ).pack(anchor="w", pady=(0, 8))
        list_hidden = tk.Listbox(
            right,
            selectmode="browse",
            bg="#F9F9F9",
            fg="#1A1A1A",
            selectbackground="#F44336",
            selectforeground="#FFFFFF",
            font=("Segoe UI", 10),
            relief="solid",
            borderwidth=1,
        )
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
        
        # Botones de operaciones - LIGHT theme
        btns = ctk.CTkFrame(win, fg_color="#F5F5F5", corner_radius=0)
        btns.pack(fill="x", padx=0, pady=0)
        
        sep2 = ctk.CTkFrame(btns, height=1, fg_color="#E0E0E0")
        sep2.pack(fill="x")
        
        btns_inner = ctk.CTkFrame(btns, fg_color="#F5F5F5")
        btns_inner.pack(fill="x", padx=15, pady=12)
        
        ctk.CTkButton(
            btns_inner,
            text="➕",
            command=lambda: move_selected(list_hidden, list_visible),
            fg_color="#4CAF50",
            hover_color="#45a049",
            text_color="#FFFFFF",
        ).pack(side="left", padx=4)
        
        ctk.CTkButton(
            btns_inner,
            text="➖",
            command=lambda: move_selected(list_visible, list_hidden),
            fg_color="#F44336",
            hover_color="#EF5350",
            text_color="#FFFFFF",
        ).pack(side="left", padx=4)
        
        ctk.CTkButton(
            btns_inner,
            text="⬆️",
            command=move_up,
            fg_color="#2196F3",
            hover_color="#1976D2",
            text_color="#FFFFFF",
        ).pack(side="left", padx=4)
        
        ctk.CTkButton(
            btns_inner,
            text="⬇️",
            command=move_down,
            fg_color="#2196F3",
            hover_color="#1976D2",
            text_color="#FFFFFF",
        ).pack(side="left", padx=4)
        
        # Botones finales
        def apply_changes():
            labels = list(list_visible.get(0, "end"))
            if not labels:
                messagebox.showwarning(
                    "⚠️  Atención",
                    "Debe quedar al menos una columna visible.",
                )
                return
            cols = [label_to_col(l) for l in labels]
            self.set_visible_columns(cols)
            win.destroy()
        
        ctk.CTkButton(
            btns_inner,
            text="✅ Aplicar",
            command=apply_changes,
            fg_color="#1B5E20",
            hover_color="#2E7D32",
            text_color="#FFFFFF",
        ).pack(side="right", padx=4)
        
        ctk.CTkButton(
            btns_inner,
            text="❌ Cerrar",
            command=win.destroy,
            fg_color="#E0E0E0",
            hover_color="#D0D0D0",
            text_color="#1A1A1A",
        ).pack(side="right", padx=4)
