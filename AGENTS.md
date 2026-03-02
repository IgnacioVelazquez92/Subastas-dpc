# AGENTS.md — Contexto para Agentes IA

> Este archivo es el punto de partida para cualquier agente IA o colaborador nuevo que trabaje en este proyecto.
> Se actualiza a medida que evolucionan decisiones de diseño, convenciones y contexto del dominio.

---

## Resumen Ejecutivo

**Monitor de Subastas Electrónicas** es una aplicación de escritorio Python que monitorea en tiempo real el portal de subastas e-Commerce de la provincia de Córdoba (Argentina). El sistema captura automáticamente cambios de precios usando Playwright, los persiste en SQLite, aplica reglas de alertas y los muestra en una UI de escritorio moderna (CustomTkinter).

**Estado actual:** v1.1 — se agregó `HttpMonitor`, un monitor de polling HTTP directo (httpx) que reemplaza el loop de Chromium para el monitoreo intensivo. Playwright sigue siendo responsable del browse + capture inicial; solo el loop de polling es reemplazado por httpx, logrando latencias de 0.2–2s vs 3–20s.

---

## Dominio del Problema

### Contexto de negocio

- El usuario participa como **proveedor** en subastas electrónicas de compras públicas.
- Las subastas son competitivas: múltiples proveedores hacen ofertas en tiempo real.
- El portal solo muestra el precio líder actual, sin historial ni alertas.
- El usuario necesita saber **cuándo cambió el precio líder** y si su oferta sigue siendo competitiva.
- Concepto clave: **"Renta a Mejorar %"** = cuánto margen hay entre el precio líder y el costo propio.

### Entidades del dominio

```
Subasta
  ├── id_cot          → ID de la cotización en el portal (string, no int)
  ├── url             → URL completa de la subasta
  ├── estado          → RUNNING | PAUSED | ENDED | ERROR
  └── mi_id_proveedor → ID del proveedor propio en esta subasta (varía por subasta)

Renglon (ítem dentro de una subasta)
  ├── id_renglon      → ID del renglón en el portal (string)
  ├── descripcion     → Descripción del bien/servicio
  └── margen_minimo   → Margen mínimo aceptable (configurable)

RenglonEstado (lectura actual del portal)
  ├── mejor_oferta    → Precio líder actual
  ├── mi_oferta       → Mi precio actual
  ├── cantidad        → Cantidad licitada
  ├── costo_unitario  → Importado desde Excel
  ├── costo_total     → Calculado: costo_unitario * cantidad
  ├── renta_para_mejorar → Calculado: ((mi_oferta / costo_total) - 1) * 100
  └── seguimiento     → bool: si tiene alertas activas
```

---

## Arquitectura del Sistema

### Flujo de datos

Modo estándar (Playwright puro):
```
[Portal web] --Playwright/Chromium--> [PlaywrightCollector._monitor_loop]
                                              |
                                      eventos (Queue)
                                              |
                                              v
                                       [Engine]
                                        /     \
                                  [SQLite]   [AlertEngine]
                                              |
                                      eventos procesados (Queue)
                                              |
                                              v
                                          [UI App]
```

Modo híbrido (use_http_monitor=True — RECOMENDADO para producción):
```
[Portal web] --Playwright/Chromium--> [PlaywrightCollector._capture_current]
                                              |
                           extrae: id_cot, renglones, cookies de sesión
                                              |
                                              v
                               [HttpMonitor.run()]  ← httpx directo, sin Chromium
                          POST BuscarOfertas (hasta 30 req. paralelas)
                                              |
                                      eventos (Queue)  ← mismo formato
                                              |
                                              v
                                       [Engine] → [UI App]  ← sin cambios
```

En modo híbrido, Chromium **queda abierto** pero en reposo: el usuario puede seguir navegando manualmente. Si la sesión httpx expira (401/403 × 5), `HttpMonitor` emite `WARN(EXCEPTION, "sesión expirada")` y se detiene; el usuario puede hacer `capture_current` de nuevo para refrescar cookies.

### Threading

- **Main thread**: UI (Tkinter — obligatorio, no puede moverse)
- **Thread Collector**: corre el loop asyncio de Playwright (`asyncio.run(_main())`)
  - Dentro del loop asyncio corre como tarea: `HttpMonitor.run()` (modo híbrido) o `_monitor_loop()` (modo estándar)
