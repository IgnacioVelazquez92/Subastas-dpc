# app/core/security.py
"""
Políticas de seguridad operativa (SecurityPolicy).

Objetivo:
- Evitar bloqueos por parte del portal.
- Detectar situaciones anómalas automáticamente.
- Cortar, pausar o degradar el monitoreo sin intervención humana.

Este módulo NO hace requests ni UI.
Solo decide acciones en base a métricas observadas.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional
from datetime import datetime, timedelta


class SecurityAction(str, Enum):
    """
    Acciones posibles sugeridas por la política de seguridad.
    """
    NONE = "NONE"              # seguir normal
    BACKOFF = "BACKOFF"        # aumentar intervalo
    PAUSE = "PAUSE"            # pausar subasta
    STOP = "STOP"              # detener subasta definitivamente
    ALERT = "ALERT"            # solo alertar al usuario


@dataclass(frozen=True)
class SecurityDecision:
    """
    Resultado de evaluar la política de seguridad.
    """
    action: SecurityAction = SecurityAction.NONE
    message: str = ""
    new_poll_seconds: Optional[float] = None


class SecurityPolicy:
    """
    Política de seguridad configurable.

    Cubre:
    - rachas de errores HTTP
    - tiempo prolongado sin respuestas válidas
    - subasta finalizada
    """

    def __init__(
        self,
        *,
        max_error_streak: int = 10,
        max_minutes_without_ok: int = 5,
        backoff_multiplier: float = 2.0,
        max_poll_seconds: float = 30.0,
        backoff_on_http0_timeout: bool = False,
        min_error_streak_for_backoff: int = 2,
    ):
        """
        Parámetros:
        - max_error_streak: cuántos errores consecutivos tolerar
        - max_minutes_without_ok: tiempo máximo sin un OK válido
        - backoff_multiplier: factor para aumentar poll_seconds
        - max_poll_seconds: tope del backoff
        - backoff_on_http0_timeout: si False, HTTP=0 timeout solo alerta (sin subir poll)
        - min_error_streak_for_backoff: errores consecutivos mínimos para aplicar backoff
        """
        self.max_error_streak = max_error_streak
        self.max_minutes_without_ok = max_minutes_without_ok
        self.backoff_multiplier = backoff_multiplier
        self.max_poll_seconds = max_poll_seconds
        self.backoff_on_http0_timeout = bool(backoff_on_http0_timeout)
        self.min_error_streak_for_backoff = max(1, int(min_error_streak_for_backoff))

    # -------------------------------------------------
    # Evaluación principal
    # -------------------------------------------------
    def evaluate(
        self,
        *,
        current_poll_seconds: float,
        err_streak: int,
        last_ok_at: Optional[str],
        http_status: int,
        mensaje: str = "",
    ) -> SecurityDecision:
        """
        Evalúa el estado actual y decide una acción.

        last_ok_at: timestamp ISO (UTC o local consistente)
        """

        # 1) Subasta finalizada explícitamente
        if "finalizada" in (mensaje or "").lower():
            return SecurityDecision(
                action=SecurityAction.STOP,
                message="Subasta finalizada detectada",
            )

        # 2) Error HTTP actual
        if http_status != 200:
            msg = (mensaje or "").lower()
            # HTTP=0 timeout/abort suele ser transitorio del browser/red.
            # En este caso evitamos backoff para no degradar la latencia global.
            is_http0_timeout = http_status == 0 and ("timeout" in msg or "abort" in msg)
            if is_http0_timeout and not self.backoff_on_http0_timeout:
                return SecurityDecision(
                    action=SecurityAction.ALERT,
                    message="HTTP 0 timeout transitorio (sin backoff)",
                )

            # Si la racha es demasiado larga, detener
            if err_streak >= self.max_error_streak:
                return SecurityDecision(
                    action=SecurityAction.STOP,
                    message=f"Demasiados errores HTTP consecutivos ({err_streak})",
                )

            # Evitar degradar por errores aislados.
            if err_streak < self.min_error_streak_for_backoff:
                return SecurityDecision(
                    action=SecurityAction.ALERT,
                    message=(
                        f"HTTP {http_status} transitorio "
                        f"(streak {err_streak}/{self.min_error_streak_for_backoff})"
                    ),
                )

            # Si todavía estamos dentro del margen, aplicar backoff
            new_poll = min(
                current_poll_seconds * self.backoff_multiplier,
                self.max_poll_seconds,
            )

            return SecurityDecision(
                action=SecurityAction.BACKOFF,
                message=f"HTTP {http_status} - aplicando backoff",
                new_poll_seconds=new_poll,
            )

        # 3) No hubo error HTTP, pero puede haber inactividad prolongada
        if last_ok_at:
            try:
                last_ok_dt = datetime.fromisoformat(last_ok_at)
                delta = datetime.now() - last_ok_dt
                if delta > timedelta(minutes=self.max_minutes_without_ok):
                    return SecurityDecision(
                        action=SecurityAction.PAUSE,
                        message=f"Sin datos válidos hace {int(delta.total_seconds() / 60)} minutos",
                    )
            except ValueError:
                # timestamp mal formado -> alertar pero no cortar
                return SecurityDecision(
                    action=SecurityAction.ALERT,
                    message="Timestamp last_ok_at inválido",
                )

        # 4) Todo normal
        return SecurityDecision(
            action=SecurityAction.NONE,
            message="Estado normal",
        )
