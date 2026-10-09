"""Pestaña «Mercado de dinero»: shocks sobre M/P que desplazan la curva LM.

La vista solo presenta: los cálculos vienen de `islm.mercado_dinero`.
El control funciona como borrador; el shock se calcula al presionar «Aplicar shock».
"""

from __future__ import annotations

import streamlit as st

from islm.charts import (
    COLOR_IS,
    COLOR_LM,
    COLOR_PUNTO_NUEVO,
    CurvaGrafico,
    PuntoGrafico,
    figura_islm,
    flecha_entre_curvas,
)
from islm.config import RANGO_OFERTA_REAL, Ventana
from islm.formatting import con_signo, numero, porcentaje, puntos_porcentuales, recta_is_tex, recta_lm_tex, tex
from islm.interpretacion import interpretar
from islm.mercado_dinero import ResultadoShockDinero, analizar_shock_dinero
from islm.model import Parametros, residuos
from vistas import interpretacion as vista_interpretacion
from vistas import ui

TOLERANCIA = 1e-9
CLAVE_MP = "dinero_MP"
CLAVE_APLICADO = "dinero_aplicado"

AYUDA = """
**Mercado de dinero**

- Elegí la oferta monetaria real **M/P** y presioná **Aplicar shock**.
- Con P fijo, cambiar M/P equivale a que el banco central cambie la oferta nominal M.
- La **LM** se desplaza; la **IS** no cambia y la economía se mueve a lo largo de ella.
- El shock parte siempre del escenario base y es independiente del mercado de bienes.
"""


# --- Estado: borrador (control) y shock aplicado -------------------------------------------

def _nivel_base(base: Parametros) -> int:
    return int(round(base.oferta_real))


def _inicializar(base: Parametros) -> None:
    st.session_state.setdefault(CLAVE_MP, _nivel_base(base))
    st.session_state.setdefault(CLAVE_APLICADO, _nivel_base(base))


def _aplicar() -> None:
    st.session_state[CLAVE_APLICADO] = st.session_state[CLAVE_MP]


def _restablecer(base: Parametros) -> None:
    st.session_state[CLAVE_MP] = _nivel_base(base)
    st.session_state[CLAVE_APLICADO] = _nivel_base(base)


def _controles(base: Parametros) -> None:
    with st.container(border=True):
        control, _ = st.columns([2, 1], gap="large")
        with control:
            st.slider(
                "Oferta monetaria real, M/P",
                min_value=int(RANGO_OFERTA_REAL.minimo),
                max_value=int(RANGO_OFERTA_REAL.maximo),
                step=int(RANGO_OFERTA_REAL.paso),
                key=CLAVE_MP,
                help=(
                    f"Rango permitido: {numero(RANGO_OFERTA_REAL.minimo)} a {numero(RANGO_OFERTA_REAL.maximo)}. "
                    f"Nivel de precios fijo: P = {numero(base.P)}."
                ),
            )
            ui.resumen_control(base.oferta_real, st.session_state[CLAVE_MP])
        ui.botones_accion(
            "dinero",
            _aplicar,
            lambda: _restablecer(base),
            pendiente=st.session_state[CLAVE_MP] != st.session_state[CLAVE_APLICADO],
        )


# --- Bloques de resultados --------------------------------------------------------------------

