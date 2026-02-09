# PLAN DE ACCIÓN: Refactorización de Columnas y Mejoras

## 📋 Resumen Ejecutivo

Migración de las columnas actuales a un new set con nombres más claros y mejor estructura. Los cambios afectan:
- **UI:** Nombres en tabla y diálogos
- **Excel:** Headers de import/export
- **BD:** Schemas y mappings
- **Lógica:** Fórmulas y cálculos

**Riesgos identificados:**
- Pérdida de compatibilidad con Excel antiguos (requiere migración manual o script)
- Necesidad de actualizar múltiples archivos en sincronía
- Caso especial: COSTO FINAL UNITARIO ↔ COSTO FINAL TOTAL (bidireccional)

---

## 🔄 MAPEO DE COLUMNAS ANTIGUO → NUEVO

### Columnas que MANTIENEN nombre/función:
| Antigua | Nueva | Fuente | Notas |
|---------|-------|--------|-------|
| id_subasta | ID SUBASTA | Playwright | ✅ Sin cambio |
| item | ITEM | Playwright | ✅ Sin cambio |
| desc | DESCRIPCION | Playwright | ✅ Sin cambio |
| unidad | UNIDAD DE MEDIDA | Usuario | ✅ Sin cambio |
| cantidad | CANTIDAD | Playwright | ✅ Sin cambio |
| marca | MARCA | Usuario | ✅ Sin cambio |
| obs | OBS USUARIO | Usuario | ⚠️ Renombrado |
| conv_usd | CONVERSIÓN USD | Usuario | ✅ Sin cambio semántico |

### Columnas NUEVAS (con fórmulas):
| Nombre | Tipo | Fórmula | Uso |
|--------|------|---------|-----|
| COSTO UNIT USD | Cálculo | = COSTO FINAL UNITARIO ARS / CONVERSIÓN USD | Analítica USD |
| COSTO TOTAL USD | Cálculo | = COSTO FINAL TOTAL ARS / CONVERSIÓN USD | Analítica USD |
| COSTO FINAL UNITARIO ARS | Usuario/Cálc | Bidireccional (ver caso especial) | Base para rentas |
| COSTO FINAL TOTAL ARS | Usuario/Cálc | Bidireccional (ver caso especial) | Principal |
| RENTA MINIMA ACEPTABLE | Usuario | N/A | Multiplicador (ej: 1.3 = 30%) |
| PRECIO UNIT ACEPTABLE | Cálculo | = COSTO FINAL UNITARIO ARS * RENTA MINIMA ACEPTABLE | Piso mínimo |
| PRECIO TOTAL ACEPTABLE | Cálculo | = COSTO FINAL TOTAL ARS * RENTA MINIMA ACEPTABLE | Piso mínimo |
| PRECIO DE REFERENCIA UNITARIO | Cálculo | = PRECIO DE REFERENCIA / CANTIDAD | Análisis |
| RENTA REFERENCIA | Cálculo | = (PRECIO DE REFERENCIA / COSTO FINAL TOTAL ARS) - 1 | Porcentaje |
| PRECIO UNITARIO MEJORA | Cálculo | = OFERTA PARA MEJORAR / CANTIDAD | Análisis |
| RENTA PARA MEJORAR | Cálculo | = (OFERTA PARA MEJORAR / COSTO FINAL TOTAL ARS) - 1 | Porcentaje |

### Columnas RENOMBRADAS (requiere cambio en BD):
| Antigua | Nueva | Impacto |
|---------|-------|---------|
| costo_final | **COSTO FINAL UNITARIO ARS** | ⚠️ Fue ambiguo |
| subtotal_costo | **COSTO FINAL TOTAL ARS** | ⚠️ Fue poco claro |
| obs_det | **Obs / Cambio** | ⚠️ Ahora más específico |
| renta_ref | **RENTA REFERENCIA** | ✅ Claridad |
| p_unit_mejora | **PRECIO UNITARIO MEJORA** | ✅ Paso a nombre completo |

### Columnas ELIMINADAS (opcionales, considerar deprecación):
- `p_unit_min` → Se reemplaza con **PRECIO UNIT ACEPTABLE** (más claridad)
- `subtotal` → Se reemplaza implícitamente (ya calculado)
- `dif_unit` → Cambiar a: **DIFERENCIA UNITARIA MEJORA** (más claro)

---

## 🎯 FASES DE IMPLEMENTACIÓN

### **FASE 1: Preparación (Sin cambios en producción)**
**Duración estimada: 1-2 horas**

