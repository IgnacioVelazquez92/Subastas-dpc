# ✅ CHECKLIST EJECUTIVO: Cambios por Archivo

## 📝 Resumen: 5 archivos principales afectados

```
app/ui/table_manager.py      ← Cambiar columns, labels, widths
app/excel/excel_io.py        ← Cambiar COLUMNS, formulas, validaciones
app/ui/formatters.py         ← Actualizar build_row_values()
app/core/app_runtime.py      ← Actualizar import_excel()
app/core/engine.py           ← Implementar bidireccionalidad COSTO
```

---

## 1️⃣ app/ui/table_manager.py

### ❌ ANTES (líneas 22-27)
```python
columns: tuple[str, ...] = (
    "id_subasta", "item", "desc", "unidad", "cantidad", "marca", "obs",
    "conv_usd", "costo_usd", "costo_final", "subtotal_costo",
    "renta", "p_unit_min", "subtotal", "renta_ref", "p_unit_mejora",
    "precio_ref_subasta", "mejor", "subtotal_mejorar", "dif_unit",
    "renta_dpc", "obs_det",
)
```

### ✅ DESPUÉS
```python
columns: tuple[str, ...] = (
    # IDs y básicos (Playwright)
    "id_subasta", "item", "desc", "cantidad",
    # Metadata usuario
    "unidad_medida", "marca", "obs_usuario",
    # Costos (bidireccionales)
    "conv_usd", "costo_unit_usd", "costo_total_usd",
    "costo_unit_ars", "costo_total_ars",
    # Rentabilidad mínima aceptable
    "renta_minima", "precio_unit_aceptable", "precio_total_aceptable",
    # Referencia de subasta
    "precio_referencia", "precio_ref_unitario", "renta_referencia",
    # Mejora en subasta
    "mejor_oferta", "oferta_para_mejorar",
    "precio_unit_mejora", "renta_para_mejorar",
    # Observaciones
    "obs_cambio",
)
```

### ❌ ANTES (column_labels, líneas 36-55)
```python
"id_subasta": "ID SUBASTA",
"item": "ITEM",
"desc": "DESCRIPCION",
"mejor": "Mejor oferta",
"precio_ref_subasta": "Precio ref. (subasta)",
"obs_det": "Obs / Cambio",
...
```

### ✅ DESPUÉS (column_labels, COMPLETE)
```python
column_labels: dict[str, str] = {
    "id_subasta": "ID SUBASTA",
    "item": "ITEM",
    "desc": "DESCRIPCION",
    "cantidad": "CANTIDAD",
    "unidad_medida": "UNIDAD DE MEDIDA",
    "marca": "MARCA",
    "obs_usuario": "OBS USUARIO",
    "conv_usd": "CONVERSIÓN USD",
    "costo_unit_usd": "COSTO UNIT USD",
    "costo_total_usd": "COSTO TOTAL USD",
    "costo_unit_ars": "COSTO UNIT ARS",
    "costo_total_ars": "COSTO TOTAL ARS",
    "renta_minima": "RENTA MINIMA %",
    "precio_unit_aceptable": "PRECIO UNIT ACEPTABLE",
    "precio_total_aceptable": "PRECIO TOTAL ACEPTABLE",
    "precio_referencia": "PRECIO DE REFERENCIA",
    "precio_ref_unitario": "PRECIO REF UNITARIO",
    "renta_referencia": "RENTA REFERENCIA %",
    "mejor_oferta": "MEJOR OFERTA ACTUAL",
    "oferta_para_mejorar": "OFERTA PARA MEJORAR",
    "precio_unit_mejora": "PRECIO UNIT MEJORA",
    "renta_para_mejorar": "RENTA PARA MEJORAR %",
    "obs_cambio": "OBS / CAMBIO",
}
```

### ❌ ANTES (column_widths, líneas 62-67)
```python
column_widths: dict[str, int] = {
    "id_subasta": 110, "item": 90, "desc": 260, "mejor": 140,
    "precio_ref_subasta": 140, "obs_det": 220, "unidad": 130,
    ...
}
```

