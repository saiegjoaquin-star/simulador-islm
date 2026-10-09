"""Motor matemático del modelo IS-LM de economía cerrada con precios fijos.

Formulación lineal, con una única tasa de interés i expresada en puntos porcentuales:

    Yd = Y - T                 ingreso disponible
    C  = C0 + c·Yd             función de consumo
    I  = I0 - b·i              función de inversión
    IS: Y = C + I + G          equilibrio del mercado de bienes
    L  = k·Y - h·i             demanda de saldos reales
    LM: M/P = L                equilibrio del mercado de dinero

Este módulo no depende de Streamlit ni de Plotly: todas las funciones son puras
y reciben un objeto `Parametros`. Un shock se representa creando un nuevo
`Parametros` con `con_cambios(...)` y recalculando el equilibrio.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Parametros:
    """Parámetros exógenos del modelo."""

    C0: float  # consumo autónomo
    c: float   # propensión marginal a consumir
    T: float   # impuestos (suma fija)
    I0: float  # inversión autónoma
    b: float   # sensibilidad de la inversión a la tasa de interés
    G: float   # gasto público
    M: float   # oferta monetaria nominal
    P: float   # nivel de precios (fijo)
    k: float   # sensibilidad de la demanda de dinero al ingreso
    h: float   # sensibilidad de la demanda de dinero a la tasa de interés

    def __post_init__(self) -> None:
        if not 0 < self.c < 1:
            raise ValueError("La propensión marginal a consumir c debe estar entre 0 y 1.")
        if self.b <= 0:
            raise ValueError("La sensibilidad de la inversión b debe ser positiva.")
        if self.k <= 0:
            raise ValueError("La sensibilidad de la demanda de dinero al ingreso k debe ser positiva.")
        if self.h <= 0:
            raise ValueError("La sensibilidad de la demanda de dinero a la tasa h debe ser positiva.")
        if self.P <= 0:
            raise ValueError("El nivel de precios P debe ser positivo.")

    @property
    def oferta_real(self) -> float:
        """Oferta monetaria real M/P."""
        return self.M / self.P

    def con_cambios(self, **cambios: float) -> "Parametros":
        """Devuelve una copia con algunos parámetros modificados (base para shocks)."""
        return replace(self, **cambios)


@dataclass(frozen=True)
class Recta:
    """Curva lineal en el plano (Y, i): i = ordenada + pendiente · Y."""

    ordenada: float
    pendiente: float

    def tasa(self, Y: float) -> float:
        return self.ordenada + self.pendiente * Y

    def producto(self, i: float) -> float:
        return (i - self.ordenada) / self.pendiente


@dataclass(frozen=True)
class Equilibrio:
    """Valores de equilibrio de las variables endógenas y sus componentes."""

    Y: float
    i: float
    Yd: float
    C: float
    I: float
    G: float
    T: float
    demanda_dinero: float
    oferta_real: float


def gasto_autonomo(p: Parametros) -> float:
    """Ā = C0 - c·T + I0 + G: la parte de la demanda que no depende de Y ni de i."""
    return p.C0 - p.c * p.T + p.I0 + p.G


def curva_is(p: Parametros) -> Recta:
    """IS: de Y = C0 + c(Y - T) + I0 - b·i + G se despeja i = Ā/b - [(1 - c)/b]·Y."""
    return Recta(ordenada=gasto_autonomo(p) / p.b, pendiente=-(1 - p.c) / p.b)


def curva_lm(p: Parametros) -> Recta:
    """LM: de M/P = k·Y - h·i se despeja i = (k/h)·Y - (M/P)/h."""
    return Recta(ordenada=-p.oferta_real / p.h, pendiente=p.k / p.h)


def consumo(p: Parametros, Y: float) -> float:
    return p.C0 + p.c * (Y - p.T)


def inversion(p: Parametros, i: float) -> float:
    return p.I0 - p.b * i


def demanda_dinero(p: Parametros, Y: float, i: float) -> float:
    return p.k * Y - p.h * i


def equilibrio(p: Parametros) -> Equilibrio:
    """Resuelve el sistema IS-LM en forma cerrada.

    Con s = 1 - c y D = h·s + b·k:
        Y* = (h·Ā + b·M/P) / D
        i* = (k·Ā - s·M/P) / D
    """
    s = 1 - p.c
    A = gasto_autonomo(p)
    D = p.h * s + p.b * p.k
    Y = (p.h * A + p.b * p.oferta_real) / D
    i = (p.k * A - s * p.oferta_real) / D
    return Equilibrio(
        Y=Y,
        i=i,
        Yd=Y - p.T,
        C=consumo(p, Y),
        I=inversion(p, i),
        G=p.G,
        T=p.T,
        demanda_dinero=demanda_dinero(p, Y, i),
        oferta_real=p.oferta_real,
    )


def residuos(e: Equilibrio) -> dict[str, float]:
    """Desvíos de las condiciones de equilibrio (deben ser cero)."""
    return {
        "mercado_bienes": e.Y - (e.C + e.I + e.G),
        "mercado_dinero": e.demanda_dinero - e.oferta_real,
    }
