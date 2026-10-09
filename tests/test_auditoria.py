"""Auditoría integral (secciones A–F).

Los valores de referencia se calculan de forma independiente del código auditado:
- el sistema IS-LM se resuelve por la regla de Cramer a partir de las ecuaciones estructurales;
- los multiplicadores se obtienen por diferencias finitas sobre ese solver y se cotejan con
  las fórmulas del libro (De Gregorio, cap. 19);
- la interfaz se inspecciona en lo que la app realmente muestra y envía al navegador.
Todo el motor se audita en aritmética racional exacta (fractions.Fraction).
"""

from __future__ import annotations

import itertools
import json
import math
import re
from fractions import Fraction as F
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from islm.comparacion import TIPOS_SHOCK, comparar, magnitud_maxima, resolver_escenario
from islm.config import PARAMETROS_BASE, RANGO_OFERTA_REAL, RANGOS_BIENES, VENTANA
from islm.interpretacion import interpretar
from islm.mercado_bienes import analizar_shock_bienes, multiplicadores
from islm.mercado_dinero import analizar_shock_dinero, multiplicador_monetario
from islm.model import (
    Parametros,
    consumo,
    curva_is,
    curva_lm,
    demanda_dinero,
    equilibrio,
    gasto_autonomo,
    inversion,
)

BASE = Parametros(
    C0=F(17), c=F(3, 5), T=F(20), I0=F(35), b=F(4), G=F(20), M=F(20), P=F(1), k=F(3, 5), h=F(8)
)
APP = Path(__file__).resolve().parent.parent / "app.py"


def cramer(p: Parametros) -> tuple[F, F]:
    """Solver independiente: (1-c)Y + b·i = C0 - cT + I0 + G ;  k·Y - h·i = M/P."""
    a11, a12, r1 = 1 - p.c, p.b, p.C0 - p.c * p.T + p.I0 + p.G
    a21, a22, r2 = p.k, -p.h, p.M / p.P
    det = a11 * a22 - a12 * a21
    assert det != 0
    return (r1 * a22 - a12 * r2) / det, (a11 * r2 - a21 * r1) / det


def niveles_slider():
    """Todos los valores enteros de cada control distintos del base, uno por vez (shocks aislados)."""
    for var, rango in RANGOS_BIENES.items():
        for nivel in range(int(rango.minimo), int(rango.maximo) + 1):
            if nivel != getattr(BASE, var):
                yield var, nivel, BASE.con_cambios(**{var: F(nivel)})
    for nivel in range(int(RANGO_OFERTA_REAL.minimo), int(RANGO_OFERTA_REAL.maximo) + 1):
        if nivel != BASE.oferta_real:
            yield "M/P", nivel, BASE.con_cambios(M=F(nivel))


def esquinas_combinadas():
    """Combinaciones de mínimo, base y máximo de G, T e I0 (modo «Combinar shocks»)."""
    valores = {v: (int(r.minimo), int(getattr(BASE, v)), int(r.maximo)) for v, r in RANGOS_BIENES.items()}
    for G, T, I0 in itertools.product(valores["G"], valores["T"], valores["I0"]):
        yield {"G": G, "T": T, "I0": I0}


def signo(x) -> int:
    return (x > 0) - (x < 0)


# ============================================================================================
# A. MOTOR MATEMÁTICO
# ============================================================================================

@pytest.mark.parametrize("Y, T", [(0, 0), (50, 20), (100, 20), (150, 40), (F(900, 7), 0)])
def test_A1_funcion_de_consumo(Y, T):
    p = BASE.con_cambios(T=F(T))
    assert consumo(p, F(Y)) == 17 + F(3, 5) * (F(Y) - T)
    assert consumo(p, F(Y) + 1) - consumo(p, F(Y)) == p.c  # dC/dY = c
    assert consumo(p.con_cambios(T=p.T + 1), F(Y)) - consumo(p, F(Y)) == -p.c  # dC/dT = -c


