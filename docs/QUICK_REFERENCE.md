# ⚡ QUICK REFERENCE: Cambios de Columnas (Tarjeta de Bolsillo)

## 🎯 Los 5 Cambios Principales

```
1. CLARIDAD EN COSTOS ARS
   "costo_final" → "costo_unit_ars"
   "subtotal_costo" → "costo_total_ars"
   WHY: Ambiguo → Claro

2. CONVERSIÓN A USD (NUEVAS)
   "costo_unit_usd" = costo_unit_ars / conversión_usd
   "costo_total_usd" = costo_total_ars / conversión_usd
   WHY: Análisis internacional

3. RENTABILIDAD MÍNIMA CLARA
   "renta" → "renta_minima" (en %)
   "precio_unit_aceptable" = costo_unit_ars * renta_minima
   "precio_total_aceptable" = costo_total_ars * renta_minima
   WHY: Usuario dice "quiero 30%", no "1.3x"

4. ANÁLISIS DE REFERENCIA (NUEVAS)
   "precio_ref_unitario" = precio_referencia / cantidad
   "renta_referencia" = (precio_ref_unitario / costo_total_ars) - 1
   WHY: Entender qué pide el cliente

5. MEJORA EN SUBASTA (MEJOR NOMBRE)
   "p_unit_mejora" → "precio_unit_mejora"
   "renta_dpc" → "renta_para_mejorar"
   "renta_para_mejorar" = (precio_unit_mejora / costo_total_ars) - 1
   WHY: Nombres más claros
```

---

## 📁 Arquivos a Editar (Copy-Paste Ready)

### 1️⃣ `app/ui/table_manager.py`

**Line 22-27:** Actualizar `columns`
```python
# ANTES: 22 columnas, nombres confusos
# DESPUES: 23 columnas, nombres claros
# Cambio: Orden nuevo, nombres nuevos
# Tiempo: 2 min
```

**Line 35-55:** Actualizar `column_labels`
```python
# CAMBIOS:
"obs" → "obs_usuario": "OBS USUARIO"
"costo_final" → "costo_unit_ars": "COSTO UNIT ARS"
"subtotal_costo" → "costo_total_ars": "COSTO TOTAL ARS"
+ ADD nuevas etiquetas (10 nuevos)
# Tiempo: 3 min
```

**Line 62-75:** Actualizar `column_widths`
```python
# CAMBIOS: Actualizar widths para nuevas columnas
# Agregar entries para 10 nodos nuevos
# Tiempo: 2 min
```

---

### 2️⃣ `app/excel/excel_io.py`

**Line 15:** Actualizar `COLUMNS`
```python
# CAMBIOS:
COLUMNS[7]: "Observaciones" → "OBS USUARIO"
+ INSERT al inicio de "COSTO UNIT USD", "COSTO TOTAL USD"
+ RENAME "COSTO FINAL PESOS" → "COSTO UNIT ARS", etc
+ ADD 7 nuevas al final
# Total: 15 columnas → 23 columnas
# Tiempo: 3 min
```

**Line 37-51:** Actualizar `USER_FIELDS`, `CALC_FIELDS`, etc
```python
# USER_FIELDS: cambiar 3, agregar 2
# CALC_FIELDS: cambiar 8
# MONEY_COLS: cambiar 4, agregar 2
# PERCENT_COLS: cambiar 2, agregar 1
# Tiempo: 4 min
```

**Line 72:** Actualizar `FORMULAS`
```python
# CAMBIOS: 8 fórmulas existentes → renombradas
# + 0 nuevas (se aplican en engine)
# Tiempo: 3 min
```

**Line 198:** Actualizar `required` en `import_excel_to_rows()`
```python
# CAMBIOS: Cambiar 3 nombres, agregar "RENTA MINIMA %"
# Tiempo: 1 min
```

---

### 3️⃣ `app/ui/formatters.py`

**Line 55-78:** Actualizar `DisplayValues.build_row_values()`
```python
# CAMBIOS: Tupla de 22 → 23 valores
# Cambiar orden de algunos
# Usar nuevos field names de UIRow
# Cambiar fmt calls para renombrados
# Tiempo: 5 min
```

---

### 4️⃣ `app/core/app_runtime.py`

**Line 123-150:** Actualizar `update_renglon_excel()`
```python
# CAMBIOS:
- Parámetros: cambiar 3 nombres, agregar 2
- Body: cambiar 3 row.get(...), agregar 1
# Tiempo: 3 min
```

**Line 196-250:** Actualizar `import_excel()`
```python
# CAMBIOS: En el loop de rows:
- row.get("Observaciones") → row.get("OBS USUARIO")
- row.get("COSTO FINAL PESOS") → row.get("COSTO UNIT ARS")
- row.get("RENTA") → row.get("RENTA MINIMA %")
+ Agregar 4 nuevas extracciones
# Tiempo: 3 min
```

---

### 5️⃣ `app/core/engine.py`