### ✅ DESPUÉS (column_widths, COMPLETE)
```python
column_widths: dict[str, int] = {
    "id_subasta": 110,
    "item": 90,
    "desc": 260,
    "cantidad": 90,
    "unidad_medida": 130,
    "marca": 120,
    "obs_usuario": 200,
    "conv_usd": 120,
    "costo_unit_usd": 130,
    "costo_total_usd": 130,
    "costo_unit_ars": 130,
    "costo_total_ars": 130,
    "renta_minima": 110,
    "precio_unit_aceptable": 150,
    "precio_total_aceptable": 150,
    "precio_referencia": 140,
    "precio_ref_unitario": 140,
    "renta_referencia": 110,
    "mejor_oferta": 140,
    "oferta_para_mejorar": 150,
    "precio_unit_mejora": 140,
    "renta_para_mejorar": 110,
    "obs_cambio": 220,
}
```

---

## 2️⃣ app/excel/excel_io.py

### ❌ ANTES (COLUMNS, líneas 15-35)
```python
COLUMNS = [
    "ID SUBASTA",
    "ITEM",
    "DESCRIPCION",
    "UNIDAD DE MEDIDA",
    "CANTIDAD",
    "MARCA",
    "Observaciones",
    "CONVERSIÓN USD",
    "COSTO USD",
    "COSTO FINAL PESOS",
    ...
]
```

