# 🎯 Plan de Refactorización: app/ui/app.py

## 📋 Problemática Actual

**Archivo**: `app/ui/app.py` (878 líneas)
**Problema**: Mezcla de responsabilidades (SRP violation)

### Responsabilidades mezcladas:
- ✗ Configuración de UI (columnas, widths, labels)
- ✗ Gestión de tabla Treeview (insert, render, clear)
- ✗ Procesamiento de eventos del motor
- ✗ Formato de datos (dinero, porcentajes, números)
- ✗ Diálogos de usuario (columnas, edición de renglones)
- ✗ Parsing y conversión de valores
- ✗ Cálculos complejos de fórmulas
- ✗ Logging

---

## ✅ Solución: Separación de Responsabilidades

### Nuevo árbol de módulos

```
app/ui/
├── __init__.py
├── app.py                    # Orquestador principal (refactorizado)
├── formatters.py            # Formateo de datos (NUEVO)
├── table_manager.py         # Gestión Treeview (NUEVO)
├── column_manager.py        # Visibilidad de columnas (NUEVO)
├── event_handler.py         # Procesamiento de eventos (NUEVO)
├── row_editor.py            # Diálogo edición renglones (NUEVO)
└── logger_widget.py         # Widget de logs (NUEVO)
```

---

## 📦 Modules Details

### 1. **formatters.py** (~80 líneas)
**Responsabilidad**: Formateo de datos para display

```python
class DataFormatter:
    @staticmethod
    def format_money(value: float | None) -> str
    @staticmethod
    def format_percentage(value: float | None) -> str
    @staticmethod
    def format_number(value: float | None, decimals: int = 2) -> str
    @staticmethod
    def truncate(s: str, n: int) -> str
    
    @staticmethod
    def parse_float(raw: str) -> float | None  # Parsing inteligente
    
class DisplayValues:
    """Prepara row.* -> tupla de valores para Treeview"""
    @staticmethod
    def build_row_values(row: UIRow) -> tuple[str, ...]
```

**Dependencias**: `app.utils.money` (ya existe)

---

### 2. **table_manager.py** (~150 líneas)
**Responsabilidad**: Crear, modificar, renderizar tabla Treeview

```python
class TableConfig:
    """Metadata estática de tabla"""
    columns: tuple[str, ...]
    column_labels: dict[str, str]
    column_widths: dict[str, int]
    row_styles: dict[str, tuple]  # Color mapping

class TableManager:
    def __init__(self, tree: ttk.Treeview, db_runtime)
    
    # Operaciones tabla
    def clear(self) -> None
    def rebuild_from_snapshot(self, items: list[dict]) -> None
    def insert_row(self, row: UIRow) -> str  # Retorna IID
    def render_row(self, row: UIRow, style: str) -> None
    def remove_row(self, rid: str) -> None
    
    # Metadata
    def get_config(self) -> TableConfig
    def apply_row_styles(self) -> None
```

**Dependencias**: `formatters.DataFormatter`, `DisplayValues`

---

### 3. **column_manager.py** (~140 líneas)
**Responsabilidad**: Diálogo de columnas, persistencia, visibilidad

```python
class ColumnManager:
    def __init__(self, tree: ttk.Treeview, db_runtime, table_config: TableConfig)
    
    # Persistencia
    def load_visible_columns(self, default: list[str]) -> None
    def save_visible_columns(self, cols: list[str]) -> None
    
    # UI Dialog
    def show_dialog(self, parent_window: ctk.CTk) -> None
    
    # Helpers
    def get_visible_columns(self) -> list[str]
    def set_visible_columns(self, cols: list[str]) -> None
```

**Responsabilidad clara**: Solo columnas, nada más.

---

### 4. **event_handler.py** (~120 líneas)
**Responsabilidad**: Procesar eventos de Engine hacia UI

```python
class EventProcessor:
    def __init__(self, table_mgr: TableManager, logger, rows_cache: dict)
    
    def process_event(self, ev: Event) -> None
    
    # Handlers por tipo de evento
    def _handle_start(self, ev: Event) -> None
    def _handle_stop(self, ev: Event) -> None
    def _handle_snapshot(self, ev: Event) -> None
    def _handle_update(self, ev: Event) -> None
    def _handle_heartbeat(self, ev: Event) -> None
    
    # Helpers
    def _build_or_update_row(self, payload: dict) -> UIRow
    def _apply_event_decorations(self, row: UIRow, payload: dict) -> str
```

**Independencia**: No toca UI directamente, solo modifica rows_cache y tabla.

---

### 5. **row_editor.py** (~180 líneas)
**Responsabilidad**: Diálogo de edición de renglón + cálculos de fórmulas

```python
class RowCalculator:
    """Encapsula lógica de cálculos de fórmulas"""
    @staticmethod
    def calculate_costo_usd(costo_final_pesos: float, conversion_usd: float) -> float
    @staticmethod
    def calculate_subtotal_costo(cantidad: float, costo_final_pesos: float) -> float
    @staticmethod
    def calculate_p_unit_minimo(renta: float, costo_final_pesos: float) -> float
    @staticmethod
    def calculate_subtotal(cantidad: float, p_unit_minimo: float) -> float
    @staticmethod
    def calculate_renta_ref(precio_ref: float, costo_final: float) -> float
    @staticmethod
    def calculate_p_unit_mejora(subtotal_mejorar: float, cantidad: float) -> float
    @staticmethod
    def calculate_dif_unit(p_unit_mejora: float, costo_final: float) -> float
    @staticmethod
    def calculate_renta_dpc(p_unit_mejora: float, costo_final: float) -> float

class RowEditorDialog:
    def __init__(self, parent: ctk.CTk, row: UIRow, db_runtime)
    
    def show(self) -> None  # Crea window y espera
    
    # Internals
    def _build_form(self) -> None
    def _on_save(self) -> None
    def _validate_and_save(self) -> bool
    def _recalculate_derived_fields(self) -> None
```

