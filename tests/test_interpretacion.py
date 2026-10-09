"""Coherencia entre la interpretación por reglas y los resultados del modelo."""

import itertools

import pytest

from islm.config import PARAMETROS_BASE as BASE
from islm.config import RANGO_OFERTA_REAL, RANGOS_BIENES
from islm.interpretacion import interpretar
from islm.model import equilibrio

TITULOS = {
    ("G", 1): "Política fiscal expansiva",
    ("G", -1): "Política fiscal contractiva",
    ("T", 1): "Política fiscal contractiva",
    ("T", -1): "Política fiscal expansiva",
    ("I0", 1): "Shock positivo de inversión",
    ("I0", -1): "Shock negativo de inversión",
    ("M/P", 1): "Política monetaria expansiva",
    ("M/P", -1): "Política monetaria contractiva",
}


def _todos_los_shocks_simples():
    for var, rango in RANGOS_BIENES.items():
        base = getattr(BASE, var)
        for nivel in range(int(rango.minimo), int(rango.maximo) + 1):
            if nivel != base:
                yield var, nivel, BASE.con_cambios(**{var: nivel})
    for nivel in range(int(RANGO_OFERTA_REAL.minimo), int(RANGO_OFERTA_REAL.maximo) + 1):
        if nivel != BASE.oferta_real:
            yield "M/P", nivel, BASE.con_cambios(M=nivel * BASE.P)


SHOCKS = list(_todos_los_shocks_simples())


def _signo(x):
    return (x > 1e-9) - (x < -1e-9)


@pytest.mark.parametrize("var, nivel, p1", SHOCKS, ids=[f"{v}={n}" for v, n, _ in SHOCKS])
def test_texto_coherente_con_los_resultados(var, nivel, p1):
    r = interpretar(BASE, p1)
    e0, e1 = equilibrio(BASE), equilibrio(p1)
    base = BASE.oferta_real if var == "M/P" else getattr(BASE, var)
    direccion = 1 if nivel > base else -1
    texto = r.texto
    pasos = " ".join(r.pasos)

    # 1-3. Variable, tipo y carácter expansivo/contractivo.
    assert r.titulo == TITULOS[(var, direccion)]
    simbolo = "I₀" if var == "I0" else var
    assert f"{simbolo}: " in texto
    if var == "I0":
        assert "shock privado" in texto and "no una política económica" in texto
        assert "política fiscal" not in texto.lower()

    # 4-5. Curva desplazada y dirección; la otra curva no se desplaza.
    curva, otra = ("LM", "IS") if var == "M/P" else ("IS", "LM")
    lado = "derecha" if (direccion > 0) != (var == "T") else "izquierda"
    assert f"desplaza la curva {curva} hacia la {lado}" in texto
    assert f"desplaza la curva {otra}" not in texto
    assert f"La {otra} no se desplaza: la economía se mueve a lo largo de {otra}₀" in texto
    assert f"**Desplazamiento de la {curva}.**" in pasos
    assert f"**Movimiento a lo largo de {otra}₀.**" in pasos

    # 6. Y, i, C e I con el signo correcto.
    dY, di, dC, dI = e1.Y - e0.Y, e1.i - e0.i, e1.C - e0.C, e1.I - e0.I
    assert ("un mayor nivel de producción" if dY > 0 else "un menor nivel de producción") in texto
    assert ("una tasa de interés más elevada" if di > 0 else "una tasa de interés más baja") in texto
    assert ("El consumo aumenta" if dC > 0 else "El consumo disminuye") in texto
    if var != "I0":
        assert ("La inversión aumenta" if dI > 0 else "La inversión disminuye") in texto

    # 7. Crowding out solo con política fiscal expansiva (que siempre sube la tasa).
    fiscal_expansiva = r.titulo == "Política fiscal expansiva"
    assert r.hay_crowding_out == fiscal_expansiva
    assert ("efecto de crowding out" in texto) == fiscal_expansiva
    if not fiscal_expansiva:
        assert "No hay crowding out" in texto

    # 8. Papel del multiplicador.
    assert "1/(1 − c) = 2,5" in texto

    # Formato.
    assert "p.p.." not in texto + pasos and "None" not in texto + pasos
    assert pasos.startswith("**Cambio exógeno.**") and r.pasos[-1].startswith("**Comprobación.**")


def test_estilo_del_ejemplo_politica_fiscal_expansiva():
    r = interpretar(BASE, BASE.con_cambios(G=30))
    assert r.resumen[0] == (
        "Un aumento del gasto público (G: 20 → 30) constituye una política fiscal expansiva. "
        "El incremento de G eleva directamente la demanda agregada (el gasto autónomo cambia en +10) "
        "y desplaza la curva IS hacia la derecha. La LM no se desplaza: la economía se mueve a lo "
        "largo de LM₀ hasta un nuevo equilibrio con un mayor nivel de producción (Y: 100 → 114,29) "
        "y una tasa de interés más elevada (i: 5% → 6,07%). Como M/P está fija, el mayor producto "
        "eleva la demanda de dinero y la tasa de interés sube."
    )
    assert "La suba de la tasa reduce parcialmente la inversión privada (en 4,29)" in r.resumen[1]
    assert "ΔY/ΔG ≈ 1,43" in r.resumen[2]


def test_politica_monetaria_expansiva_numeros():
    r = interpretar(BASE, BASE.con_cambios(M=30))
    assert "ΔY = ΔI/(1 − c) = +2,86 × 2,5 ≈ +7,14" in r.texto
    assert "exceso de oferta de 10" in " ".join(r.pasos)
    assert "dY/d(M/P) ≈ 0,71" in r.texto


def test_presupuesto_equilibrado_consumo_cae_aunque_suba_el_producto():
    r = interpretar(BASE, BASE.con_cambios(G=30, T=30))
    assert "constituyen una política fiscal expansiva" in r.texto
    assert "desplazan la curva IS hacia la derecha" in r.texto
    assert "un mayor nivel de producción" in r.texto
    assert "El consumo disminuye" in r.texto and "ΔYd = ΔY − ΔT" in r.texto


def test_cambios_que_se_compensan():
    # ΔG = c·ΔT: el gasto autónomo no cambia.
    r = interpretar(BASE, BASE.con_cambios(G=26, T=30))
    assert r.titulo == "Política fiscal neutra sobre la demanda"
    assert "la IS no se desplaza" in r.texto and "el equilibrio no cambia" in r.texto
    assert any("Sin desplazamientos" in p for p in r.pasos)
    assert not r.hay_crowding_out


@pytest.mark.parametrize(
    "G, T, I0", list(itertools.product((0, 20, 50), (0, 20, 40), (15, 35, 55)))
)
def test_shocks_combinados_del_mercado_de_bienes(G, T, I0):
    p1 = BASE.con_cambios(G=G, T=T, I0=I0)
    r = interpretar(BASE, p1)
    if (G, T, I0) == (20, 20, 35):
        assert r.titulo == "Sin cambios" and r.pasos == []
        return
    e0, e1 = equilibrio(BASE), equilibrio(p1)
    assert "desplaza la curva LM" not in r.texto
    if _signo(e1.Y - e0.Y):
        assert ("un mayor nivel" if e1.Y > e0.Y else "un menor nivel") in r.texto
    if I0 != 35:
        assert "shock privado" in r.texto
    assert "p.p.." not in r.texto + " ".join(r.pasos)


def test_sin_cambios():
    r = interpretar(BASE, BASE)
    assert r.titulo == "Sin cambios" and not r.pasos
