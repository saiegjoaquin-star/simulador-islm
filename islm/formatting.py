"""Formato de números y ecuaciones para la interfaz (coma decimal)."""

from __future__ import annotations

from islm.model import Recta


def numero(x: float, max_dec: int = 3, min_dec: int = 0) -> str:
    """Redondea a `max_dec` decimales, quita ceros sobrantes y usa coma decimal."""
    valor = round(float(x), max_dec)
    if valor == 0:
        valor = 0.0  # evita "-0"
    texto = f"{valor:.{max_dec}f}"
    if "." in texto:
        entero, decimales = texto.split(".")
        decimales = decimales.rstrip("0")
        if len(decimales) < min_dec:
            decimales = decimales.ljust(min_dec, "0")
        texto = f"{entero},{decimales}" if decimales else entero
    return texto


def porcentaje(x: float, max_dec: int = 2) -> str:
    return f"{numero(x, max_dec)}%"


def con_signo(x: float, max_dec: int = 2) -> str:
    """Variación con signo explícito: +28,57 / -8,57 / 0.

    Usa el guion ASCII para los negativos: st.metric lo necesita para orientar la flecha.
    """
    texto = numero(x, max_dec)
    if texto == "0":
        return "0"
    return texto if texto.startswith("-") else f"+{texto}"


def puntos_porcentuales(x: float, max_dec: int = 2) -> str:
    texto = con_signo(x, max_dec)
    return f"{texto} p.p." if texto != "0" else "0 p.p."


def tex(x: float, max_dec: int = 3, min_dec: int = 0) -> str:
    """Número listo para LaTeX: la coma decimal va entre llaves para que no deje espacio."""
    return numero(x, max_dec, min_dec).replace(",", "{,}")


def _signo(x: float) -> str:
    return "-" if x < 0 else "+"


def recta_is_tex(recta: Recta) -> str:
    """IS en la forma i = a - m·Y."""
    m = recta.pendiente
    return rf"i = {tex(recta.ordenada)} {_signo(m)} {tex(abs(m), min_dec=2)}\,Y"


def recta_lm_tex(recta: Recta) -> str:
    """LM en la forma i = m·Y - a."""
    a = recta.ordenada
    return rf"i = {tex(recta.pendiente, min_dec=2)}\,Y {_signo(a)} {tex(abs(a))}"
