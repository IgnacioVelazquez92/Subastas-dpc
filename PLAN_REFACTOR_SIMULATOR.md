# 📋 Plan de Acción: Refactorización del Simulador

**Objetivo**: Eliminar datos hardcodeados del simulador y migrar a un sistema basado en JSON que sea **previsible, configurable y mantenible**.

---

## 🎯 Problemas Actuales

### 1. Datos Hardcodeados Dispersos

**Ubicación**: `app/core/simulator.py`

```python
# Línea 119 - Valores base inventados
base_best = 18_000_000.0 + (int(rid) % 7) * 1_250_000.0

# Líneas 123-132 - Ofertas con datos ficticios
st.ofertas[0].monto = base_best
st.ofertas[1].monto = base_best * 1.01

# Línea 176 - RNG con semilla fija
self._rng = random.Random(12345)

# Líneas 149-150 - Lógica de variación hardcodeada
self.auto_drop_seconds = 60.0  # 1% cada 60 segundos
self.auto_drop_pct = 0.01

# Líneas 152-153 - Probabilidades hardcodeadas
self.prob_http_500 = 0.0
self.prob_end = 0.0
```

### 2. Consecuencias

❌ Imposible reproducir escenarios específicos  
❌ No se puede probar comportamiento bajo condiciones controladas  
❌ Difícil validar reglas de alertas/seguridad  
❌ Logs impredecibles → debugging complicado  
❌ Tests no determinísticos  

---

## 🚀 Solución Propuesta

### Arquitectura Nueva

```
data/
├── monitor.db
└── test_scenarios/
    ├── scenario_basic.json          # Escenario básico estable
    ├── scenario_high_volatility.json # Precios caen rápido
    ├── scenario_http_errors.json     # Errores HTTP frecuentes
    ├── scenario_end_auction.json     # Subasta termina en X ticks
    └── scenario_custom.json          # Tu escenario personalizado
```

Cada JSON define:
- Estado inicial de cada renglón
- Timeline de eventos (tick → cambios)
- Comportamiento automático (si aplica)

---

## 📝 Estructura del JSON de Escenario (Formato Real del Portal)

### Formato de Respuesta Real

El portal devuelve este formato en `/BuscarOfertas`:

```json
{
  "d": "[{array_de_ofertas}]@@presupuesto@@oferta_minima@@"
}
```

**Nuestro escenario replica exactamente este formato**, permitiendo snapshots con datos reales del portal.

### Formato Completo del Escenario

