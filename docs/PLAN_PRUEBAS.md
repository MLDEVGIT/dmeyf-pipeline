# Plan de pruebas

Actualizado el 24-nov-2026. Requisitos en `CONSIGNA.md`, ganancia en `GANANCIA.md`, propuestas en
`RELEVAMIENTO.md` § 2.5. **Todas las decisiones se toman con 201901–201912 (R1).**

## 1. Particiones y disponibilidad del target

`clase_ternaria` del mes *t* sale de la **lista de clientes** de *t+1* y *t+2*
(`entrenamiento/legado/03_construir_target.py`):

| Caso | Necesita |
|---|---|
| BAJA+1: ausente en *t+1* | lista de *t+1* |
| BAJA+2: presente en *t+1*, ausente en *t+2* | listas de *t+1* y *t+2* |
| CONTINUA: presente en *t+1* y en *t+2* | listas de *t+1* y *t+2* |

| Mes | Rol | Features (historia que usan) | Etiqueta usa la presencia en | Etiqueta con datos hasta 201912 |
|---|---|---|---|---|
| 201901–201902 | Sólo historia | 201901 sin lags; 201902 sin lag2 | 201902–201904 | Completa, no se usa |
| 201903–201906 | **Entrenamiento** | 201901–201905 | 201904–201908 | Completa |
| 201907 | **Hueco**: sólo historia para agosto/septiembre | — | 201908–201909 | Completa, **no se usa** (ver abajo) |
| 201908 | **Desarrollo** y elección de cortes | 201906–201907 | 201909–201910 | Completa |
| 201909 | **Desarrollo** y elección de cortes | 201907–201908 | 201910–201911 | Completa |
| 201910 | **Evaluación final**, una sola vez | 201908–201909 | 201911–201912 | Completa, **reservada** |
| 201911 | Pendiente | 201909–201910 | 201912–**202001** | Sólo BAJA+1 (ausentes en 201912). BAJA+2/CONTINUA necesitan 202001 |
| 201912 | Pendiente | 201910–201911 | **202001–202002** | Ninguna |

**Cuándo se conoce cada etiqueta y por qué julio no entra.** La etiqueta completa del mes *t* se
conoce recién cuando llega la lista de clientes de *t+2*:

| Etiqueta de | Se conoce completa al recibir | Disponible para predecir agosto (llega 201908)? | ¿Y septiembre (llega 201909)? |
|---|---|---|---|
| 201906 | 201908 | Sí | Sí |
| 201907 | 201909 | **No**: falta saber quién sigue en septiembre | Sí |
| 201908 | 201910 | No | No |

Dos razones para cortar el entrenamiento en 201906:
1. **Simulación de producción.** Cuando llega agosto, el último mes con etiqueta completa es
   junio. Entrenar con julio usaría información que en producción no existe todavía.
2. **Fuga hacia el desarrollo.** Una BAJA+2 de julio está presente en agosto y ausente en
   septiembre: es exactamente una BAJA+1 de agosto. Entrenar con julio le daría al modelo parte de
   la etiqueta de agosto.

En general, un mes de entrenamiento *t* sirve para evaluar el mes *d* sólo si *t + 2 ≤ d*.

**Para septiembre, cortar en 201906 es conservador.** Julio ya estaría disponible, pero se usa el
mismo modelo para los dos meses de desarrollo, para que el corte elegido entre ambos sea comparable.
Para la evaluación final en 201910 se reentrena con 201903–201908 (= 201910 − 2), como pide
Zulip 211210.

**Octubre y las listas de clientes.** Etiquetar agosto y septiembre usa las **listas** de clientes de
octubre y noviembre (sólo `numero_de_cliente`), no las features ni la etiqueta de octubre. "Reservar
octubre" significa que no se miran sus features, scores ni etiquetas hasta la evaluación final.

