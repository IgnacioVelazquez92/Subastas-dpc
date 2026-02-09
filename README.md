# Monitor de Subastas Electrónicas

Aplicación de escritorio para monitoreo avanzado de subastas electrónicas en tiempo real del portal e-Commerce de la provincia de Córdoba. 

Proporciona una **alternativa visual moderna** al portal oficial con:
- Seguimiento automático de cambios de precios
- Sistema de alertas configurables
- Exportación/importación de datos a Excel
- Persistencia de históricos en SQLite
- Ordenamiento y filtros rápidos en la UI

---

## 🚀 Ejecución Rápida

### Producción (Playwright - Navegador Real)
```bash
python main.py --mode PLAYWRIGHT --poll-seconds 5
```

### Testing Local (MOCK - Escenarios Ficticios)
```bash
python main.py --mode MOCK --scenario "data/test_scenarios/scenario_controlled_real.json" --poll-seconds 5
```

---

## 🎯 Arquitectura

**Flujo principal:** `Collector → Engine → UI` | `Engine → SQLite`

### Componentes

- **Collector**: Obtiene datos del portal real (Playwright) y emite eventos normalizados
- **Engine**: Persiste en DB, aplica reglas de alertas/seguridad, emite eventos procesados
- **UI**: Presenta información en tiempo real, permite edición de datos, dispara acciones (captura, Excel, limpieza)
- **DB**: SQLite para observabilidad, histórico de cambios, configuración y datos Excel

## ✅ Funcionalidades

### Monitoreo en Tiempo Real
- **Seguimiento automático**: Captura cambios de precios cada N segundos
- **Alertas**: Notificaciones visuales/sonoras ante cambios significativos
- **Histórico**: Persistencia de todos los cambios en SQLite
- **USD persistente**: Conversión y costos USD se mantienen en BD y UI

### Gestión de Datos Excel
- **Importación**: Carga datos de costos y observaciones desde Excel
- **Exportación**: Descarga de renglones con precios capturados y totales
- **Edición**: Modifica datos directamente desde la UI

### Control y Configuración
- **Columnas configurables**: Personaliza vista con persistencia en BD
- **Limpieza de datos**: Gestión de logs y estados históricos
- **Control de ejecución**: Supervisión del ciclo de vida del monitoreo
- **Ordenamiento**: Click en headers (incluye Renta a Mejorar %)
- **Filtros rápidos**: Ocultar vacíos por columna, solo con costo, solo seguimiento

## 📁 Estructura del Proyecto

```
monitor_subastas/
├── main.py                    # Entry point principal
├── requirements.txt           # Dependencias Python
├── README.md
│
├── app/
│   ├── core/
│   │   ├── app_runtime.py     # Orquestador: Collector → Engine → UI
│   │   ├── engine.py          # Motor: persistencia + alertas + seguridad
│   │   ├── events.py          # Contratos de eventos
│   │   ├── alert_engine.py    # Reglas de alertas (estilos, sonidos)
│   │   ├── security.py        # Políticas de backoff ante errores
│   │   ├── simulator_v2.py    # Simulador con escenarios JSON (testing)
│   │   └── scenario_loader.py # Carga escenarios JSON
│   │
│   ├── collector/
│   │   ├── base.py            # Interfaz BaseCollector
│   │   ├── mock_collector.py  # Collector MOCK (escenarios JSON para UI testing)
│   │   └── playwright_collector.py  # Collector PLAYWRIGHT (producción)
│   │
│   ├── db/
│   │   ├── database.py        # Conexión SQLite + CRUD
│   │   └── schema.sql         # Schema de la base de datos
│   │
│   ├── excel/
│   │   └── excel_io.py        # Import/export Excel
│   │
│   ├── ui/
│   │   └── app.py             # UI principal (Tkinter/CustomTkinter)
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
│   ├── monitor.db             # Base de datos SQLite (generada automáticamente)
│   └── test_scenarios/        # Escenarios JSON para testing MOCK
│
├── scripts/
│   └── create_db.py           # Script de inicialización DB
│
└── tests/
    ├── test_mock_v2_integration.py
    └── test_scenario_loader.py
```

## 🔑 Componentes Clave en Producción

