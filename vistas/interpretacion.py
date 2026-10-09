"""Componente de interpretación económica, común a todas las pestañas con shocks."""

from __future__ import annotations

import streamlit as st

from islm.interpretacion import Interpretacion


def mostrar(
    interpretacion: Interpretacion,
    encabezado: str | None = "Interpretación económica",
    compacto: bool = False,
) -> None:
    """Recuadro con la interpretación y desplegable «¿Qué ocurrió en el modelo?».

    En modo compacto solo el primer párrafo queda visible; el resto va en un desplegable.
    No debe llamarse dentro de un `st.expander` (Streamlit no permite anidarlos).
    """
    if encabezado:
        st.subheader(encabezado)
    with st.container(border=True):
        st.markdown(f"**{interpretacion.titulo}**")
        if compacto and len(interpretacion.resumen) > 1:
            st.markdown(interpretacion.resumen[0])
            with st.expander("Consumo, inversión y multiplicador"):
                st.markdown("\n\n".join(interpretacion.resumen[1:]))
        else:
            st.markdown(interpretacion.texto)
    if interpretacion.pasos:
        with st.expander("¿Qué ocurrió en el modelo?", icon=":material/account_tree:"):
            st.markdown("\n".join(f"{n}. {paso}" for n, paso in enumerate(interpretacion.pasos, start=1)))
            st.caption(
                "Los pasos ordenan la lógica causal de la estática comparativa entre E₀ y E₁; no describen "
                "una trayectoria en el tiempo. El texto se genera con reglas fijas a partir de los "
                "resultados calculados por el modelo."
            )
