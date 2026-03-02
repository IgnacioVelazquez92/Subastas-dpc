# Monitor de Subastas Electrónicas

> **v1.1**  Aplicación de escritorio para el monitoreo avanzado de subastas electrónicas en tiempo real del portal e-Commerce de la provincia de Córdoba (Argentina).

Proporciona una **interfaz visual moderna** como alternativa al portal oficial, con capacidades que el portal no ofrece:

| Capacidad | Descripción |
|---|---|
| Seguimiento automático | Captura cambios de precio cada N segundos vía Playwright |
| Polling HTTP directo | `HttpMonitor` usa `httpx` directo después de la captura inicial para bajar latencia |
| Alertas configurables | Notificaciones visuales y sonoras ante cambios relevantes |
| Gestión Excel | Importa costos, exporta resultados con columnas calculadas |
| Histórico completo | Persiste todos los cambios y ofertas en SQLite |
| Renglones compuestos | Contempla renglones con múltiples ítems usando `items_por_renglon` |
| Filtros y ordenamiento | Vistas personalizadas, filtros rápidos, columnas configurables |
| Modo testing | Escenarios JSON reproducibles para desarrollo sin portal real |

---

## Inicio Rápido

### Producción  Playwright (navegador real)

```bash
python main.py --mode PLAYWRIGHT --poll-seconds 5
```

### Producción  Playwright + HttpMonitor

```bash
python main.py --mode PLAYWRIGHT --poll-seconds 1 --use-http-monitor
```

### Testing local  MOCK (escenarios ficticios)

```bash
python main.py --mode MOCK --scenario "data/test_scenarios/scenario_controlled_real.json" --poll-seconds 5
```

---

## Instalación

**Requisitos:** Python 3.10+ y pip.

```bash
# 1. Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate        # Windows

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Instalar navegadores de Playwright
playwright install chromium

# 4. Inicializar la base de datos (solo primera vez)
python scripts/create_db.py
```

La base de datos `data/monitor.db` también se crea automáticamente al ejecutar `main.py`.

---

## Argumentos CLI

| Argumento | Tipo | Default | Descripción |
|---|---|---|---|
| `--mode` | `PLAYWRIGHT` / `MOCK` | `MOCK` | Fuente de datos |
| `--scenario` | path |  | JSON de escenario (requerido en MOCK) |
| `--poll-seconds` | float | `1.0` | Intervalo de polling en segundos |
| `--headless` | flag | off | Playwright sin ventana de navegador |
| `--use-http-monitor` | flag | off | Activa `httpx` directo para el polling luego de capturar la subasta |

### Ejemplos

```bash
# Producción visible
python main.py --mode PLAYWRIGHT --poll-seconds 5

# Producción visible con httpx directo
python main.py --mode PLAYWRIGHT --poll-seconds 1 --use-http-monitor

# Producción headless
python main.py --mode PLAYWRIGHT --headless --poll-seconds 10

# MOCK: escenario de guerra de precios
python main.py --mode MOCK --scenario "data/test_scenarios/scenario_price_war.json" --poll-seconds 2

# MOCK: escenario con datos reales capturados
python main.py --mode MOCK --scenario "data/test_scenarios/scenario_controlled_real.json" --poll-seconds 5
```

---

## Arquitectura

```
+-----------------------------------------------------------+
|                         main.py                           |
|   bootstrap_db() -> AppRuntime.start() -> App().mainloop  |
+------------------+-----------------------------+----------+
                   | control_q / eventos         | handles
                   v                             v
  +--------------------+             +------------------------+
  |      Collector     | eventos ->  |        Engine          |
  |   (thread propio)  | ----------> |    (thread propio)     |
  |                    |             |  - Persiste en SQLite  |
  |  PLAYWRIGHT:       |             |  - AlertEngine         |
  |   Chromium +       |             |  - SecurityPolicy      |
  |   scraping real    |             |  - Emite a UI          |
  |                    |             +----------+-------------+
  |  MOCK:             |                        | eventos procesados
  |   SimulatorV2 +    |                        v
  |   JSON scenario    |             +------------------------+
  +--------------------+             |      UI (Tkinter)      |
                                     |  - Tabla de renglones  |
                                     |  - Logger widget       |
                                     |  - LED de estado       |
                                     |  - Diálogos edicion    |
                                     +------------------------+
```

