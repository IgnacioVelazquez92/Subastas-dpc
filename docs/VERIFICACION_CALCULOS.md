# ✅ VERIFICACIÓN DE CÁLCULOS - Monitor de Subastas

## 🎯 PRIORIDAD ABSOLUTA: INTEGRIDAD DE DATOS

Los datos y cálculos son **CRÍTICOS** para la toma de decisiones. Cualquier error en cálculos puede llevar a decisiones erróneas en subastas.

## 📊 FÓRMULAS VERIFICADAS

### 1. **Bidireccionalidad de Costos ARS** (`_resolve_costo_final`)

**Ubicación:** `app/core/engine.py` línea 139

**Reglas de prioridad:**
```
1. Si AMBOS están presentes (unit_ars Y total_ars):
   - PRIORIZAR TOTAL (es el valor autorizado)
   - RECALCULAR: unit = total / cantidad
   
2. Si SOLO TOTAL está presente:
   - CALCULAR: unit = total / cantidad
   
3. Si SOLO UNITARIO está presente:
   - CALCULAR: total = unit * cantidad
   
4. Si NINGUNO:
   - Retornar (None, None)
```

**Ejemplos:**
```
Entrada: unit=1000, total=10000, cant=10
Salida: unit=1000.00, total=10000.00 (recalcula unit desde total)

Entrada: unit=None, total=10000, cant=10
Salida: unit=1000.00, total=10000.00

Entrada: unit=1000, total=None, cant=10
Salida: unit=1000.00, total=10000.00

Entrada: unit=None, total=None, cant=10
Salida: unit=None, total=None
```

### 2. **Precio Unitario Aceptable** (engine.py línea 444)

**Fórmula:**
```
precio_unit_aceptable = renta_minima × costo_unit_ars
```

**Ejemplo:**
```
Si renta_minima = 1.3 (30%)
   costo_unit_ars = 1000
   
Entonces: precio_unit_aceptable = 1.3 × 1000 = 1300
```

### 3. **Precio Total Aceptable** (engine.py línea 448)

**Fórmula:**
```
precio_total_aceptable = renta_minima × costo_total_ars
```

**Ejemplo:**
```
Si renta_minima = 1.3
   costo_total_ars = 10000
   
Entonces: precio_total_aceptable = 1.3 × 10000 = 13000
```

### 4. **Rentabilidad Sobre Referencia** (engine.py línea 464)

**Fórmula:**
```
renta_referencia = (precio_ref_unitario / costo_unit_ars) - 1.0
```

**Ejemplo:**
```
Si precio_ref_unitario = 1500
   costo_unit_ars = 1000
   
Entonces: renta_referencia = (1500 / 1000) - 1 = 0.5 = 50%
```

### 5. **Precio Unitario Para Mejorar** (engine.py línea 475)

**Fórmula:**
```
precio_unit_mejora = oferta_min_val / cantidad
```

**Ejemplo:**
```
Si oferta_min_val = 12000
   cantidad = 10
   
Entonces: precio_unit_mejora = 12000 / 10 = 1200
```

### 6. **Rentabilidad Para Mejorar** (engine.py línea 482)

**Fórmula:**
```
renta_para_mejorar = (precio_unit_mejora / costo_unit_ars) - 1.0
```

**Ejemplo:**
```
Si precio_unit_mejora = 1200
   costo_unit_ars = 1000
   
Entonces: renta_para_mejorar = (1200 / 1000) - 1 = 0.2 = 20%
```

### 7. **Utilidad Porcentual** (engine.py línea 523) 🔴 CRÍTICO PARA COLORACIÓN

**Fórmula:**
```
utilidad_pct = ((oferta_min_val - base_cost) / base_cost) × 100
```

**Donde:**
- `base_cost` = `costo_subtotal` (si existe) o `costo_unit_ars`
- `oferta_min_val` = mejor oferta para mejorar la subasta

**Ejemplo:**
```
Si oferta_min_val = 1300
   base_cost = 1000
   
Entonces: utilidad_pct = ((1300 - 1000) / 1000) × 100 = 30%
```

**Coloración según utilidad_pct vs utilidad_min_pct:**
```
VERDE (SUCCESS):  utilidad_pct >= utilidad_min_pct + 5%
AMARILLO (WARNING): utilidad_min_pct <= utilidad_pct < utilidad_min_pct + 5%
ROJO (DANGER):    utilidad_pct < utilidad_min_pct
```