#### 1.1 Actualizar mapeo interno en código
- [ ] Crear `ColumnMapping` dataclass con OLD → NEW mappings
- [ ] Archivo: `app/models/domain.py` o nuevo `app/core/column_mapping.py`
- **Objetivo:** Un único lugar donde documentar la relación

```python
@dataclass
class ColumnMapping:
    """Traduce entre nombres internos y nombres de UI/Excel"""
    internal_name: str      # ej: "costo_final"
    ui_label: str          # ej: "COSTO FINAL UNITARIO ARS"
    excel_header: str      # Mismo que UI
    source: str            # "usuario" | "playwright" | "calculo"
    formula: Optional[str] # La fórmula si aplica
```

#### 1.2 Crear tabla de migración en BD
```sql
-- Nueva tabla para mapear IDs antiguos → nuevos
CREATE TABLE IF NOT EXISTS column_mapping (
    id INTEGER PRIMARY KEY,
    old_name TEXT,
    new_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

### **FASE 2: Actualizar UI (Table Columns)**
**Duración estimada: 2-3 horas**

#### 2.1 Actualizar `TableConfig.columns` ordenado
**Archivo:** [app/ui/table_manager.py](app/ui/table_manager.py#L22)

Cambiar de:
```python
columns: tuple[str, ...] = (
    "id_subasta", "item", "desc", ..., "obs_det",
)
```

A:
```python
columns: tuple[str, ...] = (
    # IDs y basicos (Playwright)
    "id_subasta", "item", "desc", "cantidad",
    # Metadata usuario
    "unidad_medida", "marca", "obs_usuario",
    # Costos (el núcleo)
    "conv_usd", "costo_unit_usd", "costo_total_usd",
    "costo_unit_ars", "costo_total_ars",
    # Rentabilidad mínima aceptable
    "renta_minima", "precio_unit_aceptable", "precio_total_aceptable",
    # Referencia
    "precio_referencia", "precio_ref_unitario", "renta_referencia",
    # Mejora en subasta
    "mejor_oferta", "oferta_para_mejorar",
    "precio_unit_mejora", "renta_para_mejorar",
    # Observaciones y cambios
    "obs_cambio",
)
```

#### 2.2 Actualizar `TableConfig.column_labels`
```python
column_labels: dict[str, str] = {
    "id_subasta": "ID SUBASTA",
    "item": "ITEM",
    "desc": "DESCRIPCION",
    ...
    "costo_unit_ars": "COSTO UNIT ARS",
    "costo_total_ars": "COSTO TOTAL ARS",
    "renta_minima": "RENTA MINIMA %",
    ...
}
```

#### 2.3 Actualizar `TableConfig.column_widths`
Dar anchos apropiados para nuevas columnas.

#### 2.4 Actualizar `DisplayValues.build_row_values()`
**Archivo:** [app/ui/formatters.py](app/ui/formatters.py#L55)

Cambiar el orden y cantidad de tuplas para que coincida con `columns`.

---

### **FASE 3: Actualizar Excel Import/Export**
**Duración estimada: 2-3 horas**

#### 3.1 Actualizar `COLUMNS` lista
**Archivo:** [app/excel/excel_io.py](app/excel/excel_io.py#L15)

```python
COLUMNS = [
    "ID SUBASTA",
    "ITEM",
    "DESCRIPCION",
    "UNIDAD DE MEDIDA",
    "CANTIDAD",
    "MARCA",
    "OBS USUARIO",
    "CONVERSIÓN USD",
    "COSTO UNIT USD",         # ← NUEVA
    "COSTO TOTAL USD",        # ← NUEVA
    "COSTO UNIT ARS",         # ← RENAMED
    "COSTO TOTAL ARS",        # ← RENAMED
    "RENTA MINIMA %",         # ← NUEVA
    "PRECIO UNIT ACEPTABLE",  # ← NUEVA
    "PRECIO TOTAL ACEPTABLE", # ← NUEVA
    "PRECIO DE REFERENCIA",
    "PRECIO REF UNITARIO",    # ← NUEVA
    "RENTA REFERENCIA %",     # ← RENAMED
    "MEJOR OFERTA ACTUAL",
    "OFERTA PARA MEJORAR",
    "PRECIO UNIT MEJORA",     # ← RENAMED
    "RENTA PARA MEJORAR %",   # ← NUEVA
    "OBS / CAMBIO",           # ← RENAMED
]
```

#### 3.2 Actualizar conjuntos de campos
```python
USER_FIELDS = {
    "UNIDAD DE MEDIDA",
    "MARCA",
    "OBS USUARIO",  # ← RENAMED
    "CONVERSIÓN USD",
    "COSTO UNIT ARS",         # ← RENAMED
    "COSTO TOTAL ARS",        # ← RENAMED
    "RENTA MINIMA %",         # ← NUEVA
}

