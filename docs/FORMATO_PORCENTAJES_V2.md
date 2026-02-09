# 📐 NUEVO FORMATO: Porcentajes como Fracciones (0-1)

## 🎯 Cambio Implementado

Hemos eliminado la ambigüedad de los porcentajes cambiando el formato de almacenamiento:

### Antes (Multiplicadores - AMBIGUO ❌)
```
BD:      1.1, 1.3, 2.0, 11.0
Fórmula: precio = renta_minima * costo
Ejemplo: precio = 1.3 * 1,000,000 = 1,300,000

Problemas:
- ¿1.3 es 30% o 130%? 🤔
- ¿11.0 es 1000% o 11%? 🤔
- Ambiguo al usar fórmulas en Excel
```

### Ahora (Fracciones - CLARO ✅)
```
BD:      0.1, 0.3, 1.0, 10.0
Fórmula: precio = (1 + renta_minima) * costo
Ejemplo: precio = (1 + 0.3) * 1,000,000 = 1,300,000

Ventajas:
- 0.3 siempre es 30% ✅
- 10.0 siempre es 1000% ✅
- Estándar matemático (fracción entre 0 y 1)
- Fórmula explícita y clara
```

---

## 📊 Tabla de Conversión

| Margen Deseado | BD (fracción) | Excel muestra | Fórmula de Precio |
|----------------|---------------|---------------|-------------------|
| 10%            | 0.10          | 10            | (1 + 0.10) × costo |
| 15%            | 0.15          | 15            | (1 + 0.15) × costo |
| 30%            | 0.30          | 30            | (1 + 0.30) × costo |
| 50%            | 0.50          | 50            | (1 + 0.50) × costo |
| 100%           | 1.0           | 100           | (1 + 1.0) × costo  |
| 1000%          | 10.0          | 1000          | (1 + 10.0) × costo |

---

## 🔄 Flujo Completo

### 1. Usuario Ingresa en UI
```
Usuario escribe: "30" (quiere 30% de margen)
↓
Sistema interpreta: >= 1.0 → es porcentaje
↓
Sistema guarda en BD: 30 / 100 = 0.30
```

### 2. Sistema Calcula
```
Costo: $1,000,000
Renta mínima: 0.30 (30%)
↓
Precio aceptable = (1 + 0.30) × 1,000,000
                 = 1.30 × 1,000,000
                 = $1,300,000
```

### 3. Exportar a Excel
```
BD: 0.30
↓
Fórmula export: 0.30 × 100 = 30
↓
Excel muestra: 30 (usuario lo lee como 30%)
```

### 4. Importar desde Excel
```
Excel: 30
↓
Sistema detecta: >= 1.0 → es porcentaje
↓
Convierte: 30 / 100 = 0.30
↓
Guarda en BD: 0.30
```

---

## 💻 Uso en la Aplicación

### Editar Renglón (UI)
1. Click derecho en renglón → "Editar Renglón"
2. Campo "Renta Mínima Aceptable (%)": escribe `30`
3. Sistema guarda: `0.30` en BD
4. Cálculos automáticos usan: `(1 + 0.30) × costo`

### Excel Export/Import
1. **Exportar**: ⚙️ Opciones → Exportar Excel
   - Columna "RENTA MINIMA %" muestra: `10`, `30`, `100` (números simples)
2. **Editar en Excel**: Cambia `30` a `15`
3. **Importar**: ⚙️ Opciones → Importar Excel
   - Sistema convierte `15` → `0.15` automáticamente
   - UI se actualiza con nuevo margen

---

## 🧮 Ejemplos de Cálculo

### Ejemplo 1: Costo $500,000 con 15% margen
```
Datos:
- Costo unit ARS: $500,000
- Renta mínima: 15% → BD guarda 0.15

Cálculo:
precio_unit_aceptable = (1 + 0.15) × 500,000
                      = 1.15 × 500,000
                      = $575,000

Resultado: $575,000 (precio mínimo para aceptar)
```

### Ejemplo 2: Costo $2M con 30% margen
```
Datos:
- Costo total ARS: $2,000,000
- Renta mínima: 30% → BD guarda 0.30

Cálculo:
precio_total_aceptable = (1 + 0.30) × 2,000,000
                       = 1.30 × 2,000,000
                       = $2,600,000

Resultado: $2,600,000 (precio mínimo para aceptar)
```