- **Thread Engine**: consume la queue del Collector, procesa y emite a la queue de la UI
- **UI polling**: `app.py` usa `after()` para consumir la queue del Engine sin bloquear la UI

Nota: `HttpMonitor` corre como `asyncio.Task` dentro del mismo event loop del Thread Collector, sin threads adicionales.

### Comunicación entre capas

Toda comunicación entre Collector → Engine → UI es via **colas de eventos** (`queue.Queue`). Los eventos son instancias de dataclasses definidas en `app/core/events.py`. **No hay llamadas directas entre capas**, solo put/get en colas.

---

## Convenciones de Código

### Estilo general

- Python 3.10+ con `from __future__ import annotations`
- Dataclasses para modelos (`@dataclass`, `@dataclass(frozen=True)` para inmutables)
- Type hints en todas las funciones públicas
- Docstrings en módulos que explican su rol (ver `events.py`, `domain.py` como referencia)

### Nomenclatura

| Contexto | Convención |
|---|---|
| IDs del portal | Siempre `str`, nunca `int` (p.ej. `id_cot`, `id_renglon`) |
| Nombres de módulos | `snake_case` |
| Clases | `PascalCase` |
| Eventos | `EventType.UPPER_CASE` |
| Columnas UI | Texto en español con espacios (p.ej. `"Renta a Mejorar %"`) |
| Columnas DB | `snake_case` (p.ej. `renta_para_mejorar`) |

### Manejo de dinero

Siempre usar las utilidades de `app/utils/money.py`:

```python
from app.utils.money import money_to_float, float_to_money_txt

# Parsear texto del portal ("$ 1.234,56") a float
valor = money_to_float("$ 1.234,56")   # → 1234.56

# Formatear float para mostrar en UI
texto = float_to_money_txt(1234.56)    # → "$ 1.234,56"
```

**No hardcodear** lógica de formato monetario en otros lugares.

### Porcentajes / Renta

El cálculo de `renta_para_mejorar` está centralizado. Ver `docs/GUIA_FORMATO_RENTA.md` y `docs/VERIFICACION_CALCULOS.md` antes de modificar cualquier fórmula de negocio.

### Base de datos

- Conexión y todas las operaciones en `app/db/database.py`
- El schema está en `app/db/schema.sql`
- **Nunca** escribir SQL directamente en capas de negocio o UI
- `Database.init_schema()` es idempotente (usa `CREATE TABLE IF NOT EXISTS`)

---

## Modos de Ejecución

### PLAYWRIGHT estándar (Chromium puro)

- Usa `PlaywrightCollector` con `use_http_monitor=False` (default actual)
- Cada request del portal pasa por Chromium: Python → asyncio → page.evaluate → fetch → portal
- Latencia por ciclo (20 renglones): 3–20 segundos
- `autostart_collector=False` — el usuario debe iniciar manualmente desde la UI (botón Start)

### PLAYWRIGHT + HttpMonitor (modo híbrido — recomendado para producción)

- Usa `PlaywrightCollector` con `use_http_monitor=True`
- Chromium sigue activo para browse + capture (extrae cookies de sesión ASP.NET)
- Una vez capturado, el polling lo hace `HttpMonitor` (httpx directo)
- Activar en `app_runtime.py`: `AppRuntime(..., use_http_monitor=True, http_concurrent_requests=10)`
- O en caliente: `collector.set_http_monitor_mode(True)` (efecto en el próximo capture)
- Latencia por ciclo (20 renglones): 0.2–2 segundos
- Concurrencia configurable: hasta 30 requests en paralelo
- Modos INTENSIVA y SUEÑO disponibles (igual que el sistema original)

#### Parámetros de HttpMonitor

| Parámetro | Tipo | Default | Descripción |
|---|---|---|---|
| `use_http_monitor` | bool | False | Activar modo híbrido |
| `http_concurrent_requests` | int | 5 | Requests paralelos (max 30) |
| `request_timeout_s` | float | 2.5 | Timeout en modo INTENSIVA |
| `relaxed_timeout_s` | float | 5.0 | Timeout en modo SUEÑO |

### MOCK (desarrollo/testing)

- Usa `MockCollector` que delega en `SimulatorV2`
- `SimulatorV2` reproduce un escenario JSON con timeline de eventos
- `autostart_collector=True` — arranca solo al lanzar
- Los JSONs en `data/test_scenarios/` son la fuente de verdad para tests

