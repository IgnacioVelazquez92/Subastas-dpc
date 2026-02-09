# app/ui/formatters.py
"""
Formateo de datos para display en la UI.

Responsabilidad única: Convertir valores Python a strings formateados para Tkinter.
"""

from __future__ import annotations

from typing import Optional
from app.utils.money import float_to_money_txt


class DataFormatter:
    """Formateo de números, dinero, porcentajes."""

    @staticmethod
    def format_money(value: float | None) -> str:
        """Formatea dinero con separadores: $ 1.234.567,89"""
        if value is None:
            return ""
        try:
            return float_to_money_txt(float(value), decimals=2)
        except Exception:
            return ""

    @staticmethod
    def format_percentage(value: float | None) -> str:
        """Formatea porcentaje desde fracción: 0.3 -> 30%"""
        if value is None:
            return ""
        return f"{value * 100:.2f}%"
    
    @staticmethod
    def format_percentage_from_multiplier(value: float | None) -> str:
        """Formatea porcentaje desde multiplicador: 1.3 -> 30%"""
        if value is None:
            return ""
        if value >= 1.0:
            return f"{(value - 1.0) * 100:.2f}%"
        # Si es < 1, probablemente ya sea fracción
        return f"{value * 100:.2f}%"

    @staticmethod
    def format_number(value: float | None, *, decimals: int = 2) -> str:
        """Formatea número decimal."""
        if value is None:
            return ""
        try:
            return f"{float(value):.{decimals}f}"
        except Exception:
            return ""

    @staticmethod
    def truncate(s: str, n: int) -> str:
        """Trunca string a n caracteres, agrega '...' si se corta."""
        s = (s or "").strip()
        return s if len(s) <= n else s[: n - 3] + "..."

    @staticmethod
    def parse_float(raw: str) -> float | None:
        """
        Parsea string a float soportando múltiples formatos:
        - "1.234,56" (decimal con coma)
        - "1,234.56" (decimal con punto)
        - "1.234.567" (sin decimales)
        - "1,234,567" (sin decimales)
        - "1234567" (número simple)
        
        Inteligencia: usa el separador final como decimal.
        """
        if raw is None:
            return None
        
        s = str(raw).strip()
        if not s:
            return None
        
        # Remover espacios y no-break spaces
        s = s.replace(" ", "").replace("\u00a0", "")
        
        try:
            if "," in s and "." in s:
                # Ambos separadores presentes: usa el final como decimal
                if s.rfind(",") > s.rfind("."):
                    # Decimal es coma: 1.234,56
                    s = s.replace(".", "").replace(",", ".")
                else:
                    # Decimal es punto: 1,234.56
                    s = s.replace(",", "")
                    
            elif "," in s:
                parts = s.split(",")
                if len(parts) > 2 and all(len(p) == 3 for p in parts[1:]):
                    # Separadores de miles: 1,234,567
                    s = "".join(parts)
                elif len(parts) > 1:
                    # Decimal: 1,23 o 1,234,56
                    s = "".join(parts[:-1]) + "." + parts[-1]
                    
            elif "." in s:
                parts = s.split(".")
                if len(parts) > 2 and all(len(p) == 3 for p in parts[1:]):
                    # Separadores de miles: 1.234.567
                    s = "".join(parts)
                elif len(parts) > 1:
                    # Decimal: 1.23 o 1.234.56
                    s = "".join(parts[:-1]) + "." + parts[-1]
            
            return float(s)
        except Exception:
            return None


class DisplayValues:
    """
    Prepara una UIRow para mostrar en Treeview.
    
    Encapsula la lógica de qué valor mostrar y cómo formatearlo,
    basado en el estado de la fila.
    """

    @staticmethod
    def build_row_values(row) -> tuple[str, ...]:
        """
        Convierte UIRow a tupla de strings para Treeview.
        
        Espera que row sea un UIRow con todos los atributos.
        Retorna tupla de 23 strings en orden de self.cols.
        """
        fmt = DataFormatter
        
        values = (
            # IDs y b\u00e1sicos
            row.id_subasta or "",
            row.id_renglon,
            fmt.truncate(row.desc, 80),
            fmt.format_number(row.cantidad, decimals=2),
            # Metadata usuario
            row.unidad_medida or "",
            row.marca or "",
            fmt.truncate(row.obs_usuario or "", 40),
            # Costos
            fmt.format_number(row.conv_usd, decimals=2),
            fmt.format_number(row.costo_unit_usd, decimals=2),
            fmt.format_number(row.costo_total_usd, decimals=2),
            fmt.format_money(row.costo_unit_ars),
            fmt.format_money(row.costo_total_ars),
            # Rentabilidad mínima (fracción 0-1)
            fmt.format_percentage(row.renta_minima) if row.renta_minima is not None else "",
            fmt.format_money(row.precio_unit_aceptable),
            fmt.format_money(row.precio_total_aceptable),
            # Referencia
            fmt.format_money(row.precio_referencia),
            fmt.format_money(row.precio_ref_unitario),
            fmt.format_percentage(row.renta_referencia) if row.renta_referencia is not None else "",
            # Mejora en subasta
            row.mejor_oferta_txt or "",
            fmt.format_money(row.oferta_para_mejorar),
            fmt.format_money(row.precio_unit_mejora),
            fmt.format_percentage(row.renta_para_mejorar) if row.renta_para_mejorar is not None else "",
            # Observaciones
            fmt.truncate(row.obs_cambio or "", 60),
        )
        
        return values
