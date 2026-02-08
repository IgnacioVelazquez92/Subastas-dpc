# app/utils/money.py
"""
Parseo/format de montos estilo portal.

El portal devuelve strings como:
- "$ 20.115.680,0000"
- "$ 3.673.540,0000"
- "" o "null"

Necesitamos:
- convertir a float de forma segura (para cálculos y SQLite)
- mantener el string original para UI (tal cual viene)
"""

from __future__ import annotations

import re
from typing import Optional


_MONEY_RE = re.compile(r"[^\d,.-]+")


def money_to_float(txt: str | None) -> Optional[float]:
    """
    Convierte texto monetario (AR) a float.
    Ej:
      "$ 20.115.680,0000" -> 20115680.0
      "20.015.101,6000"   -> 20015101.6

    Retorna None si no se puede parsear.
    """
    if not txt:
        return None

    s = str(txt).strip()
    if not s or s.lower() == "null":
        return None

    # quitar $ y cualquier texto no numérico
    s = _MONEY_RE.sub("", s)

    # miles con ".", decimales con ","
    # Pasamos a formato python:
    # 20.115.680,0000 -> 20115680.0000
    s = s.replace(".", "").replace(",", ".")

    try:
        return float(s)
    except ValueError:
        return None


def float_to_money_txt(value: float, decimals: int = 4) -> str:
    """
    Formato simple estilo portal.
    No buscamos que sea idéntico al portal; es para mostrar.
    """
    s = f"{value:,.{decimals}f}"
    # python: 20,115,680.0000 -> AR: 20.115.680,0000
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"$ {s}"
