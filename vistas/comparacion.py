"""Pestaña «Comparar políticas»: dos escenarios (A y B) desde el mismo equilibrio base.

La vista solo presenta: los cálculos vienen de `islm.comparacion`.
Los controles funcionan como borrador; los escenarios se calculan al presionar «Aplicar escenarios».
"""

from __future__ import annotations

import streamlit as st

from islm.charts import (
    COLOR_ESCENARIO_A,
    COLOR_ESCENARIO_B,
    COLOR_IS,
    COLOR_LM,
    CurvaGrafico,
    PuntoGrafico,
    figura_islm,
    ubicar_etiquetas_de_curvas,
)
from islm.comparacion import TIPOS_SHOCK, Comparacion, ResultadoEscenario, comparar, magnitud_maxima
from islm.config import Ventana
from islm.formatting import con_signo, numero, porcentaje, puntos_porcentuales
from islm.interpretacion import interpretar
from islm.model import Parametros, residuos
from vistas import interpretacion as vista_interpretacion
from vistas import ui

TOLERANCIA = 1e-9
COLORES = {"A": COLOR_ESCENARIO_A, "B": COLOR_ESCENARIO_B}
INSIGNIA = {"A": "violet", "B": "green"}
VALORES_INICIALES = {"A": ("G+", 10), "B": ("M+", 10)}
ORDEN_TIPOS = ["G+", "G-", "T+", "T-", "M+", "M-", "I0+", "I0-"]
VISTAS = ["A y B", "Solo A", "Solo B"]
CLAVE_APLICADO = "comp_aplicado"

AYUDA = """
**Comparar políticas**

- Elegí el tipo de shock y su magnitud para los escenarios **A** y **B**, y presioná **Aplicar escenarios**.
- Ambos parten del **mismo equilibrio base** y se calculan por separado: no se suman.
- Tipos de intervención: **política fiscal** (G o T), **política monetaria** (M/P) y **shock privado** (I₀).
- La comparación describe efectos dentro del modelo; no indica qué intervención es preferible.
"""


def _clave(escenario: str, campo: str) -> str:
    return f"comp_{escenario}_{campo}"


# --- Estado: borrador (controles) y escenarios aplicados ----------------------------------

def _borrador() -> dict[str, tuple[str, int]]:
    return {n: (st.session_state[_clave(n, "tipo")], st.session_state[_clave(n, "magnitud")]) for n in ("A", "B")}


def _inicializar() -> None:
    for nombre, (tipo, magnitud) in VALORES_INICIALES.items():
        st.session_state.setdefault(_clave(nombre, "tipo"), tipo)
        st.session_state.setdefault(_clave(nombre, "magnitud"), magnitud)
    st.session_state.setdefault("comp_vista", VISTAS[0])
    st.session_state.setdefault(CLAVE_APLICADO, dict(VALORES_INICIALES))


def _aplicar() -> None:
    st.session_state[CLAVE_APLICADO] = _borrador()


def _restablecer() -> None:
    for nombre, (tipo, magnitud) in VALORES_INICIALES.items():
        st.session_state[_clave(nombre, "tipo")] = tipo
        st.session_state[_clave(nombre, "magnitud")] = magnitud
    st.session_state["comp_vista"] = VISTAS[0]
    st.session_state[CLAVE_APLICADO] = dict(VALORES_INICIALES)


def _al_cambiar_tipo(nombre: str, base: Parametros) -> None:
    """Ajusta la magnitud si supera el máximo permitido para el nuevo tipo de shock."""
    tipo = TIPOS_SHOCK[st.session_state[_clave(nombre, "tipo")]]
    maximo = int(magnitud_maxima(base, tipo))
    clave = _clave(nombre, "magnitud")
    st.session_state[clave] = max(1, min(st.session_state[clave], maximo))


def _formato_tipo(clave: str) -> str:
    tipo = TIPOS_SHOCK[clave]
    return f"{tipo.categoria} · {tipo.descripcion}"


