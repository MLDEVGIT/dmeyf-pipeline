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
| E02 | Peso de BAJA+1 en el multiclase: 0,5 contra 1 (= E01). El peso 0,25 queda fuera de esta corrida (§ 7) | E01 multiclase | **Ejecutada** (§ 8): 0,5 no se adopta; queda peso 1; el binario sigue de referencia |
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

## 7. E02 — peso de BAJA+1 en el multiclase (protocolo, escrito antes de correr)

Rama `martin/e02-peso-baja1`. Script: `experimentos/e02_peso_baja1.py`.

**Qué cambia respecto de E01:** sólo el peso de las filas BAJA+1 en el `Dataset` multiclase, que pasa
de 1 a **0,5**. CONTINUA y BAJA+2 siguen con peso 1. Todo lo demás es idéntico a E01:
- las 760 features;
- particiones: train 201903–201906, desarrollo 201908 y 201909, octubre bloqueado;
- las 5 semillas, los hiperparámetros y las 300 rondas;
- el binado (`max_bin` 255, `data_random_seed` 1);
- 8 hilos para entrenar y 4 para predecir.

El score es P(BAJA+2). El script se detiene si la configuración de E01 o la composición del train no
coinciden.

**Peso 0,25.** Estaba en la lista inicial de E02, pero la tarea pedida compara 1 contra 0,5. Queda como
extensión: correrlo después y presentarlo como exploratorio no invalida esta decisión.

**Reutilización de E01.** El brazo de peso 1 son exactamente los modelos multiclase de E01 (mismo
código, datos, semillas y parámetros, sin pesos), y el binario de E01 es la referencia del proyecto.
No se reentrenan. Se reutilizan sólo si pasan tres comprobaciones; si alguna falla, se reentrenan:
1. filas, clases y clientes de agosto y septiembre idénticos a los de E01;
2. los modelos guardados de E01, vueltos a predecir acá, reproducen exactamente las predicciones que
   E01 guardó;
3. la evaluación de `evaluacion/comparacion.py` reproduce las cifras de `resultados.json` de E01:
   fracción, envíos, ganancias del ensamble y por semilla, y transferencias.

**Métricas** (`evaluacion/comparacion.py`, idéntica a E01):
- ganancia del ensamble de probabilidades en la fracción de cada brazo;
- ganancia por semilla en esa fracción y diferencias pareadas por semilla y mes;
- transferencia del corte entre agosto y septiembre;
- estabilidad del corte: la fracción que elegiría cada semilla sola;
- AUC de BAJA+2, tiempos y memoria.

**Regla de adopción** (la misma de E01, en dos pasos):
1. **Peso 0,5 contra peso 1.** Se adopta 0,5 sólo si se cumplen las tres condiciones:
   - mayor ganancia del ensamble en su fracción, en 201908 **y** en 201909;
   - diferencia pareada positiva en al menos 4 de 5 semillas en **cada** mes;
   - peor caso de transferencia del corte no mayor que el de peso 1.

   Si no se cumplen, queda peso 1.
2. **Multiclase elegido contra binario de E01**, con la misma regla. Si la cumple, el multiclase pasa a
   ser la referencia del proyecto para E03. Si no, el binario sigue de referencia.

El otro multiclase también se compara con el binario, solo como diagnóstico, sin efecto en la decisión.

**Limitaciones conocidas de antemano:**
- 5 semillas y 2 meses: la regla de 4 de 5 es exigente y una diferencia chica puede no alcanzarla
  aunque exista.
- Hiperparámetros fijos, no optimizados para ningún brazo. Un peso distinto podría requerir otros
  hiperparámetros.
- El corte se elige con los mismos dos meses en que se mide; la transferencia es la medida fuera de
  muestra.

## 8. Resultados de E02

Corrida `ejecuciones/e02/20261124T161122_13560` (24-nov, 16:11–17:07, 3.391 s). Resumen versionado:
`resultados/e02_peso_baja1.json`, sin datos por cliente.
- **Regla fijada antes de correr:** el sha256 de `PLAN_PRUEBAS.md` registrado al inicio
  (`03ee1d46e616…`) es el del archivo con el § 7 y sin este § 8.
