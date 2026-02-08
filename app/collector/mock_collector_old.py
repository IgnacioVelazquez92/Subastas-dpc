# app/collector/mock_collector.py
"""
Collector simulado (MockCollector).

Objetivo:
- Probar UX/UI, alertas, seguridad y observabilidad SIN Playwright.
- Emitir el MISMO contrato de eventos que PlaywrightCollector:
  - SNAPSHOT con renglones enriquecidos (cantidad, precio_referencia, presupuesto)
  - UPDATE con mejor/oferta_min/presupuesto/mensaje/http_status

Soporta dos modos:
1. Legacy: Usar Simulator (hardcodeado) - deprecado
2. V2: Usar SimulatorV2 con escenarios JSON (recomendado)
"""

from __future__ import annotations

import time
from pathlib import Path
from threading import Thread
from queue import Queue
from typing import Optional

from app.collector.base import BaseCollector
from app.core.simulator import Simulator
from app.core.events import EventType, info, warn, error

# Import opcional de SimulatorV2
try:
    from app.core.simulator_v2 import SimulatorV2, load_simulator_from_file
    HAS_SIMULATOR_V2 = True
except ImportError:
    HAS_SIMULATOR_V2 = False
    SimulatorV2 = None


class MockCollector(BaseCollector):
    def __init__(
        self,
        *,
        out_q: Queue,
        id_cot: str = "",
        renglones: Optional[list[tuple[str, str]]] = None,
        poll_seconds: float = 1.0,
        scenario_path: Optional[str] = None,
    ):
        """
        Inicializa MockCollector.
        
        Args:
            out_q: Cola de salida para eventos
            id_cot: ID de cotización (solo para modo legacy)
            renglones: Lista de (id_renglon, descripción) (solo para modo legacy)
            poll_seconds: Intervalo entre ticks
            scenario_path: Path a JSON de escenario (activa modo V2)
        """
        super().__init__(out_q=out_q)

        self.poll_seconds = max(0.2, float(poll_seconds))
        self._thread: Thread | None = None
        self._running = False
        self._tick = 0
        self._snapshot_sent = False
        self._ended_renglones: set[str] = set()
        
        # Detectar modo: V2 (escenario JSON) o Legacy (hardcodeado)
        self.use_v2 = scenario_path is not None
        
        if self.use_v2:
            if not HAS_SIMULATOR_V2:
                raise ImportError("SimulatorV2 no disponible. Instala las dependencias necesarias.")
            
            # Modo V2: Cargar escenario JSON
            self.sim_v2 = load_simulator_from_file(scenario_path)
            self.id_cot = self.sim_v2.id_cot
            self.renglones = self.sim_v2.renglones
            self._desc_by_id: dict[str, str] = {rid: desc for rid, desc in self.renglones}
            self.sim = None  # No usar legacy
            
            self.emit(info(
                EventType.START, 
                f"MockCollector V2 (escenario: {Path(scenario_path).name})"
            ))
        else:
            # Modo Legacy: Usar Simulator hardcodeado
            self.id_cot = str(id_cot)
            self.renglones = [(str(rid), str(desc)) for rid, desc in (renglones or [])]
            self._desc_by_id: dict[str, str] = {rid: desc for rid, desc in self.renglones}
            self.sim = Simulator(id_cot=self.id_cot, renglones=self.renglones)
            self.sim_v2 = None
            
            import warnings
            warnings.warn(
                "MockCollector en modo Legacy (Simulator hardcodeado). "
                "Se recomienda usar scenario_path con SimulatorV2.",
                DeprecationWarning,
                stacklevel=2
            )

    def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._snapshot_sent = False
        self._ended_renglones.clear()

        # SNAPSHOT inicial (alineado a Playwright: renglones enriquecidos)
        if not self._snapshot_sent:
            self._snapshot_sent = True

            # inventamos datos “de subasta” que Playwright traería:
            # cantidad, precio_referencia (subasta), presupuesto
            enriched = []
            for rid, desc in self.renglones:
                rid_int = 0
                try:
                    rid_int = int(rid)
                except Exception:
                    rid_int = abs(hash(rid)) % 10_000

                cantidad = float((rid_int % 50) + 1)  # 1..50
                # precio referencia unitario “subasta” (determinístico)
                precio_ref_unit = 1500.0 + (rid_int % 25) * 125.0
                presupuesto = float(cantidad * precio_ref_unit * 1.05)

                enriched.append(
                    {
                        "value": rid,
                        "text": desc,
                        "cantidad": cantidad,
                        "precio_referencia": float(precio_ref_unit),  # unitario (subasta)
                        "presupuesto": float(presupuesto),
                    }
                )

            self.emit(
                info(
                    EventType.SNAPSHOT,
                    "SNAPSHOT (MOCK) inicial",
                    payload={
                        "id_cot": self.id_cot,
                        "margen": "0,0050",
                        "subasta_url": "MOCK://subasta",
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

            # Ejecutar tick según el modo
            if self.use_v2:
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
            else:
                # Modo legacy
                states = self.sim.tick()

            for st in states:
                rid = str(st.id_renglon)
                desc = self._desc_by_id.get(rid, "")

                # Error HTTP simulado (solo legacy)
                if not self.use_v2 and st.http_status != 200:
                    self.emit(
                        warn(
                            EventType.HTTP_ERROR,
                            f"HTTP {st.http_status} en renglón {rid}",
                            payload={
                                "id_cot": self.id_cot,
                                "id_renglon": rid,
                                "desc": desc,
                                "http_status": int(st.http_status),
                            },
                        )
                    )
                    continue

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
                            "http_status": 200,
                        },
                    )
                )

            time.sleep(self.poll_seconds)

        self.emit(info(EventType.STOP, f"MockCollector loop finalizado (id_cot={self.id_cot})"))