@pytest.mark.parametrize("i", [0, 1, 5, F(50, 7), 10])
def test_A2_funcion_de_inversion(i):
    assert inversion(BASE, F(i)) == 35 - 4 * F(i)
    assert inversion(BASE, F(i) + 1) - inversion(BASE, F(i)) == -BASE.b  # dI/di = -b < 0
    assert inversion(BASE, 0) == BASE.I0


@pytest.mark.parametrize("cambios", list(esquinas_combinadas()))
def test_A3_curva_IS_cumple_el_equilibrio_de_bienes(cambios):
    p = BASE.con_cambios(**{k: F(v) for k, v in cambios.items()})
    IS = curva_is(p)
    assert IS.pendiente == -(1 - p.c) / p.b < 0
    for Y in (50, 75, 100, 125, 150):
        i = IS.tasa(F(Y))
        assert F(Y) == consumo(p, F(Y)) + inversion(p, i) + p.G  # Y = C + I + G en todo punto de la IS
        assert IS.producto(i) == Y


@pytest.mark.parametrize("mp", [5, 10, 20, 30, 60])
def test_A4_curva_LM_cumple_el_equilibrio_de_dinero(mp):
    p = BASE.con_cambios(M=F(mp))
    LM = curva_lm(p)
    assert LM.pendiente == p.k / p.h > 0
    for Y in (50, 75, 100, 125, 150):
        assert demanda_dinero(p, F(Y), LM.tasa(F(Y))) == p.oferta_real  # M/P = L en todo punto de la LM


def test_A5_solucion_simultanea_coincide_con_solver_independiente():
    casos = [p for _, _, p in niveles_slider()]
    casos += [BASE.con_cambios(**{k: F(v) for k, v in c.items()}) for c in esquinas_combinadas()]
    for p in casos:
        e = equilibrio(p)
        assert (e.Y, e.i) == cramer(p)
        assert curva_is(p).tasa(e.Y) == curva_lm(p).tasa(e.Y) == e.i  # intersección de IS y LM


def test_A6_multiplicadores_contra_diferencias_finitas_y_formulas_del_libro():
    Y0, i0 = cramer(BASE)
    def efecto(**cambio):
        Y1, i1 = cramer(BASE.con_cambios(**cambio))
        return Y1 - Y0, i1 - i0

    c, b, k, h = BASE.c, BASE.b, BASE.k, BASE.h
    m = multiplicadores(BASE)
    for var in ("G", "I0"):
        dY, di = efecto(**{var: getattr(BASE, var) + 1})
        assert (m[var].islm, m[var].tasa) == (dY, di)
        assert m[var].islm == 1 / (1 - c + b * k / h)            # p. 520: 1/(1 - C' + I'·L_Y/L_i)
        assert m[var].tasa == (k / h) * m[var].islm              # p. 521: dr/dG = -(L_Y/L_i)·dY/dG
        assert m[var].simple == 1 / (1 - c)                      # ec. 19.7 con τ = 0
    dY, di = efecto(T=BASE.T + 1)
    assert (m["T"].islm, m["T"].tasa, m["T"].simple) == (dY, di, -c / (1 - c))  # p. 504
    mm = multiplicador_monetario(BASE)
    dY, di = efecto(M=BASE.M + 1)
    assert (mm.producto, mm.tasa) == (dY, di)
    assert mm.producto == 1 / (k + h * (1 - c) / b)              # ec. 19.20, p. 518
    assert mm.tasa == (-1 / h) * (1 - k * mm.producto)           # p. 518
    # Valores calibrados aprobados.
    assert (m["G"].islm, m["T"].islm, mm.producto, mm.tasa) == (F(10, 7), F(-6, 7), F(5, 7), F(-1, 14))


