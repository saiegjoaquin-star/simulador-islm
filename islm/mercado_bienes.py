"""Shocks del mercado de bienes: G, T e I0 desplazan la IS; la LM no cambia.

Multiplicadores (De Gregorio, cap. 19):
    simple (cruz keynesiana, ec. 19.7 y p. 504):  dY/dG = dY/dI0 = 1/(1-c),  dY/dT = -c/(1-c)
    IS-LM (p. 520):                               dY/dG = dY/dI0 = h/D,      dY/dT = -c·h/D
    tasa:                                         di/dG = di/dI0 = k/D,      di/dT = -c·k/D
con D = h(1-c) + b·k.

El multiplicador simple mide el desplazamiento horizontal de la IS; el de IS-LM, el
efecto final una vez que la tasa de interés se ajusta a lo largo de la LM.
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
    gasto_autonomo,
)
from islm.shocks import FilaComparacion, FueraDeRango, controlar_dominio, tabla_comparativa

VARIABLES_BIENES = ("G", "T", "I0")

NOMBRES = {
    "G": "Gasto público",
    "T": "Impuestos",
    "I0": "Inversión autónoma",
}


@dataclass(frozen=True)
class Multiplicador:
    variable: str
    simple: float   # efecto sobre Y sin ajuste de la tasa (desplazamiento de la IS)
    islm: float     # efecto final sobre Y en el equilibrio IS-LM
    tasa: float     # efecto final sobre i


def multiplicadores(p: Parametros) -> dict[str, Multiplicador]:
    s = 1 - p.c
    D = p.h * s + p.b * p.k
    gasto = Multiplicador("G", simple=1 / s, islm=p.h / D, tasa=p.k / D)
    return {
        "G": gasto,
        "I0": Multiplicador("I0", simple=gasto.simple, islm=gasto.islm, tasa=gasto.tasa),
        "T": Multiplicador("T", simple=-p.c / s, islm=-p.c * p.h / D, tasa=-p.c * p.k / D),
    }


@dataclass(frozen=True)
class EfectoVariable:
    """Aporte de una variable modificada al cambio total."""

    variable: str
    delta: float
    multiplicador: Multiplicador

    @property
    def desplazamiento_is(self) -> float:
        return self.multiplicador.simple * self.delta

    @property
    def efecto_Y(self) -> float:
        return self.multiplicador.islm * self.delta

    @property
    def efecto_i(self) -> float:
        return self.multiplicador.tasa * self.delta


@dataclass(frozen=True)
class ShockIdentificado:
    tipo: str        # "fiscal" o "inversion"
    signo: int       # +1 expansivo / positivo, -1 contractivo / negativo, 0 neutro
    etiqueta: str
    detalle: str


def _verbo(delta: float) -> str:
    return "Aumento" if delta > 0 else "Reducción"


def clasificar_shock(p0: Parametros, p1: Parametros) -> list[ShockIdentificado]:
    """Identifica el shock. La inversión autónoma es un shock privado, nunca política fiscal."""
    dG, dT, dI0 = p1.G - p0.G, p1.T - p0.T, p1.I0 - p0.I0
    shocks = []

    if dG or dT:
        # Signo de la política según su efecto sobre el gasto autónomo: ΔĀ = ΔG - c·ΔT.
        impulso = dG - p0.c * dT
        signo = (impulso > 0) - (impulso < 0)
        componentes = []
        if dG:
            componentes.append(f"{_verbo(dG).lower()} del gasto público")
        if dT:
            componentes.append(f"{_verbo(dT).lower()} de los impuestos")
        etiqueta = {
            1: "Política fiscal expansiva",
            -1: "Política fiscal contractiva",
            0: "Política fiscal neutra sobre la demanda",
        }[signo]
        detalle = " y ".join(componentes).capitalize() + "."
        shocks.append(ShockIdentificado("fiscal", signo, etiqueta, detalle))

    if dI0:
        signo = 1 if dI0 > 0 else -1
        etiqueta = "Shock positivo de inversión" if signo > 0 else "Shock negativo de inversión"
        detalle = (
            f"{_verbo(dI0)} de la inversión autónoma: es un shock privado "
            "(cambio en las expectativas de las empresas), no una política económica."
        )
        shocks.append(ShockIdentificado("inversion", signo, etiqueta, detalle))

    return shocks


@dataclass(frozen=True)
class ResultadoShockBienes:
    p0: Parametros
    p1: Parametros
    e0: Equilibrio
    e1: Equilibrio
    is0: Recta
    is1: Recta
    lm: Recta
    efectos: list[EfectoVariable]
    shocks: list[ShockIdentificado]
    fuera_de_rango: list[FueraDeRango]
    tabla: list[FilaComparacion]

    @property
    def hay_shock(self) -> bool:
        return bool(self.efectos)

    @property
    def delta_gasto_autonomo(self) -> float:
        return gasto_autonomo(self.p1) - gasto_autonomo(self.p0)

    @property
    def desplazamiento_is(self) -> float:
        """Corrimiento horizontal de la IS: ΔĀ/(1-c). Es el efecto de la cruz keynesiana."""
        return self.delta_gasto_autonomo / (1 - self.p0.c)

    @property
    def delta_Y(self) -> float:
        return self.e1.Y - self.e0.Y

    @property
    def delta_i(self) -> float:
        return self.e1.i - self.e0.i

    @property
    def delta_I(self) -> float:
        return self.e1.I - self.e0.I

    @property
    def delta_I0(self) -> float:
        return self.p1.I0 - self.p0.I0

    @property
    def efecto_tasa_sobre_inversion(self) -> float:
        """Parte de ΔI causada por el cambio de la tasa: -b·Δi (crowding out si es negativa)."""
        return -self.p0.b * self.delta_i

    @property
    def producto_perdido_por_tasa(self) -> float:
        """Diferencia entre el desplazamiento de la IS y el efecto final sobre Y."""
        return self.desplazamiento_is - self.delta_Y

    @property
    def delta_i_fiscal(self) -> float:
        """Parte de Δi atribuible a G y T (el modelo es lineal: los efectos se suman)."""
        return sum(ef.efecto_i for ef in self.efectos if ef.variable in ("G", "T"))

    @property
    def crowding_out(self) -> float | None:
        """Inversión privada desplazada por la suba de la tasa que causa una política fiscal
        expansiva: b·Δi_fiscal. None si no hay política fiscal expansiva."""
        fiscal = next((s for s in self.shocks if s.tipo == "fiscal"), None)
        if fiscal is None or fiscal.signo <= 0:
            return None
        return self.p0.b * self.delta_i_fiscal


def analizar_shock_bienes(
    base: Parametros, ventana: Ventana, **niveles: float
) -> ResultadoShockBienes:
    """Aplica nuevos niveles de G, T y/o I0 sobre el escenario base y compara equilibrios.

    Siempre parte de `base`: los shocks no se acumulan entre llamadas.
    """
    desconocidas = set(niveles) - set(VARIABLES_BIENES)
    if desconocidas:
        raise ValueError(f"Variables no permitidas en el mercado de bienes: {sorted(desconocidas)}")

    p1 = base.con_cambios(**niveles)
    e0, e1 = equilibrio(base), equilibrio(p1)
    mult = multiplicadores(base)
    efectos = [
        EfectoVariable(var, getattr(p1, var) - getattr(base, var), mult[var])
        for var in VARIABLES_BIENES
        if getattr(p1, var) != getattr(base, var)
    ]
    return ResultadoShockBienes(
        p0=base,
        p1=p1,
        e0=e0,
        e1=e1,
        is0=curva_is(base),
        is1=curva_is(p1),
        lm=curva_lm(p1),
        efectos=efectos,
        shocks=clasificar_shock(base, p1),
        fuera_de_rango=controlar_dominio(e1, ventana),
        tabla=tabla_comparativa(base, e0, p1, e1),
    )