---

## Testing

### Suite de tests

```bash
python -m pytest tests/ -v
```

### Tests importantes

| Archivo | Qué prueba |
|---|---|
| `test_mock_v2_integration.py` | Integración completa Collector → Engine con MOCK |
| `test_scenario_loader.py` | Carga y validación de escenarios JSON |
| `test_formatters_parse_float.py` | Parseo de formatos monetarios del portal |
| `test_renta_format_v2.py` | Lógica de cálculo y formato de renta |
| `test_export_import.py` | Ciclo completo de Excel export/import |
| `test_headers.py` | Configuración y persistencia de columnas |
| `test_calculos.py` | Fórmulas de negocio (renta, costos, USD) |

### Cómo crear un nuevo escenario MOCK

Ver `docs/GUIA_CAPTURA_DATOS.md`. El formato básico:

```json
{
  "meta": { "description": "...", "id_cot": "12345" },
  "timeline": [
    { "t": 0, "event": "SNAPSHOT", "renglones": [...] },
    { "t": 5, "event": "UPDATE", "id_renglon": "1", "mejor_oferta": "$ 1.000,00" }
  ]
}
```

---

## UI — Decisiones de Diseño

### Framework

- **CustomTkinter** sobre Tkinter estándar: permite temas oscuros/claros, widgets modernos
- La UI **solo vive en el main thread** (restricción de Tkinter)
- Para actualizaciones desde otros threads: `root.after(0, callback)`

### Estructura de la UI (`app/ui/`)

| Módulo | Responsabilidad |
|---|---|
| `app.py` | Ventana principal, menús, layout, loop de eventos |
| `table_manager.py` | Insertar, actualizar y ordenar filas en la tabla |
| `event_handler.py` | Translate `EventType` → acciones en la UI |
| `formatters.py` | Colores de fila, formato de celdas |
| `column_manager.py` | Qué columnas se muestran y en qué orden (persiste en DB) |
| `row_editor.py` | Diálogo modal para editar un renglón |
| `state.py` | Estado mutable compartido de la UI (filtros activos, selección, etc.) |
| `led_indicator.py` | LED de estado: verde=OK, amarillo=warning, rojo=error |
| `improved_logger.py` | Panel de log inferior con niveles y colores |

### Estilos de fila

Los estilos se definen en `alert_engine.py` y se aplican en `formatters.py`:

| Estilo | Color | Significado |
|---|---|---|
| `NORMAL` | Blanco/gris | Sin cambios |
| `TRACKED` | Celeste | Renglón en seguimiento |
| `ALERT_UP` | Rojo suave | Precio subió |
| `ALERT_DOWN` | Verde suave | Precio bajó (oportunidad) |
| `WINNER` | Verde intenso | Soy el precio más bajo |
| `LOSER` | Naranja | Fui superado |

---

## Decisiones Técnicas Tomadas

### Por qué SQLite y no otro DB

- Aplicación de escritorio local, sin necesidad de servidor
- Simplicidad de instalación (no requiere setup adicional)
- Suficiente para el volumen de datos (< 1000 renglones por subasta)

### Por qué eventos tipados y no dicts

- `EventType` + dataclasses evita bugs por typos en keys
- Facilita el testing (se puede instanciar un evento limpio)
- El IDE puede autocompletar y detectar errores

### Por qué threads y no asyncio

- Tkinter no es compatible con asyncio sin bridges complejos
- Playwright tiene su propio loop, más simple en thread separado
- Comunicación via `queue.Queue` es thread-safe nativamente

### Por qué dos modos (PLAYWRIGHT / MOCK)

- El portal real solo está disponible durante días de subasta
- MOCK permite desarrollar y testear la UI en cualquier momento
- Los escenarios JSON documentan casos de uso reales

### Por qué HttpMonitor en lugar de reescribir el collector

- `PlaywrightCollector` sigue siendo el responsable del browse + capture: el usuario navega normalmente en Chromium y nosotros extraemos los datos del DOM (id_cot, renglones, cookies)
- `HttpMonitor` es un módulo separado (`app/collector/http_monitor.py`) que el collector activa como `asyncio.Task` en el mismo event loop, sin afectar Engine/UI/DB
- El flag `use_http_monitor=False` por defecto: el colector Playwright original sigue siendo el fallback estable — regresión cero
- `httpx` async se integra limpio con el `asyncio.run()` existente del Thread Collector, sin threads adicionales ni cambios en la arquitectura de colas
- Emite exactamente los mismos `Event` con los mismos payloads: Engine y UI no notan la diferencia

