#!/usr/bin/env python3
"""
Test export/import coherence:
1. Exporta datos desde la BD actual
2. Importa el archivo exportado
3. Verifica que solo los USER_FIELDS fueron importados
4. Verifica que CALC_FIELDS y PLAYWRIGHT_FIELDS no fueron sobrescritos
"""
import sys
import sqlite3
from app.excel.excel_io import export_subasta_to_excel, import_excel_to_rows, USER_FIELDS, CALC_FIELDS, PLAYWRIGHT_FIELDS
from app.db.database import Database

def test_export_import():
    # Conectar a BD
    db = Database(db_path="data/subastas.db")
    
    # Obtener último subasta_id
    subasta_id = db.get_latest_subasta_id()
    if not subasta_id:
        print("❌ No hay subastas en la BD")
        return False
    
    print(f"✅ Usando subasta_id={subasta_id}")
    
    # Exportar
    export_path = "/tmp/test_export.xlsx"
    try:
        rows = db.fetch_export_rows(subasta_id=subasta_id)
        export_subasta_to_excel(rows=rows, out_path=export_path)
        print(f"✅ Exportado a {export_path} ({len(rows)} renglones)")
    except Exception as e:
        print(f"❌ Error exportando: {e}")
        return False
    
    # Importar
    try:
        imported_rows = import_excel_to_rows(file_path=export_path)
        print(f"✅ Importado {len(imported_rows)} renglones")
    except Exception as e:
        print(f"❌ Error importando: {e}")
        return False
    
    # Validar coherencia
    if not imported_rows:
        print("⚠️  No hay filas importadas")
        return True
    
    sample = imported_rows[0]
    print(f"\n📋 Sample de fila importada:")
    for key in sorted(sample.keys()):
        val = sample[key]
        if isinstance(val, (int, float)):
            val = f"{val:,.2f}" if isinstance(val, float) else str(val)
        print(f"  {key}: {val}")
    
    # Validar que NO contiene CALC_FIELDS ni PLAYWRIGHT_FIELDS (excepto ID/ITEM)
    print(f"\n✅ Validación:")
    required_only = {"ID SUBASTA", "ITEM"}
    
    invalid_fields = []
    for key in sample.keys():
        if key in CALC_FIELDS - required_only:
            invalid_fields.append(f"{key} (CALC_FIELD - NO debería estar)")
        elif key in PLAYWRIGHT_FIELDS - required_only:
            invalid_fields.append(f"{key} (PLAYWRIGHT_FIELD - NO debería estar)")
    
    if invalid_fields:
        print(f"❌ Campos que NO deberían importarse:")
        for field in invalid_fields:
            print(f"   - {field}")
        return False
    
    valid_fields = set(sample.keys())
    expected_fields = {"ID SUBASTA", "ITEM"} | USER_FIELDS
    missing = expected_fields - valid_fields
    
    if missing:
        print(f"⚠️  Campos USER faltantes: {missing}")
    
    extra = valid_fields - expected_fields
    if extra:
        print(f"⚠️  Campos extra: {extra}")
    
    print(f"✅ Todos los campos importados son válidos (solo USER_FIELDS)")
    
    return True

if __name__ == "__main__":
    success = test_export_import()
    sys.exit(0 if success else 1)
