# app/models/domain.py
"""
Modelos de dominio (dataclasses) usados por el core y la UI.

Reglas:
- Acá NO hay lógica de DB ni lógica de UI.
- Son estructuras claras para transportar información.
- Las claves principales del portal se conservan como texto (id_cot, id_renglon).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# -------------------------
# Entidades principales
# -------------------------

@dataclass(frozen=True)
class Subasta:
    """
    Una subasta monitoreada del portal.
    id_cot: id_Cotizacion (texto, como viene del portal)
    """
    id: int
    id_cot: str
    url: str
    estado: str  # RUNNING | PAUSED | ENDED | ERROR
    started_at: str
    ended_at: Optional[str] = None
    last_ok_at: Optional[str] = None
    last_http_code: Optional[int] = None
    err_streak: int = 0


@dataclass(frozen=True)
class Renglon:
    """
    Un renglón dentro de una subasta (ddlItemRenglon option).
    """
    id: int
    subasta_id: int
    id_renglon: str
    descripcion: str
    margen_minimo: Optional[str] = None
    created_at: Optional[str] = None


# -------------------------
# Estado operativo (lecturas del portal)
# -------------------------

@dataclass
class RenglonEstado:
    """
    Estado "actual" del renglón (última lectura).
    Guardamos:
    - *_txt: string original del portal (para mostrar tal cual)
    - *_val: float normalizado (para cálculos)
    """
    renglon_id: int

    mejor_oferta_txt: str = ""
    oferta_min_txt: str = ""
    presupuesto_txt: str = ""

    mejor_oferta_val: Optional[float] = None
    oferta_min_val: Optional[float] = None
    presupuesto_val: Optional[float] = None

    mensaje: str = ""
    updated_at: str = ""


# -------------------------
# Configuración del usuario por renglón
# -------------------------

@dataclass
class RenglonConfig:
    """
    Config persistente del usuario.
    - costo_subtotal: costo propio (si está presente, se calcula utilidad)
    - oferta_mia: marca si la mejor oferta vigente es tuya
    - seguir: habilita alertas / seguimiento activo
    - utilidad_min_pct: umbral para marcar / filtrar
    - ocultar_bajo_umbral: UX (ocultar renglones que no cumplen)
    """
    renglon_id: int

    costo_subtotal: Optional[float] = None
    oferta_mia: bool = False
    seguir: bool = False

    utilidad_min_pct: float = 10.0
    ocultar_bajo_umbral: bool = False

    updated_at: str = ""


# -------------------------
# Datos derivados (para UI)
# -------------------------

@dataclass
class RenglonVista:
    """
    Vista consolidada para la UI (no se persiste como tabla; es derivada).
    Une:
    - Renglon + Estado + Config
    y agrega:
    - utilidad_pct
    - flags de color/estado
    """
    subasta_id: int
    id_renglon: str
    descripcion: str

    mejor_oferta_txt: str = ""
    oferta_min_txt: str = ""
    presupuesto_txt: str = ""
    mensaje: str = ""

    costo_subtotal: Optional[float] = None
    utilidad_pct: Optional[float] = None

    seguir: bool = False
    oferta_mia: bool = False

# -------------------------
# Formato para UI en Treeview
# -------------------------

@dataclass
class UIRow:
    """
    Fila en la UI (Treeview).
    
    Contiene todos los campos que se muestran en la tabla,
    incluyendo datos de oferta, costos y rentabilidad calculados.
    """
    id_renglon: str
    desc: str
    
    # IDs de referencia
    update_led: str = ""
    id_subasta: Optional[str] = None
    subasta_id: Optional[str] = None
    renglon_pk: Optional[int] = None
    
    # Datos de oferta
    mejor_oferta_txt: Optional[str] = None
    oferta_min_txt: Optional[str] = None
    oferta_para_mejorar: Optional[float] = None
    precio_referencia: Optional[float] = None
    
    # Observaciones
    obs_cambio: Optional[str] = None
    
    # Datos técnicos del renglón
    unidad_medida: Optional[str] = None
    cantidad: Optional[float] = None
    marca: Optional[str] = None
    obs_usuario: Optional[str] = None
    
    # Conversión y costos
    conv_usd: Optional[float] = None
    costo_unit_usd: Optional[float] = None
    costo_total_usd: Optional[float] = None
    costo_unit_ars: Optional[float] = None
    costo_total_ars: Optional[float] = None
    renta_minima: Optional[float] = None
    
    # Precios aceptables
    precio_unit_aceptable: Optional[float] = None
    precio_total_aceptable: Optional[float] = None
    
    # Análisis de referencia
    precio_ref_unitario: Optional[float] = None
    renta_referencia: Optional[float] = None
    
    # Análisis de mejora
    precio_unit_mejora: Optional[float] = None
    renta_para_mejorar: Optional[float] = None
    
    # Flags de estado
    seguir: bool = False
    oferta_mia: bool = False
