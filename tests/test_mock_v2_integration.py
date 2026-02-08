# tests/test_mock_v2_integration.py
"""
Test de integración para MockCollector V2 con escenarios JSON.
"""

from queue import Queue
import time
from pathlib import Path

from app.collector.mock_collector import MockCollector
from app.core.events import EventType


def test_mock_v2_with_scenario():
    """Prueba MockCollector V2 con scenario_controlled_real.json"""
    
    project_root = Path(__file__).resolve().parent.parent
    scenario_path = project_root / "data" / "test_scenarios" / "scenario_controlled_real.json"
    
    print(f"🧪 Test: MockCollector V2 con escenario {scenario_path.name}")
    print("=" * 80)
    
    # Cola de salida para eventos
    out_q = Queue()
    
    # Crear MockCollector en modo V2
    collector = MockCollector(
        out_q=out_q,
        scenario_path=str(scenario_path),
        poll_seconds=0.5,
    )
    
    print(f"✓ MockCollector V2 creado")
    print(f"✓ ID Cotización: {collector.id_cot}")
    print(f"✓ Renglones: {len(collector.renglones)}")
    print()
    
    # Iniciar collector
    collector.start()
    print("✓ Collector iniciado")
    print()
    
    # Recolectar eventos por 10 segundos
    print("📡 Eventos recibidos:")
    print("-" * 80)
    
    event_count = 0
    start_time = time.time()
    max_duration = 10  # segundos
    
    while time.time() - start_time < max_duration:
        if not out_q.empty():
            event = out_q.get_nowait()
            event_count += 1
            
            # Mostrar evento
            event_type = event.type
            message = event.message
            payload = event.payload or {}
            
            print(f"[{event_count}] {event_type}: {message}")
            
            # Mostrar payload relevante según tipo de evento
            if event_type == EventType.SNAPSHOT:
                renglones = payload.get("renglones", [])
                print(f"  → {len(renglones)} renglones en snapshot")
            
            elif event_type == EventType.UPDATE:
                rid = payload.get("id_renglon", "?")
                mejor = payload.get("mejor_oferta_txt", "?")
                print(f"  → Renglón {rid}: mejor oferta = {mejor}")
            
            elif event_type == EventType.HTTP_ERROR:
                http_status = payload.get("http_status", "?")
                error_msg = payload.get("error_message", "?")
                print(f"  → HTTP {http_status}: {error_msg}")
            
            elif event_type == EventType.END:
                print(f"  → Finalizado")
                break
            
            print()
        
        time.sleep(0.1)
    
    # Detener collector
    collector.stop()
    
    print("-" * 80)
    print(f"✓ Test completado: {event_count} eventos procesados")
    print()


if __name__ == "__main__":
    test_mock_v2_with_scenario()
