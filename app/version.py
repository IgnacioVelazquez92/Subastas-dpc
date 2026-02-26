# app/version.py
"""
Versión de la aplicación y URLs para el sistema de actualización automática.

Para publicar una nueva versión:
  1. Subir el nuevo .exe a GitHub Releases con el nombre definido en EXE_NAME.
  2. Actualizar version.txt en el repositorio con el nuevo número de versión.
  3. El sistema de actualización compara esta constante con la versión remota.
"""

from __future__ import annotations

# ─── Versión actual de la app ────────────────────────────────────────────────
VERSION_ACTUAL = "1.0.0"

# ─── Configuración del repositorio GitHub ────────────────────────────────────
# Usuario y repositorio donde se alojan los releases y version.txt
GITHUB_USER = "TU_USUARIO_GITHUB"        # <-- Reemplazar con tu usuario
GITHUB_REPO = "monitor_subastas"         # <-- Reemplazar con el nombre del repo

# URL raw de version.txt (se consulta para verificar si hay nueva versión)
VERSION_TXT_URL = (
    f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/version.txt"
)

# Nombre del ejecutable en GitHub Releases (debe coincidir con el archivo subido)
EXE_NAME = "MonitorSubastas.exe"

# URL del .exe en GitHub Releases (se descarga cuando hay actualización disponible)
RELEASE_EXE_URL = (
    f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases/latest/download/{EXE_NAME}"
)
