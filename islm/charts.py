"""Gráfico IS-LM con Plotly.

El gráfico recibe listas de curvas y de equilibrios, así que los módulos de shocks
podrán agregar IS1, LM1 y E1 sin cambiar esta función.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import plotly.graph_objects as go

from islm.config import Ventana
from islm.formatting import numero, porcentaje
from islm.model import Recta

COLOR_IS = "#2a78d6"
COLOR_LM = "#eb6834"
COLOR_PUNTO = "#6b6a66"
COLOR_PUNTO_NUEVO = "#7b6ee0"
# Colores de los escenarios comparados (distinguibles de COLOR_IS y COLOR_LM, también con daltonismo).
COLOR_ESCENARIO_A = "#4a3aa7"
COLOR_ESCENARIO_B = "#1baf7a"
COLOR_GUIA = "rgba(120, 120, 120, 0.55)"
COLOR_FLECHA = "rgba(110, 110, 110, 0.9)"


@dataclass(frozen=True)
class CurvaGrafico:
    nombre: str          # p. ej. "IS₀"
    recta: Recta
    color: str
    punteada: bool = False
    etiqueta_lado_opuesto: bool = False  # rotular del otro lado de la recta (curvas paralelas cercanas)
    posicion_etiqueta: float = 0.9  # fracción del tramo visible donde va la etiqueta
    rotular: bool = True             # False: sin etiqueta directa (otra curva ya la nombra)
    atenuada: bool = False           # curva de referencia (inicial): más fina y tenue
    leyenda: str | None = None       # texto de la leyenda (por defecto, el nombre)


@dataclass(frozen=True)
class PuntoGrafico:
    nombre: str          # p. ej. "E₀"
    Y: float
    i: float
    color: str = COLOR_PUNTO
    etiqueta_izquierda: bool | None = None  # None: se decide según la posición en la ventana
    etiqueta_vertical: str = "centro"       # "centro", "arriba" o "abajo" del punto
    atenuado: bool = False                  # punto de referencia (inicial): más chico
    leyenda: str | None = None              # texto de la leyenda (por defecto, el nombre)


@dataclass(frozen=True)
class FlechaGrafico:
    """Flecha horizontal entre dos curvas a una misma tasa (p. ej., desplazamiento de la IS)."""

    Y_desde: float
    Y_hasta: float
    i: float
    texto: str
    curvas_crecientes: bool = False  # LM: el texto lateral va abajo, del lado libre de la recta


def tramo_visible(recta: Recta, ventana: Ventana) -> tuple[float, float] | None:
    """Intervalo de Y en el que la recta queda dentro de la ventana (o None)."""
    y_desde, y_hasta = ventana.y_min, ventana.y_max
    for limite in (ventana.i_min, ventana.i_max):
        y_corte = recta.producto(limite)
        sube = recta.pendiente > 0
        # Para pendiente positiva, i_min acota por la izquierda e i_max por la derecha.
        if (limite == ventana.i_min) == sube:
            y_desde = max(y_desde, y_corte)
        else:
            y_hasta = min(y_hasta, y_corte)
    return (y_desde, y_hasta) if y_desde < y_hasta else None


def _tasas_visibles(recta: Recta, ventana: Ventana) -> tuple[float, float] | None:
    tramo = tramo_visible(recta, ventana)
    if tramo is None:
        return None
    extremos = sorted(recta.tasa(y) for y in tramo)
    return extremos[0], extremos[1]


def flecha_entre_curvas(
    desde: Recta, hasta: Recta, ventana: Ventana, texto: str, altura: float = 0.85
) -> FlechaGrafico | None:
    """Flecha horizontal de `desde` a `hasta` a una tasa en la que ambas curvas se ven.

    Se ubica en la parte alta del tramo común (`altura` = 0,85) para no tapar los equilibrios.
    Devuelve None si las curvas no comparten ninguna tasa visible.
    """
    t0, t1 = _tasas_visibles(desde, ventana), _tasas_visibles(hasta, ventana)
    if t0 is None or t1 is None:
        return None
    i_min, i_max = max(t0[0], t1[0]), min(t0[1], t1[1])
    if i_min >= i_max:
        return None
    i = i_min + altura * (i_max - i_min)
    return FlechaGrafico(desde.producto(i), hasta.producto(i), i, texto, curvas_crecientes=desde.pendiente > 0)


def _ancla_etiqueta(curva: CurvaGrafico, ventana: Ventana, posicion: float) -> tuple[float, float] | None:
    tramo = tramo_visible(curva.recta, ventana)
    if tramo is None:
        return None
    Y = tramo[0] + posicion * (tramo[1] - tramo[0])
    return Y, curva.recta.tasa(Y)


def ubicar_etiquetas_de_curvas(
    curvas: list[CurvaGrafico],
    puntos: list[PuntoGrafico],
    ventana: Ventana,
    fijas: int = 0,
    candidatas: tuple[float, ...] = (0.9, 0.78, 0.66, 0.5, 0.34, 0.2, 0.1),
) -> list[CurvaGrafico]:
    """Elige, para cada curva a partir de `fijas`, la posición de etiqueta más alejada de los
    equilibrios, de sus rótulos y de las etiquetas ya ubicadas (distancias normalizadas por la
    ventana). Las primeras `fijas` curvas conservan su posición."""
    ancho = ventana.y_max - ventana.y_min
    alto = ventana.i_max - ventana.i_min
    obstaculos: list[tuple[float, float]] = []
    for p in puntos:
        if not punto_visible(p, ventana):
            continue
        obstaculos.append((p.Y, p.i))
        lado = -1 if etiqueta_a_la_izquierda(p, ventana) else 1
        dy = {"centro": 0, "arriba": 0.035, "abajo": -0.035}[p.etiqueta_vertical] * alto
        for fraccion in (0.06, 0.13, 0.2):  # el rótulo del punto ocupa ~20 % del ancho
            obstaculos.append((p.Y + lado * fraccion * ancho, p.i + dy))

    def distancia(ancla: tuple[float, float]) -> float:
        if not obstaculos:
            return float("inf")
        return min(((ancla[0] - y) / ancho) ** 2 + ((ancla[1] - i) / alto) ** 2 for y, i in obstaculos) ** 0.5

    resultado = []
    for k, curva in enumerate(curvas):
        if k >= fijas and curva.rotular:
            opciones = [(p, _ancla_etiqueta(curva, ventana, p)) for p in candidatas]
            opciones = [(p, a) for p, a in opciones if a is not None]
            if opciones:
                mejor, _ = max(opciones, key=lambda op: distancia(op[1]))
                curva = replace(curva, posicion_etiqueta=mejor)
        ancla = _ancla_etiqueta(curva, ventana, curva.posicion_etiqueta) if curva.rotular else None
        if ancla:
            obstaculos.append(ancla)
        resultado.append(curva)
    return resultado


def _agregar_flecha(fig: go.Figure, flecha: FlechaGrafico, ventana: Ventana) -> None:
    fig.add_annotation(
        x=flecha.Y_hasta,
        y=flecha.i,
        ax=flecha.Y_desde,
        ay=flecha.i,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        text="",
        showarrow=True,
        arrowhead=2,
        arrowsize=1.2,
        arrowwidth=1.6,
        arrowcolor=COLOR_FLECHA,
        standoff=3,
        startstandoff=3,
    )
    # Ancho aproximado del texto en unidades de Y (~1 % del eje por carácter a tamaño 12).
    caracteres = max(len(linea) for linea in flecha.texto.split("<br>"))
    ancho_texto = caracteres * 0.01 * (ventana.y_max - ventana.y_min)
    izquierda, derecha = sorted((flecha.Y_desde, flecha.Y_hasta))
    margen = 0.02 * (ventana.y_max - ventana.y_min)
    # Al costado de una recta creciente, el lado libre es abajo a la derecha (o arriba a la izquierda).
    vertical_der = dict(yanchor="top", yshift=-6) if flecha.curvas_crecientes else dict(yanchor="middle")
    vertical_izq = dict(yanchor="bottom", yshift=6) if flecha.curvas_crecientes else dict(yanchor="middle")
    if ancho_texto + 2 * margen <= derecha - izquierda:
        posicion = dict(x=(izquierda + derecha) / 2, xanchor="center", yanchor="bottom", yshift=4)
    elif derecha + margen + ancho_texto <= ventana.y_max:
        posicion = dict(x=derecha, xanchor="left", xshift=10, **vertical_der)
    elif izquierda - margen - ancho_texto >= ventana.y_min:
        posicion = dict(x=izquierda, xanchor="right", xshift=-10, **vertical_izq)
    else:
        return  # el texto no entra sin salirse de la ventana; la interfaz lo informa aparte
    fig.add_annotation(y=flecha.i, text=flecha.texto, showarrow=False, font=dict(size=12), **posicion)


def _agregar_curva(fig: go.Figure, curva: CurvaGrafico, ventana: Ventana) -> None:
    ys = [ventana.y_min, ventana.y_max]
    fig.add_trace(
        go.Scatter(
            x=ys,
            y=[curva.recta.tasa(y) for y in ys],
            mode="lines",
            name=curva.leyenda or curva.nombre,
            opacity=0.55 if curva.atenuada else 1.0,
            line=dict(
                color=curva.color,
                width=1.8 if curva.atenuada else 3,
                dash="dash" if (curva.punteada or curva.atenuada) else "solid",
            ),
            hovertemplate=f"{curva.nombre}<br>Y = %{{x:.1f}}<br>i = %{{y:.2f}}%<extra></extra>",
        )
    )
    tramo = tramo_visible(curva.recta, ventana)
    if tramo is None or not curva.rotular:
        return
    # Etiqueta directa cerca del extremo derecho visible. Por defecto va a la derecha de la recta
    # (debajo si sube, encima si baja); con `etiqueta_lado_opuesto`, a la izquierda.
    y_etiqueta = tramo[0] + curva.posicion_etiqueta * (tramo[1] - tramo[0])
    sube = curva.recta.pendiente > 0
    izquierda = curva.etiqueta_lado_opuesto
    fig.add_annotation(
        x=y_etiqueta,
        y=curva.recta.tasa(y_etiqueta),
        text=f"<b>{curva.nombre}</b>",
        showarrow=False,
        xanchor="right" if izquierda else "left",
        yanchor="top" if sube != izquierda else "bottom",
        xshift=-6 if izquierda else 6,
        yshift=-4 if sube != izquierda else 4,
        font=dict(size=14 if curva.atenuada else 16, color=curva.color),
        opacity=0.7 if curva.atenuada else 1.0,
    )


def punto_visible(punto: PuntoGrafico, ventana: Ventana) -> bool:
    return ventana.y_min <= punto.Y <= ventana.y_max and ventana.i_min <= punto.i <= ventana.i_max


def etiqueta_a_la_izquierda(punto: PuntoGrafico, ventana: Ventana) -> bool:
    """La etiqueta va a la derecha salvo que el punto esté en el último cuarto horizontal."""
    if punto.etiqueta_izquierda is not None:
        return punto.etiqueta_izquierda
    return punto.Y > ventana.y_min + 0.75 * (ventana.y_max - ventana.y_min)


def _agregar_punto(fig: go.Figure, punto: PuntoGrafico, ventana: Ventana) -> None:
    etiqueta = f"{punto.nombre} = ({numero(punto.Y, 2)}; {porcentaje(punto.i)})"
    if not punto_visible(punto, ventana):
        # Fuera de la ventana: no se dibuja ni se recorta; se informa su valor real en una nota.
        fig.add_annotation(
            xref="paper",
            yref="paper",
            x=0.99,
            y=0.99,
            xanchor="right",
            yanchor="top",
            text=f"{etiqueta} queda fuera del gráfico",
            showarrow=False,
            font=dict(size=13),
            bordercolor=punto.color,
            borderwidth=1.5,
            borderpad=6,
        )
        return
    guia = dict(color=COLOR_GUIA, width=1.2, dash="dot")
    fig.add_shape(type="line", x0=punto.Y, x1=punto.Y, y0=ventana.i_min, y1=punto.i, line=guia, layer="below")
    fig.add_shape(type="line", x0=ventana.y_min, x1=punto.Y, y0=punto.i, y1=punto.i, line=guia, layer="below")
    fig.add_trace(
        go.Scatter(
            x=[punto.Y],
            y=[punto.i],
            mode="markers",
            name=punto.leyenda or punto.nombre,
            marker=dict(
                size=10 if punto.atenuado else 15,
                color=punto.color,
                line=dict(color="white", width=2 if punto.atenuado else 2.5),
            ),
            hovertemplate=f"{etiqueta}<extra></extra>",
        )
    )
    izquierda = etiqueta_a_la_izquierda(punto, ventana)
    fig.add_annotation(
        x=punto.Y,
        y=punto.i,
        text=f"<b>{etiqueta}</b>",
        showarrow=False,
        xanchor="right" if izquierda else "left",
        yanchor={"centro": "middle", "arriba": "bottom", "abajo": "top"}[punto.etiqueta_vertical],
        xshift=-12 if izquierda else 12,
        yshift={"centro": 0, "arriba": 2, "abajo": -2}[punto.etiqueta_vertical],
        font=dict(size=13 if punto.atenuado else 14),
        opacity=0.75 if punto.atenuado else 1.0,
    )


def figura_islm(
    curvas: list[CurvaGrafico],
    puntos: list[PuntoGrafico],
    ventana: Ventana,
    flechas: list[FlechaGrafico] | None = None,
    alto: int = 540,
) -> go.Figure:
    """Arma el gráfico IS-LM con ejes fijos dados por `ventana`.

    Los puntos fuera de la ventana no se recortan ni se reubican: simplemente no se ven.
    """
    fig = go.Figure()
    for curva in curvas:
        _agregar_curva(fig, curva, ventana)
    for flecha in flechas or []:
        _agregar_flecha(fig, flecha, ventana)
    for punto in puntos:
        _agregar_punto(fig, punto, ventana)

    fig.update_layout(
        height=alto,
        margin=dict(l=10, r=20, t=50, b=10),
        separators=",.",
        hovermode="closest",
        showlegend=True,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            font=dict(size=13), itemwidth=40, bgcolor="rgba(0,0,0,0)",
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=13),
    )
    fig.update_xaxes(
        title_text="Producto, Y",
        range=[ventana.y_min, ventana.y_max],
        dtick=10,
        fixedrange=True,
        showgrid=True,
        gridcolor="rgba(128,128,128,0.12)",
        gridwidth=1,
        zeroline=False,
        showline=True,
        linecolor="rgba(128,128,128,0.55)",
        ticks="outside",
        tickcolor="rgba(128,128,128,0.55)",
        tickfont=dict(size=12),
        title_font=dict(size=14),
    )
    fig.update_yaxes(
        title_text="Tasa de interés, i (%)",
        range=[ventana.i_min, ventana.i_max],
        dtick=1,
        fixedrange=True,
        showgrid=True,
        gridcolor="rgba(128,128,128,0.12)",
        gridwidth=1,
        zeroline=False,
        showline=True,
        linecolor="rgba(128,128,128,0.55)",
        ticks="outside",
        tickcolor="rgba(128,128,128,0.55)",
        tickfont=dict(size=12),
        title_font=dict(size=14),
    )
    return fig