### ✅ DESPUÉS (COLUMNS)
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
    "COSTO UNIT USD",
    "COSTO TOTAL USD",
    "COSTO UNIT ARS",
    "COSTO TOTAL ARS",
    "RENTA MINIMA %",
    "PRECIO UNIT ACEPTABLE",
    "PRECIO TOTAL ACEPTABLE",
    "PRECIO DE REFERENCIA",
    "PRECIO REF UNITARIO",
    "RENTA REFERENCIA %",
    "MEJOR OFERTA ACTUAL",
    "OFERTA PARA MEJORAR",
    "PRECIO UNIT MEJORA",
    "RENTA PARA MEJORAR %",
    "OBS / CAMBIO",
]
```

### ❌ ANTES (USER_FIELDS, líneas ~37-43)
```python
USER_FIELDS = {
    "UNIDAD DE MEDIDA",
    "MARCA",
    "Observaciones",
    "CONVERSIÓN USD",
    "COSTO FINAL PESOS",
    "RENTA",
}
```

### ✅ DESPUÉS (USER_FIELDS)
```python
USER_FIELDS = {
    "UNIDAD DE MEDIDA",
    "MARCA",
    "OBS USUARIO",
    "CONVERSIÓN USD",
    "COSTO UNIT ARS",
    "COSTO TOTAL ARS",
    "RENTA MINIMA %",
}
```

### ❌ ANTES (CALC_FIELDS, líneas ~45-51)
```python
CALC_FIELDS = {
    "COSTO USD",
    "SUBTOTAL COSTO PESOS",
    "P.UNIT MINIMO",
    "SUBTOTAL",
    "RENTA/ REF",
    "P. UNIT MEJORA",
    "dif unit",
    "Renta DPC",
}
```

### ✅ DESPUÉS (CALC_FIELDS)
```python
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
```

### ❌ ANTES (MONEY_COLS, líneas ~53-62)
```python
MONEY_COLS = {
    "COSTO USD",
    "COSTO FINAL PESOS",
    "SUBTOTAL COSTO PESOS",
    "P.UNIT MINIMO",
    "SUBTOTAL",
    "Precio referencia",
    "P. UNIT MEJORA",
    "SUBTOTAL PARA MEJORAR",
    "dif unit",
}
```

### ✅ DESPUÉS (MONEY_COLS)
```python
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
    "OFERTA PARA MEJORAR",
}
```

### ❌ ANTES (PERCENT_COLS, líneas ~64-67)
```python
PERCENT_COLS = {
    "RENTA/ REF",
    "Renta DPC",
}
```

### ✅ DESPUÉS (PERCENT_COLS)
```python
PERCENT_COLS = {
    "RENTA MINIMA %",
    "RENTA REFERENCIA %",
    "RENTA PARA MEJORAR %",
}
```

### ❌ ANTES (FORMULAS, líneas ~72-82)
```python
FORMULAS = {
    "COSTO USD": "=[@[COSTO FINAL PESOS]]/[@[CONVERSIÓN USD]]",
    "SUBTOTAL COSTO PESOS": "=[@CANTIDAD]*[@[COSTO FINAL PESOS]]",
    "P.UNIT MINIMO": "=[@RENTA]*[@[COSTO FINAL PESOS]]",
    "SUBTOTAL": "=[@CANTIDAD]*[@[P.UNIT MINIMO]]",
    "RENTA/ REF": "=[@[Precio referencia]]/[@[COSTO FINAL PESOS]]-1",
    "P. UNIT MEJORA": "=[@[SUBTOTAL PARA MEJORAR]]/[@[CANTIDAD]]",
    "dif unit": "=[@[P. UNIT MEJORA]]-[@[COSTO FINAL PESOS]]",
    "Renta DPC": "=[@[P. UNIT MEJORA]]/[@[COSTO FINAL PESOS]]-1",
}
```

### ✅ DESPUÉS (FORMULAS)
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

### ❌ ANTES (required set en import_excel_to_rows(), líneas ~198-207)
```python
required = {
    "ID SUBASTA",
    "ITEM",
    "UNIDAD DE MEDIDA",
    "MARCA",
    "Observaciones",
    "CONVERSION USD",
    "COSTO FINAL PESOS",
    "RENTA",
}
```

### ✅ DESPUÉS (required set)
```python
required = {
    "ID SUBASTA",
    "ITEM",
    "UNIDAD DE MEDIDA",
    "MARCA",
    "OBS USUARIO",
    "CONVERSIÓN USD",
    "COSTO UNIT ARS",
    "COSTO TOTAL ARS",
    "RENTA MINIMA %",
}
```

---

## 3️⃣ app/ui/formatters.py

### ❌ ANTES (build_row_values, líneas ~72-93)
```python
values = (
    row.id_subasta or "",
    row.id_renglon,
    fmt.truncate(row.desc, 80),
    row.unidad_medida or "",
    fmt.format_number(row.cantidad, decimals=2),
    row.marca or "",
    fmt.truncate(row.observaciones or "", 40),
    fmt.format_number(row.conversion_usd, decimals=2),
    fmt.format_number(row.costo_usd, decimals=2),
    fmt.format_money(row.costo_final_pesos),
    fmt.format_money(row.subtotal_costo_pesos),
    fmt.format_number(row.renta, decimals=4),
    fmt.format_money(row.p_unit_minimo),
    fmt.format_money(row.subtotal),
    fmt.format_percentage(row.renta_ref) if row.renta_ref is not None else "",
    fmt.format_money(row.p_unit_mejora),
    fmt.format_money(row.precio_ref_subasta),
    row.mejor_txt or "",
    fmt.format_money(row.subtotal_para_mejorar),
    fmt.format_money(row.dif_unit),
    fmt.format_percentage(row.renta_dpc) if row.renta_dpc is not None else "",
    fmt.truncate(row.obs_det or "", 60),
)
```

### ✅ DESPUÉS (build_row_values)
```python
values = (
    # IDs y básicos
    row.id_subasta or "",
    row.id_renglon,
    fmt.truncate(row.desc, 80),
    fmt.format_number(row.cantidad, decimals=2),
    # Metadata usuario
    row.unidad_medida or "",
    row.marca or "",
    fmt.truncate(row.obs_usuario or "", 40),
    # Costos
    fmt.format_number(row.conversion_usd, decimals=2),
    fmt.format_number(row.costo_unit_usd, decimals=2),
    fmt.format_number(row.costo_total_usd, decimals=2),
    fmt.format_money(row.costo_unit_ars),
    fmt.format_money(row.costo_total_ars),
    # Rentabilidad mínima
    fmt.format_percentage(row.renta_minima) if row.renta_minima is not None else "",
    fmt.format_money(row.precio_unit_aceptable),
    fmt.format_money(row.precio_total_aceptable),
    # Referencia
    fmt.format_money(row.precio_referencia),
    fmt.format_money(row.precio_ref_unitario),
    fmt.format_percentage(row.renta_referencia) if row.renta_referencia is not None else "",
    # Mejora en subasta
    row.mejor_oferta_txt or "",
    fmt.format_money(row.oferta_para_mejorar),
    fmt.format_money(row.precio_unit_mejora),
    fmt.format_percentage(row.renta_para_mejorar) if row.renta_para_mejorar is not None else "",
    # Observaciones
    fmt.truncate(row.obs_cambio or "", 60),
)
```

---

## 4️⃣ app/core/app_runtime.py

### ❌ ANTES (import_excel, líneas ~230-250)
```python
for row in rows:
    id_cot = row.get("ID SUBASTA")
    id_renglon = row.get("ITEM")
    ...
    self.db.upsert_renglon_excel(
        renglon_id=renglon_id,
        unidad_medida=(row.get("UNIDAD DE MEDIDA") or None),
        cantidad=_to_float(row.get("CANTIDAD")),
        marca=(row.get("MARCA") or None),
        observaciones=(row.get("Observaciones") or None),
        conversion_usd=_to_float(row.get("CONVERSIÓN USD")),
        costo_usd=existing.get("costo_usd"),
        costo_final_pesos=_to_float(row.get("COSTO FINAL PESOS")),
        renta=_to_float(row.get("RENTA")),
        ...
    )
