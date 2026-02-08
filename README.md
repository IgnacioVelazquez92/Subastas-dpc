# Monitor de Subastas Electrónicas

Aplicación de escritorio para monitoreo en tiempo real de subastas electrónicas del portal de e-Commerce de la provincia de Córdoba. La UI consume eventos normalizados y es agnóstica al origen de datos (simulador o Playwright).

## 🎯 Arquitectura

**Flujo principal:** `Collector → Engine → UI` | `Engine → SQLite`

### Componentes

- **Collector**: Obtiene datos (Mock o Playwright) y emite eventos normalizados
- **Engine**: Persiste en DB, aplica reglas de alertas/seguridad, emite eventos procesados
- **UI**: Presenta información, edita datos, dispara acciones (captura, Excel, limpieza)
- **DB**: SQLite para observabilidad, estado operativo, configuración UI y datos Excel

## ✅ Funcionalidades Implementadas

### Modos de Operación
- **MOCK**: Simula subastas con datos generados automáticamente para pruebas de UX
- **PLAYWRIGHT**: Navegador automatizado que captura y monitorea subastas reales

### Gestión de Datos
- **Excel**: Exportación/importación de campos de costos y observaciones
- **Columnas configurables**: Personalización de vista con persistencia en DB
- **Edición de filas**: Modificación de datos de renglones desde la UI
- **Limpieza de datos**: Gestión de logs y estados históricos

### Sistema de Alertas y Seguridad
- **Logs agregados**: Anti-spam para eventos repetitivos
- **Backoff/Stop**: Políticas de corte automático ante errores HTTP
- **Control de runtime**: Supervisión del ciclo de vida del collector

## 📁 Estructura del Proyecto

```
monitor_subastas/
├── main.py                    # Entry point principal
├── requirements.txt           # Dependencias Python
├── README.md
│
├── app/
│   ├── core/
│   │   ├── app_runtime.py     # Orquestador Collector → Engine → UI
│   │   ├── engine.py          # Motor principal: persistencia + alertas + seguridad
│   │   ├── events.py          # Contratos de eventos (Event, EventType, EventLevel)
│   │   ├── alert_engine.py    # Reglas de alertas (estilos, sonidos, ocultamiento)
│   │   ├── security.py        # Políticas de backoff y stop ante errores
│   │   └── simulator.py       # ⚠️ Simulador con datos hardcodeados (A REFACTORIZAR)
│   │
│   ├── collector/
│   │   ├── base.py            # Interfaz BaseCollector
│   │   ├── mock_collector.py  # Collector modo MOCK (usa simulator.py)
│   │   └── playwright_collector.py  # Collector modo PLAYWRIGHT (scraping real)
│   │
│   ├── db/
│   │   ├── database.py        # Conexión SQLite + operaciones CRUD
│   │   └── schema.sql         # Schema de la base de datos
│   │
│   ├── excel/
│   │   └── excel_io.py        # Import/export Excel con openpyxl
│   │
│   ├── models/
│   │   └── domain.py          # ⚠️ Modelos de dominio (sin uso actual)
│   │
│   ├── ui/
│   │   ├── app.py             # UI principal (Tkinter)
│   │   └── state.py           # ⚠️ Entry point duplicado (sin uso)
│   │
│   └── utils/
│       ├── money.py           # Conversión money_to_float / float_to_money_txt
│       └── time.py            # Helpers de timestamp
│
├── assets/
│   ├── sounds/                # Archivos de audio para alertas
│   └── icons/                 # Iconos de la aplicación
│
├── data/
│   └── monitor.db             # Base de datos SQLite (generada automáticamente)
│
├── scripts/
│   └── create_db.py           # Script de inicialización DB
│
└── tests/
    └── test_simulator.py      # Tests del simulador
```

## 🔑 API Principal (Clases y Funciones Clave)

### Core

#### `main.py`
- **`bootstrap_db()`**: Crea `data/monitor.db` y aplica schema SQL
- **`main()`**: Entry point - inicializa AppRuntime, UI, gestiona ciclo de vida

#### `app_runtime.py`
- **`AppRuntime`**: Orquestador central (Collector → Engine → UI)
  - `start()` → RuntimeHandles: Inicia threads del engine y collector
  - `stop()`: Detiene collector y engine loop
  - `start_collector()`: Inicia Playwright on-demand desde UI
  - `update_renglon_excel()`, `update_renglon_config()`: Persistencia datos usuario
  - `export_excel()`, `import_excel()`: Integración Excel ↔ DB
  - `cleanup_data(mode)`: Limpieza logs/estados/all

#### `engine.py`
- **`Engine`**: Motor principal - persistencia, alertas, seguridad
  - `run_once()`: Consume evento, aplica reglas, emite logs agregados
  - Gestiona: `SNAPSHOT`, `UPDATE`, `HTTP_ERROR`, `END`
  - Emite control: `BACKOFF`, `STOP` vía `control_q`

