"""Interfaz Streamlit del simulador IS-LM.

Este archivo solo arma la página: los cálculos viven en `islm/` y cada sección en `vistas/`.
"""

from __future__ import annotations

import streamlit as st

from islm.config import PARAMETROS_BASE, VENTANA
from islm.formatting import numero
from vistas import comparacion, escenario_base, marco_teorico, mercado_bienes, mercado_dinero, ui

st.set_page_config(page_title="Simulador IS-LM", page_icon=":material/show_chart:", layout="wide")
ui.estilos()

st.title("Simulador interactivo del modelo IS-LM")
st.caption(
    "Determinación conjunta del producto (Y) y la tasa de interés (i) en una economía cerrada con precios "
    "fijos. Aplicá shocks fiscales, monetarios o de inversión y observá cómo se desplazan las curvas."
)

tab_inicio, tab_bienes, tab_dinero, tab_comparar, tab_teoria = st.tabs(
    ["Inicio / Modelo base", "Mercado de bienes", "Mercado de dinero", "Comparar políticas", "Marco teórico"]
)

with tab_inicio:
    escenario_base.mostrar(PARAMETROS_BASE, VENTANA)

with tab_bienes:
    mercado_bienes.mostrar(PARAMETROS_BASE, VENTANA)

with tab_dinero:
    mercado_dinero.mostrar(PARAMETROS_BASE, VENTANA)

with tab_comparar:
    comparacion.mostrar(PARAMETROS_BASE, VENTANA)

with tab_teoria:
    marco_teorico.mostrar(PARAMETROS_BASE)

st.divider()
st.caption(
    f"Supuestos: economía cerrada, precios fijos (P = {numero(PARAMETROS_BASE.P)}), impuestos de suma fija y "
    "una única tasa de interés i, en puntos porcentuales. Ejes fijos: "
    f"{numero(VENTANA.y_min)} ≤ Y ≤ {numero(VENTANA.y_max)} y {numero(VENTANA.i_min)} ≤ i ≤ {numero(VENTANA.i_max)}. "
    "Fuente: De Gregorio, Macroeconomía, cap. 19."
)
