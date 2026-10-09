# Simulador interactivo del modelo IS-LM

Aplicación web educativa para estudiar el modelo IS-LM de una economía cerrada con precios
fijos. Parte de un equilibrio inicial calibrado y permite aplicar shocks fiscales, monetarios
y de inversión para ver cómo se desplazan las curvas IS y LM y cómo cambian el producto, la
tasa de interés, el consumo y la inversión.

## 1. Objetivo

Que un estudiante pueda seguir visualmente la cadena completa:

> shock exógeno → desplazamiento de la IS o de la LM → nuevo equilibrio → variación del
> producto y de la tasa de interés → efectos sobre el consumo y la inversión.

Todos los resultados se calculan con las ecuaciones del modelo, sin aproximaciones. Los textos
de interpretación se generan con reglas fijas a partir de esos resultados; la aplicación no usa
inteligencia artificial.

## 2. Bibliografía

José De Gregorio, *Macroeconomía*, capítulo 19: «El modelo keynesiano de economía cerrada:
IS-LM», pp. 499–527. La pestaña **Marco teórico** indica para cada concepto la sección, las
páginas y las ecuaciones o figuras del capítulo de las que surge.

## 3. Ecuaciones principales

El libro trabaja con funciones generales I(r) y L(i, Y); el simulador usa sus versiones lineales.

| Relación | Ecuación |
|---|---|
| Ingreso disponible | Yd = Y − T |
| Consumo | C = C₀ + c·(Y − T) |
| Inversión | I = I₀ − b·i |
| Equilibrio del mercado de bienes | Y = C + I + G |
| Curva IS | i = Ā/b − [(1 − c)/b]·Y, con Ā = C₀ − c·T + I₀ + G |
| Demanda de dinero (saldos reales) | L = k·Y − h·i |
| Equilibrio del mercado de dinero (LM) | M/P = k·Y − h·i ⇒ i = (k/h)·Y − (M/P)/h |
| Equilibrio IS-LM | Y\* = [h·Ā + b·(M/P)] / D,  i\* = [k·Ā − (1 − c)·(M/P)] / D,  con D = h(1 − c) + b·k |

Multiplicadores:

| Multiplicador | Fórmula | Valor |
|---|---|---|
| Simple (tasa constante) | 1/(1 − c) | 2,5 |
| Simple de impuestos | −c/(1 − c) | −1,5 |
| IS-LM del gasto público y de I₀ | dY/dG = h/D | 10/7 ≈ 1,43 |
| IS-LM de impuestos | dY/dT = −c·h/D | −6/7 ≈ −0,86 |
| Monetario | dY/d(M/P) = b/D | 5/7 ≈ 0,71 |
| Efecto de M/P sobre la tasa | di/d(M/P) = −(1 − c)/D | −1/14 ≈ −0,071 p.p. |

## 4. Variables del modelo

| Tipo | Variables |
|---|---|
| Endógenas | Producto Y, tasa de interés i, ingreso disponible Yd, consumo C, inversión I, demanda de dinero L |
| Exógenas que se pueden modificar | Gasto público G, impuestos T, inversión autónoma I₀, oferta monetaria real M/P |
| Parámetros fijos | Consumo autónomo C₀ = 17, propensión marginal a consumir c = 0,60, sensibilidad de la inversión b = 4, sensibilidades de la demanda de dinero k = 0,60 y h = 8, nivel de precios P = 1 |

La tasa de interés se expresa en puntos porcentuales: i = 5 significa 5%. Sus variaciones se
informan en puntos porcentuales (p.p.).

## 5. Equilibrio inicial

| Variable | Valor |
|---|---|
| Producto, Y₀ | 100 |
| Tasa de interés, i₀ | 5% |
| Consumo, C | 65 |
| Inversión, I | 15 |
| Gasto público, G | 20 |
| Impuestos, T | 20 |
| Oferta monetaria real, M/P | 20 |

- IS₀: i = 15 − 0,10·Y
- LM₀: i = 0,075·Y − 2,5
- E₀ = (100; 5%). Se cumple C + I + G = 65 + 15 + 20 = 100 = Y y L = 0,6·100 − 8·5 = 20 = M/P.

## 6. Políticas y shocks que pueden simularse

| Intervención | Variable | Rango del control | Curva | Efecto en el modelo |
|---|---|---|---|---|
| Política fiscal expansiva | G ↑ o T ↓ | G: 0 a 50 · T: 0 a 40 | IS a la derecha | Y ↑, i ↑, crowding out |
| Política fiscal contractiva | G ↓ o T ↑ | ídem | IS a la izquierda | Y ↓, i ↓ |
| Política monetaria expansiva | M/P ↑ | 5 a 60 | LM a la derecha | Y ↑, i ↓ |
| Política monetaria contractiva | M/P ↓ | ídem | LM a la izquierda | Y ↓, i ↑ |
| Shock positivo de inversión (privado) | I₀ ↑ | 15 a 55 | IS a la derecha | Y ↑, i ↑ |
| Shock negativo de inversión (privado) | I₀ ↓ | ídem | IS a la izquierda | Y ↓, i ↓ |

Un cambio de I₀ es un shock privado: la aplicación nunca lo presenta como política fiscal.
Con un shock por vez, todos los valores de los controles dejan el equilibrio dentro del gráfico.

## 7. Instalación

Requiere Python 3.10 o superior.