### `main.py`
- **Entry point**: Parsea CLI, inicializa DB, crea AppRuntime y lanza UI
- **CLI arguments**:
  - `--mode PLAYWRIGHT`: Modo producción con navegador real
  - `--mode MOCK`: Modo testing con escenarios JSON (desarrollo)
  - `--poll-seconds`: Intervalo de chequeo (default: 1.0)
  - `--headless`: Ejecuta Playwright sin UI del navegador

### `app_runtime.py`
- **AppRuntime**: Orquestador central
  - `start()`: Inicia Engine y Collector en threads separados
  - `stop()`: Detiene gracefully ambos componentes
  - `update_renglon_excel()`, `export_excel()`, `import_excel()`: Operaciones Excel
  - `cleanup_data()`: Limpieza de logs y históricos

### `engine.py`
- **Engine**: Motor de persistencia y procesamiento
  - Consume eventos del Collector normalizados
  - Aplica reglas de alertas (AlertEngine)
  - Persiste cambios en SQLite
  - Emite eventos procesados a UI

### `playwright_collector.py`
- **PlaywrightCollector**: Captura automática del portal
  - Ejecuta browser automático en background
  - Emite SNAPSHOT (estado inicial) y UPDATE (cambios) en tiempo real
  - Emite HTTP_ERROR ante fallos de conexión
  - Control via control_q desde AppRuntime

### `alert_engine.py`
- **AlertEngine**: Decisiones de alertas
  - Evalúa cambios de precios vs reglas configuradas
  - Decides: sonido, color, visibilidad, mensaje

### `security.py`
- **SecurityPolicy**: Manejo inteligente de errores
  - Backoff progresivo ante fallos HTTP
  - Stop automático si excede límites

### `database.py`
- **Operaciones principales**:
  - Persistencia de subastas y renglones
  - Histórico de cambios y ofertas
  - Configuración de UI (columnas, preferencias)
  - Datos Excel (costos, observaciones)

---

## 🛠 Instalación

### Requisitos
- Python 3.10+
- pip

### Pasos

```bash
# Clonar repositorio
git clone <repo_url>
cd monitor_subastas

# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Inicializar base de datos
python scripts/create_db.py
```

## 🚀 Uso

### Modo Producción (Playwright)
```bash
# Monitoreo normal (UI del navegador visible)
python main.py --mode PLAYWRIGHT --poll-seconds 5

# Modo headless (sin UI del navegador)
python main.py --mode PLAYWRIGHT --headless --poll-seconds 5
```

### Modo Testing (MOCK con Escenarios JSON)
Para desarrollar/testear la UI sin acceso a subastas reales:

```bash
# Escenario controlado con datos reales
python main.py --mode MOCK --scenario "data/test_scenarios/scenario_controlled_real.json" --poll-seconds 5
```

**Nota**: MOCK es **solo para testing de UI**. En producción el lunes usarás PLAYWRIGHT.

## 🧰 UI: Ordenamiento y Filtros

- **Ordenar por Renta a Mejorar %**: click en el header de la columna `Renta a Mejorar %`.
- **Ocultar vacías**: permite elegir una columna y ocultar filas sin valor.
- **Solo con costo**: muestra únicamente renglones con costo unitario o total.
- **Solo seguimiento**: filtra renglones marcados como seguimiento.
- **Solo en carrera**: oculta renglones donde `renta_para_mejorar` < `renta_minima` (fuera de umbral).

## 📊 Cómo Hacer Seguimiento

El seguimiento activa alertas visuales/sonoras en un renglón. Para hacerlo:

1. **Selecciona renglón** en la tabla (click)
2. **Abre Opciones → Editar renglón** (o botón en la barra)
3. En el diálogo, marca el **checkbox "Seguir este renglón"**
4. Confirma y guarda

A partir de ese momento:
- El renglón cambia de estilo a **TRACKED** (fondo celeste)
- Recibirá alertas si el precio cambia significativamente
- Filtro **"Solo seguimiento"** lo mantiene visible cuando está activo

## ℹ️ Información Adicional

### Para Testing (Desarrollo de UI)
Los escenarios JSON en `data/test_scenarios/` contienen respuestas reales capturadas del portal. Úsalos para desarrollar/validar la UI sin depender de subastas reales.

### Captura de Datos Reales
Para crear nuevos escenarios con datos reales del portal, consulta [GUIA_CAPTURA_DATOS.md](GUIA_CAPTURA_DATOS.md).

---

## 📝 Licencia

[Especificar licencia]
