# tests/test_scenario_loader.py
"""
Tests unitarios para ScenarioLoader.
"""

import json
from pathlib import Path

from app.core.scenario_loader import ScenarioLoader, ScenarioConfig


def test_load_controlled_real_scenario():
    """Test: Cargar scenario_controlled_real.json"""
    project_root = Path(__file__).resolve().parent.parent
    scenario_path = project_root / "data" / "test_scenarios" / "scenario_controlled_real.json"
    
    config = ScenarioLoader.load(scenario_path)
    
    assert config.scenario_name == "controlled_real_scenario"
    assert config.id_cot == "22053"
    assert len(config.timeline) > 0
    assert config.tick_duration_seconds == 60.0
    assert config.max_ticks == 20


def test_timeline_validation():
    """Test: Validación de timeline (ticks ordenados)"""
    project_root = Path(__file__).resolve().parent.parent
    scenario_path = project_root / "data" / "test_scenarios" / "scenario_controlled_real.json"
    
    config = ScenarioLoader.load(scenario_path)
    
    # Verificar que los ticks están ordenados
    ticks = [entry.tick for entry in config.timeline]
    assert ticks == sorted(ticks), "Los ticks no están ordenados"




def test_scenario_with_http_errors():
    """Test: Escenario con errores HTTP"""
    project_root = Path(__file__).resolve().parent.parent
    scenario_path = project_root / "data" / "test_scenarios" / "scenario_controlled_real.json"
    
    # Usar el escenario que si tiene errores HTTP
    config = ScenarioLoader.load(scenario_path)
    
    # Buscar entradas con status != 200
    http_errors = [e for e in config.timeline if e.status != 200]
    
    assert len(http_errors) == 2, f"Se esperaban 2 errores HTTP, se encontraron {len(http_errors)}"
    assert any(e.status == 500 for e in http_errors), "No hay HTTP 500"



if __name__ == "__main__":
    print("🧪 Ejecutando tests unitarios de ScenarioLoader...\n")
    
    test_load_controlled_real_scenario()
    print("✓ test_load_controlled_real_scenario")
    
    test_timeline_validation()
    print("✓ test_timeline_validation")
    
    test_scenario_with_http_errors()
    print("✓ test_scenario_with_http_errors")
    
    print("\n✅ Todos los tests pasaron correctamente")
