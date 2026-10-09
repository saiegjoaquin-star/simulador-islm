"""Pestaña "Marco teórico": síntesis del modelo IS-LM, supuestos y limitaciones.

Contenido estático. Los valores del simulador que se citan como ejemplo se leen de la
configuración y de las funciones del motor (solo lectura): no se modifica ningún cálculo.

Fuente principal: José De Gregorio, Macroeconomía, capítulo 19,
"El modelo keynesiano de economía cerrada: IS-LM", pp. 499-527.
"""

from __future__ import annotations

import streamlit as st

from islm.formatting import numero, porcentaje, recta_is_tex, recta_lm_tex
from islm.mercado_bienes import multiplicadores
from islm.mercado_dinero import multiplicador_monetario
from islm.model import Parametros, curva_is, curva_lm, equilibrio
from vistas import ui

FUENTE = "De Gregorio, cap. 19"


# Fórmula breve que acompaña el título de cada desplegable.
FORMULA_TITULO = {
    3: "C = C₀ + c(Y − T)",
    4: "I = I₀ − b·i",
    5: "Y = C + I + G",
    8: "L = kY − h·i",
    9: "M/P",
    14: "1/(1 − c)",
}


def _concepto(
    numero_concepto: int,
    titulo: str,
    texto: str,
    fuente: str,
    formula: str | None = None,
    simulador: str | None = None,
    desplegable: bool = True,
) -> None:
    def cuerpo() -> None:
        st.markdown(texto)
        if formula:
            st.latex(formula)
        pie = f"Fuente: {FUENTE}, {fuente}."
        if simulador:
            pie = f"En el simulador: {simulador} · {pie}"
        st.caption(pie)

    if not desplegable:
        st.markdown(f"**{numero_concepto}. {titulo}**")
        cuerpo()
        return
    etiqueta = f"{numero_concepto}. {titulo}"
    if numero_concepto in FORMULA_TITULO:
        etiqueta += f"  ·  {FORMULA_TITULO[numero_concepto]}"
    with st.expander(etiqueta):
        cuerpo()