## 🔧 LOGGING IMPLEMENTADO

Ahora cada vez que se procesa un renglón, se imprimen en la terminal:

### Console Output Format:
```
============================================================
[UPDATE] Renglón: 836400
============================================================

[CALC] _resolve_costo_final:
  INPUT: unit_ars=1000, total_ars=10000, cant=10
  AMBOS PRESENTES -> Priorizar TOTAL: unit=1000.00, total=10000.00

[CALC] Precio aceptable (renta_minima * costo):
  renta_minima=1.3
  precio_unit_aceptable = 1.3 * 1000 = 1300.0
  precio_total_aceptable = 1.3 * 10000 = 13000.0

[CALC] Precio referencia unitario:
  precio_ref_unitario = _resolve_precio_ref_unitario(...) = 1500.0

[CALC] Rentabilidad referencia:
  renta_referencia = (1500.0 / 1000) - 1 = 50.00%

[CALC] Precio para mejorar:
  precio_unit_mejora = 12000 / 10 = 1200.0

[CALC] Rentabilidad para mejorar:
  renta_para_mejorar = (1200.0 / 1000) - 1 = 20.00%

[CALC] Utilidad porcentual (CRÍTICO para coloración):
  base_cost = 1000.0 (costo_subtotal=None o costo_unit_ars=1000)
  oferta_min_val = 12000
  utilidad_pct = ((12000 - 1000) / 1000) * 100 = 1100.00%

[DECISION] AlertEngine.decide:
  tracked=True, oferta_mia=False
  utilidad_pct=1100.00%, utilidad_min_pct=10.00%
  ocultar_bajo_umbral=False, changed=True
  RESULTADO: style=success, hide=False, highlight=True
  mensaje='✓ Utilidad 1100.00% (excelente, +1090.00%)'
============================================================
```

## 🐛 BUG CRÍTICO CORREGIDO: Tooltips Desincronizados

### Problema Anterior:
Cuando se ocultaban columnas, los tooltips mostraban información incorrecta porque la detección de columna por posición X fallaba.

### Solución Implementada:
```python
# ANTES (INCORRECTO):
col_idx = int(col_id.replace('#', '')) - 1
col = self.config.columns[col_idx]  # ❌ Asume orden original

# DESPUÉS (CORRECTO):
display_cols = self.tree.cget('displaycolumns')
if display_cols == '#all':
    col = self.config.columns[col_idx]  # ✅ Orden original
else:
    col = display_cols[col_idx]  # ✅ Orden con columnas ocultas/reordenadas
```

**Ubicación:** `app/ui/table_manager.py` método `_on_tree_motion`

## ✅ TESTING RECOMENDADO

Para verificar que los cálculos son correctos:

1. **Ejecutar la aplicación con logging:**
   ```bash
   python main.py --mode MOCK --scenario data/test_scenarios/scenario_controlled_real.json
   ```

2. **Editar un renglón** desde la UI
3. **Observar en la terminal** todos los cálculos paso a paso
4. **Verificar manualmente** con calculadora que las fórmulas sean correctas

## 📝 ARCHIVOS MODIFICADOS

| Archivo | Cambios |
|---------|---------|
| `app/core/engine.py` | +50 líneas: Logging detallado de TODOS los cálculos |
| `app/ui/table_manager.py` | Corrección crítica: detección correcta de columna para tooltips |

## ⚠️ NOTAS IMPORTANTES

1. **Prioridad en bidireccionalidad:** El sistema SIEMPRE prioriza `costo_total_ars` si ambos valores están presentes
2. **División por cero:** Todos los cálculos usan `_safe_div` que retorna None si el divisor es 0
3. **Multiplicación segura:** Todos los productos usan `_safe_mul` que retorna None si algún operando es None
4. **Logging NO afecta performance:** Los prints van a stdout, no hay overhead significativo

## 🚨 SI UN CÁLCULO ESTÁ INCORRECTO

1. Ejecutar la app y reproducir el caso
2. Capturar el output de la terminal con todos los logs
3. Verificar paso a paso cada cálculo contra este documento
4. Reportar el cálculo específico que está fallando con datos de entrada/salida esperada
