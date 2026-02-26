# app/ui/views/info_view.py
"""
Ventana de información de la aplicación y sistema de actualización.

Responsabilidades:
  - InfoWindow: ventana modal "Acerca de" con datos de la app.
  - verificar_y_actualizar(): descarga y aplica actualizaciones desde GitHub Releases.

Flujo de actualización:
  1. Consulta version.txt en GitHub raw.
  2. Compara con VERSION_ACTUAL usando packaging.version.
  3. Si hay versión nueva: descarga el .exe con nombre temporal.
  4. Genera updater.bat que reemplaza el ejecutable y relanza la app.
  5. Lanza el .bat y cierre la app actual.
"""

from __future__ import annotations

import os
import sys
import subprocess
import threading
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from typing import Callable, Optional

try:
    import requests
    _requests_ok = True
except ImportError:
    _requests_ok = False

try:
    from packaging.version import Version as PkgVersion
    _packaging_ok = True
except ImportError:
    _packaging_ok = False

from app.version import VERSION_ACTUAL, VERSION_TXT_URL, RELEASE_EXE_URL, EXE_NAME


# ─── Helpers de versión ───────────────────────────────────────────────────────

def _version_mayor(remota: str, local: str) -> bool:
    """Retorna True si la versión remota es mayor a la local."""
    if _packaging_ok:
        return PkgVersion(remota.strip()) > PkgVersion(local.strip())
    # Fallback: comparación de tuplas "X.Y.Z"
    def _parse(v: str):
        return tuple(int(x) for x in v.strip().split("."))
    try:
        return _parse(remota) > _parse(local)
    except ValueError:
        return False


# ─── Updater core ─────────────────────────────────────────────────────────────

