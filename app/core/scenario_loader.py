# app/core/scenario_loader.py
"""
Cargador de escenarios JSON para el simulador V2.

Lee archivos JSON con datos reales del portal y timeline controlado,
permitiendo escenarios de prueba 100% reproducibles.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class RenglonResponse:
    """Respuesta real del portal para un renglón."""
    id_renglon: str
    descripcion: str
    response_json: Dict[str, str]  # {"d": "...@@...@@..."}


@dataclass
class TimelineEntry:
    """
    Una entrada del timeline con hora, status HTTP y data.
    
    Representa el estado del sistema en un tick específico:
    - tick: número de iteración (0 = snapshot inicial)
    - hora: timestamp HH:MM:SS
    - status: código HTTP (200 = OK, 500/502/503 = error)
    - renglones: responses reales del portal (si status=200)
    - error_message: mensaje de error (si status != 200)
    - event: evento especial (end_auction, pause, etc.)
    """
    tick: int
    hora: str
    status: int
    description: Optional[str] = None
    renglones: Optional[List[RenglonResponse]] = None
    error_message: Optional[str] = None
    event: Optional[str] = None
    message: Optional[str] = None


@dataclass
class ScenarioConfig:
    """Configuración completa de un escenario de simulación."""
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
    """Carga y parsea archivos JSON de escenarios."""
    
    @staticmethod
    def load(path: Path) -> ScenarioConfig:
        """
        Carga un archivo JSON de escenario.
        
        Args:
            path: Ruta al archivo JSON del escenario
            
        Returns:
            ScenarioConfig con toda la configuración parseada
            
        Raises:
            FileNotFoundError: Si el archivo no existe
            ValueError: Si el JSON es inválido o faltan campos requeridos
            json.JSONDecodeError: Si el JSON está mal formado
        """
        if not path.exists():
            raise FileNotFoundError(f"Archivo de escenario no encontrado: {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Validar campos requeridos
        ScenarioLoader._validate_required_fields(data)
        
        # Parse timeline
        timeline = []
        for entry_data in data.get("timeline", []):
            renglones = None
            if "renglones" in entry_data:
                renglones = [
                    RenglonResponse(
                        id_renglon=r["id_renglon"],
                        descripcion=r.get("descripcion", ""),
                        response_json=r["response_json"]
                    )
                    for r in entry_data["renglones"]
                ]
            
            timeline.append(TimelineEntry(
                tick=entry_data["tick"],
                hora=entry_data["hora"],
                status=entry_data["status"],
                description=entry_data.get("description"),
                renglones=renglones,
                error_message=entry_data.get("error_message"),
                event=entry_data.get("event"),
                message=entry_data.get("message")
            ))
        
        # Construir ScenarioConfig
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
    def _validate_required_fields(data: Dict[str, Any]) -> None:
        """Valida que el JSON tenga todos los campos requeridos."""
        required_fields = {
            "scenario_name": str,
            "description": str,
            "subasta": dict,
            "timeline": list,
            "config": dict
        }
        
        for field, expected_type in required_fields.items():
            if field not in data:
                raise ValueError(f"Campo requerido faltante: '{field}'")
            if not isinstance(data[field], expected_type):
                raise ValueError(f"Campo '{field}' debe ser {expected_type.__name__}")
        
        # Validar subasta
        if "id_cot" not in data["subasta"]:
            raise ValueError("Campo requerido faltante: 'subasta.id_cot'")
        if "url" not in data["subasta"]:
            raise ValueError("Campo requerido faltante: 'subasta.url'")
        
        # Validar config
        if "tick_duration_seconds" not in data["config"]:
            raise ValueError("Campo requerido faltante: 'config.tick_duration_seconds'")
        if "max_ticks" not in data["config"]:
            raise ValueError("Campo requerido faltante: 'config.max_ticks'")
        
        # Validar timeline
        if not data["timeline"]:
            raise ValueError("El timeline no puede estar vacío")
        
        for i, entry in enumerate(data["timeline"]):
            if "tick" not in entry:
                raise ValueError(f"Timeline[{i}]: falta campo 'tick'")
            if "hora" not in entry:
                raise ValueError(f"Timeline[{i}]: falta campo 'hora'")
            if "status" not in entry:
                raise ValueError(f"Timeline[{i}]: falta campo 'status'")
            
            # Validar status HTTP válido
            valid_statuses = [200, 500, 502, 503, 504]
            if entry["status"] not in valid_statuses:
                raise ValueError(f"Timeline[{i}]: status HTTP inválido {entry['status']} (válidos: {valid_statuses})")
    
    @staticmethod
    def parse_portal_response(response_json: Dict[str, str]) -> Dict[str, Any]:
        """
        Parse del formato real del portal:
        {"d": "[{...ofertas...}]@@presupuesto@@oferta_min@@"}
        
        Args:
            response_json: Diccionario con campo "d" en formato portal
            
        Returns:
            {
                "ofertas": [...],  # Array de ofertas parseadas
                "presupuesto_txt": "$ ...",
                "oferta_min_txt": "$ ..."
            }
            
        Raises:
            ValueError: Si el formato es inválido
        """
        d = response_json.get("d", "")
        
        if not d:
            raise ValueError("El campo 'd' está vacío en response_json")
        
        # Split por '@@'
        parts = d.split("@@")
        
        if len(parts) < 3:
            raise ValueError(
                f"Formato inválido: esperado 3 partes separadas por '@@', "
                f"encontrado {len(parts)}. Formato esperado: "
                f"'[{{...}}]@@presupuesto@@oferta_min@@'"
            )
        
        ofertas_json_str = parts[0]
        presupuesto_txt = parts[1]
        oferta_min_txt = parts[2]
        
        # Parse ofertas (es un array JSON stringificado)
        try:
            ofertas = json.loads(ofertas_json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"No se pudo parsear el array de ofertas: {e}")
        
        if not isinstance(ofertas, list):
            raise ValueError(f"ofertas debe ser un array, encontrado: {type(ofertas)}")
        
        return {
            "ofertas": ofertas,
            "presupuesto_txt": presupuesto_txt,
            "oferta_min_txt": oferta_min_txt
        }
