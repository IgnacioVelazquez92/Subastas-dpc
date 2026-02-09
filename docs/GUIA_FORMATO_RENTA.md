# 📋 Guía de Formato: RENTA MINIMA % en Excel

## Cómo interpretar y editar la columna "RENTA MINIMA %"

### ✅ Formato Correcto en Excel

Cuando exportas datos a Excel, la columna **RENTA MINIMA %** muestra el **porcentaje directo**:

| En UI configuras | Se guarda en BD | Aparece en Excel | Significado |
|------------------|-----------------|------------------|-------------|
| 10% de margen    | 1.1             | **10**           | 10% utilidad |
| 30% de margen    | 1.3             | **30**           | 30% utilidad |
| 100% de margen   | 2.0             | **100**          | 100% utilidad (duplicar) |
| 5% de margen     | 1.05            | **5**            | 5% utilidad |

### 📝 Cómo Editar en Excel

Simplemente escribe el **porcentaje de utilidad** que deseas:

- Para **10% de margen** → escribe: `10`
- Para **30% de margen** → escribe: `30`
- Para **50% de margen** → escribe: `50`

**NO agregues el símbolo %** - el sistema lo interpretará automáticamente.

### 🔄 Al Importar de Vuelta

El sistema detecta automáticamente si escribiste:
- **Valores > 2.0**: Se interpretan como **porcentaje** → se convierten a multiplicador
  - Ejemplo: `30` se convierte a `1.3` (30% margen)
- **Valores ≤ 2.0**: Se interpretan como **multiplicador directo**
  - Ejemplo: `1.3` se mantiene como `1.3` (30% margen)

### ⚠️ Casos Especiales

| Si escribes | Se interpreta como | Se guarda | Resultado |
|-------------|-------------------|-----------|-----------|
| 10          | 10% utilidad      | 1.1       | ✅ Correcto |
| 1.1         | Multiplicador 1.1 | 1.1       | ✅ Correcto (equivale a 10%) |
| 30          | 30% utilidad      | 1.3       | ✅ Correcto |
| 1.3         | Multiplicador 1.3 | 1.3       | ✅ Correcto (equivale a 30%) |
| 100         | 100% utilidad     | 2.0       | ✅ Correcto |
| 2.0         | Multiplicador 2.0 | 2.0       | ✅ Correcto (equivale a 100%) |
| 1000        | 1000% utilidad    | 11.0      | ⚠️ Válido pero extremo |

### 💡 Recomendaciones

1. **Usa números simples** en Excel: `10`, `15`, `20`, `30`, etc.
2. Si ves un valor como `1.1` en Excel (exportado incorrectamente en versiones antiguas), cámbialo a `10` para mayor claridad
3. Después de importar, **verifica los cálculos** en la UI para confirmar que se aplicaron correctamente
4. La UI se actualizará automáticamente después de importar

### 📊 Ejemplos Prácticos

#### Caso 1: Margen del 15%
```
1. Exportas → ves "15" en Excel
2. Cambias a "20" (quieres 20% ahora)
3. Importas → se guarda como 1.2
4. UI muestra "Renta mínima: 20%"
```

#### Caso 2: Error común (versión antigua)
```
1. Exportas con bug viejo → ves "1.1" en Excel
2. Corriges a "10" (más claro)
3. Importas → se guarda correctamente como 1.1
4. UI muestra "Renta mínima: 10%"
```

#### Caso 3: Roundtrip perfecto
```
1. Configuras 30% en UI → se guarda 1.3
2. Exportas → ves "30" en Excel
3. Reimportas sin cambios → vuelve a 1.3
4. ✅ Coherencia total
```

---

## 🔧 Solución al Bug Reportado

### Problema Anterior
```
Usuario configura: 10% en UI
Se exportaba:      1.1 (confuso)
Usuario veía:      "1,1" en Excel (con formato regional)
Al reimportar:     Se leía como "1" coma decimal = 1.0 
                   o se malinterpretaba → 1000%
```

### Solución Actual
```
Usuario configura: 10% en UI
Se exporta:        10 (claro)
Usuario ve:        "10" en Excel
Al reimportar:     Se detecta > 2.0 → convierte a 1.1
                   ✅ Funciona correctamente
```