#### `alert_engine.py`
- **`AlertEngine.decide()`**: Aplica reglas → AlertDecision (style, sound, hide, message)

#### `security.py`
- **`SecurityPolicy.evaluate()`**: Políticas backoff/pause/stop ante errores HTTP

#### `simulator.py` ⚠️ **A REFACTORIZAR**
- **`Simulator.tick()`**: Genera variaciones con datos hardcodeados
- **Problema**: Valores hardcodeados por toda la clase, lógica no previsible

### Collectors

- **`BaseCollector`**: Interfaz abstracta (start, stop, emit, running)
- **`MockCollector`**: Usa Simulator, emite eventos sintéticos
- **`PlaywrightCollector`**: Scraping real, captura renglones, monitoreo

### Database

- **`database.py`**: CRUD completo
  - Subastas: `upsert_subasta()`, `set_subasta_estado()`, `get_running_subasta_id()`
  - Renglones: `upsert_renglon()`, `upsert_renglon_estado()`
  - Config: `get/upsert_renglon_config()`, `get/set_ui_config()`
  - Excel: `get/upsert_renglon_excel()`, `fetch_export_rows()`
  - Limpieza: `cleanup_logs()`, `cleanup_states()`, `cleanup_all()`

### UI

- **`app.py`**: UI Tkinter principal
  - Tabla con columnas configurables (persistidas en DB)
  - Acciones: abrir navegador, capturar, import/export Excel, editar fila, limpieza

### Utils

- **`money.py`**: `money_to_float()`, `float_to_money_txt()`
- **`time.py`**: `now_iso()`, `now_hhmmss()`

---

## ⚠️ Problemas Identificados

### Datos Hardcodeados en Simulador

**Ubicación**: `app/core/simulator.py`

**Problemas**:
1. Valores base inventados línea 119: `base_best = 18_000_000.0 + (int(rid) % 7) * 1_250_000.0`
2. Ofertas con datos ficticios hardcodeados (líneas 123-132)
3. RNG con semilla fija (línea 176: `random.Random(12345)`)
4. Lógica de variación hardcodeada (1% por minuto)
5. Probabilidades de eventos hardcodeadas

**Consecuencia**: Es imposible predecir/controlar escenarios de prueba específicos

### 🚀 Solución en Desarrollo

Nueva arquitectura basada en JSON con **datos reales del portal**:

```
data/test_scenarios/
├── scenario_controlled_real.json    # ✅ Con responses reales
├── scenario_basic.json              # Escenario básico
├── scenario_price_war.json          # Precios volátiles
├── scenario_http_errors.json        # Errores HTTP
└── scenario_specific_timeline.json  # Timeline exacto
```

**Ventajas**:
- ✅ Logs 100% predecibles
- ✅ Copy/paste directo desde DevTools del portal
- ✅ Control exacto de hora + status HTTP + cambios
- ✅ Escenarios reproducibles sin tocar código

**Documentación**:
- 📋 [PLAN_REFACTOR_SIMULATOR.md](PLAN_REFACTOR_SIMULATOR.md) - Plan completo de refactorización
- 📖 [GUIA_CAPTURA_DATOS.md](GUIA_CAPTURA_DATOS.md) - Cómo capturar datos reales del portal

---

## 🚀 Instalación y Uso

### Requisitos
- Python 3.10+
- Playwright (para modo PLAYWRIGHT)

### Instalación

```bash
# Clonar repositorio
git clone <repo_url>
cd monitor_subastas

# Instalar dependencias
pip install -r requirements.txt

# Inicializar base de datos
python scripts/create_db.py
```

### Ejecución

```bash
# Modo MOCK (simulador)
python main.py --mode MOCK

# Modo PLAYWRIGHT (navegador real)
python main.py --mode PLAYWRIGHT --headless

# Con escenario JSON personalizado (próximamente)
python main.py --mode MOCK --scenario data/test_scenarios/scenario_price_war.json
```

---

## 🧪 Testing

```bash
# Ejecutar tests
python -m pytest tests/

# Test específico del simulador
python -m pytest tests/test_simulator.py -v
```

---

## 📚 Documentación Adicional

- [Plan de Refactorización del Simulador](PLAN_REFACTOR_SIMULATOR.md)
- [Schema de Base de Datos](app/db/schema.sql)
- [Escenarios de Prueba](data/test_scenarios/)

---

## 🤝 Contribución

Este proyecto está en desarrollo activo. Consulta el [plan de refactorización](PLAN_REFACTOR_SIMULATOR.md) para conocer las próximas mejoras.

---

## 📝 Licencia

[Especificar licencia]
