from app.core.engine import Engine
from app.utils.renglon_math import resolve_cantidad_equivalente


def _engine_stub() -> Engine:
    engine = Engine.__new__(Engine)
    return engine


def test_resolve_cantidad_equivalente_divides_por_items():
    assert resolve_cantidad_equivalente(293700.0, 5.0) == 58740.0


def test_engine_resolve_precio_ref_unitario_uses_items_por_renglon():
    engine = _engine_stub()
    result = engine._resolve_precio_ref_unitario(
        cantidad=293700.0,
        items_por_renglon=5.0,
        precio_referencia=None,
        presupuesto=2320230000.0,
    )
    assert result == 39500.0


def test_engine_resolve_costo_final_uses_cantidad_equivalente():
    engine = _engine_stub()
    unit, total = engine._resolve_costo_final(
        costo_unit_ars=39500.0,
        costo_total_ars=None,
        cantidad=293700.0,
        items_por_renglon=5.0,
    )
    assert unit == 39500.0
    assert total == 2320230000.0


def test_engine_resolve_costo_final_total_to_unit_uses_items_por_renglon():
    engine = _engine_stub()
    unit, total = engine._resolve_costo_final(
        costo_unit_ars=None,
        costo_total_ars=2320230000.0,
        cantidad=293700.0,
        items_por_renglon=5.0,
    )
    assert total == 2320230000.0
    assert unit == 39500.0
