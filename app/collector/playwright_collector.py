# app/collector/playwright_collector.py
"""
Collector real con Playwright (PlaywrightCollector).

Este es el "corazón" del proyecto: extraer información del portal y emitir eventos.

Diseño:
- Corre en un thread dedicado y dentro usa asyncio (async_playwright).
- Usa un navegador REAL (Chromium) y ejecuta fetch DESDE la página para
  reutilizar cookies/sesión/tokens ASP.NET del mismo contexto del DOM.
- Modo de captura:
  - El usuario navega manualmente a la subasta en el navegador visible.
  - La UI envía el comando capture_current().
  - El collector captura:
    - id_cot (desde HTML)
    - margen mínimo
    - listado de renglones (#ddlItemRenglon options)
  - Comienza el monitoreo (loop) rotando renglones.

Eventos emitidos (app/core/events.py):
- START / STOP
- SNAPSHOT (cuando captura subasta+renglones)
- UPDATE (por renglón)
- HTTP_ERROR / EXCEPTION
- HEARTBEAT
- END (cuando detecta subasta finalizada)

Nota:
- Este collector NO escribe en SQLite.
- Solo emite eventos y el "core" (luego) persiste y decide alertas/seguridad.
"""

from __future__ import annotations

import asyncio
import time
from threading import Thread
from queue import Queue, Empty

from playwright.async_api import async_playwright, TimeoutError as PWTimeoutError

from app.collector.base import BaseCollector
from app.core.events import EventType, info, warn, error, debug, Event
from app.utils.money import money_to_float


# -------------------------
# Selectores / constantes
# -------------------------

LISTADO_URL = "https://webecommerce.cba.gov.ar/VistaPublica/OportunidadProveedores.aspx"

# La subasta pública suele estar en esta ruta con query tokenizada
SUBASTA_URL_PART = "SubastaVivoAccesoPublico.aspx"

# Selectores esperados en la página de subasta
SEL_RENGLON_SELECT = "#ddlItemRenglon"
SEL_MARGEN_MINIMO = "#txtMargenMinimo"