CALC_FIELDS = {
    "COSTO UNIT USD",
    "COSTO TOTAL USD",
    "PRECIO UNIT ACEPTABLE",
    "PRECIO TOTAL ACEPTABLE",
    "PRECIO REF UNITARIO",
    "RENTA REFERENCIA %",
    "PRECIO UNIT MEJORA",
    "RENTA PARA MEJORAR %",
}

MONEY_COLS = {
    "COSTO UNIT USD",
    "COSTO TOTAL USD",
    "COSTO UNIT ARS",
    "COSTO TOTAL ARS",
    "PRECIO UNIT ACEPTABLE",
    "PRECIO TOTAL ACEPTABLE",
    "PRECIO DE REFERENCIA",
    "PRECIO REF UNITARIO",
    "PRECIO UNIT MEJORA",
}

PERCENT_COLS = {
    "RENTA MINIMA %",
    "RENTA REFERENCIA %",
    "RENTA PARA MEJORAR %",
}
```

#### 3.3 Actualizar REQUIRED en import
```python
required = {
    "ID SUBASTA",
    "ITEM",
    "UNIDAD DE MEDIDA",
    "MARCA",
    "OBS USUARIO",           # ← RENAMED
    "CONVERSIÓN USD",
    "COSTO UNIT ARS",        # ← RENAMED
    "COSTO TOTAL ARS",       # ← RENAMED
    "RENTA MINIMA %",        # ← NUEVA (si es obligatoria)
}
```

#### 3.4 Actualizar FORMULAS
```python
FORMULAS = {
    "COSTO UNIT USD": "=[@[COSTO UNIT ARS]]/[@[CONVERSIÓN USD]]",
    "COSTO TOTAL USD": "=[@[COSTO TOTAL ARS]]/[@[CONVERSIÓN USD]]",
    "PRECIO UNIT ACEPTABLE": "=[@[COSTO UNIT ARS]]*[@[RENTA MINIMA %]]",
    "PRECIO TOTAL ACEPTABLE": "=[@[COSTO TOTAL ARS]]*[@[RENTA MINIMA %]]",
    "PRECIO REF UNITARIO": "=[@[PRECIO DE REFERENCIA]]/[@[CANTIDAD]]",
    "RENTA REFERENCIA %": "=([@[PRECIO DE REFERENCIA]]/[@[COSTO TOTAL ARS]])-1",
    "PRECIO UNIT MEJORA": "=[@[OFERTA PARA MEJORAR]]/[@[CANTIDAD]]",
    "RENTA PARA MEJORAR %": "=([@[OFERTA PARA MEJORAR]]/[@[COSTO TOTAL ARS]])-1",
}
```

#### 3.5 Actualizar AppRuntime.import_excel()
**Archivo:** [app/core/app_runtime.py](app/core/app_runtime.py#L196)

Cambiar los `row.get("...")` para que usen nuevos nombres.

---

### **FASE 4: Actualizar Lógica de Cálculos (Engine)**
**Duración estimada: 2-4 horas**

#### 4.1 Implementar bidireccionalidad: COSTO UNIT ARS ↔ COSTO TOTAL ARS
**Archivo:** [app/core/engine.py](app/core/engine.py#L327)

**Caso especial:** El usuario puede ingresar:
1. Solo **COSTO UNIT ARS** → calcular COSTO TOTAL ARS = UNIT * CANTIDAD
2. Solo **COSTO TOTAL ARS** → calcular COSTO UNIT ARS = TOTAL / CANTIDAD
3. Ambos → prioridad a **COSTO TOTAL ARS** (el más fundamental)

Pseudocódigo:
```python
def _resolve_costo_final(
    unit: float | None,
    total: float | None,
    cantidad: float | None,
) -> tuple[float | None, float | None]:
    """
    Resuelve el par unit/total de forma bidireccional.
    Prioridad: total > unit
    """
    # Si ambos presentes, validar consistencia
    if unit and total and cantidad:
        expected_total = unit * cantidad
        if abs(expected_total - total) > 0.01:
            # User override: prioridad a TOTAL
            return (total / cantidad, total)
        return (unit, total)
    
    # Si solo uno: calcular el otro
    if total and cantidad:
        return (total / cantidad, total)
    if unit and cantidad:
        return (unit, unit * cantidad)
    
    return (unit, total)