```json
{
  "scenario_name": "controlled_real_data",
  "description": "Escenario con datos reales del portal, 3-4 cambios controlados + errores HTTP",
  "metadata": {
    "author": "DPC",
    "created_at": "2026-02-07",
    "version": "2.0",
    "notes": "Basado en responses reales del portal webecommerce.cba.gov.ar"
  },
  
  "subasta": {
    "id_cot": "22053",
    "url": "https://webecommerce.cba.gov.ar/..."
  },
  
  "timeline": [
    {
      "tick": 0,
      "hora": "10:00:00",
      "status": 200,
      "renglones": [
        {
          "id_renglon": "836160",
          "descripcion": "Item extraído del portal",
          "response_json": {
            "d": "[{\"id_oferta_subasta\":1,\"id_renglon\":836160,\"id_proveedor\":30696129,\"monto\":20115680,\"proveedor\":\"Prov. 30718165\",\"mejor_oferta\":\"Mejor Oferta Vigente:\",\"hora\":\"10:33:06\",\"monto_a_mostrar\":\"$ 20.115.680,0000\"},{\"id_oferta_subasta\":2,\"id_renglon\":836160,\"id_proveedor\":69728,\"monto\":20251036,\"proveedor\":\"Prov. 91764\",\"mejor_oferta\":\"Oferta Superada:\",\"hora\":\"10:08:06\",\"monto_a_mostrar\":\"$ 20.251.036,0000\"}]@@$ 21.696.480,0000@@$ 20.015.101,6000@@"
          }
        }
      ]
    },
    {
      "tick": 5,
      "hora": "10:05:00",
      "status": 200,
      "renglones": [
        {
          "id_renglon": "836160",
          "response_json": {
            "d": "[{\"id_oferta_subasta\":1,\"id_renglon\":836160,\"id_proveedor\":69728,\"monto\":20000000,\"proveedor\":\"Prov. 91764\",\"mejor_oferta\":\"Mejor Oferta Vigente:\",\"hora\":\"10:35:12\",\"monto_a_mostrar\":\"$ 20.000.000,0000\"},{\"id_oferta_subasta\":2,\"id_renglon\":836160,\"id_proveedor\":30696129,\"monto\":20115680,\"proveedor\":\"Prov. 30718165\",\"mejor_oferta\":\"Oferta Superada:\",\"hora\":\"10:33:06\",\"monto_a_mostrar\":\"$ 20.115.680,0000\"}]@@$ 21.696.480,0000@@$ 19.800.000,0000@@"
          }
        }
      ]
    },
    {
      "tick": 8,
      "hora": "10:08:00",
      "status": 500,
      "error_message": "Internal Server Error - timeout BD"
    },
    {
      "tick": 10,
      "hora": "10:10:00",
      "status": 200,
      "renglones": [
        {
          "id_renglon": "836160",
          "response_json": {
            "d": "[{\"id_oferta_subasta\":1,\"id_renglon\":836160,\"id_proveedor\":30696129,\"monto\":19850000,\"proveedor\":\"Prov. 30718165\",\"mejor_oferta\":\"Mejor Oferta Vigente:\",\"hora\":\"10:40:22\",\"monto_a_mostrar\":\"$ 19.850.000,0000\"},{\"id_oferta_subasta\":2,\"id_renglon\":836160,\"id_proveedor\":69728,\"monto\":20000000,\"proveedor\":\"Prov. 91764\",\"mejor_oferta\":\"Oferta Superada:\",\"hora\":\"10:35:12\",\"monto_a_mostrar\":\"$ 20.000.000,0000\"}]@@$ 21.696.480,0000@@$ 19.651.500,0000@@"
          }
        }
      ]
    },
    {
      "tick": 15,
      "hora": "10:15:00",
      "status": 500,
      "error_message": "Internal Server Error - conexión perdida"
    },
    {
      "tick": 18,
      "hora": "10:18:00",
      "status": 200,
      "renglones": [
        {
          "id_renglon": "836160",
          "response_json": {
            "d": "[{\"id_oferta_subasta\":1,\"id_renglon\":836160,\"id_proveedor\":69728,\"monto\":19700000,\"proveedor\":\"Prov. 91764\",\"mejor_oferta\":\"Mejor Oferta Vigente:\",\"hora\":\"10:45:08\",\"monto_a_mostrar\":\"$ 19.700.000,0000\"},{\"id_oferta_subasta\":2,\"id_renglon\":836160,\"id_proveedor\":30696129,\"monto\":19850000,\"proveedor\":\"Prov. 30718165\",\"mejor_oferta\":\"Oferta Superada:\",\"hora\":\"10:40:22\",\"monto_a_mostrar\":\"$ 19.850.000,0000\"}]@@$ 21.696.480,0000@@$ 19.503.000,0000@@"
          }
        }
      ]
    },
    {
      "tick": 20,
      "hora": "10:20:00",
      "status": 200,
      "event": "end_auction",
      "message": "Subasta finalizada"
    }
  ],
  
  "config": {
    "tick_duration_seconds": 60.0,
    "max_ticks": 25,
    "expected_behavior": "4 cambios de precios, 2 errores HTTP 500, finaliza en tick 20"
  }
}
```

### Campos del Timeline

Cada entrada del timeline representa un tick con:

- **`tick`**: Número de tick (0 = snapshot inicial)
- **`hora`**: Timestamp del evento (formato HH:MM:SS)
- **`status`**: Código HTTP (200 = OK, 500/502/503 = error)
- **`renglones`**: Array de renglones con `response_json` en formato real del portal
- **`error_message`**: Mensaje de error (solo si status != 200)
- **`event`**: Evento especial (`end_auction`, `pause`, etc.)
- **`message`**: Mensaje adicional

### Ventajas de este Formato

✅ **Datos reales** del portal (copy/paste directo)  
✅ **Timeline cronológico** exacto (hora + tick)  
✅ **Status HTTP** controlado por tick  
✅ **Previsibilidad total** de logs  
✅ **Fácil captura** desde DevTools del navegador  
✅ **Múltiples renglones** en un solo snapshot  

---

## 📦 Implementación (Paso a Paso)

### Fase 1: Estructura Base (2-3 horas)

**Entregables**:
- `app/core/scenario_loader.py`: Carga y valida JSON
- Tests unitarios para loader

