# app/ui/app.py
"""
UI principal (CustomTkinter) - conectada a AppRuntime (Collector -> Engine -> UI).
"""

from __future__ import annotations

import json
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from queue import Empty
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.core.app_runtime import RuntimeHandles
from app.core.events import Event, EventType
from app.core.alert_engine import RowStyle, SoundCue
from app.utils.money import float_to_money_txt


def _pct(value: float) -> str:
    return f"{value:.2f}%"


def _fmt_money(value: float | None) -> str:
    if value is None:
        return ""
    try:
        return float_to_money_txt(float(value), decimals=2)
    except Exception:
        return ""


def _fmt_num(value: float | None, *, decimals: int = 2) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.{decimals}f}"
    except Exception:
        return ""


@dataclass
class UIRow:
    id_renglon: str
    desc: str = ""

    mejor_txt: str | None = None
    oferta_min_txt: str | None = None
    obs_det: str | None = None
    precio_ref_subasta: float | None = None

    id_subasta: str | None = None
    subasta_id: int | None = None
    renglon_pk: int | None = None

    unidad_medida: str | None = None
    cantidad: float | None = None
    marca: str | None = None
    observaciones: str | None = None
    conversion_usd: float | None = None
    costo_usd: float | None = None
    costo_final_pesos: float | None = None
    renta: float | None = None

    subtotal_para_mejorar: float | None = None
    subtotal_costo_pesos: float | None = None
    p_unit_minimo: float | None = None
    subtotal: float | None = None
    renta_ref: float | None = None
    p_unit_mejora: float | None = None
    dif_unit: float | None = None
    renta_dpc: float | None = None

    seguir: bool = False
    oferta_mia: bool = False