def _control_escenario(nombre: str, base: Parametros) -> None:
    with st.container(border=True):
        st.markdown(f":{INSIGNIA[nombre]}-badge[Escenario {nombre}]")
        st.selectbox(
            "Tipo de shock",
            options=ORDEN_TIPOS,
            format_func=_formato_tipo,
            key=_clave(nombre, "tipo"),
            on_change=_al_cambiar_tipo,
            args=(nombre, base),
        )
        tipo = TIPOS_SHOCK[st.session_state[_clave(nombre, "tipo")]]
        maximo = int(magnitud_maxima(base, tipo))
        st.slider(
            "Magnitud del shock",
            min_value=1,
            max_value=maximo,
            step=1,
            key=_clave(nombre, "magnitud"),
            help=f"Máximo {maximo}: mantiene {tipo.variable} dentro del rango permitido.",
        )
        magnitud = st.session_state[_clave(nombre, "magnitud")]
        inicial = base.oferta_real if tipo.variable == "M/P" else getattr(base, tipo.variable)
        ui.resumen_control(inicial, inicial + tipo.direccion * magnitud)
        st.caption(f"{tipo.clasificacion} · desplaza la {tipo.curva}")


def _controles(base: Parametros) -> None:
    columnas = st.columns(2, gap="medium")
    for col, nombre in zip(columnas, ("A", "B")):
        with col:
            _control_escenario(nombre, base)
    ui.botones_accion(
        "comp",
        _aplicar,
        _restablecer,
        pendiente=_borrador() != st.session_state[CLAVE_APLICADO],
        texto_aplicar="Aplicar escenarios",
    )


# --- Gráfico --------------------------------------------------------------------------------

def _sub(nombre: str) -> str:
    return f"<sub>{nombre}</sub>"


def _nombre_curva(r: ResultadoEscenario) -> str:
    return f"{r.tipo.curva}{_sub(r.nombre)}"


def _recta(r: ResultadoEscenario):
    return r.is1 if r.tipo.curva == "IS" else r.lm1


def _misma_curva(a: ResultadoEscenario, b: ResultadoEscenario) -> bool:
    ra, rb = _recta(a), _recta(b)
    return (
        a.tipo.curva == b.tipo.curva
        and abs(ra.ordenada - rb.ordenada) < TOLERANCIA
        and abs(ra.pendiente - rb.pendiente) < TOLERANCIA
    )


def _mismo_punto(a: ResultadoEscenario, b: ResultadoEscenario) -> bool:
    return abs(a.e1.Y - b.e1.Y) < TOLERANCIA and abs(a.e1.i - b.e1.i) < TOLERANCIA


def _puntos(c: Comparacion, escenarios: list[ResultadoEscenario]) -> list[PuntoGrafico]:
    e0 = c.e0
    # E0 rotulado del lado opuesto a hacia donde se mueven los escenarios.
    a_la_derecha = [r.e1.Y >= e0.Y for r in escenarios]
    lado_e0 = True if all(a_la_derecha) else (False if not any(a_la_derecha) else None)
    puntos = [PuntoGrafico("E₀", e0.Y, e0.i, etiqueta_izquierda=lado_e0, atenuado=True, leyenda="E₀ · base")]

    if len(escenarios) == 2 and _mismo_punto(escenarios[0], escenarios[1]):
        r = escenarios[0]
        puntos.append(PuntoGrafico(f"E{_sub('A')} = E{_sub('B')}", r.e1.Y, r.e1.i, COLORES["A"]))
        return puntos

    ordenados = sorted(escenarios, key=lambda r: r.e1.i, reverse=True)
    for k, r in enumerate(ordenados):
        vertical = "centro" if len(ordenados) == 1 else ("arriba" if k == 0 else "abajo")
        puntos.append(
            PuntoGrafico(
                f"E{_sub(r.nombre)}", r.e1.Y, r.e1.i, COLORES[r.nombre], etiqueta_vertical=vertical,
                leyenda=f"E{_sub(r.nombre)} · escenario {r.nombre}",
            )
        )
    return puntos