**Claridad**: Separación entre cálculos y UI.

---

### 6. **logger_widget.py** (~40 líneas)
**Responsabilidad**: Widget de logs con filtro de spam

```python
class LoggerWidget:
    def __init__(self, parent_frame: ctk.CTkFrame, height: int = 8)
    
    def log(self, msg: str, level: str = "INFO") -> None
    def clear(self) -> None
    
    # Internals
    def _should_skip(self, msg: str) -> bool
    def _put(self, formatted: str) -> None
```

**Independencia**: Widget puro, zero dependencias de negocio.

---

## 🔧 Refactorización de app.py

### Antes (878 líneas)
```python
class App(ctk.CTk):
    def _build_ui(self): # TODO todo
    def _poll_events(self): # TODO todo
    def _handle_event(self, ev): # TODO evento
    def _render_row(self, row): # TODO tabla
    def on_columns(self): # Dialog 140 líneas!
    def on_edit_row(self): # Dialog 180 líneas!!
    def _parse_float(self): # Parsing
    def _log(self): # Logging
```

### Después (~250 líneas)
```python
class App(ctk.CTk):
    def __init__(self, *, handles: RuntimeHandles):
        # Setup básico
        
    def _build_ui(self) -> None:
        """Construye estructura principal"""
        # Crea frames, buttons top
        # Delega tabla a TableManager
        # Delega logs a LoggerWidget
        
    def _poll_events(self) -> None:
        """Poll desde engine"""
        
    def _handle_event(self, ev: Event) -> None:
        """Delega a EventProcessor"""
        
    def on_columns(self) -> None:
        """Delega a ColumnManager.show_dialog()"""
        
    def on_edit_row(self) -> None:
        """Crea RowEditorDialog"""
        
    # Button handlers (on_start_browser, on_stop, etc.) 
    # → Mínimos, solo delegación
```

---

## 📋 Ventajas de esta Refactorización

| Aspecto | Antes | Después |
|---------|-------|---------|
| **Líneas por clase** | 878 (monolítica) | 250 (orquestador) |
| **Responsabilidades** | 8+ mezcladas | 1 (orquestación) |
| **Testabilidad** | Muy difícil | Cada módulo aislado |
| **Reutilización** | Imposible | `TableManager`, `EventProcessor`, etc. reutilizables |
| **Cambios en formato** | Toca 5 métodos | Solo `formatters.py` |
| **Cambios en tabla** | Toca 200 líneas | Solo `table_manager.py` |
| **Mantenibilidad** | Baja (spaghetti) | Alta (modular) |

---

## 🚀 Estrategia de Implementación

### Fase 1: Crear módulos nuevos (Sin tocar app.py)
1. `formatters.py` - Funciones de formato
2. `table_manager.py` - Gestión Treeview
3. `column_manager.py` - Dialog columnas
4. `event_handler.py` - Procesador eventos
5. `row_editor.py` - Dialog edición + cálculos
6. `logger_widget.py` - Widget logs

**Riesgo**: BAJO (nuevos archivos, no interfieren)

### Fase 2: Reemplazar en App (Cuidadoso)
1. Importar módulos nuevos
2. Adaptar `__init__()` para usar managers
3. Simplificar `_build_ui()`
4. Redirigir `_handle_event()` a `EventProcessor`
5. Redirigir `on_columns()` a `ColumnManager`
6. Redirigir `on_edit_row()` a `RowEditorDialog`

**Riesgo**: MEDIO (cambios secuenciales, validar cada uno)

### Fase 3: Validación
- ✓ Todos los imports funcionan
- ✓ UI se abre sin errores
- ✓ Eventos se procesan igual
- ✓ Diálogos funcionan igual
- ✓ Formatting idéntico
- ✓ Tests passed

**Riesgo**: BAJO (solo validación)

---

## ⚠️ Cuidados Especiales

1. **UIRow dataclass**: Mantener igual, es el "currency" entre módulos
2. **Imports circulares**: Evita importar `App` en sub-módulos
3. **db_runtime**: Pasar como inyección de dependencia
4. **Sincronía**: `on_edit_row()` debe esperar a que dialog cierre antes de renderizar
5. **Event queue**: No cambiar tamaño ni tipo, solo procesamiento interno

---

## 📊 Estimado

| Tarea | Líneas | Tiempo |
|-------|--------|--------|
| formatters.py | 80 | 20 min |
| table_manager.py | 150 | 40 min |
| column_manager.py | 140 | 35 min |
| event_handler.py | 120 | 35 min |
| row_editor.py | 180 | 45 min |
| logger_widget.py | 40 | 15 min |
| app.py refactor | 250 | 30 min |
| Validación | - | 20 min |
| **TOTAL** | 960 | **240 min** (4 horas) |

---

## ✅ Checklist Final

- [ ] Todos los módulos crean sin errores
- [ ] app.py importa todos correctamente
- [ ] UI abre y muestra tabla
- [ ] Eventos procesan sin delay perceptible
- [ ] Dialog "Columnas" funciona igual
- [ ] Dialog "Editar renglón" funciona igual  
- [ ] Logs se filtran correctamente
- [ ] Cálculos de fórmulas dan resultados iguales
- [ ] No hay errores en terminal
- [ ] No hay warnings de imports no usados
