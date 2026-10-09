"""Interpretación económica por reglas determinísticas (sin inteligencia artificial).

Recibe el escenario base y el escenario con shock, resuelve ambos con el motor y redacta:
- un resumen breve (qué cambió, tipo de intervención, curva desplazada, efectos, crowding out,
  papel del multiplicador);
- los pasos de transmisión del shock, distinguiendo desplazamiento de curva y movimiento a lo
  largo de una curva.

La clasificación reutiliza las reglas de `mercado_bienes` y `mercado_dinero`.
"""

from __future__ import annotations

from dataclasses import dataclass

from islm.formatting import con_signo, numero, porcentaje, puntos_porcentuales
from islm.mercado_bienes import clasificar_shock, multiplicadores
from islm.mercado_dinero import clasificar_politica_monetaria, multiplicador_monetario
from islm.model import Parametros, equilibrio, gasto_autonomo

TOLERANCIA = 1e-9

NOMBRES = {
    "G": ("gasto público", "el"),
    "T": ("los impuestos", None),
    "I0": ("inversión autónoma", "la"),
    "M/P": ("oferta monetaria real", "la"),
}


def _sube(x: float) -> bool:
    return x > TOLERANCIA


def _baja(x: float) -> bool:
    return x < -TOLERANCIA


def _signo(x: float) -> int:
    return 1 if _sube(x) else (-1 if _baja(x) else 0)


@dataclass(frozen=True)
class Cambio:
    variable: str
    antes: float
    despues: float

    @property
    def delta(self) -> float:
        return self.despues - self.antes

    @property
    def simbolo(self) -> str:
        return {"I0": "I₀"}.get(self.variable, self.variable)

    @property
    def simbolo_delta(self) -> str:
        return "Δ(M/P)" if self.variable == "M/P" else f"Δ{self.simbolo}"

    @property
    def detalle(self) -> str:
        return f"{self.simbolo}: {numero(self.antes)} → {numero(self.despues)}"

    def sustantivo(self) -> str:
        """'un aumento del gasto público', 'una reducción de los impuestos', etc."""
        nombre, articulo = NOMBRES[self.variable]
        complemento = {"el": f"del {nombre}", "la": f"de la {nombre}", None: f"de {nombre}"}[articulo]
        return f"un aumento {complemento}" if self.delta > 0 else f"una reducción {complemento}"


def _cambios(p0: Parametros, p1: Parametros) -> list[Cambio]:
    cambios = [Cambio(v, getattr(p0, v), getattr(p1, v)) for v in ("G", "T", "I0") if getattr(p0, v) != getattr(p1, v)]
    if p0.oferta_real != p1.oferta_real:
        cambios.append(Cambio("M/P", p0.oferta_real, p1.oferta_real))
    return cambios