**Tareas**:
1. Crear `ScenarioConfig` (dataclass) para representar JSON con timeline
2. Implementar `ScenarioLoader.load(path) -> ScenarioConfig`
3. Parser del formato real del portal: `"d": "[{...}]@@presupuesto@@oferta_min@@"`
4. Validar schema JSON (campos requeridos, status HTTP válidos)

**Código inicial**:

```python
# app/core/scenario_loader.py
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import json
from pathlib import Path

@dataclass
class RenglonResponse:
    """Respuesta real del portal para un renglón"""
    id_renglon: str
    descripcion: str
    response_json: Dict[str, str]  # {"d": "...@@...@@..."}

@dataclass
class TimelineEntry:
    """Una entrada del timeline con hora, status y data"""
    tick: int
    hora: str  # HH:MM:SS
    status: int  # 200, 500, 502, 503
    description: Optional[str] = None
    renglones: Optional[List[RenglonResponse]] = None
    error_message: Optional[str] = None
    event: Optional[str] = None  # "end_auction", etc.
    message: Optional[str] = None

@dataclass
class ScenarioConfig:
    scenario_name: str
    description: str
    id_cot: str
    url: str
    timeline: List[TimelineEntry]
    tick_duration_seconds: float
    max_ticks: int
    expected_behavior: Optional[str] = None
    expected_logs: Optional[List[str]] = None

class ScenarioLoader:
    @staticmethod
    def load(path: Path) -> ScenarioConfig:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Parse timeline
        timeline = []
        for entry in data.get("timeline", []):
            renglones = None
            if "renglones" in entry:
                renglones = [
                    RenglonResponse(
                        id_renglon=r["id_renglon"],
                        descripcion=r.get("descripcion", ""),
                        response_json=r["response_json"]
                    )
                    for r in entry["renglones"]
                ]
            
            timeline.append(TimelineEntry(
                tick=entry["tick"],
                hora=entry["hora"],
                status=entry["status"],
                description=entry.get("description"),
                renglones=renglones,
                error_message=entry.get("error_message"),
                event=entry.get("event"),
                message=entry.get("message")
            ))
        
        return ScenarioConfig(
            scenario_name=data["scenario_name"],
            description=data["description"],
            id_cot=data["subasta"]["id_cot"],
            url=data["subasta"]["url"],
            timeline=timeline,
            tick_duration_seconds=data["config"]["tick_duration_seconds"],
            max_ticks=data["config"]["max_ticks"],
            expected_behavior=data["config"].get("expected_behavior"),
            expected_logs=data["config"].get("expected_logs")
        )
    
    @staticmethod
    def parse_portal_response(response_json: Dict[str, str]) -> Dict[str, Any]:
        """
        Parse del formato real del portal:
        {"d": "[{...ofertas...}]@@presupuesto@@oferta_min@@"}
        
        Returns:
            {
                "ofertas": [...],
                "presupuesto_txt": "$ ...",
                "oferta_min_txt": "$ ..."
            }
        """
        d = response_json.get("d", "")
        parts = d.split("@@")
        
        if len(parts) < 3:
            raise ValueError(f"Formato inválido: esperado 3 partes, encontrado {len(parts)}")
        
        ofertas_json = parts[0]
        presupuesto_txt = parts[1]
        oferta_min_txt = parts[2]
        
        ofertas = json.loads(ofertas_json)
        
        return {
            "ofertas": ofertas,
            "presupuesto_txt": presupuesto_txt,
            "oferta_min_txt": oferta_min_txt
        }
```

### Fase 2: Refactorización del Simulator (3-4 horas)

**Entregables**:
- `app/core/simulator_v2.py`: Nuevo simulador basado en JSON con timeline
- Deprecar `simulator.py` (renombrar a `simulator_legacy.py`)
- Adaptar `MockCollector` para usar v2

**Tareas**:
1. Crear `SimulatorV2` que recibe `ScenarioConfig`
2. Implementar lógica de timeline (tick → response real del portal)
3. Manejar status HTTP (200, 500, 502, 503)
4. Emitir eventos con formato compatible con Engine
5. Tests de regresión con escenarios JSON

**Código inicial**:

