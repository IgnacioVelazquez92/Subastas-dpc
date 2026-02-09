# USO DE SIMULACIÓN CON ESCENARIOS JSON - V2

## Introducción

La refactorización Fase 3-4 ha eliminado completamente los datos hardcodeados de `simulator.py`. Ahora el sistema utiliza **escenarios JSON con datos reales del portal** para reproducir exactamente cualquier test case.

## Modos de Ejecución

### 1️⃣ Modo Legacy (DEPRECADO)

Usa Simulator con datos hardcodeados (para compatibilidad atrás):

```bash
python main.py --mode MOCK
# o simplemente
python main.py
```

**Salida esperada:**
- Se genera rendimiento sintético determinístico pero poco útil
- Se emite deprecation warning
- Obsoleto: usar Modo V2 en su lugar

---

### 2️⃣ Modo V2 - Escenarios JSON (RECOMENDADO)

Carga un escenario JSON y ejecuta timeline exacto con datos reales:

```bash
python main.py --mode MOCK --scenario "data/test_scenarios/scenario_controlled_real.json"
```

**Parámetros:**
- `--mode MOCK`: Usar MockCollector (no requiere navegador)
- `--scenario <path>`: Path a JSON de escenario (se requiere para V2)
- `--poll-seconds <float>`: Intervalo entre ticks (default: 1.0)

---

## Ejemplos de Escenarios Incluidos

### scenario_controlled_real.json
✅ **Mejor para testing de producción**
- 1 renglón con 4 cambios de precio
- 2 errores HTTP 500 realistas
- Datos copiados directamente del portal
- Timeline de 20 ticks con eventos específicos

**Uso:**
```bash
python main.py --mode MOCK --scenario "data/test_scenarios/scenario_controlled_real.json" --poll-seconds 0.5
```

### scenario_http_errors.json
✅ **Testing de manejo de errores**
- Múltiples errores HTTP (500, 502, 503)
- Recuperación después de errores
- Válida alert engine y logging

### scenario_price_war.json
✅ **Testing de contienda de precios**
- Múltiples ofertas en corto plazo
- Cambios frecuentes de mejor oferta
- Stress test del UI y alertas

---

## Estructura de un Escenario JSON

```json
{
  "scenario_name": "mi_escenario",
  "description": "Descripción del caso",
  "subasta": {
    "id_cot": "22053",
    "url": "https://portal.url/"
  },
  "config": {
    "tick_duration_seconds": 60.0,
    "max_ticks": 20
  },
  "timeline": [
    {
      "tick": 1,
      "hora": "10:30:00",
      "status": 200,
      "renglones": [
        {
          "id_renglon": "836160",
          "descripcion": "Descripción del renglón",
          "response_json": "{\"d\":\"[...]\",\"presupuesto\":\"...\",\"oferta_min\":\"...\"}"
        }
      ]
    },
    {
      "tick": 5,
      "hora": "10:35:00",
      "status": 500,
      "error_message": "Internal Server Error",
      "renglones": []
    }
  ]
}
```

---

## Archivos Modificados en Refactorización

### Nuevos Archivos (Fase 1-2)
- ✅ `app/core/scenario_loader.py` (197 líneas) - Carga y valida escenarios
- ✅ `app/core/simulator_v2.py` (179 líneas) - Timeline-based simulator
- ✅ `data/test_scenarios/*.json` - 5 escenarios de ejemplo

### Archivos Modificados (Fase 3-4)
- ✅ `app/collector/mock_collector.py` - Soporta V2 y Legacy con switch automático
- ✅ `app/core/app_runtime.py` - Acepta `scenario_path` en `__init__`
- ✅ `main.py` - CLI con `--scenario` argument

### Archivos Testeados
- ✅ `tests/test_mock_v2_integration.py` - Test de integración completo
- ✅ `tests/test_scenario_loader.py` - Tests unitarios

### Archivos Legados (Deprecados)
- ❌ `app/core/simulator.py` - Replaced by SimulatorV2 (sin borrar por compatibilidad)

---

## Testing

### Test de Integración Completo

Ejecuta MockCollector V2 con scenario real y valida eventos:

```bash
python -m tests.test_mock_v2_integration
```

**Validación:**
- ✓ SNAPSHOT emitido con datos reales
- ✓ 4 UPDATE events con cambios de precio
- ✓ 2 HTTP_ERROR events
- ✓ END event al finalizar
- **Total: 20 eventos procesados correctamente**

---

### Tests Unitarios

```bash
python -m tests.test_scenario_loader
```

**Validación:**
- ✓ Cargar escenario JSON válido
- ✓ Timeline ordenado por tick
- ✓ Detección de errores HTTP
- **Todos los tests pasaron ✅**

---

## Cómo Crear Tu Propio Escenario

### Paso 1: Capturar respuesta real del portal

1. Abre DevTools (F12) en cualquier navegador
2. Ve a la subasta en `webecommerce.cba.gov.ar`
3. Copia el JSON response del endpoint BuscarOfertas
4. Guárdalo en texto

### Paso 2: Crear JSON de escenario

```json
{
  "scenario_name": "mi_test",
  "description": "Mi caso de prueba",
  "subasta": {
    "id_cot": "12345",
    "url": "https://..."
  },
  "config": {
    "tick_duration_seconds": 1.0,
    "max_ticks": 10
  },
  "timeline": [
    {
      "tick": 1,
      "hora": "10:00:00",
      "status": 200,
      "renglones": [
        {
          "id_renglon": "836160",
          "descripcion": "Mi producto",
          "response_json": "<PEGA EL JSON AQUI>"
        }
      ]
    }
  ]
}
```

### Paso 3: Usar en testing

```bash
python main.py --mode MOCK --scenario "data/test_scenarios/mi_test.json"
```

---

## Validación de Escenarios

El `ScenarioLoader` valida automáticamente:
- ✅ Campos requeridos presentes
- ✅ Timeline ordenada por tick
- ✅ JSON response valido
- ✅ Referencia a renglones consistentes

Si hay error → excepción clara + mensaje descriptivo

---

## Beneficios de V2

| Aspecto | Legacy | V2 |
|--------|--------|-------|
| **Datos** | Hardcodeados | Reales del portal |
| **Reproducibilidad** | ❌ No | ✅ Exacta |
| **Testing** | Débil | Fuerte |
| **Debugging** | Imposible | Fácil |
| **CI/CD** | No apto | Ideal |
| **Mantenibilidad** | Baja | Alta |

---

## Próximos Pasos

- [ ] Migrar todos los tests manuales a JSON scenarios
- [ ] Crear scenarios para edge cases (timeout, conexión perdida, etc)
- [ ] Documentar formato JSON final
- [ ] Considerar CI/CD con scenarios en repo
- [ ] Deprecation warning en simulator.py (ya existe)

---

## Soporte

¿Preguntas sobre escenarios?

1. Ver `PLAN_REFACTOR_SIMULATOR.md` para arquitectura
2. Ver `GUIA_CAPTURA_DATOS.md` para capturar datos reales
3. Ver ejemplos en `data/test_scenarios/`
4. Ejecutar `tests/test_mock_v2_integration.py` 

