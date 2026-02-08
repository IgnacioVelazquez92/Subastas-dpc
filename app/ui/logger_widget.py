# app/ui/logger_widget.py
"""
Widget de logs con filtro automático de spam.

Responsabilidad única: Display de logs mediante Text widget.
"""

from __future__ import annotations

import tkinter as tk
import customtkinter as ctk
from datetime import datetime


class LoggerWidget:
    """Widget para mostrar logs con filtro de eventos repetitivos."""
    
    def __init__(self, parent_frame: ctk.CTkFrame, height: int = 8):
        """
        Args:
            parent_frame: Frame padre donde agregar el Text widget
            height: Altura en líneas del widget
        """
        ctk.CTkLabel(parent_frame, text="Logs:").pack(anchor="w", padx=10)
        self.text_widget = tk.Text(parent_frame, height=height)
        self.text_widget.pack(fill="both", expand=False, padx=10, pady=(0, 10))
    
    def log(self, msg: str, level: str = "INFO") -> None:
        """
        Registra un mensaje, filtrando spam.
        
        Args:
            msg: Mensaje a registrar
            level: Nivel (INFO, DEBUG, WARNING, ERROR)
        """
        # Filtrar eventos repetitivos (DEBUG, HEARTBEAT sin contexto)
        if self._should_skip(msg):
            return
        
        ts = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{ts}] {msg}\n"
        
        self.text_widget.insert("end", formatted)
        self.text_widget.see("end")  # Auto-scroll al final
    
    def clear(self) -> None:
        """Limpia todos los logs."""
        self.text_widget.delete("1.0", "end")
    
    def _should_skip(self, msg: str) -> bool:
        """
        Determina si el mensaje debe ser filtrado (es spam).
        
        Criterios:
        - DEBUG sin contexto relevante
        - HEARTBEAT sin SNAPSHOT
        """
        if "EventLevel.DEBUG" in msg:
            return True
        
        if "EventType.HEARTBEAT" in msg:
            # Permitir solo HEARTBEAT con contexto (SNAPSHOT, Resumen)
            if "Resumen" not in msg and "SNAPSHOT" not in msg:
                return True
        
        return False