**Noviembre y diciembre.** La única información que completaría sus etiquetas es la presencia de
cada cliente en **202001** (noviembre) y **202001–202002** (diciembre). Esa presencia está en los
archivos de 2020, fuera del período autorizado por R1. Es la contradicción registrada en
`CONSIGNA.md` (la presentación valida en 201911 y testea en 201912). Mientras no se aclare:
noviembre y diciembre sólo aportan historia; la BAJA+1 de noviembre, que sí se puede calcular, no se
usa sola porque sesgaría la clase.

`evaluacion/particiones.py` aplica esto en código: `leer_target` rechaza cualquier mes fuera de
201903–201906 y 201908–201909, y hay una prueba unitaria que lo comprueba.

## 2. Antecedente: octubre de 2019 ya se usó

| Dónde | Uso de 201910 | ¿Se eligió algo con 201910? |
|---|---|---|
| `dmeyf-experimento-sampling` (grupo, 1 al 13-nov-2026; README y `experimentos/control/docs/hipotesis.md`) | **Test** del control y de las variantes H1–H4. Métrica G: ganancia a N\* = 3.300 envíos con los importes de la cátedra, más ΔAUC al lado. **Dos rondas evaluadas en 201910**: final 201903–201906 con 10 semillas, y final 201903–201908 con 20 semillas (la vigente, por Zulip 211210). De ahí salen los veredictos por variante (gana / no pierde / pierde, con margen δ = 2 % de la ganancia del control en 201910) y la conclusión "achicar la optimización, no el entrenamiento final". | Hiperparámetros: no (Optuna valida en 201908). Corte: no (N\* = 3.300 se fijó con el control en 201908). **Conclusiones del experimento: sí**, salen de 201910. El valor de δ también depende de 201910. |
| `C:\dev\DMEyF\experimento_sampling\06_comparar_control_h3.py` y `07_sensibilidad_muestra_h3.py` (Martín) | No leen 201910: eligen y evalúan en 201908. | No |
| `C:\dev\DMEyF\experimento_sampling\08_evaluar_ganancia_h3.py` (Martín) | Ganancia en 201910 de los modelos de 07 (control y la elección de H3 por semilla), con N = 3.300 fijo y sin reentrenar; "una sola vez por configuración", según su docstring. | Según el script, no; sus resultados forman parte de lo que el grupo vio de 201910. |
| `C:\dev\DMEyF\experimento_sampling\05` y el pipeline mensual | No leen la etiqueta de 201910. | No |
| Este repo | No leyó la etiqueta de 201910; lo garantiza `particiones.py`. | No |

**Qué no es independiente en octubre:**
- la ganancia del LightGBM de control del baseline 208135 en ese mes;
- las conclusiones sobre optimizar con una muestra (H3, H4) y sobre la ventana 201903–201908.

**Cómo evaluar respetando el antecedente:**
1. **Las decisiones salen de agosto y septiembre**: elección entre estrategias, cortes y regla de
   recomendación. Octubre no decide nada.
2. **Ninguna conclusión del experimento de sampling decide entre A, B o A+B.** Si se adopta alguna,
   por ejemplo optimizar con una muestra para ahorrar tiempo, se marca "informada por 201910
   (experimento de sampling)" y se aplica igual a todas las estrategias, para que no favorezca a
   ninguna.
3. **Protocolo congelado:** antes de leer octubre se fija en un commit con tag `protocolo-final`:
   features, objetivos, hiperparámetros, semillas, fracciones de corte, regla de recomendación y
   el script de evaluación. El script de octubre verifica ese tag y corre una sola vez.
4. **Lo que se reporta de octubre**: el ordenamiento entre A, B y A+B, la ganancia en la fracción ya
   fijada y el arrepentimiento contra el máximo de octubre. Se reporta todo, aunque contradiga a
   desarrollo. La ganancia absoluta no se compara con el control del experimento de sampling.
5. **Evidencia de transferencia sin octubre**: cada experimento mide la transferencia cruzada del
   corte (elegido en agosto y medido en septiembre, y al revés). Es la evidencia principal de
   robustez temporal; octubre la confirma o no.

