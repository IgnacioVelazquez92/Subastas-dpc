# app/ui/led_indicator.py
"""
LEDs visuales para mostrar estado del sistema.

Responsabilidades:
- LEDIndicator: Base para un LED visual
- HTTPStatusLED: Titila según estado de peticiones HTTP (rápido, por petición)
- OfferChangeLED: Se enciende 3 segundos cuando hay cambio, parpadea si hay múltiples
"""

from __future__ import annotations

import customtkinter as ctk
from typing import Literal, Optional


class LEDIndicator(ctk.CTkFrame):
    """LED visual que puede cambiar de color, parpadear o estar encendido."""
    
    STATE_COLORS = {
        "idle": "#333333",           # Gris oscuro (apagado)
        "green": "#00FF00",          # Verde (OK)
        "yellow": "#FFFF00",         # Amarillo (warning)
        "red": "#FF0000",            # Rojo (error)
        "red_alarm": "#FF4444",      # Rojo alarmante (crítico)
    }
    
    def __init__(self, parent, label: str = "", size: int = 24):
        super().__init__(parent, fg_color="transparent")
        
        self.label_text = label
        self.led_size = size
        self.current_state: str = "idle"
        self.blink_enabled = False
        self.blink_count = 0
        self.is_blinking_on = False
        self._return_to_idle = False
        self.after_id: Optional[str] = None  # ID del scheduled task
        
        # Frame para el LED
        self.led_frame = ctk.CTkFrame(
            self,
            width=size,
            height=size,
            fg_color=self.STATE_COLORS["idle"],
            corner_radius=size // 2
        )
        self.led_frame.pack(side="left", padx=5)
        
        # Label
        if label:
            ctk.CTkLabel(self, text=label, font=ctk.CTkFont(size=10)).pack(
                side="left", padx=5
            )
    
    def set_state(self, state: Literal["idle", "green", "yellow", "red", "red_alarm"]) -> None:
        """Establece estado del LED sin parpadeo, detiene parpadeos previos."""
        self._cancel_scheduled()
        self.current_state = state
        self.blink_enabled = False
        color = self.STATE_COLORS.get(state, self.STATE_COLORS["idle"])
        self.led_frame.configure(fg_color=color)
    
    def blink_once(
        self,
        state: Literal["idle", "green", "yellow", "red", "red_alarm"],
        *,
        return_to_idle: bool = False,
    ) -> None:
        """Hace parpadear el LED una vez (on 200ms, off 200ms)."""
        if self.blink_enabled:
            return  # Ya está en proceso de parpadeo
        
        self.current_state = state
        self._return_to_idle = return_to_idle
        self.blink_enabled = True
        self.blink_count = 0
        self.is_blinking_on = True
        
        self._do_blink()
    
    def _do_blink(self) -> None:
        """Ejecuta la secuencia de parpadeo."""
        if self.blink_count >= 2:  # 2 cambios = on + off
            self.blink_enabled = False
            if self._return_to_idle:
                self.current_state = "idle"
                self.led_frame.configure(fg_color=self.STATE_COLORS["idle"])
            else:
                color = self.STATE_COLORS[self.current_state]
                self.led_frame.configure(fg_color=color)
            return
        
        # Alter entre on y off
        if self.is_blinking_on:
            color = self.STATE_COLORS[self.current_state]
            self.is_blinking_on = False
        else:
            color = self.STATE_COLORS["idle"]
            self.is_blinking_on = True
        
        self.led_frame.configure(fg_color=color)
        self.blink_count += 1
        
        # Próximo cambio en 200ms
        self.after_id = self.after(200, self._do_blink)
    
    def turn_on(self, state: Literal["idle", "green", "yellow", "red", "red_alarm"]) -> None:
        """Enciende el LED con color específico (sin parpadear)."""
        self._cancel_scheduled()
        self.current_state = state
        self.blink_enabled = False
        color = self.STATE_COLORS.get(state, self.STATE_COLORS["idle"])
        self.led_frame.configure(fg_color=color)
    
    def turn_off(self) -> None:
        """Apaga el LED."""
        self._cancel_scheduled()
        self.set_state("idle")
    
    def _cancel_scheduled(self) -> None:
        """Cancela cualquier tarea programada (timers)."""
        if self.after_id:
            try:
                self.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None


class HTTPStatusLED(LEDIndicator):
    """
    LED que muestra estado de peticiones HTTP.
    - Parpadea verde cuando hay petición exitosa (200 OK)
    - Parpadea rojo cuando hay error 500
    - Parpadea rojo alarmante cuando hay 403 Forbidden o 429 Too Many Requests
    """
    
    def __init__(self, parent):
        super().__init__(parent, label="HTTP", size=24)
    
    def on_http_status(self, status_code: int) -> None:
        """Llamar con el código HTTP obtenido."""
        if status_code == 200:
            self.blink_once("green", return_to_idle=True)
        elif status_code == 403 or status_code == 429:
            self.blink_once("red_alarm", return_to_idle=True)
        elif status_code >= 500:
            self.blink_once("red", return_to_idle=True)
        elif status_code >= 400:
            self.blink_once("red", return_to_idle=True)
        else:
            self.blink_once("green", return_to_idle=True)
    
    def on_request_started(self) -> None:
        """Llamar cuando inicia una petición BuscarOfertas."""
        self.blink_once("green", return_to_idle=True)
    
    def on_response_200(self) -> None:
        """Llamar cuando la respuesta es 200 OK."""
        self.blink_once("green", return_to_idle=True)
    
    def on_response_500(self) -> None:
        """Llamar cuando la respuesta es 500 Internal Server Error."""
        self.blink_once("red", return_to_idle=True)
    
    def on_response_403(self) -> None:
        """Llamar cuando la respuesta es 403 Forbidden."""
        self.blink_once("red_alarm", return_to_idle=True)
    
    def on_response_429(self) -> None:
        """Llamar cuando la respuesta es 429 Too Many Requests."""
        self.blink_once("red_alarm", return_to_idle=True)
    
    def on_other_error(self, status_code: int) -> None:
        """Llamar para otros status codes de error."""
        if status_code >= 500:
            self.on_response_500()
        elif status_code >= 400:
            self.on_response_403()


class OfferChangeLED(LEDIndicator):
    """
    LED que se enciende cuando hay cambios REALES de oferta.
    
    Comportamiento:
    - Apagado por defecto (Idle)
    - Cuando hay cambio: se enciende VERDE por 3 segundos
    - Si hay otro evento DENTRO de esos 3 segundos: parpadea
    - Después de 3 segundos sin más eventos: se apaga
    """
    
    def __init__(self, parent):
        super().__init__(parent, label="Ofertas", size=24)
        self.is_active = False  # Si está en el período de 3 segundos
        self.event_count = 0  # Contador de eventos en período activo
    
    def on_offer_changed(self) -> None:
        """Llamar cuando la mejor oferta cambió (cambio real del sistema)."""
        if not self.is_active:
            # Primer evento: encender y programar apagado en 3 segundos
            self.is_active = True
            self.event_count = 1
            self.turn_on("green")
            
            # Programar que se apague en 3 segundos
            self.after_id = self.after(3000, self._auto_turn_off)
        else:
            # Evento durante período activo: parpadear y contar
            self.event_count += 1
            self.blink_once("green")
    
    def _auto_turn_off(self) -> None:
        """Call internal para apagar después de 3 segundos sin eventos."""
        self.is_active = False
        self.event_count = 0
        self.turn_off()
    
    def on_price_improved(self) -> None:
        """Alias para on_offer_changed."""
        self.on_offer_changed()

