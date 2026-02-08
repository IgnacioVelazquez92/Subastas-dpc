# app/collector/base.py
"""
Interfaz base para Collectors.

Objetivo:
- Definir un contrato común para cualquier fuente de datos:
  - MockCollector (simulador)
  - PlaywrightCollector (real)
- Desacoplar completamente la UI y el Core de la implementación concreta.

Reglas:
- Un Collector:
  - se inicia con start()
  - se detiene con stop()
  - emite eventos normalizados (Event) hacia una cola de salida
- NO conoce la UI
- NO escribe directamente en la base de datos
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from queue import Queue

from app.core.events import Event


class BaseCollector(ABC):
    """
    Clase base abstracta para collectors.

    Implementaciones concretas:
    - MockCollector: usa Simulator
    - PlaywrightCollector: usa Playwright + portal real
    """

    def __init__(self, *, out_q: Queue):
        """
        out_q: cola de salida donde el collector emite Event
        """
        self.out_q = out_q
        self._running: bool = False

    # -------------------------
    # Ciclo de vida
    # -------------------------
    @abstractmethod
    def start(self) -> None:
        """
        Inicia el collector.
        Debe ser no bloqueante (thread / asyncio / task).
        """
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        """
        Solicita la detención del collector.
        Debe ser idempotente.
        """
        raise NotImplementedError

    # -------------------------
    # Utilidades comunes
    # -------------------------
    def set_poll_seconds(self, seconds: float) -> None:
        """
        Actualiza el intervalo de polling si el collector lo soporta.
        Implementaciones reales pueden sobreescribirlo.
        """
        _ = seconds

    def emit(self, event: Event) -> None:
        """
        Envía un evento al sistema.
        """
        self.out_q.put(event)

    @property
    def running(self) -> bool:
        return self._running