```bash
pip install -r requirements.txt
```

Opcionalmente, en un entorno virtual:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 8. Ejecución

Desde la carpeta del proyecto:

```bash
streamlit run app.py
```

La aplicación se abre en el navegador (por defecto, http://localhost:8501). Conviene ejecutarla
desde esta carpeta para que se aplique el tema visual definido en `.streamlit/config.toml`.

## 9. Uso de cada pestaña

**Inicio / Modelo base.** Muestra el equilibrio inicial en tarjetas, el gráfico IS-LM y las
ecuaciones de las curvas. Las funciones de comportamiento, la derivación de las curvas, los
parámetros y la verificación del equilibrio están en secciones desplegables.

**Mercado de bienes.** Mové G, T o I₀; debajo de cada control se ven el valor base, el nuevo
valor y la variación. Presioná **Aplicar shock** para calcular el nuevo equilibrio. Cada shock
parte del escenario base: al mover un control, los otros vuelven a su valor inicial. Para
acumular cambios en varias variables, activá **Combinar shocks**. El gráfico muestra IS₀
(tenue), IS₁, LM₀, E₀ y E₁; las tarjetas muestran ΔY, Δi, ΔC y ΔI. Debajo hay una interpretación
breve y desplegables con la tabla de resultados, los multiplicadores, el crowding out, las
ecuaciones y la verificación numérica.

**Mercado de dinero.** Elegí la oferta monetaria real M/P y presioná **Aplicar shock**. La LM
se desplaza y la economía se mueve a lo largo de IS₀. Se muestra el mecanismo de transmisión
(M/P ↑ → exceso de oferta de dinero → i ↓ → I ↑ → Y ↑, o el inverso) y los multiplicadores
monetarios.

**Comparar políticas.** Elegí el tipo de shock y la magnitud de los escenarios A y B y presioná
**Aplicar escenarios**. Ambos parten del mismo equilibrio base y se calculan por separado. Se
muestran tarjetas con ΔY, Δi, ΔC y ΔI de cada escenario, un gráfico (A y B, solo A o solo B),
qué escenario genera el mayor cambio en cada variable y una interpretación descriptiva. La
comparación no juzga qué intervención es preferible.

**Marco teórico.** Síntesis de los conceptos del modelo con sus fuentes en el capítulo 19, los
supuestos del simulador y sus limitaciones.

En las tres pestañas de simulación, **Restablecer** vuelve al escenario base y los desplegables
**¿Qué ocurrió en el modelo?** explican paso a paso la transmisión de cada shock. El botón
**Cómo usar** (en Inicio y en las pestañas de simulación) resume las instrucciones.

## 10. Supuestos

- Precios fijos (P = 1): la demanda determina el producto.
- Economía cerrada: no hay comercio exterior ni flujos de capital.
- Tasa de interés única: con inflación esperada nula, la tasa nominal y la real coinciden.
- Impuestos de suma fija: T no depende del ingreso.
- Expectativas de inflación iguales a cero.
- Parámetros estructurales constantes (c, b, k y h).
- Funciones de inversión y de demanda de dinero lineales.
- Estática comparativa: se comparan el equilibrio inicial y el final; no se modela el ajuste en
  el tiempo.

## 11. Limitaciones

- El IS-LM es una representación simplificada de la economía: sirve para entender mecanismos y
  la dirección de los efectos, pero no constituye una predicción empírica.
- Los parámetros están calibrados con fines pedagógicos, no estimados con datos; las magnitudes
  dependen de esa calibración.
- El modelo deja fuera la oferta agregada y el ajuste de precios, el sector externo, las
  expectativas, la restricción presupuestaria intertemporal del gobierno, la equivalencia
  ricardiana, el efecto riqueza y la trampa de la liquidez.
- Si una combinación de shocks lleva el equilibrio fuera del gráfico (50 ≤ Y ≤ 150,
  0 ≤ i ≤ 10) o a una inversión negativa, la aplicación muestra una advertencia con el valor
  exacto, sin recortarlo.

## 12. Estructura del proyecto

```
app.py                    Página principal: arma las cinco pestañas
requirements.txt          Dependencias (Streamlit y Plotly)
.streamlit/config.toml    Tema visual
islm/                     Lógica económica, sin dependencia de la interfaz
  model.py                Ecuaciones del modelo y equilibrio
  config.py               Calibración base, ventana del gráfico y rangos de los controles
  shocks.py               Comparación de equilibrios y control de dominio
  mercado_bienes.py       Shocks de G, T e I₀: multiplicadores, clasificación, crowding out
  mercado_dinero.py       Shocks de M/P: multiplicadores monetarios y controles de signo
  comparacion.py          Escenarios A y B
  interpretacion.py       Interpretación económica por reglas
  charts.py               Gráfico IS-LM (Plotly)
  formatting.py           Formato de números y ecuaciones
vistas/                   Interfaz Streamlit (una vista por pestaña y componentes comunes)
tests/                    Pruebas automáticas (opcionales)
pytest.ini                Configuración de las pruebas
```

### Pruebas (opcional)

No son necesarias para usar la aplicación. Para ejecutarlas:

```bash
pip install pytest
pytest
```

Incluyen la verificación exacta del motor (aritmética racional), un solver independiente para
la auditoría, todos los valores de los controles, casos límite, la interfaz y la consistencia
de los textos.
