from __future__ import annotations

from pathlib import Path

from app.db.database import Database
from app.excel.excel_io import (
    CALC_FIELDS,
    PLAYWRIGHT_FIELDS,
    USER_FIELDS,
    export_subasta_to_excel,
    import_excel_to_rows,
)


def test_export_import(tmp_path):
    db_path = tmp_path / "test_monitor.db"
    export_path = tmp_path / "test_export.xlsx"
    schema_path = Path(__file__).resolve().parents[1] / "app" / "db" / "schema.sql"

    db = Database(db_path=db_path)
    db.init_schema(schema_path)

    subasta_id = db.upsert_subasta(id_cot="123456", url="https://example.invalid/subasta")
    renglon_id = db.upsert_renglon(
        subasta_id=subasta_id,
        id_renglon="1",
        descripcion="Test Item",
        margen_minimo="0,0050",
    )
    db.upsert_renglon_excel(
        renglon_id=renglon_id,
        unidad_medida="KG",
        cantidad=100.0,
        items_por_renglon=5.0,
        marca="TestBrand",
        obs_usuario="Test obs",
        conv_usd=1500.0,
        costo_unit_ars=7500000.0,
        costo_total_ars=750000000.0,
        renta_minima=0.30,
        precio_referencia=1000000000.0,
        precio_ref_unitario=50000000.0,
        renta_referencia=0.33,
        precio_unit_aceptable=9750000.0,
        precio_total_aceptable=975000000.0,
        oferta_para_mejorar=900000000.0,
        precio_unit_mejora=45000000.0,
        renta_para_mejorar=0.20,
        obs_cambio="Cambio de prueba",
    )

    rows = db.fetch_export_rows(subasta_id=subasta_id)
    assert len(rows) == 1

    export_subasta_to_excel(rows=rows, out_path=str(export_path))
    imported_rows = import_excel_to_rows(file_path=str(export_path))

    assert len(imported_rows) == 1
    sample = imported_rows[0]

    required_only = {"ID SUBASTA", "ITEM"}
    invalid_fields = []
    for key in sample.keys():
        if key in CALC_FIELDS - required_only:
            invalid_fields.append(key)
        elif key in PLAYWRIGHT_FIELDS - required_only:
            invalid_fields.append(key)

    assert not invalid_fields

    valid_fields = set(sample.keys())
    expected_fields = {"ID SUBASTA", "ITEM"} | USER_FIELDS
    assert expected_fields.issubset(valid_fields)