**Principio clave:** cada capa solo conoce a la siguiente; la comunicación es via eventos tipados (`EventType`).

### Backend de monitoreo en modo PLAYWRIGHT

Hay dos backends posibles para el loop de polling:

- `PLAYWRIGHT_PAGE`: hace `fetch` desde Chromium usando `page.evaluate(...)`.
- `HTTPX_DIRECT`: usa `HttpMonitor` con `httpx` reutilizando cookies capturadas por Playwright.

Regla vigente:

- El switch `HTTP Monitor` de la UI tiene prioridad sobre el backend activo.
- Si está activado, el collector usa `HTTPX_DIRECT`.
- Si está desactivado, vuelve a `PLAYWRIGHT_PAGE`.
- El cambio puede aplicarse en caliente si ya hay una subasta capturada y monitoreo activo.
- El modo `INTENSIVA` / `SUEÑO` se mantiene independientemente del backend.

### Ciclo operativo completo del MVP

La UI ya soporta el flujo completo de trabajo:

- `Abrir navegador`: abre o reutiliza la sesión de Playwright.
- `Capturar actual`: toma la subasta visible en el navegador y empieza a monitorearla con el backend prioritario actual.
- `Detener`: pausa la supervisión sin cerrar navegador ni perder la captura.
- `Reanudar`: retoma la supervisión de la captura actual.

Comportamiento al reanudar:

- Si seguís parado en la misma subasta, reanuda directamente.
- Si dejaste el navegador en otra subasta, el collector la recaptura antes de retomar.
- Si no hay subasta capturada y tampoco estás parado en una subasta válida, la app te pide hacer `Capturar actual`.

Importante:

- Navegar manualmente a otra subasta en Chromium no cambia por sí solo la subasta monitoreada.
- Para que el backend activo monitoree la nueva subasta, hay que hacer `Capturar actual` nuevamente.
- Ese recapture refresca `id_cot`, `renglones`, `subasta_url` y cookies de sesión.
- Si el monitoreo estaba pausado, `Reanudar` también puede hacer esa recaptura automáticamente si detecta otra subasta abierta.

### Eventos del sistema (`app/core/events.py`)

| Evento | Emitido por | Descripción |
|---|---|---|
| `SNAPSHOT` | Collector | Estado completo inicial de la subasta |
| `UPDATE` | Collector | Cambio detectado en un renglon |
| `HEARTBEAT` | Collector | Pulso periódico, sin cambios |
| `ALERT` | Engine | Alerta de negocio (cambio significativo) |
| `HTTP_ERROR` | Collector | Error de conexión con el portal |
| `SECURITY` | Engine | Backoff activado por errores acumulados |
| `START` / `STOP` / `END` | Engine | Ciclo de vida de la sesión |

---

## Estructura del Proyecto

