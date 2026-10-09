"""Comparación de dos intervenciones (escenarios A y B) desde el mismo equilibrio base.

Cada escenario se resuelve con los módulos ya verificados: `mercado_bienes` para G, T e I0
y `mercado_dinero` para M/P. Este módulo solo agrega la clasificación, la comparación de
efectos y una interpretación descriptiva (no normativa).
"""

from __future__ import annotations

from dataclasses import dataclass

from islm.config import RANGO_OFERTA_REAL, RANGOS_BIENES, Ventana
from islm.formatting import con_signo, numero, puntos_porcentuales
from islm.mercado_bienes import analizar_shock_bienes
from islm.mercado_dinero import analizar_shock_dinero
from islm.model import Equilibrio, Parametros, Recta, curva_is, curva_lm, equilibrio
from islm.shocks import FueraDeRango

FISCAL = "Política fiscal"
MONETARIA = "Política monetaria"
PRIVADO = "Shock privado"

TOLERANCIA = 1e-9


@dataclass(frozen=True)
class TipoShock:
    clave: str
    variable: str          # "G", "T", "I0" o "M/P"
    direccion: int         # +1 aumento, -1 reducción
    categoria: str         # FISCAL, MONETARIA o PRIVADO
    descripcion: str       # p. ej. "Aumento del gasto público (G ↑)"
    clasificacion: str     # p. ej. "Política fiscal expansiva"
    signo_Y: int           # signo teórico de ΔY
    signo_i: int           # signo teórico de Δi

    @property
    def curva(self) -> str:
        return "LM" if self.variable == "M/P" else "IS"

    @property
    def simbolo(self) -> str:
        return {"I0": "I₀"}.get(self.variable, self.variable)

    @property
    def simbolo_delta(self) -> str:
        """Δ aplicado a la variable: ΔG, ΔT, ΔI₀, Δ(M/P)."""
        return "Δ(M/P)" if self.variable == "M/P" else f"Δ{self.simbolo}"


TIPOS_SHOCK: dict[str, TipoShock] = {
    t.clave: t
    for t in [
        TipoShock("G+", "G", 1, FISCAL, "Aumento del gasto público (G ↑)", "Política fiscal expansiva", 1, 1),
        TipoShock("G-", "G", -1, FISCAL, "Reducción del gasto público (G ↓)", "Política fiscal contractiva", -1, -1),
        TipoShock("T+", "T", 1, FISCAL, "Aumento de impuestos (T ↑)", "Política fiscal contractiva", -1, -1),
        TipoShock("T-", "T", -1, FISCAL, "Reducción de impuestos (T ↓)", "Política fiscal expansiva", 1, 1),
        TipoShock("M+", "M/P", 1, MONETARIA, "Aumento de la oferta monetaria real (M/P ↑)", "Política monetaria expansiva", 1, -1),
        TipoShock("M-", "M/P", -1, MONETARIA, "Reducción de la oferta monetaria real (M/P ↓)", "Política monetaria contractiva", -1, 1),
        TipoShock("I0+", "I0", 1, PRIVADO, "Aumento de la inversión autónoma (I₀ ↑)", "Shock positivo de inversión", 1, 1),
        TipoShock("I0-", "I0", -1, PRIVADO, "Reducción de la inversión autónoma (I₀ ↓)", "Shock negativo de inversión", -1, -1),
    ]
}


def _nivel_base(base: Parametros, variable: str) -> float:
    return base.oferta_real if variable == "M/P" else getattr(base, variable)


def magnitud_maxima(base: Parametros, tipo: TipoShock) -> float:
    """Mayor magnitud que mantiene el nivel dentro del rango permitido para esa variable."""
    rango = RANGO_OFERTA_REAL if tipo.variable == "M/P" else RANGOS_BIENES[tipo.variable]
    nivel = _nivel_base(base, tipo.variable)
    return rango.maximo - nivel if tipo.direccion > 0 else nivel - rango.minimo