```

### ✅ DESPUÉS (import_excel)
```python
for row in rows:
    id_cot = row.get("ID SUBASTA")
    id_renglon = row.get("ITEM")
    ...
    self.db.upsert_renglon_excel(
        renglon_id=renglon_id,
        unidad_medida=(row.get("UNIDAD DE MEDIDA") or None),
        cantidad=_to_float(row.get("CANTIDAD")),
        marca=(row.get("MARCA") or None),
        obs_usuario=(row.get("OBS USUARIO") or None),
        conversion_usd=_to_float(row.get("CONVERSIÓN USD")),
        costo_unit_usd=_to_float(row.get("COSTO UNIT USD")),
        costo_total_usd=_to_float(row.get("COSTO TOTAL USD")),
        costo_unit_ars=_to_float(row.get("COSTO UNIT ARS")),
        costo_total_ars=_to_float(row.get("COSTO TOTAL ARS")),
        renta_minima=_to_float(row.get("RENTA MINIMA %")),
        precio_referencia=existing.get("precio_referencia"),
        precio_referencia_subasta=existing.get("precio_referencia_subasta"),
        updated_at=now_iso(),
    )
```

### ❌ ANTES (update_renglon_excel, líneas ~123-147)
```python
def update_renglon_excel(
    self,
    *,
    renglon_id: int,
    unidad_medida: str | None = None,
    marca: str | None = None,
    observaciones: str | None = None,
    conversion_usd: float | None = None,
    costo_final_pesos: float | None = None,
    renta: float | None = None,
) -> None:
```

### ✅ DESPUÉS (update_renglon_excel)
```python
def update_renglon_excel(
    self,
    *,
    renglon_id: int,
    unidad_medida: str | None = None,
    marca: str | None = None,
    obs_usuario: str | None = None,
    conversion_usd: float | None = None,
    costo_unit_ars: float | None = None,
    costo_total_ars: float | None = None,
    renta_minima: float | None = None,
) -> None:
    existing = self.db.get_renglon_excel(renglon_id=renglon_id) or {}
    self.db.upsert_renglon_excel(
        renglon_id=renglon_id,
        unidad_medida=unidad_medida,
        cantidad=existing.get("cantidad"),
        marca=marca,
        obs_usuario=obs_usuario,
        conversion_usd=conversion_usd,
        costo_unit_ars=costo_unit_ars,
        costo_total_ars=costo_total_ars,
        renta_minima=renta_minima,
        costo_unit_usd=existing.get("costo_unit_usd"),
        costo_total_usd=existing.get("costo_total_usd"),
        precio_referencia=existing.get("precio_referencia"),
        precio_referencia_subasta=existing.get("precio_referencia_subasta"),
        updated_at=now_iso(),
    )