def _capitalizar(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


def _enumerar(partes: list[str]) -> str:
    return partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " y " + partes[-1]


@dataclass(frozen=True)
class Interpretacion:
    titulo: str
    resumen: list[str]   # párrafos
    pasos: list[str]
    hay_crowding_out: bool

    @property
    def texto(self) -> str:
        return "\n\n".join(self.resumen)


def interpretar(p0: Parametros, p1: Parametros) -> Interpretacion:
    cambios = _cambios(p0, p1)
    if not cambios:
        return Interpretacion(
            "Sin cambios",
            ["No hay cambios en las variables exógenas: la economía permanece en el equilibrio base."],
            [],
            False,
        )
    return _Redactor(p0, p1, cambios).interpretacion()


class _Redactor:
    def __init__(self, p0: Parametros, p1: Parametros, cambios: list[Cambio]) -> None:
        self.p0, self.p1, self.cambios = p0, p1, cambios
        self.e0, self.e1 = equilibrio(p0), equilibrio(p1)
        self.s = 1 - p0.c
        self.dA = gasto_autonomo(p1) - gasto_autonomo(p0)
        self.dMP = p1.oferta_real - p0.oferta_real
        self.dY = self.e1.Y - self.e0.Y
        self.di = self.e1.i - self.e0.i
        self.dC = self.e1.C - self.e0.C
        self.dI = self.e1.I - self.e0.I
        self.dT = p1.T - p0.T
        self.dI0 = p1.I0 - p0.I0
        self.efecto_tasa = -p0.b * self.di
        # Parte de Δi causada por G y T (el modelo es lineal: los efectos de cada shock se suman).
        m = multiplicadores(p0)
        self.di_fiscal = sum(m[c.variable].tasa * c.delta for c in cambios if c.variable in ("G", "T"))
        self.mueve_is = abs(self.dA) > TOLERANCIA
        self.mueve_lm = abs(self.dMP) > TOLERANCIA
        self.desplazamiento_is = self.dA / self.s
        self.desplazamiento_lm = self.dMP / p0.k
        self.fiscal = next((s for s in clasificar_shock(p0, p1) if s.tipo == "fiscal"), None)
        self.inversion = next((s for s in clasificar_shock(p0, p1) if s.tipo == "inversion"), None)
        self.monetaria = clasificar_politica_monetaria(p0, p1)

    # --- Piezas comunes -----------------------------------------------------------------

    def titulo(self) -> str:
        etiquetas = [x.etiqueta for x in (self.fiscal, self.monetaria, self.inversion) if x is not None]
        return " + ".join(etiquetas)

    def resultado(self) -> str:
        if _sube(self.dY):
            prod = "un mayor nivel de producción"
        elif _baja(self.dY):
            prod = "un menor nivel de producción"
        else:
            prod = "el mismo nivel de producción"
        if _sube(self.di):
            tasa = "una tasa de interés más elevada"
        elif _baja(self.di):
            tasa = "una tasa de interés más baja"
        else:
            tasa = "la misma tasa de interés"
        return (
            f"{prod} (Y: {numero(self.e0.Y, 2)} → {numero(self.e1.Y, 2)}) y {tasa} "
            f"(i: {porcentaje(self.e0.i)} → {porcentaje(self.e1.i)})"
        )

    def combina_fiscal_e_inversion(self) -> bool:
        return self.fiscal is not None and bool(self.dI0)

    def hay_crowding_out(self) -> bool:
        if self.fiscal is None or self.fiscal.signo <= 0:
            return False
        # Con un shock de inversión simultáneo, cuenta la suba de la tasa que causa la política fiscal.
        return _sube(self.di_fiscal) if self.combina_fiscal_e_inversion() else _sube(self.di)

    # --- Resumen ------------------------------------------------------------------------

    def identificacion(self) -> list[str]:
        frases = []
        fiscales = [c for c in self.cambios if c.variable in ("G", "T")]
        if fiscales:
            sujeto = _capitalizar(_enumerar([f"{c.sustantivo()} ({c.detalle})" for c in fiscales]))
            verbo = "constituye" if len(fiscales) == 1 else "constituyen"
            frases.append(f"{sujeto} {verbo} una {self.fiscal.etiqueta.lower()}.")
        for c in self.cambios:
            if c.variable == "I0":
                tipo = "positivo" if c.delta > 0 else "negativo"
                frases.append(
                    f"{_capitalizar(c.sustantivo())} ({c.detalle}) es un shock privado {tipo} de inversión: "
                    "refleja un cambio en las decisiones de gasto de las empresas, no una política económica."
                )
            elif c.variable == "M/P":
                frases.append(
                    f"{_capitalizar(c.sustantivo())} ({c.detalle}) constituye una "
                    f"{self.monetaria.etiqueta.lower()}."
                )
        return frases

    def causa_is(self) -> str:
        eleva = "eleva" if self.dA > 0 else "reduce"
        solo_is = [c for c in self.cambios if c.variable != "M/P"]
        if len(solo_is) == 1:
            c = solo_is[0]
            if c.variable == "G":
                return f"El {'incremento' if c.delta > 0 else 'recorte'} de G {eleva} directamente la demanda agregada"
            if c.variable == "T":
                if c.delta < 0:
                    return ("La reducción de T aumenta el ingreso disponible y, con él, el consumo; esto "
                            f"{eleva} la demanda agregada")
                return ("El aumento de T reduce el ingreso disponible y, con él, el consumo; esto "
                        f"{eleva} la demanda agregada")
            return f"El {'aumento' if c.delta > 0 else 'descenso'} de la inversión autónoma {eleva} la demanda agregada"
        return f"En conjunto, estos cambios {'elevan' if self.dA > 0 else 'reducen'} la demanda agregada"

    def desplazamientos(self) -> list[str]:
        frases = []
        if self.mueve_is:
            lado = "derecha" if self.dA > 0 else "izquierda"
            combinado = len([c for c in self.cambios if c.variable != "M/P"]) > 1
            frases.append(
                f"{self.causa_is()} (el gasto autónomo cambia en {con_signo(self.dA)}) y "
                f"{'desplazan' if combinado else 'desplaza'} la curva IS hacia la {lado}."
            )
        elif any(c.variable != "M/P" for c in self.cambios):
            frases.append("Los cambios en el mercado de bienes se compensan: el gasto autónomo no varía y la IS no se desplaza.")
        if self.mueve_lm:
            if self.dMP > 0:
                frases.append(
                    "El incremento de M/P genera un exceso de oferta de dinero a los valores iniciales de Y e i "
                    "y desplaza la curva LM hacia la derecha (hacia abajo)."
                )
            else:
                frases.append(
                    "La reducción de M/P genera un exceso de demanda de dinero a los valores iniciales de Y e i "
                    "y desplaza la curva LM hacia la izquierda (hacia arriba)."
                )
        return frases

    def nuevo_equilibrio(self) -> str:
        if self.mueve_is and not self.mueve_lm:
            return (f"La LM no se desplaza: la economía se mueve a lo largo de LM₀ hasta un nuevo equilibrio "
                    f"con {self.resultado()}.")
        if self.mueve_lm and not self.mueve_is:
            return (f"La IS no se desplaza: la economía se mueve a lo largo de IS₀ hasta un nuevo equilibrio "
                    f"con {self.resultado()}.")
        if self.mueve_is and self.mueve_lm:
            return f"Ambas curvas se desplazan; el nuevo equilibrio presenta {self.resultado()}."
        return "Ninguna curva se desplaza, así que el equilibrio no cambia."

    def causa_del_resultado(self) -> str | None:
        """Por qué cambian Y e i cuando se desplaza una sola curva."""
        if not (_sube(self.dY) or _baja(self.dY)):
            return None
        sube = _sube(self.dY)
        if self.mueve_is and not self.mueve_lm:
            return (f"Como M/P está fija, el {'mayor' if sube else 'menor'} producto "
                    f"{'eleva' if sube else 'reduce'} la demanda de dinero y la tasa de interés "
                    f"{'sube' if sube else 'baja'}.")
        if self.mueve_lm and not self.mueve_is:
            return (f"La {'menor' if sube else 'mayor'} tasa de interés {'estimula' if sube else 'desalienta'} "
                    f"la inversión y, por el multiplicador, el producto {'sube' if sube else 'baja'}.")
        return None

    def consumo(self) -> str:
        dYd = self.dY - self.dT
        explicacion = f"ΔYd = ΔY − ΔT = {con_signo(dYd)}" if self.dT else f"ΔYd = ΔY = {con_signo(dYd)}"
        if _sube(self.dC):
            return f"El consumo aumenta ({con_signo(self.dC)}) porque sube el ingreso disponible ({explicacion})."
        if _baja(self.dC):
            return f"El consumo disminuye ({con_signo(self.dC)}) porque cae el ingreso disponible ({explicacion})."
        return "El consumo no cambia porque el ingreso disponible se mantiene."

    def inversion_frase(self) -> str:
        if not self.dI0:
            if _sube(self.di):
                return (f"La inversión disminuye ({con_signo(self.dI)}) porque sube la tasa de interés "
                        f"(ΔI = −b·Δi).")
            if _baja(self.di):
                return (f"La inversión aumenta ({con_signo(self.dI)}) porque baja la tasa de interés "
                        f"(ΔI = −b·Δi).")
            return "La inversión no cambia porque la tasa de interés se mantiene."
        if not (_sube(self.di) or _baja(self.di)):
            return (
                f"La inversión autónoma cambia {con_signo(self.dI0)} y la tasa de interés no cambia: la "
                f"inversión de equilibrio cambia {con_signo(self.dI)}."
            )
        movimiento = "suba" if _sube(self.di) else "baja"
        return (
            f"La inversión autónoma cambia {con_signo(self.dI0)}, pero la {movimiento} de la tasa agrega "
            f"−b·Δi = {con_signo(self.efecto_tasa)}: la inversión de equilibrio cambia {con_signo(self.dI)}."
        )

    def crowding_out(self) -> str | None:
        if self.combina_fiscal_e_inversion() and self.fiscal.signo != 0:
            # Shocks combinados: se aísla el efecto de la política fiscal sobre la tasa.
            desplazada = numero(abs(self.p0.b * self.di_fiscal), 2)
            if self.fiscal.signo > 0:
                efecto = f"sube la tasa {numero(abs(self.di_fiscal), 2)} p.p. y desplaza {desplazada} de inversión privada (crowding out)"
            else:
                efecto = f"baja la tasa {numero(abs(self.di_fiscal), 2)} p.p. y estimula {desplazada} de inversión privada (crowding in)"
            return (
                f"Considerada por sí sola, la política fiscal {efecto}; el resto del efecto de la tasa sobre la "
                "inversión proviene del shock de inversión."
            )
        if self.hay_crowding_out():
            return (
                f"La suba de la tasa reduce parcialmente la inversión privada (en {numero(abs(self.efecto_tasa), 2)}), "
                "generando un efecto de crowding out que compensa en parte el impulso fiscal."
            )
        if self.fiscal is not None and self.fiscal.signo < 0 and _baja(self.di):
            return ("No hay crowding out: la baja de la tasa estimula la inversión privada (crowding in) y "
                    "amortigua la caída del producto.")
        if self.monetaria is not None and self.fiscal is None:
            if self.monetaria.signo > 0:
                return ("No hay crowding out: la política monetaria expansiva opera bajando la tasa de interés, "
                        "lo que estimula la inversión privada.")
            return ("No hay crowding out: la caída de la inversión no se debe a un mayor gasto público, sino que "
                    "es el canal por el que actúa la política monetaria contractiva.")
        if self.inversion is not None and self.fiscal is None:
            if self.inversion.signo > 0:
                return ("No hay crowding out, porque no interviene el sector público: es la propia inversión "
                        "privada la que se ajusta, y la suba de la tasa compensa en parte el aumento de la "
                        "inversión autónoma.")
            return ("No hay crowding out: la baja de la tasa amortigua en parte la caída de la inversión "
                    "autónoma.")
        return None

    def multiplicador(self) -> str | None:
        alfa = 1 / self.s
        if self.mueve_is and not self.mueve_lm:
            frase = (
                f"El multiplicador simple 1/(1 − c) = {numero(alfa, 2)} amplifica el impulso inicial sobre el "
                f"gasto autónomo: a tasa constante, el producto cambiaría {con_signo(self.desplazamiento_is)}. "
                f"En el equilibrio IS-LM el efecto final es {con_signo(self.dY)}, menor en valor absoluto, "
                "porque el ajuste de la tasa mueve la inversión en sentido opuesto"
            )
            solo_is = [c for c in self.cambios if c.variable != "M/P"]
            if len(solo_is) == 1:
                c = solo_is[0]
                m = multiplicadores(self.p0)[c.variable].islm
                frase += f" (multiplicador IS-LM: ΔY/{c.simbolo_delta} ≈ {numero(m, 2)})"
            return frase + "."
        if self.mueve_lm and not self.mueve_is:
            m = multiplicador_monetario(self.p0).producto
            return (
                f"El multiplicador del gasto 1/(1 − c) = {numero(alfa, 2)} amplifica el cambio de la inversión: "
                f"ΔY = ΔI/(1 − c) = {con_signo(self.dI)} × {numero(alfa, 2)} ≈ {con_signo(self.dY)}. "
                f"Por cada unidad de M/P, el producto cambia dY/d(M/P) ≈ {numero(m, 2)}."
            )
        return None

    def resumen(self) -> list[str]:
        """Tres párrafos breves: qué ocurrió, efectos sobre C e I, papel del multiplicador."""
        parrafos = [
            [*self.identificacion(), *self.desplazamientos(), self.nuevo_equilibrio(), self.causa_del_resultado()],
            [self.consumo(), self.inversion_frase(), self.crowding_out()],
            [self.multiplicador()],
        ]
        return [" ".join(f for f in p if f) for p in parrafos if any(p)]

    # --- Pasos ----------------------------------------------------------------------------

    def paso_cambio_exogeno(self) -> str:
        detalle = "; ".join(f"{c.detalle} ({c.simbolo_delta} = {con_signo(c.delta)})" for c in self.cambios)
        quien = []
        if any(c.variable in ("G", "T") for c in self.cambios):
            quien.append("G y T los decide el gobierno")
        if any(c.variable == "M/P" for c in self.cambios):
            quien.append("M lo fija el banco central y P está dado")
        if any(c.variable == "I0" for c in self.cambios):
            quien.append("I₀ refleja las expectativas de las empresas")
        return f"**Cambio exógeno.** {detalle}. {_capitalizar(_enumerar(quien))}."

    def pasos_is(self) -> list[str]:
        exceso = "demanda" if self.dA > 0 else "oferta"
        signo = ">" if self.dA > 0 else "<"
        impuesto = (
            f" Solo la fracción c del cambio impositivo llega al consumo: −c·ΔT = {con_signo(-self.p0.c * self.dT)}."
            if self.dT else ""
        )
        sube_Y = _sube(self.dY)
        pasos = [
            f"**Impulso sobre la demanda agregada.** A los valores iniciales (Y = {numero(self.e0.Y)}, "
            f"i = {porcentaje(self.e0.i)}), la demanda agregada A = C + I + G cambia en ΔĀ = {con_signo(self.dA)}: "
            f"aparece un exceso de {exceso} de bienes (A {signo} Y).{impuesto}",
            f"**Desplazamiento de la IS.** Para cada tasa de interés, el producto que equilibra el mercado de "
            f"bienes cambia en ΔĀ/(1 − c) = {con_signo(self.desplazamiento_is)}: la IS se desplaza hacia la "
            f"{'derecha' if self.dA > 0 else 'izquierda'}. La LM no cambia.",
            f"**Movimiento a lo largo de LM₀.** Al {'subir' if sube_Y else 'bajar'} el producto, "
            f"{'aumenta' if sube_Y else 'disminuye'} la demanda de dinero por transacciones. Con M/P fija, la tasa "
            f"{'sube' if _sube(self.di) else 'baja'} para mantener el equilibrio monetario: "
            f"i pasa de {porcentaje(self.e0.i)} a {porcentaje(self.e1.i)}.",
            f"**Efecto sobre la inversión.** {self.inversion_frase()}"
            + (" Es el crowding out." if self.hay_crowding_out() else ""),
            f"**Efecto sobre el consumo.** {self.consumo()}",
            f"**Nuevo equilibrio.** E₁ = ({numero(self.e1.Y, 2)}; {porcentaje(self.e1.i)}), con "
            f"Δi = {puntos_porcentuales(self.di)} y ΔY = {con_signo(self.dY)}. El efecto final es menor que el "
            f"desplazamiento de la IS ({con_signo(self.desplazamiento_is)}) porque el cambio de la tasa modifica "
            "la inversión.",
        ]
        return pasos

    def pasos_lm(self) -> list[str]:
        expansiva = self.dMP > 0
        L0 = self.e0.demanda_dinero
        alfa = 1 / self.s
        return [
            f"**Desequilibrio en el mercado de dinero.** En E₀ la demanda de dinero es {numero(L0)} y la oferta "
            f"pasa a {numero(self.p1.oferta_real)}: hay un exceso de {'oferta' if expansiva else 'demanda'} de "
            f"{numero(abs(self.dMP), 2)}. El público {'compra' if expansiva else 'vende'} bonos, su precio "
            f"{'sube' if expansiva else 'baja'} y la tasa de interés {'baja' if expansiva else 'sube'}.",
            f"**Desplazamiento de la LM.** Para cada nivel de producto, la tasa que equilibra el mercado de dinero "
            f"cambia en −Δ(M/P)/h = {puntos_porcentuales(-self.dMP / self.p0.h)}; a cada tasa, el producto "
            f"compatible cambia en Δ(M/P)/k = {con_signo(self.desplazamiento_lm)}. La LM se desplaza hacia la "
            f"{'derecha (hacia abajo)' if expansiva else 'izquierda (hacia arriba)'}. La IS no cambia.",
            f"**Efecto sobre la inversión.** {self.inversion_frase()}",
            f"**Movimiento a lo largo de IS₀.** La {'mayor' if expansiva else 'menor'} inversión "
            f"{'eleva' if expansiva else 'reduce'} la demanda agregada y el multiplicador lo amplifica: "
            f"ΔY = ΔI/(1 − c) = {con_signo(self.dI)} × {numero(alfa, 2)} ≈ {con_signo(self.dY)}.",
            f"**Ajuste de la demanda de dinero.** Al {'subir' if expansiva else 'bajar'} el producto, la demanda de "
            f"dinero por transacciones {'aumenta' if expansiva else 'disminuye'} (k·ΔY = {con_signo(self.p0.k * self.dY)}). "
            f"Por eso la tasa cambia menos (Δi = {puntos_porcentuales(self.di)}) que el desplazamiento vertical "
            f"de la LM ({puntos_porcentuales(-self.dMP / self.p0.h)}).",
            f"**Efecto sobre el consumo.** {self.consumo()}",
            f"**Nuevo equilibrio.** E₁ = ({numero(self.e1.Y, 2)}; {porcentaje(self.e1.i)}), con "
            f"Δi = {puntos_porcentuales(self.di)} y ΔY = {con_signo(self.dY)}.",
        ]

    def pasos(self) -> list[str]:
        pasos = [self.paso_cambio_exogeno()]
        if self.mueve_is and not self.mueve_lm:
            pasos += self.pasos_is()
        elif self.mueve_lm and not self.mueve_is:
            pasos += self.pasos_lm()
        elif self.mueve_is and self.mueve_lm:
            pasos += [
                f"**Desplazamientos.** La IS se corre {con_signo(self.desplazamiento_is)} y la LM "
                f"{con_signo(self.desplazamiento_lm)} (a tasa constante).",
                f"**Nuevo equilibrio.** E₁ = ({numero(self.e1.Y, 2)}; {porcentaje(self.e1.i)}).",
            ]
        else:
            pasos.append("**Sin desplazamientos.** Los cambios se compensan y el equilibrio no varía.")
        pasos.append("**Comprobación.** En E₁ se cumplen a la vez Y = C + I + G y M/P = L(Y, i).")
        return pasos

    def interpretacion(self) -> Interpretacion:
        return Interpretacion(self.titulo(), self.resumen(), self.pasos(), self.hay_crowding_out())