- **Compatibilidad con E01: total.** Coinciden los datos de desarrollo, las 20 predicciones repetidas
  con los modelos de E01 (binario y multiclase, bit a bit en float32) y las cifras recalculadas
  (fracción, envíos y ganancias del ensamble, por semilla y de transferencia). El binario y el
  multiclase de peso 1 no se reentrenaron. Train: 506.871 filas; suma de pesos con BAJA+1 a 0,5:
  505.512,5.

**Ganancia en el corte de cada brazo** (millones). "Ensamble" = promedio de probabilidades de las 5
semillas; "semillas" = cada semilla sola en la misma fracción. Ganancia sin suavizar.

| Brazo | *f* | Mes | Envíos | Ensamble | Semillas: media ± desvío | AUC BAJA+2 |
|---|---|---|---|---|---|---|
| Binario (E01) | 2,900 % | 201908 | 3.822 | 202,9 | 191,9 ± 1,9 | 0,9105 |
| | | 201909 | 3.870 | 250,0 | 243,6 ± 5,8 | 0,9092 |
| Multiclase, peso 1 (E01) | 2,800 % | 201908 | 3.690 | **208,7** | 196,8 ± 3,1 | 0,9061 |
| | | 201909 | 3.736 | 250,4 | 241,6 ± 4,2 | 0,9067 |
| Multiclase, peso 0,5 | 2,850 % | 201908 | 3.756 | 202,5 | 192,4 ± 6,4 | 0,9049 |
| | | 201909 | 3.803 | **256,2** | 243,9 ± 4,4 | 0,9061 |

**Diferencias pareadas por semilla y mes** (millones, cada brazo en su fracción; semillas 20261124 a
20261128):

| Comparación | Mes | Por semilla | A favor | Media | Ensamble |
|---|---|---|---|---|---|
| Peso 0,5 − peso 1 | 201908 | +3,7 · +0,4 · −13,9 · −7,3 · −5,1 | 2 de 5 | −4,5 | −6,2 |
| | 201909 | +2,6 · −5,1 · +1,5 · +10,3 · +2,6 | 4 de 5 | +2,3 | +5,9 |
| Peso 1 − binario | 201908 | +6,9 · +4,7 · +5,8 · +8,0 · −0,8 | 4 de 5 | +5,0 | +5,8 |
| | 201909 | −1,8 · +0,4 · +5,9 · −5,1 · −9,5 | 2 de 5 | −2,0 | +0,4 |
| Peso 0,5 − binario (diagnóstico) | 201908 | +10,6 · +5,1 · −8,1 · +0,7 · −5,9 | 3 de 5 | +0,5 | −0,4 |
| | 201909 | +0,7 · −4,8 · +7,3 · +5,1 · −7,0 | 3 de 5 | +0,3 | +6,2 |

**Estabilidad del corte:**

| Brazo | Arrepentimiento máx. (en muestra) | Transferencia ago → sep | Transferencia sep → ago | Peor caso | *f* que elegiría cada semilla sola |
|---|---|---|---|---|---|
| Binario | 0,9 % | 2,725 % · 248,7 M · 1,0 % | 2,175 % · 196,2 M · 3,8 % | 3,8 % | 2,275 %–3,875 % |
| Peso 1 | 0,4 % | 2,675 % · 250,6 M · 1,0 % | 2,850 % · 206,9 M · 0,5 % | **1,0 %** | 2,500 %–3,375 % |
| Peso 0,5 | 0,3 % | 2,600 % · 252,2 M · 1,5 % | 2,950 % · 200,0 M · 0,6 % | 1,5 % | 2,300 %–3,050 % |

**Decisión según la regla del § 7:**

| Paso | Criterio 1 (ensamble, 2 meses) | Criterio 2 (≥ 4/5 semillas, cada mes) | Criterio 3 (transferencia) | Resultado |
|---|---|---|---|---|
| Peso 0,5 contra peso 1 | No (−6,2 M en agosto) | No (2 de 5 en agosto) | No (1,5 % > 1,0 %) | **Queda peso 1** |
| Peso 1 contra binario | Sí | No (2 de 5 en septiembre) | Sí | **El binario sigue de referencia** |

