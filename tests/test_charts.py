"""Verificación del gráfico: escalas fijas, curvas y punto de equilibrio."""

import pytest

from islm.charts import COLOR_IS, COLOR_LM, CurvaGrafico, PuntoGrafico, figura_islm, tramo_visible
from islm.config import PARAMETROS_BASE, VENTANA
from islm.model import curva_is, curva_lm, equilibrio


@pytest.fixture
def figura():
    p = PARAMETROS_BASE
    e0 = equilibrio(p)
    return figura_islm(
        curvas=[CurvaGrafico("IS₀", curva_is(p), COLOR_IS), CurvaGrafico("LM₀", curva_lm(p), COLOR_LM)],
        puntos=[PuntoGrafico("E₀", e0.Y, e0.i)],
        ventana=VENTANA,
    )


def test_ejes_fijos(figura):
    assert list(figura.layout.xaxis.range) == [50, 150]
    assert list(figura.layout.yaxis.range) == [0, 10]
    assert figura.layout.xaxis.fixedrange and figura.layout.yaxis.fixedrange


def test_curvas_dibujadas(figura):
    trazos = {t.name: t for t in figura.data}
    assert list(trazos["IS₀"].x) == [50, 150]
    assert list(trazos["IS₀"].y) == pytest.approx([10, 0])
    assert list(trazos["LM₀"].x) == [50, 150]
    assert list(trazos["LM₀"].y) == pytest.approx([1.25, 8.75])


def test_punto_e0(figura):
    e0 = next(t for t in figura.data if t.name == "E₀")
    assert e0.x[0] == pytest.approx(100)
    assert e0.y[0] == pytest.approx(5)


def test_curvas_base_visibles_en_toda_la_ventana():
    p = PARAMETROS_BASE
    assert tramo_visible(curva_is(p), VENTANA) == pytest.approx((50, 150))
    assert tramo_visible(curva_lm(p), VENTANA) == pytest.approx((50, 150))


def test_flecha_de_desplazamiento_mide_el_corrimiento_de_la_is():
    from islm.charts import flecha_entre_curvas

    p = PARAMETROS_BASE
    is0, is1 = curva_is(p), curva_is(p.con_cambios(G=40))
    flecha = flecha_entre_curvas(is0, is1, VENTANA, "IS")
    assert flecha.Y_hasta - flecha.Y_desde == pytest.approx(50)
    assert VENTANA.i_min <= flecha.i <= VENTANA.i_max
    # Ambos extremos dentro de la ventana.
    assert VENTANA.y_min <= flecha.Y_desde <= VENTANA.y_max
    assert VENTANA.y_min <= flecha.Y_hasta <= VENTANA.y_max


def test_punto_fuera_de_ventana_no_se_recorta():
    p = PARAMETROS_BASE
    fig = figura_islm(
        curvas=[CurvaGrafico("IS₀", curva_is(p), COLOR_IS)],
        puntos=[PuntoGrafico("E₁", 171.43, 10.36)],
        ventana=VENTANA,
    )
    assert list(fig.layout.xaxis.range) == [50, 150]  # los ejes no se reajustan
    assert all(t.name != "E₁" for t in fig.data)  # no se dibuja en el borde
    notas = [a.text for a in fig.layout.annotations]
    assert "E₁ = (171,43; 10,36%) queda fuera del gráfico" in notas
