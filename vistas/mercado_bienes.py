"""Pestaña «Mercado de bienes»: shocks sobre G, T e I0 que desplazan la curva IS.

La vista solo presenta: los cálculos vienen de `islm.mercado_bienes`.
Los controles funcionan como borrador; el shock se calcula al presionar «Aplicar shock».
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
from islm.config import RANGOS_BIENES, Ventana
from islm.formatting import con_signo, numero, porcentaje, puntos_porcentuales, recta_is_tex, recta_lm_tex, tex
from islm.interpretacion import interpretar
from islm.mercado_bienes import NOMBRES, VARIABLES_BIENES, ResultadoShockBienes, analizar_shock_bienes
from islm.model import Parametros, residuos
from vistas import interpretacion as vista_interpretacion
from vistas import ui

TOLERANCIA = 1e-9
CLAVES = {var: f"bienes_{var}" for var in VARIABLES_BIENES}
CLAVE_COMBINAR = "bienes_combinar"
CLAVE_APLICADO = "bienes_aplicado"
SIMBOLO = {"G": "G", "T": "T", "I0": "I₀"}
SIMBOLO_TEX = {"G": "G", "T": "T", "I0": "I_0"}

AYUDA = """
**Mercado de bienes**

- Mové **G**, **T** o **I₀** y presioná **Aplicar shock**.
- Cada shock parte del escenario base: al mover un control, los otros vuelven a su valor inicial.
- Para acumular cambios en varias variables, activá **Combinar shocks**.
- La **IS** se desplaza; la **LM** no cambia y la economía se mueve a lo largo de ella.
- Los rangos de los controles garantizan que un shock aislado deje el equilibrio dentro del gráfico.
"""


# --- Estado: borrador (controles) y shock aplicado --------------------------------------

def _nivel_base(base: Parametros, var: str) -> int:
    return int(round(getattr(base, var)))


def _niveles_base(base: Parametros) -> dict[str, int]:
    return {var: _nivel_base(base, var) for var in VARIABLES_BIENES}


def _borrador() -> dict[str, int]:
    return {var: st.session_state[CLAVES[var]] for var in VARIABLES_BIENES}


def _inicializar(base: Parametros) -> None:
    for var, clave in CLAVES.items():
        st.session_state.setdefault(clave, _nivel_base(base, var))
    st.session_state.setdefault(CLAVE_COMBINAR, False)
    st.session_state.setdefault(CLAVE_APLICADO, _niveles_base(base))


def _aplicar() -> None:
    st.session_state[CLAVE_APLICADO] = _borrador()


def _restablecer(base: Parametros) -> None:
    for var, clave in CLAVES.items():
        st.session_state[clave] = _nivel_base(base, var)
    st.session_state[CLAVE_COMBINAR] = False
    st.session_state[CLAVE_APLICADO] = _niveles_base(base)


def _al_mover(var_movida: str, base: Parametros) -> None:
    """Sin combinación explícita, cada shock parte del escenario base: los demás vuelven a su nivel base."""
    if st.session_state[CLAVE_COMBINAR]:
        return
    for var, clave in CLAVES.items():
        if var != var_movida:
            st.session_state[clave] = _nivel_base(base, var)


def _al_cambiar_combinar(base: Parametros) -> None:
    if not st.session_state[CLAVE_COMBINAR]:
        for var, clave in CLAVES.items():
            st.session_state[clave] = _nivel_base(base, var)


def _controles(base: Parametros) -> None:
    with st.container(border=True):
        columnas = st.columns(3, gap="large")
        for col, var in zip(columnas, VARIABLES_BIENES):
            rango = RANGOS_BIENES[var]
            with col:
                st.slider(
                    f"{NOMBRES[var]}, {SIMBOLO[var]}",
                    min_value=int(rango.minimo),
                    max_value=int(rango.maximo),
                    step=int(rango.paso),
                    key=CLAVES[var],
                    on_change=_al_mover,
                    args=(var, base),
                    help=f"Rango permitido: {numero(rango.minimo)} a {numero(rango.maximo)}.",
                )
                ui.resumen_control(getattr(base, var), st.session_state[CLAVES[var]])
        st.checkbox(
            "Combinar shocks",
            key=CLAVE_COMBINAR,
            on_change=_al_cambiar_combinar,
            args=(base,),
            help="Permite acumular cambios en más de una variable. Desactivado, cada shock parte del escenario base.",
        )
        ui.botones_accion(
            "bienes",
            _aplicar,
            lambda: _restablecer(base),
            pendiente=_borrador() != st.session_state[CLAVE_APLICADO],
        )


# --- Bloques de resultados ----------------------------------------------------------------

def _grafico(r: ResultadoShockBienes, ventana: Ventana) -> None:
    if not r.hay_shock:
        curvas = [
            CurvaGrafico("IS₀", r.is0, COLOR_IS, leyenda="IS₀ · inicial"),
            CurvaGrafico("LM₀", r.lm, COLOR_LM, leyenda="LM₀ · inicial"),
        ]
        puntos = [PuntoGrafico("E₀", r.e0.Y, r.e0.i, leyenda="E₀ · equilibrio inicial")]
        st.plotly_chart(figura_islm(curvas, puntos, ventana), config={"displaylogo": False}, key="grafico_bienes")
        return

    # Cada IS se rotula del lado exterior: la que queda más a la izquierda, a su izquierda.
    is1_a_la_derecha = r.desplazamiento_is >= 0
    curvas = [
        CurvaGrafico("IS₀", r.is0, COLOR_IS, atenuada=True, etiqueta_lado_opuesto=is1_a_la_derecha,
                     leyenda="IS₀ · inicial"),
        CurvaGrafico("IS₁", r.is1, COLOR_IS, etiqueta_lado_opuesto=not is1_a_la_derecha,
                     leyenda="IS₁ · tras el shock"),
        CurvaGrafico("LM₀", r.lm, COLOR_LM, leyenda="LM₀ · sin cambios"),
    ]
    # Equilibrios cercanos: etiquetas a lados opuestos para que no se superpongan.
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
    flechas = []
    if abs(r.desplazamiento_is) > TOLERANCIA:
        flecha = flecha_entre_curvas(r.is0, r.is1, ventana, f"Desplazamiento de la IS: {con_signo(r.desplazamiento_is)}")
        if flecha:
            flechas.append(flecha)
    figura = figura_islm(curvas=curvas, puntos=puntos, ventana=ventana, flechas=flechas)
    st.plotly_chart(figura, config={"displaylogo": False}, key="grafico_bienes")


def _identificacion(r: ResultadoShockBienes) -> None:
    insignias = " ".join(
        f":{'blue' if s.tipo == 'fiscal' else 'violet'}-badge[{s.etiqueta}]" for s in r.shocks
    )
    cambios = " · ".join(
        f"{SIMBOLO[ef.variable]}: {numero(getattr(r.p0, ef.variable))} → {numero(getattr(r.p1, ef.variable))} "
        f"(Δ{SIMBOLO[ef.variable]} = {con_signo(ef.delta)})"
        for ef in r.efectos
    )
    st.markdown(f"{insignias} &nbsp; <small>{cambios}</small>", unsafe_allow_html=True)


def _tarjetas(r: ResultadoShockBienes) -> None:
    fila1, fila2 = st.columns(2), st.columns(2)
    ui.tarjeta_variacion(fila1[0], "Producto", "Y", r.e0.Y, r.e1.Y, "Variación del producto de equilibrio.")
    ui.tarjeta_variacion(fila1[1], "Tasa de interés", "i", r.e0.i, r.e1.i, "En puntos porcentuales (p.p.).", es_tasa=True)
    ui.tarjeta_variacion(fila2[0], "Consumo", "C", r.e0.C, r.e1.C, "ΔC = c·(ΔY − ΔT).")
    ui.tarjeta_variacion(fila2[1], "Inversión", "I", r.e0.I, r.e1.I, "ΔI = ΔI₀ − b·Δi.")
    if r.crowding_out is not None and r.crowding_out > TOLERANCIA:
        st.caption(
            f":material/south_east: **Crowding out**: la suba de la tasa causada por la política fiscal reduce "
            f"la inversión privada en {numero(r.crowding_out, 2)}."
        )


def _ecuaciones(r: ResultadoShockBienes) -> None:
    st.latex(rf"IS_0:\ {recta_is_tex(r.is0)}")
    st.latex(rf"IS_1:\ {recta_is_tex(r.is1)}")
    st.latex(rf"LM_0:\ {recta_lm_tex(r.lm)} \quad \text{{(sin cambios)}}")
    dA = r.delta_gasto_autonomo
    if abs(dA) <= TOLERANCIA:
        paso1 = "1. Los cambios se compensan y el gasto autónomo no varía: la IS no se desplaza."
    else:
        paso1 = (
            f"1. **Desplazamiento de la IS** hacia la {'derecha' if dA > 0 else 'izquierda'}: el gasto autónomo "
            f"Ā = C₀ − cT + I₀ + G cambia en {con_signo(dA)}. A tasa constante, el producto cambiaría "
            f"ΔĀ/(1 − c) = {con_signo(r.desplazamiento_is)}."
        )
    if abs(r.delta_Y) <= TOLERANCIA:
        paso2 = "2. El producto no cambia, así que la economía permanece en E₀ sobre la LM₀."
    else:
        sube = r.delta_Y > 0
        paso2 = (
            f"2. **Movimiento a lo largo de LM₀**: al {'subir' if sube else 'bajar'} el producto, "
            f"{'aumenta' if sube else 'disminuye'} la demanda de dinero y la tasa {'sube' if sube else 'baja'}."
        )
    paso3 = (
        f"3. **Nuevo equilibrio** E₁ = ({numero(r.e1.Y, 2)}; {porcentaje(r.e1.i)}): "
        f"ΔY = {con_signo(r.delta_Y)} y Δi = {puntos_porcentuales(r.delta_i)}"
    )
    st.markdown("\n".join([paso1, paso2, paso3]))


def _formulas_multiplicador(var: str, p: Parametros) -> tuple[str, str]:
    s = 1 - p.c
    D = p.h * s + p.b * p.k
    dx = rf"\Delta {SIMBOLO_TEX[var]}"
    if var == "T":
        simple = (
            rf"\frac{{\Delta Y}}{{{dx}}}\Big|_{{i\ \text{{constante}}}} = -\frac{{c}}{{1-c}}"
            rf"= -\frac{{{tex(p.c)}}}{{{tex(s)}}} = {tex(-p.c / s, 4)}"
        )
        islm = (
            rf"\frac{{\Delta Y}}{{{dx}}}\Big|_{{IS\text{{-}}LM}} = -\frac{{c\,h}}{{h(1-c) + b\,k}}"
            rf"= -\frac{{{tex(p.c * p.h)}}}{{{tex(D)}}} \approx {tex(-p.c * p.h / D, 4)}"
        )
    else:
        simple = (
            rf"\frac{{\Delta Y}}{{{dx}}}\Big|_{{i\ \text{{constante}}}} = \frac{{1}}{{1-c}}"
            rf"= \frac{{1}}{{{tex(s)}}} = {tex(1 / s, 4)}"
        )
        islm = (
            rf"\frac{{\Delta Y}}{{{dx}}}\Big|_{{IS\text{{-}}LM}} = \frac{{h}}{{h(1-c) + b\,k}}"
            rf"= \frac{{{tex(p.h)}}}{{{tex(p.h)} \cdot {tex(s)} + {tex(p.b)} \cdot {tex(p.k)}}}"
            rf"= \frac{{{tex(p.h)}}}{{{tex(D)}}} \approx {tex(p.h / D, 4)}"
        )
    return simple, islm


def _multiplicadores(r: ResultadoShockBienes) -> None:
    for ef in r.efectos:
        simple, islm = _formulas_multiplicador(ef.variable, r.p0)
        st.markdown(f"**{NOMBRES[ef.variable]}, {SIMBOLO[ef.variable]}**")
        izquierda, derecha = st.columns(2)
        with izquierda:
            st.caption("Multiplicador simple (tasa constante)")
            st.latex(simple)
        with derecha:
            st.caption("Efecto final en IS-LM (la tasa se ajusta)")
            st.latex(islm)
    filas = [
        {
            "Variable": SIMBOLO[ef.variable],
            "Δ": con_signo(ef.delta),
            "Multiplicador simple": numero(ef.multiplicador.simple, 4),
            "Desplazamiento de la IS": con_signo(ef.desplazamiento_is),
            "Multiplicador IS-LM": numero(ef.multiplicador.islm, 4),
            "Efecto final ΔY": con_signo(ef.efecto_Y),
            "Efecto sobre i (p.p.)": con_signo(ef.efecto_i),
        }
        for ef in r.efectos
    ]
    if len(r.efectos) > 1:
        filas.append(
            {
                "Variable": "Total", "Δ": "", "Multiplicador simple": "",
                "Desplazamiento de la IS": con_signo(r.desplazamiento_is), "Multiplicador IS-LM": "",
                "Efecto final ΔY": con_signo(r.delta_Y), "Efecto sobre i (p.p.)": con_signo(r.delta_i),
            }
        )
    st.dataframe(filas, hide_index=True, width="stretch", height="content")
    if abs(r.desplazamiento_is) > TOLERANCIA:
        st.markdown(
            f"El multiplicador simple supone la tasa constante y mide cuánto se desplaza la IS "
            f"({con_signo(r.desplazamiento_is)}). En IS-LM la tasa se ajusta y modifica la inversión, por lo "
            f"que el efecto final es {con_signo(r.delta_Y)}: la diferencia de "
            f"{numero(abs(r.producto_perdido_por_tasa), 2)} es el efecto de la tasa sobre la inversión."
        )
    st.caption("Fuente: De Gregorio, cap. 19, ec. 19.7 (p. 502), p. 504 y p. 520.")


def _solo_fiscal(r: ResultadoShockBienes):
    """El shock fiscal, si es el único presente (sin cambio de I0); si no, None."""
    fiscal = next((s for s in r.shocks if s.tipo == "fiscal"), None)
    return fiscal if fiscal is not None and not r.delta_I0 else None


def _titulo_inversion(r: ResultadoShockBienes) -> str:
    fiscal = _solo_fiscal(r)
    if fiscal and fiscal.signo > 0 and r.delta_i > 0:
        return "Crowding out (efecto desplazamiento)"
    if fiscal and fiscal.signo < 0 and r.delta_i < 0:
        return "Crowding in (efecto inverso al desplazamiento)"
    return "Efecto de la tasa de interés sobre la inversión"


def _inversion(r: ResultadoShockBienes) -> None:
    fiscal = _solo_fiscal(r)
    combinado = r.delta_I0 and any(s.tipo == "fiscal" for s in r.shocks)
    efecto_tasa = r.efecto_tasa_sobre_inversion
    if combinado:
        parte_fiscal = -r.p0.b * r.delta_i_fiscal
        texto = (
            f"La tasa pasa de {porcentaje(r.e0.i)} a {porcentaje(r.e1.i)} por la combinación de shocks. Del efecto "
            f"total de la tasa sobre la inversión ({con_signo(efecto_tasa)}), la política fiscal aporta "
            f"−b·Δi (parte fiscal) = {con_signo(parte_fiscal)}"
            + (" (crowding out)" if parte_fiscal < 0 else " (crowding in)" if parte_fiscal > 0 else "")
            + f" y el shock de inversión, {con_signo(efecto_tasa - parte_fiscal)}."
        )
    elif fiscal and r.delta_i > 0:
        texto = (
            f"La política fiscal eleva la tasa de {porcentaje(r.e0.i)} a {porcentaje(r.e1.i)}. Como I = I₀ − b·i, "
            f"la inversión privada cae en b·Δi = {numero(r.p0.b)} × {numero(r.delta_i, 4)} ≈ "
            f"{numero(abs(efecto_tasa), 2)}: la política fiscal expansiva desplaza parcialmente a la inversión privada "
            "(crowding out)."
        )
    elif fiscal:
        texto = (
            f"La política fiscal reduce la tasa de {porcentaje(r.e0.i)} a {porcentaje(r.e1.i)}; la inversión "
            f"privada aumenta en {numero(efecto_tasa, 2)} y amortigua la caída del producto."
        )
    elif r.delta_i > 0:
        texto = (
            f"La inversión autónoma sube {numero(r.delta_I0, 2)}, pero la suba de la tasa la reduce en "
            f"{numero(abs(efecto_tasa), 2)}: la inversión de equilibrio aumenta {numero(r.delta_I, 2)}. Es la "
            "propia inversión privada que se ajusta a la tasa."
        )
    else:
        texto = (
            f"La inversión autónoma cae {numero(abs(r.delta_I0), 2)}, pero la baja de la tasa la aumenta en "
            f"{numero(efecto_tasa, 2)}: la inversión de equilibrio cae {numero(abs(r.delta_I), 2)}."
        )
    st.latex(rf"\Delta I = I(E_1) - I(E_0) = {tex(r.e1.I, 2)} - {tex(r.e0.I, 2)} = {tex(r.delta_I, 2)}")
    st.latex(
        rf"\Delta I = \underbrace{{\Delta I_0}}_{{\text{{autónoma}}}} "
        rf"\underbrace{{-\ b\,\Delta i}}_{{\text{{efecto tasa}}}}"
        rf"= {tex(r.delta_I0, 2)} {'-' if efecto_tasa < 0 else '+'} {tex(abs(efecto_tasa), 2)}"
    )
    st.markdown(texto)


def _verificacion(r: ResultadoShockBienes) -> list[tuple[str, bool]]:
    res = residuos(r.e1)
    suma_efectos = sum(ef.efecto_Y for ef in r.efectos)
    return [
        (
            f"Mercado de bienes: C₁ + I₁ + G₁ = {numero(r.e1.C, 4)} + {numero(r.e1.I, 4)} + "
            f"{numero(r.e1.G, 4)} = {numero(r.e1.C + r.e1.I + r.e1.G, 4)} = Y₁",
            abs(res["mercado_bienes"]) < TOLERANCIA,
        ),
        (
            f"Mercado de dinero: L(Y₁, i₁) = {numero(r.e1.demanda_dinero, 4)} = M/P = {numero(r.e1.oferta_real, 4)}",
            abs(res["mercado_dinero"]) < TOLERANCIA,
        ),
        ("E₁ pertenece a IS₁", abs(r.is1.tasa(r.e1.Y) - r.e1.i) < TOLERANCIA),
        ("E₁ pertenece a LM₀ (la LM no cambió)", abs(r.lm.tasa(r.e1.Y) - r.e1.i) < TOLERANCIA),
        (
            f"Pendiente de la IS sin cambios: {numero(r.is0.pendiente, 4)} = {numero(r.is1.pendiente, 4)}",
            abs(r.is0.pendiente - r.is1.pendiente) < TOLERANCIA,
        ),
        (
            f"Suma de efectos por multiplicador = ΔY: {numero(suma_efectos, 4)} = {numero(r.delta_Y, 4)}",
            abs(suma_efectos - r.delta_Y) < TOLERANCIA,
        ),
    ]


# --- Vista ----------------------------------------------------------------------------------

def mostrar(base: Parametros, ventana: Ventana) -> None:
    ui.encabezado(
        "Mercado de bienes",
        "Shocks sobre G, T o I₀ desplazan la curva IS; la LM no cambia.",
        AYUDA,
    )
    _inicializar(base)
    _controles(base)
    r = analizar_shock_bienes(base, ventana, **st.session_state[CLAVE_APLICADO])

    if not r.hay_shock:
        st.info(
            "Elegí un valor en los controles y presioná **Aplicar shock**. Por ahora la economía está en "
            f"E₀ = ({numero(r.e0.Y)}; {porcentaje(r.e0.i)}).",
            icon=":material/touch_app:",
        )
        _grafico(r, ventana)
        return

    _identificacion(r)
    ui.advertencia_dominio(
        r.fuera_de_rango, "Reducí la magnitud del shock (o desactivá la combinación de shocks)."
    )

    col_grafico, col_resultados = st.columns([3, 2], gap="large")
    with col_grafico:
        _grafico(r, ventana)
    with col_resultados:
        _tarjetas(r)
        vista_interpretacion.mostrar(interpretar(r.p0, r.p1), encabezado=None, compacto=True)

    with st.expander("Tabla de resultados", icon=":material/table_chart:"):
        ui.tabla_comparativa(r.tabla)
    with st.expander("Multiplicadores", icon=":material/functions:"):
        _multiplicadores(r)
    if abs(r.delta_i) > TOLERANCIA:
        with st.expander(_titulo_inversion(r), icon=":material/trending_flat:"):
            _inversion(r)
    with st.expander("Ecuaciones y lectura del gráfico", icon=":material/show_chart:"):
        _ecuaciones(r)
    with st.expander("Verificación numérica", icon=":material/fact_check:"):
        st.markdown(ui.lista_verificacion(_verificacion(r)))