```

#### 4.2 Actualizar paso a `DisplayValues.build_row_values()`
Asegurar que los nuevos names mapeen correctamente a los campos en `UIRow`.

#### 4.3 Revisar y actualizar reglas de rentabilidad mínima
Cambiar `renta` (multiplicador simple) a `renta_minima` (con descripción %).

---

### **FASE 5: Actualizar Base de Datos**
**Duración estimada: 1-2 horas**

#### 5.1 Crear script de migración (REVERSIBLE)

**Archivo nuevo:** `scripts/migrate_columns_v2.py`

```python
"""
Migración de columnas: vieja estructura → nueva estructura.
REVERSIBLE: genera backup antes de aplicar cambios.
"""

def migrate_up():
    """Renombra columnas en BD"""
    # 1. Backup
    # 2. ALTER TABLE renglon_excel RENAME COLUMN obs TO obs_usuario;
    # 3. ALTER TABLE renglon_excel RENAME COLUMN costo_final TO costo_unit_ars;
    # 4. ALTER TABLE renglon_excel ADD COLUMN costo_total_ars REAL;
    # ... etc
    
def migrate_down():
    """Revert a estructura antigua"""
    # Inverso de migrate_up
```

#### 5.2 Agregar nuevas columnas a DB (si no existen)
- `costo_unit_usd` (REAL)
- `costo_total_usd` (REAL)
- `renta_minima` (REAL)
- `precio_unit_aceptable` (REAL)
- `precio_total_aceptable` (REAL)
- `precio_ref_unitario` (REAL)
- `renta_para_mejorar` (REAL)

#### 5.3 Actualizar `Database._ensure_columns()`
Verificar que todas estas nuevas columnas existan.

---

### **FASE 6: Testing & Integración**
**Duración estimada: 2-4 horas**

#### 6.1 Tests unitarios
- [ ] `test_costo_bidireccional()` → UNIT ↔ TOTAL
- [ ] `test_excel_export_headers()` → Headers correctos
- [ ] `test_excel_import_required()` → Valida requeridos nuevos
- [ ] `test_formulas_excel()` → Fórmulas recalculan bien

#### 6.2 Test de integración end-to-end
- [ ] Importar Excel con NUEVO formato
- [ ] Verificar que tabla muestre columnas nuevas
- [ ] Verificar que fórmulas se calculen
- [ ] Exportar y comparar

#### 6.3 Test de compatibilidad hacia atrás
- [ ] ¿Qué ocurre si se importa Excel ANTIGUO?
- [ ] Ofrecer migración automática o error claro

---

## 📊 DIAGRAMA DE DEPENDENCIAS

```
TableManager.columns ──────→ DisplayValues.build_row_values()
       ↓
 column_labels ──→ ColumnManager (UI labels)
       ↓
   Excel COLUMNS ──────→ export_subasta_to_excel()
       ↓                      ↓
  FORMULAS ──────────────→ import_excel_to_rows()
       ↓
   Engine ───→ UIRow generation ──→ Treeview render
```

---

## ⚠️ RIESGOS Y MITIGACIÓN

| Riesgo | Impacto | Mitigación |
|--------|--------|-----------|
| **Pérdida de Excel antiguos** | Alto | Crear script de conversión o advertencia clara |
| **Inconsistencia nombres** | Medio | Una ÚNICA fuente de verdad (ColumnMapping) |
| **Bidireccionalidad COSTO** | Medio | Tests unitarios estrictos |
| **Fórmulas rotas en Excel** | Medio | Validar fórmulas antes de guardar |
| **Usuarios con datos en BD** | Alto | Migración reversible con backup automático |

---

## 📅 CRONOGRAMA ESTIMADO

| Fase | Estimado | Duración Total |
|------|----------|----------------|
| 1. Preparación | 1.5h | 1.5h |
| 2. UI | 2.5h | 4h |
| 3. Excel | 2.5h | 6.5h |
| 4. Engine | 3h | 9.5h |
| 5. BD | 1.5h | 11h |
| 6. Testing | 3h | 14h |

**Total: ~14 horas de trabajo**

---

## 🎬 PRÓXIMOS PASOS

1. **Confirmar cambios** en `COMULMNAS.TXT`
2. **Crear ColumnMapping** (centralizar mapeos)
3. **Ejecutar Fase 1** → Preparación
4. **Ejecutar Fases 2-3** en paralelo → UI + Excel
5. **Ejecutar Fases 4-5** → Engine + BD
6. **Testing exhaustivo** → Fase 6
7. **Migración de datos existentes** (si aplica)