## 3. Detección, alerta y tratamiento de anomalías

| Etapa | Qué hace | Estado |
|---|---|---|
| **Detección** | Regla objetiva sobre el mes que llega, sin etiquetas: columna 100 % nula; todos los observados en 0; constante no nula; cambio > 20 pp en la tasa de nulos (`politica_incidentes.json`). A agregar: PSI por variable contra la referencia de 2019, con NaN como bin aparte. | Implementada, menos PSI |
| **Alerta** | Incidente en `reporte.json` y `reporte_acumulado.csv` con variable, regla y acción. `estado_calidad = con_alertas`. No bloquea. | Implementada |
| **Tratamiento** | Cambiar el dato antes de calcular features. **Hoy no hay ninguno**: el score usa el dato tal como llega. | No implementado |

**Sustitución automática por faltante (NA): no se adopta sin prueba.**
- *A favor:* LightGBM trata NA como faltante con una dirección aprendida. Un 0 por falla de carga se
  confunde con "no tiene el producto", que es un valor con significado.
- *En contra, con evidencia propia:* en la prueba de robustez del 2-nov sobre 202001, `mcaja_ahorro`
  en 0 dejó 827 de los 1.000 seleccionados originales, y `mcaja_ahorro` en NULL dejó **800**. Para
  esa variable, NA alteró más la selección que el 0. Además, el valor sustituido entra en la
  historia y cambia los lags del mes siguiente.

**Prueba E06** (tras E01, sobre el modelo ganador; meses de desarrollo):

| Variante | Qué se hace con las columnas detectadas en el mes |
|---|---|
| O | Original, sin inyección (referencia) |
| Z | Inyección del patrón de 202006: las 47 columnas con todos los observados en 0 pasan a 0, tal como llegaría |
| N | Z con tratamiento NA: esas columnas pasan a NULL antes de calcular features |
| L | Z con tratamiento "último valor": esas columnas toman el valor del mes anterior del cliente |

- *Inyección en un mes:* inyectar en 201909, recalcular features (crudas y deltas; los lags vienen
  de la historia) y medir: ganancia a la fracción f\* de E01, coincidencia del top-f\* con O y AUC.
- *Efecto en la historia:* inyectar en 201908 y puntuar 201909. Los lags de septiembre heredan el
  tratamiento de agosto.
- *Falsos positivos de la detección:* correr la regla sobre 201901–201909 y listar cada detección
  (hay casos conocidos en 201905). Una detección en un mes normal impide automatizar el tratamiento.
- *Regla de adopción, fijada de antemano:* N o L se adoptan sólo si recuperan más ganancia que Z en
  los dos escenarios y la detección no da falsos positivos en 2019. Si no, se queda en detectar y
  alertar, y el tratamiento sigue siendo una decisión humana registrada.

## 4. Pruebas incrementales

Cada paso cambia **una** cosa respecto del de referencia. Todos comparten:
- particiones del § 1;
- ganancia de `GANANCIA.md`;
- curva suavizada con media móvil de 501;
- corte por fracción con menor arrepentimiento máximo entre 201908 y 201909;
- transferencia cruzada;
- ganancia por semilla en el corte, con media, desvío y mínimo;
- envíos, memoria y tiempos.

| Paso | Pregunta | Cambia respecto de | Estado |
|---|---|---|---|
| **E01** | ¿Binario o multiclase, con features e hiperparámetros idénticos? | — | **Ejecutada** (§ 5): no se cumple la regla; binario sigue de referencia |
| E02 | Peso de BAJA+1 en el multiclase: 0,25, 0,5 y 1 (= E01) | E01 multiclase | Pendiente |
| E03 | Escalado monetario por mes, antes de lags: crudo (= E01), rank con cero fijo, división por la mediana mensual | Objetivo elegido en E01 | Pendiente; requiere cambiar `features.py` en entrenamiento **y** producción |
| E04 | Combinación por rangos de binario y multiclase | Predicciones guardadas de E01, sin reentrenar | Pendiente; costo bajo |
| E05 | Lags por calendario con indicador de disponibilidad contra lags por fila | El mejor de E01–E04 | Pendiente |
| E06 | Tratamiento de anomalías (§ 3) | Modelo elegido | Pendiente |
| T01 | Tiempo de inferencia con modelos representativos | Modelos de E01 | **Ejecutada** (§ 6) |
| F01 | Evaluación final en 201910, protocolo congelado (§ 2) | Todo lo anterior | Al final, una vez |

