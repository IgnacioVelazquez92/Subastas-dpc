# app/collector/http_monitor.py
"""
HttpMonitor — Monitor HTTP directo de alta velocidad.

Reemplaza el loop de monitoreo de PlaywrightCollector en producción:
en lugar de hacer los requests VIA Chromium (page.evaluate → fetch),
los hace directamente con httpx reutilizando las cookies de sesión
que Playwright ya capturó.

Ventaja de rendimiento real:
  - Playwright (via Chromium):  3–20s por ciclo de 20 renglones
  - HttpMonitor (httpx async):  0.2–2s por ciclo de 20 renglones

Integración con el sistema existente:
- NO modifica Engine, DB, UI ni eventos.
- Emite exactamente los mismos Event (UPDATE, HTTP_ERROR, HEARTBEAT, END, STOP)
  con los mismos payloads que _monitor_loop de PlaywrightCollector.
- PlaywrightCollector sigue siendo responsable del browse + capture.
  HttpMonitor solo toma el relevo del loop de polling.

Modos de operación (idénticos al sistema actual):
- INTENSIVA: todas las peticiones por ciclo en paralelo (asyncio.Semaphore).
- SUEÑO:     rotación de un renglón por ciclo (cursor).

Re-autenticación:
- Si recibe N_AUTH_FAILURES_MAX respuestas 401/403/0 consecutivas,
  emite WARN(EXCEPTION) con mensaje "sesión expirada" y se detiene.
  PlaywrightCollector puede reconectar automáticamente (recapture).

Uso típico (desde PlaywrightCollector):
    monitor = HttpMonitor(out_q=self.out_q, poll_seconds=self.poll_seconds)
    self._http_monitor = monitor
    task = asyncio.create_task(monitor.run(
        id_cot=..., margen=..., renglones=...,
        cookies=..., referer=...
    ))
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from queue import Queue
from typing import TYPE_CHECKING

import httpx

from app.core.events import EventType, info, warn, error, Event
from app.utils.money import money_to_float

# --------------------------------
# Configuración de endpoints
# --------------------------------
BASE_DOMAIN = "webecommerce.cba.gov.ar"
BASE_URL = f"https://{BASE_DOMAIN}/VistaPublica"
ENDPOINT_BUSCAR_OFERTAS = f"{BASE_URL}/SubastaVivoAccesoPublico.aspx/BuscarOfertas"

# Cantidad de fallos de auth consecutivos antes de declarar sesión expirada
N_AUTH_FAILURES_MAX = 5


class HttpMonitor:
    """
    Monitor de polling HTTP sin Chromium.

    Constructor:
        out_q                — cola de salida (misma que usa PlaywrightCollector)
        poll_seconds         — intervalo base entre ciclos (default 1.0)
        intensive_mode       — True=INTENSIVA, False=SUEÑO (default True)
        concurrent_requests  — semáforo de concurrencia en INTENSIVA (default 5, max 30)
        request_timeout_s    — timeout HTTP por request en INTENSIVA (default 2.5)
        relaxed_timeout_s    — timeout HTTP por request en SUEÑO (default 5.0)
        relaxed_poll_seconds — intervalo entre ciclos en SUEÑO (default max(1,poll_seconds))
        console_perf_logs    — imprimir métricas en consola (default True)
    """

    def __init__(
        self,
        *,
        out_q: Queue,
        poll_seconds: float = 1.0,
        intensive_mode: bool = True,
        concurrent_requests: int = 5,
        request_timeout_s: float = 2.5,
        relaxed_timeout_s: float = 5.0,
        relaxed_poll_seconds: float | None = None,
        console_perf_logs: bool = True,
    ):
        self.out_q = out_q
        self.poll_seconds = max(0.2, float(poll_seconds))
        self.intensive_mode = bool(intensive_mode)
        self.concurrent_requests = max(1, min(30, int(concurrent_requests)))
        self.request_timeout_s = max(0.5, float(request_timeout_s))
        self.relaxed_timeout_s = max(1.0, float(relaxed_timeout_s))
        self.relaxed_poll_seconds = float(relaxed_poll_seconds) if relaxed_poll_seconds is not None else max(1.0, self.poll_seconds)
        self.console_perf_logs = bool(console_perf_logs)

        self._stop_flag = False
        self._consecutive_auth_failures = 0

    # --------------------------------
    # Control externo
    # --------------------------------
    def stop(self) -> None:
        """Señal de parada (thread-safe, se comprueba en el loop async)."""
        self._stop_flag = True

    def set_intensive(self, enabled: bool) -> None:
        self.intensive_mode = bool(enabled)

    def set_poll_seconds(self, seconds: float) -> None:
        self.poll_seconds = max(0.2, float(seconds))
        self.relaxed_poll_seconds = max(1.0, self.poll_seconds)

    def set_concurrent_requests(self, n: int) -> None:
        self.concurrent_requests = max(1, min(30, int(n)))

    def emit(self, event: Event) -> None:
        self.out_q.put(event)

    # --------------------------------
    # Loop principal
    # --------------------------------
    async def run(
        self,
        *,
        id_cot: str,
        margen: str,
        renglones: list[dict],
        cookies: dict[str, str],
        referer: str,
    ) -> None:
        """
        Loop de monitoreo directo con httpx.

        Argumentos:
            id_cot     — ID de cotización del portal
            margen     — margen mínimo (str, puede ser "")
            renglones  — lista de dicts con "value" (id_renglon) y "text" (desc)
            cookies    — dict {name: value} extraído de la sesión de Playwright
            referer    — URL de la subasta (para el header Referer)
        """
        if not id_cot or not renglones:
            self.emit(error(EventType.EXCEPTION,
                "[HttpMonitor] No puede iniciar: faltan id_cot o renglones."))
            return

        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "es-AR,es;q=0.9",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Referer": referer,
            "Origin": f"https://{BASE_DOMAIN}",
        }

        tick = 0
        sleep_cursor = 0
        last_sig: dict[str, str] = {}

        mode_txt = "INTENSIVA" if self.intensive_mode else "SUEÑO"
        self.emit(info(EventType.HEARTBEAT,
            f"[HttpMonitor] Iniciado: id_cot={id_cot} renglones={len(renglones)} "
            f"modo={mode_txt} poll={self.poll_seconds:.1f}s "
            f"concurrencia={self.concurrent_requests}"))

        # httpx AsyncClient con connection pool persistente
        async with httpx.AsyncClient(
            headers=headers,
            cookies=cookies,
            timeout=httpx.Timeout(
                connect=3.0,
                read=self.request_timeout_s,
                write=3.0,
                pool=3.0,
            ),
            limits=httpx.Limits(
                max_connections=min(30, self.concurrent_requests + 5),
                max_keepalive_connections=self.concurrent_requests,
                keepalive_expiry=30.0,
            ),
            verify=False,   # el portal usa cert auto-firmado frecuentemente
            http2=True,     # HTTP/2 si el servidor lo soporta (reduce overhead)
        ) as client:

            while not self._stop_flag:
                cycle_start = time.monotonic()
                tick += 1

                if tick % 10 == 1:
                    self.emit(info(EventType.HEARTBEAT,
                        f"[HttpMonitor] tick={tick} renglones={len(renglones)} "
                        f"modo={'INTENSIVA' if self.intensive_mode else 'SUEÑO'}"))

                # --- Selección de renglones para este ciclo ---
                if self.intensive_mode:
                    cycle_renglones = list(renglones)
                    timeout_s = self.request_timeout_s
                else:
                    idx = sleep_cursor % len(renglones)
                    sleep_cursor += 1
                    cycle_renglones = [renglones[idx]]
                    timeout_s = self.relaxed_timeout_s

                # --- Peticiones en paralelo con semáforo ---
                semaphore = asyncio.Semaphore(self.concurrent_requests)
                total_updates = 0
                total_errors = 0
                total_timeouts = 0

                async def fetch_one(opt: dict) -> tuple[dict, int, dict | None, str | None]:
                    """Realiza un POST BuscarOfertas y devuelve (opt, status, body, error_kind)."""
                    async with semaphore:
                        payload = {
                            "id_Cotizacion": id_cot,
                            "id_Item_Renglon": opt.get("value"),
                            "Margen_Minimo": margen,
                        }
                        try:
                            r = await client.post(
                                ENDPOINT_BUSCAR_OFERTAS,
                                json=payload,
                                timeout=httpx.Timeout(
                                    connect=3.0,
                                    read=timeout_s,
                                    write=3.0,
                                    pool=3.0,
                                ),
                            )
                            if r.status_code == 200:
                                try:
                                    body = r.json()
                                except Exception:
                                    body = {}
                                return opt, 200, body, None
                            else:
                                return opt, r.status_code, None, "http_error"
                        except httpx.TimeoutException:
                            return opt, 0, None, "timeout"
                        except httpx.NetworkError as e:
                            return opt, 0, None, f"network:{e}"
                        except Exception as e:
                            return opt, 0, None, f"exception:{e}"

                tasks = [fetch_one(opt) for opt in cycle_renglones]
                results = await asyncio.gather(*tasks, return_exceptions=False)

                # --- Procesar resultados ---
                for opt, status, body, error_kind in results:
                    if self._stop_flag:
                        break

                    rid = opt.get("value")
                    desc = opt.get("text") or ""

                    # Detectar fallos de autenticación
                    if status in (401, 403):
                        self._consecutive_auth_failures += 1
                        if self._consecutive_auth_failures >= N_AUTH_FAILURES_MAX:
                            self.emit(warn(EventType.EXCEPTION,
                                f"[HttpMonitor] Sesión expirada ({N_AUTH_FAILURES_MAX} fallos auth). "
                                f"Reconectar con Playwright."))
                            self._stop_flag = True
                            return
                        self.emit(warn(EventType.HTTP_ERROR,
                            f"[HttpMonitor] Auth error {status} renglon={rid}",
                            payload={"id_cot": id_cot, "id_renglon": rid, "desc": desc,
                                    "http_status": status, "error_kind": "auth_error"}))
                        total_errors += 1
                        continue

                    if status != 200:
                        is_timeout = (error_kind == "timeout")
                        if is_timeout:
                            total_timeouts += 1
                        total_errors += 1
                        self.emit(warn(EventType.HTTP_ERROR,
                            f"[HttpMonitor] Error HTTP={status} renglon={rid} ({error_kind})",
                            payload={
                                "id_cot": id_cot, "id_renglon": rid, "desc": desc,
                                "http_status": status,
                                "error_kind": "timeout" if is_timeout else (error_kind or "network"),
                                "error_message": error_kind or "",
                            }))
                        continue

                    # Respuesta OK — resetear contador de auth failures
                    self._consecutive_auth_failures = 0

                    d = (body or {}).get("d", "") or ""
                    parsed = self._parse_d_field(d)

                    mejor_txt = parsed.get("mejor_oferta_txt", "")
                    mejor_val = parsed.get("mejor_oferta_val")
                    oferta_min_txt = parsed.get("oferta_min_txt", "")
                    oferta_min_val = parsed.get("oferta_min_val")
                    presupuesto_txt = parsed.get("presupuesto_txt", "")
                    presupuesto_val = parsed.get("presupuesto_val")
                    mensaje = parsed.get("mensaje", "") or ""
                    hora_ultima_oferta = parsed.get("hora_ultima_oferta")
                    ofertas = parsed.get("ofertas") or []

                    mejor_id_proveedor = None
                    if ofertas:
                        raw = ofertas[0].get("id_proveedor")
                        if raw is not None:
                            mejor_id_proveedor = str(raw)

                    sig = f"{mejor_txt}|{oferta_min_txt}|{mensaje}"
                    changed = last_sig.get(rid) != sig
                    last_sig[rid] = sig

                    if changed:
                        self.emit(info(EventType.HEARTBEAT,
                            f"[HttpMonitor] CAMBIO renglon={rid} mejor={mejor_txt} min={oferta_min_txt}",
                            payload={"id_renglon": rid}))

                    # Emitir UPDATE con el MISMO payload que _monitor_loop de PlaywrightCollector
                    self.emit(info(EventType.UPDATE, f"Update renglón {rid}", payload={
                        "id_cot": id_cot,
                        "id_renglon": rid,
                        "desc": desc,
                        "mejor_oferta_txt": mejor_txt,
                        "mejor_oferta_val": mejor_val,
                        "oferta_min_txt": oferta_min_txt,
                        "oferta_min_val": oferta_min_val,
                        "presupuesto_txt": presupuesto_txt,
                        "presupuesto_val": presupuesto_val,
                        "mensaje": mensaje,
                        "hora_ultima_oferta": hora_ultima_oferta,
                        "mejor_id_proveedor": mejor_id_proveedor,
                        "ofertas": ofertas,
                        "changed": changed,
                        "http_status": 200,
                    }))
                    total_updates += 1

                    if "finalizada" in mensaje.lower():
                        self.emit(info(EventType.END,
                            f"[HttpMonitor] Subasta finalizada (renglon={rid})",
                            payload={"id_cot": id_cot, "id_renglon": rid, "desc": desc}))
                        return

                # --- Dormir el tiempo restante del ciclo ---
                elapsed = time.monotonic() - cycle_start
                effective_poll = self.poll_seconds if self.intensive_mode else self.relaxed_poll_seconds
                sleep_for = max(0.0, effective_poll - elapsed)
                cycle_total = elapsed + sleep_for

                # Métricas de ciclo (mismo formato que PlaywrightCollector)
                self.emit(info(EventType.HEARTBEAT, (
                    f"[HttpMonitor][METRICA] ciclo={tick} renglones={len(cycle_renglones)} "
                    f"updates={total_updates} errores={total_errors} timeouts={total_timeouts} "
                    f"dur_real={elapsed:.3f}s ciclo_total={cycle_total:.2f}s "
                    f"(modo={'INTENSIVA' if self.intensive_mode else 'SUEÑO'} "
                    f"poll={effective_poll:.2f}s concurrencia={self.concurrent_requests})"
                )))

                if self.console_perf_logs:
                    ts = datetime.now().strftime("%H:%M:%S")
                    mode_log = "INTENSIVA" if self.intensive_mode else "SUEÑO"
                    print(
                        f"[{ts}] [HttpMonitor][PERF] ciclo={tick} modo={mode_log} "
                        f"dur={elapsed:.3f}s ciclo={cycle_total:.2f}s "
                        f"updates={total_updates}/{len(cycle_renglones)} "
                        f"err={total_errors} timeouts={total_timeouts} "
                        f"conc={self.concurrent_requests} poll={effective_poll:.2f}s",
                        flush=True,
                    )

                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)

        self.emit(info(EventType.STOP, "[HttpMonitor] Monitoreo detenido."))

    # --------------------------------
    # Parser del campo d
    # (misma lógica que PlaywrightCollector._parse_d_field)
    # --------------------------------
    @staticmethod
    def _parse_d_field(d: str) -> dict:
        """
        El portal devuelve:
          d = "<json_ofertas>@@<presupuesto>@@<oferta_min>@@<mensaje>"

        Ejemplo real:
          "[{...}]@@$ 21.696.480,0000@@$ 20.015.101,6000@@"
        """
        parts = (d or "").split("@@")
        grid = parts[0] if len(parts) > 0 else ""
        presupuesto_txt = parts[1] if len(parts) > 1 else ""
        oferta_min_txt = parts[2] if len(parts) > 2 else ""
        mensaje = parts[3] if len(parts) > 3 else ""

        ofertas: list[dict] = []
        if grid and grid != "null":
            try:
                ofertas = json.loads(grid)
            except Exception:
                ofertas = []

        mejor_txt = ""
        mejor_val = None
        hora_ultima_oferta = None
        if ofertas:
            mejor_txt = ofertas[0].get("monto_a_mostrar") or ""
            mejor_val = money_to_float(mejor_txt)
            hora_ultima_oferta = ofertas[0].get("hora") or None

        return {
            "ofertas": ofertas,
            "presupuesto_txt": presupuesto_txt,
            "presupuesto_val": money_to_float(presupuesto_txt),
            "oferta_min_txt": oferta_min_txt,
            "oferta_min_val": money_to_float(oferta_min_txt),
            "mejor_oferta_txt": mejor_txt,
            "mejor_oferta_val": mejor_val,
            "hora_ultima_oferta": hora_ultima_oferta,
            "mensaje": mensaje,
        }