@pytest.mark.parametrize("dG", range(1, 31))
def test_A7_crowding_out(dG):
    r = analizar_shock_bienes(BASE, VENTANA, G=BASE.G + dG)
    crowding = BASE.b * r.delta_i
    assert crowding > 0
    assert r.e0.I - r.e1.I == crowding                           # la inversión cae exactamente b·Δi
    assert r.desplazamiento_is - r.delta_Y == crowding / (1 - BASE.c)  # producto perdido = b·Δi/(1-c)
    assert 0 < r.delta_Y < r.desplazamiento_is                    # crowding out parcial
    assert resolver_escenario("A", BASE, VENTANA, TIPOS_SHOCK["G+"], F(dG)).crowding_out == crowding


def test_A8_demanda_y_oferta_de_dinero():
    assert demanda_dinero(BASE, F(101), F(5)) - demanda_dinero(BASE, F(100), F(5)) == BASE.k > 0   # L_Y > 0
    assert demanda_dinero(BASE, F(100), F(6)) - demanda_dinero(BASE, F(100), F(5)) == -BASE.h < 0  # L_i < 0
    for _, _, p in niveles_slider():
        e = equilibrio(p)
        assert e.oferta_real == p.M / p.P
        assert e.demanda_dinero == e.oferta_real


# ============================================================================================
# B. CALIBRACIÓN BASE
# ============================================================================================

def test_B_calibracion_base():
    e = equilibrio(BASE)
    assert (e.Y, e.i, e.C, e.I, e.G, e.T, e.oferta_real) == (100, 5, 65, 15, 20, 20, 20)
    assert e.C + e.I + e.G == e.Y
    assert demanda_dinero(BASE, e.Y, e.i) == BASE.M / BASE.P == 20
    assert e.Yd == 80 and (e.Yd - e.C) + (e.T - e.G) == e.I    # ahorro = inversión
    assert (curva_is(BASE).ordenada, curva_is(BASE).pendiente) == (15, F(-1, 10))
    assert (curva_lm(BASE).ordenada, curva_lm(BASE).pendiente) == (F(-5, 2), F(3, 40))
    assert gasto_autonomo(BASE) == 60
    assert equilibrio(PARAMETROS_BASE).Y == pytest.approx(100, abs=1e-12)
    assert equilibrio(PARAMETROS_BASE).i == pytest.approx(5, abs=1e-12)


# ============================================================================================
# C. SHOCKS
# ============================================================================================

# clave: (curva, dirección del desplazamiento, ΔY, Δi, ΔC, ΔI, crowding out)
ESPERADO = {
    "G+": ("IS", +1, +1, +1, +1, -1, True),
    "G-": ("IS", -1, -1, -1, -1, +1, False),
    "T+": ("IS", -1, -1, -1, -1, +1, False),
    "T-": ("IS", +1, +1, +1, +1, -1, True),
    "I0+": ("IS", +1, +1, +1, +1, +1, False),
    "I0-": ("IS", -1, -1, -1, -1, -1, False),
    "M+": ("LM", +1, +1, -1, +1, +1, False),
    "M-": ("LM", -1, -1, +1, -1, -1, False),
}


@pytest.mark.parametrize("clave", list(ESPERADO))
@pytest.mark.parametrize("magnitud", ["minima", 10, "maxima"])
def test_C_shocks(clave, magnitud):
    tipo = TIPOS_SHOCK[clave]
    if magnitud == "minima":
        m = F(1)
    elif magnitud == "maxima":
        m = F(magnitud_maxima(BASE, tipo))
    else:
        m = F(magnitud)
    curva, direccion, sY, si, sC, sI, crowding = ESPERADO[clave]
    r = resolver_escenario("A", BASE, VENTANA, tipo, m)
    is0, lm0 = curva_is(BASE), curva_lm(BASE)
    # Dirección de la curva desplazada (corrimiento horizontal a i = 5) y la otra sin cambios.
    if curva == "IS":
        assert signo(r.is1.producto(5) - is0.producto(5)) == direccion
        assert r.lm1 == lm0
    else:
        assert signo(r.lm1.producto(5) - lm0.producto(5)) == direccion
        assert r.is1 == is0
    assert r.is1.pendiente == is0.pendiente and r.lm1.pendiente == lm0.pendiente  # traslado paralelo
    # Signos de Y, i, C e I, verificados también con el solver independiente.
    Y1, i1 = cramer(r.p1)
    assert (r.e1.Y, r.e1.i) == (Y1, i1)
    assert (signo(r.delta_Y), signo(r.delta_i), signo(r.delta_C), signo(r.delta_I)) == (sY, si, sC, sI)
    # Crowding out: solo política fiscal expansiva, y en la magnitud b·Δi.
    assert (r.crowding_out is not None and r.crowding_out > 0) == crowding
    assert interpretar(BASE, r.p1).hay_crowding_out == crowding
    if crowding:
        assert r.crowding_out == BASE.b * r.delta_i