**Regla de decisión de E01, escrita antes de ver resultados.** Gana un objetivo si cumple las tres:
1. mayor ganancia del ensamble en su propia fracción, **en los dos** meses de desarrollo;
2. la diferencia pareada por semilla tiene el mismo signo en al menos 4 de 5 semillas, en cada mes;
3. no empeora la transferencia cruzada del corte.

Si no se cumplen las tres, se mantiene **binario** como referencia, que es el objetivo del
baseline 208135. Las mismas reglas valen para E02–E05 contra su referencia.

**Parámetros fijos de las comparaciones.** No están optimizados: sirven para comparar objetivos y
features en igualdad. La optimización (Optuna según 208135, validación 201908) va después, sobre la
configuración elegida.
- lr 0,05, 63 hojas, `min_data_in_leaf` 200, `feature_fraction` 0,5, sin bagging;
- 300 rondas;
- `deterministic`;
- 5 semillas.

## 5. Resultados de E01

Corrida `ejecuciones/e01/20261124T092205_3832` (24-nov, 09:22–10:08):
- 5 semillas, 300 rondas, parámetros del § 4;
- máquina de Martín: 8 hilos, 15,7 GB, Windows 11, Python 3.12.0, LightGBM 4.7.0.

Train: 506.871 filas (CONTINUA 501.558, BAJA+1 2.717, BAJA+2 2.596). Desarrollo: 201908 con 131.775
filas (543 BAJA+2) y 201909 con 133.419 (615 BAJA+2). Octubre no se leyó.

**Ganancia en el corte elegido** (millones, ganancia **sin suavizar** en el envío número
⌈*f*·n⌉).

Cómo leer las columnas:
- **Ensamble**: ganancia del **promedio de probabilidades** de las 5 semillas, ordenado y cortado
  una sola vez. Es lo que haría el pipeline en producción.
- **Semillas: media ± desvío** y **mín–máx**: ganancia de **cada semilla sola**, cortada en el mismo
  *f* del ensamble; después, media, desvío (n − 1) y extremos de esas 5 ganancias. **No es el
  ensamble.** Mide la estabilidad entre semillas.
- *f* se eligió con la curva **suavizada del ensamble** (menor arrepentimiento máximo entre
  agosto y septiembre). Como se eligió con estos mismos dos meses, las cifras son optimistas. La
  transferencia de la tabla siguiente es la medida fuera de muestra.
- Criterios de la regla: el 1 usa la columna Ensamble; el 2 compara las semillas una por una.

| Objetivo | *f* | Mes | Envíos | Ensamble | Semillas: media ± desvío | Mín–máx semillas | AUC BAJA+2 (ensamble) |
|---|---|---|---|---|---|---|---|
| Binario | 2,900 % | 201908 | 3.822 | 202,9 | 191,9 ± 1,9 | 188,6–193,0 | 0,9105 |
| | | 201909 | 3.870 | 250,0 | 243,6 ± 5,8 | 233,5–247,8 | 0,9092 |
| Multiclase, P(BAJA+2) | 2,800 % | 201908 | 3.690 | **208,7** | 196,8 ± 3,1 | 192,2–199,9 | 0,9061 |
| | | 201909 | 3.736 | **250,4** | 241,6 ± 4,2 | 237,2–248,2 | 0,9067 |
| Multiclase, P(B1)+P(B2) (diagnóstico) | 3,950 % | 201908 | 5.206 | 198,9 | 191,5 ± 7,1 | 182,4–200,0 | 0,9072 |
| | | 201909 | 5.271 | 247,7 | 244,2 ± 4,7 | 240,0–251,0 | 0,9081 |

