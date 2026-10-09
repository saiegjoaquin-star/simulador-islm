"""Pestaña «Inicio / Modelo base»: equilibrio inicial, gráfico IS-LM y ecuaciones."""

from __future__ import annotations

import streamlit as st

from islm.charts import COLOR_IS, COLOR_LM, CurvaGrafico, PuntoGrafico, figura_islm
from islm.config import DESCRIPCION_PARAMETROS, Ventana
from islm.formatting import numero, porcentaje, recta_is_tex, recta_lm_tex, tex
from islm.model import Parametros, curva_is, curva_lm, equilibrio, gasto_autonomo, residuos
from vistas import ui

TOLERANCIA = 1e-9

AYUDA = """
**Cómo usar el simulador**

1. Esta pestaña muestra el **equilibrio inicial E₀**, punto de partida de todas las simulaciones.
2. En **Mercado de bienes** cambiá G, T o I₀ y presioná **Aplicar shock**: se desplaza la IS.
3. En **Mercado de dinero** cambiá M/P: se desplaza la LM.
4. En **Comparar políticas** enfrentá dos intervenciones desde el mismo E₀.
5. **Marco teórico** resume los conceptos y supuestos del modelo.
"""


def mostrar(p: Parametros, ventana: Ventana) -> None:
    e0 = equilibrio(p)
    is0, lm0 = curva_is(p), curva_lm(p)

    ui.encabezado(
        "Escenario base",
        "Economía cerrada con precios fijos. Este equilibrio es el punto de partida de todas las simulaciones.",
        AYUDA,
    )

    tarjetas = [
        ("Producto", "Y₀", numero(e0.Y), "Producto de equilibrio en E₀."),
        ("Tasa de interés", "i₀", porcentaje(e0.i), "Tasa que equilibra a la vez el mercado de bienes y el de dinero."),
        ("Consumo", "C", numero(e0.C), "C = C₀ + c(Y − T) evaluado en E₀."),
        ("Inversión", "I", numero(e0.I), "I = I₀ − b·i evaluado en E₀."),
        ("Gasto público", "G", numero(e0.G), "Variable exógena de política fiscal."),
    ]
    for col, (nombre, simbolo, texto, ayuda) in zip(st.columns(5), tarjetas):
        col.metric(f"{nombre}, {simbolo}", texto, help=ayuda, border=True)
    st.caption(
        f"Además: impuestos T = {numero(e0.T)} · oferta monetaria real M/P = {numero(e0.oferta_real)} · "
        f"C + I + G = {numero(e0.C)} + {numero(e0.I)} + {numero(e0.G)} = {numero(e0.Y)}"
    )

    col_grafico, col_ecuaciones = st.columns([2.2, 1], gap="large")
    with col_grafico:
        figura = figura_islm(
            curvas=[
                CurvaGrafico("IS₀", is0, COLOR_IS, leyenda="IS₀ · mercado de bienes"),
                CurvaGrafico("LM₀", lm0, COLOR_LM, leyenda="LM₀ · mercado de dinero"),
            ],
            puntos=[PuntoGrafico("E₀", e0.Y, e0.i, leyenda="E₀ · equilibrio")],
            ventana=ventana,
            alto=560,
        )
        st.plotly_chart(figura, config={"displaylogo": False}, key="grafico_base")

    with col_ecuaciones:
        with st.container(border=True):
            st.markdown("**Curva IS** · equilibrio del mercado de bienes")
            st.latex(rf"\boxed{{{recta_is_tex(is0)}}}")
            st.markdown("**Curva LM** · equilibrio del mercado de dinero")
            st.latex(rf"\boxed{{{recta_lm_tex(lm0)}}}")
            st.markdown("**Equilibrio** · intersección de IS₀ y LM₀")
            st.latex(rf"E_0 = (Y_0;\ i_0) = ({tex(e0.Y)};\ {tex(e0.i)}\%)")

        with st.expander("Funciones de comportamiento"):
            st.latex(rf"C = {tex(p.C0)} + {tex(p.c, min_dec=2)}\,(Y - {tex(p.T)})")
            st.latex(rf"I = {tex(p.I0)} - {tex(p.b)}\,i")
            st.latex(rf"L = {tex(p.k, min_dec=2)}\,Y - {tex(p.h)}\,i")

        with st.expander("Derivación de las curvas"):
            st.markdown("IS: $Y = C + I + G$")
            st.latex(
                rf"i = \frac{{C_0 - cT + I_0 + G}}{{b}} - \frac{{1-c}}{{b}}\,Y"
                rf"= \frac{{{tex(gasto_autonomo(p))}}}{{{tex(p.b)}}} - \frac{{{tex(1 - p.c)}}}{{{tex(p.b)}}}\,Y"
            )
            st.markdown("LM: $M/P = L$")
            st.latex(
                rf"i = \frac{{k}}{{h}}\,Y - \frac{{M/P}}{{h}}"
                rf"= \frac{{{tex(p.k, min_dec=2)}}}{{{tex(p.h)}}}\,Y - \frac{{{tex(p.oferta_real)}}}{{{tex(p.h)}}}"
            )

        with st.expander("Parámetros del escenario base"):
            st.dataframe(
                [
                    {"Parámetro": nombre, "Descripción": descripcion, "Valor": numero(getattr(p, nombre))}
                    for nombre, descripcion in DESCRIPCION_PARAMETROS.items()
                ],
                hide_index=True,
                width="stretch",
                height="content",
            )

        with st.expander("Verificación del equilibrio"):
            r = residuos(e0)
            st.markdown(
                ui.lista_verificacion(
                    [
                        (
                            f"Bienes: C + I + G = {numero(e0.C)} + {numero(e0.I)} + {numero(e0.G)} "
                            f"= {numero(e0.C + e0.I + e0.G)} = Y",
                            abs(r["mercado_bienes"]) < TOLERANCIA,
                        ),
                        (
                            f"Dinero: L = {numero(p.k)}·{numero(e0.Y)} − {numero(p.h)}·{numero(e0.i)} "
                            f"= {numero(e0.demanda_dinero)} = M/P",
                            abs(r["mercado_dinero"]) < TOLERANCIA,
                        ),
                    ]
                )
            )