⇒ **E02: el peso 0,5 de BAJA+1 no se adopta.** Con estos hiperparámetros, el efecto del peso cambia de
signo entre meses: −6,2 M en agosto y +5,9 M en septiembre en el ensamble. Es del mismo orden que la
dispersión entre semillas (desvío de 2–6 M según brazo y mes), así que no hay evidencia de que mejore. E03 (escalado
monetario) parte del binario como referencia y vuelve a incluir al multiclase de peso 1 como
candidato.

**Tiempos** (8 hilos para entrenar, 4 para predecir):

| | Medido en E01 | Medido en E02 |
|---|---|---|
| Entrenar multiclase, 300 rondas | peso 1: 330–396 s | peso 0,5: 528–601 s |
| Predecir multiclase, un mes (~132 mil filas) | peso 1: 10,1–16,0 s | peso 1 (modelos de E01, vueltos a predecir): 18,9–22,4 s · peso 0,5: 20,2–23,5 s |
| Predecir binario, un mes | 2,8–5,2 s | 4,1–6,4 s (modelos de E01, vueltos a predecir) |
| Carga · binado · total | 71 s · 32 s · 2.774 s | 79 s · 24 s · 3.391 s (incluye 268 s de comprobación de E01) |
| Pico de working set | 5,45 GB | 5,13 GB |

Los mismos modelos de E01 predijeron un 40–50 % más lento en E02: probablemente la máquina tuvo otra carga
durante esta corrida; la CPU estaba al 100 % y no se identificó otro proceso dominante. Por eso:
- **predecir**: la única comparación válida es dentro de E02. Peso 0,5 y peso 1 tardan lo mismo, con
  diferencias menores al 10 %, que es lo esperable con la misma cantidad de árboles;
- **entrenar**: los 528–601 s del peso 0,5 **no** son comparables con los 330–396 s de E01. No se
  puede atribuir la diferencia al peso. Para medirlo habría que entrenar los dos brazos en la misma
  corrida.

**Limitaciones:**
- 5 semillas y 2 meses: la regla es exigente; un efecto chico y real podría no detectarse.
- Hiperparámetros fijos y no optimizados para ningún brazo. Con Optuna, el peso podría interactuar
  con `min_data_in_leaf` o con la cantidad de rondas.
- Solo se probaron los pesos 1 y 0,5; el 0,25 queda pendiente como exploración.
- El corte se elige con los mismos meses en que se mide. Las cifras "en muestra" son optimistas; la
  transferencia es la medida fuera de muestra.
- Octubre no se leyó: ninguna de estas cifras dice cómo se comporta el modelo a 4 meses del
  entrenamiento.

## 9. TC01 — target consistente (protocolo, escrito antes de entrenar)

Rama `martin/target-consistente`.
- **Scripts:** `experimentos/tc01_target_2019.py` (etiquetas) y `experimentos/tc01_target_corregido.py`
  (modelos y comparación).
- **Definición única del target:** `evaluacion/target.py`. La usan el entrenamiento, la evaluación y la
  retrospectiva del pipeline.

**Qué cambia.** Sólo la regla del target, de la versión 1 a la 2. El cliente presente en *t*, ausente
en *t+1* y presente en *t+2* pasa de BAJA+1 a CONTINUA. La etiqueta definitiva necesita *t+2*.
- **Paso 1, ya corrido:** el target de 2019 se regeneró por presencia, sólo para 201903–201906 y
  201908–201909. Cambian 17 filas, todas de BAJA+1 a CONTINUA: 5 en entrenamiento y 12 en 201908. BAJA+2
  queda idéntico (`resultados/tc01_target_2019_v2.json`). El target anterior se conserva.
- **Lo que queda igual que en E01:**
  - las 760 features;
  - entrenamiento 201903–201906 y desarrollo 201908–201909; octubre bloqueado;
  - las mismas 5 semillas (20261124–20261128), hiperparámetros y 300 rondas;
  - el mismo binado (`max_bin` 255, `data_random_seed` 1);
  - 8 hilos para entrenar y 4 para predecir.
- **Brazos:**
  - binario, positivo = BAJA+1 ∪ BAJA+2;
  - multiclase con peso 1, score = P(BAJA+2).