# ============================================================================================
# D. INTERFAZ
# ============================================================================================

def _app() -> AppTest:
    return AppTest.from_file(str(APP), default_timeout=30).run()


def _graficos(at: AppTest) -> list[dict]:
    return [json.loads(g.proto.spec) for g in at.get("plotly_chart")]


def _pestana(at: AppTest, etiqueta: str):
    return next(t for t in at.tabs if t.label == etiqueta)


@pytest.fixture(scope="module")
def app_con_shocks() -> AppTest:
    at = _app()
    at.slider(key="bienes_G").set_value(40).run()
    at.button(key="bienes_aplicar").click().run()
    at.slider(key="dinero_MP").set_value(30).run()
    at.button(key="dinero_aplicar").click().run()
    return at


def test_D1_ejes_y_escalas_fijas_en_todos_los_graficos(app_con_shocks):
    graficos = _graficos(app_con_shocks)
    assert len(graficos) == 4  # inicio, bienes, dinero y comparación
    for g in graficos:
        x, y = g["layout"]["xaxis"], g["layout"]["yaxis"]
        assert (x["range"], y["range"]) == ([50, 150], [0, 10])
        assert x["fixedrange"] and y["fixedrange"]
        assert x["title"]["text"] == "Producto, Y" and y["title"]["text"] == "Tasa de interés, i (%)"
        assert g["layout"]["showlegend"] is True
        assert all(t["type"] == "scatter" for t in g["data"])  # sin gráficos 3D


def test_D2_leyendas_y_prominencia(app_con_shocks):
    inicio, bienes, dinero, comparacion = _graficos(app_con_shocks)
    nombres = lambda g: [t["name"] for t in g["data"]]
    assert nombres(inicio) == ["IS₀ · mercado de bienes", "LM₀ · mercado de dinero", "E₀ · equilibrio"]
    assert nombres(bienes) == ["IS₀ · inicial", "IS₁ · tras el shock", "LM₀ · sin cambios", "E₀ · inicial",
                               "E₁ · nuevo equilibrio"]
    assert nombres(dinero) == ["IS₀ · sin cambios", "LM₀ · inicial", "LM₁ · tras el shock", "E₀ · inicial",
                               "E₁ · nuevo equilibrio"]
    assert "IS<sub>A</sub> · escenario A" in nombres(comparacion) and "LM<sub>B</sub> · escenario B" in nombres(comparacion)
    for g, original, nueva in ((bienes, 0, 1), (dinero, 1, 2)):
        o, n = g["data"][original], g["data"][nueva]
        assert o["line"]["dash"] == "dash" and o["opacity"] < 1 <= n.get("opacity", 1)
        assert o["line"]["width"] < n["line"]["width"]
        assert g["data"][3]["marker"]["size"] < g["data"][4]["marker"]["size"]  # E₁ destacado sobre E₀
    # Las curvas dibujadas son las del modelo: IS₁ en bienes con ΔG = +20 es i = 20 - 0,10·Y.
    is1 = bienes["data"][1]
    assert is1["x"] == [50, 150] and is1["y"] == pytest.approx([15, 5])


