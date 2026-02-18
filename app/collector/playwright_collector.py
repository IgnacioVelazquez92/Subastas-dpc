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
        self.intensive_mode = True
        self.relaxed_poll_seconds = max(10.0, self.poll_seconds * 10.0)

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
        # Si el thread murió inesperadamente, normalizar estado para permitir relanzar.
        if self._thread is not None and not self._thread.is_alive():
            self._running = False
            self._thread = None

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

    def stop_monitoring(self) -> None:
        """
        Comando: pausar solo el monitoreo (sin apagar todo el runtime).
        """
        self.cmd_q.put({"cmd": "stop_monitor"})

    def open_listado(self) -> None:
        """
        Comando: volver al listado (útil si el usuario se perdió).
        """
        self.cmd_q.put({"cmd": "open_listado"})

    def set_poll_seconds(self, seconds: float) -> None:
        self.cmd_q.put({"cmd": "set_poll", "seconds": float(seconds)})

    def set_intensive_monitoring(self, enabled: bool) -> None:
        self.cmd_q.put({"cmd": "set_intensive", "enabled": bool(enabled)})

    # -------------------------
    # Internals
    # -------------------------
    def _run_thread(self) -> None:
        try:
            asyncio.run(self._main())
        except Exception as e:
            self.emit(error(EventType.EXCEPTION, f"PlaywrightCollector terminó por excepción: {e}"))
        finally:
            self._running = False
            self._thread = None
            self.emit(info(EventType.STOP, "PlaywrightCollector thread finalizado."))

    async def _main(self) -> None:
        poll_seconds = self.poll_seconds

        async with async_playwright() as p:
            browser = None
            ctx = None
            page = None

            async def _create_browser_session():
                try:
                    _browser = await p.chromium.launch(headless=self.headless)
                    _ctx = await _browser.new_context(ignore_https_errors=True)
                    _page = await _ctx.new_page()

                    # Debug: detectar navegacion a URL tokenizada de subasta
                    _page.on(
                        "request",
                        lambda req: (
                            self.emit(debug(EventType.HEARTBEAT, f"(DBG) Request Subasta: {req.url}"))
                            if SUBASTA_URL_PART in req.url
                            else None
                        ),
                    )

                    # Abrimos el listado al arrancar
                    try:
                        await _page.goto(LISTADO_URL, wait_until="domcontentloaded")
                        self.emit(info(EventType.HEARTBEAT, f"Listado OK: {_page.url}"))
                    except Exception as e:
                        self.emit(error(EventType.EXCEPTION, f"No se pudo abrir listado: {e}"))

                    return _browser, _ctx, _page
                except Exception as e:
                    self.emit(error(EventType.EXCEPTION, f"No se pudo crear sesion Playwright: {e}"))
                    return None, None, None

            async def _ensure_page() -> bool:
                nonlocal browser, ctx, page
                if page is not None:
                    try:
                        if not page.is_closed():
                            return True
                    except Exception:
                        pass

                browser, ctx, page = await _create_browser_session()
                return page is not None

            browser, ctx, page = await _create_browser_session()

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
                    self.poll_seconds = poll_seconds
                    effective = self.poll_seconds if self.intensive_mode else self.relaxed_poll_seconds
                    mode_txt = "INTENSIVA" if self.intensive_mode else "SUEÑO"
                    self.emit(info(EventType.HEARTBEAT, f"poll_seconds actualizado: base={poll_seconds:.2f}s modo={mode_txt} efectivo={effective:.2f}s"))

                elif name == "set_intensive":
                    self.intensive_mode = bool(cmd.get("enabled", True))
                    effective = self.poll_seconds if self.intensive_mode else self.relaxed_poll_seconds
                    mode_txt = "INTENSIVA" if self.intensive_mode else "SUEÑO"
                    self.emit(info(EventType.HEARTBEAT, f"Modo monitoreo: {mode_txt} (poll efectivo={effective:.2f}s)"))

                elif name == "open_listado":
                    if not await _ensure_page():
                        continue
                    try:
                        await page.goto(LISTADO_URL, wait_until="domcontentloaded")
                        self.emit(info(EventType.HEARTBEAT, f"Listado OK: {page.url}"))
                    except Exception as e:
                        self.emit(error(EventType.EXCEPTION, f"Error abriendo listado: {e}"))

                elif name == "stop_monitor":
                    if monitor_task and not monitor_task.done():
                        monitor_task.cancel()
                        try:
                            await monitor_task
                        except asyncio.CancelledError:
                            pass
                        except Exception:
                            pass
                    self.emit(info(EventType.STOP, "Monitoreo pausado por usuario."))

                elif name == "capture_current":
                    # Cancelar monitoreo anterior si existia
                    if monitor_task and not monitor_task.done():
                        monitor_task.cancel()
                        try:
                            await monitor_task
                        except asyncio.CancelledError:
                            pass
                        except Exception:
                            pass

                    if not await _ensure_page():
                        self.emit(warn(EventType.EXCEPTION, "No se pudo relanzar navegador para capturar."))
                        continue

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

            try:
                if browser:
                    await browser.close()
            except Exception:
                pass
    @staticmethod
    def _normalize_desc(text: str) -> str:
        import unicodedata

        raw = " ".join((text or "").strip().lower().split())
        norm = unicodedata.normalize("NFKD", raw)
        return "".join(ch for ch in norm if not unicodedata.combining(ch))

    @classmethod
    def _normalize_renglon_key(cls, text: str) -> str:
        """
        Normaliza etiquetas de renglon para mejorar matching entre:
        - option del select (ej: "Renglón 1 - Insumos")
        - fila resumen de la grilla (ej: "RENGLON INSUMOS ...")
        """
        import re

        key = cls._normalize_desc(text)
        key = re.sub(r"^renglon\s*", "", key).strip()
        key = re.sub(r"^\d+\s*[-:.]?\s*", "", key).strip()
        return key

    @classmethod
    def _token_overlap_score(cls, a: str, b: str) -> int:
        import re

        ta = {t for t in re.findall(r"[a-z0-9]+", cls._normalize_renglon_key(a)) if len(t) >= 3}
        tb = {t for t in re.findall(r"[a-z0-9]+", cls._normalize_renglon_key(b)) if len(t) >= 3}
        if not ta or not tb:
            return 0
        return len(ta & tb)

    @classmethod
    def _match_resumen_row(
        cls,
        *,
        option_text: str,
        resumen_rows: list[dict],
        used_resumen_indices: set[int],
    ) -> dict | None:
        if not resumen_rows:
            return None

        option_norm = cls._normalize_desc(option_text)
        option_key = cls._normalize_renglon_key(option_text)

        # 1) Match exacto por descripción completa normalizada.
        for i, row in enumerate(resumen_rows):
            if i in used_resumen_indices:
                continue
            row_desc = row.get("descripcion", "")
            if cls._normalize_desc(row_desc) == option_norm:
                used_resumen_indices.add(i)
                return row

        # 2) Match por key de renglón sin prefijo.
        for i, row in enumerate(resumen_rows):
            if i in used_resumen_indices:
                continue
            row_desc = row.get("descripcion", "")
            row_key = cls._normalize_renglon_key(row_desc)
            if row_key and option_key and (row_key == option_key or row_key in option_key or option_key in row_key):
                used_resumen_indices.add(i)
                return row

        # 3) Match por superposición de tokens.
        best_idx = None
        best_score = 0
        for i, row in enumerate(resumen_rows):
            if i in used_resumen_indices:
                continue
            score = cls._token_overlap_score(option_text, row.get("descripcion", ""))
            if score > best_score:
                best_score = score
                best_idx = i

        if best_idx is not None and best_score > 0:
            used_resumen_indices.add(best_idx)
            return resumen_rows[best_idx]

        return None

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
            precio_ref_col3 = money_to_float(precio_ref_unit_txt)
            presupuesto = money_to_float(presupuesto_txt)

            # En fila resumen (RENGLON ...), la columna 3 no es unitario confiable.
            # Derivamos unitario consistente como TOTAL / CANTIDAD.
            precio_ref_unit = precio_ref_col3
            if is_resumen and presupuesto is not None and cantidad not in (None, 0):
                try:
                    precio_ref_unit = float(presupuesto) / float(cantidad)
                except Exception:
                    precio_ref_unit = None

            rows.append({
                "idx": idx,
                "descripcion": desc,
                "is_resumen": is_resumen,
                "cantidad": cantidad,
                # Unitario util para calculos internos:
                # - detalle: columna 3
                # - resumen: presupuesto / cantidad
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
        detalle_map: dict[str, list[dict]] = {}
        for row in detalle_rows:
            k = self._normalize_desc(row.get("descripcion", ""))
            detalle_map.setdefault(k, []).append(row)
        detalle_rows_no_resumen = [r for r in detalle_rows if not r.get("is_resumen")]
        detalle_rows_resumen = [r for r in detalle_rows if r.get("is_resumen")]
        used_resumen_indices: set[int] = set()
        used_detalle_indices_by_key: dict[str, int] = {}

        enriched = []
        for idx, opt in enumerate(options):
            key = self._normalize_desc(opt.get("text") or "")
            det = None

            # Match directo por descripcion; si hay duplicados, avanzar secuencialmente.
            rows_for_key = detalle_map.get(key) or []
            if rows_for_key:
                use_idx = used_detalle_indices_by_key.get(key, 0)
                if use_idx < len(rows_for_key):
                    det = rows_for_key[use_idx]
                    used_detalle_indices_by_key[key] = use_idx + 1
                else:
                    det = rows_for_key[-1]

            # Si no hubo match directo, intentar match contra filas resumen.
            if det is None:
                det = self._match_resumen_row(
                    option_text=opt.get("text") or "",
                    resumen_rows=detalle_rows_resumen,
                    used_resumen_indices=used_resumen_indices,
                )

            # Fallback por orden cuando cantidad de options y resúmenes coincide.
            if det is None and detalle_rows_resumen and len(options) == len(detalle_rows_resumen):
                if idx < len(detalle_rows_resumen) and idx not in used_resumen_indices:
                    det = detalle_rows_resumen[idx]
                    used_resumen_indices.add(idx)

            # Fallback por posición solo cuando no hay resumen y tamaños compatibles.
            if (
                not det
                and not detalle_rows_resumen
                and len(options) == len(detalle_rows_no_resumen)
                and idx < len(detalle_rows_no_resumen)
            ):
                det = detalle_rows_no_resumen[idx]

            # Si existe tabla resumen y esta option no pudo mapearse, se descarta.
            # Evita renglones "fantasma" cuando el portal expone options por item
            # pero la licitacion opera por un unico renglon resumen.
            if det is None and detalle_rows_resumen:
                continue

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

    @staticmethod
    def _chunked(items: list[dict], size: int) -> list[list[dict]]:
        """Parte una lista en lotes de tamaño fijo."""
        batch_size = max(1, int(size))
        return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]

    async def _fetch_buscar_ofertas_batch(self, page, payloads: list[dict]) -> list[dict]:
        """
        Ejecuta múltiples fetch en paralelo dentro de la página.
        Devuelve una lista alineada con payloads:
          [{status, json, error?}, ...]
        """
        if not payloads:
            return []
        return await page.evaluate(
            """async (batch) => {
                const endpoint = "SubastaVivoAccesoPublico.aspx/BuscarOfertas";
                const tasks = batch.map(async (p) => {
                    try {
                        const r = await fetch(endpoint, {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json; charset=UTF-8",
                                "X-Requested-With": "XMLHttpRequest"
                            },
                            body: JSON.stringify(p)
                        });
                        let j = null;
                        try { j = await r.json(); } catch (_e) { j = null; }
                        return { status: r.status, json: j };
                    } catch (e) {
                        return { status: 0, json: null, error: String(e || "fetch_error") };
                    }
                });
                return await Promise.all(tasks);
            }""",
            payloads,
        )

    async def _monitor_loop(self, page, poll_seconds: float) -> None:
        """
        Loop de monitoreo:
        - rota renglones capturados
        - por cada renglón hace POST BuscarOfertas desde la página
        - parsea el campo "d" (cuando tengamos parser real) y emite UPDATE

        Nota operativa:
        - poll_seconds se aplica ENTRE ciclos completos.
          Evita que el refresco por renglón crezca linealmente con la cantidad de renglones.
        """
        id_cot = self.current.get("id_cot")
        margen = self.current.get("margen") or ""
        renglones = self.current.get("renglones") or []

        if not id_cot or not renglones:
            self.emit(error(EventType.EXCEPTION, "Monitor no puede iniciar: faltan datos capturados."))
            return

        last_sig: dict[str, str] = {}
        tick = 0
        # Para lotes grandes (ej. 60 renglones) evitamos rondas secuenciales.
        # Se consulta en paralelo dentro del navegador en tandas grandes.
        batch_size = max(10, min(80, len(renglones)))

        self.emit(info(EventType.HEARTBEAT, f"Monitoreo activo: id_cot={id_cot} poll_base={self.poll_seconds:.2f}s"))

        while not self._stop_flag:
            cycle_started = time.monotonic()
            try:
                if page.is_closed():
                    self.emit(warn(EventType.STOP, "Navegador/pestana cerrada. Monitoreo pausado."))
                    return
            except Exception:
                self.emit(warn(EventType.STOP, "No se pudo validar estado de pagina. Monitoreo pausado."))
                return

            tick += 1

            if tick % 10 == 1:
                self.emit(info(EventType.HEARTBEAT, f"Heartbeat monitor tick={tick} renglones={len(renglones)}"))

            total_batches = 0
            total_updates = 0
            for chunk in self._chunked(renglones, batch_size):
                if self._stop_flag:
                    break
                total_batches += 1

                payloads = [
                    {
                        "id_Cotizacion": id_cot,
                        "id_Item_Renglon": opt.get("value"),
                        "Margen_Minimo": margen,
                    }
                    for opt in chunk
                ]

                try:
                    results = await self._fetch_buscar_ofertas_batch(page, payloads)
                except Exception as e:
                    msg = str(e).lower()
                    if "closed" in msg or "target page" in msg or "target closed" in msg:
                        self.emit(warn(EventType.STOP, "Pagina cerrada durante monitoreo. Reabri navegador y recaptura."))
                        return
                    self.emit(error(EventType.EXCEPTION, f"Fetch batch BuscarOfertas falló: {e}"))
                    continue

                for opt, res in zip(chunk, results):
                    rid = opt.get("value")
                    desc = opt.get("text") or ""
                    status = int((res or {}).get("status", 0))
                    body = ((res or {}).get("json") or {})

                    if status != 200:
                        if status == 0:
                            self.emit(
                                error(
                                    EventType.EXCEPTION,
                                    f"Fetch BuscarOfertas falló (renglon={rid}): {(res or {}).get('error', 'error desconocido')}",
                                    payload={"id_renglon": rid},
                                )
                            )
                        else:
                            self.emit(
                                warn(
                                    EventType.HTTP_ERROR,
                                    f"BuscarOfertas HTTP={status} (renglon={rid})",
                                    payload={"id_cot": id_cot, "id_renglon": rid, "desc": desc, "http_status": status},
                                )
                            )
                        continue

                    d = body.get("d", "") or ""
                    parsed = self._parse_d_field(d)

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
                    total_updates += 1

                    if "finalizada" in mensaje.lower():
                        self.emit(info(EventType.END, f"Subasta finalizada detectada (renglon={rid})", payload={"id_cot": id_cot, "id_renglon": rid, "desc": desc}))
                        return

            elapsed = time.monotonic() - cycle_started
            effective_poll = self.poll_seconds if self.intensive_mode else self.relaxed_poll_seconds
            sleep_for = max(0.0, float(effective_poll) - elapsed)
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
            cycle_total = elapsed + sleep_for

            self.emit(
                info(
                    EventType.HEARTBEAT,
                    (
                        f"[METRICA] ciclo={tick} renglones={len(renglones)} "
                        f"updates={total_updates} batches={total_batches} "
                        f"intervalo_real_por_renglon={cycle_total:.2f}s "
                        f"(modo={'INTENSIVA' if self.intensive_mode else 'SUEÑO'} "
                        f"poll_efectivo={effective_poll:.2f}s)"
                    ),
                )
            )

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

