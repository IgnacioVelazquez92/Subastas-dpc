# app/core/events.py
"""
Definición de eventos del sistema (contrato entre Collector / Core / UI).

Objetivo:
- Estandarizar qué mensajes circulan internamente.
- Evitar diccionarios “sueltos” con claves ambiguas.
- Facilitar logging, observabilidad y testeo (mock / simulator).

Regla:
- Un evento es SOLO datos + metadata.
- La lógica se aplica en capas superiores (AlertEngine, UI, Security).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any


# =========================================================
# Niveles y tipos de evento
# =========================================================

class EventLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class EventType(str, Enum):
    # Operativos
    HEARTBEAT = "HEARTBEAT"
    UPDATE = "UPDATE"              # actualización de un renglón
    SNAPSHOT = "SNAPSHOT"          # estado completo (ej. al capturar subasta)

    # Alertas / negocio
    ALERT = "ALERT"
    SECURITY = "SECURITY"

    # Sistema
    HTTP_ERROR = "HTTP_ERROR"
    EXCEPTION = "EXCEPTION"
    START = "START"
    STOP = "STOP"
    END = "END"                    # subasta finalizada


# =========================================================
# Evento base
# =========================================================

@dataclass(frozen=True)
class Event:
    """
    Evento base del sistema.

    Campos comunes:
    - level: severidad
    - type: tipo semántico
    - message: texto humano (logs / UI)
    - subasta_id: FK interna (opcional)
    - renglon_id: FK interna (opcional)
    - payload: datos estructurados adicionales (dict u objeto)
    """
    level: EventLevel
    type: EventType
    message: str

    subasta_id: Optional[int] = None
    renglon_id: Optional[int] = None
    payload: Optional[Any] = None


# =========================================================
# Helpers de fábrica (conveniencia)
# =========================================================

def info(
    type: EventType,
    message: str,
    *,
    subasta_id: Optional[int] = None,
    renglon_id: Optional[int] = None,
    payload: Optional[Any] = None,
) -> Event:
    return Event(
        level=EventLevel.INFO,
        type=type,
        message=message,
        subasta_id=subasta_id,
        renglon_id=renglon_id,
        payload=payload,
    )


def warn(
    type: EventType,
    message: str,
    *,
    subasta_id: Optional[int] = None,
    renglon_id: Optional[int] = None,
    payload: Optional[Any] = None,
) -> Event:
    return Event(
        level=EventLevel.WARN,
        type=type,
        message=message,
        subasta_id=subasta_id,
        renglon_id=renglon_id,
        payload=payload,
    )


def error(
    type: EventType,
    message: str,
    *,
    subasta_id: Optional[int] = None,
    renglon_id: Optional[int] = None,
    payload: Optional[Any] = None,
) -> Event:
    return Event(
        level=EventLevel.ERROR,
        type=type,
        message=message,
        subasta_id=subasta_id,
        renglon_id=renglon_id,
        payload=payload,
    )


def debug(
    type: EventType,
    message: str,
    *,
    subasta_id: Optional[int] = None,
    renglon_id: Optional[int] = None,
    payload: Optional[Any] = None,
) -> Event:
    return Event(
        level=EventLevel.DEBUG,
        type=type,
        message=message,
        subasta_id=subasta_id,
        renglon_id=renglon_id,
        payload=payload,
    )