@dataclass(frozen=True)
class ResultadoEscenario:
    nombre: str              # "A" o "B"
    base: Parametros
    tipo: TipoShock
    magnitud: float
    p1: Parametros
    e0: Equilibrio
    e1: Equilibrio
    is1: Recta
    lm1: Recta
    desplazamiento: float    # corrimiento horizontal de la curva que se mueve
    fuera_de_rango: list[FueraDeRango]

    @property
    def nivel_inicial(self) -> float:
        return _nivel_base(self.base, self.tipo.variable)

    @property
    def nivel_final(self) -> float:
        return _nivel_base(self.p1, self.tipo.variable)

    @property
    def delta_Y(self) -> float:
        return self.e1.Y - self.e0.Y

    @property
    def delta_i(self) -> float:
        return self.e1.i - self.e0.i

    @property
    def delta_C(self) -> float:
        return self.e1.C - self.e0.C

    @property
    def delta_I(self) -> float:
        return self.e1.I - self.e0.I

    @property
    def efecto_tasa_sobre_inversion(self) -> float:
        """Parte de ΔI que se debe al cambio de la tasa: -b·Δi."""
        return -self.p1.b * self.delta_i

    @property
    def es_fiscal_expansiva(self) -> bool:
        return self.tipo.clasificacion == "Política fiscal expansiva"

    @property
    def crowding_out(self) -> float | None:
        """Inversión privada desplazada por la suba de la tasa. Solo se define para la política
        fiscal expansiva; en los demás casos devuelve None."""
        if not self.es_fiscal_expansiva:
            return None
        return max(0.0, -self.efecto_tasa_sobre_inversion)

    @property
    def multiplicador(self) -> float:
        """Efecto final sobre Y por unidad de shock (en la dirección de la variable)."""
        return self.delta_Y / (self.tipo.direccion * self.magnitud)

    def controles_de_signo(self) -> list[tuple[str, bool]]:
        flecha = {1: "↑", -1: "↓"}
        return [
            (
                f"{self.tipo.clasificacion}: Y {flecha[self.tipo.signo_Y]}",
                (self.delta_Y > 0) - (self.delta_Y < 0) == self.tipo.signo_Y,
            ),
            (
                f"{self.tipo.clasificacion}: i {flecha[self.tipo.signo_i]}",
                (self.delta_i > 0) - (self.delta_i < 0) == self.tipo.signo_i,
            ),
        ]


def resolver_escenario(
    nombre: str, base: Parametros, ventana: Ventana, tipo: TipoShock, magnitud: float
) -> ResultadoEscenario:
    if magnitud <= 0:
        raise ValueError("La magnitud del shock debe ser positiva.")
    if magnitud > magnitud_maxima(base, tipo) + TOLERANCIA:
        raise ValueError(f"La magnitud supera el máximo permitido para {tipo.descripcion}.")
    nivel = _nivel_base(base, tipo.variable) + tipo.direccion * magnitud
    if tipo.variable == "M/P":
        r = analizar_shock_dinero(base, ventana, nivel)
        desplazamiento = r.desplazamiento_lm_horizontal
    else:
        r = analizar_shock_bienes(base, ventana, **{tipo.variable: nivel})
        desplazamiento = r.desplazamiento_is
    return ResultadoEscenario(
        nombre=nombre,
        base=base,
        tipo=tipo,
        magnitud=magnitud,
        p1=r.p1,
        e0=r.e0,
        e1=r.e1,
        is1=curva_is(r.p1),
        lm1=curva_lm(r.p1),
        desplazamiento=desplazamiento,
        fuera_de_rango=r.fuera_de_rango,
    )


# --- Comparación ----------------------------------------------------------------------

@dataclass(frozen=True)
class Veredicto:
    criterio: str
    ganador: str | None      # "A", "B", None (empate) o "—" (no aplica)
    texto: str


def _mayor_en_valor_absoluto(a: float, b: float) -> str | None:
    if abs(abs(a) - abs(b)) <= TOLERANCIA:
        return None
    return "A" if abs(a) > abs(b) else "B"


