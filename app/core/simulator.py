# app/core/simulator.py
"""
Simulador de respuestas del portal para probar UX/UI sin Playwright.

Devuelve un "estado normalizado" para que el resto del sistema trabaje siempre igual.
"""

from __future__ import annotations

import copy
import random
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Oferta:
    proveedor: str
    mejor_oferta_label: str  # "Mejor Oferta Vigente:" | "Oferta Superada:"
    monto: float
    hora: str
    monto_a_mostrar: str


@dataclass
class BuscarOfertasState:
    id_renglon: str

    ofertas: list[Oferta]

    presupuesto_txt: str
    oferta_min_txt: str
    mensaje: str

    presupuesto_val: Optional[float]
    oferta_min_val: Optional[float]

    http_status: int = 200
    finalizada: bool = False


def _money_txt(value: float) -> str:
    """
    Formato estilo portal: "$ 20.115.680,0000" (miles '.' y decimal ',')
    """
    s = f"{value:,.4f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"$ {s}"


def _now_hhmmss() -> str:
    return datetime.now().strftime("%H:%M:%S")


def build_initial_state(id_renglon: str) -> BuscarOfertasState:
    """
    Estado inicial base por renglón. La lógica final se ajusta en Simulator.
    """
    best_val = 20_000_000.0
    presupuesto_val = best_val * 1.08
    oferta_min_val = round(best_val * 0.99, 4)  # 👈 oferta a superar = 1% menos que best

    ofertas = [
        Oferta(
            proveedor="Prov. 30718165",
            mejor_oferta_label="Mejor Oferta Vigente:",
            monto=best_val,
            hora=_now_hhmmss(),
            monto_a_mostrar=_money_txt(best_val),
        ),
        Oferta(
            proveedor="Prov. 91764",
            mejor_oferta_label="Oferta Superada:",
            monto=best_val * 1.01,
            hora=_now_hhmmss(),
            monto_a_mostrar=_money_txt(best_val * 1.01),
        ),
    ]

    return BuscarOfertasState(
        id_renglon=str(id_renglon),
        ofertas=ofertas,
        presupuesto_txt=_money_txt(presupuesto_val),
        oferta_min_txt=_money_txt(oferta_min_val),
        mensaje="Subasta en curso",
        presupuesto_val=float(presupuesto_val),
        oferta_min_val=float(oferta_min_val),
        http_status=200,
        finalizada=False,
    )


class Simulator:
    """
    Simula una subasta con múltiples renglones.

    Reglas clave pedidas:
    - Sólo varía la mejor oferta vigente.
    - La oferta a superar es SIEMPRE 1% menos que la mejor oferta vigente.
    - La mejor oferta vigente baja 1% por minuto.
    """

    def __init__(self, *, id_cot: str, renglones: list[tuple[str, str]]):
        self.id_cot = str(id_cot)
        self.renglones = [(str(rid), str(desc)) for rid, desc in (renglones or [])]

        self._rng = random.Random(12345)  # determinístico/repetible
        self._states: dict[str, BuscarOfertasState] = {}
        self._meta: dict[str, dict] = {}

        now = time.monotonic()

        for rid, _desc in self.renglones:
            st = build_initial_state(rid)

            # inventamos bases determinísticas por renglón
            base_best = 18_000_000.0 + (int(rid) % 7) * 1_250_000.0  # varía por rid
            presupuesto_val = base_best * 1.08

            st.ofertas[0].monto = base_best
            st.ofertas[0].monto_a_mostrar = _money_txt(base_best)
            st.ofertas[0].hora = _now_hhmmss()
            st.ofertas[0].mejor_oferta_label = "Mejor Oferta Vigente:"

            # segunda oferta solo como histórico
            st.ofertas[1].monto = base_best * 1.01
            st.ofertas[1].monto_a_mostrar = _money_txt(base_best * 1.01)
            st.ofertas[1].hora = _now_hhmmss()
            st.ofertas[1].mejor_oferta_label = "Oferta Superada:"

            st.presupuesto_val = float(presupuesto_val)
            st.presupuesto_txt = _money_txt(float(presupuesto_val))

            # oferta_min siempre 1% menos del best
            oferta_min_val = round(base_best * 0.99, 4)
            st.oferta_min_val = float(oferta_min_val)
            st.oferta_min_txt = _money_txt(float(oferta_min_val))

            self._states[rid] = st
            self._meta[rid] = {
                "last_drop_at": now,
                "best_monto": float(base_best),
            }

        # knobs (podés ajustar)
        self.auto_drop_seconds = 60.0
        self.auto_drop_pct = 0.01  # 1% por minuto

        # si querés conservar algunos eventos “reales”, dejalo en 0
        self.prob_http_500 = 0.0
        self.prob_end = 0.0

    def tick(self) -> list[BuscarOfertasState]:
        out: list[BuscarOfertasState] = []
        for rid, _desc in self.renglones:
            cur = self._states[rid]
            nxt = self._tick_one(cur)
            self._states[rid] = nxt
            out.append(copy.deepcopy(nxt))
        return out

    def _apply_drop_1pct_per_minute(self, st: BuscarOfertasState) -> bool:
        meta = self._meta.get(st.id_renglon)
        if not meta or not st.ofertas:
            return False

        now = time.monotonic()
        last = float(meta.get("last_drop_at", now))
        elapsed = now - last
        if elapsed < self.auto_drop_seconds:
            return False

        steps = int(elapsed // self.auto_drop_seconds)
        if steps <= 0:
            return False

        best = float(meta.get("best_monto", st.ofertas[0].monto))
        factor = (1.0 - self.auto_drop_pct) ** steps
        new_best = max(1.0, best * factor)

        meta["best_monto"] = new_best
        meta["last_drop_at"] = last + steps * self.auto_drop_seconds

        # actualizar mejor oferta vigente
        st.ofertas[0].monto = float(new_best)
        st.ofertas[0].monto_a_mostrar = _money_txt(float(new_best))
        st.ofertas[0].hora = _now_hhmmss()
        st.ofertas[0].mejor_oferta_label = "Mejor Oferta Vigente:"

        # oferta mínima = 1% menos del best (pedido explícito)
        oferta_min_val = round(float(new_best) * 0.99, 4)
        st.oferta_min_val = float(oferta_min_val)
        st.oferta_min_txt = _money_txt(float(oferta_min_val))

        return True

    def _tick_one(self, st: BuscarOfertasState) -> BuscarOfertasState:
        s = copy.deepcopy(st)

        if s.finalizada:
            s.http_status = 200
            s.mensaje = "Subasta finalizada"
            return s

        # errores/finalización opcionales (por defecto desactivados)
        roll = self._rng.random()
        if self.prob_http_500 > 0 and roll < self.prob_http_500:
            s.http_status = 500
            s.mensaje = "Error interno del servidor"
            return s

        if self.prob_end > 0 and self._rng.random() < self.prob_end:
            s.finalizada = True
            s.http_status = 200
            s.mensaje = "Subasta finalizada"
            return s

        # ✅ ÚNICO cambio: bajar mejor oferta vigente 1%/min
        changed = self._apply_drop_1pct_per_minute(s)
        s.http_status = 200
        s.mensaje = "Sin cambios" if not changed else "Nueva mejor oferta (auto 1%/min)"
        return s
