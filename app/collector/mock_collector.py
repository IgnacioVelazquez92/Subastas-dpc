# app/collector/mock_collector.py
"""
MockCollector - Simulación V2 con escenarios JSON.

Carga un escenario JSON y ejecuta timeline exacto.
SIN datos hardcodeados - todo debe venir del JSON.

Emite los mismos eventos que PlaywrightCollector:
- SNAPSHOT: renglones con precios iniciales
- UPDATE: cambios de mejor oferta
- HTTP_ERROR: errores simulados (500, 502, 503)
- END: fin de la subasta
"""

from __future__ import annotations

import time
from pathlib import Path
from threading import Thread
from queue import Queue

from app.collector.base import BaseCollector
from app.core.simulator_v2 import SimulatorV2, load_simulator_from_file
from app.core.events import EventType, info, warn, error


class MockCollector(BaseCollector):
    def __init__(
        self,
        *,
        out_q: Queue,
        poll_seconds: float = 1.0,
        scenario_path: str,
    ):
        """
        Inicializa MockCollector V2.
        
        Args:
            out_q: Cola de salida para eventos
            poll_seconds: Intervalo entre ticks (segundos)
            scenario_path: Path REQUERIDO a JSON de escenario (sin datos hardcodeados)
        """
        super().__init__(out_q=out_q)

        self.poll_seconds = max(0.2, float(poll_seconds))
        self._thread: Thread | None = None
        self._running = False
        self._tick = 0
        self._snapshot_sent = False
        self._ended_renglones: set[str] = set()
        
        # V2: Cargar escenario JSON
        self.sim_v2 = load_simulator_from_file(scenario_path)
        self.id_cot = self.sim_v2.id_cot
        
        # Renglones se extraerán en start() después del primer tick
        self.renglones = []
        self._desc_by_id: dict[str, str] = {}
        
        self.emit(info(
            EventType.START, 
            f"MockCollector V2 (escenario: {Path(scenario_path).name})"
        ))

    def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._snapshot_sent = False
        self._ended_renglones.clear()

        # SNAPSHOT inicial (alineado a Playwright: renglones enriquecidos)
        if not self._snapshot_sent:
            self._snapshot_sent = True

            # Ejecutar primer tick para obtener datos reales del escenario
            http_status, states, _ = self.sim_v2.tick()
            
            # Extraer renglones del simulador después del primer tick
            self.renglones = self.sim_v2.renglones
            self._desc_by_id = {rid: desc for rid, desc in self.renglones}
            
            enriched = []
            for st in states:
                rid = str(st.id_renglon)
                desc = self._desc_by_id.get(rid, "")
                
                # Usar datos reales del escenario
                enriched.append(
                    {
                        "value": rid,
                        "text": desc,
                        "cantidad": 1.0,  # No disponible en JSON
                        "precio_referencia": st.presupuesto_val if st.presupuesto_val else 0.0,
                        "presupuesto": st.presupuesto_val if st.presupuesto_val else 0.0,
                    }
                )
            
            self.emit(
                info(
                    EventType.SNAPSHOT,
                    f"SNAPSHOT V2 (escenario: {self.sim_v2.scenario.scenario_name})",
                    payload={
                        "id_cot": self.id_cot,
                        "margen": "0,0050",
                        "subasta_url": "MOCK://subasta/v2",
                        "renglones": enriched,
                    },
                )
            )

        self._thread = Thread(target=self._loop, daemon=True)
        self._thread.start()

        self.emit(info(EventType.START, f"MockCollector iniciado (id_cot={self.id_cot})"))

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self.emit(info(EventType.STOP, f"MockCollector detenido (id_cot={self.id_cot})"))

    def set_poll_seconds(self, seconds: float) -> None:
        self.poll_seconds = max(0.2, float(seconds))

    def _loop(self) -> None:
        while self._running:
            self._tick += 1

            # Heartbeat cada ~10 ticks
            if self._tick % 10 == 1:
                self.emit(
                    info(
                        EventType.HEARTBEAT,
                        f"Heartbeat mock (tick={self._tick})",
                        payload={"id_cot": self.id_cot},
                    )
                )

            # Ejecutar tick del escenario
            http_status, states, ended = self.sim_v2.tick()
            
            # Manejar error HTTP
            if http_status != 200:
                self.emit(
                    warn(
                        EventType.HTTP_ERROR,
                        f"HTTP {http_status} - {self.sim_v2.last_error_message}",
                        payload={
                            "id_cot": self.id_cot,
                            "http_status": int(http_status),
                            "error_message": self.sim_v2.last_error_message,
                        },
                    )
                )
                time.sleep(self.poll_seconds)
                continue
            
            # Manejar finalización global
            if ended:
                self.emit(
                    info(
                        EventType.END,
                        "Subasta finalizada (escenario completado)",
                        payload={"id_cot": self.id_cot},
                    )
                )
                self._running = False
                break

            # Procesar estados y emitir UPDATEs
            for st in states:
                rid = str(st.id_renglon)
                desc = self._desc_by_id.get(rid, "")

                # Subasta finalizada por renglón
                if st.finalizada:
                    if rid not in self._ended_renglones:
                        self._ended_renglones.add(rid)
                        self.emit(
                            info(
                                EventType.END,
                                f"Subasta finalizada (renglón {rid})",
                                payload={
                                    "id_cot": self.id_cot,
                                    "id_renglon": rid,
                                    "desc": desc,
                                },
                            )
                        )
                    continue

                # Update normal (alineado a PlaywrightCollector)
                best = st.ofertas[0] if st.ofertas else None
                mejor_txt = best.monto_a_mostrar if best else ""
                mejor_val = float(best.monto) if best else None
                hora_ultima_oferta = best.hora if best else None

                self.emit(
                    info(
                        EventType.UPDATE,
                        f"Update renglón {rid}",
                        payload={
                            "id_cot": self.id_cot,
                            "id_renglon": rid,
                            "desc": desc,
                            "mejor_oferta_txt": mejor_txt,
                            "mejor_oferta_val": mejor_val,
                            "oferta_min_txt": st.oferta_min_txt,
                            "oferta_min_val": st.oferta_min_val,
                            "presupuesto_txt": st.presupuesto_txt,
                            "presupuesto_val": st.presupuesto_val,
                            "mensaje": st.mensaje,
                            "hora_ultima_oferta": hora_ultima_oferta,
                            "http_status": 200,
                        },
                    )
                )

            time.sleep(self.poll_seconds)

        self.emit(info(EventType.STOP, f"MockCollector loop finalizado (id_cot={self.id_cot})"))