@dataclass(frozen=True)
class Comparacion:
    base: Parametros
    e0: Equilibrio
    a: ResultadoEscenario
    b: ResultadoEscenario

    def escenario(self, nombre: str) -> ResultadoEscenario:
        return self.a if nombre == "A" else self.b

    @property
    def is0(self) -> Recta:
        return curva_is(self.base)

    @property
    def lm0(self) -> Recta:
        return curva_lm(self.base)

    def veredictos(self) -> list[Veredicto]:
        return [
            self._veredicto_magnitud("Producción", "Y", self.a.delta_Y, self.b.delta_Y, "el producto"),
            self._veredicto_magnitud("Tasa de interés", "i", self.a.delta_i, self.b.delta_i, "la tasa de interés", tasa=True),
            self._veredicto_crowding_out(),
            self._veredicto_magnitud("Inversión", "I", self.a.delta_I, self.b.delta_I, "la inversión"),
        ]

    @staticmethod
    def _veredicto_magnitud(criterio, simbolo, da, db, nombre, tasa=False) -> Veredicto:
        fmt = puntos_porcentuales if tasa else con_signo
        ganador = _mayor_en_valor_absoluto(da, db)
        valores = f"Δ{simbolo}: {fmt(da)} en A y {fmt(db)} en B"
        if ganador is None:
            return Veredicto(criterio, None, f"Ambos escenarios mueven {nombre} en la misma magnitud ({valores}).")
        distinto_signo = (da > 0) != (db > 0) and abs(da) > TOLERANCIA and abs(db) > TOLERANCIA
        sentido = "sube" if (da if ganador == "A" else db) > 0 else "baja"
        texto = f"Mayor cambio en {nombre}: escenario {ganador}, donde {nombre} {sentido} ({valores})."
        if distinto_signo:
            texto += " Los escenarios mueven la variable en sentidos opuestos."
        return Veredicto(criterio, ganador, texto)

    def _veredicto_crowding_out(self) -> Veredicto:
        ca, cb = self.a.crowding_out, self.b.crowding_out
        if ca is None and cb is None:
            return Veredicto(
                "Crowding out",
                "—",
                "Ninguno de los dos escenarios es una política fiscal expansiva, así que no hay "
                "crowding out que comparar. El efecto de la tasa sobre la inversión (−b·Δi) figura en la tabla.",
            )
        if ca is None or cb is None:
            ganador = "A" if cb is None else "B"
            valor = ca if ganador == "A" else cb
            return Veredicto(
                "Crowding out",
                ganador,
                f"Solo el escenario {ganador} es una política fiscal expansiva: la suba de la tasa "
                f"desplaza {numero(valor, 2)} de inversión privada.",
            )
        ganador = _mayor_en_valor_absoluto(ca, cb)
        if ganador is None:
            return Veredicto(
                "Crowding out",
                None,
                f"Ambas políticas fiscales desplazan la misma inversión privada ({numero(ca, 2)}).",
            )
        return Veredicto(
            "Crowding out",
            ganador,
            f"Mayor crowding out: escenario {ganador} (inversión desplazada: {numero(ca, 2)} en A y "
            f"{numero(cb, 2)} en B).",
        )

    def interpretacion(self) -> list[str]:
        frases = []
        for r in (self.a, self.b):
            lado = "derecha" if r.desplazamiento > 0 else "izquierda"
            otra = "LM₀" if r.tipo.curva == "IS" else "IS₀"
            frases.append(
                f"**Escenario {r.nombre}** ({r.tipo.clasificacion.lower()}): desplaza la {r.tipo.curva} "
                f"hacia la {lado} y la economía se mueve a lo largo de {otra}. "
                f"ΔY = {con_signo(r.delta_Y)}, Δi = {puntos_porcentuales(r.delta_i)}, ΔI = {con_signo(r.delta_I)}."
            )

        a, b = self.a, self.b
        mismo_Y = (a.delta_Y > 0) == (b.delta_Y > 0)
        mismo_i = (a.delta_i > 0) == (b.delta_i > 0)
        if mismo_Y and not mismo_i:
            frases.append(
                f"Ambos escenarios {'aumentan' if a.delta_Y > 0 else 'reducen'} el producto, pero la tasa "
                f"se mueve en sentidos opuestos. Por eso la inversión responde distinto: el efecto de la "
                f"tasa sobre la inversión es {con_signo(a.efecto_tasa_sobre_inversion)} en A y "
                f"{con_signo(b.efecto_tasa_sobre_inversion)} en B."
            )
        elif not mismo_Y:
            frases.append(
                "Los escenarios mueven el producto en sentidos opuestos: uno es expansivo y el otro "
                "contractivo dentro del modelo."
            )
        elif abs(a.delta_Y - b.delta_Y) <= TOLERANCIA and abs(a.delta_i - b.delta_i) <= TOLERANCIA:
            frases.append(
                "Ambos escenarios llevan al mismo equilibrio (mismo Y y misma i): desplazan la misma "
                f"curva en la misma magnitud. La diferencia está en la composición del gasto: G pasa de "
                f"{numero(a.e0.G)} a {numero(a.e1.G)} en A y de {numero(b.e0.G)} a {numero(b.e1.G)} en B, "
                f"y la inversión de equilibrio cambia {con_signo(a.delta_I)} en A y {con_signo(b.delta_I)} en B."
            )
        else:
            frases.append(
                "Ambos escenarios mueven el producto y la tasa en el mismo sentido; la diferencia está en la magnitud."
            )

        if a.tipo.curva != b.tipo.curva:
            frases.append(
                "La diferencia en la tasa surge de qué curva se desplaza: si se mueve la IS, la tasa "
                "acompaña al producto a lo largo de la LM; si se mueve la LM, la tasa se mueve en "
                "sentido contrario al producto a lo largo de la IS."
            )
        frases.append(
            f"Por unidad de cambio en la variable del shock, el efecto final sobre el producto es "
            f"ΔY/{a.tipo.simbolo_delta} = {numero(a.multiplicador, 4)} en A y "
            f"ΔY/{b.tipo.simbolo_delta} = {numero(b.multiplicador, 4)} en B. Unidades de variables distintas "
            "(por ejemplo, de G y de M/P) no son directamente equivalentes."
        )
        frases.append(
            "Esta comparación describe efectos dentro del modelo IS-LM con la calibración base; no "
            "indica que una intervención sea preferible a otra."
        )
        return frases


def comparar(
    base: Parametros,
    ventana: Ventana,
    tipo_a: TipoShock,
    magnitud_a: float,
    tipo_b: TipoShock,
    magnitud_b: float,
) -> Comparacion:
    """Resuelve A y B por separado desde el mismo `base` (nunca se combinan)."""
    return Comparacion(
        base=base,
        e0=equilibrio(base),
        a=resolver_escenario("A", base, ventana, tipo_a, magnitud_a),
        b=resolver_escenario("B", base, ventana, tipo_b, magnitud_b),
    )