def test_D3_sliders_rangos_y_pasos():
    at = _app()
    esperado = {"bienes_G": (0, 50, 20), "bienes_T": (0, 40, 20), "bienes_I0": (15, 55, 35), "dinero_MP": (5, 60, 20)}
    for clave, (minimo, maximo, inicial) in esperado.items():
        s = at.slider(key=clave)
        assert (s.min, s.max, s.value, s.step) == (minimo, maximo, inicial, 1)
    for nombre in ("A", "B"):
        assert at.slider(key=f"comp_{nombre}_magnitud").min == 1


def test_D4_botones_aplicar_y_restablecer():
    at = _app()
    for clave in ("bienes", "dinero", "comp"):
        assert at.button(key=f"{clave}_aplicar").disabled          # sin cambios pendientes
        assert not at.button(key=f"{clave}_restablecer").disabled
    at.slider(key="bienes_T").set_value(0).run()
    assert not at.button(key="bienes_aplicar").disabled
    at.button(key="bienes_aplicar").click().run()
    assert _pestana(at, "Mercado de bienes").metric[0].value == "+17,14"
    at.button(key="bienes_restablecer").click().run()
    assert at.slider(key="bienes_T").value == 20 and not _pestana(at, "Mercado de bienes").metric
    at.slider(key="dinero_MP").set_value(5).run()
    at.button(key="dinero_aplicar").click().run()
    at.button(key="dinero_restablecer").click().run()
    assert at.slider(key="dinero_MP").value == 20 and not _pestana(at, "Mercado de dinero").metric
    at.selectbox(key="comp_A_tipo").set_value("T+").run()
    at.button(key="comp_aplicar").click().run()
    at.button(key="comp_restablecer").click().run()
    assert at.selectbox(key="comp_A_tipo").value == "G+" and at.button(key="comp_aplicar").disabled
    assert not at.exception


def test_D5_tablas(app_con_shocks):
    bienes = _pestana(app_con_shocks, "Mercado de bienes")
    tabla = bienes.dataframe[0].value
    assert list(tabla.columns) == ["Variable", "Escenario base", "Nuevo equilibrio", "Variación"]
    filas = dict(zip(tabla["Variable"], zip(tabla["Escenario base"], tabla["Nuevo equilibrio"], tabla["Variación"])))
    assert filas["Producto, Y"] == ("100", "128,57", "+28,57")
    assert filas["Tasa de interés, i (%)"] == ("5%", "7,14%", "+2,14 p.p.")
    assert filas["Gasto público, G"] == ("20", "40", "+20")
    assert filas["Demanda de dinero, L"] == ("20", "20", "0")
    comp = _pestana(app_con_shocks, "Comparar políticas").dataframe[0].value
    assert list(comp.columns) == ["Variable", "Base", "Escenario A", "Escenario B"]
    assert len(comp) == 17


# ============================================================================================
# E. CASOS LÍMITE
# ============================================================================================

def _finitos(*valores) -> bool:
    return all(math.isfinite(float(v)) for v in valores)


def test_E1_extremos_de_cada_slider_aislado():
    for var, rango in list(RANGOS_BIENES.items()) + [("M/P", RANGO_OFERTA_REAL)]:
        for nivel in (rango.minimo, rango.maximo):
            if var == "M/P":
                r = analizar_shock_dinero(BASE, VENTANA, F(nivel))
            else:
                r = analizar_shock_bienes(BASE, VENTANA, **{var: F(nivel)})
            e = r.e1
            assert _finitos(e.Y, e.i, e.C, e.I, e.demanda_dinero)
            assert r.fuera_de_rango == []                     # rangos aprobados: dentro del gráfico
            assert e.C > 0 and e.I > 0 and e.Yd > 0 and e.G >= 0 and e.T >= 0 and e.oferta_real > 0
            assert e.Yd - e.C >= 0                            # ahorro privado no negativo