```python
# app/core/simulator_v2.py
from app.core.scenario_loader import ScenarioConfig, TimelineEntry, ScenarioLoader
from app.core.simulator import BuscarOfertasState, Oferta, _money_txt, _now_hhmmss
from app.utils.money import money_to_float
import copy
import json

class SimulatorV2:
    """
    Simulador basado en timeline con datos reales del portal.
    
    - Lee el JSON de escenario
    - En cada tick, busca la entrada correspondiente en timeline
    - Devuelve el estado exacto definido en el JSON
    - Maneja status HTTP y errores
    """
    
    def __init__(self, scenario: ScenarioConfig):
        self.scenario = scenario
        self._tick_count = 0
        self._states: Dict[str, BuscarOfertasState] = {}
        self._last_ok_states: Dict[str, BuscarOfertasState] = {}
        self._http_status = 200
        self._error_message = ""
        self._ended = False
    
    def tick(self) -> tuple[int, list[BuscarOfertasState], bool]:
        """
        Ejecuta un tick del simulador.
        
        Returns:
            (http_status, states, ended)
        """
        # Buscar entrada del timeline para este tick
        entry = self._find_timeline_entry(self._tick_count)
        
        if entry is None:
            # No hay cambios, devolver último estado OK
            self._tick_count += 1
            return (200, list(self._last_ok_states.values()), self._ended)
        
        # Procesar entrada
        http_status = entry.status
        states = []
        
        if http_status == 200:
            if entry.renglones:
                # Parsear responses reales del portal
                for renglon_resp in entry.renglones:
                    state = self._parse_portal_response(renglon_resp)
                    self._states[state.id_renglon] = state
                    self._last_ok_states[state.id_renglon] = copy.deepcopy(state)
                    states.append(state)
            else:
                # Sin cambios, devolver último OK
                states = list(self._last_ok_states.values())
            
            # Check end event
            if entry.event == "end_auction":
                self._ended = True
                for state in states:
                    state.finalizada = True
                    state.mensaje = entry.message or "Subasta finalizada"
        else:
            # Error HTTP
            self._error_message = entry.error_message or f"HTTP {http_status}"
        
        self._http_status = http_status
        self._tick_count += 1
        
        return (http_status, states, self._ended)
    
    def _find_timeline_entry(self, tick: int) -> Optional[TimelineEntry]:
        for entry in self.scenario.timeline:
            if entry.tick == tick:
                return entry
        return None
    
    def _parse_portal_response(self, renglon_resp) -> BuscarOfertasState:
        """
        Convierte el response real del portal a BuscarOfertasState.
        
        Formato portal: {"d": "[{...ofertas...}]@@presupuesto@@oferta_min@@"}
        """
        parsed = ScenarioLoader.parse_portal_response(renglon_resp.response_json)
        
        # Construir ofertas
        ofertas = []
        for oferta_data in parsed["ofertas"]:
            ofertas.append(Oferta(
                proveedor=oferta_data.get("proveedor", ""),
                mejor_oferta_label=oferta_data.get("mejor_oferta", ""),
                monto=float(oferta_data.get("monto", 0)),
                hora=oferta_data.get("hora", ""),
                monto_a_mostrar=oferta_data.get("monto_a_mostrar", "")
            ))
        
        # Extraer valores numéricos
        presupuesto_val = money_to_float(parsed["presupuesto_txt"])
        oferta_min_val = money_to_float(parsed["oferta_min_txt"])
        
        # Mejor oferta vigente (primera con "Mejor Oferta Vigente:")
        mejor_oferta_val = None
        mejor_oferta_txt = ""
        for oferta in ofertas:
            if "Vigente" in oferta.mejor_oferta_label:
                mejor_oferta_val = oferta.monto
                mejor_oferta_txt = oferta.monto_a_mostrar
                break
        
        return BuscarOfertasState(
            id_renglon=renglon_resp.id_renglon,
            ofertas=ofertas,
            presupuesto_txt=parsed["presupuesto_txt"],
            oferta_min_txt=parsed["oferta_min_txt"],
            mensaje="Subasta en curso",
            presupuesto_val=presupuesto_val,
            oferta_min_val=oferta_min_val,
            http_status=200,
            finalizada=False
        )
```

### Fase 3: Integración y Testing (2 horas)

**Entregables**:
- Integración en `MockCollector`
- Selector de escenario en UI (opcional)
- 5 escenarios de prueba listos
- Tests end-to-end

**Tareas**:
1. Modificar `mock_collector.py`:
   ```python
   def __init__(self, ..., scenario_path: Optional[Path] = None):
       if scenario_path:
           scenario = ScenarioLoader.load(scenario_path)
           self._sim = SimulatorV2(scenario)
       else:
           self._sim = Simulator(...)  # legacy
   ```

2. Crear escenarios:
   - `scenario_basic.json`: Estable, sin cambios
   - `scenario_price_war.json`: Precios caen constantemente
   - `scenario_errors.json`: HTTP 500 cada 5 ticks
   - `scenario_end_quick.json`: Termina en tick 10
   - `scenario_custom_demo.json`: Mix de comportamientos