def verificar_y_actualizar(
    parent: tk.Misc,
    on_progress: Optional[Callable[[str], None]] = None,
) -> None:
    """
    Verifica si hay una versión nueva en GitHub y la aplica si el usuario confirma.

    Parámetros:
        parent      — ventana padre para los diálogos modales.
        on_progress — callback opcional para reportar texto de progreso.
    """
    def _log(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    # ── Guardia: requests disponible ─────────────────────────────────────────
    if not _requests_ok:
        messagebox.showerror(
            "Falta dependencia",
            "El paquete 'requests' no está instalado.\n"
            "Ejecuta: pip install requests",
            parent=parent,
        )
        return

    # ── Fase 1: Verificación ─────────────────────────────────────────────────
    _log("Consultando versión remota...")
    try:
        resp = requests.get(VERSION_TXT_URL, timeout=10)
        resp.raise_for_status()
        version_remota = resp.text.strip()
    except requests.exceptions.ConnectionError:
        messagebox.showerror(
            "Sin conexión",
            "No se pudo conectar con GitHub.\nVerificá tu conexión a internet.",
            parent=parent,
        )
        return
    except requests.exceptions.HTTPError as e:
        messagebox.showerror(
            "Error HTTP",
            f"Error al consultar la versión remota:\n{e}",
            parent=parent,
        )
        return
    except Exception as e:
        messagebox.showerror(
            "Error inesperado",
            f"No se pudo verificar la versión:\n{e}",
            parent=parent,
        )
        return

    _log(f"Versión remota: {version_remota} | Local: {VERSION_ACTUAL}")

    if not _version_mayor(version_remota, VERSION_ACTUAL):
        messagebox.showinfo(
            "Sin actualizaciones",
            f"Ya tenés la versión más reciente ({VERSION_ACTUAL}).",
            parent=parent,
        )
        return

    # ── Confirmar descarga ───────────────────────────────────────────────────
    ok = messagebox.askyesno(
        "Actualización disponible",
        f"Versión disponible: {version_remota}\n"
        f"Versión actual:     {VERSION_ACTUAL}\n\n"
        "¿Querés descargar e instalar la actualización?\n"
        "(La app se cerrará y se relanzará automáticamente.)",
        parent=parent,
    )
    if not ok:
        return

    # ── Fase 2: Descarga segura ───────────────────────────────────────────────
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    temp_path = os.path.join(app_dir, "update_temp.exe")
    bat_path  = os.path.join(app_dir, "updater.bat")

    _log(f"Descargando desde: {RELEASE_EXE_URL}")
    try:
        with requests.get(RELEASE_EXE_URL, stream=True, timeout=60) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            descargado = 0
            with open(temp_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        descargado += len(chunk)
                        if total:
                            pct = int(descargado * 100 / total)
                            _log(f"Descargando... {pct}%  ({descargado // 1024} KB)")
    except Exception as e:
        # Limpiar archivo temporal incompleto
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        messagebox.showerror(
            "Error de descarga",
            f"No se pudo descargar la actualización:\n{e}",
            parent=parent,
        )
        return

    _log("Descarga completa. Preparando actualización...")

    # ── Fase 3: Generar updater.bat ───────────────────────────────────────────
    exe_actual = os.path.abspath(sys.argv[0])
    exe_nombre = os.path.basename(exe_actual)

    bat_content = (
        "@echo off\n"
        "rem updater.bat — generado automáticamente por Monitor de Subastas\n"
        "timeout /t 2 /nobreak > nul\n"
        f'del /f /q "{exe_actual}"\n'
        f'rename "{temp_path}" "{exe_nombre}"\n'
        f'start "" "{exe_actual}"\n'
        "del %0\n"
    )

    try:
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)
    except Exception as e:
        messagebox.showerror(
            "Error al crear updater",
            f"No se pudo crear el script de actualización:\n{e}",
            parent=parent,
        )
        return

    # ── Fase 4: Lanzar .bat y cerrar ─────────────────────────────────────────
    _log("Lanzando updater.bat — la app se cerrará en instantes...")

    try:
        subprocess.Popen(
            bat_path,
            shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
    except Exception as e:
        messagebox.showerror(
            "Error al lanzar updater",
            f"No se pudo iniciar el proceso de reemplazo:\n{e}",
            parent=parent,
        )
        return

    sys.exit(0)


# ─── Ventana Info ─────────────────────────────────────────────────────────────

class InfoWindow(ctk.CTkToplevel):
    """
    Ventana modal 'Acerca de' con:
      - Versión y descripción de la app.
      - Botón 'Buscar actualizaciones' que corre verificar_y_actualizar().
    """

    def __init__(self, parent: tk.Misc):
        super().__init__(parent)

        self.title("Información de la aplicación")
        self.geometry("520x480")
        self.resizable(False, False)
        self.grab_set()  # Modal

        # Centrar sobre el padre
        self.after(50, self._center_on_parent)

        self._parent = parent
        self._update_thread: Optional[threading.Thread] = None

        self._build()

    # ── Construcción de la UI ─────────────────────────────────────────────────

    def _build(self) -> None:
        pad = {"padx": 24, "pady": 8}

        # ── Encabezado ───────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=("#1f538d", "#1a3f6a"), corner_radius=0)
        header.pack(fill="x")

        ctk.CTkLabel(
            header,
            text="Monitor de Subastas Electrónicas",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="white",
        ).pack(pady=(16, 4))

        ctk.CTkLabel(
            header,
            text=f"Versión {VERSION_ACTUAL}",
            font=ctk.CTkFont(size=13),
            text_color="#a8d4f5",
        ).pack(pady=(0, 16))

        # ── Cuerpo ───────────────────────────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, **pad)

        info_items = [
            ("Plataforma",  "Subastas e-Commerce — Gobierno de Córdoba"),
            ("Framework UI", "CustomTkinter + Tkinter"),
            ("Scraping",    "Playwright (Chromium)"),
            ("Base de datos", "SQLite"),
            ("Python",      f"{sys.version.split()[0]}"),
        ]

        for label, valor in info_items:
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(
                row,
                text=f"{label}:",
                font=ctk.CTkFont(size=11, weight="bold"),
                width=130,
                anchor="w",
            ).pack(side="left")
            ctk.CTkLabel(
                row,
                text=valor,
                font=ctk.CTkFont(size=11),
                text_color="#888888",
                anchor="w",
            ).pack(side="left")

        # Separador
        ctk.CTkFrame(body, height=1, fg_color="#333333").pack(fill="x", pady=12)

        # Descripción
        ctk.CTkLabel(
            body,
            text=(
                "Monitorea en tiempo real los precios líder de subastas públicas,\n"
                "aplica alertas visuales/sonoras y persiste el historial."
            ),
            font=ctk.CTkFont(size=11),
            text_color="#aaaaaa",
            justify="left",
            anchor="w",
        ).pack(fill="x")

        # ── Log de progreso de actualización ─────────────────────────────────
        ctk.CTkFrame(body, height=1, fg_color="#333333").pack(fill="x", pady=12)

        ctk.CTkLabel(
            body,
            text="Actualización:",
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w",
        ).pack(fill="x")

        self._lbl_progress = ctk.CTkLabel(
            body,
            text="Presioná el botón para buscar actualizaciones.",
            font=ctk.CTkFont(size=10),
            text_color="#888888",
            anchor="w",
        )
        self._lbl_progress.pack(fill="x", pady=(4, 0))

        # ── Botones inferiores ────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=(0, 20))

        self._btn_update = ctk.CTkButton(
            btn_frame,
            text="🔄  Buscar actualizaciones",
            command=self._on_update_click,
            fg_color="#1f538d",
            hover_color="#174070",
            width=200,
        )
        self._btn_update.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_frame,
            text="Cerrar",
            command=self.destroy,
            fg_color="#444444",
            hover_color="#333333",
            width=100,
        ).pack(side="right")

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _on_update_click(self) -> None:
        """Ejecuta la verificación en un thread para no bloquear la UI."""
        self._btn_update.configure(state="disabled", text="Verificando...")
        self._set_progress("Iniciando verificación...")

        self._update_thread = threading.Thread(
            target=self._run_update,
            daemon=True,
        )
        self._update_thread.start()

    def _run_update(self) -> None:
        """Corre en thread secundario. Al finalizar reactiva el botón."""
        try:
            verificar_y_actualizar(
                parent=self,
                on_progress=lambda msg: self.after(0, lambda m=msg: self._set_progress(m)),
            )
        finally:
            # Reactivar botón (solo si la ventana sigue abierta)
            self.after(0, self._restore_btn)

    def _restore_btn(self) -> None:
        try:
            self._btn_update.configure(state="normal", text="🔄  Buscar actualizaciones")
        except Exception:
            pass

    def _set_progress(self, msg: str) -> None:
        try:
            self._lbl_progress.configure(text=msg)
        except Exception:
            pass

    # ── Posicionamiento ──────────────────────────────────────────────────────

    def _center_on_parent(self) -> None:
        try:
            parent = self._parent
            px = parent.winfo_x()
            py = parent.winfo_y()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            w = self.winfo_reqwidth() or 520
            h = self.winfo_reqheight() or 480
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass
