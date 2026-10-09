"""Verificación exacta de los shocks del mercado de bienes."""

from fractions import Fraction as F

import pytest

from islm.config import PARAMETROS_BASE, RANGOS_BIENES, VENTANA
from islm.mercado_bienes import analizar_shock_bienes, clasificar_shock, multiplicadores
from islm.model import Parametros, equilibrio

BASE = Parametros(
    C0=F(17), c=F(3, 5), T=F(20), I0=F(35), b=F(4), G=F(20), M=F(20), P=F(1), k=F(3, 5), h=F(8)
)

# Tabla aprobada en la etapa de calibración: (Y1, i1, C1, I1, G1, T1), en séptimos.
CASOS = {
    "G+20": ({"G": 40}, (F(900, 7), F(50, 7), F(575, 7), F(45, 7), 40, 20)),
    "G-20": ({"G": 0}, (F(500, 7), F(20, 7), F(335, 7), F(165, 7), 0, 20)),
    "T+20": ({"T": 40}, (F(580, 7), F(26, 7), F(299, 7), F(141, 7), 20, 40)),
    "T-20": ({"T": 0}, (F(820, 7), F(44, 7), F(611, 7), F(69, 7), 20, 0)),
    "I0+20": ({"I0": 55}, (F(900, 7), F(50, 7), F(575, 7), F(185, 7), 20, 20)),
    "I0-20": ({"I0": 15}, (F(500, 7), F(20, 7), F(335, 7), F(25, 7), 20, 20)),
}

# Desplazamiento horizontal esperado de la IS: ΔĀ/(1-c), con ΔĀ = ΔG - c·ΔT + ΔI0.
DESPLAZAMIENTOS = {"G+20": 50, "G-20": -50, "T+20": -30, "T-20": 30, "I0+20": 50, "I0-20": -50}


def analizar(**niveles):
    return analizar_shock_bienes(BASE, VENTANA, **{k: F(v) for k, v in niveles.items()})


@pytest.mark.parametrize("nombre", CASOS)
def test_nuevo_equilibrio_coincide_con_tabla_aprobada(nombre):
    niveles, esperado = CASOS[nombre]
    r = analizar(**niveles)
    assert (r.e1.Y, r.e1.i, r.e1.C, r.e1.I, r.e1.G, r.e1.T) == esperado
    assert r.e1.C + r.e1.I + r.e1.G == r.e1.Y
    assert r.e1.demanda_dinero == r.e1.oferta_real == 20


@pytest.mark.parametrize("nombre", CASOS)
def test_desplazamiento_de_la_is(nombre):
    niveles, _ = CASOS[nombre]
    r = analizar(**niveles)
    # Misma pendiente: la IS se traslada en paralelo.
    assert r.is1.pendiente == r.is0.pendiente == F(-1, 10)
    # El corrimiento horizontal es el mismo a cualquier tasa y vale ΔĀ/(1-c).
    for i in (0, 2, 5, 10):
        assert r.is1.producto(i) - r.is0.producto(i) == DESPLAZAMIENTOS[nombre]
    assert r.desplazamiento_is == DESPLAZAMIENTOS[nombre]
    # La LM no cambia.
    assert (r.lm.ordenada, r.lm.pendiente) == (F(-5, 2), F(3, 40))
    # E1 está sobre IS1 y sobre LM0.
    assert r.is1.tasa(r.e1.Y) == r.lm.tasa(r.e1.Y) == r.e1.i


def test_multiplicadores_exactos():
    m = multiplicadores(BASE)
    assert (m["G"].simple, m["G"].islm, m["G"].tasa) == (F(5, 2), F(10, 7), F(3, 28))
    assert (m["I0"].simple, m["I0"].islm, m["I0"].tasa) == (F(5, 2), F(10, 7), F(3, 28))
    assert (m["T"].simple, m["T"].islm, m["T"].tasa) == (F(-3, 2), F(-6, 7), F(-9, 140))