```

---

## 5️⃣ app/core/engine.py

### NUEVO: Función helper para bidireccionalidad

**Insertar antes del método `_process_renglon()`, alrededor de línea ~320**

```python
def _resolve_costo_final(
    self,
    unit: float | None,
    total: float | None,
    cantidad: float | None,
) -> tuple[float | None, float | None]:
    """
    Resuelve COSTO UNIT ARS ↔ COSTO TOTAL ARS de forma bidireccional.
    
    Regla: Si ambos presentes, prioridad a TOTAL.
    Si solo uno, se calcula el otro usando CANTIDAD.
    
    Returns:
        (costo_unit_ars, costo_total_ars)
    """
    if cantidad is None or cantidad == 0:
        return (unit, total)
    
    # Caso 1: Ambos presentes
    if unit is not None and total is not None:
        # Validar consistencia
        try:
            expected_total = float(unit) * float(cantidad)
            # Si hay considerable discrepancia, prioridad a TOTAL
            if abs(expected_total - float(total)) > 0.01:
                # User override: recalcular UNIT desde TOTAL
                return (float(total) / float(cantidad), float(total))
        except Exception:
            pass
        return (float(unit), float(total))
    
    # Caso 2: Solo TOTAL presente
    if total is not None:
        try:
            calc_unit = float(total) / float(cantidad)
            return (calc_unit, float(total))
        except Exception:
            return (None, float(total))
    
    # Caso 3: Solo UNIT presente
    if unit is not None:
        try:
            calc_total = float(unit) * float(cantidad)
            return (float(unit), calc_total)
        except Exception:
            return (float(unit), None)
    
    # Caso 4: Ninguno presente
    return (None, None)
```

### ❌ ANTES (en _process_renglon, líneas ~327-350)
```python
excel = self.db.get_renglon_excel(renglon_id=renglon_pk)

unidad_medida = None
cantidad = None
marca = None
observaciones = None
conversion_usd = None
costo_usd = None
costo_final_pesos = None
renta = None
precio_referencia_subasta = None

if excel:
    unidad_medida = excel.get("unidad_medida")
    cantidad = excel.get("cantidad")
    marca = excel.get("marca")
    observaciones = excel.get("observaciones")
    conversion_usd = excel.get("conversion_usd")
    costo_usd = excel.get("costo_usd")
    costo_final_pesos = excel.get("costo_final_pesos")
    renta = excel.get("renta")
    precio_referencia_subasta = excel.get("precio_referencia_subasta")
```

### ✅ DESPUÉS (en _process_renglon)
```python
excel = self.db.get_renglon_excel(renglon_id=renglon_pk)

unidad_medida = None
cantidad = None
marca = None
obs_usuario = None
conversion_usd = None
costo_unit_usd = None
costo_total_usd = None
costo_unit_ars = None
costo_total_ars = None
renta_minima = None
precio_referencia = None
precio_referencia_subasta = None

if excel:
    unidad_medida = excel.get("unidad_medida")
    cantidad = excel.get("cantidad")
    marca = excel.get("marca")
    obs_usuario = excel.get("obs_usuario")
    conversion_usd = excel.get("conversion_usd")
    costo_unit_usd = excel.get("costo_unit_usd")
    costo_total_usd = excel.get("costo_total_usd")
    renta_minima = excel.get("renta_minima")
    precio_referencia = excel.get("precio_referencia")
    precio_referencia_subasta = excel.get("precio_referencia_subasta")
    
    # Resolver bidireccionalidad COSTO
    costo_unit_ars, costo_total_ars = self._resolve_costo_final(
        unit=excel.get("costo_unit_ars"),
        total=excel.get("costo_total_ars"),
        cantidad=cantidad,
    )