def _grafico(r: ResultadoShockDinero, ventana: Ventana) -> None:
    if not r.hay_shock:
        curvas = [
            CurvaGrafico("IS₀", r.is_, COLOR_IS, leyenda="IS₀ · inicial"),
            CurvaGrafico("LM₀", r.lm0, COLOR_LM, leyenda="LM₀ · inicial"),
        ]
        puntos = [PuntoGrafico("E₀", r.e0.Y, r.e0.i, leyenda="E₀ · equilibrio inicial")]
        st.plotly_chart(figura_islm(curvas, puntos, ventana), config={"displaylogo": False}, key="grafico_dinero")
        return

    # Cada LM se rotula del lado exterior: la que queda más a la izquierda, a su izquierda.
    lm1_a_la_derecha = r.delta_oferta_real > 0
    curvas = [
        CurvaGrafico("IS₀", r.is_, COLOR_IS, leyenda="IS₀ · sin cambios"),
        CurvaGrafico("LM₀", r.lm0, COLOR_LM, atenuada=True, etiqueta_lado_opuesto=lm1_a_la_derecha,
                     leyenda="LM₀ · inicial"),
        CurvaGrafico("LM₁", r.lm1, COLOR_LM, etiqueta_lado_opuesto=not lm1_a_la_derecha,
                     leyenda="LM₁ · tras el shock"),
    ]
    cercanos = abs(r.delta_Y) < 0.3 * (ventana.y_max - ventana.y_min) and abs(r.delta_i) < 0.08 * (
        ventana.i_max - ventana.i_min
    )
    lado_e1 = (r.e1.Y < r.e0.Y) if cercanos else None
    lado_e0 = (not lado_e1) if cercanos else None
    puntos = [
        PuntoGrafico("E₀", r.e0.Y, r.e0.i, etiqueta_izquierda=lado_e0, atenuado=True, leyenda="E₀ · inicial"),
        PuntoGrafico("E₁", r.e1.Y, r.e1.i, COLOR_PUNTO_NUEVO, etiqueta_izquierda=lado_e1,
                     leyenda="E₁ · nuevo equilibrio"),
    ]
    flecha = flecha_entre_curvas(
        r.lm0, r.lm1, ventana,
        f"Desplazamiento<br>de la LM: {con_signo(r.desplazamiento_lm_horizontal)}",
        altura=0.15,
    )
    figura = figura_islm(curvas=curvas, puntos=puntos, ventana=ventana, flechas=[flecha] if flecha else [])
    st.plotly_chart(figura, config={"displaylogo": False}, key="grafico_dinero")


def _identificacion(r: ResultadoShockDinero) -> None:
    st.markdown(
        f":green-badge[{r.politica.etiqueta}] &nbsp; <small>M/P: {numero(r.p0.oferta_real)} → "
        f"{numero(r.p1.oferta_real)} (Δ(M/P) = {con_signo(r.delta_oferta_real)}) · {r.politica.detalle}</small>",
        unsafe_allow_html=True,
    )


def _tarjetas(r: ResultadoShockDinero) -> None:
    fila1, fila2 = st.columns(2), st.columns(2)
    ui.tarjeta_variacion(fila1[0], "Producto", "Y", r.e0.Y, r.e1.Y, "Variación del producto de equilibrio.")
    ui.tarjeta_variacion(fila1[1], "Tasa de interés", "i", r.e0.i, r.e1.i, "En puntos porcentuales (p.p.).", es_tasa=True)
    ui.tarjeta_variacion(fila2[0], "Consumo", "C", r.e0.C, r.e1.C, "ΔC = c·ΔY (T no cambia).")
    ui.tarjeta_variacion(fila2[1], "Inversión", "I", r.e0.I, r.e1.I, "ΔI = −b·Δi (I₀ no cambia).")
    if r.delta_oferta_real > 0:
        cadena = "M/P ↑ → exceso de oferta de dinero → i ↓ → I ↑ → Y ↑"
    else:
        cadena = "M/P ↓ → exceso de demanda de dinero → i ↑ → I ↓ → Y ↓"
    st.markdown(f"**{cadena}**")
    st.caption(
        f"Oferta real M/P: {numero(r.e0.oferta_real)} → {numero(r.e1.oferta_real)} · "
        f"Demanda de dinero L: {numero(r.e0.demanda_dinero)} → {numero(r.e1.demanda_dinero, 2)}"
    )