**Before Line 320:** Agregar nueva función
```python
def _resolve_costo_final(self, unit, total, cantidad):
    """Resuelve bidireccionalidad COSTO UNIT ↔ COSTO TOTAL"""
    # ~40 líneas
# Tiempo: 5 min
```

**Line 327-350:** Actualizar variable extraction
```python
# CAMBIOS:
- Reemplazar 9 variables antiguas
+ Agregar 10 nuevas variables
- Llamar _resolve_costo_final() para la bidireccionalidad
# Tiempo: 5 min
```

**Line 370-405:** Actualizar cálculos
```python
# CAMBIOS:
- Actualizar cálculos que usan costo_final → costo_unit_ars
- Actualizar cálculos que usan renta → renta_minima
+ Agregar cálculos para COSTO USD, PRECIOS ACEPTABLES, etc
# Tiempo: 10 min
```

---

### 6️⃣ `app/models/domain.py`

**UIRow dataclass:** Agregar nuevos campos
```python
# AGREGAR: 11 nuevos campos de tipo float | None
# CAMBIAR: 3 nombres de campos existentes
# Tiempo: 2 min
```

---

## 🔄 Bidireccionalidad COSTO (Lo más complejo)

```python
# PROBLEMA: Usuario puede ingresar UNIT o TOTAL o AMBOS
# SOLUCIÓN: Función resolver que:
#   - Si AMBOS: prioridad a TOTAL
#   - Si solo UNIT: calcular TOTAL = UNIT * CANTIDAD
#   - Si solo TOTAL: calcular UNIT = TOTAL / CANTIDAD
#   - Si NINGUNO: retornar (None, None)

# UBICACIÓN: Agregar en engine.py, línea ~320
# NOMBRE: _resolve_costo_final(unit, total, cantidad)
# RESULTADO: (costo_unit_ars, costo_total_ars)

# USO:
costo_unit_ars, costo_total_ars = self._resolve_costo_final(
    unit=excel.get("costo_unit_ars"),
    total=excel.get("costo_total_ars"),
    cantidad=cantidad,
)
```

---

## 📊 Checklist Ultra-Rápido

### Antes de empezar
- [ ] Cada cambio está documentado (ver CHECKLIST_CAMBIOS.md)
- [ ] Tengo backup de BD listo
- [ ] Git branch creado (ej: `feature/columns-v2`)

### Durante implementación (tabla_manager.py)
- [ ] `columns` tuple actualizado
- [ ] `column_labels` dict completado (todo matches con columns)
- [ ] `column_widths` dict completado
- [ ] Sin errores de sintaxis (python -m py_compile)

### Durante implementación (excel_io.py)
- [ ] `COLUMNS` lista tiene 23 elementos
- [ ] Todos en COLUMNS están en algún set (USER/CALC/OBS)
- [ ] `FORMULAS` keys coinciden con columnas que necesitan fórmulas (7 total)
- [ ] `required` set contiene headers obligatorios para import
- [ ] `_normalize_header()` sigue igual (no cambiar)

### Durante implementación (formatters.py)
- [ ] `build_row_values()` retorna 23 strings (mismo orden que columns)
- [ ] Todos los field names de UIRow existen
- [ ] Los tipos de formato son correctos (money, percentage, number, text)

### Durante implementación (app_runtime.py)
- [ ] `update_renglon_excel()` signature cambió (parámetros nuevos)
- [ ] `import_excel()` usa `row.get()` con nombres NUEVOS
- [ ] `_to_float()` helper sigue igual

### Durante implementación (engine.py)
- [ ] `_resolve_costo_final()` está agregada antes de `_process_renglon()`
- [ ] Variables en `_process_renglon()` usan nombres NUEVOS
- [ ] Bidireccionalidad se llama: `costo_unit_ars, costo_total_ars = self._resolve_costo_final(...)`
- [ ] Cálculos posteriores usan `costo_unit_ars` y `costo_total_ars` (no viejos nombres)

### Durante implementación (domain.py)
- [ ] `UIRow` dataclass tiene 23 campos (contarlos)
- [ ] Todos los nuevos campos son `| None = None`

### Después de implementación
- [ ] `python main.py` lanza sin errores
- [ ] UI muestra tabla con nuevas columnas
- [ ] Exportar Excel genera headers correctos
- [ ] Importar Excel detecta headers nuevos
- [ ] Fórmulas en Excel se recalculan

---

## 🚨 Errores Comunes a Evitar

```
❌ "AttributeError: UIRow has no attribute costo_unit_ars"
   → Olvidaste agregar campo en domain.py

❌ "ValueError: Faltan columnas requeridas: ['RENTA MINIMA %']"
   → Olvidaste actualizar 'required' set en excel_io.py

❌ "IndexError" al render tabla
   → `columns` tiene diferente cantidad que `build_row_values()` retorna
   → Contar: debe ser 23 en ambos

❌ Fórmulas rotas en Excel
   → Olvidaste actualizar claves en FORMULAS dict
   → Cambiar "COSTO FINAL PESOS" → "COSTO UNIT ARS" en fórmulas

❌ Bidireccionalidad no funciona
   → `_resolve_costo_final()` no se llamó en engine.py
   → O no usaste el resultado correcto

❌ Old Excel files don't import
   → No hay migración automática
   → Usuario debe renombrar headers manualmente
```

