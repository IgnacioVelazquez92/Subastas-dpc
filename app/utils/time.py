# app/utils/time.py
"""
Utilidades de tiempo.

Objetivo:
- Proveer timestamps consistentes para:
  - SQLite (TEXT en ISO)
  - logs
  - métricas de seguridad (last_ok_at, etc.)

Decisión práctica:
- Usamos hora local (Argentina) en ISO sin microsegundos.
- Si más adelante necesitás UTC, se cambia en un solo lugar.
"""

from __future__ import annotations

from datetime import datetime


def now_iso() -> str:
    """
    Timestamp ISO local (sin microsegundos).
    Ej: "2026-02-04T21:18:00"
    """
    return datetime.now().replace(microsecond=0).isoformat()


def now_hhmmss() -> str:
    """
    Hora para logs.
    Ej: "21:18:00"
    """
    return datetime.now().strftime("%H:%M:%S")