3. Agregar parámetro opcional en `main.py`:
   ```python
   parser.add_argument('--scenario', type=str, help='Path al JSON de escenario')
   ```

4. Tests:
   - Test: escenario carga correctamente
   - Test: tick N genera evento esperado
   - Test: auto_behavior funciona
   - Test: global_events se aplican

### Fase 4: Deprecación del Simulador Legacy (1 hora)

**Entregables**:
- Renombrar `simulator.py` → `simulator_legacy.py`
- Agregar warnings de deprecación
- Actualizar imports
- Documentar migración

**Tareas**:
1. Renombrar archivo
2. Agregar decorator `@deprecated` a clases legacy
3. Actualizar README con nueva forma de uso
4. Pull request / commit final

---

## 📊 Escenarios de Prueba (Con Datos Reales)

### 1. Escenario Controlado (4 cambios + 2 errores)

**Objetivo**: Testear alertas, UI updates, y recuperación de errores HTTP

```json
{
  "scenario_name": "controlled_real_scenario",
  "description": "4 cambios de precio controlados + 2 errores HTTP 500",
  "timeline": [
    {
      "tick": 0,
      "hora": "10:00:00",
      "status": 200,
      "renglones": [
        {
          "id_renglon": "836160",
          "descripcion": "IMPRESORA LASER",
          "response_json": {
            "d": "[{\"id_oferta_subasta\":1,\"id_renglon\":836160,\"monto\":20115680,\"proveedor\":\"Prov. 30718165\",\"mejor_oferta\":\"Mejor Oferta Vigente:\",\"hora\":\"10:00:00\",\"monto_a_mostrar\":\"$ 20.115.680,0000\"},{\"id_oferta_subasta\":2,\"id_renglon\":836160,\"monto\":20251036,\"proveedor\":\"Prov. 91764\",\"mejor_oferta\":\"Oferta Superada:\",\"hora\":\"09:55:00\",\"monto_a_mostrar\":\"$ 20.251.036,0000\"}]@@$ 21.696.480,0000@@$ 19.914.523,2000@@"
          }
        }
      ]
    },
    {
      "tick": 3,
      "hora": "10:03:00",
      "status": 200,
      "renglones": [
        {
          "id_renglon": "836160",
          "response_json": {
            "d": "[{\"id_oferta_subasta\":1,\"id_renglon\":836160,\"monto\":20000000,\"proveedor\":\"Prov. 91764\",\"mejor_oferta\":\"Mejor Oferta Vigente:\",\"hora\":\"10:02:45\",\"monto_a_mostrar\":\"$ 20.000.000,0000\"},{\"id_oferta_subasta\":2,\"id_renglon\":836160,\"monto\":20115680,\"proveedor\":\"Prov. 30718165\",\"mejor_oferta\":\"Oferta Superada:\",\"hora\":\"10:00:00\",\"monto_a_mostrar\":\"$ 20.115.680,0000\"}]@@$ 21.696.480,0000@@$ 19.800.000,0000@@"
          }
        }
      ]
    },
    {
      "tick": 5,
      "hora": "10:05:00",
      "status": 500,
      "error_message": "Internal Server Error - timeout BD"
    },
    {
      "tick": 7,
      "hora": "10:07:00",
      "status": 200,
      "renglones": [
        {
          "id_renglon": "836160",
          "response_json": {
            "d": "[{\"id_oferta_subasta\":1,\"id_renglon\":836160,\"monto\":19850000,\"proveedor\":\"Prov. 30718165\",\"mejor_oferta\":\"Mejor Oferta Vigente:\",\"hora\":\"10:06:30\",\"monto_a_mostrar\":\"$ 19.850.000,0000\"},{\"id_oferta_subasta\":2,\"id_renglon\":836160,\"monto\":20000000,\"proveedor\":\"Prov. 91764\",\"mejor_oferta\":\"Oferta Superada:\",\"hora\":\"10:02:45\",\"monto_a_mostrar\":\"$ 20.000.000,0000\"}]@@$ 21.696.480,0000@@$ 19.651.500,0000@@"
          }
        }
      ]
    },
    {
      "tick": 10,
      "hora": "10:10:00",
      "status": 200,
      "renglones": [
        {
          "id_renglon": "836160",
          "response_json": {
            "d": "[{\"id_oferta_subasta\":1,\"id_renglon\":836160,\"monto\":19700000,\"proveedor\":\"Prov. 91764\",\"mejor_oferta\":\"Mejor Oferta Vigente:\",\"hora\":\"10:09:15\",\"monto_a_mostrar\":\"$ 19.700.000,0000\"},{\"id_oferta_subasta\":2,\"id_renglon\":836160,\"monto\":19850000,\"proveedor\":\"Prov. 30718165\",\"mejor_oferta\":\"Oferta Superada:\",\"hora\":\"10:06:30\",\"monto_a_mostrar\":\"$ 19.850.000,0000\"}]@@$ 21.696.480,0000@@$ 19.503.000,0000@@"
          }
        }
      ]
    },
    {
      "tick": 12,
      "hora": "10:12:00",
      "status": 500,
      "error_message": "Internal Server Error - conexión perdida"
    },
    {
      "tick": 14,
      "hora": "10:14:00",
      "status": 200,
      "event": "end_auction",
      "message": "Subasta finalizada - Ganador: Prov. 91764"
    }
  ],
  "config": {
    "tick_duration_seconds": 60.0,
    "max_ticks": 15
  }
}
```

