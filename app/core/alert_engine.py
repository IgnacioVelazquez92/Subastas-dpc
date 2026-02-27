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
    MY_OFFER = "MY_OFFER"    # oferta propia (detectada por mi_id_proveedor) → #5B9BD5
    OUTBID = "OUTBID"        # oferta propia superada por otro → alerta naranja


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
        outbid: bool = False,          # True cuando la oferta propia fue superada este tick
        oferta_mia_auto: bool = False, # True cuando se detectó por mi_id_proveedor automáticamente
    ) -> AlertDecision:
        """
        Retorna la decisión de alertas/estilo para un renglón.

        Parámetros clave:
        - tracked: el renglón está en seguimiento (ej. costo cargado o seguir=1)
        - oferta_mia: marca de oferta propia (manual o auto-detectado)
        - oferta_mia_auto: True si fue detectado automáticamente por mi_id_proveedor
        - outbid: True si en este tick la oferta propia fue superada
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
        if "finalizada" in (mensaje or "").lower():
            return AlertDecision(
                style=RowStyle.WARNING,
                play_sound=SoundCue.NONE,
                highlight=False,
                hide=False,
                message="Subasta finalizada",
            )

        # 3a) Oferta propia SUPERADA:
        # mantener alerta sonora/log, pero NO forzar color OUTBID.
        # El color debe seguir reflejando utilidad para decidir si conviene reofertar.
        if outbid:
            if utilidad_pct is not None:
                if utilidad_pct >= utilidad_min_pct + 5.0:
                    style = RowStyle.SUCCESS
                elif utilidad_pct >= utilidad_min_pct:
                    style = RowStyle.WARNING
                else:
                    style = RowStyle.DANGER
            else:
                style = RowStyle.TRACKED if tracked else RowStyle.NORMAL
            return AlertDecision(
                style=style,
                play_sound=SoundCue.ALERT,
                highlight=True,
                hide=False,
                message="⚠️ ¡Tu oferta fue superada! (color según utilidad)",
            )

        # 3b) Oferta propia vigente (auto-detectada por id_proveedor)
        if oferta_mia and oferta_mia_auto:
            return AlertDecision(
                style=RowStyle.MY_OFFER,
                play_sound=SoundCue.SUCCESS if (changed and tracked) else SoundCue.NONE,
                highlight=bool(changed and tracked),
                hide=False,
                message="✅ Mejor oferta: es la tuya",
            )

        # 3c) Oferta marcada manualmente como mía => SUCCESS clásico
        if oferta_mia:
            return AlertDecision(
                style=RowStyle.SUCCESS,
                play_sound=SoundCue.SUCCESS if (changed and tracked) else SoundCue.NONE,
                highlight=bool(changed and tracked),
                hide=False,
                message="Oferta marcada como mía",
            )

        # 4) Reglas por utilidad (si existe datos para comparar)
        # - Verde: utilidad > (renta_minima + 5%)
        # - Amarillo: utilidad entre renta_minima y (renta_minima + 5%)
        # - Rojo: utilidad <= renta_minima
        if utilidad_pct is not None:
            if utilidad_pct >= utilidad_min_pct + 5.0:
                return AlertDecision(
                    style=RowStyle.SUCCESS,
                    play_sound=SoundCue.ALERT if (changed and tracked) else SoundCue.NONE,
                    highlight=bool(changed and tracked),
                    hide=False,
                    message=f"✓ Utilidad {utilidad_pct:.2f}% (excelente, +{utilidad_pct - utilidad_min_pct:.2f}%)",
                )
            elif utilidad_pct >= utilidad_min_pct:
                return AlertDecision(
                    style=RowStyle.WARNING,
                    play_sound=SoundCue.NONE,
                    highlight=bool(changed and tracked),
                    hide=False,
                    message=f"⚠ Utilidad {utilidad_pct:.2f}% (justo, +{utilidad_pct - utilidad_min_pct:.2f}%)",
                )
            else:
                return AlertDecision(
                    style=RowStyle.DANGER,
                    play_sound=SoundCue.ERROR if tracked else SoundCue.NONE,
                    highlight=bool(tracked),
                    hide=bool(ocultar_bajo_umbral),
                    message=f"✗ Utilidad {utilidad_pct:.2f}% (insuficiente, {utilidad_pct - utilidad_min_pct:.2f}%)",
                )

        # 5) Sin utilidad calculable: reglas por tracked/cambios
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
                message="En seguimiento (sin datos para evaluar rentabilidad)",
            )

        # Default
        return AlertDecision(
            style=RowStyle.NORMAL,
            play_sound=SoundCue.NONE,
            highlight=False,
            hide=False,
            message="",
        )