def _grafico(c: Comparacion, ventana: Ventana, vista: str) -> None:
    nombres = {"A y B": ["A", "B"], "Solo A": ["A"], "Solo B": ["B"]}[vista]
    escenarios = [c.escenario(n) for n in nombres]

    # Curvas base atenuadas; cada escenario aporta solo la curva que desplaza, en su color.
    curvas = [
        CurvaGrafico("IS₀", c.is0, COLOR_IS, atenuada=True, leyenda="IS₀ · base"),
        CurvaGrafico("LM₀", c.lm0, COLOR_LM, atenuada=True, leyenda="LM₀ · base"),
    ]
    if len(escenarios) == 2 and _misma_curva(*escenarios):
        a, b = escenarios
        # Misma curva en A y B: B va punteada encima y una sola etiqueta nombra a las dos.
        curvas += [
            CurvaGrafico(f"{_nombre_curva(a)} = {_nombre_curva(b)}", _recta(a), COLORES["A"], posicion_etiqueta=0.75),
            CurvaGrafico(_nombre_curva(b), _recta(b), COLORES["B"], punteada=True, rotular=False),
        ]
    else:
        for posicion, r in zip((0.75, 0.6), escenarios):
            curvas.append(
                CurvaGrafico(_nombre_curva(r), _recta(r), COLORES[r.nombre], posicion_etiqueta=posicion,
                             leyenda=f"{_nombre_curva(r)} · escenario {r.nombre}")
            )

    puntos = _puntos(c, escenarios)
    # IS₀ y LM₀ mantienen su posición habitual; las curvas de A y B buscan lugar libre.
    curvas = ubicar_etiquetas_de_curvas(curvas, puntos, ventana, fijas=2)
    figura = figura_islm(curvas=curvas, puntos=puntos, ventana=ventana)
    st.plotly_chart(figura, config={"displaylogo": False}, key="grafico_comparacion")


# --- Resultados ----------------------------------------------------------------------------

def _tarjetas(c: Comparacion) -> None:
    bloques = [
        ("Producto", "Y", lambda r: (r.e0.Y, r.e1.Y), False),
        ("Tasa de interés", "i", lambda r: (r.e0.i, r.e1.i), True),
        ("Consumo", "C", lambda r: (r.e0.C, r.e1.C), False),
        ("Inversión", "I", lambda r: (r.e0.I, r.e1.I), False),
    ]
    for col, (titulo, simbolo, niveles, es_tasa) in zip(st.columns(4), bloques):
        with col.container(border=True):
            st.markdown(f"**Δ{simbolo}** · {titulo}")
            for sub, r in zip(st.columns(2), (c.a, c.b)):
                v0, v1 = niveles(r)
                sub.metric(f"Escenario {r.nombre}", ui.variacion(v1 - v0, es_tasa))
                sub.caption(f"{ui.valor(v0, es_tasa)} → {ui.valor(v1, es_tasa)}")


def _veredictos(c: Comparacion) -> None:
    st.markdown("**¿Qué escenario genera…?**")
    for v in c.veredictos():
        if v.ganador in ("A", "B"):
            insignia = f":{INSIGNIA[v.ganador]}-badge[Escenario {v.ganador}]"
        elif v.ganador is None:
            insignia = ":gray-badge[Empate]"
        else:
            insignia = ":gray-badge[No aplica]"
        with st.container(border=True):
            st.markdown(f"**{v.criterio}** &nbsp; {insignia}", unsafe_allow_html=True)
            st.caption(v.texto)


