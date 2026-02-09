#!/usr/bin/env python3
"""
Script de prueba para verificar que todos los cálculos y logging funcionen correctamente.
"""

print("="*60)
print("VERIFICACIÓN DE CÁLCULOS - Monitor de Subastas")
print("="*60)

# Test 1: Bidireccionalidad de costos
print("\n[TEST 1] Bidireccionalidad de costos")
print("-" * 40)

from app.core.engine import Engine

# Crear instancia temporal del Engine para acceder al método
e = Engine.__new__(Engine)
e.config = type('obj', (object,), {'utilidad_min_pct_default': 10.0})()

# Caso 1: Solo UNITARIO presente
print("\nCaso 1: Solo UNITARIO")
result = e._resolve_costo_final(costo_unit_ars=1000.0, costo_total_ars=None, cantidad=10.0)
print(f"✓ Esperado: (1000.0, 10000.0)")
print(f"✓ Obtenido: {result}")
assert result == (1000.0, 10000.0), "❌ Error en caso 1"

# Caso 2: Solo TOTAL presente
print("\nCaso 2: Solo TOTAL")
result = e._resolve_costo_final(costo_unit_ars=None, costo_total_ars=10000.0, cantidad=10.0)
print(f"✓ Esperado: (1000.0, 10000.0)")
print(f"✓ Obtenido: {result}")
assert result[0] == 1000.0 and result[1] == 10000.0, "❌ Error en caso 2"

# Caso 3: AMBOS presentes (debe priorizar TOTAL)
print("\nCaso 3: AMBOS presentes (priorizar TOTAL)")
result = e._resolve_costo_final(costo_unit_ars=999.0, costo_total_ars=10000.0, cantidad=10.0)
print(f"✓ Esperado: (1000.0, 10000.0) - recalcula unit desde total")
print(f"✓ Obtenido: {result}")
assert result == (1000.0, 10000.0), "❌ Error en caso 3"

# Caso 4: NINGUNO presente
print("\nCaso 4: NINGUNO")
result = e._resolve_costo_final(costo_unit_ars=None, costo_total_ars=None, cantidad=10.0)
print(f"✓ Esperado: (None, None)")
print(f"✓ Obtenido: {result}")
assert result == (None, None), "❌ Error en caso 4"

print("\n" + "="*60)
print("✅ TODOS LOS TESTS PASARON EXITOSAMENTE")
print("="*60)
print("\n📊 Los cálculos están funcionando correctamente.")
print("💡 Ejecuta la aplicación para ver el logging detallado en acción.")
