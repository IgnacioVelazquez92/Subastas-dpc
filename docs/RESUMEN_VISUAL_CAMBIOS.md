# 🎯 RESUMEN RÁPIDO: Cambios de Columnas

## 📊 Mapeo Visual: Viejo → Nuevo

```
VIEJO                           NUEVO (Columnas Mejoradas)
════════════════════════════════════════════════════════════════════════════════

ID SUBASTA        ───────→      ID SUBASTA        ✅ Sin cambio
ITEM              ───────→      ITEM              ✅ Sin cambio
DESCRIPCION       ───────→      DESCRIPCION       ✅ Sin cambio
QUANTITY          ───────→      CANTIDAD          ✅ Mismo en Excel
UNIDAD DE MEDIDA  ───────→      UNIDAD DE MEDIDA  ✅ Sin cambio
MARCA             ───────→      MARCA             ✅ Sin cambio
───────────────────────────────────────────────────────────────────────────
Observaciones     ───────→      OBS USUARIO       📝 Renombrado
CONVERSIÓN USD    ───────→      CONVERSIÓN USD    ✅ Sin cambio
───────────────────────────────────────────────────────────────────────────
[NEW]                   ───→    COSTO UNIT USD     ✨ NUEVA (fórmula)
[NEW]                   ───→    COSTO TOTAL USD    ✨ NUEVA (fórmula)
───────────────────────────────────────────────────────────────────────────
COSTO FINAL PESOS (ambiguo) ─→  COSTO UNIT ARS     📝 Renombrado + Claridad
SUBTOTAL COSTO PESOS    ───→    COSTO TOTAL ARS    📝 Renombrado + Claridad
───────────────────────────────────────────────────────────────────────────
RENTA (multiplicador) ──→        RENTA MINIMA %     📝 Renombrado + % claro
───────────────────────────────────────────────────────────────────────────
[NEW]                   ───→    PRECIO UNIT ACEPTABLE    ✨ NUEVA (fórmula)
[NEW]                   ───→    PRECIO TOTAL ACEPTABLE   ✨ NUEVA (fórmula)
───────────────────────────────────────────────────────────────────────────
Precio referencia       ───→    PRECIO DE REFERENCIA     ✅ Sin cambio
[NEW]                   ───→    PRECIO REF UNITARIO      ✨ NUEVA (fórmula)
RENTA/ REF              ───→    RENTA REFERENCIA %       📝 Renombrado + %
───────────────────────────────────────────────────────────────────────────
MEJOR OFERTA            ───→    MEJOR OFERTA ACTUAL      📝 Más claro
OFERTA PARA MEJORAR     ───→    OFERTA PARA MEJORAR      ✅ Sin cambio
P. UNIT MEJORA          ───→    PRECIO UNIT MEJORA       📝 Nombre completo
[NEW]                   ───→    RENTA PARA MEJORAR %     ✨ NUEVA (fórmula)
───────────────────────────────────────────────────────────────────────────
Obs / Cambio            ───→    OBS / CAMBIO             ✅ Sin cambio
───────────────────────────────────────────────────────────────────────────
[REMOVED]               ───→    [No mostrar]
dif unit                        (se calcula on-the-fly)   
Renta DPC                       → RENTA PARA MEJORAR %
P.UNIT MINIMO                   → PRECIO UNIT ACEPTABLE
SUBTOTAL                        → (cálculo interno)
```

---

## 🔑 Cambios Clave

### 1️⃣ **Claridad en Costos ARS**

| Concepto | Viejo | Nuevo | Por qué |
|----------|-------|-------|---------|
| Costo por unidad | `costo_final` | `COSTO UNIT ARS` | Ambiguo si es total o unitario |
| Costo total | `subtotal_costo` | `COSTO TOTAL ARS` | Muy genérico |

### 2️⃣ **Conversion a USD (Nuevas columnas)**

```
Usuario ingresa:
  CONVERSIÓN USD = 1000 (pesos por dólar)
  COSTO UNIT ARS = 500.000

Sistema calcula:
  COSTO UNIT USD = 500.000 / 1000 = 500 USD
  COSTO TOTAL USD = COSTO TOTAL ARS / CONVERSIÓN USD
```

### 3️⃣ **Rentabilidad Mínima (Mejora importante)**

**Viejo:** Usuario ingresa `RENTA = 1.3` (confuso: ¿1.3x o 30%?)

**Nuevo:** Usuario ingresa `RENTA MINIMA % = 30` (usuario dice: "quiero 30% de utilidad")

Sistema calcula:
- `PRECIO UNIT ACEPTABLE = COSTO UNIT ARS * 1.30` (costo + 30%)
- `PRECIO TOTAL ACEPTABLE = COSTO TOTAL ARS * 1.30`

### 4️⃣ **Análisis de Referencia (Nuevas columnas)**

```
Cuando Playwright trae PRECIO DE REFERENCIA de la subasta:

Sistema calcula:
  PRECIO REF UNITARIO = PRECIO DE REFERENCIA / CANTIDAD
  RENTA REFERENCIA % = (PRECIO REF UNITARIO / COSTO TOTAL ARS) - 1
  
Ejemplo:
  PRECIO DE REFERENCIA = 100.000
  CANTIDAD = 10
  COSTO TOTAL ARS = 50.000
  
  → PRECIO REF UNITARIO = 10.000
  → RENTA REFERENCIA % = (10.000 / 50.000) - 1 = 0.20 = 20%
```

### 5️⃣ **Análisis de Mejora (Mejor claridad)**

