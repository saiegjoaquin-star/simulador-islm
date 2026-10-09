"""Herramientas comunes a cualquier shock: comparación de equilibrios y control de dominio.

Se usan desde el mercado de bienes y se reutilizarán en el mercado de dinero.
No recortan resultados: solo informan si un equilibrio cae fuera de lo admitido.
"""

from __future__ import annotations

from dataclasses import dataclass

from islm.config import Ventana
from islm.model import Equilibrio, Parametros


@dataclass(frozen=True)
class FilaComparacion:
    variable: str
    base: float
    nuevo: float
    es_tasa: bool = False

    @property
    def variacion(self) -> float:
        return self.nuevo - self.base


def tabla_comparativa(
    p0: Parametros, e0: Equilibrio, p1: Parametros, e1: Equilibrio
) -> list[FilaComparacion]:
    """Filas Variable | Escenario base | Nuevo equilibrio | Variación."""
    return [
        FilaComparacion("Producto, Y", e0.Y, e1.Y),
        FilaComparacion("Tasa de interés, i (%)", e0.i, e1.i, es_tasa=True),
        FilaComparacion("Ingreso disponible, Yd", e0.Yd, e1.Yd),
        FilaComparacion("Consumo de equilibrio, C", e0.C, e1.C),
        FilaComparacion("Inversión de equilibrio, I", e0.I, e1.I),
        FilaComparacion("Inversión autónoma, I₀", p0.I0, p1.I0),
        FilaComparacion("Gasto público, G", e0.G, e1.G),
        FilaComparacion("Impuestos, T", e0.T, e1.T),
        FilaComparacion("Saldo fiscal, T − G", e0.T - e0.G, e1.T - e1.G),
        FilaComparacion("Oferta monetaria real, M/P", e0.oferta_real, e1.oferta_real),
        FilaComparacion("Demanda de dinero, L", e0.demanda_dinero, e1.demanda_dinero),
    ]


@dataclass(frozen=True)
class FueraDeRango:
    """Variable de equilibrio que viola un límite visual o económico."""

    variable: str
    valor: float
    minimo: float | None
    maximo: float | None


def controlar_dominio(e: Equilibrio, ventana: Ventana) -> list[FueraDeRango]:
    """Lista las variables fuera del dominio admitido (vacía si todo está en orden)."""
    problemas = []
    if not ventana.y_min <= e.Y <= ventana.y_max:
        problemas.append(FueraDeRango("Y", e.Y, ventana.y_min, ventana.y_max))
    if not ventana.i_min <= e.i <= ventana.i_max:
        problemas.append(FueraDeRango("i", e.i, ventana.i_min, ventana.i_max))
    if e.C < 0:
        problemas.append(FueraDeRango("C", e.C, 0, None))
    if e.I < 0:
        problemas.append(FueraDeRango("I", e.I, 0, None))
    return problemas