@pytest.mark.parametrize("var", ["G", "T", "I0"])
def test_multiplicadores_coinciden_con_el_motor(var):
    """Un shock unitario recalculado con el motor reproduce exactamente cada multiplicador."""
    m = multiplicadores(BASE)[var]
    e0 = equilibrio(BASE)
    e1 = equilibrio(BASE.con_cambios(**{var: getattr(BASE, var) + 1}))
    assert e1.Y - e0.Y == m.islm
    assert e1.i - e0.i == m.tasa


def test_shock_combinado_suma_efectos():
    r = analizar(G=35, T=10, I0=25)
    assert sum(ef.efecto_Y for ef in r.efectos) == r.delta_Y
    assert sum(ef.efecto_i for ef in r.efectos) == r.delta_i
    assert sum(ef.desplazamiento_is for ef in r.efectos) == r.desplazamiento_is


def test_crowding_out_fiscal():
    r = analizar(G=40)
    assert r.delta_i == F(15, 7)
    assert r.efecto_tasa_sobre_inversion == F(-60, 7)
    assert r.delta_I == r.efecto_tasa_sobre_inversion  # sin cambio de I0, todo ΔI es efecto tasa
    assert r.producto_perdido_por_tasa == 50 - F(200, 7)


def test_inversion_autonoma_descompone_delta_I():
    r = analizar(I0=55)
    assert r.delta_I == F(80, 7)
    assert r.delta_I == r.delta_I0 + r.efecto_tasa_sobre_inversion


@pytest.mark.parametrize(
    "niveles, etiquetas",
    [
        ({"G": 40}, ["Política fiscal expansiva"]),
        ({"G": 0}, ["Política fiscal contractiva"]),
        ({"T": 0}, ["Política fiscal expansiva"]),
        ({"T": 40}, ["Política fiscal contractiva"]),
        ({"I0": 55}, ["Shock positivo de inversión"]),
        ({"I0": 15}, ["Shock negativo de inversión"]),
        ({"G": 30, "T": 30}, ["Política fiscal expansiva"]),  # presupuesto equilibrado
        ({"G": 30, "I0": 25}, ["Política fiscal expansiva", "Shock negativo de inversión"]),
    ],
)
def test_clasificacion(niveles, etiquetas):
    shocks = clasificar_shock(BASE, BASE.con_cambios(**{k: F(v) for k, v in niveles.items()}))
    assert [s.etiqueta for s in shocks] == etiquetas


def test_inversion_no_se_describe_como_politica_fiscal():
    for nivel in (15, 55):
        (shock,) = clasificar_shock(BASE, BASE.con_cambios(I0=F(nivel)))
        assert shock.tipo == "inversion"
        assert "fiscal" not in (shock.etiqueta + shock.detalle).lower()


def test_sin_shock():
    r = analizar()
    assert not r.hay_shock and r.shocks == [] and r.delta_Y == 0
    assert (r.e1.Y, r.e1.i) == (100, 5)


@pytest.mark.parametrize("var", ["G", "T", "I0"])
def test_todos_los_valores_de_cada_slider_quedan_en_el_dominio(var):
    """Con un shock aislado, todo el rango aprobado deja el equilibrio dentro de la ventana."""
    rango = RANGOS_BIENES[var]
    for nivel in range(int(rango.minimo), int(rango.maximo) + 1, int(rango.paso)):
        r = analizar_shock_bienes(PARAMETROS_BASE, VENTANA, **{var: nivel})
        assert r.fuera_de_rango == [], (var, nivel)
        assert r.e1.I > 0 and r.e1.C > 0


def test_fuera_de_dominio_no_recorta():
    r = analizar(G=50, T=0, I0=55)
    Y_esperado = (8 * F(122) + 4 * 20) / F(28, 5)
    assert r.e1.Y == Y_esperado > 150  # el valor se informa tal cual, sin recortar
    assert {f.variable for f in r.fuera_de_rango} == {"Y", "i"}


def test_variables_no_permitidas():
    with pytest.raises(ValueError):
        analizar_shock_bienes(BASE, VENTANA, M=30)
