"""Escenario base calibrado y ventana gráfica del simulador."""

from __future__ import annotations

from dataclasses import dataclass

from islm.model import Parametros

# Calibración: IS0 y LM0 se cortan exactamente en E0 = (100, 5).
PARAMETROS_BASE = Parametros(
    C0=17,
    c=0.60,
    T=20,
    I0=35,
    b=4,
    G=20,
    M=20,
    P=1,
    k=0.60,
    h=8,
)

Y_OBJETIVO = 100
I_OBJETIVO = 5


@dataclass(frozen=True)
class Ventana:
    """Límites fijos de los ejes del gráfico IS-LM."""

    y_min: float
    y_max: float
    i_min: float
    i_max: float


VENTANA = Ventana(y_min=50, y_max=150, i_min=0, i_max=10)


@dataclass(frozen=True)
class RangoControl:
    """Rango de un control de shock (valor en niveles, no en variaciones)."""

    minimo: float
    maximo: float
    paso: float = 1


# Rangos de los controles: con un shock por vez, el nuevo equilibrio queda dentro de VENTANA
# y se respetan G ≥ 0, T ≥ 0, ahorro privado ≥ 0 e inversión ≥ 0.
RANGOS_BIENES = {
    "G": RangoControl(minimo=0, maximo=50),
    "T": RangoControl(minimo=0, maximo=40),
    "I0": RangoControl(minimo=15, maximo=55),
}

# Rango de la oferta monetaria real: Y entre 89,29 y 128,57; i entre 6,07% y 2,14%.
RANGO_OFERTA_REAL = RangoControl(minimo=5, maximo=60)

DESCRIPCION_PARAMETROS = {
    "C0": "Consumo autónomo",
    "c": "Propensión marginal a consumir",
    "T": "Impuestos (suma fija)",
    "I0": "Inversión autónoma",
    "b": "Sensibilidad de la inversión a la tasa",
    "G": "Gasto público",
    "M": "Oferta monetaria nominal",
    "P": "Nivel de precios (fijo)",
    "k": "Sensibilidad de la demanda de dinero al ingreso",
    "h": "Sensibilidad de la demanda de dinero a la tasa",
}