### Ejemplo 3: Comparación Antes vs Ahora

**Caso: 30% de margen sobre $1M**

| Aspecto | Formato VIEJO | Formato NUEVO |
|---------|---------------|---------------|
| **Almacenamiento** | 1.3 (multiplicador) | 0.3 (fracción) |
| **Interpretación** | ¿30% o 130%? 🤔 | Siempre 30% ✅ |
| **Fórmula** | `1.3 × costo` | `(1 + 0.3) × costo` |
| **Resultado** | $1,300,000 | $1,300,000 |
| **Claridad** | Ambiguo ❌ | Explícito ✅ |

---

## 🔧 Archivos Modificados

Los cambios se aplicaron en:

1. **app/core/engine.py** (líneas ~527-614)
   - Fórmulas: `precio = (1 + renta_minima) * costo`
   - Umbral alertas: `utilidad_min_pct = renta_minima * 100`

2. **app/db/database.py** (línea ~318)
   - Export: `renta_minima * 100` → porcentaje para Excel

3. **app/core/app_runtime.py** (líneas ~217-257)
   - Import: `valor / 100` → fracción para BD

4. **app/ui/row_editor.py** (líneas ~57-450)
   - Display: `renta * 100` → muestra como porcentaje
   - Input: `valor / 100` → guarda como fracción
   - Validación: `>= 0` (antes era `>= 1.0`)

5. **app/ui/app.py** (líneas ~336-343)
   - Filtro "Solo en carrera": compara fracciones directamente

---

## ✅ Validación

Ejecuta el test para verificar:
```bash
python tests/test_renta_format_v2.py
```

**Resultados esperados**:
- ✅ Export: 0.10 → 10%, 0.30 → 30%, 1.0 → 100%
- ✅ Import: 10 → 0.10, 30 → 0.30, 100 → 1.0
- ✅ Fórmulas: `(1 + 0.30) × 1M = 1.3M`
- ✅ Roundtrip: 0.30 → 30% → 0.30

---

## 📋 Migración de Datos Existentes

Si tienes datos con formato viejo (multiplicadores):

```sql
-- Ver datos actuales
SELECT id, renta_minima FROM renglon_excel WHERE renta_minima IS NOT NULL;

-- Migrar multiplicadores a fracciones
UPDATE renglon_excel 
SET renta_minima = renta_minima - 1.0 
WHERE renta_minima >= 1.0;

-- Ejemplo: 1.3 → 0.3, 1.15 → 0.15, 2.0 → 1.0
```

**⚠️ IMPORTANTE**: Hacer backup antes de migrar.

---

## 🎓 Preguntas Frecuentes

### ¿Por qué no usar multiplicadores directamente?
Porque `1.3` puede interpretarse como:
- 130% (valor absoluto)
- 30% de margen (1 + 0.30)
- Ambiguos al usar fórmulas de Excel

### ¿Por qué fracciones y no porcentajes enteros?
- Estándar matemático universal
- Más fácil para cálculos: `(1 + fracción) × base`
- Compatible con display: `fracción × 100 = porcentaje`

### ¿Qué pasa si escribo 0.30 en la UI?
El sistema detecta que es < 1.0 y lo guarda directamente como 0.30 (30%).

### ¿Puedo usar decimales como 15.5%?
Sí:
- UI: escribes `15.5`
- BD: guarda `0.155`
- Excel: muestra `15.5`
- Cálculo: `(1 + 0.155) × costo`

---

## 🚀 Ventajas

1. **Sin ambigüedad**: 0.3 siempre significa 30%
2. **Estándar matemático**: Fracción entre 0 y 1
3. **Fórmula explícita**: `(1 + margen) × costo`
4. **Excel coherente**: Muestra números simples (10, 30, 100)
5. **Migración suave**: Detecta formato automáticamente

---

## 📞 Soporte

Si encuentras problemas:
1. Verifica con `tests/test_renta_format_v2.py`
2. Revisa logs de conversión en consola
3. Exporta e importa para validar roundtrip