**Transferencia del corte** (sobre el ensamble: *f* elegido con la curva suavizada de un mes y
aplicado al otro; arrepentimiento = pérdida relativa al máximo suavizado del mes medido):

| Objetivo | 201908 → 201909 | 201909 → 201908 | Peor caso |
|---|---|---|---|
| Binario | 2,725 % · 248,7 M · 1,0 % | 2,175 % · 196,2 M · 3,8 % | 3,8 % |
| Multiclase | 2,675 % · 250,6 M · 1,0 % | 2,850 % · 206,9 M · 0,5 % | **1,0 %** |
| Multiclase B1+B2 | 2,525 % · 244,0 M · 2,2 % | 4,250 % · 192,5 M · 3,1 % | 3,1 % |

**Comparación pareada por semilla** (multiclase − binario, cada uno en su *f*):
- 201908: +6,9, +4,7, +5,8, +8,0 y −0,8 M ⇒ 4 de 5 a favor del multiclase.
- 201909: −1,8, +0,4, +5,9, −5,1 y −9,5 M ⇒ 2 de 5.

**Decisión según la regla fijada antes de correr:**

| Criterio | ¿Se cumple? |
|---|---|
| 1. Mayor ganancia del ensamble en los dos meses | Sí: +5,8 M en agosto, +0,4 M en septiembre |
| 2. Mismo signo en ≥ 4 de 5 semillas en cada mes | Agosto sí; **septiembre no (2 de 5)** |
| 3. No empeora la transferencia | Sí: peor caso 1,0 % contra 3,8 % |

⇒ **No se cumple la regla: el binario sigue como referencia.** El multiclase queda como candidato con
señal a favor en agosto y en la transferencia del corte, y empate en septiembre. E02 (peso de BAJA+1)
parte del multiclase de E01.

**Otras observaciones:**
- El ensamble de 5 semillas supera a la semilla media en 11–12 M en agosto y en 6–9 M en septiembre:
  promediar semillas aporta más que la diferencia entre objetivos.
- El AUC de BAJA+2 es mayor en el binario (0,909–0,911 contra 0,906–0,907), aunque la ganancia en el
  corte favorece al multiclase: el AUC no ordena igual que la ganancia en la zona de corte.
- El corte óptimo está entre 2,2 % y 2,9 % de los clientes (unos 2.900–3.900 envíos). El cupo
  diagnóstico de 1.000 queda muy por debajo.

**Tiempo y memoria** (8 hilos para entrenar, 4 para predecir, como el pipeline):

| | Binario | Multiclase |
|---|---|---|
| Entrenar 300 rondas (5 semillas) | 104–166 s, media 131 s | 330–396 s, media 368 s |
| Predecir un mes de desarrollo (~132 mil filas) | 2,8–5,2 s | 10,1–16,0 s |

Carga de datos: 71 s. Binado: 32 s. Total: 2.774 s.
Memoria: pico de working set 5,45 GB, durante la carga y el binado (matrices float64 de train y desarrollo más el Dataset);
2,0–2,4 GB durante el entrenamiento.

## 6. Tiempos de inferencia (T01)

Corrida `ejecuciones/t01/20261124T101351`, en la misma máquina, después de E01, sin otra carga del
experimento. Modelos de E01 (63 hojas). `predict` puro sobre 201909 (133.419 filas × 760, float64),
mediana de 3 repeticiones. Se hicieron dos corridas: la primera falló en la parte punta a punta (ver
abajo). La tabla muestra la segunda, con la primera entre paréntesis.

**Medido:**