def _tabla(c: Comparacion) -> None:
    a, b, e0 = c.a, c.b, c.e0

    def nivel(r: ResultadoEscenario) -> str:
        return f"{r.tipo.simbolo}: {numero(r.nivel_inicial)} → {numero(r.nivel_final)}"

    def crowding(r: ResultadoEscenario) -> str:
        return "No aplica" if r.crowding_out is None else numero(r.crowding_out, 2)

    filas = [
        ("Tipo de intervención", "—", a.tipo.categoria, b.tipo.categoria),
        ("Clasificación", "—", a.tipo.clasificacion, b.tipo.clasificacion),
        ("Variable modificada", "—", nivel(a), nivel(b)),
        ("Curva que se desplaza (horizontal)", "—",
         f"{a.tipo.curva}: {con_signo(a.desplazamiento)}", f"{b.tipo.curva}: {con_signo(b.desplazamiento)}"),
        ("Producto, Y", numero(e0.Y, 2), numero(a.e1.Y, 2), numero(b.e1.Y, 2)),
        ("ΔY", "—", con_signo(a.delta_Y), con_signo(b.delta_Y)),
        ("Tasa de interés, i", porcentaje(e0.i), porcentaje(a.e1.i), porcentaje(b.e1.i)),
        ("Δi", "—", puntos_porcentuales(a.delta_i), puntos_porcentuales(b.delta_i)),
        ("Consumo de equilibrio, C", numero(e0.C, 2), numero(a.e1.C, 2), numero(b.e1.C, 2)),
        ("Inversión de equilibrio, I", numero(e0.I, 2), numero(a.e1.I, 2), numero(b.e1.I, 2)),
        ("ΔI", "—", con_signo(a.delta_I), con_signo(b.delta_I)),
        ("Efecto de la tasa sobre I (−b·Δi)", "—",
         con_signo(a.efecto_tasa_sobre_inversion), con_signo(b.efecto_tasa_sobre_inversion)),
        ("Crowding out", "—", crowding(a), crowding(b)),
        ("Gasto público, G", numero(e0.G), numero(a.e1.G), numero(b.e1.G)),
        ("Impuestos, T", numero(e0.T), numero(a.e1.T), numero(b.e1.T)),
        ("Inversión autónoma, I₀", numero(c.base.I0), numero(a.p1.I0), numero(b.p1.I0)),
        ("Oferta monetaria real, M/P", numero(e0.oferta_real), numero(a.e1.oferta_real), numero(b.e1.oferta_real)),
    ]
    st.dataframe(
        [{"Variable": v, "Base": base, "Escenario A": va, "Escenario B": vb} for v, base, va, vb in filas],
        hide_index=True,
        width="stretch",
        height="content",
    )
    st.caption(
        "Crowding out: inversión privada desplazada por la suba de la tasa ante una política fiscal "
        "expansiva. En los demás casos, el efecto de la tasa sobre la inversión figura en la fila −b·Δi."
    )


def _advertencias(c: Comparacion) -> None:
    for r in (c.a, c.b):
        ui.advertencia_dominio(r.fuera_de_rango, f"Reducí la magnitud del shock del escenario {r.nombre}.")


def _verificacion(c: Comparacion) -> None:
    lineas = []
    for r in (c.a, c.b):
        res = residuos(r.e1)
        lineas.append(f"**Escenario {r.nombre}**")
        lineas.append(
            ui.lista_verificacion(
                [
                    (f"Parte de E₀ = ({numero(r.e0.Y)}; {porcentaje(r.e0.i)})", r.e0 == c.e0),
                    ("Mercado de bienes: C + I + G = Y", abs(res["mercado_bienes"]) < TOLERANCIA),
                    ("Mercado de dinero: L = M/P", abs(res["mercado_dinero"]) < TOLERANCIA),
                    *r.controles_de_signo(),
                ]
            )
        )
    st.markdown("\n".join(lineas))


# --- Vista ------------------------------------------------------------------------------------

def mostrar(base: Parametros, ventana: Ventana) -> None:
    ui.encabezado(
        "Comparar políticas",
        "Dos intervenciones evaluadas por separado desde el mismo equilibrio base.",
        AYUDA,
    )
    _inicializar()
    _controles(base)

    aplicado = st.session_state[CLAVE_APLICADO]
    (tipo_a, mag_a), (tipo_b, mag_b) = aplicado["A"], aplicado["B"]
    c = comparar(base, ventana, TIPOS_SHOCK[tipo_a], mag_a, TIPOS_SHOCK[tipo_b], mag_b)

    _advertencias(c)
    _tarjetas(c)

    col_grafico, col_texto = st.columns([3, 2], gap="large")
    with col_grafico:
        vista = st.segmented_control(
            "Escenarios en el gráfico", VISTAS, key="comp_vista", required=True, label_visibility="collapsed"
        )
        _grafico(c, ventana, vista or VISTAS[0])
    with col_texto:
        _veredictos(c)

    with st.expander("Tabla comparativa", icon=":material/table_chart:"):
        _tabla(c)
    with st.expander("Interpretación de la comparación", icon=":material/compare_arrows:"):
        st.markdown("\n\n".join(c.interpretacion()))

    st.subheader("Interpretación económica de cada escenario")
    for pestana, r in zip(st.tabs(["Escenario A", "Escenario B"]), (c.a, c.b)):
        with pestana:
            vista_interpretacion.mostrar(interpretar(c.base, r.p1), encabezado=None, compacto=True)

    with st.expander("Verificación numérica y de signos", icon=":material/fact_check:"):
        _verificacion(c)