```
monitor_subastas/
 main.py                        # Entry point: CLI -> DB -> AppRuntime -> UI
 requirements.txt
 README.md
 AGENTS.md                      # Contexto para agentes IA / onboarding

 app/
    core/
       app_runtime.py         # Orquestador central (threads + queues)
       engine.py              # Motor: persiste + alertas + seguridad -> UI
       events.py              # Contratos de eventos (dataclasses + Enum)
       alert_engine.py        # Reglas: estilo, sonido, visibilidad
       security.py            # Backoff progresivo ante errores HTTP
       simulator_v2.py        # Reproduce escenarios JSON (MOCK)
       scenario_loader.py     # Carga y valida archivos JSON
   
    collector/
       base.py                # Interfaz BaseCollector
       mock_collector.py      # Collector MOCK -> SimulatorV2
       playwright_collector.py# Collector producción (Chromium + orquestación de backend)
       http_monitor.py        # Polling HTTP directo con httpx
   
    db/
       database.py            # Clase Database: SQLite CRUD + init_schema
       schema.sql             # DDL completo
   
    excel/
       excel_io.py            # Importar / exportar con openpyxl
   
    models/
       domain.py              # Dataclasses: Subasta, Renglon, RenglonEstado
   
    ui/
       app.py                 # Ventana principal (CustomTkinter)
       column_manager.py      # Configuración de columnas con persistencia
       event_handler.py       # Despacha eventos del Engine a la UI
       formatters.py          # Formateo de celdas (colores, porcentajes, $)
       improved_logger.py     # Widget logger mejorado
       led_indicator.py       # Indicador LED de estado de conexión
       logger_widget.py       # Widget logger base
       row_editor.py          # Diálogo de edición de renglon
       state.py               # Estado mutable de la UI
       table_manager.py       # Gestión de la tabla (insertar/actualizar/ordenar)
       views/                 # Vistas secundarias
   
    utils/
        audio.py               # Reproducción de alertas sonoras + generación WAV
        money.py               # money_to_float / float_to_money_txt
        time.py                # Helpers de timestamp

 assets/
    sounds/                    # WAV de alertas (generados automáticamente)
    icons/

 data/
    monitor.db                 # SQLite (auto-generada)
    test_scenarios/            # JSONs para modo MOCK
        scenario_basic.json
        scenario_controlled_real.json
        scenario_http_errors.json
        scenario_price_war.json
        scenario_specific_timeline.json

 docs/                          # Documentación técnica y decisiones de diseño
 scripts/
    create_db.py               # Script standalone de inicialización DB
 tests/                         # Suite de tests unitarios e integración
```

---

## Funcionalidades de la UI

### Tabla de Renglones

Cada fila representa un renglon de subasta con las siguientes columnas clave:

| Columna | Descripción |
|---|---|
| Renglón | ID y descripción del ítem |
| Items x Renglón | Cantidad de ítems/productos que componen el renglón |
| Mejor Oferta | Precio líder actual del portal |
| Presupuesto Oficial | Total oficial del renglón publicado por el portal |
| Precio de Referencia | Valor unitario de referencia derivado correctamente |
| Costo Unitario / Total | Importados desde Excel |
| Renta a Mejorar % | Margen calculado respecto a la mejor oferta |
| USD | Equivalente en dólares (cotización configurable) |
| Seguimiento | Si el renglon está marcado para alertas |

La columna `Items x Renglón` puede mostrarse desde la configuración de columnas para auditar rápido subastas donde un renglón agrupa varios productos.

### Fórmula general de cálculo

Cuando un renglón tiene más de un ítem, la fórmula base deja de ser `cantidad * precio_unitario = total` usando `cantidad` directa. La regla correcta es:

```text
cantidad_equivalente = cantidad / items_por_renglon

PRESUPUESTO OFICIAL = PRECIO DE REFERENCIA * cantidad_equivalente
PRECIO DE REFERENCIA = PRESUPUESTO OFICIAL / cantidad_equivalente
PRECIO UNIT MEJORA = OFERTA PARA MEJORAR / cantidad_equivalente
COSTO TOTAL ARS = COSTO UNIT ARS * cantidad_equivalente
```

Eso afecta todos los cálculos de unitarios y totales del sistema. `oferta_para_mejorar` sigue siendo el valor total del renglón, pero el dato útil para ofertar es `precio_unit_mejora`, calculado con la misma `cantidad_equivalente`.

### Filtros Rápidos

- **Ocultar vacías**: elige una columna y oculta filas sin valor
- **Solo con costo**: muestra únicamente renglones con costo cargado
- **Solo seguimiento**: muestra solo renglones marcados como seguimiento
- **Solo en carrera**: oculta renglones donde `renta_para_mejorar < renta_minima`

### Ordenamiento

