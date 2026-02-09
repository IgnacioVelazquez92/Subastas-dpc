# 📖 Guía Rápida de Mantención: Módulos de UI

## 🎯 Dónde Hacer Cada Cambio

### ❓ "Necesito cambiar cómo se ven los números"
**Dónde**: `app/ui/formatters.py`  
**Qué clase**: `DataFormatter`  
**Métodos relevantes**:
- `format_money()` → Dinero
- `format_percentage()` → Porcentajes
- `format_number()` → Números decimales

```python
# Ejemplo: Cambiar formato de dinero de "$ 1.234.567,89" a "$1234567.89"
@staticmethod
def format_money(value: float | None) -> str:
    if value is None:
        return ""
    return f"${value:,.2f}"
```

---

### ❓ "Necesito agregar una columna nueva a la tabla"
**Dónde**: `app/ui/table_manager.py`  
**Qué clase**: `TableConfig`  
**Pasos**:
1. Agregar nombre en `TableConfig.columns` tuple
2. Agregar label en `TableConfig.column_labels` dict
3. Agregar width en `TableConfig.column_widths` dict

```python
@dataclass(frozen=True)
class TableConfig:
    columns: tuple[str, ...] = (
        "id_subasta", "item", "desc",
        # Agregar aquí:
        "nueva_columna",
        ...
    )
    
    def __post_init__(self):
        if self.column_labels is None:
            labels = {
                ...
                "nueva_columna": "Mi Nueva Columna",  # ← Aquí
                ...
            }
            object.__setattr__(self, 'column_labels', labels)
```

---

### ❓ "Quiero cambiar cómo se ve la tabla (colores, fuentes)"
**Dónde**: `app/ui/table_manager.py`  
**Qué método**: `TableManager.initialize()`  
**Dónde cambiar**:
```python
def initialize(self) -> None:
    # Cambiar aquí los colores de estilos:
    self.tree.tag_configure(RowStyle.NORMAL.value, background="")
    self.tree.tag_configure(RowStyle.TRACKED.value, background="#e7f1ff")  # ← Azul claro
    self.tree.tag_configure(RowStyle.WARNING.value, background="#fff3cd")  # ← Amarillo
    self.tree.tag_configure(RowStyle.DANGER.value, background="#f8d7da")   # ← Rojo
    self.tree.tag_configure(RowStyle.SUCCESS.value, background="#d1e7dd")  # ← Verde
```

---

### ❓ "Necesito agregar un nuevo campo al renglón"
**Dónde**: `app/models/domain.py` (actualizar `UIRow`)  
**También necesitas**:
1. Update `event_handler.py` → `_update_row_from_payload()`
2. Update `table_manager.py` → `DisplayValues.build_row_values()`
3. Agregar columna como arriba

```python
# Estructura:
# 1. En app/models/domain.py, agregar el campo a UIRow:
@dataclass
class UIRow:
    ...
    nuevo_campo: float | None = None  # ← Agregar

# 2. En app/ui/event_handler.py, copiar desde payload:
def _update_row_from_payload(self, row: UIRow, payload: dict, ev: Event) -> None:
    ...
    row.nuevo_campo = payload.get("nuevo_campo")  # ← Agregar

# 3. En app/ui/formatters.py, formatear para tabla:
class DisplayValues:
    @staticmethod
    def build_row_values(row: UIRow) -> tuple[str, ...]:
        ...
        _fmt_money(row.nuevo_campo),  # ← En posición correcta
        ...
```

---

### ❓ "El parsing de números no funciona bien para mi formato"
**Dónde**: `app/ui/formatters.py`  
**Qué método**: `DataFormatter.parse_float()`  
**Estado actual**: Soporta múltiples formatos (1.234,56 / 1,234.56 / 1234567)

```python
# El método actualmente inteligente detecta:
# - Decimal con coma: "1.234,56" → "1234.56"
# - Decimal con punto: "1,234.56" → sin cambio
# - Miles separados: "1.234.567" → "1234567"
# Agregar tu formato personalizado aquí
```

---

### ❓ "Necesito cambiar cómo se procesan los eventos"
**Dónde**: `app/ui/event_handler.py`  
**Qué clase**: `EventProcessor`  
**Métodos existentes**:
- `_handle_snapshot()` → Reconstruye tabla
- `_handle_update()` → Crea u actualiza fila
- `_update_row_from_payload()` → Copia datos

```python
class EventProcessor:
    def _handle_snapshot(self, ev: Event) -> None:
        # Aquí procesas SNAPSHOT events
        
    def _handle_update(self, ev: Event) -> None:
        # Aquí procesas UPDATE events
        
    def _update_row_from_payload(self, row, payload, ev) -> None:
        # Aquí defines qué datos copiar de cada event
```

---

### ❓ "Quiero cambiar el diálogo de edición de renglón"
**Dónde**: `app/ui/row_editor.py`  
**Qué clase**: `RowEditorDialog`  
**Métodos**:
- `_build_dialog()` → Estructura del diálogo
- `_add_entry()` → Agregar campos
- `_save()` → Lógica de guardado
- `_recalculate_derived_fields()` → Cálculos después de edición

```python
def _add_entry(self, parent, label: str, key: str, value=None):
    # Agregar más campos aquí:
    self._add_entry(frame, "Mi campo", "mi_campo", self.row.mi_campo)
```

---