**Viejo confuso:**
```
P. UNIT MEJORA     = ???  (¿mejora qué cosa?)
dif unit           = ???  (¿diferencia de qué?)
Renta DPC          = ???  (¿qué es DPC?)
SUBTOTAL PARA MEJORAR = OFERTA PARA MEJORAR (¿por qué dos nombres?)
```

**Nuevo, claro:**
```
PRECIO UNIT MEJORA = OFERTA PARA MEJORAR / CANTIDAD
RENTA PARA MEJORAR % = (PRECIO UNIT MEJORA / COSTO TOTAL ARS) - 1

Ejemplo:
  OFERTA PARA MEJORAR = 11.000
  CANTIDAD = 10
  COSTO TOTAL ARS = 50.000
  
  → PRECIO UNIT MEJORA = 1.100
  → RENTA PARA MEJORAR % = (1.100 / 50.000) - 1 = -0.978 = ❌ PÉRDIDA 97.8%
```

---

## 🔄 **Caso Especial: Bidireccionalidad COSTO**

El usuario puede ingresar:

### Opción A: Solo COSTO UNIT ARS
```
Usuario ingresa:
  COSTO UNIT ARS = 100

Sistema calcula:
  COSTO TOTAL ARS = COSTO UNIT ARS × CANTIDAD
                  = 100 × 10
                  = 1.000
```

### Opción B: Solo COSTO TOTAL ARS
```
Usuario ingresa:
  COSTO TOTAL ARS = 1.000

Sistema calcula:
  COSTO UNIT ARS = COSTO TOTAL ARS / CANTIDAD
                 = 1.000 / 10
                 = 100
```

### Opción C: Ambos (conflicto)
```
Usuario ingresa:
  COSTO UNIT ARS = 100
  COSTO TOTAL ARS = 1.500  ← NO COINCIDE (100 × 10 = 1.000, no 1.500)

Sistema usa PRIORIDAD a TOTAL:
  COSTO UNIT ARS = 1.500 / 10 = 150  ← CORREGIDO
  COSTO TOTAL ARS = 1.500  ← MANTIENE
```

---

## 📋 Campos Eliminados (o Deprecados)

| Campo Viejo | Razón | Qué hacer |
|-------------|-------|-----------|
| `dif unit` | Poco claro, no se usa | Calcular on-the-fly si se necesita |
| `P.UNIT MINIMO` | Sustituido por `PRECIO UNIT ACEPTABLE` | Usar el nuevo nombre |
| `SUBTOTAL` | Ambiguo y no se usa | Usar `COSTO TOTAL ARS` |
| `Renta DPC` | Sustituido por `RENTA PARA MEJORAR %` | Usar el nuevo nombre |

---

## 💾 Base de Datos: Cambios

### Renombres en tabla `renglon_excel`:
```sql
obs               → obs_usuario
costo_final       → costo_unit_ars
subtotal_costo    → costo_total_ars
renta_ref         → renta_referencia
p_unit_mejora     → precio_unit_mejora
renta_dpc         → renta_para_mejorar  (deprecar)
```

### Nuevas columnas:
```sql
costo_unit_usd         (REAL)
costo_total_usd        (REAL)
renta_minima           (REAL)
precio_unit_aceptable  (REAL)
precio_total_aceptable (REAL)
precio_ref_unitario    (REAL)
```

---

## 📁 Archivos a Editar (EN ORDEN)

1. **`app/ui/table_manager.py`**
   - Actualizar `columns` tuple
   - Actualizar `column_labels` dict
   - Actualizar `column_widths` dict

2. **`app/ui/formatters.py`**
   - Actualizar `DisplayValues.build_row_values()` con nuevos fields en nuevo orden

3. **`app/excel/excel_io.py`**
   - Actualizar `COLUMNS` lista
   - Actualizar `USER_FIELDS`, `CALC_FIELDS`, `MONEY_COLS`, `PERCENT_COLS` sets
   - Actualizar `FORMULAS` dict
   - Actualizar `required` set en `import_excel_to_rows()`

4. **`app/core/app_runtime.py`**
   - Actualizar `import_excel()` → cambiar `row.get("...")` calls
   - Actualizar `update_renglon_excel()` signature

5. **`app/core/engine.py`**
   - Agregar método `_resolve_costo_final()` (bidireccionalidad)
   - Actualizar `_process_renglon()` para usar nuevos fields
   - Actualizar cálculos de rentas/precios

6. **`app/models/domain.py`**
   - Actualizar `UIRow` dataclass con nuevos fields

7. **`scripts/migrate_columns_v2.py` (NUEVO)**
   - Script para migrar BD (reversible)

---

## ⏱️ Timeframe

| Tarea | Tiempo |
|-------|--------|
| Actualizar 5 archivos Python | 2-3 horas |
| Implementar bidireccionalidad | 1-2 horas |
| Migrar BD | 30 min |
| Testing exhaustivo | 2-4 horas |
| **TOTAL** | **5.5 - 9.5 horas** |

---

## ✅ Validaciones Finales

Antes de commit, verificar:

- [ ] Tabla en UI muestra columnas nuevas en correcto orden
- [ ] Labels son claros y legibles
- [ ] Diálogo de "Configurar Columnas" muestra etiquetas nuevas
- [ ] Exportar Excel genera encabezados correctos
- [ ] Importar Excel detecta encabezados nuevos
- [ ] Fórmulas en Excel se recalculan correctamente
- [ ] Bidireccionalidad COSTO funciona (ambos sentidos)
- [ ] No hay errores en consola
- [ ] Datos viejos se migran sin pérdida

