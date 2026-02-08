# 📖 Guía: Capturar Datos Reales del Portal

Esta guía explica cómo capturar responses reales del portal webecommerce.cba.gov.ar para crear escenarios JSON previsibles.

---

## 🎯 Objetivo

Crear escenarios JSON basados en **datos reales** del portal, controlando exactamente cuándo y cómo cambian los precios.

---

## 🔧 Herramientas Necesarias

- Navegador con DevTools (Chrome, Edge, Firefox)
- Editor de texto (VS Code recomendado)
- Acceso al portal: https://webecommerce.cba.gov.ar

---

## 📋 Paso a Paso

### 1. Abrir el Portal y DevTools

```
1. Navega a: https://webecommerce.cba.gov.ar/VistaPublica/OportunidadProveedores.aspx
2. Busca una subasta activa
3. Click en "Ingresar a Subasta"
4. Abre DevTools (F12 o Ctrl+Shift+I)
5. Ve a la pestaña "Network"
6. Marca el checkbox "Preserve log"
7. Filtra por "XHR" o "Fetch"
```

### 2. Identificar el Request `BuscarOfertas`

El portal hace polling cada segundo a:
```
POST /VistaPublica/SubastaVivoAccesoPublico.aspx/BuscarOfertas
```

**En DevTools verás**:
- Múltiples requests con el mismo nombre
- Aparecen cada 1 segundo
- Status: 200 (normalmente)

### 3. Capturar un Response

**Opción A: Copy Response**
```
1. Click en el request "BuscarOfertas"
2. Ve a la pestaña "Response"
3. Click derecho → Copy → Copy Response
4. Pega en tu editor (será 1 línea de JSON)
```

**Opción B: Copy as JSON**
```
1. Click en el request "BuscarOfertas"
2. Click derecho → Copy → Copy as JSON
3. Extrae el campo "response" → "body"
```

### 4. Formato del Response Real

El portal devuelve:

```json
{
  "d": "[{\"id_oferta_subasta\":1,\"id_cotizacion_det\":null,\"id_renglon\":836160,\"id_proveedor\":30696129,\"monto\":20115680,\"cantidad\":null,\"fecha_hora\":null,\"proveedor\":\"Prov. 30718165\",\"mejor_oferta\":\"Mejor Oferta Vigente:\",\"hora\":\"10:33:06\",\"monto_acumulado_renglon\":null,\"monto_a_mostrar\":\"$ 20.115.680,0000\"},{\"id_oferta_subasta\":2,\"id_cotizacion_det\":null,\"id_renglon\":836160,\"id_proveedor\":69728,\"monto\":20251036,\"cantidad\":null,\"fecha_hora\":null,\"proveedor\":\"Prov. 91764\",\"mejor_oferta\":\"Oferta Superada:\",\"hora\":\"10:08:06\",\"monto_acumulado_renglon\":null,\"monto_a_mostrar\":\"$ 20.251.036,0000\"}]@@$ 21.696.480,0000@@$ 20.015.101,6000@@"
}
```

**Estructura**:
- Campo `"d"`: Contiene todo separado por `@@`
- Parte 1 (antes del primer `@@`): Array JSON de ofertas (stringificado)
- Parte 2: Presupuesto oficial `$ X.XXX.XXX,XXXX`
- Parte 3: Oferta mínima a superar `$ X.XXX.XXX,XXXX`

### 5. Crear un Escenario JSON

```json
{
  "scenario_name": "mi_escenario_real",
  "description": "Capturado el 2026-02-07 a las 10:00",
  "subasta": {
    "id_cot": "22053",
    "url": "https://webecommerce.cba.gov.ar/..."
  },
  "timeline": [
    {
      "tick": 0,
      "hora": "10:00:00",
      "status": 200,
      "description": "Snapshot inicial capturado",
      "renglones": [
        {
          "id_renglon": "836160",
          "descripcion": "IMPRESORA LASER A4",
          "response_json": {
            "d": "<PEGAR_AQUÍ_EL_RESPONSE_CAPTURADO>"
          }
        }
      ]
    }
  ],
  "config": {
    "tick_duration_seconds": 60.0,
    "max_ticks": 20
  }
}
```

### 6. Capturar Cambios de Precio (Timeline)

Para tener un escenario realista con 4 cambios:

**Estrategia 1: Esperar cambios reales**
```
1. Captura snapshot inicial (tick 0)
2. Espera 2-3 minutos monitoreando DevTools
3. Cuando veas un cambio de precio → captura (tick 3)
4. Espera otro cambio → captura (tick 7)
5. Repite hasta tener 4-5 cambios
```

**Estrategia 2: Captura rápida (recommended)**
```
1. Graba toda una sesión de monitoreo (10-15 min)
2. En DevTools, guarda todos los requests (HAR export)
3. Extrae los responses que te interesan
4. Arma el timeline con los que tengan cambios
```