**Logs esperados**:
```
[10:00:00] SNAPSHOT: id_renglon=836160 mejor=$20.115.680,0000 min=$19.914.523,2000
[10:01:00] Tick 1 (sin cambios)
[10:02:00] Tick 2 (sin cambios)
[10:03:00] 🔄 UPDATE r=836160 mejor=$20.000.000,0000 min=$19.800.000,0000 (Prov. 91764)
[10:04:00] Tick 4 (sin cambios)
[10:05:00] ❌ HTTP 500 - Internal Server Error - timeout BD
[10:06:00] Tick 6 (recuperando...)
[10:07:00] ✅ RECUPERADO - UPDATE r=836160 mejor=$19.850.000,0000 (Prov. 30718165)
[10:08:00] Tick 8 (sin cambios)
[10:09:00] Tick 9 (sin cambios)
[10:10:00] 🔄 UPDATE r=836160 mejor=$19.700.000,0000 min=$19.503.000,0000 (Prov. 91764)
[10:11:00] Tick 11 (sin cambios)
[10:12:00] ❌ HTTP 500 - Internal Server Error - conexión perdida
[10:13:00] Tick 13 (recuperando...)
[10:14:00] 🏁 END - Subasta finalizada - Ganador: Prov. 91764
```

---

### 2. Escenario Multi-Renglón

**Objetivo**: Testear múltiples renglones con cambios independientes

```json
{
  "scenario_name": "multi_renglon_real",
  "description": "3 renglones con cambios independientes",
  "timeline": [
    {
      "tick": 0,
      "hora": "11:00:00",
      "status": 200,
      "renglones": [
        {
          "id_renglon": "836160",
          "descripcion": "IMPRESORA LASER",
          "response_json": {
            "d": "[{\"id_oferta_subasta\":1,\"id_renglon\":836160,\"monto\":20115680,\"proveedor\":\"Prov. A\",\"mejor_oferta\":\"Mejor Oferta Vigente:\",\"hora\":\"11:00:00\",\"monto_a_mostrar\":\"$ 20.115.680,0000\"}]@@$ 21.696.480,0000@@$ 19.914.523,2000@@"
          }
        },
        {
          "id_renglon": "836161",
          "descripcion": "MONITOR LED 24",
          "response_json": {
            "d": "[{\"id_oferta_subasta\":1,\"id_renglon\":836161,\"monto\":850000,\"proveedor\":\"Prov. B\",\"mejor_oferta\":\"Mejor Oferta Vigente:\",\"hora\":\"11:00:00\",\"monto_a_mostrar\":\"$ 850.000,0000\"}]@@$ 918.000,0000@@$ 841.500,0000@@"
          }
        },
        {
          "id_renglon": "836162",
          "descripcion": "TECLADO USB",
          "response_json": {
            "d": "[{\"id_oferta_subasta\":1,\"id_renglon\":836162,\"monto\":45000,\"proveedor\":\"Prov. C\",\"mejor_oferta\":\"Mejor Oferta Vigente:\",\"hora\":\"11:00:00\",\"monto_a_mostrar\":\"$ 45.000,0000\"}]@@$ 54.000,0000@@$ 44.550,0000@@"
          }
        }
      ]
    },
    {
      "tick": 2,
      "hora": "11:02:00",
      "status": 200,
      "renglones": [
        {
          "id_renglon": "836160",
          "response_json": {
            "d": "[{\"id_oferta_subasta\":1,\"id_renglon\":836160,\"monto\":20000000,\"proveedor\":\"Prov. A\",\"mejor_oferta\":\"Mejor Oferta Vigente:\",\"hora\":\"11:01:45\",\"monto_a_mostrar\":\"$ 20.000.000,0000\"}]@@$ 21.696.480,0000@@$ 19.800.000,0000@@"
          }
        }
      ]
    },
    {
      "tick": 4,
      "hora": "11:04:00",
      "status": 200,
      "renglones": [
        {
          "id_renglon": "836161",
          "response_json": {
            "d": "[{\"id_oferta_subasta\":1,\"id_renglon\":836161,\"monto\":840000,\"proveedor\":\"Prov. D\",\"mejor_oferta\":\"Mejor Oferta Vigente:\",\"hora\":\"11:03:30\",\"monto_a_mostrar\":\"$ 840.000,0000\"}]@@$ 918.000,0000@@$ 831.600,0000@@"
          }
        }
      ]
    },
    {
      "tick": 6,
      "hora": "11:06:00",
      "status": 200,
      "event": "end_auction"
    }
  ],
  "config": {
    "tick_duration_seconds": 60.0,
    "max_ticks": 10
  }
}
```

