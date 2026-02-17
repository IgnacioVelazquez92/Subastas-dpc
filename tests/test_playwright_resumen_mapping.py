from app.collector.playwright_collector import PlaywrightCollector


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