```

### ❌ ANTES (cálculos posteriores, líneas ~370-385)
```python
costo_usd_calc = None
if conversion_usd not in (None, 0) and costo_final_pesos is not None:
    try:
        costo_usd_calc = float(costo_final_pesos) / float(conversion_usd)
    except Exception:
        costo_usd_calc = None

subtotal_para_mejorar = oferta_min_val
subtotal_costo_pesos = self._safe_mul(cantidad, costo_final_pesos)
p_unit_minimo = self._safe_mul(renta, costo_final_pesos)
subtotal = self._safe_mul(cantidad, p_unit_minimo)
```

### ✅ DESPUÉS (cálculos posteriores)
```python
# Calcular COSTO USD si no viene del usuario
if costo_unit_usd is None and conversion_usd not in (None, 0) and costo_unit_ars is not None:
    try:
        costo_unit_usd = float(costo_unit_ars) / float(conversion_usd)
    except Exception:
        pass

if costo_total_usd is None and conversion_usd not in (None, 0) and costo_total_ars is not None:
    try:
        costo_total_usd = float(costo_total_ars) / float(conversion_usd)
    except Exception:
        pass

oferta_para_mejorar = oferta_min_val
precio_unit_aceptable = self._safe_mul(renta_minima, costo_unit_ars)
precio_total_aceptable = self._safe_mul(renta_minima, costo_total_ars)
```

### ❌ ANTES (resto de cálculos, líneas ~387-405)
```python
precio_ref_unit = self._resolve_precio_ref_unitario(
    cantidad=cantidad,
    precio_referencia=precio_referencia_subasta,
    presupuesto=presupuesto_val,
)

renta_ref = None
if precio_ref_unit is not None and costo_final_pesos not in (None, 0):
    renta_ref = (float(precio_ref_unit) / float(costo_final_pesos)) - 1.0

p_unit_mejora = self._safe_div(subtotal_para_mejorar, cantidad)

dif_unit = None
if p_unit_mejora is not None and costo_final_pesos is not None:
    dif_unit = float(p_unit_mejora) - float(costo_final_pesos)

renta_dpc = None
if p_unit_mejora is not None and costo_final_pesos not in (None, 0):
    renta_dpc = (float(p_unit_mejora) / float(costo_final_pesos)) - 1.0
```

### ✅ DESPUÉS (resto de cálculos)
```python
# PRECIO DE REFERENCIA UNITARIO
precio_ref_unitario = self._safe_div(precio_referencia_subasta, cantidad)

# RENTA REFERENCIA
renta_referencia = None
if precio_ref_unitario is not None and costo_total_ars not in (None, 0):
    renta_referencia = (float(precio_ref_unitario) / float(costo_total_ars)) - 1.0

# PRECIO UNITARIO MEJORA
precio_unit_mejora = self._safe_div(oferta_para_mejorar, cantidad)

# RENTA PARA MEJORAR
renta_para_mejorar = None
if precio_unit_mejora is not None and costo_total_ars not in (None, 0):
    renta_para_mejorar = (float(precio_unit_mejora) / float(costo_total_ars)) - 1.0
```

---

## 6️⃣ app/models/domain.py

### NUEVO: Actualizar UIRow para incluir nuevos campos

**Buscar la clase `UIRow` (alrededor de línea ~30) y AGREGAR estos campos:**

```python
# NUEVOS CAMPOS
costo_unit_usd: float | None = None
costo_total_usd: float | None = None
costo_unit_ars: float | None = None
costo_total_ars: float | None = None
renta_minima: float | None = None
precio_unit_aceptable: float | None = None
precio_total_aceptable: float | None = None
precio_ref_unitario: float | None = None
renta_referencia: float | None = None
precio_unit_mejora: float | None = None
renta_para_mejorar: float | None = None
obs_usuario: str | None = None
mejor_oferta_txt: str | None = None