**Logs esperados**:
```
[11:00:00] SNAPSHOT: 3 renglones capturados
[11:00:00]   - r=836160 mejor=$20.115.680,0000 (IMPRESORA LASER)
[11:00:00]   - r=836161 mejor=$850.000,0000 (MONITOR LED 24)
[11:00:00]   - r=836162 mejor=$45.000,0000 (TECLADO USB)
[11:01:00] Tick 1 (sin cambios)
[11:02:00] 🔄 UPDATE r=836160 mejor=$20.000.000,0000
[11:03:00] Tick 3 (sin cambios)
[11:04:00] 🔄 UPDATE r=836161 mejor=$840.000,0000 (Prov. D)
[11:05:00] Tick 5 (sin cambios)
[11:06:00] 🏁 END - Subasta finalizada
```

---

## 🔧 Cómo Capturar Datos Reales del Portal

Para crear escenarios con datos reales, seguí estos pasos:

### 1. Abrir DevTools del Navegador

1. Abrí el portal: `https://webecommerce.cba.gov.ar/...`
2. Presioná **F12** para abrir DevTools
3. Andá a la pestaña **Network** (Red)
4. Filtrá por **Fetch/XHR**

### 2. Capturar Request de BuscarOfertas

1. Navegá a una subasta activa
2. En la lista de requests, buscá: **`BuscarOfertas`**
3. Click derecho → **Copy** → **Copy response**
4. Pegalo en un archivo temporal

### 3. Limpiar y Formatear

El response crudo se ve así:

```json
{"d":"[{...}]@@$ 21.696.480,0000@@$ 20.015.101,6000@@"}
```

**Ya está listo para usar en el JSON del escenario.**

### 4. Agregar al Timeline del Escenario

```json
{
  "tick": 0,
  "hora": "10:00:00",
  "status": 200,
  "renglones": [
    {
      "id_renglon": "836160",
      "descripcion": "ITEM CAPTURADO DEL PORTAL",
      "response_json": {
        "d": "[{...datos pegados aquí...}]@@$ 21.696.480,0000@@$ 20.015.101,6000@@"
      }
    }
  ]
}
```

### 5. Capturar Múltiples Snapshots

Para simular cambios:

1. **Tick 0**: Capturá el estado inicial
2. **Espera 2-3 minutos** (o hasta que cambien los precios)
3. **Tick 3**: Capturá el nuevo estado
4. **Repetí** para tener 3-4 snapshots

Ahora tenés un **escenario 100% realista** con datos exactos del portal.

### 6. Simular Errores HTTP

Para errores, solo cambiá el `status`:

```json
{
  "tick": 5,
  "hora": "10:05:00",
  "status": 500,
  "error_message": "Internal Server Error - timeout BD"
}
```

---

## 🎯 Beneficios de la Solución

### Para Desarrollo
✅ Reproducibilidad total de escenarios  
✅ Tests determinísticos  
✅ Debugging preciso con logs predecibles  
✅ Validación de reglas de alertas/seguridad  

### Para Testing
✅ Escenarios edge-case controlados  
✅ Pruebas de estrés (HTTP errors, timeouts)  
✅ Simulación de condiciones reales específicas  
✅ CI/CD con escenarios automáticos  

