from app.collector.playwright_collector import PlaywrightCollector
import asyncio


def test_match_resumen_row_assigns_each_option_to_distinct_resumen():
    resumen_rows = [
        {"descripcion": "RENGLON  INSUMOS DE LIBRERÍA PARA DEPENDENCIAS ADMINISTRATIVAS"},
        {"descripcion": "RENGLON RESMAS DE PAPEL PARA DEPENDENCIAS ADMINISTRATIVAS"},
    ]
    used = set()

    row_1 = PlaywrightCollector._match_resumen_row(
        option_text="1 - INSUMOS DE LIBRERIA PARA DEPENDENCIAS ADMINISTRATIVAS",
        resumen_rows=resumen_rows,
        used_resumen_indices=used,
    )
    row_2 = PlaywrightCollector._match_resumen_row(
        option_text="2 - RESMAS DE PAPEL PARA DEPENDENCIAS ADMINISTRATIVAS",
        resumen_rows=resumen_rows,
        used_resumen_indices=used,
    )

    assert row_1 is not None
    assert row_2 is not None
    assert row_1["descripcion"] != row_2["descripcion"]
    assert "INSUMOS" in row_1["descripcion"]
    assert "RESMAS" in row_2["descripcion"]


def test_match_resumen_row_can_match_without_renglon_prefix():
    resumen_rows = [
        {"descripcion": "RENGLON REPUESTOS INFORMATICOS"},
    ]
    used = set()

    row = PlaywrightCollector._match_resumen_row(
        option_text="REPUESTOS INFORMATICOS",
        resumen_rows=resumen_rows,
        used_resumen_indices=used,
    )

    assert row is not None
    assert row["descripcion"] == "RENGLON REPUESTOS INFORMATICOS"


def test_parse_detalle_table_derives_items_por_renglon_and_precio_referencia():
    data = [
        ["prod 1,1", "76600", "$ 7.900,00", "$ 605.140.000,00"],
        ["prod 1,2", "45500", "$ 7.900,00", "$ 359.450.000,00"],
        ["prod 1,3", "27400", "$ 7.900,00", "$ 216.460.000,00"],
        ["prod 1,4", "23700", "$ 7.900,00", "$ 187.230.000,00"],
        ["prod 1,5", "120500", "$ 7.900,00", "$ 951.950.000,00"],
        ["RENGLON 1", "293700", "$ 39.500,00", "$ 2.320.230.000,00"],
    ]

    class FakeLocator:
        async def evaluate_all(self, _script):
            return data

    class FakePage:
        def locator(self, _selector):
            return FakeLocator()

    collector = PlaywrightCollector.__new__(PlaywrightCollector)
    rows = asyncio.run(collector._parse_detalle_table(FakePage()))

    resumen = rows[-1]
    assert resumen["is_resumen"] is True
    assert resumen["items_por_renglon"] == 5.0
    assert resumen["precio_ref_unitario"] == 39500.0
