"""Shocks del mercado de dinero: un cambio en M/P desplaza la LM; la IS no cambia.

Con D = h(1-c) + b·k (De Gregorio, cap. 19, ec. 19.20 y p. 518):
    dY/d(M/P) = 1 / (k + h(1-c)/b) = b/D     > 0
    di/d(M/P) = -(1/h)·[1 - k·dY/d(M/P)] = -(1-c)/D   < 0

Desplazamiento de la LM (sin ajuste del mercado de bienes):
    horizontal, a tasa constante:     ΔY = Δ(M/P)/k
    vertical, a producto constante:   Δi = -Δ(M/P)/h
"""

from __future__ import annotations

from dataclasses import dataclass

from islm.config import Ventana
from islm.model import (
    Equilibrio,
    Parametros,
    Recta,
    curva_is,
    curva_lm,
    equilibrio,
)
from islm.shocks import FilaComparacion, FueraDeRango, controlar_dominio, tabla_comparativa


@dataclass(frozen=True)
class MultiplicadorMonetario:
    producto: float   # dY/d(M/P)
    tasa: float       # di/d(M/P)


def multiplicador_monetario(p: Parametros) -> MultiplicadorMonetario:
    s = 1 - p.c
    D = p.h * s + p.b * p.k
    return MultiplicadorMonetario(producto=p.b / D, tasa=-s / D)


@dataclass(frozen=True)
class PoliticaMonetaria:
    signo: int        # +1 expansiva, -1 contractiva
    etiqueta: str
    detalle: str


def clasificar_politica_monetaria(p0: Parametros, p1: Parametros) -> PoliticaMonetaria | None:
    delta = p1.oferta_real - p0.oferta_real
    if delta == 0:
        return None
    if delta > 0:
        return PoliticaMonetaria(
            1,
            "Política monetaria expansiva",
            "El banco central aumenta la oferta monetaria. Con el nivel de precios fijo, "
            "la oferta monetaria real M/P sube.",
        )
    return PoliticaMonetaria(
        -1,
        "Política monetaria contractiva",
        "El banco central reduce la oferta monetaria. Con el nivel de precios fijo, "
        "la oferta monetaria real M/P baja.",
    )


def _signo(x: float) -> int:
    return (x > 0) - (x < 0)


@dataclass(frozen=True)
class ResultadoShockDinero:
    p0: Parametros
    p1: Parametros
    e0: Equilibrio
    e1: Equilibrio
    is_: Recta
    lm0: Recta
    lm1: Recta
    multiplicador: MultiplicadorMonetario
    politica: PoliticaMonetaria | None
    fuera_de_rango: list[FueraDeRango]
    tabla: list[FilaComparacion]

    @property
    def hay_shock(self) -> bool:
        return self.politica is not None

    @property
    def delta_oferta_real(self) -> float:
        return self.p1.oferta_real - self.p0.oferta_real

    @property
    def delta_Y(self) -> float:
        return self.e1.Y - self.e0.Y

    @property
    def delta_i(self) -> float:
        return self.e1.i - self.e0.i

    @property
    def delta_I(self) -> float:
        """Con I0 fijo, todo el cambio de la inversión se debe a la tasa: ΔI = -b·Δi."""
        return self.e1.I - self.e0.I

    @property
    def delta_C(self) -> float:
        return self.e1.C - self.e0.C

    @property
    def desplazamiento_lm_horizontal(self) -> float:
        return self.delta_oferta_real / self.p0.k

    @property
    def desplazamiento_lm_vertical(self) -> float:
        return -self.delta_oferta_real / self.p0.h

    def controles_de_signo(self) -> list[tuple[str, bool]]:
        """Signos que exige la teoría ante un cambio de M/P (todos deben ser True)."""
        s = _signo(self.delta_oferta_real)
        return [
            ("La tasa de interés se mueve en sentido opuesto a M/P", _signo(self.delta_i) == -s),
            ("La inversión se mueve en el mismo sentido que M/P", _signo(self.delta_I) == s),
            ("El producto se mueve en el mismo sentido que M/P", _signo(self.delta_Y) == s),
            ("El consumo se mueve en el mismo sentido que M/P", _signo(self.delta_C) == s),
            (
                "G, T e I₀ no cambian (la IS no se desplaza)",
                (self.p1.G, self.p1.T, self.p1.I0) == (self.p0.G, self.p0.T, self.p0.I0),
            ),
            (
                "En E₁ la demanda de dinero absorbe todo el cambio de la oferta",
                abs(self.e1.demanda_dinero - self.e0.demanda_dinero - self.delta_oferta_real) < 1e-9,
            ),
            (
                "El producto cambia menos que el desplazamiento horizontal de la LM",
                abs(self.delta_Y) < abs(self.desplazamiento_lm_horizontal),
            ),
            (
                "La tasa cambia menos que el desplazamiento vertical de la LM",
                abs(self.delta_i) < abs(self.desplazamiento_lm_vertical),
            ),
        ]


def analizar_shock_dinero(base: Parametros, ventana: Ventana, oferta_real: float) -> ResultadoShockDinero:
    """Fija un nuevo nivel de M/P (con P constante) y compara con el escenario base.

    Siempre parte de `base`: los shocks no se acumulan entre llamadas.
    """
    if oferta_real <= 0:
        raise ValueError("La oferta monetaria real M/P debe ser positiva.")
    p1 = base.con_cambios(M=oferta_real * base.P)
    e0, e1 = equilibrio(base), equilibrio(p1)
    return ResultadoShockDinero(
        p0=base,
        p1=p1,
        e0=e0,
        e1=e1,
        is_=curva_is(p1),
        lm0=curva_lm(base),
        lm1=curva_lm(p1),
        multiplicador=multiplicador_monetario(base),
        politica=clasificar_politica_monetaria(base, p1),
        fuera_de_rango=controlar_dominio(e1, ventana),
        tabla=tabla_comparativa(base, e0, p1, e1),
    )
