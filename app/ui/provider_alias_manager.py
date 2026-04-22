"""
Dialogo para administrar alias de proveedores.

Responsabilidad unica:
- listar alias existentes
- crear/editar un alias por id_proveedor
- eliminar alias
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

import customtkinter as ctk


class ProviderAliasManager:
    """Gestiona el maestro de proveedores desde una ventana simple."""

    def __init__(self, runtime, logger):
        self.runtime = runtime
        self.log = logger

    def show_dialog(self, parent_window: ctk.CTk, *, suggested_provider_id: str | None = None) -> None:
        win = ctk.CTkToplevel(parent_window)
        win.title("Maestro de Proveedores")
        win.geometry("860x520")
        win.transient(parent_window)

        win.update_idletasks()
        parent_x = parent_window.winfo_x()
        parent_y = parent_window.winfo_y()
        parent_w = parent_window.winfo_width()
        parent_h = parent_window.winfo_height()
        x = parent_x + (parent_w - 860) // 2
        y = parent_y + (parent_h - 520) // 2
        win.geometry(f"860x520+{x}+{y}")

        header = ctk.CTkFrame(win, fg_color="#F5F5F5", corner_radius=0)
        header.pack(fill="x", padx=0, pady=0)

        ctk.CTkLabel(
            header,
            text="Maestro de Proveedores",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#1A1A1A",
        ).pack(anchor="w", padx=20, pady=(15, 5))

        ctk.CTkLabel(
            header,
            text="Carga alias para IDs de proveedor. Se usan en logs solo si el toggle de resolucion esta activado.",
            font=ctk.CTkFont(size=10),
            text_color="#666666",
        ).pack(anchor="w", padx=20, pady=(0, 15))

        ctk.CTkFrame(header, height=1, fg_color="#E0E0E0").pack(fill="x")

        body = ctk.CTkFrame(win, fg_color="#FFFFFF")
        body.pack(fill="both", expand=True, padx=20, pady=20)

        left = ctk.CTkFrame(body, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=(0, 14))

        ctk.CTkLabel(
            left,
            text="Proveedores cargados",
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(anchor="w", pady=(0, 8))

        columns = ("id_proveedor", "alias", "activo")
        tree = ttk.Treeview(left, columns=columns, show="headings", height=14, selectmode="browse")
        tree.pack(fill="both", expand=True, side="left")

        tree.heading("id_proveedor", text="ID Proveedor")
        tree.heading("alias", text="Alias")
        tree.heading("activo", text="Activo")
        tree.column("id_proveedor", width=160, stretch=False)
        tree.column("alias", width=220, stretch=True)
        tree.column("activo", width=70, stretch=False, anchor="center")

        yscroll = ttk.Scrollbar(left, orient="vertical", command=tree.yview)
        yscroll.pack(side="right", fill="y")
        tree.configure(yscrollcommand=yscroll.set)

        right = ctk.CTkFrame(body, fg_color="#FAFAFA")
        right.pack(side="right", fill="y", padx=(14, 0))

        ctk.CTkLabel(
            right,
            text="Edicion",
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 8))

        id_var = tk.StringVar(value=str(suggested_provider_id or "").strip())
        alias_var = tk.StringVar(value="")
        active_var = tk.BooleanVar(value=True)

        ctk.CTkLabel(right, text="ID proveedor").pack(anchor="w", padx=16, pady=(4, 2))
        id_entry = ctk.CTkEntry(right, textvariable=id_var, width=240, placeholder_text="Ej: 30718165")
        id_entry.pack(anchor="w", padx=16)

        ctk.CTkLabel(right, text="Alias / Empresa").pack(anchor="w", padx=16, pady=(12, 2))
        alias_entry = ctk.CTkEntry(right, textvariable=alias_var, width=240, placeholder_text="Ej: Empresa X")
        alias_entry.pack(anchor="w", padx=16)

        ctk.CTkLabel(right, text="Notas").pack(anchor="w", padx=16, pady=(12, 2))
        notes_text = tk.Text(right, width=30, height=8, wrap="word")
        notes_text.pack(anchor="w", padx=16)

        ctk.CTkSwitch(
            right,
            text="Activo",
            variable=active_var,
        ).pack(anchor="w", padx=16, pady=(12, 4))

        selected_id: dict[str, str | None] = {"value": None}
        records_by_id: dict[str, dict] = {}

        def _load_form(record: dict | None) -> None:
            selected_id["value"] = None if not record else str(record["id_proveedor"])
            id_var.set("" if not record else str(record["id_proveedor"]))
            alias_var.set("" if not record else str(record["alias"]))
            active_var.set(True if not record else bool(record["activo"]))
            notes_text.delete("1.0", "end")
            if record and record.get("notas"):
                notes_text.insert("1.0", str(record["notas"]))

        def _refresh_list(select_id: str | None = None) -> None:
            records_by_id.clear()
            for iid in tree.get_children():
                tree.delete(iid)
            for record in self.runtime.list_provider_aliases():
                provider_id = str(record["id_proveedor"])
                records_by_id[provider_id] = record
                tree.insert(
                    "",
                    "end",
                    iid=provider_id,
                    values=(
                        provider_id,
                        record["alias"],
                        "Si" if record["activo"] else "No",
                    ),
                )
            if select_id and tree.exists(select_id):
                tree.selection_set(select_id)
                tree.focus(select_id)
                _load_form(records_by_id.get(select_id))

        def _save() -> None:
            provider_id = id_var.get().strip()
            alias = alias_var.get().strip()
            notas = notes_text.get("1.0", "end").strip()
            if not provider_id:
                messagebox.showwarning("Atencion", "Ingresa un ID de proveedor.")
                return
            if not alias:
                messagebox.showwarning("Atencion", "Ingresa un alias o nombre de empresa.")
                return
            try:
                self.runtime.save_provider_alias(
                    id_proveedor=provider_id,
                    alias=alias,
                    notas=notas or None,
                    activo=bool(active_var.get()),
                )
                self.log(f"🪪 Alias proveedor guardado: {alias} (id={provider_id})")
                _refresh_list(select_id=provider_id)
            except Exception as exc:
                messagebox.showerror("Error", f"No se pudo guardar el proveedor:\n{exc}")

        def _delete() -> None:
            provider_id = id_var.get().strip()
            if not provider_id:
                return
            if not messagebox.askyesno(
                "Confirmar",
                f"¿Eliminar alias del proveedor {provider_id}?",
            ):
                return
            try:
                self.runtime.delete_provider_alias(id_proveedor=provider_id)
                self.log(f"🪪 Alias proveedor eliminado: id={provider_id}")
                _refresh_list()
                _load_form(None)
            except Exception as exc:
                messagebox.showerror("Error", f"No se pudo eliminar el proveedor:\n{exc}")

        def _new() -> None:
            _load_form(None)
            if suggested_provider_id:
                id_var.set(str(suggested_provider_id).strip())
            id_entry.focus_set()

        def _on_select(_event=None) -> None:
            selection = tree.selection()
            if not selection:
                return
            provider_id = str(selection[0])
            _load_form(records_by_id.get(provider_id))

        tree.bind("<<TreeviewSelect>>", _on_select)

        btns = ctk.CTkFrame(right, fg_color="transparent")
        btns.pack(fill="x", padx=12, pady=(16, 0))

        ctk.CTkButton(btns, text="Nuevo", command=_new, width=90).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Guardar", command=_save, width=90, fg_color="#2E7D32", hover_color="#27682B").pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Eliminar", command=_delete, width=90, fg_color="#C62828", hover_color="#AD2020").pack(side="left", padx=4)

        footer = ctk.CTkFrame(win, fg_color="#F5F5F5", corner_radius=0)
        footer.pack(fill="x", padx=0, pady=0)
        ctk.CTkFrame(footer, height=1, fg_color="#E0E0E0").pack(fill="x")

        footer_btns = ctk.CTkFrame(footer, fg_color="#F5F5F5")
        footer_btns.pack(fill="x", padx=16, pady=12)

        ctk.CTkButton(
            footer_btns,
            text="Cerrar",
            command=win.destroy,
            width=120,
            fg_color="#E0E0E0",
            hover_color="#D0D0D0",
            text_color="#1A1A1A",
        ).pack(side="right")

        _refresh_list(select_id=str(suggested_provider_id).strip() if suggested_provider_id else None)
        if suggested_provider_id and str(suggested_provider_id).strip() not in records_by_id:
            id_var.set(str(suggested_provider_id).strip())
        if not suggested_provider_id:
            _new()
