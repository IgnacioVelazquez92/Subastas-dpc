#!/usr/bin/env python3
"""
Test de conversión de porcentajes con NUEVO FORMATO (fracciones 0-1)

Formato NUEVO:
- BD almacena: 0.10 para 10%, 0.30 para 30%, 1.0 para 100%
- Excel muestra: 10, 30, 100 (porcentajes directos)
- Fórmula: precio_aceptable = (1 + renta_minima) * costo
"""

def test_export_fraction_to_percent():
    """Test: Fracciones en BD → Porcentajes en Excel"""
    print("=" * 60)
    print("TEST EXPORT: Fracción → Porcentaje")
    print("=" * 60)
    
    test_cases = [
        (0.10, 10.0),   # 10% margen
        (0.30, 30.0),   # 30% margen
        (1.0, 100.0),   # 100% margen (duplicar precio)
        (0.05, 5.0),    # 5% margen
        (10.0, 1000.0), # 1000% margen (caso extremo)
    ]
    
    for bd_value, expected_excel in test_cases:
        # Fórmula de export: renta_minima * 100
        excel_value = bd_value * 100
        
        status = "✅" if abs(excel_value - expected_excel) < 0.01 else "❌"
        print(f"{status} BD: {bd_value:6.2f} → Excel: {excel_value:6.2f}% (esperado: {expected_excel:6.2f}%)")
    
    print()

def test_import_percent_to_fraction():
    """Test: Porcentajes en Excel → Fracciones en BD"""
    print("=" * 60)
    print("TEST IMPORT: Porcentaje → Fracción")
    print("=" * 60)
    
    test_cases = [
        (10.0, 0.10, "10% → 0.1"),
        (30.0, 0.30, "30% → 0.3"),
        (100.0, 1.0, "100% → 1.0"),
        (5.0, 0.05, "5% → 0.05"),
        (0.10, 0.10, "0.1 (ya fracción) → 0.1"),
        (0.50, 0.50, "0.5 (ya fracción) → 0.5"),
        (1000.0, 10.0, "1000% → 10.0"),
    ]
    
    for excel_value, expected_bd, description in test_cases:
        # Fórmula de import: >= 1.0 → val/100, < 1.0 → val
        if excel_value >= 1.0:
            bd_value = excel_value / 100.0
        else:
            bd_value = excel_value
        
        status = "✅" if abs(bd_value - expected_bd) < 0.001 else "❌"
        print(f"{status} Excel: {excel_value:7.2f} → BD: {bd_value:5.2f} (esperado: {expected_bd:5.2f}) - {description}")
    
    print()

def test_formula_calculation():
    """Test: Fórmulas con nuevo formato"""
    print("=" * 60)
    print("TEST FÓRMULAS: Cálculo de precio aceptable")
    print("=" * 60)
    
    test_cases = [
        (1000000, 0.10, 1100000, "Costo 1M + 10% = 1.1M"),
        (1000000, 0.30, 1300000, "Costo 1M + 30% = 1.3M"),
        (500000, 0.15, 575000, "Costo 500K + 15% = 575K"),
        (750000, 1.0, 1500000, "Costo 750K + 100% = 1.5M (duplicar)"),
    ]
    
    for costo, renta_minima, expected_precio, description in test_cases:
        # Fórmula NUEVA: precio = (1 + renta_minima) * costo
        precio_aceptable = (1 + renta_minima) * costo
        
        status = "✅" if abs(precio_aceptable - expected_precio) < 1 else "❌"
        print(f"{status} {description}")
        print(f"   Fórmula: ({1.0} + {renta_minima}) * {costo:,} = {precio_aceptable:,.0f}")
        print(f"   Esperado: {expected_precio:,}")
        print()

def test_roundtrip():
    """Test: BD → Excel → BD (ida y vuelta)"""
    print("=" * 60)
    print("TEST ROUNDTRIP: BD → Excel → BD")
    print("=" * 60)
    
    original_values = [0.10, 0.30, 1.0, 0.05, 10.0]
    
    for original in original_values:
        # Export: fracción → porcentaje
        excel_value = original * 100
        
        # Import: porcentaje → fracción
        if excel_value >= 1.0:
            reimport = excel_value / 100.0
        else:
            reimport = excel_value
        
        status = "✅" if abs(reimport - original) < 0.001 else "❌"
        print(f"{status} Original: {original:6.2f} → Excel: {excel_value:7.2f}% → Reimport: {reimport:6.2f}")
    
    print()

def test_comparison_old_vs_new():
    """Test: Comparación formato viejo vs nuevo"""
    print("=" * 60)
    print("COMPARACIÓN: Formato VIEJO vs NUEVO")
    print("=" * 60)
    
    print("\nPara 30% de margen:")
    print("-" * 60)
    print("FORMATO VIEJO (multiplicador):")
    print("  BD:      1.3")
    print("  Fórmula: precio = 1.3 * costo")
    print("  Ejemplo: precio = 1.3 * 1,000,000 = 1,300,000")
    print("  ⚠️  Ambiguo: ¿1.3 es 30% o 130%?")
    
    print("\nFORMATO NUEVO (fracción):")
    print("  BD:      0.3")
    print("  Fórmula: precio = (1 + 0.3) * costo")
    print("  Ejemplo: precio = 1.3 * 1,000,000 = 1,300,000")
    print("  ✅ Claro: 0.3 siempre es 30%")
    
    print("\n" + "=" * 60)
    print("VENTAJAS DEL NUEVO FORMATO:")
    print("=" * 60)
    print("✅ Sin ambigüedad: 0.3 = 30%, 0.1 = 10%, 1.0 = 100%")
    print("✅ Estándar matemático: fracción entre 0 y 1")
    print("✅ Excel coherente: muestra 10, 30, 100 (porcentajes)")
    print("✅ Fórmula explícita: (1 + margen) * costo")
    print()

if __name__ == "__main__":
    test_export_fraction_to_percent()
    test_import_percent_to_fraction()
    test_formula_calculation()
    test_roundtrip()
    test_comparison_old_vs_new()
    
    print("=" * 60)
    print("EJEMPLO PRÁCTICO - Usuario configura 30% de margen:")
    print("=" * 60)
    print("1. En UI edita renglón y pone 'Renta mínima: 30' → se guarda 0.3 en BD")
    print("2. Se exporta a Excel → aparece '30' (porcentaje claro)")
    print("3. Usuario ve '30' y lo entiende como 30%")
    print("4. Si lo cambia a '15' y reimporta → se convierte a 0.15")
    print("5. Fórmula: precio = (1 + 0.15) * costo = 1.15 * costo")
    print("=" * 60)