| Modelo | Árboles | 4 hilos (s) | 8 hilos (s) |
|---|---|---|---|
| Binario | 100 | 2,4 (2,0) | 1,3 (1,1) |
| | 200 | 3,7 (3,2) | 2,7 (2,9) |
| | 300 | 5,2 (5,4) | 4,0 (4,2) |
| Multiclase (3 árboles por ronda) | 100 rondas | 5,0 (6,0) | 3,3 (3,4) |
| | 200 rondas | 11,6 (11,6) | 5,7 (8,2) |
| | 300 rondas | 16,6 (16,1) | 10,7 (10,8) |

Pendiente con 4 hilos: **0,014 s por ronda** en el binario y **0,058 s por ronda** en el multiclase,
cada 133 mil filas. La variación entre corridas es de hasta ±20 %, por la carga de la máquina.

**Medido punta a punta** con el pipeline real (`ejecutar_mes`) sobre 202001 (142.929 clientes,
ensayo operativo), con el modelo binario de 300 rondas de E01:
- total **57,0 s**: validación 14,8 · features 22,0 · inferencia 17,8 · estrategias 2,0;
- pared 63,3 s; pico de working set 3,0 GB; pico de commit 4,0 GB;
- la salida pasó los 11 chequeos de `scripts/verificar_salida.py`.

La etapa de inferencia tardó casi lo mismo que con el modelo diagnóstico de 100 árboles (17,3 s):
**unos 12 s son conversión de datos** (lectura por bloques con DuckDB en un hilo y paso a float64),
no `predict`. Es un costo fijo que se puede bajar.

**Ensambles: qué se midió y qué no.**
- T01 midió **un modelo por vez**. Ningún `predict` de un ensamble se midió como una sola
  operación.
- Lo más parecido medido es la **suma de los `predict` individuales de E01** (5 semillas de 300
  rondas, una tras otra, 4 hilos, sobre ~132 mil filas):

| Mes | Binario: suma de 5 semillas (medido) | Multiclase: suma de 5 semillas (medido) | Estimación lineal para el mismo caso |
|---|---|---|---|
| 201908 (131.775 filas) | 18,9 s | 66,2 s | 25,6 s · 83,2 s |
| 201909 (133.419 filas) | 18,3 s | 62,9 s | 25,9 s · 84,2 s |

  Para este caso, la estimación lineal sobreestima entre un 26 % y un 41 %: es conservadora.
  Promediar las probabilidades cuesta milisegundos y no cambia el total.
- **Lo que no se midió**: más de 300 rondas, más de 5 semillas, más de 63 hojas, y dos estrategias en
  el mismo proceso del pipeline.

**Estimaciones** (no medidas). Son lineales en rondas y semillas a partir de la pendiente medida,
escaladas a 153.000 filas (202006), con 4 hilos. No incluyen la conversión ni el resto del pipeline,
unos 45–60 s.

| Configuración | Binario | Multiclase |
|---|---|---|
| 300 rondas × 5 semillas | 30 s | 97 s |
| 300 rondas × 20 semillas | 119 s | 386 s |
| 1.000 rondas × 5 semillas | 87 s | 330 s |
| 1.000 rondas × 10 semillas | 174 s | 659 s |
| 1.000 rondas × 20 semillas | 348 s | **1.318 s (no entra en 15 min)** |

**Implicancia para el presupuesto** (a confirmar en la máquina del vivo, T12): dos estrategias con 5–10
semillas de hasta 1.000 rondas entran con margen si una es binaria. Un multiclase de 1.000 rondas
con más de ~10 semillas no entra junto con otra estrategia. Con más de 63 hojas, `predict` es más
lento; no se midió.

**Incidente de la primera corrida de T01.** La copia del modelo con los nombres de features se
escribió con `write_text`, que en Windows convierte los fines de línea a `\r\n`. LightGBM no pudo
leer los árboles (`Model format error`). Se corrigió escribiendo en bytes y verificando que la copia
prediga igual que el original. Las mediciones de `predict` de esa corrida son válidas y figuran entre
paréntesis.