def _ecuaciones(r: ResultadoShockDinero) -> None:
    st.latex(rf"IS_0:\ {recta_is_tex(r.is_)} \quad \text{{(sin cambios)}}")
    st.latex(rf"LM_0:\ {recta_lm_tex(r.lm0)}")
    st.latex(rf"LM_1:\ {recta_lm_tex(r.lm1)}")
    expansiva = r.delta_oferta_real > 0
    lado = "derecha (hacia abajo)" if expansiva else "izquierda (hacia arriba)"
    st.markdown(
        "\n".join(
            [
                f"1. **Desplazamiento de la LM** hacia la {lado}: a tasa constante, Δ(M/P)/k = "
                f"{con_signo(r.desplazamiento_lm_horizontal)}; a producto constante, −Δ(M/P)/h = "
                f"{puntos_porcentuales(r.desplazamiento_lm_vertical)}",
                f"2. **Movimiento a lo largo de IS₀**: la tasa {'baja' if expansiva else 'sube'}, la inversión "
                f"{'aumenta' if expansiva else 'disminuye'} y el producto {'crece' if expansiva else 'cae'}.",
                f"3. **Nuevo equilibrio** E₁ = ({numero(r.e1.Y, 2)}; {porcentaje(r.e1.i)}): "
                f"ΔY = {con_signo(r.delta_Y)} y Δi = {puntos_porcentuales(r.delta_i)}",
            ]
        )
    )


def _multiplicadores(r: ResultadoShockDinero) -> None:
    p = r.p0
    s = 1 - p.c
    D = p.h * s + p.b * p.k
    m = r.multiplicador
    izquierda, derecha = st.columns(2)
    with izquierda:
        st.caption("Efecto sobre el producto")
        st.latex(
            rf"\frac{{dY}}{{d(M/P)}} = \frac{{b}}{{h(1-c) + b\,k}}"
            rf"= \frac{{{tex(p.b)}}}{{{tex(p.h)} \cdot {tex(s)} + {tex(p.b)} \cdot {tex(p.k)}}}"
            rf"= \frac{{{tex(p.b)}}}{{{tex(D)}}} \approx {tex(m.producto, 4)}"
        )
    with derecha:
        st.caption("Efecto sobre la tasa de interés (p.p. por unidad de M/P)")
        st.latex(
            rf"\frac{{di}}{{d(M/P)}} = -\frac{{1-c}}{{h(1-c) + b\,k}}"
            rf"= -\frac{{{tex(s)}}}{{{tex(D)}}} \approx {tex(m.tasa, 4)}"
        )
    st.dataframe(
        [
            {
                "Δ(M/P)": con_signo(r.delta_oferta_real),
                "Desplazamiento horizontal de la LM, Δ(M/P)/k": con_signo(r.desplazamiento_lm_horizontal),
                "Efecto final ΔY": con_signo(r.delta_Y),
                "Desplazamiento vertical de la LM, −Δ(M/P)/h (p.p.)": con_signo(r.desplazamiento_lm_vertical),
                "Efecto final Δi (p.p.)": con_signo(r.delta_i),
            }
        ],
        hide_index=True,
        width="stretch",
    )
    expansiva = r.delta_oferta_real > 0
    st.markdown(
        f"El producto cambia {con_signo(r.delta_Y)}, menos que el desplazamiento horizontal de la LM "
        f"({con_signo(r.desplazamiento_lm_horizontal)}), y la tasa cambia {puntos_porcentuales(r.delta_i)}, menos "
        f"que el desplazamiento vertical ({puntos_porcentuales(r.desplazamiento_lm_vertical)}): al "
        f"{'subir' if expansiva else 'bajar'} el producto, la demanda de dinero por transacciones absorbe "
        "parte del cambio de la oferta. La economía se mueve a lo largo de la IS."
    )
    st.caption("Fuente: De Gregorio, cap. 19, ec. 19.20 y p. 518.")


def _inversion(r: ResultadoShockDinero) -> None:
    st.latex(rf"\Delta I = I(E_1) - I(E_0) = {tex(r.e1.I, 2)} - {tex(r.e0.I, 2)} = {tex(r.delta_I, 2)}")
    st.latex(
        rf"\Delta I = -\,b\,\Delta i = -{tex(r.p0.b)} \times ({tex(r.delta_i, 4)}) = {tex(r.delta_I, 2)}"
        rf"\qquad (\Delta I_0 = 0)"
    )
    if r.delta_oferta_real > 0:
        st.markdown(
            f"Todo el aumento de la inversión ({con_signo(r.delta_I)}) se explica por la baja de la tasa de "
            f"{porcentaje(r.e0.i)} a {porcentaje(r.e1.i)}. A diferencia de una política fiscal expansiva, que "
            "sube la tasa y desplaza inversión privada, la política monetaria expansiva la estimula."
        )
    else:
        st.markdown(
            f"Toda la caída de la inversión ({con_signo(r.delta_I)}) se explica por la suba de la tasa de "
            f"{porcentaje(r.e0.i)} a {porcentaje(r.e1.i)}, que encarece el financiamiento de la inversión."
        )


