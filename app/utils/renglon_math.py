from __future__ import annotations


def normalize_items_por_renglon(items_por_renglon: float | None) -> float:
    try:
        value = float(items_por_renglon)
    except Exception:
        return 1.0
    return value if value > 0 else 1.0


def resolve_cantidad_equivalente(
    cantidad: float | None,
    items_por_renglon: float | None,
) -> float | None:
    if cantidad is None:
        return None
    try:
        return float(cantidad) / normalize_items_por_renglon(items_por_renglon)
    except Exception:
        return None