**Ejemplo Timeline Completo**:
```json
"timeline": [
  {
    "tick": 0,
    "hora": "10:00:00",
    "status": 200,
    "renglones": [{"id_renglon": "836160", "response_json": {...}}]
  },
  {
    "tick": 1,
    "hora": "10:01:00",
    "status": 200,
    "description": "Sin cambios"
  },
  {
    "tick": 3,
    "hora": "10:03:00",
    "status": 200,
    "description": "Cambio de precio observado",
    "renglones": [{"id_renglon": "836160", "response_json": {...}}]
  }
]
```

### 7. Simular Errores HTTP

**Forzar un error 500 en el portal** (para testing):

Opción A: Desconectar WiFi
```
1. Durante el monitoreo, desconecta WiFi por 1 minuto
2. El portal responderá con error (o timeout)
3. En DevTools verás el status HTTP != 200
4. Agrégalo al timeline
```

Opción B: DevTools → Offline Mode
```
1. DevTools → Network → Throttling → Offline
2. Espera 1 tick (el request fallará)
3. Vuelve a Online
4. Captura el error
```

**Agregar al timeline**:
```json
{
  "tick": 5,
  "hora": "10:05:00",
  "status": 500,
  "error_message": "Internal Server Error - timeout BD",
  "description": "Error forzado para testear recuperación"
}
```

### 8. Validar el Escenario

**Validar JSON syntax**:
```bash
python -m json.tool data/test_scenarios/mi_escenario.json
```

**Validar con ScenarioLoader** (cuando esté implementado):
```bash
python -c "
from pathlib import Path
from app.core.scenario_loader import ScenarioLoader
scenario = ScenarioLoader.load(Path('data/test_scenarios/mi_escenario.json'))
print(f'✅ Escenario válido: {scenario.scenario_name}')
print(f'   Timeline entries: {len(scenario.timeline)}')
"
```

---

## 💡 Tips y Trucos

### Identificar el `id_renglon`

En el response, busca:
```json
"id_renglon": 836160
```

Todos los renglones tienen un ID único.

### Extraer la descripción

En la página web, el dropdown tiene:
```html
<option value="836160">Item 1 - IMPRESORA LASER A4 MONOCROMO</option>
```

Copia la descripción para el JSON.

### Determinar cuándo hubo cambio

Compara el campo `"monto"` de la primera oferta (Mejor Oferta Vigente):
- Si cambió → hay update
- Si es igual → sin cambios (skip ese tick)

### Automatizar la captura

Puedes crear un script que:
1. Use Playwright para monitorear BuscarOfertas
2. Guarde cada response con timestamp
3. Filtre solo los que tienen cambios
4. Genere el JSON automáticamente

**Ejemplo**:
```python
# scripts/capture_scenario.py
import json
from playwright.sync_api import sync_playwright

responses = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    
    def handle_response(response):
        if "BuscarOfertas" in response.url:
            responses.append({
                "time": datetime.now().isoformat(),
                "status": response.status,
                "body": response.json()
            })
    
    page.on("response", handle_response)
    page.goto("https://webecommerce.cba.gov.ar/...")
    page.wait_for_timeout(600000)  # 10 min
    browser.close()

# Procesar responses y generar JSON
with open("captured_scenario.json", "w") as f:
    json.dump(responses, f, indent=2)
```

---

## ✅ Checklist Final

Antes de usar el escenario:

- [ ] Capturé al menos 1 snapshot inicial (tick 0)
- [ ] Tengo 3-4 cambios de precio reales
- [ ] Agregué 1-2 errores HTTP para testing
- [ ] Incluí un evento "end_auction" al final
- [ ] Validé la sintaxis JSON
- [ ] Probé con ScenarioLoader (cuando esté listo)
- [ ] Documenté expected_logs en config

---

## 📝 Plantilla Vacía

```json
{
  "scenario_name": "",
  "description": "",
  "metadata": {
    "author": "DPC",
    "created_at": "2026-02-07",
    "version": "1.0",
    "notes": ""
  },
  "subasta": {
    "id_cot": "",
    "url": ""
  },
  "timeline": [
    {
      "tick": 0,
      "hora": "10:00:00",
      "status": 200,
      "renglones": []
    }
  ],
  "config": {
    "tick_duration_seconds": 60.0,
    "max_ticks": 20
  }
}
```

---

**¿Dudas? Consulta:**
- [PLAN_REFACTOR_SIMULATOR.md](PLAN_REFACTOR_SIMULATOR.md) - Plan general
- [scenario_controlled_real.json](data/test_scenarios/scenario_controlled_real.json) - Ejemplo completo
