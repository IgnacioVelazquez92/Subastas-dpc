# AGENTS.md — Contexto para Agentes IA

> Este archivo es el punto de partida para cualquier agente IA o colaborador nuevo que trabaje en este proyecto.
> Se actualiza a medida que evolucionan decisiones de diseño, convenciones y contexto del dominio.

---

## Resumen Ejecutivo

**Monitor de Subastas Electrónicas** es una aplicación de escritorio Python que monitorea en tiempo real el portal de subastas e-Commerce de la provincia de Córdoba (Argentina). El sistema captura automáticamente cambios de precios usando Playwright, los persiste en SQLite, aplica reglas de alertas y los muestra en una UI de escritorio moderna (CustomTkinter).

**Estado actual:** v1.0 — primera versión funcional completa. El sistema fue construido iterativamente con refactors documentados en `docs/`.

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

```
[Portal web] --Playwright--> [PlaywrightCollector]
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
                               (event_handler.py despacha
                                a table_manager, logger, etc.)
```

### Threading

- **Main thread**: UI (Tkinter — obligatorio, no puede moverse)
- **Thread Collector**: corre el loop de scraping / simulación
- **Thread Engine**: consume la queue del Collector, procesa y emite a la queue de la UI
- **UI polling**: `app.py` usa `after()` para consumir la queue del Engine sin bloquear la UI

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

### PLAYWRIGHT (producción)

- Usa `PlaywrightCollector` que lanza Chromium automáticamente
- Navega al portal, hace scraping de la tabla de renglones
- Emite `SNAPSHOT` al inicio y `UPDATE` por cada cambio detectado
- `autostart_collector=False` en este modo — el usuario debe iniciar manualmente desde la UI (botón Start)

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

**Pendiente / mejoras posibles:**
- Autenticación y manejo de sesión del portal (login automático)
- Múltiples subastas simultáneas en pestañas
- Dashboard de resumen entre subastas
- Exportación a PDF
- Notificaciones del sistema operativo (además del sonido)
- Empaquetado como ejecutable (.exe) con PyInstaller

---

*Última actualización: 2026-02-25*