def _verificacion(r: ResultadoShockDinero) -> None:
    res = residuos(r.e1)
    controles = [
        (
            f"Mercado de bienes: C₁ + I₁ + G₁ = {numero(r.e1.C, 4)} + {numero(r.e1.I, 4)} + "
            f"{numero(r.e1.G, 4)} = {numero(r.e1.C + r.e1.I + r.e1.G, 4)} = Y₁",
            abs(res["mercado_bienes"]) < TOLERANCIA,
        ),
        (
            f"Mercado de dinero: L(Y₁, i₁) = {numero(r.e1.demanda_dinero, 4)} = M/P = {numero(r.e1.oferta_real, 4)}",
            abs(res["mercado_dinero"]) < TOLERANCIA,
        ),
        ("E₁ pertenece a IS₀ (la IS no cambió)", abs(r.is_.tasa(r.e1.Y) - r.e1.i) < TOLERANCIA),
        ("E₁ pertenece a LM₁", abs(r.lm1.tasa(r.e1.Y) - r.e1.i) < TOLERANCIA),
        (
            f"Pendiente de la LM sin cambios: {numero(r.lm0.pendiente, 4)} = {numero(r.lm1.pendiente, 4)}",
            abs(r.lm0.pendiente - r.lm1.pendiente) < TOLERANCIA,
        ),
        (
            f"Multiplicadores: {numero(r.multiplicador.producto, 4)} × {con_signo(r.delta_oferta_real)} = "
            f"{numero(r.delta_Y, 4)} = ΔY y {numero(r.multiplicador.tasa, 4)} × "
            f"{con_signo(r.delta_oferta_real)} = {numero(r.delta_i, 4)} = Δi",
            abs(r.multiplicador.producto * r.delta_oferta_real - r.delta_Y) < TOLERANCIA
            and abs(r.multiplicador.tasa * r.delta_oferta_real - r.delta_i) < TOLERANCIA,
        ),
    ]
    st.markdown("**Equilibrio**")
    st.markdown(ui.lista_verificacion(controles))
    st.markdown("**Signos económicos**")
    st.markdown(ui.lista_verificacion(r.controles_de_signo()))


# --- Vista ------------------------------------------------------------------------------------

def mostrar(base: Parametros, ventana: Ventana) -> None:
    ui.encabezado(
        "Mercado de dinero",
        "Un cambio en la oferta monetaria real M/P desplaza la curva LM; la IS no cambia.",
        AYUDA,
    )
    _inicializar(base)
    _controles(base)
    r = analizar_shock_dinero(base, ventana, st.session_state[CLAVE_APLICADO])

    if not r.hay_shock:
        st.info(
            "Elegí un valor de M/P y presioná **Aplicar shock**. Por ahora la economía está en "
            f"E₀ = ({numero(r.e0.Y)}; {porcentaje(r.e0.i)}).",
            icon=":material/touch_app:",
        )
        _grafico(r, ventana)
        return

    _identificacion(r)
    ui.advertencia_dominio(r.fuera_de_rango, "Reducí la magnitud del cambio de M/P.")

    col_grafico, col_resultados = st.columns([3, 2], gap="large")
    with col_grafico:
        _grafico(r, ventana)
    with col_resultados:
        _tarjetas(r)
        vista_interpretacion.mostrar(interpretar(r.p0, r.p1), encabezado=None, compacto=True)

    with st.expander("Tabla de resultados", icon=":material/table_chart:"):
        ui.tabla_comparativa(r.tabla)
    with st.expander("Multiplicadores de la política monetaria", icon=":material/functions:"):
        _multiplicadores(r)
    with st.expander("Cambio de la inversión por el movimiento de la tasa", icon=":material/trending_flat:"):
        _inversion(r)
    with st.expander("Ecuaciones y lectura del gráfico", icon=":material/show_chart:"):
        _ecuaciones(r)
    with st.expander("Verificación numérica y de signos", icon=":material/fact_check:"):
        _verificacion(r)