def mostrar(p: Parametros) -> None:
    e0 = equilibrio(p)
    is0, lm0 = curva_is(p), curva_lm(p)
    m_bienes = multiplicadores(p)
    m_dinero = multiplicador_monetario(p)
    alfa = 1 / (1 - p.c)

    ui.encabezado(
        "Marco teórico",
        "Fuente principal: José De Gregorio, Macroeconomía, cap. 19, «El modelo keynesiano de economía "
        "cerrada: IS-LM» (pp. 499–527). Abrí cada concepto para ver su desarrollo.",
    )

    # --- 1. El modelo -------------------------------------------------------------------
    with st.container(border=True):
        _concepto(
            1,
            "Qué representa el modelo IS-LM",
            "Explica cómo se determinan **simultáneamente el producto (Y) y la tasa de interés (i)** en el "
            "corto plazo, en una economía con capacidad ociosa y **precios rígidos**: los cambios en la "
            "demanda agregada se traducen en cambios de cantidades y no de precios. La curva **IS** "
            "(*investment–saving*) reúne los equilibrios del mercado de bienes y la **LM** "
            "(*liquidity–money*), los del mercado monetario. Fue formalizado por Hicks (1937) a partir de "
            "la *Teoría general* de Keynes (1936). Las funciones de inversión y de demanda de dinero del "
            "libro son generales; el simulador usa sus versiones lineales.",
            "introducción, p. 499",
            desplegable=False,
        )

    # --- 2-10. Los dos mercados ---------------------------------------------------------
    col_bienes, col_dinero = st.columns(2, gap="large")
    with col_bienes:
        st.subheader("Mercado de bienes")
        _concepto(
            2,
            "Mercado de bienes",
            "En una economía cerrada, la demanda agregada es A = C + I + G. La producción se ajusta a la "
            "demanda: si A > Y, las empresas desacumulan inventarios y aumentan la producción; si A < Y, "
            "acumulan inventarios no deseados y la reducen.",
            "§19.1, pp. 500–502, ec. 19.1",
        )
        _concepto(
            3,
            "Función de consumo",
            "C₀ es el consumo autónomo, c la propensión marginal a consumir (0 < c < 1) e Y − T el "
            "ingreso disponible. Por cada unidad adicional de ingreso disponible, el consumo sube c.",
            "§19.1, p. 500, ec. 19.2 (allí el consumo autónomo se escribe C̄)",
            formula=r"C = C_0 + c\,(Y - T)",
            simulador=f"C₀ = {numero(p.C0)}, c = {numero(p.c, min_dec=2)}, T = {numero(p.T)}",
        )
        _concepto(
            4,
            "Función de inversión",
            "I₀ es la inversión autónoma (expectativas de las empresas, los «espíritus animales») y b > 0 "
            "su sensibilidad a la tasa: una tasa más alta encarece el financiamiento y reduce la inversión. "
            "El libro usa I = I(r) con I′ < 0; con inflación esperada nula, r = i.",
            "§19.3, pp. 507–508, ec. 19.8",
            formula=r"I = I_0 - b\,i",
            simulador=f"I₀ = {numero(p.I0)}, b = {numero(p.b)}",
        )
        _concepto(
            5,
            "Equilibrio del mercado de bienes",
            "El producto iguala a la demanda agregada (equivalentemente, el ahorro iguala a la inversión). "
            "Despejando Y, el gasto autónomo Ā = C₀ − cT + I₀ + G se multiplica por 1/(1 − c).",
            "§19.1, pp. 501–502, ecs. 19.3–19.5; §19.3, p. 507, ec. 19.8",
            formula=r"Y = C + I + G \;\Rightarrow\; Y = \frac{C_0 - cT + I_0 + G - b\,i}{1 - c}",
        )
        _concepto(
            6,
            "Curva IS",
            "Pares (Y, i) que equilibran el mercado de bienes. Tiene **pendiente negativa**: una tasa más "
            "baja eleva la inversión y, por el multiplicador, el producto. Un cambio de i es un "
            "**movimiento a lo largo** de la IS; un cambio en G, T, C₀ o I₀ la **desplaza** (a la derecha "
            "si aumenta el gasto autónomo).",
            "§19.3, pp. 507–510, ecs. 19.8–19.9, fig. 19.4",
            formula=r"i = \frac{\bar{A}}{b} - \frac{1-c}{b}\,Y",
            simulador=f"${recta_is_tex(is0)}$",
        )

    with col_dinero:
        st.subheader("Mercado monetario")
        _concepto(
            7,
            "Mercado monetario",
            "El dinero se demanda para realizar transacciones, pero no rinde interés: su costo de "
            "oportunidad es la tasa nominal que pagan los bonos. Como la riqueza se reparte entre dinero y "
            "bonos, un exceso de oferta de dinero equivale a un exceso de demanda de bonos: sube su precio "
            "y baja la tasa de interés.",
            "§19.4, pp. 510–514, ec. 19.13",
        )
        _concepto(
            8,
            "Demanda de dinero",
            "Demanda de saldos reales. k > 0: más actividad requiere más dinero para transacciones; "
            "h > 0: una tasa más alta eleva el costo de mantener dinero. El libro usa L(i, Y) con "
            "$L_Y > 0$ y $L_i < 0$.",
            "§19.4, p. 510, ec. 19.10",
            formula=r"L = k\,Y - h\,i",
            simulador=f"k = {numero(p.k, min_dec=2)}, h = {numero(p.h)}",
        )
        _concepto(
            9,
            "Oferta monetaria real",
            "La oferta nominal M es exógena y la fija el banco central. Con el nivel de precios P dado, "
            "el banco central controla también la oferta real M/P.",
            "§19.4, p. 510",
            formula=r"\frac{M}{P}\ \text{exógena}",
            simulador=f"M/P = {numero(p.oferta_real)} (P = {numero(p.P)})",
        )
        _concepto(
            10,
            "Curva LM",
            "Pares (Y, i) que equilibran el mercado monetario. Tiene **pendiente positiva**: si sube Y, "
            "aumenta la demanda de dinero y, con la oferta fija, la tasa debe subir para equilibrarlo. Un "
            "aumento de M/P la **desplaza** hacia la derecha (hacia abajo); una reducción, hacia la izquierda.",
            "§19.4, pp. 510–514, ecs. 19.11–19.12, fig. 19.8",
            formula=r"\frac{M}{P} = k\,Y - h\,i \;\Rightarrow\; i = \frac{k}{h}\,Y - \frac{M/P}{h}",
            simulador=f"${recta_lm_tex(lm0)}$",
        )

    # --- 11. Equilibrio conjunto ---------------------------------------------------------
    st.subheader("Equilibrio conjunto")
    _concepto(
        11,
        "Equilibrio IS-LM",
        "La intersección de la IS y la LM es el único par (Y\\*, i\\*) en el que ambos mercados están "
        "en equilibrio. Con las formas lineales del simulador tiene solución cerrada:",
        "§19.5, pp. 514–516, ecs. 19.14–19.16",
        formula=(
            r"Y^* = \frac{h\,\bar{A} + b\,M/P}{h(1-c) + b\,k} \qquad "
            r"i^* = \frac{k\,\bar{A} - (1-c)\,M/P}{h(1-c) + b\,k}"
        ),
        simulador=f"E₀ = ({numero(e0.Y)}; {porcentaje(e0.i)})",
    )

    # --- 12-15. Política económica -------------------------------------------------------
    st.subheader("Política económica y sus efectos")
    fila1 = st.columns(2, gap="large")
    with fila1[0]:
        _concepto(
            12,
            "Política fiscal",
            "Un aumento de G o una reducción de T eleva la demanda agregada y **desplaza la IS a la "
            "derecha**. La economía se mueve a lo largo de la LM: suben el producto y la tasa de interés. "
            "La política contractiva tiene los efectos opuestos.",
            "§19.6.2, pp. 519–521",
            simulador=f"ΔY/ΔG ≈ {numero(m_bienes['G'].islm, 2)}; ΔY/ΔT ≈ {numero(m_bienes['T'].islm, 2)}",
        )
    with fila1[1]:
        _concepto(
            13,
            "Política monetaria",
            "Un aumento de M/P genera un exceso de oferta de dinero y **desplaza la LM a la derecha**. La "
            "tasa baja, la inversión aumenta y el producto crece a lo largo de la IS. La política "
            "contractiva tiene los efectos opuestos.",
            "§19.6.1, pp. 517–519, ec. 19.20",
            simulador=f"dY/d(M/P) ≈ {numero(m_dinero.producto, 2)}; di/d(M/P) ≈ {numero(m_dinero.tasa, 3)} p.p.",
        )
    fila2 = st.columns(2, gap="large")
    with fila2[0]:
        _concepto(
            14,
            "Multiplicador",
            "Mide cuánto cambia el producto ante un cambio unitario de un componente autónomo del gasto. "
            "Con la tasa de interés constante vale 1/(1 − c) (para los impuestos, −c/(1 − c)). En el "
            "equilibrio IS-LM es menor, porque la tasa se ajusta y modifica la inversión.",
            "§19.2, pp. 502–506, ec. 19.7; p. 520; ec. 19.20, p. 518",
            formula=r"\frac{1}{1-c} \qquad \frac{dY}{dG}\Big|_{IS\text{-}LM} = \frac{h}{h(1-c) + b\,k}",
            simulador=f"1/(1 − c) = {numero(alfa, 2)}; dY/dG en IS-LM ≈ {numero(m_bienes['G'].islm, 2)}",
        )
    with fila2[1]:
        _concepto(
            15,
            "Crowding out",
            "Una política fiscal expansiva eleva la tasa de interés y **desplaza parcialmente la inversión "
            "privada**: por eso el producto crece menos que lo que indica el multiplicador simple. Es total "
            "si la LM es vertical (h = 0) y nulo si la LM es horizontal (trampa de la liquidez) o si la "
            "inversión no depende de la tasa (b = 0).",
            "§19.6.2, pp. 519–521, fig. 19.13",
            simulador=(
                f"con ΔG = +10, la inversión cae {numero(10 * p.b * m_bienes['G'].tasa, 2)}"
            ),
        )

    # --- Supuestos y limitaciones ---------------------------------------------------------
    col_sup, col_lim = st.columns(2, gap="large")
    with col_sup:
        st.subheader("Supuestos del simulador")
        st.markdown(
            "\n".join(
                [
                    f"- **Precios fijos** (P = {numero(p.P)}): la demanda determina el producto (p. 499).",
                    "- **Economía cerrada**: no hay comercio exterior ni flujos de capital; A = C + I + G.",
                    "- **Tasa de interés única**: con inflación esperada nula, la tasa nominal y la real "
                    "coinciden, y la misma i afecta a la inversión y a la demanda de dinero (p. 515).",
                    "- **Impuestos de suma fija**: T no depende del ingreso. El libro también analiza "
                    "impuestos proporcionales (ec. 19.6), que el simulador no incluye.",
                    "- **Expectativas de inflación iguales a cero** (πᵉ = 0, p. 515).",
                    f"- **Parámetros estructurales constantes**: c = {numero(p.c, min_dec=2)}, b = {numero(p.b)}, "
                    f"k = {numero(p.k, min_dec=2)} y h = {numero(p.h)} no cambian; solo se modifican G, T, "
                    "I₀ y M/P.",
                    "- **Funciones lineales** de inversión y de demanda de dinero.",
                    "- **Estática comparativa**: se comparan el equilibrio inicial y el final; no se modela "
                    "el ajuste en el tiempo (la dinámica se discute en §19.5, p. 515).",
                ]
            )
        )
    with col_lim:
        st.subheader("Limitaciones")
        st.markdown(
            "El IS-LM es una **representación simplificada** de la economía. Sirve para entender "
            "mecanismos y la dirección de los efectos, pero **no constituye una predicción empírica**."
        )
        st.markdown(
            "\n".join(
                [
                    f"- Los parámetros están **calibrados con fines pedagógicos** (E₀ = ({numero(e0.Y)}; "
                    f"{porcentaje(e0.i)})), no estimados con datos: las magnitudes dependen de esa calibración.",
                    "- Deja fuera la oferta agregada y el ajuste de precios, el sector externo y las "
                    "expectativas.",
                    "- Ignora la restricción presupuestaria intertemporal del gobierno y la equivalencia "
                    "ricardiana (pp. 504–505).",
                    "- No incluye el efecto riqueza (§19.6.4) ni el límite inferior de la tasa nominal "
                    "(trampa de la liquidez, §19.7).",
                ]
            )
        )

    st.caption(
        "Referencia: De Gregorio, J. *Macroeconomía*. Capítulo 19, «El modelo "
        "keynesiano de economía cerrada: IS-LM», pp. 499–527."
    )
