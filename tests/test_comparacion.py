"""Verificación de la comparación de políticas."""

from fractions import Fraction as F

import pytest

from islm.comparacion import TIPOS_SHOCK, comparar, magnitud_maxima, resolver_escenario
from islm.config import PARAMETROS_BASE, VENTANA
from islm.mercado_bienes import analizar_shock_bienes
from islm.mercado_dinero import analizar_shock_dinero
from islm.model import Parametros

BASE = Parametros(
    C0=F(17), c=F(3, 5), T=F(20), I0=F(35), b=F(4), G=F(20), M=F(20), P=F(1), k=F(3, 5), h=F(8)
)

# Signos teóricos exigidos: (ΔY, Δi)
SIGNOS = {
    "Política fiscal expansiva": (1, 1),
    "Política monetaria expansiva": (1, -1),
    "Política fiscal contractiva": (-1, -1),
    "Política monetaria contractiva": (-1, 1),
    "Shock positivo de inversión": (1, 1),
    "Shock negativo de inversión": (-1, -1),
}


def signo(x):
    return (x > 0) - (x < 0)


def test_magnitudes_maximas_respetan_los_rangos_aprobados():
    esperado = {"G+": 30, "G-": 20, "T+": 20, "T-": 20, "M+": 40, "M-": 15, "I0+": 20, "I0-": 20}
    assert {k: magnitud_maxima(BASE, t) for k, t in TIPOS_SHOCK.items()} == esperado


def test_categorias():
    categorias = {k: t.categoria for k, t in TIPOS_SHOCK.items()}
    assert categorias == {
        "G+": "Política fiscal", "G-": "Política fiscal", "T+": "Política fiscal", "T-": "Política fiscal",
        "M+": "Política monetaria", "M-": "Política monetaria",
        "I0+": "Shock privado", "I0-": "Shock privado",
    }
    # Un shock de inversión nunca se clasifica como política.
    for clave in ("I0+", "I0-"):
        assert "política" not in TIPOS_SHOCK[clave].clasificacion.lower()


@pytest.mark.parametrize("clave", list(TIPOS_SHOCK))
def test_signos_en_todo_el_rango(clave):
    """Para cada tipo y cada magnitud entera permitida, Y e i se mueven según la teoría."""
    tipo = TIPOS_SHOCK[clave]
    sY, si = SIGNOS[tipo.clasificacion]
    for magnitud in range(1, int(magnitud_maxima(BASE, tipo)) + 1):
        r = resolver_escenario("A", BASE, VENTANA, tipo, F(magnitud))
        assert (signo(r.delta_Y), signo(r.delta_i)) == (sY, si), (clave, magnitud)
        assert all(ok for _, ok in r.controles_de_signo())
        assert r.fuera_de_rango == []


@pytest.mark.parametrize("clave", list(TIPOS_SHOCK))
def test_coincide_con_los_modulos_aprobados(clave):
    tipo = TIPOS_SHOCK[clave]
    r = resolver_escenario("A", BASE, VENTANA, tipo, F(10))
    if tipo.variable == "M/P":
        ref = analizar_shock_dinero(BASE, VENTANA, 20 + tipo.direccion * 10)
    else:
        ref = analizar_shock_bienes(BASE, VENTANA, **{tipo.variable: getattr(BASE, tipo.variable) + tipo.direccion * 10})
    assert (r.e1.Y, r.e1.i, r.e1.C, r.e1.I) == (ref.e1.Y, ref.e1.i, ref.e1.C, ref.e1.I)


def test_escenarios_independientes_desde_la_misma_base():
    c = comparar(BASE, VENTANA, TIPOS_SHOCK["G+"], F(10), TIPOS_SHOCK["M+"], F(10))
    assert c.a.e0 == c.b.e0 == c.e0
    assert (c.e0.Y, c.e0.i) == (100, 5)
    # A no lleva el cambio de M/P de B, ni B el cambio de G de A.
    assert c.a.p1.M == 20 and c.b.p1.G == 20
    # Valores exactos: ΔG = +10 → (800/7; 85/14); Δ(M/P) = +10 → (750/7; 30/7).
    assert (c.a.e1.Y, c.a.e1.i) == (F(800, 7), F(85, 14))
    assert (c.b.e1.Y, c.b.e1.i) == (F(750, 7), F(30, 7))


