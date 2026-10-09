"""Verificación exacta de los shocks del mercado de dinero."""

from fractions import Fraction as F

import pytest

from islm.config import PARAMETROS_BASE, RANGO_OFERTA_REAL, VENTANA
from islm.mercado_dinero import analizar_shock_dinero, multiplicador_monetario
from islm.model import Parametros, demanda_dinero, equilibrio

BASE = Parametros(
    C0=F(17), c=F(3, 5), T=F(20), I0=F(35), b=F(4), G=F(20), M=F(20), P=F(1), k=F(3, 5), h=F(8)
)

# Tabla aprobada en la calibración (Y1, i1, C1, I1), en séptimos.
CASOS = {
    30: (F(750, 7), F(30, 7), F(485, 7), F(125, 7)),
    10: (F(650, 7), F(40, 7), F(425, 7), F(85, 7)),
}


def analizar(mp):
    return analizar_shock_dinero(BASE, VENTANA, F(mp))


@pytest.mark.parametrize("mp", CASOS)
def test_nuevo_equilibrio_coincide_con_tabla_aprobada(mp):
    r = analizar(mp)
    assert (r.e1.Y, r.e1.i, r.e1.C, r.e1.I) == CASOS[mp]
    assert (r.e1.G, r.e1.T) == (20, 20)
    assert r.e1.C + r.e1.I + r.e1.G == r.e1.Y
    assert r.e1.demanda_dinero == r.e1.oferta_real == mp


def test_extremos_del_rango_aprobado():
    r = analizar(60)
    assert (r.e1.Y, r.e1.i) == (F(900, 7), F(15, 7))  # 128,57 y 2,14
    r = analizar(5)
    assert (r.e1.Y, r.e1.i) == (F(625, 7), F(85, 14))  # 89,29 y 6,07


def test_multiplicadores_exactos_y_consistentes_con_el_motor():
    m = multiplicador_monetario(BASE)
    assert (m.producto, m.tasa) == (F(5, 7), F(-1, 14))
    e0 = equilibrio(BASE)
    e1 = equilibrio(BASE.con_cambios(M=BASE.M + 1))
    assert (e1.Y - e0.Y, e1.i - e0.i) == (m.producto, m.tasa)


@pytest.mark.parametrize("mp", [5, 10, 19, 21, 30, 60])
def test_desplazamiento_de_la_lm(mp):
    r = analizar(mp)
    d = F(mp) - 20
    # Pendiente igual: la LM se traslada en paralelo; la IS no cambia.
    assert r.lm1.pendiente == r.lm0.pendiente == F(3, 40)
    assert (r.is_.ordenada, r.is_.pendiente) == (15, F(-1, 10))
    # Corrimiento horizontal Δ(M/P)/k a cualquier tasa y vertical -Δ(M/P)/h a cualquier producto.
    for i in (0, 3, 5, 10):
        assert r.lm1.producto(i) - r.lm0.producto(i) == d / F(3, 5) == r.desplazamiento_lm_horizontal
    for Y in (50, 100, 150):
        assert r.lm1.tasa(Y) - r.lm0.tasa(Y) == -d / 8 == r.desplazamiento_lm_vertical
    # E1 sobre IS0 y LM1.
    assert r.is_.tasa(r.e1.Y) == r.lm1.tasa(r.e1.Y) == r.e1.i


@pytest.mark.parametrize("mp", [5, 10, 19, 21, 30, 60])
def test_signos_economicos(mp):
    r = analizar(mp)
    assert all(ok for _, ok in r.controles_de_signo()), r.controles_de_signo()
    if mp > 20:
        assert r.delta_i < 0 and r.delta_I > 0 and r.delta_Y > 0 and r.delta_C > 0
        assert r.politica.etiqueta == "Política monetaria expansiva"
        assert r.p1.oferta_real - demanda_dinero(r.p1, r.e0.Y, r.e0.i) > 0  # exceso de oferta en E0
    else:
        assert r.delta_i > 0 and r.delta_I < 0 and r.delta_Y < 0 and r.delta_C < 0
        assert r.politica.etiqueta == "Política monetaria contractiva"
        assert r.p1.oferta_real - demanda_dinero(r.p1, r.e0.Y, r.e0.i) < 0  # exceso de demanda en E0


def test_mecanismo_cierra_numericamente():
    r = analizar(30)
    assert r.p1.oferta_real - demanda_dinero(r.p1, r.e0.Y, r.e0.i) == 10
    assert r.delta_I == -4 * r.delta_i  # ΔI = -b·Δi, con I0 fijo
    assert r.delta_Y == r.delta_I / F(2, 5)  # ΔY = ΔI/(1-c)
    assert r.delta_C == F(3, 5) * r.delta_Y
    # La demanda de dinero absorbe el aumento de la oferta por ingreso y por tasa.
    por_ingreso, por_tasa = BASE.k * r.delta_Y, -BASE.h * r.delta_i
    assert por_ingreso + por_tasa == 10
    assert (por_ingreso, por_tasa) == (F(30, 7), F(40, 7))


def test_sin_shock():
    r = analizar(20)
    assert not r.hay_shock and r.politica is None
    assert (r.e1.Y, r.e1.i) == (100, 5)


def test_todo_el_rango_del_slider_queda_en_el_dominio():
    for mp in range(int(RANGO_OFERTA_REAL.minimo), int(RANGO_OFERTA_REAL.maximo) + 1):
        r = analizar_shock_dinero(PARAMETROS_BASE, VENTANA, mp)
        assert r.fuera_de_rango == [], mp


def test_fuera_de_dominio_no_recorta():
    r = analizar(100)  # fuera del rango del slider: i negativa
    assert r.e1.i == F(-5, 7) < 0
    assert r.e1.Y == F(1100, 7) > 150
    assert {f.variable for f in r.fuera_de_rango} == {"Y", "i"}


def test_oferta_no_positiva():
    with pytest.raises(ValueError):
        analizar_shock_dinero(BASE, VENTANA, 0)
