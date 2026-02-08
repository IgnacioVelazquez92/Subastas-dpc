# app/core/simulator_v2.py
"""
Simulador V2: Basado en timeline JSON con datos reales del portal.

Elimina 100% del código hardcodeado del simulator legacy.
Lee escenarios JSON y devuelve estados exactos definidos en el timeline.
"""

from __future__ import annotations

import copy
import json
from typing import Dict, List, Optional, Tuple

from app.core.scenario_loader import ScenarioConfig, ScenarioLoader, TimelineEntry
from app.core.simulator import BuscarOfertasState, Oferta, _money_txt
from app.utils.money import money_to_float


class SimulatorV2:
    """
    Simulador basado en timeline con datos reales del portal.
    
    - Lee escenarios JSON con ScenarioLoader
    - En cada tick, busca la entrada correspondiente en timeline
    - Devuelve el estado exacto definido en el JSON
    - Maneja status HTTP (200, 500, 502, 503)
    - 100% reproducible y predecible
    """
    
    def __init__(self, scenario: ScenarioConfig):
        """
        Inicializa el simulador con un escenario.
        
        Args:
            scenario: ScenarioConfig cargado desde JSON
        """
        self.scenario = scenario
        self._tick_count = 0
        self._states: Dict[str, BuscarOfertasState] = {}
        self._last_ok_states: Dict[str, BuscarOfertasState] = {}
        self._http_status = 200
        self._error_message = ""
        self._ended = False
        
        # Metadata para tracking
        self.id_cot = scenario.id_cot
        self.renglones: List[Tuple[str, str]] = []  # [(id_renglon, descripcion), ...]
    
    def tick(self) -> Tuple[int, List[BuscarOfertasState], bool]:
        """
        Ejecuta un tick del simulador.
        
        Returns:
            (http_status, states, ended) donde:
            - http_status: código HTTP (200, 500, 502, 503)
            - states: lista de BuscarOfertasState actualizados
            - ended: True si la subasta finalizó
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
                    state = self._parse_portal_response(renglon_resp, entry)
                    self._states[state.id_renglon] = state
                    self._last_ok_states[state.id_renglon] = copy.deepcopy(state)
                    states.append(state)
                    
                    # Registrar renglón si es nuevo
                    if (state.id_renglon, renglon_resp.descripcion) not in self.renglones:
                        self.renglones.append((state.id_renglon, renglon_resp.descripcion))
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
            # Error HTTP - devolver último estado OK pero con error
            self._error_message = entry.error_message or f"HTTP {http_status}"
            states = list(self._last_ok_states.values())
        
        self._http_status = http_status
        self._tick_count += 1
        
        return (http_status, states, self._ended)
    
    def _find_timeline_entry(self, tick: int) -> Optional[TimelineEntry]:
        """Busca la entrada del timeline para el tick dado."""
        for entry in self.scenario.timeline:
            if entry.tick == tick:
                return entry
        return None
    
    def _parse_portal_response(
        self, 
        renglon_resp, 
        entry: TimelineEntry
    ) -> BuscarOfertasState:
        """
        Convierte el response real del portal a BuscarOfertasState.
        
        Formato portal: {"d": "[{...ofertas...}]@@presupuesto@@oferta_min@@"}
        
        Args:
            renglon_resp: RenglonResponse con el response_json del portal
            entry: TimelineEntry para metadata (hora, mensaje)
            
        Returns:
            BuscarOfertasState compatible con el Engine
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
        
        # Mensaje del estado
        mensaje = entry.message or entry.description or "Subasta en curso"
        
        return BuscarOfertasState(
            id_renglon=renglon_resp.id_renglon,
            ofertas=ofertas,
            presupuesto_txt=parsed["presupuesto_txt"],
            oferta_min_txt=parsed["oferta_min_txt"],
            mensaje=mensaje,
            presupuesto_val=presupuesto_val,
            oferta_min_val=oferta_min_val,
            http_status=200,
            finalizada=False
        )
    
    @property
    def current_tick(self) -> int:
        """Tick actual del simulador."""
        return self._tick_count
    
    @property
    def is_ended(self) -> bool:
        """True si la simulación finalizó."""
        return self._ended
    
    @property
    def last_http_status(self) -> int:
        """Último status HTTP devuelto."""
        return self._http_status
    
    @property
    def last_error_message(self) -> str:
        """Último mensaje de error."""
        return self._error_message


def load_simulator_from_file(scenario_path: str) -> SimulatorV2:
    """
    Helper para cargar un SimulatorV2 desde un archivo JSON.
    
    Args:
        scenario_path: Ruta al archivo JSON del escenario
        
    Returns:
        SimulatorV2 inicializado con el escenario
        
    Example:
        sim = load_simulator_from_file("data/test_scenarios/scenario_controlled_real.json")
        status, states, ended = sim.tick()
    """
    from pathlib import Path
    
    path = Path(scenario_path)
    scenario = ScenarioLoader.load(path)
    return SimulatorV2(scenario)