class App(ctk.CTk):
    def __init__(self, *, handles: RuntimeHandles):
        super().__init__()

        ctk.set_appearance_mode("System")
        self.title(f"Monitor de Subastas - {handles.mode}")
        self.geometry("1480x820")

        self.handles = handles
        self.engine_out_q = handles.engine_out_q
        self.collector_cmd_q = handles.collector_cmd_q

        self.rows: dict[str, UIRow] = {}
        self.iids: dict[str, str] = {}
        self._sort_state: dict[str, bool] = {}

        self._build_ui()

        # Poll de eventos desde engine
        self.after(100, self._poll_events)

    # -------------------------
    # UI
    # -------------------------
    def _build_ui(self):
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=10, pady=10)

        btn_browser = ctk.CTkButton(top, text="Abrir navegador", command=self.on_start_browser)
        btn_browser.pack(side="left")

        btn_cap = ctk.CTkButton(top, text="Capturar subasta actual", command=self.on_capture_current)
        btn_cap.pack(side="left", padx=8)

        btn_stop = ctk.CTkButton(top, text="Detener", command=self.on_stop)
        btn_stop.pack(side="left", padx=8)

        btn_import = ctk.CTkButton(top, text="Importar Excel", command=self.on_import_excel)
        btn_import.pack(side="left", padx=8)

        btn_export = ctk.CTkButton(top, text="Exportar Excel", command=self.on_export_excel)
        btn_export.pack(side="left", padx=8)

        btn_edit = ctk.CTkButton(top, text="Editar registro", command=self.on_edit_row)
        btn_edit.pack(side="left", padx=8)

        btn_cols = ctk.CTkButton(top, text="Columnas", command=self.on_columns)
        btn_cols.pack(side="left", padx=8)

        btn_clean = ctk.CTkButton(top, text="Liberar espacio", command=self.on_cleanup)
        btn_clean.pack(side="left", padx=8)

        self.lbl_status = ctk.CTkLabel(top, text="RUNNING", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_status.pack(side="right")

        body = ctk.CTkFrame(self)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.cols = (
            "id_subasta",
            "item",
            "desc",
            "unidad",
            "cantidad",
            "marca",
            "obs",
            "conv_usd",
            "costo_usd",
            "costo_final",
            "subtotal_costo",
            "renta",
            "p_unit_min",
            "subtotal",
            "renta_ref",
            "p_unit_mejora",
            "precio_ref_subasta",
            "mejor",
            "subtotal_mejorar",
            "dif_unit",
            "renta_dpc",
            "obs_det",
        )

        self.col_labels = {
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
        }

        widths = {
            "id_subasta": 110,
            "item": 90,
            "desc": 260,
            "mejor": 140,
            "precio_ref_subasta": 140,
            "obs_det": 220,
            "unidad": 130,
            "cantidad": 90,
            "marca": 120,
            "obs": 200,
            "conv_usd": 120,
            "costo_usd": 110,
            "costo_final": 130,
            "subtotal_costo": 140,
            "renta": 90,
            "p_unit_min": 120,
            "subtotal": 120,
            "renta_ref": 100,
            "p_unit_mejora": 120,
            "subtotal_mejorar": 150,
            "dif_unit": 100,
            "renta_dpc": 100,
        }

        self.tree = ttk.Treeview(body, columns=self.cols, show="headings", height=16)
        self.tree.pack(side="top", fill="both", expand=True)

        yscroll = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        yscroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=yscroll.set)

        xscroll = ttk.Scrollbar(body, orient="horizontal", command=self.tree.xview)
        xscroll.pack(side="bottom", fill="x")
        self.tree.configure(xscrollcommand=xscroll.set)

        for c in self.cols:
            self.tree.heading(c, text=self.col_labels.get(c, c))
            self.tree.column(c, width=widths.get(c, 120), anchor="w")

        # Sort en columnas clave
        self.tree.heading("item", command=lambda: self._sort_by("item", numeric=True))
        self.tree.heading("desc", command=lambda: self._sort_by("desc", numeric=False))

        self.tree.tag_configure(RowStyle.NORMAL.value, background="")
        self.tree.tag_configure(RowStyle.TRACKED.value, background="#e7f1ff")
        self.tree.tag_configure(RowStyle.WARNING.value, background="#fff3cd")
        self.tree.tag_configure(RowStyle.DANGER.value, background="#f8d7da")
        self.tree.tag_configure(RowStyle.SUCCESS.value, background="#d1e7dd")

        ctk.CTkLabel(self, text="Logs:").pack(anchor="w", padx=10)
        self.txt_log = tk.Text(self, height=8)
        self.txt_log.pack(fill="both", expand=False, padx=10, pady=(0, 10))

        self._apply_saved_columns(
            default_cols=[
                "id_subasta",
                "item",
                "desc",
                "unidad",
                "cantidad",
                "marca",
                "obs",
                "conv_usd",
                "costo_usd",
                "costo_final",
                "subtotal_costo",
                "renta",
                "p_unit_min",
                "subtotal",
                "renta_ref",
                "p_unit_mejora",
                "precio_ref_subasta",
                "mejor",
                "subtotal_mejorar",
                "dif_unit",
                "renta_dpc",
                "obs_det",
            ]
        )

    # -------------------------
    # Event loop
    # -------------------------
    def _poll_events(self):
        try:
            while True:
                ev: Event = self.engine_out_q.get_nowait()
                self._handle_event(ev)
        except Empty:
            pass

        self.after(100, self._poll_events)

    def _handle_event(self, ev: Event):
        self._log(f"[{ev.level}] {ev.type}: {ev.message}")

        if ev.type == EventType.START:
            self.lbl_status.configure(text="RUNNING")
            return

        if ev.type == EventType.STOP:
            self.lbl_status.configure(text="STOPPED")
            return

        if ev.type == EventType.END:
            self.lbl_status.configure(text="ENDED")
            return

        if ev.type == EventType.SNAPSHOT:
            payload = ev.payload or {}
            items = payload.get("renglones") or []
            self._rebuild_table_from_snapshot(items)
            return

        if ev.type == EventType.UPDATE:
            payload = ev.payload or {}
            rid = payload.get("id_renglon")
            if not rid:
                return

            row = self.rows.get(rid)
            is_new = False
            if not row:
                row = UIRow(id_renglon=str(rid), desc=str(payload.get("desc") or ""))
                self.rows[str(rid)] = row
                self._insert_row(row)
                is_new = True

            if payload.get("id_cot") is not None:
                row.id_subasta = str(payload.get("id_cot"))
            if ev.subasta_id is not None:
                row.subasta_id = ev.subasta_id
            if ev.renglon_id is not None:
                row.renglon_pk = ev.renglon_id

            row.desc = str(payload.get("desc") or row.desc)

            row.mejor_txt = payload.get("mejor_oferta_txt")
            row.oferta_min_txt = payload.get("oferta_min_txt")
            row.precio_ref_subasta = payload.get("precio_referencia_subasta")
            msg = str(payload.get("mensaje") or "")
            changed = bool(payload.get("changed", False))
            if changed:
                ts = datetime.now().strftime("%H:%M:%S")
                row.obs_det = f"{msg} | cambio {ts}" if msg else f"Cambio detectado | {ts}"
            else:
                row.obs_det = msg or row.obs_det

            row.unidad_medida = payload.get("unidad_medida")
            row.cantidad = payload.get("cantidad")
            row.marca = payload.get("marca")
            row.observaciones = payload.get("observaciones")
            row.conversion_usd = payload.get("conversion_usd")
            row.costo_usd = payload.get("costo_usd")
            row.costo_final_pesos = payload.get("costo_final_pesos")
            row.renta = payload.get("renta")

            row.subtotal_para_mejorar = payload.get("subtotal_para_mejorar")
            row.subtotal_costo_pesos = payload.get("subtotal_costo_pesos")
            row.p_unit_minimo = payload.get("p_unit_minimo")
            row.subtotal = payload.get("subtotal")
            row.renta_ref = payload.get("renta_ref")
            row.p_unit_mejora = payload.get("p_unit_mejora")
            row.dif_unit = payload.get("dif_unit")
            row.renta_dpc = payload.get("renta_dpc")

            row.seguir = bool(payload.get("seguir", row.seguir))
            row.oferta_mia = bool(payload.get("oferta_mia", row.oferta_mia))

            style = payload.get("alert_style") or RowStyle.NORMAL.value
            sound = payload.get("sound") or SoundCue.NONE.value
            highlight = bool(payload.get("highlight", False))

            should_render = is_new or bool(payload.get("changed", False))
            if should_render:
                self._render_row(row, style=style)

            if sound != SoundCue.NONE.value and highlight:
                try:
                    self.bell()
                except Exception:
                    pass

    # -------------------------
    # Snapshot/table helpers
    # -------------------------
    def _clear_ui_data(self):
        """Limpia todos los datos de la UI (tabla y cache)."""
        self.tree.delete(*self.tree.get_children())
        self.rows.clear()
        self.iids.clear()

    def _rebuild_table_from_snapshot(self, items: list[dict]):
        self.tree.delete(*self.tree.get_children())
        self.rows.clear()
        self.iids.clear()

        for it in items:
            rid = str(it.get("value") or "")
            desc = str(it.get("text") or "")
            if not rid:
                continue
            row = UIRow(id_renglon=rid, desc=desc)
            self.rows[rid] = row
            self._insert_row(row)

    def _insert_row(self, row: UIRow):
        iid = self.tree.insert(
            "",
            "end",
            values=(row.id_subasta or "", row.id_renglon, self._truncate(row.desc, 80)) + ("",) * 19,
            tags=(RowStyle.NORMAL.value,),
        )
        self.iids[row.id_renglon] = iid

    def _render_row(self, row: UIRow, *, style: str):
        iid = self.iids.get(row.id_renglon)
        if not iid:
            return

        values = (
            row.id_subasta or "",
            row.id_renglon,
            self._truncate(row.desc, 80),
            row.unidad_medida or "",
            _fmt_num(row.cantidad, decimals=2),
            row.marca or "",
            self._truncate(row.observaciones or "", 40),
            _fmt_num(row.conversion_usd, decimals=2),
            _fmt_num(row.costo_usd, decimals=2),
            _fmt_money(row.costo_final_pesos),
            _fmt_money(row.subtotal_costo_pesos),
            _fmt_num(row.renta, decimals=4),
            _fmt_money(row.p_unit_minimo),
            _fmt_money(row.subtotal),
            _pct(row.renta_ref) if row.renta_ref is not None else "",
            _fmt_money(row.p_unit_mejora),
            _fmt_money(row.precio_ref_subasta),
            row.mejor_txt or "",
            _fmt_money(row.subtotal_para_mejorar),
            _fmt_money(row.dif_unit),
            _pct(row.renta_dpc) if row.renta_dpc is not None else "",
            self._truncate(row.obs_det or "", 60),
        )

        self.tree.item(iid, values=values, tags=(style,))

    @staticmethod
    def _truncate(s: str, n: int) -> str:
        s = (s or "").strip()
        return s if len(s) <= n else s[: n - 3] + "..."

    # -------------------------
    # Column visibility
    # -------------------------
    def _apply_saved_columns(self, default_cols: list[str] | None = None) -> None:
        raw = self.handles.runtime.get_ui_config(key="visible_columns")
        if not raw:
            if default_cols:
                self.tree.configure(displaycolumns=tuple(default_cols))
                self._save_visible_columns(default_cols)
            return
        try:
            cols = json.loads(raw)
        except Exception:
            return
        if cols:
            valid = [c for c in cols if c in self.cols]
            if valid:
                self.tree.configure(displaycolumns=tuple(valid))
                return
            # fallback to defaults if saved config is invalid
            if default_cols:
                self.tree.configure(displaycolumns=tuple(default_cols))
                self._save_visible_columns(default_cols)
            return

    def _save_visible_columns(self, cols: list[str]) -> None:
        self.handles.runtime.set_ui_config(key="visible_columns", value=json.dumps(cols))

    def on_columns(self):
        win = ctk.CTkToplevel(self)
        win.title("Columnas")
        win.geometry("520x420")

        body = ctk.CTkFrame(win)
        body.pack(fill="both", expand=True, padx=10, pady=10)

        left = ctk.CTkFrame(body)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        right = ctk.CTkFrame(body)
        right.pack(side="right", fill="both", expand=True, padx=(6, 0))

        ctk.CTkLabel(left, text="Visibles (orden)").pack(anchor="w")
        list_visible = tk.Listbox(left, selectmode="browse")
        list_visible.pack(fill="both", expand=True)

        ctk.CTkLabel(right, text="Ocultas").pack(anchor="w")
        list_hidden = tk.Listbox(right, selectmode="browse")
        list_hidden.pack(fill="both", expand=True)

        current = self.tree.cget("displaycolumns")
        if not current or current == ("#all",):
            current = self.cols
        current_list = list(current)
        hidden_list = [c for c in self.cols if c not in current_list]

        for c in current_list:
            list_visible.insert("end", self.col_labels.get(c, c))
        for c in hidden_list:
            list_hidden.insert("end", self.col_labels.get(c, c))

        def _label_to_col(label: str) -> str:
            for k, v in self.col_labels.items():
                if v == label:
                    return k
            return label

        def _move_selected(src: tk.Listbox, dst: tk.Listbox):
            sel = src.curselection()
            if not sel:
                return
            idx = sel[0]
            label = src.get(idx)
            src.delete(idx)
            dst.insert("end", label)

        def _move_up():
            sel = list_visible.curselection()
            if not sel:
                return
            idx = sel[0]
            if idx <= 0:
                return
            label = list_visible.get(idx)
            list_visible.delete(idx)
            list_visible.insert(idx - 1, label)
            list_visible.selection_set(idx - 1)

        def _move_down():
            sel = list_visible.curselection()
            if not sel:
                return
            idx = sel[0]
            if idx >= list_visible.size() - 1:
                return
            label = list_visible.get(idx)
            list_visible.delete(idx)
            list_visible.insert(idx + 1, label)
            list_visible.selection_set(idx + 1)

        btns = ctk.CTkFrame(win)
        btns.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkButton(btns, text="Agregar", command=lambda: _move_selected(list_hidden, list_visible)).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Quitar", command=lambda: _move_selected(list_visible, list_hidden)).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Subir", command=_move_up).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="Bajar", command=_move_down).pack(side="left", padx=6)

        def _apply():
            labels = list(list_visible.get(0, "end"))
            if not labels:
                messagebox.showwarning("Atención", "Debe quedar al menos una columna visible.")
                return
            cols = [_label_to_col(l) for l in labels]
            self.tree.configure(displaycolumns=tuple(cols))
            self._save_visible_columns(cols)
            win.destroy()

        ctk.CTkButton(btns, text="Aplicar", command=_apply).pack(side="right", padx=6)
        ctk.CTkButton(btns, text="Cerrar", command=win.destroy).pack(side="right", padx=6)

    # -------------------------
    # Sorting
    # -------------------------
    def _sort_by(self, col: str, *, numeric: bool) -> None:
        data = []
        for iid in self.tree.get_children(""):
            value = self.tree.set(iid, col)
            data.append((value, iid))

        reverse = self._sort_state.get(col, False)
        self._sort_state[col] = not reverse

        def _key(item):
            val = item[0]
            if numeric:
                try:
                    return float(val)
                except Exception:
                    return 0.0
            return str(val).lower()

        data.sort(key=_key, reverse=reverse)
        for idx, (_, iid) in enumerate(data):
            self.tree.move(iid, "", idx)

    # -------------------------
    # Selection
    # -------------------------
    def _selected_row(self) -> Optional[UIRow]:
        sel = self.tree.selection()
        if not sel:
            return None
        iid = sel[0]
        rid = self.tree.item(iid, "values")[1]
        return self.rows.get(rid)

    # -------------------------
    # User actions
    # -------------------------
    def _parse_float(self, raw: str) -> float | None:
        if raw is None:
            return None
        s = str(raw).strip()
        if not s:
            return None
        s = s.replace(" ", "").replace("\u00a0", "")
        try:
            if "," in s and "." in s:
                # Usa el separador que aparece al final como decimal.
                if s.rfind(",") > s.rfind("."):
                    s = s.replace(".", "").replace(",", ".")
                else:
                    s = s.replace(",", "")
            elif "," in s:
                parts = s.split(",")
                if len(parts) > 2 and all(len(p) == 3 for p in parts[1:]):
                    # 1,234,567 -> 1234567
                    s = "".join(parts)
                elif len(parts) > 1:
                    # 1,23 / 1,234,56 -> 1.23 / 1234.56
                    s = "".join(parts[:-1]) + "." + parts[-1]
            elif "." in s:
                parts = s.split(".")
                if len(parts) > 2 and all(len(p) == 3 for p in parts[1:]):
                    # 1.234.567 -> 1234567
                    s = "".join(parts)
                elif len(parts) > 1:
                    # 1.23 / 1.234.56 -> 1.23 / 1234.56
                    s = "".join(parts[:-1]) + "." + parts[-1]

            return float(s)
        except Exception:
            return None

    def _parse_decimal(self, raw: str) -> float | None:
        return self._parse_float(raw)

    def on_capture_current(self):
        self.collector_cmd_q.put({"cmd": "capture_current"})
        self._log("CMD: capture_current enviado al collector (si es Playwright, capturará).")

    def on_stop(self):
        self.handles.runtime.stop()

    def on_start_browser(self):
        if self.handles.mode != "PLAYWRIGHT":
            self._log("Modo actual no es PLAYWRIGHT.")
            return
        try:
            self.handles.runtime.start_collector()
            self._log("Collector Playwright iniciado por usuario.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir navegador: {e}")

    def on_cleanup(self):
        choice = messagebox.askyesnocancel(
            "Liberar espacio",
            "Sí = solo logs\nTodo = logs + subastas + costos\nCancelar = no hacer nada",
        )
        if choice is None:
            return
        if choice is True:
            try:
                self.handles.runtime.cleanup_data(mode="logs")
                self._log("Logs limpiados.")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudieron limpiar logs: {e}")
            return

        # Limpiar estados (logs + subastas + costos)
        try:
            self.handles.runtime.cleanup_data(mode="states")
            self._clear_ui_data()  # Limpiar la UI también
            self._log("Logs, subastas y costos limpiados.")
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
                self._log("Reset total realizado.")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo hacer reset total: {e}")

    def on_export_excel(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            title="Exportar Excel",
        )
        if not path:
            return
        try:
            self.handles.runtime.export_excel(out_path=path)
            self._log(f"Excel exportado: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar Excel: {e}")

    def on_import_excel(self):
        path = filedialog.askopenfilename(
            filetypes=[("Excel", "*.xlsx")],
            title="Importar Excel",
        )
        if not path:
            return
        try:
            updated = self.handles.runtime.import_excel(file_path=path)
            self._log(f"Excel importado: {updated} filas actualizadas")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo importar Excel: {e}")

    def on_edit_row(self):
        row = self._selected_row()
        if not row:
            messagebox.showwarning("Atención", "Seleccioná un renglón.")
            return
        if row.renglon_pk is None:
            messagebox.showwarning("Atención", "El renglón todavía no está listo.")
            return

        win = ctk.CTkToplevel(self)
        win.title(f"Editar renglón {row.id_renglon}")
        win.geometry("520x520")

        canvas = tk.Canvas(win, highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        scroll = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        scroll.pack(side="right", fill="y")
        canvas.configure(yscrollcommand=scroll.set)

        frame = ctk.CTkFrame(canvas)
        frame_id = canvas.create_window((0, 0), window=frame, anchor="nw")

        def _on_frame_config(_ev=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(frame_id, width=canvas.winfo_width())

        frame.bind("<Configure>", _on_frame_config)

        entries: dict[str, tk.Widget] = {}
        cfg = self.handles.runtime.get_renglon_config(renglon_id=row.renglon_pk) or {}
        row_utilidad_min = cfg.get("utilidad_min_pct", "")

        def _add_entry(label: str, key: str, value: str | None = None):
            ctk.CTkLabel(frame, text=label).pack(anchor="w")
            ent = ctk.CTkEntry(frame)
            ent.pack(fill="x", pady=(0, 6))
            if value is not None:
                ent.insert(0, str(value))
            entries[key] = ent

        _add_entry("Unidad de medida", "unidad_medida", row.unidad_medida)
        qty_txt = "" if row.cantidad is None else str(row.cantidad)
        ctk.CTkLabel(frame, text=f"Cantidad (subasta): {qty_txt}").pack(anchor="w")

        _add_entry("Marca", "marca", row.marca)

        ctk.CTkLabel(frame, text="Observaciones").pack(anchor="w")
        txt_obs = tk.Text(frame, height=4)
        txt_obs.pack(fill="x", pady=(0, 6))
        if row.observaciones:
            txt_obs.insert("1.0", row.observaciones)
        entries["observaciones"] = txt_obs

        _add_entry("Conversión USD", "conversion_usd", row.conversion_usd)
        _add_entry("Costo final pesos", "costo_final_pesos", row.costo_final_pesos)
        _add_entry("Renta", "renta", row.renta)

        _add_entry("Utilidad min %", "utilidad_min_pct", row_utilidad_min)

        btns = ctk.CTkFrame(win)
        btns.pack(fill="x", padx=10, pady=(0, 10))

        def _save():
            unidad_medida = entries["unidad_medida"].get().strip() or None
            marca = entries["marca"].get().strip() or None
            observaciones = entries["observaciones"].get("1.0", "end").strip() or None
            conversion_usd = self._parse_float(entries["conversion_usd"].get())
            costo_final_pesos = self._parse_float(entries["costo_final_pesos"].get())
            renta = self._parse_float(entries["renta"].get())

            utilidad_min_pct = self._parse_float(entries["utilidad_min_pct"].get())

            if costo_final_pesos is None or costo_final_pesos <= 0:
                messagebox.showwarning("Atención", "COSTO FINAL PESOS debe ser > 0.")
                return
            if renta is not None and renta < 0:
                messagebox.showwarning("Atención", "RENTA no puede ser negativa.")
                return

            if utilidad_min_pct is not None:
                self.handles.runtime.update_renglon_config(
                    renglon_id=row.renglon_pk,
                    utilidad_min_pct=utilidad_min_pct,
                )
            self.handles.runtime.update_renglon_excel(
                renglon_id=row.renglon_pk,
                unidad_medida=unidad_medida,
                marca=marca,
                observaciones=observaciones,
                conversion_usd=conversion_usd,
                costo_final_pesos=costo_final_pesos,
                renta=renta,
            )

            row.unidad_medida = unidad_medida
            row.marca = marca
            row.observaciones = observaciones
            row.conversion_usd = conversion_usd
            row.costo_final_pesos = costo_final_pesos
            row.renta = renta
            if conversion_usd not in (None, 0) and costo_final_pesos is not None:
                row.costo_usd = costo_final_pesos / conversion_usd
            else:
                row.costo_usd = None

            if row.cantidad is not None and costo_final_pesos is not None:
                row.subtotal_costo_pesos = row.cantidad * costo_final_pesos
            else:
                row.subtotal_costo_pesos = None

            if renta is not None and costo_final_pesos is not None:
                row.p_unit_minimo = renta * costo_final_pesos
            else:
                row.p_unit_minimo = None

            if row.cantidad is not None and row.p_unit_minimo is not None:
                row.subtotal = row.cantidad * row.p_unit_minimo
            else:
                row.subtotal = None

            if row.precio_ref_subasta is not None and costo_final_pesos not in (None, 0):
                row.renta_ref = (row.precio_ref_subasta / costo_final_pesos) - 1.0
            else:
                row.renta_ref = None

            if row.subtotal_para_mejorar is not None and row.cantidad not in (None, 0):
                row.p_unit_mejora = row.subtotal_para_mejorar / row.cantidad
            else:
                row.p_unit_mejora = None

            if row.p_unit_mejora is not None and costo_final_pesos is not None:
                row.dif_unit = row.p_unit_mejora - costo_final_pesos
            else:
                row.dif_unit = None

            if row.p_unit_mejora is not None and costo_final_pesos not in (None, 0):
                row.renta_dpc = (row.p_unit_mejora / costo_final_pesos) - 1.0
            else:
                row.renta_dpc = None

            self._render_row(row, style=RowStyle.TRACKED.value if row.seguir else RowStyle.NORMAL.value)
            self._log(f"Fila actualizada: {row.id_renglon}")
            win.destroy()

        ctk.CTkButton(btns, text="Guardar", command=_save).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="Cancelar", command=win.destroy).pack(side="right", padx=6)

    # -------------------------
    # Logging
    # -------------------------
    def _log(self, msg: str):
        # Filtrar spam: solo resumen o eventos relevantes
        if "EventLevel.DEBUG" in msg:
            return
        if "EventType.HEARTBEAT" in msg and "Resumen" not in msg and "SNAPSHOT" not in msg:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        self.txt_log.insert("end", f"[{ts}] {msg}\n")
        self.txt_log.see("end")