### ❓ "Necesito agregar una nueva fórmula de cálculo"
**Dónde**: `app/ui/row_editor.py`  
**Qué clase**: `RowCalculator`  
**Pasos**:
1. Agregar método `@staticmethod` con lógica pura
2. Llamarlo desde `RowEditorDialog._recalculate_derived_fields()`

```python
class RowCalculator:
    @staticmethod
    def calculate_mi_formula(valor_a: float, valor_b: float) -> float | None:
        if valor_a is None or valor_b is None:
            return None
        return valor_a * valor_b + 100  # Tu lógica

# Luego en _recalculate_derived_fields():
self.row.mi_resultado = self.calc.calculate_mi_formula(a, b)
```

---

### ❓ "El filtro de logs deja pasar eventos que no quiero ver"
**Dónde**: `app/ui/logger_widget.py`  
**Qué método**: `LoggerWidget._should_skip()`  
**Estado actual**: Filtra `EventLevel.DEBUG` y `HEARTBEAT` sin contexto

```python
def _should_skip(self, msg: str) -> bool:
    """Agregar aquí tus filtros personalizados."""
    if "EventLevel.DEBUG" in msg:
        return True
    if "EventType.HEARTBEAT" in msg and "Resumen" not in msg:
        return True
    # Agregar:
    if "SPAM" in msg:
        return True
    return False
```

---

### ❓ "Necesito agregar/quitar columnas por código (no por UI)"
**Dónde**: `app/ui/column_manager.py`  
**Métodos**:
- `load_visible_columns()` → Cargar del storage
- `save_visible_columns()` → Guardar a storage
- `set_visible_columns()` → Cambiar visibles

```python
# Desde app.py:
self.col_mgr.set_visible_columns([
    "id_subasta", "item", "desc",
    # Solo estas columnas visibles
])
```

---

### ❓ "Quiero persistir datos nuevos de la UI (no renglones)"
**Dónde**: `app/core/app_runtime.py` o `app/db/database.py`  
**Sistema existente**: UI config en tabla `ui_config` (key/value)

```python
# Ya existe sistema para UI config:
self.db_runtime.get_ui_config(key="visible_columns")
self.db_runtime.set_ui_config(key="visible_columns", value=json.dumps([...]))

# Reutilizar para tus datos:
self.db_runtime.set_ui_config(key="mi_config", value=json.dumps(mi_valor))
```

---

### ❓ "Necesito crear un nuevo manager especializado"
**Patrón a seguir**:
```python
# app/ui/mi_manager.py

class MiManager:
    """Responsabilidad específica aquí."""
    
    def __init__(self, dependency1, dependency2):
        """Inyectar dependencias."""
        self.dep1 = dependency1
        self.dep2 = dependency2
    
    def metodo_publico(self) -> ReturnType:
        """Interfaz pública."""
        return self._helper_privado()
    
    def _helper_privado(self) -> ReturnType:
        """Lógica sin exposición."""
        pass

# En app.py:
from app.ui.mi_manager import MiManager
self.mi_mgr = MiManager(self.dep1, self.dep2)
```

---

## 🧪 Testing de Cambios

### Test Rápido: Formatters
```python
from app.ui.formatters import DataFormatter

# Test format_money
assert DataFormatter.format_money(1234567.89) == "$ 1.234.567,89"

# Test parse_float
assert DataFormatter.parse_float("1.234,56") == 1234.56
assert DataFormatter.parse_float("1,234.56") == 1234.56
```

### Test Rápido: RowCalculator
```python
from app.ui.row_editor import RowCalculator

# Test seguridad
assert RowCalculator.safe_div(10, 0) is None
assert RowCalculator.safe_div(10, 2) == 5.0

# Test cálculo
assert RowCalculator.calculate_renta_ref(100, 50) == 1.0
```

---

## 🚀 Cambios Comunes

| Cambio | Dónde | Riesgo | Notas |
|--------|-------|--------|-------|
| Nuevo formato de dinero | formatters.py | 🟢 Bajo | Aislado, no afecta lógica |
| Agregar columna | table_manager.py + formatters.py | 🟡 Medio | Coordinar 3 lugares |
| Cambiar colores filas | table_manager.py | 🟢 Bajo | Solo UI |
| Nueva fórmula | row_editor.py | 🟢 Bajo | RowCalculator es testeable |
| Nuevo tipo de evento | event_handler.py | 🟡 Medio | Agregar handler nuevo |
| Cambiar logs | logger_widget.py | 🟢 Bajo | Aislado |

---

## 🧠 Filosofía de Mantención

**Cada módulo es responsable de UNA cosa:**

- `formatters.py` → "¿Cómo se ven los datos?"
- `table_manager.py` → "¿Cómo se estructura la tabla?"
- `event_handler.py` → "¿Cómo procesar eventos?"
- `row_editor.py` → "¿Cómo editar y calcular?"
- `column_manager.py` → "¿Cómo gestionar columnas?"
- `logger_widget.py` → "¿Cómo loguear?"

**Antes de cambiar cualquier cosa:**
1. Pregúntate: "¿Cuál es la responsabilidad de este cambio?"
2. Ve al módulo que tiene esa responsabilidad
3. Haz el cambio allí
4. NO modifices otros módulos a menos que sea absolutamente necesario

---

## 📞 Soporte

**Si algo no funciona:**
1. Verifica que importes el módulo correcto
2. Revisa que los tipos pasados matcheen (ej: `UIRow` vs `dict`)
3. Chequea que no haya dependencias circulares
4. Usa los docstrings de cada módulo como referencia

**Riesgo CERO**: Cada módulo es independiente. Cambiar uno no debería romper otro.