def test_E2_todos_los_valores_de_los_sliders_sin_resultados_absurdos():
    for _, _, p in niveles_slider():
        e = equilibrio(p)
        texto = interpretar(BASE, p).texto
        assert 50 <= e.Y <= 150 and 0 <= e.i <= 10
        assert e.C > 0 and e.I > 0 and e.Yd > 0
        assert "nan" not in texto.lower() and "inf" not in texto.lower().replace("inflación", "")


@pytest.mark.parametrize("cambios", list(esquinas_combinadas()))
def test_E3_combinaciones_extremas_advierten_y_no_recortan(cambios):
    r = analizar_shock_bienes(BASE, VENTANA, **{k: F(v) for k, v in cambios.items()})
    Y, i = cramer(r.p1)
    assert (r.e1.Y, r.e1.i) == (Y, i)                         # sin recorte
    fuera = {f.variable for f in r.fuera_de_rango}
    assert ("Y" in fuera) == (not 50 <= Y <= 150)
    assert ("i" in fuera) == (not 0 <= i <= 10)
    assert ("I" in fuera) == (r.e1.I < 0)
    assert _finitos(r.e1.Y, r.e1.i, r.e1.C, r.e1.I)


def test_E4_inversion_negativa_dentro_de_la_ventana_se_advierte():
    # G = 50, T = 0, I0 = 15: Y e i quedan dentro del gráfico pero I < 0.
    r = analizar_shock_bienes(BASE, VENTANA, G=F(50), T=F(0), I0=F(15))
    assert 50 <= r.e1.Y <= 150 and 0 <= r.e1.i <= 10
    assert r.e1.I < 0 and [f.variable for f in r.fuera_de_rango] == ["I"]


def test_E5_advertencia_en_la_interfaz_con_valores_sin_recortar():
    at = _app()
    at.checkbox(key="bienes_combinar").check().run()
    for clave, valor in (("bienes_G", 50), ("bienes_T", 0), ("bienes_I0", 55)):
        at.slider(key=clave).set_value(valor).run()
    at.button(key="bienes_aplicar").click().run()
    aviso = _pestana(at, "Mercado de bienes").warning[0].value
    Y, i = cramer(BASE.con_cambios(G=F(50), T=F(0), I0=F(55)))
    assert f"Y₁ = {float(Y):.2f}".replace(".", ",") in aviso and "no se recortan" in aviso
    assert not at.exception


@pytest.mark.parametrize("a, b", list(itertools.product(TIPOS_SHOCK, repeat=2)))
def test_E6_comparacion_con_magnitudes_extremas(a, b):
    for ma, mb in ((1, 1), ("max", "max")):
        ma_ = magnitud_maxima(PARAMETROS_BASE, TIPOS_SHOCK[a]) if ma == "max" else ma
        mb_ = magnitud_maxima(PARAMETROS_BASE, TIPOS_SHOCK[b]) if mb == "max" else mb
        c = comparar(PARAMETROS_BASE, VENTANA, TIPOS_SHOCK[a], ma_, TIPOS_SHOCK[b], mb_)
        for r in (c.a, c.b):
            assert _finitos(r.e1.Y, r.e1.i, r.e1.C, r.e1.I, r.multiplicador)
            assert r.fuera_de_rango == []


def test_E7_sin_divisiones_por_cero():
    for invalido in ({"c": 1}, {"c": 0}, {"b": 0}, {"k": 0}, {"h": 0}, {"P": 0}):
        with pytest.raises(ValueError):
            BASE.con_cambios(**invalido)
    with pytest.raises(ValueError):
        analizar_shock_dinero(BASE, VENTANA, 0)
    with pytest.raises(ValueError):
        resolver_escenario("A", BASE, VENTANA, TIPOS_SHOCK["G+"], 0)
    D = BASE.h * (1 - BASE.c) + BASE.b * BASE.k
    assert D > 0 and curva_is(BASE).pendiente != 0 and curva_lm(BASE).pendiente != 0


# ============================================================================================
# F. CONSISTENCIA PEDAGÓGICA
# ============================================================================================