**Comprobaciones antes de comparar** (si alguna falla, el script se detiene):
1. **Configuración y train.** La configuración es la de E01. El train difiere del de E01 sólo en las 5
   filas esperadas: BAJA+1 −5 y CONTINUA +5.
2. **Modelos anteriores.** Los de E01, vueltos a predecir, reproducen bit a bit sus predicciones
   guardadas, y sus cifras reproducen `resultados.json` de E01. Se usa `reusar_e01` de E02, con las
   etiquetas de desarrollo de la versión 1.
3. **Las cifras de los modelos anteriores no dependen de la versión del target.** Evaluados con las
   etiquetas de la versión 2, dan las mismas cifras de corte y ganancia, porque BAJA+2 es idéntico.

**Comparación**, anteriores (E01) contra corregidos (TC01). Se evalúan en 201908 y 201909 con las
etiquetas de la versión 2, por objetivo, semilla y ensamble:
- **Ganancia:** del ensamble y por semilla, cada brazo en su fracción, con diferencias pareadas por
  semilla (`evaluacion/comparacion.py`). También, para aislar el efecto del score, cada brazo en la
  fracción del otro.
- **Scores:** correlación de Pearson, correlación de rangos y diferencia absoluta media y máxima entre
  el score anterior y el corregido de la misma semilla y del ensamble; media del score.
- **Rankings y envíos:** envíos en la fracción de cada brazo y Jaccard del conjunto enviado anterior
  contra el corregido. Como escala de ruido se usa el Jaccard entre dos semillas distintas del modelo
  anterior.
- **AUC de BAJA+2.**
- **Estabilidad del corte:** fracción minimax, arrepentimiento máximo, transferencia agosto ↔
  septiembre y fracción que elegiría cada semilla sola.

**Procedimiento de corte** (el documentado en § 4 y § 5, sin cambios): fracción de clientes con menor
arrepentimiento máximo entre 201908 y 201909, sobre la curva suavizada del ensamble, en la grilla de
0,25 % a 8 %. Se aplica a cada modelo corregido y se registra si la fracción cambia respecto de E01.

**Decisión, fijada de antemano:**
- **Los modelos corregidos reemplazan a los anteriores por consistencia de definición, no por
  desempeño.** El catálogo nuevo usa los modelos corregidos y su propia fracción minimax.
- **Alerta, para revisar antes del vivo.** En un objetivo, se registra una alerta si se cumple
  cualquiera de dos condiciones:
  - la ganancia del ensamble corregido es menor que la anterior en **ambos** meses por más de dos
    desvíos entre semillas del modelo anterior;
  - el AUC de BAJA+2 cae más de 0,005 en ambos meses.

  Con una alerta, el catálogo nuevo se arma igual, pero no pasa a ser el activo hasta discutirlo.
- **Roles de recomendación y alternativa.** Se aplica a los modelos corregidos la regla de adopción de
  E02 (§ 7, paso 2: multiclase contra binario). El catálogo sigue su resultado. Si no se cumple, el
  binario sigue como recomendación.

**Después:** catálogo nuevo (`catalogo/estrategias_tc01.json`) y secuencia 202001–202006 en una
carpeta nueva, con las mismas comprobaciones, el reintento en 202003 y las métricas retrospectivas
de la versión 2. Se compara con la secuencia anterior, que se conserva: envíos, coincidencia de las
salidas por mes y métricas retrospectivas.

**Limitaciones conocidas de antemano:**
- **El cambio es mínimo.** Son 5 filas de 506.871 en entrenamiento. Las diferencias esperables son del
  orden del ruido entre ejecuciones con distinto target. LightGBM es determinista con la misma entrada,
  pero un cambio de etiqueta puede alterar una división temprana y propagarse.
- **El desarrollo no distingue las versiones en la ganancia.** Las 12 filas que cambian en 201908 no
  son BAJA+2, así que el target de desarrollo no puede distinguir entre las versiones por la ganancia.
  Sí cambia la clase BAJA+1 del multiclase y el positivo del binario.

## 10. Resultados de TC01

- **Corrida:** `ejecuciones/tc01/20261124T212203_16624`.
- **Resumen versionado:** `resultados/tc01_target_corregido.json`, sin datos por cliente. Target:
  `resultados/tc01_target_2019_v2.json`.
