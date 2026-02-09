# app/ui/improved_logger.py
"""
Sistema mejorado de logging que separa logs de usuario final vs desarrollador.

Responsabilidades:
- Loguear solo cambios significativos (cambios de oferta, cambios del usuario)
- Ignorar eventos repetitivos (HEARTBEAT, DEBUG, actualizaciones sin cambios)
- Mejor legibilidad para usuario final: "renglón X cambió Y de Z a W"
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional


class LogLevel:
    """Niveles de log."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    USER = "USER"  # Eventos que el usuario final debe ver


class ChangeMessage:
    """Generador de mensajes legibles para cambios."""
    
    @staticmethod
    def offer_changed(
        renglon_desc: str,
        old_offer: Optional[str],
        new_offer: str,
    ) -> str:
        """Mensaje cuando la mejor oferta cambió."""
        if old_offer and old_offer != new_offer:
            return f"📊 {renglon_desc}: Oferta {old_offer} → {new_offer}"
        return f"📊 {renglon_desc}: Nueva oferta {new_offer}"
    
    @staticmethod
    def price_changed(
        renglon_desc: str,
        field_name: str,
        old_value: Optional[str | float],
        new_value: str | float,
    ) -> str:
        """Mensaje cuando un precio/valor cambió."""
        if old_value:
            return f"💰 {renglon_desc}: {field_name} {old_value} → {new_value}"
        return f"💰 {renglon_desc}: {field_name} = {new_value}"
    
    @staticmethod
    def user_modified(
        renglon_desc: str,
        fields: list[str],
    ) -> str:
        """Mensaje cuando el usuario modificó campos."""
        fields_str = ", ".join(fields)
        return f"✏️  {renglon_desc}: Modificaste {fields_str}"
    
    @staticmethod
    def system_status(status: str) -> str:
        """Mensaje de estado del sistema."""
        if status == "RUNNING":
            return "▶️  Sistema iniciado - recopilando datos..."
        elif status == "STOPPED":
            return "⏹️  Sistema detenido"
        elif status == "ENDED":
            return "✅ Proceso finalizado"
        return f"ℹ️  Sistema: {status}"


class ImprovedLoggerWidget:
    """
    Widget mejorado que filtra y formatea logs inteligentemente.
    
    Estrategia:
    - Ignora: HEARTBEAT, DEBUG (a menos que sea error), actualizaciones sin cambios
    - Muestra: Cambios de oferta, cambios del usuario, estado del sistema
    - Formato: Legible, con emojis, timestamp
    """
    
    def __init__(self, max_lines: int = 100):
        self.max_lines = max_lines
        self.logs: list[tuple[str, str, str]] = []  # (timestamp, level, message)
        
        # Tracking para evitar logs duplicados
        self.last_snapshot_id: Optional[str] = None
        self.tracked_rows: dict[str, dict] = {}  # rid -> {cambios}
    
    def add(self, message: str, level: str = LogLevel.INFO) -> None:
        """Agregar un mensaje al log."""
        ts = datetime.now().strftime("%H:%M:%S")
        self.logs.append((ts, level, message))
        
        # Limitar a max_lines
        if len(self.logs) > self.max_lines:
            self.logs.pop(0)
    
    def log_offer_change(
        self,
        renglon_desc: str,
        old_offer: Optional[str],
        new_offer: str,
    ) -> str:
        """Log cuando la mejor oferta cambió."""
        msg = ChangeMessage.offer_changed(renglon_desc, old_offer, new_offer)
        self.add(msg, LogLevel.USER)
        return msg
    
    def log_price_change(
        self,
        renglon_desc: str,
        field_name: str,
        old_value: Optional[str | float],
        new_value: str | float,
    ) -> str:
        """Log cuando un precio cambió."""
        msg = ChangeMessage.price_changed(renglon_desc, field_name, old_value, new_value)
        self.add(msg, LogLevel.USER)
        return msg
    
    def log_user_modification(
        self,
        renglon_desc: str,
        fields: list[str],
    ) -> str:
        """Log cuando el usuario modificó campos."""
        msg = ChangeMessage.user_modified(renglon_desc, fields)
        self.add(msg, LogLevel.USER)
        return msg
    
    def log_system_status(self, status: str) -> str:
        """Log de cambio de estado del sistema."""
        msg = ChangeMessage.system_status(status)
        self.add(msg, LogLevel.INFO)
        return msg
    
    def log_http_error(self, http_code: int, context: str = "") -> None:
        """Log de error HTTP."""
        ctx = f" ({context})" if context else ""
        msg = f"🔴 Error HTTP {http_code}{ctx}"
        self.add(msg, LogLevel.ERROR)
    
    def log_info(self, message: str) -> None:
        """Log de información general."""
        self.add(message, LogLevel.INFO)
    
    def log_warning(self, message: str) -> None:
        """Log de advertencia."""
        self.add(message, LogLevel.WARNING)
    
    def log_error(self, message: str) -> None:
        """Log de error."""
        self.add(message, LogLevel.ERROR)
    
    def get_lines(self, count: Optional[int] = None) -> list[str]:
        """Retorna últimas N líneas formateadas."""
        count = count or len(self.logs)
        lines = []
        
        for ts, level, msg in self.logs[-count:]:
            # Colorear por nivel (solo en forma de prefijo, el widget maneja color)
            prefix = f"[{level}]" if level != LogLevel.USER else ""
            line = f"{ts} {prefix} {msg}".strip()
            lines.append(line)
        
        return lines
    
    def clear(self) -> None:
        """Limpiar logs."""
        self.logs.clear()
        self.tracked_rows.clear()
        self.last_snapshot_id = None
