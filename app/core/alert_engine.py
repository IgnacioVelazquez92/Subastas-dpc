# app/core/alert_engine.py
"""
Motor de alertas (AlertEngine).

Objetivo:
- Tomar un estado consolidado (estado del portal + config del usuario)
- Decidir si corresponde:
  - emitir una alerta (visual/sonora)
  - marcar estilos (rojo/verde/amarillo)
  - ocultar renglones por umbral (UX)
- Mantener la lógica FUERA de la UI.

Este motor no "reproduce sonidos" ni "colorea widgets".
Devuelve decisiones (acciones) que la UI aplica.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RowStyle(str, Enum):
    """Estilos lógicos para UI (la UI decide el color final)."""
    NORMAL = "NORMAL"
    TRACKED = "TRACKED"      # en seguimiento
    WARNING = "WARNING"      # alerta amarilla
    DANGER = "DANGER"        # alerta roja
    SUCCESS = "SUCCESS"      # oferta mía / situación positiva


class SoundCue(str, Enum):
    """Identificadores lógicos de sonido."""
    NONE = "NONE"
    ALERT = "ALERT"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


@dataclass(frozen=True)
class AlertDecision:
    """
    Decisión resultante para un renglón en un tick.

    - style: estilo lógico (para UI)
    - play_sound: qué sonido reproducir (si corresponde)
    - highlight: si aplicar highlight temporal
    - hide: si ocultar (UX)
    - message: texto para logs/tooltip
    """
    style: RowStyle = RowStyle.NORMAL
    play_sound: SoundCue = SoundCue.NONE
    highlight: bool = False
    hide: bool = False
    message: str = ""


class AlertEngine:
    """
    Motor de reglas para un renglón.

    Diseñado para ser simple y extensible.
    Hoy cubre:
    - utilidad mínima
    - oferta marcada como "mía"
    - renglón en seguimiento
    - cambios relevantes (mejor/oferta_min/mensaje)
    """

    def decide(
        self,
        *,
        tracked: bool,
        oferta_mia: bool,
        utilidad_pct: Optional[float],
        utilidad_min_pct: float,
        ocultar_bajo_umbral: bool,
        changed: bool,
        http_status: int = 200,
        mensaje: str = "",
    ) -> AlertDecision:
        """
        Retorna la decisión de alertas/estilo para un renglón.

        Parámetros clave:
        - tracked: el renglón está en seguimiento (ej. costo cargado o seguir=1)
        - oferta_mia: marca del usuario
        - utilidad_pct: utilidad calculada (None si no se puede calcular)
        - utilidad_min_pct: umbral configurado
        - ocultar_bajo_umbral: UX (ocultar si no cumple)
        - changed: hubo cambio relevante en este tick
        - http_status: último status (para señales de error)
        """

        # 1) Señales críticas primero (seguridad/errores)
        if http_status != 200:
            return AlertDecision(
                style=RowStyle.DANGER,
                play_sound=SoundCue.ERROR if tracked else SoundCue.NONE,
                highlight=tracked,
                hide=False,
                message=f"HTTP {http_status} - {mensaje}".strip(),
            )

        # 2) Si la subasta está finalizada (por mensaje)
        #    (esto se refina cuando tengamos el parser real)
        if "finalizada" in (mensaje or "").lower():
            return AlertDecision(
                style=RowStyle.WARNING,
                play_sound=SoundCue.NONE,
                highlight=False,
                hide=False,
                message="Subasta finalizada",
            )

        # 3) Oferta marcada como mía => prioridad visual (SUCCESS)
        #    (pero igual podemos alertar si cambia algo)
        if oferta_mia:
            return AlertDecision(
                style=RowStyle.SUCCESS,
                play_sound=SoundCue.SUCCESS if (changed and tracked) else SoundCue.NONE,
                highlight=bool(changed and tracked),
                hide=False,
                message="Oferta marcada como mía",
            )

        # 4) Reglas por utilidad (si existe)
        if utilidad_pct is not None:
            if utilidad_pct < utilidad_min_pct:
                # debajo de umbral
                return AlertDecision(
                    style=RowStyle.DANGER if tracked else RowStyle.NORMAL,
                    play_sound=SoundCue.NONE,
                    highlight=False,
                    hide=bool(ocultar_bajo_umbral),
                    message=f"Utilidad {utilidad_pct:.2f}% < {utilidad_min_pct:.2f}%",
                )
            else:
                # cumple umbral
                return AlertDecision(
                    style=RowStyle.TRACKED if tracked else RowStyle.NORMAL,
                    play_sound=SoundCue.ALERT if (changed and tracked) else SoundCue.NONE,
                    highlight=bool(changed and tracked),
                    hide=False,
                    message=f"Utilidad {utilidad_pct:.2f}% OK",
                )

        # 5) Si no hay utilidad calculable, igual aplicamos reglas por tracked/cambios
        if tracked and changed:
            return AlertDecision(
                style=RowStyle.WARNING,
                play_sound=SoundCue.ALERT,
                highlight=True,
                hide=False,
                message="Cambio detectado en renglón seguido",
            )

        if tracked:
            return AlertDecision(
                style=RowStyle.TRACKED,
                play_sound=SoundCue.NONE,
                highlight=False,
                hide=False,
                message="En seguimiento",
            )

        # Default
        return AlertDecision(
            style=RowStyle.NORMAL,
            play_sound=SoundCue.NONE,
            highlight=False,
            hide=False,
            message="",
        )