Click en cualquier header para ordenar. La columna `Renta a Mejorar %` ordena numéricamente incluso con formato porcentual.

### Seguimiento de Renglones

El modo de seguimiento activa alertas visuales y sonoras sobre un renglon:

1. Seleccionar renglon  **Opciones  Editar renglon**
2. Marcar **"Seguir este renglon"**  Guardar

El renglon pasa a estilo `TRACKED` (fondo celeste) y recibe alertas ante cambios significativos de precio.

### Indicadores visuales

- LED `HTTP`: parpadea ante respuestas exitosas y errores HTTP de ambos backends.
- LED `Ofertas`: refleja cambios reales de oferta detectados por el sistema.
- Columna `LED`: muestra actividad por renglón y también responde durante monitoreo por `httpx`.
- Botón `Reanudar`: permite volver a supervisar sin reiniciar todo el runtime ni relanzar el navegador.

### Logs operativos

Los logs de consola identifican explícitamente el backend activo:

```text
[PERF] backend=PLAYWRIGHT_PAGE ...
[HttpMonitor][PERF] backend=HTTPX_DIRECT ...
```

Esto permite confirmar rápido:

- si el polling lo hace Chromium o `httpx`
- si las requests están devolviendo `200`
- si hubo errores, timeouts o cambios de backend

---

## Gestión Excel

### Importar costos

Cargar un Excel con columnas de costo unitario/total y observaciones. Los datos se asocian por `id_renglon` y persisten en la BD.

### Exportar resultados

Genera un Excel con todos los renglones, sus precios capturados, `ITEMS POR RENGLON`, costos y columnas calculadas (renta, totales, USD).

---

## Modelos de Dominio (`app/models/domain.py`)

```python
Subasta          # Una subasta: id_cot, url, estado, proveedor propio
Renglon          # Un ítem dentro de una subasta: id_renglon, descripción
RenglonEstado    # Estado actual: mejor_oferta, mi_oferta, historico de cambios
```

---

## Tests

```bash
# Ejecutar toda la suite
python -m pytest tests/ -v

# Tests específicos
python -m pytest tests/test_mock_v2_integration.py -v
python -m pytest tests/test_formatters_parse_float.py -v
python -m pytest tests/test_renta_format_v2.py -v
```

### Escenarios MOCK disponibles

| Archivo | Descripción |
|---|---|
| `scenario_basic.json` | Caso base, pocos renglones |
| `scenario_controlled_real.json` | Datos reales capturados del portal |
| `scenario_price_war.json` | Cambios rápidos de precio (stress test alertas) |
| `scenario_http_errors.json` | Simula fallos de red y backoff |
| `scenario_specific_timeline.json` | Timeline con eventos en tiempos exactos |

---

## Dependencias

| Paquete | Versión | Uso |
|---|---|---|
| `customtkinter` | 5.2.2 | UI moderna sobre Tkinter |
| `playwright` | 1.58.0 | Scraping del portal (modo PLAYWRIGHT) |
| `openpyxl` | 3.1.5 | Import/export Excel |
| `darkdetect` | 0.8.0 | Detección del tema del sistema |

---

## Documentación Técnica

Ver carpeta [`docs/`](docs/) para guías detalladas:

- [GUIA_CAPTURA_DATOS.md](docs/GUIA_CAPTURA_DATOS.md)  Cómo capturar datos reales para escenarios
- [GUIA_FORMATO_RENTA.md](docs/GUIA_FORMATO_RENTA.md)  Lógica de cálculo de renta
- [GUIA_MANTENCION_UI.md](docs/GUIA_MANTENCION_UI.md)  Mantenimiento y extensión de la UI
- [VERIFICACION_CALCULOS.md](docs/VERIFICACION_CALCULOS.md)  Validación de fórmulas de negocio
- [USO_ESCENARIOS_V2.md](docs/USO_ESCENARIOS_V2.md)  Formato y uso de escenarios JSON

---

## Licencia

Uso privado  proyecto propietario.
