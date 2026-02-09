#!/usr/bin/env python3
"""
Test para verificar conversión de renta_minima:
- Export: Multiplicador → Porcentaje
- Import: Porcentaje → Multiplicador
"""

def test_export_format():
    """Test: Multiplicador (BD) → Porcentaje (Excel)"""
    print("=" * 60)
    print("TEST EXPORT: Multiplicador → Porcentaje")
    print("=" * 60)
    
    test_cases = [
        (1.1, 10.0),   # 10% margen
        (1.3, 30.0),   # 30% margen
        (2.0, 100.0),  # 100% margen
        (1.05, 5.0),   # 5% margen
        (11.0, 1000.0),  # caso extremo reported por usuario
    ]
    
    for multiplier, expected_percent in test_cases:
        # Fórmula: (multiplicador - 1) * 100
        result = (multiplier - 1.0) * 100
        status = "✅" if abs(result - expected_percent) < 0.01 else "❌"
        print(f"{status} BD:{multiplier:6.2f} → Excel:{result:7.2f}% (esperado:{expected_percent:7.2f}%)")
    print()

def test_import_format():
    """Test: Porcentaje (Excel) → Multiplicador (BD)"""
    print("=" * 60)
    print("TEST IMPORT: Porcentaje → Multiplicador")
    print("=" * 60)
    
    def _renta_to_multiplier(val):
        """Converter function (copiar de app_runtime.py)"""
        if val is None or val == "":
            return None
        try:
            num = float(val)
            if num is None:
                return None
            # Si es mayor a 2.0, asumimos porcentaje: 10 → 1.1, 30 → 1.3
            if num > 2.0:
                return 1.0 + (num / 100.0)
            # Si es <= 2.0, asumimos que ya es multiplicador: 1.1 → 1.1
            return num
        except Exception:
            return None
    
    test_cases = [
        # (input_excel, expected_multiplier, description)
        (10.0, 1.1, "10% → 1.1"),
        (30.0, 1.3, "30% → 1.3"),
        (100.0, 2.0, "100% → 2.0"),
        (5.0, 1.05, "5% → 1.05"),
        (1.1, 1.1, "1.1 (ya multiplicador) → 1.1"),
        (1.5, 1.5, "1.5 (ya multiplicador) → 1.5"),
        (2.0, 2.0, "2.0 (límite) → 2.0"),
        (1000.0, 11.0, "1000% → 11.0"),
    ]
    
    for input_val, expected, desc in test_cases:
        result = _renta_to_multiplier(input_val)
        status = "✅" if result is not None and abs(result - expected) < 0.01 else "❌"
        print(f"{status} Excel:{input_val:7.2f} → BD:{result:6.2f} (esperado:{expected:6.2f}) - {desc}")
    print()

def test_roundtrip():
    """Test: Multiplicador → Export → Import → Multiplicador"""
    print("=" * 60)
    print("TEST ROUNDTRIP: BD → Excel → BD")
    print("=" * 60)
    
    def _renta_to_multiplier(val):
        if val is None or val == "":
            return None
        try:
            num = float(val)
            if num is None:
                return None
            if num > 2.0:
                return 1.0 + (num / 100.0)
            return num
        except Exception:
            return None
    
    test_cases = [1.1, 1.3, 2.0, 1.05, 11.0]
    
    for original in test_cases:
        # Export
        exported_percent = (original - 1.0) * 100
        # Import
        reimported = _renta_to_multiplier(exported_percent)
        
        status = "✅" if reimported is not None and abs(reimported - original) < 0.01 else "❌"
        print(f"{status} Original:{original:6.2f} → Excel:{exported_percent:7.2f}% → Reimport:{reimported:6.2f}")
    print()

if __name__ == "__main__":
    test_export_format()
    test_import_format()
    test_roundtrip()
    
    print("\n" + "=" * 60)
    print("EJEMPLO PRÁCTICO - Usuario configura 10% de margen:")
    print("=" * 60)
    print("1. En UI edita renglón y pone 'Renta mínima: 10%' → se guarda 1.1 en BD")
    print("2. Se exporta a Excel → aparece '10' o '10.0' (porcentaje)")
    print("3. Usuario ve '10' y lo entiende como 10%")
    print("4. Si lo cambia a '30' y reimporta → se convierte a 1.3")
    print("5. Si por error escribe '1.3' → se mantiene como 1.3 (30%)")
    print("=" * 60)