### Para Mantenimiento
✅ Configuración sin tocar código  
✅ Nuevos escenarios = nuevo JSON  
✅ Colaboración (compartir escenarios)  
✅ Documentación implícita (JSON autodescriptivo)  

---

## 📅 Timeline Estimado

| Fase | Duración | Entregables |
|------|----------|-------------|
| **Fase 1** | 2-3 horas | ScenarioLoader + 1 JSON básico |
| **Fase 2** | 3-4 horas | SimulatorV2 completo + tests |
| **Fase 3** | 2 horas | Integración + 5 escenarios |
| **Fase 4** | 1 hora | Deprecar legacy + docs |
| **TOTAL** | **8-10 horas** | Sistema completo funcionando |

---

## 🚦 Criterios de Éxito

1. ✅ Se elimina **100% del código hardcodeado** de simulator.py
2. ✅ Los logs son **100% predecibles** según el JSON
3. ✅ Se pueden crear nuevos escenarios **sin modificar código**
4. ✅ Los tests pasan con escenarios determinísticos
5. ✅ La UI/Engine no cambia (API de Simulator compatible)

---

## 🔄 Próximos Pasos

1. **Revisar y aprobar este plan**
2. **Crear branch**: `refactor/simulator-json-based`
3. **Ejecutar Fase 1**: Crear ScenarioLoader
4. **Validar con 1 escenario real**: Probar integración
5. **Continuar Fases 2-4**: Implementación completa
6. **Merge a main**: Con tests pasando

---

## 📚 Referencias

- JSON Schema: https://json-schema.org/
- Pydantic Validation: https://docs.pydantic.dev/
- Dataclasses: https://docs.python.org/3/library/dataclasses.html

---

## 🔍 Cómo Capturar Datos Reales del Portal

Para crear escenarios con datos reales, sigue estos pasos:

### 1. Abrir DevTools en el Navegador

1. Navega a: https://webecommerce.cba.gov.ar/VistaPublica/SubastaVivoAccesoPublico.aspx
2. Abre DevTools (F12)
3. Ve a la pestaña **Network**
4. Filtra por **XHR**

### 2. Capturar el Request `BuscarOfertas`

1. Observa las requests que se hacen cada segundo
2. Busca: `SubastaVivoAccesoPublico.aspx/BuscarOfertas`
3. Click derecho → **Copy → Copy Response**

### 3. Estructura del Response

El portal devuelve:

```json
{
  "d": "[{\"id_oferta_subasta\":1,\"id_renglon\":836160,...}]@@$ 21.696.480,0000@@$ 20.015.101,6000@@"
}
```

Donde:
- **Primera parte** (antes de `@@`): Array JSON stringificado con ofertas
- **Segunda parte**: Presupuesto oficial con formato `$ X.XXX.XXX,XXXX`
- **Tercera parte**: Oferta mínima a superar con formato `$ X.XXX.XXX,XXXX`

### 4. Crear Entry en el Timeline

```json
{
  "tick": 0,
  "hora": "10:00:00",
  "status": 200,
  "renglones": [
    {
      "id_renglon": "836160",
      "descripcion": "IMPRESORA LASER",
      "response_json": {
        "d": "<PEGAR_AQUÍ_EL_RESPONSE_CAPTURADO>"
      }
    }
  ]
}
```

### 5. Capturar Múltiples Snapshots

Para un escenario realista:

1. **Tick 0**: Snapshot inicial (captura en tiempo T)
2. **Tick 3**: Espera 3 minutos, captura cambio de precio
3. **Tick 7**: Espera 4 minutos, captura otro cambio
4. **Tick N**: Repite hasta tener 4-5 cambios

### 6. Simular Errores HTTP

Para forzar un error en el portal:

- Desconecta el WiFi momentáneamente
- O usa DevTools → **Network** → **Offline** durante 1 tick
- Captura el error HTTP 500/502/503
- Agrégalo al timeline:

```json
{
  "tick": 5,
  "hora": "10:05:00",
  "status": 500,
  "error_message": "Internal Server Error"
}
```

### 7. Validar el JSON

```bash
# Verifica que el JSON sea válido
python -m json.tool data/test_scenarios/mi_escenario.json

# O usa el loader
python -c "from app.core.scenario_loader import ScenarioLoader; ScenarioLoader.load('data/test_scenarios/mi_escenario.json')"
```

---

**¿Listo para arrancar? 🚀**