- **Protocolo fijado antes de entrenar:** el sha256 de `PLAN_PRUEBAS.md` registrado al inicio
  (`5bccf983c903…`) es el del archivo con el § 9 y sin este § 10.
- **Comprobaciones previas, todas OK:**
  - el train difiere de E01 sólo en las 5 filas esperadas: 501.563 CONTINUA, 2.712 BAJA+1 y 2.596
    BAJA+2;
  - BAJA+2 de desarrollo es idéntico;
  - los modelos de E01 se reprodujeron bit a bit;
  - las cifras de E01 dan iguales con el target versión 2.
- **Desarrollo con el target versión 2:** en 201908, 12 BAJA+1 pasan a CONTINUA (659 → 647); 201909
  no cambia.

**Ganancia en el corte de cada modelo** (millones, sin suavizar; "semillas" = cada semilla sola en
la misma fracción):

| Brazo | Modelos | *f* | Mes | Envíos | Ensamble | Semillas: media ± desvío | AUC BAJA+2 |
|---|---|---|---|---|---|---|---|
| Binario | anterior (E01) | 2,900 % | 201908 | 3.822 | 202,9 | 191,9 ± 1,9 | 0,9105 |
| | | | 201909 | 3.870 | 250,0 | 243,6 ± 5,8 | 0,9092 |
| | **corregido** | **4,475 %** | 201908 | 5.897 | 200,8 | 190,5 ± 4,2 | 0,9094 |
| | | | 201909 | 5.971 | 253,8 | 243,2 ± 4,2 | 0,9080 |
| Multiclase peso 1 | anterior (E01) | 2,800 % | 201908 | 3.690 | 208,7 | 196,8 ± 3,1 | 0,9061 |
| | | | 201909 | 3.736 | 250,4 | 241,6 ± 4,2 | 0,9067 |
| | **corregido** | 2,800 % | 201908 | 3.690 | 208,7 | 198,6 ± 5,4 | 0,9079 |
| | | | 201909 | 3.736 | 253,7 | 245,1 ± 4,4 | 0,9059 |

- **Binario corregido en la fracción anterior (2,9 %):** 197,4 M en agosto y 243,4 M en septiembre.
- **Multiclase:** el ensamble corregido manda en agosto la misma cantidad de BAJA+2 que el anterior;
  por eso la ganancia sale igual.

**Diferencias pareadas por semilla, corregido − anterior** (millones, cada modelo en su fracción):

| Brazo | Mes | Por semilla | A favor | Ensamble |
|---|---|---|---|---|
| Binario | 201908 | +2,3 · +2,3 · −4,3 · −7,6 · +0,1 | 3 de 5 | −2,1 |
| | 201909 | −0,6 · −2,8 · +2,7 · +1,6 · −2,8 | 2 de 5 | +3,8 |
| Multiclase | 201908 | +5,5 · −4,4 · +7,7 · −2,2 · +2,2 | 3 de 5 | 0,0 |
| | 201909 | +7,7 · −2,2 · +6,6 · +4,4 · +1,1 | 4 de 5 | +3,3 |

**Scores y rankings**, anterior contra corregido, 201908 / 201909:

| | Binario | Multiclase |
|---|---|---|
| Ensamble: Pearson · correlación de rangos | 0,997 / 0,997 · 0,983 / 0,984 | 0,995 / 0,994 · 0,987 / 0,988 |
| Ensamble: media del score (anterior → corregido) | 0,00793 → 0,00795 / 0,00821 → 0,00821 | 0,00338 → 0,00338 / 0,00352 → 0,00352 |
| Por semilla: correlación de rangos | 0,938–0,944 / 0,938–0,947 | 0,948–0,953 / 0,950–0,955 |
| Jaccard de los enviados con la misma cantidad *k*: ensamble | 0,883 / 0,881 | 0,889 / 0,887 |
| Jaccard con la misma *k*: misma semilla, anterior contra corregida | 0,767–0,787 / 0,748–0,793 | 0,776–0,790 / 0,774–0,788 |
| **Escala de ruido**: Jaccard entre dos semillas anteriores | 0,683–0,709 / 0,674–0,696 | 0,677–0,694 / 0,668–0,695 |

