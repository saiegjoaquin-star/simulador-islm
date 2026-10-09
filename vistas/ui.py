"""Componentes visuales comunes a todas las pestañas (solo presentación)."""

from __future__ import annotations

from typing import Callable

import streamlit as st

from islm.formatting import con_signo, numero, porcentaje, puntos_porcentuales
from islm.shocks import FilaComparacion, FueraDeRango

# Ajustes mínimos: menos espacio vacío arriba (notebooks) y cifras de tarjetas más compactas.
_CSS = """
<style>
[data-testid="stMainBlockContainer"] { padding-top: 1.4rem; padding-bottom: 2.5rem; max-width: 1440px; }
[data-testid="stMetricValue"] { font-size: 1.7rem; }
[data-testid="stMetricLabel"] p { font-size: 0.88rem; }
[data-testid="stExpander"] summary p { font-size: 0.95rem; }
</style>
"""


def estilos() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def encabezado(titulo: str, bajada: str, ayuda: str | None = None) -> None:
    izquierda, derecha = st.columns([6, 1], vertical_alignment="bottom")
    with izquierda:
        st.header(titulo)
        st.caption(bajada)
    if ayuda:
        with derecha.popover("Cómo usar", icon=":material/help:", width="stretch"):
            st.markdown(ayuda)


def valor(x: float, es_tasa: bool = False, decimales: int = 2) -> str:
    return porcentaje(x) if es_tasa else numero(x, decimales)


def variacion(x: float, es_tasa: bool = False) -> str:
    return puntos_porcentuales(x) if es_tasa else con_signo(x)


def resumen_control(base: float, nuevo: float) -> None:
    """Línea bajo un control: valor base, nuevo valor y variación."""
    st.markdown(
        f"<small>Base&nbsp;**{numero(base)}** &nbsp;·&nbsp; Nuevo&nbsp;**{numero(nuevo)}** "
        f"&nbsp;·&nbsp; Δ&nbsp;**{con_signo(nuevo - base)}**</small>",
        unsafe_allow_html=True,
    )


def tarjeta_variacion(
    contenedor, titulo: str, simbolo: str, v0: float, v1: float, ayuda: str, es_tasa: bool = False
) -> None:
    contenedor.metric(f"Δ{simbolo} · {titulo}", variacion(v1 - v0, es_tasa), help=ayuda, border=True)
    contenedor.caption(f"{simbolo}: {valor(v0, es_tasa)} → {valor(v1, es_tasa)}")


def botones_accion(
    clave: str,
    al_aplicar: Callable[[], None],
    al_restablecer: Callable[[], None],
    pendiente: bool,
    texto_aplicar: str = "Aplicar shock",
) -> None:
    """Botones «Restablecer» y «Aplicar …», con aviso de cambios pendientes."""
    aviso, restablecer, aplicar = st.columns([3, 1.2, 1.2], vertical_alignment="center")
    with aviso:
        if pendiente:
            st.badge("Cambios sin aplicar", icon=":material/pending:", color="orange")
    restablecer.button(
        "Restablecer",
        key=f"{clave}_restablecer",
        on_click=al_restablecer,
        icon=":material/restart_alt:",
        width="stretch",
        help="Vuelve al escenario base: Y = 100 e i = 5%.",
    )
    aplicar.button(
        texto_aplicar,
        key=f"{clave}_aplicar",
        on_click=al_aplicar,
        type="primary",
        icon=":material/play_arrow:",
        width="stretch",
        disabled=not pendiente,
    )


def tabla_comparativa(filas: list[FilaComparacion]) -> None:
    st.dataframe(
        [
            {
                "Variable": f.variable,
                "Escenario base": valor(f.base, f.es_tasa),
                "Nuevo equilibrio": valor(f.nuevo, f.es_tasa),
                "Variación": variacion(f.variacion, f.es_tasa),
            }
            for f in filas
        ],
        hide_index=True,
        width="stretch",
        height="content",
    )
    st.caption(
        "C e I son el consumo y la inversión de equilibrio; C₀ e I₀ son sus componentes autónomos."
    )


def advertencia_dominio(problemas: list[FueraDeRango], sugerencia: str) -> None:
    if not problemas:
        return
    nombres = {"Y": "Y₁", "i": "i₁", "C": "C₁", "I": "I₁"}
    lineas = []
    for f in problemas:
        texto = valor(f.valor, f.variable == "i")
        if f.maximo is None:
            lineas.append(f"- {nombres[f.variable]} = {texto}: debe ser mayor o igual que {numero(f.minimo)}.")
        else:
            limites = (
                f"{porcentaje(f.minimo)} y {porcentaje(f.maximo)}"
                if f.variable == "i"
                else f"{numero(f.minimo)} y {numero(f.maximo)}"
            )
            lineas.append(f"- {nombres[f.variable]} = {texto}: fuera del rango admitido, entre {limites}.")
    st.warning(
        "**El nuevo equilibrio queda fuera del dominio permitido.**\n\n"
        + "\n".join(lineas)
        + f"\n\nLos valores no se recortan: son el resultado exacto de las ecuaciones. {sugerencia}",
        icon=":material/warning:",
    )


def lista_verificacion(controles: list[tuple[str, bool]]) -> str:
    return "\n".join(f"- {texto} {'✓' if ok else '✗'}" for texto, ok in controles)