def _textos_de_todas_las_simulaciones() -> list[tuple[str, str]]:
    textos = []
    for var, nivel, p in niveles_slider():
        it = interpretar(BASE, p)
        textos.append((f"{var}={nivel}", it.texto + "\n" + "\n".join(it.pasos)))
    for a, b in itertools.product(TIPOS_SHOCK, repeat=2):
        c = comparar(PARAMETROS_BASE, VENTANA, TIPOS_SHOCK[a], 10, TIPOS_SHOCK[b], 10)
        textos.append((f"{a} vs {b}", "\n".join(c.interpretacion() + [v.texto for v in c.veredictos()])))
    return textos


TEXTOS = _textos_de_todas_las_simulaciones()


def test_F1_shock_de_inversion_nunca_es_politica_fiscal():
    for var, nivel, p in niveles_slider():
        if var != "I0":
            continue
        it = interpretar(BASE, p)
        r = analizar_shock_bienes(BASE, VENTANA, I0=F(nivel))
        assert [s.tipo for s in r.shocks] == ["inversion"]
        assert "política fiscal" not in (it.texto + " ".join(it.pasos)).lower()
        assert "shock privado" in it.texto and "no una política económica" in it.texto
    for clave in ("I0+", "I0-"):
        assert TIPOS_SHOCK[clave].categoria == "Shock privado"
        assert resolver_escenario("A", BASE, VENTANA, TIPOS_SHOCK[clave], F(10)).crowding_out is None


def test_F2_desplazamiento_frente_a_movimiento_a_lo_largo():
    for var, nivel, p in niveles_slider():
        it = interpretar(BASE, p)
        texto = it.texto + " ".join(it.pasos)
        movida, fija = ("LM", "IS") if var == "M/P" else ("IS", "LM")
        assert f"desplaza la curva {movida}" in texto
        assert f"**Desplazamiento de la {movida}.**" in texto
        assert f"**Movimiento a lo largo de {fija}₀.**" in texto
        assert f"La {fija} no se desplaza" in texto
        assert f"desplaza la curva {fija}" not in texto
        assert "se desplaza a lo largo" not in texto


# Δi seguido de un valor que no esté en puntos porcentuales (se excluye «b·Δi = b × …»).
VARIACION_SIN_PP = re.compile(r"(?<!·)Δi\s*[=:]\s*[+−-]?\d+(?:,\d+)?(?!,?\d*\s*p\.p\.)")
# Niveles de tasa expresados en puntos porcentuales.
NIVEL_EN_PP = re.compile(r"\bi[₀₁]?\s*[=:]\s*\d+(?:,\d+)?\s*p\.p\.|i:\s*\d+(?:,\d+)?\s*p\.p\.")


@pytest.mark.parametrize("nombre, texto", TEXTOS, ids=[n for n, _ in TEXTOS])
def test_F3_porcentaje_frente_a_punto_porcentual(nombre, texto):
    assert not VARIACION_SIN_PP.search(texto), VARIACION_SIN_PP.search(texto)
    assert not NIVEL_EN_PP.search(texto), NIVEL_EN_PP.search(texto)
    # Los niveles de i van con %: «i: 5% → 6,07%».
    for m in re.finditer(r"i: (\S+) → (\S+?)\)", texto):
        assert m.group(1).endswith("%") and m.group(2).endswith("%")


def test_F4_interfaz_tasa_frente_a_variacion(app_con_shocks):
    for etiqueta in ("Mercado de bienes", "Mercado de dinero"):
        pestana = _pestana(app_con_shocks, etiqueta)
        tarjetas = {m.label: m.value for m in pestana.metric}
        assert tarjetas["Δi · Tasa de interés"].endswith(" p.p.")      # variación: puntos porcentuales
        leyendas = [c.value for c in pestana.caption]
        assert any(re.fullmatch(r"i: 5% → \d+,\d+%", c) for c in leyendas)  # niveles: porcentaje
    inicio = {m.label: m.value for m in _pestana(app_con_shocks, "Inicio / Modelo base").metric}
    assert inicio["Tasa de interés, i₀"] == "5%"


