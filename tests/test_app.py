"""Pruebas de la interfaz: navegación, flujo borrador → «Aplicar shock», resultados y textos."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parent.parent / "app.py"
PESTANAS = ["Inicio / Modelo base", "Mercado de bienes", "Mercado de dinero", "Comparar políticas", "Marco teórico"]


def nueva_app() -> AppTest:
    return AppTest.from_file(str(APP), default_timeout=30).run()


def pestana(at: AppTest, etiqueta: str):
    return next(t for t in at.tabs if t.label == etiqueta)


def textos(contenedor) -> str:
    return "\n".join(m.value for m in contenedor.markdown)


def tarjetas(contenedor) -> dict[str, str]:
    return {m.label: m.value for m in contenedor.metric}


def aplicar_bienes(at: AppTest, **niveles) -> AppTest:
    for var, nivel in niveles.items():
        at.slider(key=f"bienes_{var}").set_value(nivel).run()
    return at.button(key="bienes_aplicar").click().run()


def aplicar_dinero(at: AppTest, nivel: int) -> AppTest:
    at.slider(key="dinero_MP").set_value(nivel).run()
    return at.button(key="dinero_aplicar").click().run()


# --- Inicio ---------------------------------------------------------------------------------

def test_inicio_tarjetas_grafico_y_ecuaciones():
    at = nueva_app()
    assert not at.exception
    assert at.title[0].value == "Simulador interactivo del modelo IS-LM"
    assert [t.label for t in at.tabs if t.label in PESTANAS] == PESTANAS
    inicio = pestana(at, "Inicio / Modelo base")
    assert tarjetas(inicio) == {
        "Producto, Y₀": "100",
        "Tasa de interés, i₀": "5%",
        "Consumo, C": "65",
        "Inversión, I": "15",
        "Gasto público, G": "20",
    }
    ecuaciones = "\n".join(l.value for l in inicio.latex)
    assert r"\boxed{i = 15 - 0{,}10\,Y}" in ecuaciones
    assert r"\boxed{i = 0{,}075\,Y - 2{,}5}" in ecuaciones
    assert r"E_0 = (Y_0;\ i_0) = (100;\ 5\%)" in ecuaciones
    assert "✗" not in textos(inicio) and textos(inicio).count("✓") == 2


# --- Mercado de bienes ----------------------------------------------------------------------

def test_bienes_arranca_en_base_y_sin_cambios_pendientes():
    at = nueva_app()
    bienes = pestana(at, "Mercado de bienes")
    assert {s.key: (s.value, s.min, s.max) for s in bienes.slider} == {
        "bienes_G": (20, 0, 50),
        "bienes_T": (20, 0, 40),
        "bienes_I0": (35, 15, 55),
    }
    assert at.button(key="bienes_aplicar").disabled
    assert "Aplicar shock" in bienes.info[0].value


def test_bienes_el_borrador_no_calcula_hasta_aplicar():
    at = nueva_app()
    at.slider(key="bienes_G").set_value(40).run()
    bienes = pestana(at, "Mercado de bienes")
    assert "Base&nbsp;**20** &nbsp;·&nbsp; Nuevo&nbsp;**40** &nbsp;·&nbsp; Δ&nbsp;**+20**" in textos(bienes)
    assert not at.button(key="bienes_aplicar").disabled
    assert not tarjetas(bienes)  # todavía no hay resultados
    at.button(key="bienes_aplicar").click().run()
    assert at.button(key="bienes_aplicar").disabled


def test_politica_fiscal_expansiva():
    at = aplicar_bienes(nueva_app(), G=40)
    assert not at.exception
    bienes = pestana(at, "Mercado de bienes")
    assert tarjetas(bienes) == {
        "ΔY · Producto": "+28,57",
        "Δi · Tasa de interés": "+2,14 p.p.",
        "ΔC · Consumo": "+17,14",
        "ΔI · Inversión": "-8,57",
    }
    contenido = textos(bienes)
    assert ":blue-badge[Política fiscal expansiva]" in contenido
    assert "**Crowding out**" in "\n".join(c.value for c in bienes.caption)
    assert "constituye una política fiscal expansiva" in contenido
    assert "efecto de crowding out" in contenido
    assert "**Movimiento a lo largo de LM₀.**" in contenido
    etiquetas = [e.label for e in bienes.expander]
    for esperado in ("Tabla de resultados", "Multiplicadores", "Crowding out (efecto desplazamiento)",
                     "Ecuaciones y lectura del gráfico", "Verificación numérica", "¿Qué ocurrió en el modelo?"):
        assert esperado in etiquetas
    assert contenido.count("✓") == 6 and "✗" not in contenido
    assert not bienes.warning


def test_shock_de_inversion_no_es_politica_fiscal():
    at = aplicar_bienes(nueva_app(), I0=15)
    contenido = textos(pestana(at, "Mercado de bienes"))
    assert ":violet-badge[Shock negativo de inversión]" in contenido
    assert "política fiscal" not in contenido.lower()


def test_los_shocks_no_se_acumulan():
    at = nueva_app()
    at.slider(key="bienes_G").set_value(40).run()
    at.slider(key="bienes_T").set_value(30).run()
    assert at.slider(key="bienes_G").value == 20  # al mover T, G vuelve a su valor base
    at.button(key="bienes_aplicar").click().run()
    bienes = pestana(at, "Mercado de bienes")
    assert ":blue-badge[Política fiscal contractiva]" in textos(bienes)
    assert tarjetas(bienes)["ΔY · Producto"] == "-8,57"


def test_combinar_shocks_y_advertencia_fuera_de_dominio():
    at = nueva_app()
    at.checkbox(key="bienes_combinar").check().run()
    at = aplicar_bienes(at, G=50, I0=55)
    assert at.slider(key="bienes_G").value == 50  # con combinación activa, se acumula
    bienes = pestana(at, "Mercado de bienes")
    assert len(bienes.warning) == 1
    assert "fuera del dominio permitido" in bienes.warning[0].value
    assert "Y₁ = 171,43" in bienes.warning[0].value and "i₁ = 10,36%" in bienes.warning[0].value


def test_restablecer_bienes():
    at = nueva_app()
    at.checkbox(key="bienes_combinar").check().run()
    at = aplicar_bienes(at, G=45, T=10)
    at.button(key="bienes_restablecer").click().run()
    bienes = pestana(at, "Mercado de bienes")
    assert {s.key: s.value for s in bienes.slider} == {"bienes_G": 20, "bienes_T": 20, "bienes_I0": 35}
    assert at.checkbox(key="bienes_combinar").value is False
    assert "Aplicar shock" in bienes.info[0].value and not tarjetas(bienes)


# --- Mercado de dinero ----------------------------------------------------------------------

def test_dinero_arranca_en_base():
    at = nueva_app()
    s = at.slider(key="dinero_MP")
    assert (s.value, s.min, s.max) == (20, 5, 60)
    assert at.button(key="dinero_aplicar").disabled
    assert "Aplicar shock" in pestana(at, "Mercado de dinero").info[0].value


def test_politica_monetaria_expansiva():
    at = aplicar_dinero(nueva_app(), 30)
    assert not at.exception
    dinero = pestana(at, "Mercado de dinero")
    assert tarjetas(dinero) == {
        "ΔY · Producto": "+7,14",
        "Δi · Tasa de interés": "-0,71 p.p.",
        "ΔC · Consumo": "+4,29",
        "ΔI · Inversión": "+2,86",
    }
    contenido = textos(dinero)
    assert ":green-badge[Política monetaria expansiva]" in contenido
    assert "**M/P ↑ → exceso de oferta de dinero → i ↓ → I ↑ → Y ↑**" in contenido
    assert "Oferta real M/P: 20 → 30 · Demanda de dinero L: 20 → 30" in "\n".join(c.value for c in dinero.caption)
    assert "desplaza la curva LM hacia la derecha (hacia abajo)" in contenido
    assert contenido.count("✓") == 14 and "✗" not in contenido  # 6 controles + 8 signos
    assert not dinero.warning


def test_politica_monetaria_contractiva():
    at = aplicar_dinero(nueva_app(), 10)
    dinero = pestana(at, "Mercado de dinero")
    assert tarjetas(dinero)["ΔY · Producto"] == "-7,14"
    assert tarjetas(dinero)["Δi · Tasa de interés"] == "+0,71 p.p."
    contenido = textos(dinero)
    assert ":green-badge[Política monetaria contractiva]" in contenido
    assert "**M/P ↓ → exceso de demanda de dinero → i ↑ → I ↓ → Y ↓**" in contenido
    assert "**Movimiento a lo largo de IS₀.**" in contenido
    assert contenido.count("✓") == 14 and "✗" not in contenido


def test_restablecer_dinero():
    at = aplicar_dinero(nueva_app(), 45)
    at.button(key="dinero_restablecer").click().run()
    assert at.slider(key="dinero_MP").value == 20
    assert "Aplicar shock" in pestana(at, "Mercado de dinero").info[0].value


# --- Comparar políticas ---------------------------------------------------------------------

def test_comparacion_por_defecto_fiscal_vs_monetaria():
    at = nueva_app()
    comp = pestana(at, "Comparar políticas")
    valores = [m.value for m in comp.metric]
    # Cuatro tarjetas (ΔY, Δi, ΔC, ΔI), cada una con A y B.
    assert valores == ["+14,29", "+7,14", "+1,07 p.p.", "-0,71 p.p.", "+8,57", "+4,29", "-4,29", "+2,86"]
    contenido = textos(comp)
    assert "**Producción** &nbsp; :violet-badge[Escenario A]" in contenido
    assert "**Crowding out** &nbsp; :violet-badge[Escenario A]" in contenido
    assert "constituye una política fiscal expansiva" in contenido
    assert "constituye una política monetaria expansiva" in contenido
    assert "no indica que una intervención sea preferible" in contenido
    assert contenido.count("✓") == 10 and "✗" not in contenido


def test_comparacion_aplicar_y_ajustar_magnitud():
    at = nueva_app()
    at.slider(key="comp_A_magnitud").set_value(30).run()  # máximo de G ↑
    at.selectbox(key="comp_A_tipo").set_value("G-").run()  # máximo de G ↓ es 20
    assert at.slider(key="comp_A_magnitud").value == 20 and at.slider(key="comp_A_magnitud").max == 20
    assert not at.button(key="comp_aplicar").disabled
    at.button(key="comp_aplicar").click().run()
    assert not at.exception
    valores = [m.value for m in pestana(at, "Comparar políticas").metric]
    assert valores[0] == "-28,57" and valores[2] == "-2,14 p.p."


def test_comparacion_selector_y_restablecer():
    at = nueva_app()
    at.segmented_control(key="comp_vista").set_value("Solo B").run()
    at.selectbox(key="comp_B_tipo").set_value("T+").run()
    at.button(key="comp_aplicar").click().run()
    assert not at.exception
    at.button(key="comp_restablecer").click().run()
    assert at.selectbox(key="comp_A_tipo").value == "G+"
    assert at.selectbox(key="comp_B_tipo").value == "M+"
    assert at.slider(key="comp_B_magnitud").value == 10
    assert at.segmented_control(key="comp_vista").value == "A y B"


# --- Marco teórico --------------------------------------------------------------------------

def test_marco_teorico():
    at = nueva_app()
    teoria = pestana(at, "Marco teórico")
    assert teoria.header[0].value == "Marco teórico"
    assert "**1. Qué representa el modelo IS-LM**" in textos(teoria)
    titulos = [
        "Mercado de bienes", "Función de consumo", "Función de inversión", "Equilibrio del mercado de bienes",
        "Curva IS", "Mercado monetario", "Demanda de dinero", "Oferta monetaria real", "Curva LM",
        "Equilibrio IS-LM", "Política fiscal", "Política monetaria", "Multiplicador", "Crowding out",
    ]
    etiquetas = [e.label for e in teoria.expander]
    for n, titulo in enumerate(titulos, start=2):
        assert any(e.startswith(f"{n}. {titulo}") for e in etiquetas), titulo
    fuentes = [c.value for c in teoria.caption if "Fuente: De Gregorio, cap. 19" in c.value]
    assert len(fuentes) == 15
    contenido = textos(teoria)
    for supuesto in ("Precios fijos", "Economía cerrada", "Tasa de interés única", "Impuestos de suma fija",
                     "Expectativas de inflación iguales a cero", "Parámetros estructurales constantes",
                     "Estática comparativa"):
        assert f"**{supuesto}**" in contenido
    assert "no constituye una predicción empírica" in contenido
    formulas = "\n".join(l.value for l in teoria.latex)
    assert r"C = C_0 + c\,(Y - T)" in formulas and r"L = k\,Y - h\,i" in formulas