# REMOVE O DEPRECATE (mantener por ahora si hay referencias)
# observaciones → obs_usuario
# costo_final → costo_unit_ars
# subtotal_costo → costo_total_ars
# renta_ref → renta_referencia
# p_unit_mejora → precio_unit_mejora
# dif_unit → (opcional, calcular on-the-fly)
# renta_dpc → renta_para_mejorar
```

---

## 🗄️ BONUS: Script de Migración BD

**Crear archivo:** `scripts/migrate_columns_v2.py`

```python
#!/usr/bin/env python3
"""
Script reversible para migrar columnas en BD.

Uso:
    python scripts/migrate_columns_v2.py --up    # Aplicar cambios
    python scripts/migrate_columns_v2.py --down  # Revertir
"""

import sys
import shutil
from pathlib import Path
from app.db.database import Database

def backup_db(db_path: str) -> str:
    """Crea backup de DB antes de migrar"""
    p = Path(db_path)
    if not p.exists():
        raise FileNotFoundError(f"DB no encontrada: {db_path}")
    
    backup_path = str(p.parent / f"{p.stem}.backup.{p.suffix}")
    shutil.copy(db_path, backup_path)
    print(f"✅ Backup creado: {backup_path}")
    return backup_path

def migrate_up(db: Database):
    """Aplica cambios a la estructura de BD"""
    print("🔄 Migrando columnas UP...")
    
    # Renombrar columnas
    renames = [
        ("obs", "obs_usuario"),
        ("costo_final", "costo_unit_ars"),
        ("subtotal_costo", "costo_total_ars"),
        ("renta_ref", "renta_referencia"),
        ("p_unit_mejora", "precio_unit_mejora"),
        ("renta_dpc", "renta_para_mejorar"),
    ]
    
    for old_col, new_col in renames:
        try:
            db.execute(f"ALTER TABLE renglon_excel RENAME COLUMN {old_col} TO {new_col}")
            print(f"  ✅ {old_col} → {new_col}")
        except Exception as e:
            print(f"  ⚠️  {old_col}: {e}")
    
    # Agregar columnas nuevas
    new_cols = [
        ("costo_unit_usd", "REAL"),
        ("costo_total_usd", "REAL"),
        ("renta_minima", "REAL"),
        ("precio_unit_aceptable", "REAL"),
        ("precio_total_aceptable", "REAL"),
        ("precio_ref_unitario", "REAL"),
        ("renta_para_mejorar", "REAL"),
    ]
    
    for col, dtype in new_cols:
        try:
            db.execute(f"ALTER TABLE renglon_excel ADD COLUMN {col} {dtype}")
            print(f"  ✅ {col} agregado")
        except Exception as e:
            print(f"  ⚠️  {col}: {e}")
    
    db.conn.commit()
    print("✅ Migración UP completada")

def migrate_down(db: Database):
    """Revierte cambios de la migración (si es posible)"""
    print("⚠️  Migrando DOWN (revert)...")
    print("⚠️  SQLite no soporta DROP COLUMN bien")
    print("⚠️  Restaurar desde backup es más seguro")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: migrate_columns_v2.py --up|--down")
        sys.exit(1)
    
    mode = sys.argv[1]
    db_path = "data/app.db"
    
    backup_db(db_path)
    
    db = Database(db_path)
    
    if mode == "--up":
        migrate_up(db)
    elif mode == "--down":
        migrate_down(db)
    else:
        print(f"Modo desconocido: {mode}")
        sys.exit(1)
```

---

## ✅ ORDEN DE EJECUCIÓN RECOMENDADO

1. **Actualizar `table_manager.py`** (UI labels)
2. **Actualizar `formatters.py`** (sync con tabla)
3. **Actualizar `excel_io.py`** (Excel headers)
4. **Actualizar `app_runtime.py`** (Import/export)
5. **Actualizar `engine.py`** (Cálculos + bidireccionalidad)
6. **Actualizar `domain.py`** (UIRow model)
7. **Ejecutar migración BD** (`scripts/migrate_columns_v2.py --up`)
8. **Testing exhaustivo** (ver Fase 6 en PLAN_CAMBIOS_COLUMNAS.md)