class PlaywrightCollector(BaseCollector):
    """
    Collector Playwright real.

    Arquitectura de colas:
    - cmd_q: comandos (UI/Core -> collector)
    - out_q: eventos (collector -> sistema)
    """

    def __init__(
        self,
        *,
        cmd_q: Queue,
        out_q: Queue,
        headless: bool = False,
        poll_seconds: float = 1.0,
    ):
        super().__init__(out_q=out_q)
        self.cmd_q = cmd_q

        self.headless = bool(headless)
        self.poll_seconds = max(0.2, float(poll_seconds))

        self._thread: Thread | None = None
        self._stop_flag = False

        # Estado de captura actual (una subasta por ahora)
        self.current = {
            "id_cot": None,
            "margen": None,
            "subasta_url": None,
            "renglones": None,  # list[dict(value,text)]
        }

    # -------------------------
    # Public API
    # -------------------------
    def start(self) -> None:
        if self._running:
            return

        self._stop_flag = False
        self._running = True
        self._thread = Thread(target=self._run_thread, daemon=True)
        self._thread.start()

        self.emit(info(EventType.START, f"PlaywrightCollector iniciado (headless={self.headless})"))

    def stop(self) -> None:
        if not self._running:
            return
        self._stop_flag = True
        self._running = False
        self.emit(info(EventType.STOP, "STOP solicitado al PlaywrightCollector"))

    def capture_current(self) -> None:
        """
        Comando: capturar la subasta actual (usuario ya navego a la subasta en el browser).
        """
        self.cmd_q.put({"cmd": "capture_current"})

    def open_listado(self) -> None:
        """
        Comando: volver al listado (útil si el usuario se perdió).
        """
        self.cmd_q.put({"cmd": "open_listado"})

    def set_poll_seconds(self, seconds: float) -> None:
        self.cmd_q.put({"cmd": "set_poll", "seconds": float(seconds)})

    # -------------------------
    # Internals
    # -------------------------
    def _run_thread(self) -> None:
        asyncio.run(self._main())

    async def _main(self) -> None:
        poll_seconds = self.poll_seconds

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            ctx = await browser.new_context(ignore_https_errors=True)
            page = await ctx.new_page()

            # Debug: detectar navegación a URL tokenizada de subasta
            page.on(
                "request",
                lambda req: (
                    self.emit(debug(EventType.HEARTBEAT, f"(DBG) Request Subasta: {req.url}"))
                    if SUBASTA_URL_PART in req.url
                    else None
                ),
            )

            # Abrimos el listado al arrancar
            try:
                await page.goto(LISTADO_URL, wait_until="domcontentloaded")
                self.emit(info(EventType.HEARTBEAT, f"Listado OK: {page.url}"))
            except Exception as e:
                self.emit(error(EventType.EXCEPTION, f"No se pudo abrir listado: {e}"))

            monitor_task: asyncio.Task | None = None
            tick = 0

            while not self._stop_flag:
                tick += 1

                # Procesar comandos sin bloquear
                try:
                    cmd = self.cmd_q.get_nowait()
                except Empty:
                    # Heartbeat general cada ~10s
                    if tick % 100 == 1:
                        self.emit(info(EventType.HEARTBEAT, "Collector vivo (sin comandos)"))
                    await asyncio.sleep(0.1)
                    continue

                name = cmd.get("cmd")
                if not name:
                    continue

                if name == "set_poll":
                    poll_seconds = max(0.2, float(cmd.get("seconds", poll_seconds)))
                    self.emit(info(EventType.HEARTBEAT, f"poll_seconds actualizado: {poll_seconds:.2f}s"))

                elif name == "open_listado":
                    try:
                        await page.goto(LISTADO_URL, wait_until="domcontentloaded")
                        self.emit(info(EventType.HEARTBEAT, f"Listado OK: {page.url}"))
                    except Exception as e:
                        self.emit(error(EventType.EXCEPTION, f"Error abriendo listado: {e}"))

                elif name == "capture_current":
                    # Cancelar monitoreo anterior si existía
                    if monitor_task and not monitor_task.done():
                        monitor_task.cancel()
                        try:
                            await monitor_task
                        except asyncio.CancelledError:
                            pass
                        except Exception:
                            pass

                    ok = await self._capture_current(page)
                    if ok:
                        # Emitimos snapshot de renglones capturados
                        self.emit(
                            info(
                                EventType.SNAPSHOT,
                                "Subasta capturada (snapshot).",
                                payload={
                                    "id_cot": self.current["id_cot"],
                                    "margen": self.current["margen"],
                                    "subasta_url": self.current["subasta_url"],
                                    "renglones": self.current["renglones"],
                                },
                            )
                        )

                        # Arranca monitoreo
                        monitor_task = asyncio.create_task(self._monitor_loop(page, poll_seconds))
                        self.emit(info(EventType.HEARTBEAT, "Monitoreo iniciado (task creada)."))
                    else:
                        self.emit(warn(EventType.EXCEPTION, "No se pudo capturar subasta actual."))

                else:
                    self.emit(warn(EventType.EXCEPTION, f"CMD desconocido: {name}"))

            # Shutdown limpio
            try:
                if monitor_task and not monitor_task.done():
                    monitor_task.cancel()
                    try:
                        await monitor_task
                    except asyncio.CancelledError:
                        pass
                    except Exception:
                        pass
            except Exception:
                pass

            await browser.close()
            self.emit(info(EventType.STOP, "PlaywrightCollector finalizado."))

    @staticmethod
    def _normalize_desc(text: str) -> str:
        import unicodedata

        raw = " ".join((text or "").strip().lower().split())
        norm = unicodedata.normalize("NFKD", raw)
        return "".join(ch for ch in norm if not unicodedata.combining(ch))

    async def _parse_detalle_table(self, page) -> list[dict]:
        rows = []
        try:
            data = await page.locator(
                "#gvDetalleCotizacion tr.Renglon, #gvDetalleCotizacion tr.RenglonAlternativo"
            ).evaluate_all(
                "rows => rows.map(r => Array.from(r.querySelectorAll('td')).map(td => (td.textContent||'').trim()))"
            )
        except Exception:
            return rows

        for idx, cells in enumerate(data):
            if len(cells) < 4:
                continue
            desc = cells[0]
            is_resumen = str(desc).strip().upper().startswith("RENGLON ")
            cantidad_txt = cells[1]
            precio_ref_unit_txt = cells[2]
            presupuesto_txt = cells[3]
            cantidad = None
            try:
                cantidad = float(str(cantidad_txt).replace('.', '').replace(',', '.'))
            except Exception:
                cantidad = None

            from app.utils.money import money_to_float
            precio_ref_unit = money_to_float(precio_ref_unit_txt)
            presupuesto = money_to_float(presupuesto_txt)

            rows.append({
                "idx": idx,
                "descripcion": desc,
                "is_resumen": is_resumen,
                "cantidad": cantidad,
                # Precio de referencia unitario (columna 3)
                "precio_ref_unitario": precio_ref_unit,
                # Precio de referencia total / Presupuesto Oficial (columna 4)
                "precio_referencia": presupuesto,
                "presupuesto": presupuesto,
            })

        return rows

    async def _capture_current(self, page) -> bool:
        """
        Captura la subasta abierta actualmente:
        - espera URL de subasta
        - espera select de renglones
        - lee margen mínimo
        - extrae id_cot del HTML (por regex simple)
        """
        # Esperar hasta 60s que el usuario esté en la subasta
        self.emit(info(EventType.HEARTBEAT, "Esperando que el usuario abra una subasta… (max 60s)"))

        for _ in range(600):
            if self._stop_flag:
                return False
            if SUBASTA_URL_PART in (page.url or ""):
                break
            await asyncio.sleep(0.1)

        if SUBASTA_URL_PART not in (page.url or ""):
            self.emit(warn(EventType.EXCEPTION, "No estás en una subasta (URL no coincide)."))
            return False

        # Esperar carga de renglones
        try:
            await page.wait_for_selector(SEL_RENGLON_SELECT, timeout=30_000)
            await page.wait_for_function(
                "document.querySelectorAll('#ddlItemRenglon option').length > 0",
                timeout=30_000,
            )
        except PWTimeoutError:
            self.emit(error(EventType.EXCEPTION, "No cargaron los renglones (#ddlItemRenglon)."))
            return False

        # Leer margen mínimo
        margen = None
        try:
            margen = await page.locator(SEL_MARGEN_MINIMO).input_value()
        except Exception:
            margen = None

        # Leer options del select
        options = await page.locator("#ddlItemRenglon option").evaluate_all(
            "opts => opts.map(o => ({value:o.value, text:(o.textContent||'').trim()}))"
        )

        detalle_rows = await self._parse_detalle_table(page)
        detalle_map = {self._normalize_desc(r.get("descripcion", "")): r for r in detalle_rows}
        detalle_rows_no_resumen = [r for r in detalle_rows if not r.get("is_resumen")]
        detalle_row_resumen = next((r for r in detalle_rows if r.get("is_resumen")), None)

        enriched = []
        for idx, opt in enumerate(options):
            key = self._normalize_desc(opt.get("text") or "")
            det = detalle_map.get(key)

            # Si el option corresponde al "renglon" total, priorizar fila resumen.
            if not det and key.startswith("renglon ") and detalle_row_resumen:
                det = detalle_row_resumen

            # Si hay un solo option y existe resumen, para este tipo de subasta
            # el dato correcto suele venir en la fila "RENGLON ...".
            if not det and len(options) == 1 and detalle_row_resumen:
                det = detalle_row_resumen

            # Fallback por posición solo cuando no hay resumen y tamaños compatibles.
            if (
                not det
                and not detalle_row_resumen
                and len(options) == len(detalle_rows_no_resumen)
                and idx < len(detalle_rows_no_resumen)
            ):
                det = detalle_rows_no_resumen[idx]

            det = det or {}
            enriched.append({
                **opt,
                "cantidad": det.get("cantidad"),
                "precio_referencia": det.get("precio_referencia"),
                "precio_ref_unitario": det.get("precio_ref_unitario"),
                "presupuesto": det.get("presupuesto"),
            })
        options = enriched

        # Extraer id_cot del HTML: buscamos un patrón robusto
        # Si mañana cambia, solo ajustamos esta función.
        html = await page.content()
        id_cot = self._extract_id_cotizacion_from_html(html)

        if not id_cot:
            self.emit(error(EventType.EXCEPTION, "No pude detectar id_cotizacion en el HTML."))
            return False

        self.current["id_cot"] = id_cot
        self.current["margen"] = margen or ""
        self.current["subasta_url"] = page.url
        self.current["renglones"] = options

        self.emit(
            info(
                EventType.HEARTBEAT,
                f"CAPTURE OK: id_cot={id_cot} margen={margen} renglones={len(options)}",
            )
        )
        return True

    @staticmethod
    def _extract_id_cotizacion_from_html(html: str) -> str | None:
        """
        Extrae id_Cotizacion desde el HTML.

        Patrón histórico visto:
          Cargar_Parametro("id_Cotizacion",'21941'
        """
        import re

        m = re.search(r'Cargar_Parametro\(\s*"id_Cotizacion"\s*,\s*\'(\d+)\'', html)
        return m.group(1) if m else None

    async def _monitor_loop(self, page, poll_seconds: float) -> None:
        """
        Loop de monitoreo:
        - rota renglones capturados
        - por cada renglón hace POST BuscarOfertas desde la página
        - parsea el campo "d" (cuando tengamos parser real) y emite UPDATE

        Nota operativa:
        - poll_seconds se aplica ENTRE requests.
          Con N renglones, el refresco por renglón es aproximadamente N * poll_seconds.
        """
        id_cot = self.current.get("id_cot")
        margen = self.current.get("margen") or ""
        renglones = self.current.get("renglones") or []

        if not id_cot or not renglones:
            self.emit(error(EventType.EXCEPTION, "Monitor no puede iniciar: faltan datos capturados."))
            return

        last_sig: dict[str, str] = {}
        tick = 0

        self.emit(info(EventType.HEARTBEAT, f"Monitoreo activo: id_cot={id_cot} poll={poll_seconds:.2f}s"))

        while not self._stop_flag:
            tick += 1

            if tick % 10 == 1:
                self.emit(info(EventType.HEARTBEAT, f"Heartbeat monitor tick={tick} renglones={len(renglones)}"))

            for opt in renglones:
                if self._stop_flag:
                    break

                rid = opt.get("value")
                desc = opt.get("text") or ""

                payload = {
                    "id_Cotizacion": id_cot,
                    "id_Item_Renglon": rid,
                    "Margen_Minimo": margen,
                }

                try:
                    res = await self._fetch_buscar_ofertas(page, payload)
                except Exception as e:
                    self.emit(
                        error(
                            EventType.EXCEPTION,
                            f"Fetch BuscarOfertas falló (renglon={rid}): {e}",
                            payload={"id_renglon": rid},
                        )
                    )
                    await asyncio.sleep(poll_seconds)
                    continue

                status = int(res.get("status", 0))
                body = (res.get("json") or {})

                if status != 200:
                    self.emit(
                        warn(
                            EventType.HTTP_ERROR,
                            f"BuscarOfertas HTTP={status} (renglon={rid})",
                            payload={"id_cot": id_cot, "id_renglon": rid, "desc": desc, "http_status": status},
                        )
                    )
                    await asyncio.sleep(poll_seconds)
                    continue

                d = body.get("d", "") or ""

                # Parser del campo "d"
                parsed = self._parse_d_field(d)

                # Mejor oferta: la primera del array suele ser la vigente
                mejor_txt = parsed.get("mejor_oferta_txt", "")
                mejor_val = parsed.get("mejor_oferta_val")

                oferta_min_txt = parsed.get("oferta_min_txt", "")
                oferta_min_val = parsed.get("oferta_min_val")

                presupuesto_txt = parsed.get("presupuesto_txt", "")
                presupuesto_val = parsed.get("presupuesto_val")

                mensaje = parsed.get("mensaje", "") or ""
                hora_ultima_oferta = parsed.get("hora_ultima_oferta")

                sig = f"{mejor_txt}|{oferta_min_txt}|{mensaje}"
                changed = last_sig.get(rid) != sig
                last_sig[rid] = sig

                if changed:
                    self.emit(
                        info(
                            EventType.HEARTBEAT,
                            f"CAMBIO renglon={rid} mejor={mejor_txt} min={oferta_min_txt}",
                            payload={"id_renglon": rid},
                        )
                    )

                self.emit(
                    info(
                        EventType.UPDATE,
                        f"Update renglón {rid}",
                        payload={
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
                            "changed": changed,
                            "http_status": 200,
                        },
                    )
                )

                # Detectar fin por mensaje (refinable)
                if "finalizada" in mensaje.lower():
                    self.emit(info(EventType.END, f"Subasta finalizada detectada (renglon={rid})", payload={"id_cot": id_cot, "id_renglon": rid, "desc": desc}))
                    return

                await asyncio.sleep(poll_seconds)

        self.emit(info(EventType.STOP, "Monitoreo detenido (stop_flag=True)."))

    async def _fetch_buscar_ofertas(self, page, payload: dict) -> dict:
        """
        Ejecuta fetch dentro de la página (como el navegador real).
        Devuelve:
          { status: <http status>, json: <json response> }
        """
        return await page.evaluate(
            """async (p) => {
                const r = await fetch("SubastaVivoAccesoPublico.aspx/BuscarOfertas", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json; charset=UTF-8",
                        "X-Requested-With": "XMLHttpRequest"
                    },
                    body: JSON.stringify(p)
                });
                const j = await r.json();
                return { status: r.status, json: j };
            }""",
            payload,
        )

    # -------------------------
    # Parser del campo d (alineado a tu ejemplo real)
    # -------------------------
    def _parse_d_field(self, d: str) -> dict:
        """
        El portal devuelve:
          d = "<json_ofertas>@@<presupuesto>@@<oferta_min>@@<mensaje>"

        Ej:
          "[{...},{...}]@@$ 21.696.480,0000@@$ 20.015.101,6000@@"

        Retornamos un dict normalizado para UI/DB.
        """
        import json

        parts = (d or "").split("@@")
        grid = parts[0] if len(parts) > 0 else ""
        presupuesto_txt = parts[1] if len(parts) > 1 else ""
        oferta_min_txt = parts[2] if len(parts) > 2 else ""
        mensaje = parts[3] if len(parts) > 3 else ""

        ofertas = []
        if grid and grid != "null":
            try:
                ofertas = json.loads(grid)
            except Exception:
                ofertas = []

        # Mejor oferta: por observación, ofertas[0] suele ser "Mejor Oferta Vigente"
        mejor_txt = ""
        mejor_val = None
        hora_ultima_oferta = None
        if ofertas:
            mejor_txt = ofertas[0].get("monto_a_mostrar") or ""
            # el portal también trae "monto" numérico a veces
            # pero confiamos más en monto_a_mostrar y lo parseamos
            mejor_val = money_to_float(mejor_txt)
            hora_ultima_oferta = ofertas[0].get("hora") or None

        presupuesto_val = money_to_float(presupuesto_txt)
        oferta_min_val = money_to_float(oferta_min_txt)

        return {
            "ofertas": ofertas,
            "presupuesto_txt": presupuesto_txt,
            "presupuesto_val": presupuesto_val,
            "oferta_min_txt": oferta_min_txt,
            "oferta_min_val": oferta_min_val,
            "mejor_oferta_txt": mejor_txt,
            "mejor_oferta_val": mejor_val,
            "hora_ultima_oferta": hora_ultima_oferta,
            "mensaje": mensaje,
        }