def test_veredictos_fiscal_vs_monetaria():
    c = comparar(BASE, VENTANA, TIPOS_SHOCK["G+"], F(10), TIPOS_SHOCK["M+"], F(10))
    v = {x.criterio: x for x in c.veredictos()}
    assert v["Producción"].ganador == "A"         # +14,29 frente a +7,14
    assert v["Tasa de interés"].ganador == "A"    # +1,07 frente a -0,71
    assert v["Crowding out"].ganador == "A"       # solo A es fiscal expansiva
    assert v["Inversión"].ganador == "A"          # |-4,29| frente a |+2,86|
    assert c.a.crowding_out == F(30, 7) and c.b.crowding_out is None


def test_crowding_out_entre_dos_politicas_fiscales_expansivas():
    c = comparar(BASE, VENTANA, TIPOS_SHOCK["G+"], F(10), TIPOS_SHOCK["T-"], F(10))
    # ΔG = +10 sube i en 15/14; ΔT = -10 la sube en 9/14. Crowding out = b·Δi.
    assert c.a.crowding_out == 4 * F(15, 14)
    assert c.b.crowding_out == 4 * F(9, 14)
    assert {x.criterio: x.ganador for x in c.veredictos()}["Crowding out"] == "A"


def test_crowding_out_no_aplica():
    c = comparar(BASE, VENTANA, TIPOS_SHOCK["M+"], F(10), TIPOS_SHOCK["I0+"], F(10))
    assert {x.criterio: x.ganador for x in c.veredictos()}["Crowding out"] == "—"


def test_empate_gasto_publico_e_inversion_autonoma():
    """ΔG y ΔI0 de igual magnitud desplazan la misma IS: mismo Y e i, distinta composición."""
    c = comparar(BASE, VENTANA, TIPOS_SHOCK["G+"], F(10), TIPOS_SHOCK["I0+"], F(10))
    v = {x.criterio: x.ganador for x in c.veredictos()}
    assert v["Producción"] is None and v["Tasa de interés"] is None
    assert v["Inversión"] == "B"  # en B la inversión sube (ΔI0 - b·Δi), en A cae
    assert c.a.is1.ordenada == c.b.is1.ordenada


def test_sentidos_opuestos():
    c = comparar(BASE, VENTANA, TIPOS_SHOCK["G+"], F(10), TIPOS_SHOCK["M-"], F(10))
    assert c.a.delta_Y > 0 > c.b.delta_Y
    texto = " ".join(c.interpretacion())
    assert "sentidos opuestos" in texto


def test_interpretacion_no_normativa():
    for a in TIPOS_SHOCK.values():
        for b in TIPOS_SHOCK.values():
            texto = " ".join(c for c in comparar(PARAMETROS_BASE, VENTANA, a, 5, b, 5).interpretacion()).lower()
            for palabra in ("mejor", "peor", "conviene", "recomend", "deberí"):
                assert palabra not in texto, (a.clave, b.clave, palabra)
            assert "no indica que una intervención sea preferible" in texto


def test_magnitud_invalida():
    with pytest.raises(ValueError):
        resolver_escenario("A", BASE, VENTANA, TIPOS_SHOCK["G-"], F(21))  # G quedaría negativo
    with pytest.raises(ValueError):
        resolver_escenario("A", BASE, VENTANA, TIPOS_SHOCK["G+"], 0)


def test_interpretacion_del_empate_no_habla_de_magnitud():
    c = comparar(BASE, VENTANA, TIPOS_SHOCK["G+"], F(10), TIPOS_SHOCK["I0+"], F(10))
    texto = " ".join(c.interpretacion())
    assert "mismo equilibrio" in texto and "composición del gasto" in texto
    assert "la diferencia está en la magnitud" not in texto


def test_notacion_de_las_variables():
    c = comparar(BASE, VENTANA, TIPOS_SHOCK["I0+"], F(10), TIPOS_SHOCK["M+"], F(10))
    texto = " ".join(c.interpretacion())
    assert "ΔY/ΔI₀" in texto and "ΔY/Δ(M/P)" in texto