---

## ⏱️ Timeframe por Archivo

```
table_manager.py    ████ 7 min
excel_io.py         ████████ 11 min
formatters.py       █████ 5 min
app_runtime.py      ██████ 6 min
engine.py           ████████████ 20 min
domain.py           ██ 2 min
──────────────────────────────
TOTAL               ████████████████████████ 51 min
+ Testing           45-120 min
= TOTAL             2-3 horas
```

---

## 🎓 Si necesitas más detalle...

| Tema | Dónde leer |
|------|-----------|
| Qué cambios exactos | RESUMEN_VISUAL_CAMBIOS.md |
| Código ANTES/DESPUÉS | CHECKLIST_CAMBIOS.md |
| Estrategia completa | PLAN_CAMBIOS_COLUMNAS.md |
| Ejemplo completo | (Vídeo o demo futura) |

---

## 📝 Mi Checklist Personal (copiar y editar)

```
IMPLEMENTACIÓN DE CAMBIOS COLUMNAS v2

Dev: ________    Fecha: ________    Branch: feature/columns-v2

PREP:
  [ ] Backup de BD: ________________
  [ ] Git branch creado
  [ ] Entendí RESUMEN_VISUAL_CAMBIOS.md

TABLA (table_manager.py):
  [ ] Actualicé columns tuple (línea 22)
  [ ] Actualicé column_labels dict (línea 36)
  [ ] Actualicé column_widths dict (línea 62)
  [ ] Sin errores de sintaxis
  [ ] Git commit -m "refactor: update table_manager columns"

EXCEL (excel_io.py):
  [ ] Actualicé COLUMNS list (línea 15)
  [ ] Actualicé USER_FIELDS set
  [ ] Actualicé CALC_FIELDS set
  [ ] Actualicé MONEY_COLS set
  [ ] Actualicé PERCENT_COLS set
  [ ] Actualicé FORMULAS dict (línea 72)
  [ ] Actualicé required set (línea 198)
  [ ] Sin errores de sintaxis
  [ ] Git commit -m "refactor: update excel_io column definitions"

FORMATO (formatters.py):
  [ ] Actualicé build_row_values() (línea 55)
  [ ] Verifico: 23 valores en la tupla
  [ ] Sin errores de sintaxis
  [ ] Git commit -m "refactor: update DisplayValues for new columns"

RUNTIME (app_runtime.py):
  [ ] Actualicé update_renglon_excel() (línea 123)
  [ ] Actualicé import_excel() (línea 196)
  [ ] Sin errores de sintaxis
  [ ] Git commit -m "refactor: update app_runtime for new columns"

ENGINE (engine.py):
  [ ] Agregué _resolve_costo_final() (línea ~320)
  [ ] Actualicé variables en _process_renglon() (línea 327)
  [ ] Actualicé cálculos posteriores (línea 370)
  [ ] Sin errores de sintaxis
  [ ] Git commit -m "refactor: implement bidirectional costs and new calculations"

MODELO (domain.py):
  [ ] Agregué 11 nuevos campos a UIRow
  [ ] Cambié 3 nombres de campos existentes
  [ ] Sin errores de sintaxis
  [ ] Git commit -m "refactor: update UIRow dataclass schema"

TESTING:
  [ ] `python main.py` lanza sin errors
  [ ] Tabla muestra nuevas columnas
  [ ] Exportar Excel genera headers correctos
  [ ] Importar Excel detecta headers nuevos
  [ ] Bidireccionalidad COSTO funciona
  [ ] Sin crashes en logs
  [ ] Git commit -m "test: validate column refactor"

MERGE:
  [ ] Code review COMPLETADO
  [ ] Todos los tests PASSED
  [ ] BD migrada (script ejecutado)
  [ ] Usuarios notificados de cambios

FINALIZADO ✅
```

---

## 🔗 One-Liners para Git

```bash
# Crear branch
git checkout -b feature/columns-v2

# Commits por archivo
git add app/ui/table_manager.py
git commit -m "refactor: update table config for new column names"

git add app/excel/excel_io.py
git commit -m "refactor: update excel headers and formulas"

git add app/ui/formatters.py
git commit -m "refactor: update display values for new columns"

git add app/core/app_runtime.py
git commit -m "refactor: update runtime methods for new columns"

git add app/core/engine.py
git commit -m "refactor: implement bidirectional costs and new calculations"

git add app/models/domain.py
git commit -m "refactor: expand UIRow schema with new fields"

# Push
git push origin feature/columns-v2

# PR/MR (crear en GitHub/GitLab)
```

---

## 📱 Share This

**Imprime o comparte:** Esta tarjeta de referencia  
**Link a docs completas:** Ver INDICE_PLAN_COLUMNAS.md  
**Para emergencias:** Contacta al devel principal

---

**Última actualización:** 2026-02-08  
**Versión:** 1.0  
**Autor:** Plan de Refactorización Automático