# ============================================================================================
# G. REGRESIÓN DE LOS ERRORES ENCONTRADOS EN LA AUDITORÍA (modo «Combinar shocks»)
# ============================================================================================

def _aplicar_combinado(**niveles) -> AppTest:
    at = _app()
    at.checkbox(key="bienes_combinar").check().run()
    for var, valor in niveles.items():
        at.slider(key=f"bienes_{var}").set_value(valor).run()
    return at.button(key="bienes_aplicar").click().run()


def _expanders(at: AppTest) -> list[str]:
    return [e.label for e in _pestana(at, "Mercado de bienes").expander]


def test_G1_fiscal_contractiva_con_suba_de_I0_no_es_crowding_out():
    # G ↓ con I0 ↑: la tasa sube por el shock de inversión, no por la política fiscal.
    at = _aplicar_combinado(G=10, I0=55)
    contenido = "\n".join(m.value for m in _pestana(at, "Mercado de bienes").markdown)
    assert "Crowding out (efecto desplazamiento)" not in _expanders(at)
    assert "La política fiscal eleva la tasa" not in contenido


def test_G2_fiscal_expansiva_con_caida_de_I0_no_es_crowding_in():
    at = _aplicar_combinado(G=30, I0=15)
    contenido = "\n".join(m.value for m in _pestana(at, "Mercado de bienes").markdown)
    assert "Crowding in (efecto inverso al desplazamiento)" not in _expanders(at)
    assert "La política fiscal reduce la tasa" not in contenido


def test_G3_crowding_out_solo_atribuye_la_parte_fiscal():
    # G +10 e I0 +10: la política fiscal sube i en 15/14 p.p. → desplaza b·15/14 = 30/7 ≈ 4,29.
    p1 = BASE.con_cambios(G=F(30), I0=F(45))
    frases = [f for f in interpretar(BASE, p1).texto.split(". ") if "crowding out" in f]
    assert len(frases) == 1 and "4,29" in frases[0] and "8,57" not in frases[0]
    r = analizar_shock_bienes(BASE, VENTANA, G=F(30), I0=F(45))
    assert r.crowding_out == BASE.b * F(15, 14)
    leyendas = [c.value for c in _pestana(_aplicar_combinado(G=30, I0=45), "Mercado de bienes").caption]
    (crowding,) = [c for c in leyendas if "**Crowding out**" in c]
    assert crowding.endswith("reduce la inversión privada en 4,29.")


def test_G4_tasa_sin_cambio_no_se_describe_como_baja():
    # G −10 e I0 +10 se compensan: Δi = 0.
    texto = interpretar(BASE, BASE.con_cambios(G=F(10), I0=F(45))).texto
    assert "baja de la tasa" not in texto and "suba de la tasa" not in texto
    assert "la tasa de interés no cambia" in texto


def test_G5_producto_sin_cambio_no_se_describe_como_caida():
    at = _aplicar_combinado(G=10, I0=45)
    contenido = "\n".join(m.value for m in _pestana(at, "Mercado de bienes").markdown)
    assert "al bajar el producto" not in contenido and "al subir el producto" not in contenido
    assert "el producto no cambia" in contenido.lower()


def test_G6_unidad_de_di_dMP_en_puntos_porcentuales():
    at = _app()
    teoria = "\n".join(c.value for c in _pestana(at, "Marco teórico").caption)
    assert re.search(r"di/d\(M/P\) ≈ -0,071 p\.p\.", teoria)
    at.slider(key="dinero_MP").set_value(30).run()
    at.button(key="dinero_aplicar").click().run()
    leyendas = "\n".join(c.value for c in _pestana(at, "Mercado de dinero").caption)
    assert "Efecto sobre la tasa de interés (p.p. por unidad de M/P)" in leyendas
