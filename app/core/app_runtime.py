# app/core/app_runtime.py
"""
Orquestador de runtime (AppRuntime).

Objetivo:
- Conectar Collector -> Engine -> UI mediante colas.
- Permitir ejecutar el sistema en modo:
  - MOCK (simulador)
  - PLAYWRIGHT (real)
sin que la UI tenga que conocer detalles internos.

Mejora clave en esta versión:
- STOP real:
  - runtime.stop() detiene collector y engine loop.
  - la UI puede llamar runtime.stop() al cerrar.
  - si el Engine decide STOP por seguridad, la UI lo ve en eventos,
    pero el corte efectivo del Collector lo hace el runtime (por cierre) o por UI.

Nota:
- Engine corre en un thread dedicado.
- No bloqueamos la UI.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Thread, Event as ThreadEvent
from queue import Queue, Empty
from typing import Literal, Optional

from app.db.database import Database
from app.core.engine import Engine, EngineConfig
from app.core.events import EventType, info
from app.utils.time import now_iso
from app.excel.excel_io import export_subasta_to_excel, import_excel_to_rows
from app.collector.mock_collector import MockCollector
from app.collector.playwright_collector import PlaywrightCollector

Mode = Literal["MOCK", "PLAYWRIGHT"]


@dataclass
class RuntimeHandles:
    """
    Referencias útiles para la UI o debugging.

    Importante:
    - engine_out_q: cola que la UI debe consumir.
    - collector_cmd_q: cola de comandos hacia collector (Playwright).
    """
    mode: Mode
    collector_cmd_q: Queue
    collector_out_q: Queue
    engine_out_q: Queue

    collector: object
    engine: Engine

    # opcional: para permitir UI cerrar runtime sin imports circulares
    runtime: "AppRuntime"


class AppRuntime:
    def __init__(
        self,
        *,
        db: Database,
        mode: Mode = "MOCK",
        headless: bool = False,
        poll_seconds: float = 1.0,
        autostart_collector: bool = True,
        scenario_path: Optional[str] = None,
    ):
        self.db = db
        self.mode: Mode = mode
        self.headless = bool(headless)
        self.poll_seconds = float(poll_seconds)
        self.scenario_path = scenario_path
        self.autostart_collector = bool(autostart_collector)

        # Colas
        self.collector_cmd_q: Queue = Queue()
        self.collector_out_q: Queue = Queue()  # eventos crudos del collector
        self.engine_out_q: Queue = Queue()     # eventos procesados del engine (UI)
        self.control_q: Queue = Queue()        # control actions desde Engine

        # Señal de stop del runtime
        self._stop_evt = ThreadEvent()
        self._engine_thread: Optional[Thread] = None

        # Engine
        self.engine = Engine(
            db=self.db,
            in_q=self.collector_out_q,
            out_q=self.engine_out_q,
            control_q=self.control_q,
            config=EngineConfig(agg_window_seconds=30),
        )
        self.engine.set_current_poll_seconds(self.poll_seconds)

        # Collector (según modo)
        self.collector = self._build_collector()

    def _build_collector(self):
        if self.mode == "PLAYWRIGHT":
            return PlaywrightCollector(
                cmd_q=self.collector_cmd_q,
                out_q=self.collector_out_q,
                headless=self.headless,
                poll_seconds=self.poll_seconds,
            )

        # MOCK: SimulatorV2 con escenarios JSON (sin datos hardcodeados)
        if not self.scenario_path:
            raise ValueError("scenario_path es requerido en modo MOCK")
        return MockCollector(
            out_q=self.collector_out_q,
            poll_seconds=self.poll_seconds,
            scenario_path=self.scenario_path,
        )

    def update_renglon_excel(
        self,
        *,
        renglon_id: int,
        unidad_medida: str | None = None,
        marca: str | None = None,
        observaciones: str | None = None,
        conversion_usd: float | None = None,
        costo_final_pesos: float | None = None,
        renta: float | None = None,
    ) -> None:
        existing = self.db.get_renglon_excel(renglon_id=renglon_id) or {}
        self.db.upsert_renglon_excel(
            renglon_id=renglon_id,
            unidad_medida=unidad_medida,
            cantidad=existing.get("cantidad"),
            marca=marca,
            observaciones=observaciones,
            conversion_usd=conversion_usd,
            costo_usd=existing.get("costo_usd"),
            costo_final_pesos=costo_final_pesos,
            renta=renta,
            precio_referencia=existing.get("precio_referencia"),
            precio_referencia_subasta=existing.get("precio_referencia_subasta"),
            updated_at=now_iso(),
        )

    def update_renglon_config(
        self,
        *,
        renglon_id: int,
        costo_subtotal: float | None = None,
        seguir: bool | None = None,
        oferta_mia: bool | None = None,
        utilidad_min_pct: float | None = None,
        ocultar_bajo_umbral: bool | None = None,
    ) -> None:
        cfg = self.db.get_renglon_config(renglon_id=renglon_id) or {}

        merged_costo = cfg.get("costo_subtotal") if costo_subtotal is None else costo_subtotal
        merged_seguir = bool(cfg.get("seguir")) if seguir is None else bool(seguir)
        merged_oferta_mia = bool(cfg.get("oferta_mia")) if oferta_mia is None else bool(oferta_mia)

        utilidad_min_pct = float(
            cfg.get("utilidad_min_pct", self.engine.config.utilidad_min_pct_default)
        )
        ocultar_bajo_umbral = bool(
            cfg.get("ocultar_bajo_umbral", self.engine.config.ocultar_bajo_umbral_default)
        )

        if utilidad_min_pct is not None:
            utilidad_min_pct = float(utilidad_min_pct)
        if ocultar_bajo_umbral is not None:
            ocultar_bajo_umbral = bool(ocultar_bajo_umbral)

        self.db.upsert_renglon_config(
            renglon_id=renglon_id,
            costo_subtotal=merged_costo,
            oferta_mia=merged_oferta_mia,
            seguir=merged_seguir,
            utilidad_min_pct=utilidad_min_pct,
            ocultar_bajo_umbral=ocultar_bajo_umbral,
            updated_at=now_iso(),
        )

    def export_excel(self, *, out_path: str) -> None:
        subasta_id = self.db.get_running_subasta_id() or self.db.get_latest_subasta_id()
        if not subasta_id:
            raise ValueError("No hay subastas en la base")

        rows = self.db.fetch_export_rows(subasta_id=subasta_id)
        export_subasta_to_excel(rows=rows, out_path=out_path)

    def import_excel(self, *, file_path: str) -> int:
        rows = import_excel_to_rows(file_path=file_path)
        updated = 0

        def _to_float(val):
            if val is None or val == "":
                return None
            try:
                # soporta números como texto con miles/decimales estilo AR
                s = str(val).strip()
                if not s:
                    return None
                return float(s.replace(".", "").replace(",", "."))
            except Exception:
                return None

        for row in rows:
            id_cot = row.get("ID SUBASTA")
            id_renglon = row.get("ITEM")
            if id_cot is None or id_renglon is None:
                continue

            subasta_id = self.db.get_subasta_id_by_id_cot(id_cot=str(id_cot))
            if not subasta_id:
                continue

            renglon_id = self.db.get_renglon_id_by_keys(
                subasta_id=subasta_id,
                id_renglon=str(id_renglon),
            )
            if not renglon_id:
                continue

            # Traer lo existente para NO pisar campos "del sistema"
            existing = self.db.get_renglon_excel(renglon_id=renglon_id) or {}

            self.db.upsert_renglon_excel(
                renglon_id=renglon_id,
                unidad_medida=(row.get("UNIDAD DE MEDIDA") or None),
                cantidad=_to_float(row.get("CANTIDAD")),
                marca=(row.get("MARCA") or None),
                observaciones=(row.get("Observaciones") or None),
                conversion_usd=_to_float(row.get("CONVERSIÓN USD")),
                costo_usd=existing.get("costo_usd"),
                costo_final_pesos=_to_float(row.get("COSTO FINAL PESOS")),
                renta=_to_float(row.get("RENTA")),
                precio_referencia=existing.get("precio_referencia"),
                # mantener el valor proveniente de la subasta/collector
                precio_referencia_subasta=existing.get("precio_referencia_subasta"),
                updated_at=now_iso(),
            )
            updated += 1

        return updated

    def get_renglon_config(self, *, renglon_id: int) -> dict | None:
        return self.db.get_renglon_config(renglon_id=renglon_id)

    def get_ui_config(self, *, key: str) -> str | None:
        return self.db.get_ui_config(key=key)

    def set_ui_config(self, *, key: str, value: str) -> None:
        self.db.set_ui_config(key=key, value=value)

    def start_collector(self) -> None:
        try:
            self.collector.start()
        except Exception as e:
            self.engine_out_q.put(info(EventType.EXCEPTION, f"Collector no pudo iniciar: {e}"))

    def cleanup_data(self, *, mode: str = "logs") -> None:
        """Limpia datos. Si mode != 'logs', pausa el collector temporalmente."""
        was_running = False
        
        # Si vamos a borrar estados/renglones, pausar el collector
        if mode in ("states", "all"):
            was_running = self.collector.running
            if was_running:
                try:
                    self.collector.stop()
                    time.sleep(0.3)  # dar tiempo a que termine el loop
                except Exception:
                    pass
        
        # Realizar cleanup
        try:
            if mode == "logs":
                self.db.cleanup_logs()
            elif mode == "states":
                self.db.cleanup_states()
            elif mode == "all":
                self.db.cleanup_all()
            else:
                raise ValueError("Modo de limpieza inválido")
        finally:
            # Reiniciar collector si estaba corriendo
            if was_running and mode in ("states", "all"):
                try:
                    self.collector.start()
                except Exception as e:
                    self.engine_out_q.put(info(EventType.EXCEPTION, f"No se pudo reiniciar collector: {e}"))

    # -------------------------
    # API
    # -------------------------
    def start(self) -> RuntimeHandles:
        """
        Inicia Engine (thread) y Collector.
        """
        if self._engine_thread and self._engine_thread.is_alive():
            # ya está corriendo
            return self._handles()

        self._stop_evt.clear()

        # Thread del engine
        self._engine_thread = Thread(target=self._engine_loop, daemon=True)
        self._engine_thread.start()

        # Evento inicial para UI
        self.engine_out_q.put(info(EventType.START, f"Runtime iniciado modo={self.mode}"))

        # Iniciar collector
        if self.autostart_collector and self.mode != "PLAYWRIGHT":
            try:
                self.collector.start()
            except Exception as e:
                self.engine_out_q.put(info(EventType.EXCEPTION, f"Collector no pudo iniciar: {e}"))
        elif self.autostart_collector and self.mode == "PLAYWRIGHT":
            try:
                self.collector.start()
            except Exception as e:
                self.engine_out_q.put(info(EventType.EXCEPTION, f"Collector no pudo iniciar: {e}"))

        return self._handles()

    def stop(self) -> None:
        """
        Detiene collector y engine loop (no bloquea la UI).
        """
        # Señalar stop al engine loop
        self._stop_evt.set()

        # Detener collector real
        try:
            self.collector.stop()
        except Exception:
            pass

        # Avisar UI
        try:
            self.engine_out_q.put(info(EventType.STOP, "Runtime stop solicitado"))
        except Exception:
            pass

    # -------------------------
    # Internals
    # -------------------------
    def _handles(self) -> RuntimeHandles:
        return RuntimeHandles(
            mode=self.mode,
            collector_cmd_q=self.collector_cmd_q,
            collector_out_q=self.collector_out_q,
            engine_out_q=self.engine_out_q,
            collector=self.collector,
            engine=self.engine,
            runtime=self,
        )

    def _apply_control_actions(self) -> None:
        while True:
            try:
                cmd = self.control_q.get_nowait()
            except Empty:
                return

            action = cmd.get("action")
            if action == "STOP":
                self.stop()
            elif action == "BACKOFF":
                seconds = float(cmd.get("seconds", self.poll_seconds))
                self.poll_seconds = seconds
                try:
                    self.collector.set_poll_seconds(seconds)
                except Exception:
                    pass
                try:
                    self.engine.set_current_poll_seconds(seconds)
                except Exception:
                    pass

    def _engine_loop(self) -> None:
        """
        Loop del engine: consume eventos del collector y los procesa.
        Se detiene cuando stop() marca _stop_evt.
        """
        while not self._stop_evt.is_set():
            # Procesa a pequeños pasos
            self.engine.run_once(timeout=0.1)
            self._apply_control_actions()
            time.sleep(0.001)

        # Cierre del loop
        try:
            self.engine_out_q.put(info(EventType.STOP, "Engine loop detenido"))
        except Exception:
            pass