Cambiar el target mueve el ranking **menos que cambiar de semilla**. El ensamble atenúa la diferencia:
coinciden el 88–89 % de los enviados con la misma *k*.

**Estabilidad del corte** (procedimiento de § 4, sin cambios):

| Brazo | Modelos | *f* minimax | Arrepentimiento máx. | Transferencia: peor caso | *f* que elegiría cada semilla sola |
|---|---|---|---|---|---|
| Binario | anterior | 2,900 % | 0,87 % | 3,8 % | 2,275 %–3,875 % |
| | corregido | **4,475 %** | 0,24 % | 0,55 % | 2,475 %–4,075 % |
| Multiclase | anterior | 2,800 % | 0,41 % | 1,0 % | 2,500 %–3,375 % |
| | corregido | 2,800 % | 0,18 % | 3,5 % | 2,450 %–3,475 % |

**El corte del binario cambia de 2,9 % a 4,475 %.** No es un cambio del modelo, sino de dónde cae el
mínimo en una curva plana. El peor arrepentimiento del binario corregido, con la ganancia suavizada,
en cada fracción:

| *f* | 2,5 % | 2,9 % | 3,5 % | 4,0 % | 4,475 % | 5,0 % |
|---|---|---|---|---|---|---|
| Peor arrepentimiento | 2,5 % | 3,0 % | 1,8 % | 0,8 % | **0,24 %** | 4,8 % |
| Ganancia suavizada 201908 / 201909 (M) | 200,0 / 246,1 | 198,6 / 244,9 | 199,8 / 248,0 | 201,1 / 250,3 | 201,0 / 252,0 | 197,4 / 240,2 |

- **La meseta.** Entre 2,5 % y 4,475 % la ganancia varía entre 1 y 3 %. El minimax elige el extremo
  derecho de la meseta, y a 5 % la curva cae.
- **Fuera del rango de las semillas.** La fracción del ensamble, 4,475 %, queda por encima de la que
  elegiría cualquier semilla sola (hasta 4,075 %).
- **Efecto en los envíos.** Son un 54 % más que con 2,9 %. En un mes de baja prevalencia, como
  202002 en el ensayo, enviar más cuesta más.
- **Decisión.** Según el protocolo, el catálogo usa 4,475 %. Queda señalado como riesgo para la
  decisión de corte (pendientes en `INTEGRACION.md`).

**Decisión según el § 9:**
- **Alertas: ninguna.**
  - La ganancia del ensamble corregido no cae más de dos desvíos en ambos meses: binario −2,1 M en
    agosto y +3,8 M en septiembre; multiclase 0,0 y +3,3 M.
  - El AUC no cae más de 0,005 en ambos meses: cambia entre −0,0012 y +0,0018.
- **Modelos.** Los corregidos reemplazan a los anteriores. El catálogo activo pasa a ser `tc01`
  (`catalogo/estrategias_tc01.json`).
- **Roles.** La regla de E02 aplicada a los modelos corregidos (multiclase contra binario) no se cumple
  en ninguna de sus tres condiciones. El binario sigue como recomendación provisional y el multiclase
  como alternativa.
- **Cortes.** Binario 4,475 % (cambia desde 2,9 %) y multiclase 2,8 % (sin cambio).

**Tiempos** (8 hilos para entrenar, 4 para predecir): binario 108–182 s y multiclase 296–563 s por
semilla. La multiclase de la semilla 20261127 registró 36.467 s porque la máquina se suspendió
durante el entrenamiento (eventos de energía entre las 22:01 y las 08:02). El resultado no cambia,
porque el entrenamiento es determinista, pero ese tiempo no es comparable. Total de la corrida:
39.610 s, de los cuales unas 10 horas fueron de suspensión.

**Limitaciones:**
- **El cambio de target es mínimo.** Son 5 filas de 506.871 en entrenamiento, y las diferencias que
  produce son del orden del ruido entre semillas.
- **El desarrollo no separa las versiones por ganancia.** BAJA+2 es igual en las dos, así que cualquier
  diferencia de ganancia viene del modelo, no de la etiqueta de evaluación.
- **El corte es sensible a la meseta.** Las alternativas, como una fracción central de la meseta, la
  mediana de las fracciones por semilla o un umbral de probabilidad, se evalúan con 2019 antes del
  vivo.
