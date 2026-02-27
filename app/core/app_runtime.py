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
        self.base_poll_seconds = max(0.2, float(poll_seconds))
        self.poll_seconds = float(self.base_poll_seconds)
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
        self.engine.set_base_poll_seconds(self.base_poll_seconds)
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
        obs_usuario: str | None = None,
        conversion_usd: float | None = None,
        costo_unit_ars: float | None = None,
        costo_total_ars: float | None = None,
        costo_unit_usd: float | None = None,
        costo_total_usd: float | None = None,
        renta_minima: float | None = None,
    ) -> None:
        existing = self.db.get_renglon_excel(renglon_id=renglon_id) or {}
        # 🔥 CRÍTICO: Guardar en AMBAS columnas (nueva y legacy) para evitar pérdida de datos
        conv_usd_value = conversion_usd if conversion_usd is not None else existing.get("conv_usd")
        self.db.upsert_renglon_excel(
            renglon_id=renglon_id,
            unidad_medida=unidad_medida,
            cantidad=existing.get("cantidad"),
            marca=marca,
            obs_usuario=obs_usuario,
            conv_usd=conv_usd_value,  # Guardar en columna NUEVA
            conversion_usd=conversion_usd,  # Guardar en columna LEGACY
            costo_unit_ars=costo_unit_ars,
            costo_total_ars=costo_total_ars,
            renta_minima=renta_minima,
            costo_unit_usd=costo_unit_usd if costo_unit_usd is not None else existing.get("costo_unit_usd"),
            costo_total_usd=costo_total_usd if costo_total_usd is not None else existing.get("costo_total_usd"),
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

        # 🔥 Preservar o actualizar utilidad_min_pct según argumento
        merged_utilidad_min_pct = cfg.get("utilidad_min_pct", self.engine.config.utilidad_min_pct_default)
        if utilidad_min_pct is not None:
            merged_utilidad_min_pct = float(utilidad_min_pct)
        else:
            merged_utilidad_min_pct = float(merged_utilidad_min_pct)
        
        merged_ocultar = bool(
            cfg.get("ocultar_bajo_umbral", self.engine.config.ocultar_bajo_umbral_default)
        ) if ocultar_bajo_umbral is None else bool(ocultar_bajo_umbral)

        self.db.upsert_renglon_config(
            renglon_id=renglon_id,
            costo_subtotal=merged_costo,
            oferta_mia=merged_oferta_mia,
            seguir=merged_seguir,
            utilidad_min_pct=merged_utilidad_min_pct,
            ocultar_bajo_umbral=merged_ocultar,
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
            if isinstance(val, (int, float)):
                return float(val)
            try:
                # soporta números como texto con miles/decimales estilo AR
                s = str(val).strip()
                if not s:
                    return None
                s = s.replace("%", "").strip()
                if "," in s and "." in s:
                    s = s.replace(".", "").replace(",", ".")
                elif "," in s and "." not in s:
                    parts = s.split(",")
                    if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
                        s = "".join(parts)
                    else:
                        s = s.replace(",", ".")
                elif "." in s and "," not in s:
                    parts = s.split(".")
                    if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
                        s = "".join(parts)
                return float(s)
            except Exception:
                return None
        
        def _normalize_id(val) -> str | None:
            if val is None:
                return None
            if isinstance(val, int):
                return str(val)
            if isinstance(val, float):
                return str(int(val)) if val.is_integer() else str(val)

            s = str(val).strip()
            if not s:
                return None
            try:
                if "." in s:
                    f = float(s)
                    if f.is_integer():
                        return str(int(f))
            except Exception:
                pass
            return s

        def _renta_to_fraction(val):
            """Convierte renta desde Excel a fracción (0-1) para BD.

            Acepta SOLO fracción:
            - 0.30 -> 0.30
            - 0.10 -> 0.10
            """
            if val is None or val == "":
                return None
            num = _to_float(val)
            if num is None:
                return None
            if num < 0:
                raise ValueError("RENTA MINIMA % debe ser >= 0")
            if num > 1.0:
                raise ValueError("RENTA MINIMA % debe estar entre 0 y 1 (ej: 0.30)")
            return num

        for row in rows:
            id_cot = _normalize_id(row.get("ID SUBASTA"))
            id_renglon = _normalize_id(row.get("ITEM"))
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

            # IMPORTANTE: Solo importamos USER_FIELDS
            # - Los CALC_FIELDS se recalculan automáticamente por el engine
            # - Los PLAYWRIGHT_FIELDS nunca deben ser sobrescritos por usuario
            try:
                renta_val = _renta_to_fraction(row.get("RENTA MINIMA %"))
            except ValueError as exc:
                raise ValueError(f"RENTA MINIMA % invalida en SUBASTA={id_cot}, ITEM={id_renglon}: {exc}")

            self.db.upsert_renglon_excel(
                renglon_id=renglon_id,
                unidad_medida=(row.get("UNIDAD DE MEDIDA") or None),
                marca=(row.get("MARCA") or None),
                obs_usuario=(row.get("OBS USUARIO") or None),
                conv_usd=_to_float(row.get("CONVERSIÓN USD")),
                costo_unit_ars=_to_float(row.get("COSTO UNIT ARS")),
                costo_total_ars=_to_float(row.get("COSTO TOTAL ARS")),
                renta_minima=renta_val,
                # Mantener valores de sistema (no sobrescribir)
                precio_referencia=existing.get("precio_referencia"),
                precio_referencia_subasta=existing.get("precio_referencia_subasta"),
                cantidad=existing.get("cantidad"),  # De Playwright, no del usuario
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

    def get_mi_id_proveedor(self) -> str | None:
        """Devuelve mi_id_proveedor de la subasta activa (o más reciente)."""
        subasta_id = self.db.get_running_subasta_id() or self.db.get_latest_subasta_id()
        if not subasta_id:
            return None
        return self.db.get_mi_id_proveedor(subasta_id=subasta_id)

    def set_mi_id_proveedor(self, value: str | None) -> None:
        """Guarda mi_id_proveedor en la subasta activa (o más reciente) e invalida cache del engine."""
        subasta_id = self.db.get_running_subasta_id() or self.db.get_latest_subasta_id()
        if not subasta_id:
            return
        self.db.set_mi_id_proveedor(
            subasta_id=subasta_id,
            mi_id_proveedor=value.strip() if value and value.strip() else None,
        )
        self.engine.refresh_mi_id_proveedor(subasta_id)


        try:
            if getattr(self.collector, "running", False):
                # Si ya esta corriendo, en Playwright intentamos abrir listado.
                if hasattr(self.collector, "open_listado"):
                    self.collector.open_listado()
                return
            self.collector.start()
        except Exception as e:
            self.engine_out_q.put(info(EventType.EXCEPTION, f"Collector no pudo iniciar: {e}"))

    def start_collector(self) -> None:
        """
        Inicia (o reinicia) el collector sin reiniciar el runtime completo.
        Útil para el botón 'Abrir navegador' en la UI.
        """
        try:
            # Si ya está corriendo, no volver a iniciar
            if getattr(self.collector, "running", False):
                self.engine_out_q.put(info(EventType.HEARTBEAT, "Collector ya estaba en ejecución"))
                return
            self.collector.start()
            self.engine_out_q.put(info(EventType.START, f"Collector iniciado (modo={self.mode})"))
        except Exception as e:
            self.engine_out_q.put(info(EventType.EXCEPTION, f"No se pudo iniciar collector: {e}"))
            raise

    def stop_collector(self) -> None:
        """
        Pausa el collector sin detener el runtime completo.
        """
        try:
            # Playwright: si soporta pausa de monitoreo, usarla.
            if hasattr(self.collector, "stop_monitoring"):
                self.collector.stop_monitoring()
            else:
                self.collector.stop()
            self.engine_out_q.put(info(EventType.STOP, "Collector pausado"))
        except Exception as e:
            self.engine_out_q.put(info(EventType.EXCEPTION, f"No se pudo pausar collector: {e}"))

    def set_intensive_monitoring(self, enabled: bool) -> None:
        """
        Alterna monitoreo intensivo en caliente.
        - ON: usa poll base (por ejemplo 1s).
        - OFF: usa modo sueño (poll más espaciado) manteniendo alertas.
        """
        try:
            if hasattr(self.collector, "set_intensive_monitoring"):
                self.collector.set_intensive_monitoring(bool(enabled))
            elif self.mode == "PLAYWRIGHT":
                self.collector_cmd_q.put({"cmd": "set_intensive", "enabled": bool(enabled)})

            # Al volver a INTENSIVA, restaurar la cadencia base para evitar
            # arrastrar backoffs históricos y recuperar velocidad real.
            if bool(enabled):
                self.poll_seconds = float(self.base_poll_seconds)
                try:
                    self.collector.set_poll_seconds(self.poll_seconds)
                except Exception:
                    pass
                try:
                    self.engine.set_current_poll_seconds(self.poll_seconds)
                except Exception:
                    pass
            mode_txt = "INTENSIVA" if bool(enabled) else "SUEÑO"
            self.engine_out_q.put(info(EventType.HEARTBEAT, f"Supervisión {mode_txt} solicitada por UI"))
        except Exception as e:
            self.engine_out_q.put(info(EventType.EXCEPTION, f"No se pudo cambiar modo intensivo: {e}"))

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
