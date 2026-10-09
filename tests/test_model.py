"""Verificación del motor matemático contra la calibración aprobada."""

from fractions import Fraction as F

import pytest

from islm.config import I_OBJETIVO, PARAMETROS_BASE, Y_OBJETIVO
from islm.model import Parametros, curva_is, curva_lm, equilibrio, gasto_autonomo, residuos

# Mismos parámetros en aritmética racional: si el modelo es exacto, los resultados también.
BASE_EXACTA = Parametros(
    C0=F(17), c=F(3, 5), T=F(20), I0=F(35), b=F(4), G=F(20), M=F(20), P=F(1), k=F(3, 5), h=F(8)
)


def test_equilibrio_base_exacto():
    e = equilibrio(BASE_EXACTA)
    assert (e.Y, e.i) == (100, 5)
    assert e.Yd == 80
    assert e.C == 65
    assert e.I == 15
    assert e.G == 20
    assert e.T == 20
    assert e.C + e.I + e.G == e.Y
    assert e.demanda_dinero == 20
    assert e.oferta_real == 20


def test_curvas_base_exactas():
    assert gasto_autonomo(BASE_EXACTA) == 60
    is0, lm0 = curva_is(BASE_EXACTA), curva_lm(BASE_EXACTA)
    assert (is0.ordenada, is0.pendiente) == (15, F(-1, 10))
    assert (lm0.ordenada, lm0.pendiente) == (F(-5, 2), F(3, 40))


def test_is_y_lm_se_cruzan_en_100_5():
    is0, lm0 = curva_is(BASE_EXACTA), curva_lm(BASE_EXACTA)
    assert is0.tasa(100) == lm0.tasa(100) == 5
    assert is0.producto(5) == lm0.producto(5) == 100


def test_configuracion_en_punto_flotante():
    e = equilibrio(PARAMETROS_BASE)
    assert e.Y == pytest.approx(Y_OBJETIVO, abs=1e-12)
    assert e.i == pytest.approx(I_OBJETIVO, abs=1e-12)
    assert all(abs(v) < 1e-12 for v in residuos(e).values())


@pytest.mark.parametrize(
    "cambios",
    [{"G": 40}, {"G": 0}, {"T": 40}, {"T": 0}, {"I0": 55}, {"I0": 15}, {"M": 30}, {"M": 10}],
)
def test_forma_cerrada_coincide_con_interseccion(cambios):
    """La solución cerrada debe ser la intersección de las curvas para cualquier shock."""
    p = BASE_EXACTA.con_cambios(**{k: F(v) for k, v in cambios.items()})
    e = equilibrio(p)
    assert curva_is(p).tasa(e.Y) == e.i
    assert curva_lm(p).tasa(e.Y) == e.i
    assert residuos(e) == {"mercado_bienes": 0, "mercado_dinero": 0}


@pytest.mark.parametrize(
    "cambios",
    [{"c": 1}, {"c": 0}, {"b": 0}, {"k": 0}, {"h": 0}, {"P": 0}],
)
def test_parametros_invalidos(cambios):
    with pytest.raises(ValueError):
        PARAMETROS_BASE.con_cambios(**cambios)