### Por qué las peticiones no funcionaban desde Python/Postman antes

El endpoint `BuscarOfertas` es un `WebMethod` de ASP.NET ScriptManager. Requiere:
1. Cookies de sesión ASP.NET (`ASP.NET_SessionId`, etc.) — obtenidas al navegar con Chromium
2. Header `X-Requested-With: XMLHttpRequest` — presente en httpx ahora
3. Body JSON con `{id_Cotizacion, id_Item_Renglon, Margen_Minimo}` — conocido desde el análisis inicial

El problema original era que no teníamos las cookies de sesión. Ahora `_capture_current` las extrae de `page.context.cookies()` y las pasa a `HttpMonitor`.

---

## Contexto de la Colaboración IA

### Historial de decisiones documentadas

Ver `docs/` para el historial completo:

- `PLAN_REFACTOR_SIMULATOR.md` — Refactor del simulador de v1 a v2
- `REFACTOR_APP_COMPLETADO.md` — Refactor de la app principal
- `SOLUCION_HEADERS_DEFINITIVA.md` — Problema de headers en la tabla
- `BUGFIX_EXPORT_IMPORT.md` — Fix del ciclo export/import Excel
- `FORMATO_PORCENTAJES_V2.md` — Cambio en formato de porcentajes
- `PLAN_CAMBIOS_COLUMNAS.md` — Rediseño del sistema de columnas

### Áreas sensibles (cambiar con cuidado)

1. **`app/utils/money.py`** — Cualquier cambio rompe el parseo de datos del portal
2. **`app/db/schema.sql`** — Cambios requieren migración (hay `migrate_renta_format.py`)
3. **`app/core/events.py`** — Contrato entre capas; cambios requieren actualizar todos los consumidores
4. **Lógica de renta** — Fórmulas validadas en `docs/VERIFICACION_CALCULOS.md`
5. **Threading** — No llamar a widgets Tkinter desde threads secundarios
6. **`app/collector/http_monitor.py`** — `_parse_d_field` es una copia del de `PlaywrightCollector`; si el portal cambia el formato de respuesta, actualizar en ambos lugares
7. **Cookies de sesión** — se extraen en `_capture_current` vía `page.context.cookies()`. Si el portal agrega validación extra (CSRF token, `__RequestVerificationToken`), hay que extraerlos también del HTML en ese mismo método

### Qué está listo vs. qué falta

**Listo (v1.0):**
- Monitoreo en tiempo real con Playwright
- Sistema de alertas visual y sonoro
- Import/export Excel completo
- Historial en SQLite
- Filtros y ordenamiento en UI
- Suite de tests básica
- Modo MOCK con escenarios JSON
- Columnas configurables con persistencia

**Listo (v1.1):**
- `HttpMonitor` — monitor de polling httpx directo sin Chromium en el loop (`app/collector/http_monitor.py`)
- `PlaywrightCollector` extrae cookies de sesión en `_capture_current` y las pasa a `HttpMonitor`
- Flag `use_http_monitor=False/True` en `PlaywrightCollector` y `AppRuntime` (sin cambio de comportamiento por default)
- Modos INTENSIVA y SUEÑO disponibles en `HttpMonitor` (idénticos al original)
- Comandos `set_poll_seconds` / `set_intensive_monitoring` propagan al `HttpMonitor` cuando está activo
- Nuevo método público: `collector.set_http_monitor_mode(True/False)` para cambiar en caliente
- `httpx[http2]>=0.27` agregado a `requirements.txt`

**Pendiente / mejoras posibles:**
- Validar en portal real que las cookies solas son suficientes (sin CSRF extra)
- Exposición del flag `use_http_monitor` en la UI (checkbox en settings o menú)
- Re-autenticación automática: si `HttpMonitor` detecta sesión expirada, notificar a la UI para que el usuario haga re-capture
- Autenticación completa: login automático con credenciales (sin intervención manual)
- Múltiples subastas simultáneas en pestañas
- Dashboard de resumen entre subastas
- Exportación a PDF
- Notificaciones del sistema operativo (además del sonido)
- Empaquetado como ejecutable (.exe) con PyInstaller

---

*Última actualización: 2026-03-01*
