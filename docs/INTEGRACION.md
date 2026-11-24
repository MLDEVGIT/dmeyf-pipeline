# Pipeline mensual con dos estrategias

Ramas `martin/integracion-estrategias` y `martin/ensayo-secuencia`, 24-nov-2026.
- **Código**: `pipeline_competencia02/mensual.py`, `preparar_ejecucion.py`, `catalogo.py`,
  `retrospectiva.py` (métricas con target a posteriori) y `correr_meses.py` (ensayo secuencial).
- **Verificadores**: `scripts/verificar_scores.py`, `scripts/verificar_salida.py` y
  `scripts/probar_reintentos.py`.
- **Diagnóstico de anomalías**: `scripts/analizar_columnas_en_cero.py`.

## Estrategias integradas

Las dos son los **candidatos de E01**: 300 rondas, hiperparámetros fijos, **sin optimización**
(`PLAN_PRUEBAS.md` § 5 y § 8). Se reutilizan los 10 modelos de E01 sin reentrenar.

| | Recomendación provisional | Alternativa |
|---|---|---|
| Id del catálogo | `binario_e01_300r` | `multiclase_p1_e01_300r` |
| Objetivo | binario, positivo = BAJA+1 ∪ BAJA+2 (baseline 208135) | multiclase CONTINUA / BAJA+1 / BAJA+2, BAJA+1 con peso 1 |
| **Qué es la probabilidad** | **P(BAJA+1 ∪ BAJA+2)**: probabilidad de que el cliente se vaya en uno o dos meses | **P(BAJA+2)**: columna 2 del multiclase |
| Semillas | 20261124 a 20261128, promedio de probabilidades | ídem |
| Corte | 2,9 % de los clientes del mes, ⌈0,029 · n⌉ | 2,8 %, ⌈0,028 · n⌉ |
| Fuente del corte | `resultados/e02_peso_baja1.json` → `resultados.binario.corte.fraccion` | `… .multiclase_p1.corte.fraccion` |
| Salida | **`output/churn_<yyyymm>.csv`** (oficial) | `diagnosticos/<yyyymm>/decisiones_<yyyymm>.csv` y el reporte |

Las dos probabilidades **no son comparables en escala**: miden cosas distintas. Cada una se compara
con su propio corte; entre estrategias se comparan conjuntos y rangos (coincidencia, Jaccard,
correlación de rangos).

**Catálogo.** `catalogo/estrategias.json` (versionado) registra, para cada uno de los 10 modelos:
- semilla, archivo y sha256 de la copia, y sha256 del original de E01;
- rondas y árboles;
- la fracción con su fuente;
- el significado del score;
- la definición de las features.

`catalogo/predictores.json` guarda los 760 predictores con su tipo y en orden. Las copias de los
modelos (41 MB) quedan fuera del repo, en la ruta `modelos` de `config.toml`. Llevan los nombres de las
features, que los originales de E01 no tenían; la línea `feature_names` se reemplaza en bytes y se
verifica que la copia prediga exactamente igual.

## Contrato de una ejecución

```
<carpeta>/input/<yyyymm>.csv            entrada (la copia el operador, o --copiar-desde)
<carpeta>/output/churn_<yyyymm>.csv     salida oficial: numero_de_cliente, probabilidad, enviar
<carpeta>/diagnosticos/<yyyymm>/        features, predicciones por semilla y ensamble, decisiones de las dos, reporte.json
<carpeta>/historia/                     201901 … mes anterior (inicial + meses completados)
<carpeta>/registro/reporte_acumulado.csv  una fila por mes completado (se regenera, no se edita)
<carpeta>/registro/ejecuciones.jsonl    todos los intentos, incluidos fallidos y rechazados
<carpeta>/registro/meses/<yyyymm>.json  estado del mes e intentos
```

**Etapas:**
1. Recepción.
2. Validación del esquema y de los valores (reglas de producción de `ejecutar_mes`).
3. Perfil de columnas.
4. Features del mes.
5. **Verificación de features**: nombres y orden iguales al catálogo y a los modelos; tipos iguales a
   los del entrenamiento; lags.
6. Inferencia de las 10 semillas.
7. Estrategias.
8. Escritura.
9. Publicación todo o nada: diagnóstico, historia y, al final, la salida oficial.
10. Estado `completado`.
11. Reporte acumulado regenerado.

**Lags.** Los modelos de E01 se entrenaron con **lags por fila**: la k-ésima observación previa del
cliente. El pipeline calcula exactamente esa definición, porque de lo contrario el score no sería el del
modelo. Por cada mes cuenta cuántos clientes tienen un lag por fila que no cae en el mes calendario
*t − k* (les falta un mes intermedio) y lo informa como incidente `lag_fila_distinto_calendario`. **No
cambia las features.** Pasar a lags por calendario es E05 y exige reentrenar.

**Reintentos y alineación:**
- Un mes completado se rechaza con código 4, sin tocar nada. Un mes con otro intento vivo también se
  rechaza.
- Si un intento falla antes de publicar, no queda nada publicado: el intento va a
  `diagnosticos/<mes>.fallido-<ejecución>/` y el mes se puede reintentar.
- Si el proceso muere después de publicar y antes de marcar el estado, el reintento reconcilia el mes:
  - si diagnóstico, historia y salida existen y sus sha256 coinciden con los registrados en
    `reporte.json`, lo marca completado **sin recalcular**;
  - si hay piezas sueltas o alteradas, las mueve a `diagnosticos/<mes>.cuarentena-<ejecución>/` y
    recalcula.
- El reporte acumulado se deriva de los meses completados: una fila por mes, reescrita entera. No
  puede duplicar meses ni quedar desalineado con la salida y la historia (`integridad_ok`).

**Octubre de 2019.** El pipeline mensual no lee ninguna etiqueta. `pruebas/test_mensual.py`
comprueba que los módulos nuevos no referencian archivos de target, y `evaluacion/particiones.py`
sigue bloqueando 201910 para los experimentos. Las features de octubre entran como historia, igual
que en el entrenamiento, pero nunca su clase.

## Supuestos

1. **Las dos estrategias son provisionales.** Son los candidatos de E01, sin optimizar. La
   recomendación es el binario porque E01 y E02 no cumplieron la regla para cambiar la referencia; no
   porque se haya demostrado mejor.
2. **El corte se aplica como fracción de los clientes de cada mes**, con la fracción elegida en
   201908–201909. Se asume que la prevalencia de 2020 es parecida; si no lo es, el corte no se adapta.
3. **La historia inicial es 201901–201912** (Parquet tipado de 2019, controlado contra la auditoría
   de filas). Para empezar en un mes de 2020 se agregan los meses previos desde los CSV de insumos, con
   la validación de producción.
4. **Reloj.** Con `--copiar-desde`, el tiempo arranca antes de copiar la entrada a `input/` y termina
   con el reporte acumulado regenerado. No incluye el arranque del intérprete y los imports (~10 s,
   la diferencia entre "pared" y "desde la entrada" en el ensayo). Sin `--copiar-desde`, arranca con
   el proceso y la entrada ya en `input/`. En el ensayo secuencial (`correr_meses`) el tiempo
   del mes es la **pared del proceso**, que sí incluye el arranque (5,5–15,7 s por mes).
5. **Probabilidad de la salida oficial = P(BAJA+1 ∪ BAJA+2), pendiente de confirmar su
   interpretación con la cátedra.** Si la consigna exige P(BAJA+2) en la
   columna `probabilidad`, la recomendación tendría que pasar al multiclase o cambiar la columna
   (pendiente de la transcripción de la consigna, F1).
6. **Métricas con target retrospectivas.** La etiqueta de un mes necesita la lista de clientes de los
   dos meses siguientes. Al publicar un mes, sus métricas son `pendiente`; cuando llegan esos meses, el
   reporte acumulado las completa (`retrospectiva.py`, regla abajo). Son **monitoreo**: no cambian
   modelos, features, cortes ni salidas, que se eligen sólo con 2019 (R1). La etiqueta se reconstruye
   con la presencia de cada cliente en los meses recibidos; no se lee ningún archivo de clase.

**Regla de target** (igual a `evaluacion/particiones.py`), para un cliente del mes *t*:

| Clase | Condición | Necesita |
|---|---|---|
| BAJA+1 | ausente en *t+1* | lista de *t+1* |
| BAJA+2 | presente en *t+1* y ausente en *t+2* | listas de *t+1* y *t+2* |
| CONTINUA | presente en *t+1* y en *t+2* | listas de *t+1* y *t+2* |

Estados en el reporte: `completa` (están *t+1* y *t+2*: ganancia, aciertos, AUC de BAJA+2),
`parcial` (sólo *t+1*: cantidad de BAJA+1 y cuántos se enviaron) y `pendiente`. Un cliente ausente
en *t+1* que vuelve en *t+2* sigue siendo BAJA+1 y se cuenta aparte. La ganancia usa los importes de
C01 (`GANANCIA.md`), porque los de C02 siguen sin fuente.

## Ensayo de 202001

Resumen versionado: `resultados/i01_ensayo_202001.json`. Dos ensayos completos, cada uno en una
carpeta nueva: preparación con historia 201901–201912, y después
`mensual --mes 202001 --copiar-desde <insumo>`. Máquina de Martín: 8 hilos, 15,7 GB, Windows 11.

**Tiempo de punta a punta**, desde antes de copiar la entrada hasta la salida oficial y el reporte
acumulado regenerado:

| | Ensayo 1 (máquina con otra carga) | Ensayo 2 |
|---|---|---|
| **Total desde la entrada** | 267,7 s | **104,1 s** |
| Pared del proceso, incluye arranque e imports | 278 s | 107 s |
| Validación · perfil | 24,1 · 5,0 s | 6,7 · 1,4 s |
| Features · verificación | 42,2 · 0,1 s | 13,1 · 0,0 s |
| Carga de modelos | 1,2 s | 0,4 s |
| Inferencia binario (5 semillas) | 40,5 s | 16,8 s |
| Inferencia multiclase (5 semillas) | 132,1 s | 58,4 s |
| Lectura y conversión de features | 15,3 s | 5,3 s |
| Estrategias · escritura · publicación y reporte | 0,3 · 3,3 · 0,2 s | 0,1 · 0,9 · ~0,2 s |
| Pico de working set | 3,2 GB | 3,3 GB |
| Preparación de la carpeta (fuera del tiempo mensual) | 67 s | 22 s |

En el ensayo 1 todas las etapas fueron entre 2,5 y 3,7 veces más lentas: la máquina tenía otra carga.
El multiclase es el 56 % del tiempo del ensayo 2. Las dos mediciones quedan por debajo del límite
de 15 minutos (900 s). En la máquina del vivo falta medir (T12).

**Resultados del mes** (142.929 clientes, idénticos en los dos ensayos):

| | Recomendación (binario) | Alternativa (multiclase) |
|---|---|---|
| Score | P(BAJA+1 ∪ BAJA+2) | P(BAJA+2) |
| Envíos | 4.145 (2,9 %) | 4.003 (2,8 %) |
| Probabilidad mínima enviada | 0,0530 | 0,0254 |
| Mediana · p99 · máximo del score | 0,00061 · 0,154 · 0,984 | 0,00025 · 0,069 · 0,839 |
| Probabilidades exactamente 0 o 1 | 0 | 0 |

Coincidencia: 3.474 clientes en las dos, 671 solo en la recomendación y 529 solo en la alternativa.
Jaccard 0,743; correlación de rangos de los scores 0,957.

Incidentes (todos `advertir`, estado de calidad `sin_alertas`):
- `clientes_sin_historia`: 4.165;
- `lag_fila_distinto_calendario`: **14 clientes** con un lag por fila que no es el mes calendario (7 en
  lag1, 13 en lag2);
- `estrategia_provisional`: las dos.

Métricas con target: **pendientes** en ese ensayo; la etiqueta de 202001 necesita las listas de
202002 y 202003. Se completaron en el ensayo secuencial (abajo).

**Verificaciones:**

| Verificación | Resultado |
|---|---|
| Cobertura de la historia inicial (201901–201912, consecutiva, filas = auditoría, mismo esquema) | OK |
| Features: nombres y orden iguales al catálogo y a los 10 modelos; tipos iguales a los del entrenamiento | OK |
| `scripts/verificar_scores.py`: los **modelos originales de E01** (sha256 verificado), aplicados a las features del pipeline | 10 de 10 semillas **idénticas bit a bit**; ensambles, probabilidades de `decisiones` y de `churn`, y decisiones de las dos estrategias idénticos |
| `scripts/verificar_salida.py` (independiente) sobre `output/churn_202001.csv`, en los dos ensayos | OK: cabecera exacta, 142.929 clientes sin duplicados = entrada, probabilidades en [0,1], 4.145 envíos de mayor probabilidad |
| Reproducibilidad entre ensayos | `churn_202001.csv` y `decisiones_202001.csv` idénticos byte a byte |
| `scripts/probar_reintentos.py`, en una carpeta nueva | OK en los 4 pasos (abajo) |

**Prueba de reintentos** (`ejecuciones/entornos/reintentos_202001_20261124T181502/prueba_reintentos.json`):

| Paso | Código | Tiempo | Qué se comprobó |
|---|---|---|---|
| 1. Falla inyectada durante la publicación | 2 | 104 s | Nada publicado (salida, historia, diagnóstico), estado `fallido`, sin candado, reporte acumulado vacío, intento conservado en `diagnosticos/202001.fallido-…`, `tmp/` vacío |
| 2. El proceso muere después de publicar | 3 | 109 s | Todo publicado, estado `en_curso` y candado huérfano: el caso que hay que reconciliar |
| 3. Reintento | 0 | 3,5 s | Reconcilia: hashes íntegros, `completado` **sin recalcular** (mismos archivos), una fila en el reporte con `integridad_ok`, intentos `fallido, fallido, completado` |
| 4. Reintento del mes completado | 4 | 2,9 s | Rechazado; ningún archivo publicado ni el reporte cambian; el intento queda en `ejecuciones.jsonl` |

**Cuestiones detectadas y corregidas durante el ensayo:**
- `verificar_scores.py` leía los CSV con el parser por defecto de pandas, que puede diferir en 1 ulp
  (1,1e-16) del valor escrito. El CSV es exacto: con `float_precision="round_trip"` coinciden los
  142.929 valores.
- `ejecutar_mes.adquirir`, ante un candado huérfano, marcaba el mes como fallido, pero dejaba el
  último intento como `en_curso`. Ahora el intento también queda `fallido`.

## Ensayo secuencial 202001–202006

Resúmenes versionados: `resultados/i02_secuencia_202001_202006.json` (secuencia, reintento y
retrospectiva) y `resultados/i02_columnas_en_cero_202006.json` (anomalía de 202006). Carpeta:
`ejecuciones/entornos/secuencia_202001_202006_20261124T200817` (no versionada).

```powershell
python -m pipeline_competencia02.correr_meses --nueva <nombre> --desde 202001 --hasta 202006 `
    --reintento-en 202003 --resumen resultados/i02_secuencia_202001_202006.json
```

- **Un archivo por vez.** Cada mes es un proceso `mensual --copiar-desde`. La historia empieza en
  201901–201912 y sólo crece con los meses recibidos y completados.
- **Modelos, features y cortes fijos** durante todo el ensayo: el catálogo de E01, con el mismo
  sha256 en los seis meses.
- **Reloj del mes.** Es la pared del proceso: desde antes de lanzarlo hasta que termina. Incluye el
  arranque del intérprete y los imports, la copia a `input/`, la salida oficial y el reporte
  acumulado regenerado. La verificación del sha256 del insumo queda fuera del reloj.
- **Preparación previa del entorno**, medida aparte: **42,4 s** de pared (38,0 s internos). Incluye
  la copia y verificación de los 10 modelos y del catálogo, y la historia 201901–201912 desde el
  Parquet de 2019, contrastada con la auditoría de filas y con la cobertura validada.

### Resultados por mes

| Mes | Tiempo total | Clientes | Envíos recomendación | Envíos alternativa | Jaccard entre estrategias | Anomalías | Métricas con target |
|---|---|---|---|---|---|---|---|
| 202001 | 183,6 s | 142.929 | 4.145 | 4.003 | 0,743 | 4.165 sin historia · 14 con lag ≠ calendario | **completa**: G 267,7 M / 259,5 M · AUC 0,938 / 0,936 |
| 202002 | 173,7 s | 146.184 | 4.240 | 4.094 | 0,721 | **6 columnas en cero** (descuentos de tarjetas y cajeros) · 3.849 · 21 | **completa**: G 26,4 M / 26,0 M · AUC 0,950 / 0,948 |
| 202003 | 171,7 s (167,3 + 4,4; reintento) | 148.313 | 4.302 | 4.153 | 0,727 | 2.643 · 24 | **completa**: G 163,3 M / 156,4 M · AUC 0,942 / 0,941 |
| 202004 | 190,9 s | 148.831 | 4.317 | 4.168 | 0,739 | 727 · 14 | **completa**: G 184,9 M / 173,6 M · AUC 0,929 / 0,928 |
| 202005 | 193,9 s | 150.267 | 4.358 | 4.208 | 0,724 | 1.826 · 13 | **parcial**: 527 BAJA+1; enviados 315 / 290. Falta 202007 |
| 202006 | 174,3 s | 152.712 | 4.429 | 4.276 | **0,460** | **47 columnas en cero** · 2.957 · 24 | **pendiente**: faltan 202007 y 202008 |

- G = ganancia recomendación / alternativa, en pesos, con los importes de C01.
- **Anomalías**: clientes sin historia · clientes con lag por fila distinto del calendario.
- **Advertencias**: todas las de la tabla son `advertir`; ningún mes se rechazó. El estado de calidad
  es `con_alertas` en 202002 y 202006 (columnas en cero) y `sin_alertas` en el resto. No hubo
  columnas 100 % nulas, constantes ni con cambios de tasa de nulos.

**Tiempos.** Todos los meses tardaron entre 172 y 194 s, menos de 900 s. El arranque y cierre del
proceso, fuera del reloj interno, sumó entre 5,5 y 15,7 s. La etapa más larga es la inferencia
multiclase, con 85–96 s. 202001 tardó 178 s en este ensayo y 104 s en el ensayo limpio de la
integración, con la misma salida byte a byte. La diferencia de tiempo viene de la carga de la
máquina y no del pipeline. El pico de working set fue de 3,1–3,4 GB. Con la historia, el tiempo
crece poco: de 12 a 17 meses de historia, el cálculo de features pasó de 19 a 24–29 s.

**Métricas retrospectivas** (sólo monitoreo, R1):

| Mes | BAJA+2 | BAJA+1 | Recomendación: aciertos / ganancia / máximo ex post (envíos) | Alternativa: aciertos / ganancia / máximo ex post (envíos) |
|---|---|---|---|---|
| 202001 | 521 | 608 | 347 / 267,7 M / 274,0 M (3.278) | 336 / 259,5 M / 260,2 M (3.699) |
| 202002 | 213 | 524 | 130 / 26,4 M / 55,1 M (996) | 126 / 26,0 M / 52,3 M (1.060) |
| 202003 | 398 | 213 | 256 / 163,3 M / 169,9 M (3.743) | 246 / 156,4 M / 162,5 M (3.570) |
| 202004 | 524 | 399 | 276 / 184,9 M / 188,3 M (4.553) | 262 / 173,6 M / 184,4 M (4.575) |

- **Las dos estrategias.** La recomendación supera a la alternativa en los cuatro meses completos:
  por +8,2, +0,4, +6,9 y +11,3 M. Es un registro, no un criterio para cambiar la recomendación
  (R1).
- **202002 tuvo muy pocas BAJA+2** (213). El corte por fracción (2,9 %) envió unas cuatro veces más
  que el máximo ex post y la ganancia quedó en menos de la mitad de ese máximo. Es el riesgo del
  supuesto 2: el corte no se adapta a la prevalencia del mes. El máximo ex post usa la etiqueta y sólo
  sirve de referencia.
- **Clientes que vuelven.** Los ausentes en *t+1* que vuelven en *t+2* son 2 en 202001, 0 en 202002 y
  202003, y 1 en 202004.

### Verificaciones

| Verificación | Resultado |
|---|---|
| Chequeos de `correr_meses` en cada mes: estado, integridad sha256, salida oficial (cabecera, clientes = entrada, probabilidades en [0,1], igual a la recomendación), decisiones de las dos estrategias (envíos = techo(f·n), prefijo del orden con desempate), historia = inicial + completados sin huecos, lecturas sólo de la entrada, la historia anterior completa y los modelos, reporte con una fila por mes completado, retrospectiva según los meses recibidos | **OK los 6 meses** |
| `scripts/verificar_scores.py` (modelos **originales** de E01) en los 6 meses | OK: 10/10 semillas, ensambles, decisiones y salida oficial idénticos bit a bit |
| `scripts/verificar_salida.py` (independiente) en los 6 meses | OK |
| Reproducibilidad: `churn_202001.csv` contra el ensayo de la integración | Idéntico byte a byte |
| Reporte acumulado final | 6 filas (202001–202006), `integridad_ok` en todas; 202003 marcada `recuperado`; `tmp/` vacío |

**Reintento provocado en 202003** (`--reintento-en 202003`):

| Paso | Código | Tiempo | Qué se comprobó |
|---|---|---|---|
| a. El proceso muere después de publicar (`tras_publicacion`) | 3 | 167,3 s | Salida, historia y diagnóstico publicados; estado `en_curso`; candado huérfano; el reporte sigue con 202001–202002 |
| b. Se intenta 202004 | 4 | 3,2 s | Rechazado: "meses previos procesados sin estado completado: [202003]". Ningún archivo publicado ni del registro cambia |
| c. Reintento de 202003 | 0 | 4,4 s | Reconciliado con hashes íntegros, `completado` **sin recalcular** (features y publicados intactos); intentos `fallido, completado`. La retrospectiva de 202001 pasa a `completa` |
| d. Se repite 202003 | 4 | 2,8 s | Rechazado sin cambios |

El paso b es una regla nueva de `mensual.py`. Sin ella, 202004 se habría aceptado: la historia de
202003 ya estaba publicada aunque el mes no figuraba completado, y el reporte habría quedado sin
la fila de 202003. El intento que muere no llega a escribir en `ejecuciones.jsonl`, por eso el
archivo tiene 8 líneas y no 9. Ese intento queda como `fallido` en `registro/meses/202003.json`.

### 202006: 47 columnas con todos los observados en 0

Diagnóstico fuera del pipeline: `scripts/analizar_columnas_en_cero.py`. No cambia lo publicado y no
usa etiquetas.

- **Precedente en la historia**:
  - 33 de las 47 columnas **nunca** habían llegado todas en cero en 201901–202005;
  - de las 14 restantes, 7 lo hicieron en 201905 y 201910 (márgenes, comisiones y rentabilidad), 1
    sólo en 201910 (`chomebanking_transacciones`) y 6 en 201910 y 202002. Esas 6 son las de descuentos,
    las mismas columnas en cero de 202002.

  En 202005, la mediana de la fracción de observados distintos de 0 en las 47 columnas era 0,33.
  Algunas, como `mrentabilidad` o `mcomisiones`, tenían más del 96 % de los observados distintos
  de 0.
- **Peso en los modelos.** Las variables crudas y sus deltas, que son las que afecta el 0 del mes,
  explican el 16 % de la importancia por ganancia del binario y el 17 % del multiclase. Los lags de
  esas columnas vienen de meses sanos: 6–7 %.
- **Efecto en lo publicado (A).**
  - **Scores**: los de las dos estrategias se corren hacia arriba. La mediana del binario pasa de
    0,00078 en 202005 a 0,0076, unas 10 veces más, y la del multiclase de 0,00030 a 0,0021.
  - **Envíos**: la cantidad no cambia, porque el corte es una fracción de los clientes. Sí cambia la
    probabilidad mínima enviada, que sube de 0,065 a **0,174** en el binario y de 0,032 a 0,054 en el
    multiclase. A esos clientes los separa menos el riesgo y más el "cero" del mes.
  - **Coincidencia entre estrategias**: baja de 0,72–0,74 a **0,46**.
  - **Coincidencia entre semillas**: la de cada semilla sola con el ensamble baja de 0,75–0,80 en los
    meses normales a 0,56–0,59.
- **Contrafácticos** sobre las features publicadas, con los mismos modelos y cortes. Ninguno es un
  tratamiento adoptado:

| Variante | Binario: mediana · mínima enviada · Jaccard con A | Multiclase: mediana · mínima enviada · Jaccard con A | Jaccard entre estrategias |
|---|---|---|---|
| A publicado (ceros) | 0,0076 · 0,174 · — | 0,0021 · 0,054 · — | 0,460 |
| N como faltantes | 0,0153 · 0,199 · 0,64 | 0,0058 · 0,080 · 0,56 | 0,424 |
| L último valor | 0,0011 · 0,067 · 0,32 | 0,0004 · 0,027 · 0,48 | **0,699** |

**Lectura.**
- **Con el último valor (L)**, la distribución de scores, la probabilidad mínima enviada y la
  coincidencia entre estrategias vuelven a niveles de 202001–202005.
- **Pasarlas a faltantes (N) no corrige el corrimiento.** Los modelos no vieron esas columnas
  vacías en entrenamiento.
- **El tratamiento cambia mucho la selección.** Con L, el binario enviaría a otros 2.266 de sus
  4.429 clientes.
- **Ganancia sin medir.** No se sabe cuál variante gana más: en 202006 hace falta 202007 y 202008.
- **Decisión.** Elegir el tratamiento corresponde a E06, con la inyección del patrón en meses de
  2019 (R1). Hasta entonces el pipeline advierte y no trata.

## Pendientes

1. **E06, tratamiento de columnas en cero.** Con 202006 se dimensiona: el 16–17 % de la importancia
   está afectada y la selección cambia en más de la mitad de los clientes según el tratamiento. Hay que
   decidir con 2019 entre advertir, N y L, y medir los falsos positivos de la detección. En 2019
   aparecen 201905 y 201910 y, en el ensayo, 202002.
2. **Corte y prevalencia.** 202002 mostró que la fracción fija puede enviar cuatro veces más que el
   máximo ex post. Cualquier alternativa, como un umbral de probabilidad calibrada, se evalúa con 2019.
3. **Tiempo en la máquina del vivo (T12).** En la máquina de Martín, 172–194 s por mes con carga
   variable. El multiclase es más de la mitad.
4. **Consigna**:
   - confirmar las columnas de la salida y **la interpretación de la probabilidad**: hoy es
     P(BAJA+1 ∪ BAJA+2), supuesto 5;
   - el formato del reporte (R2, R3; T1);
   - si las métricas retrospectivas con la presencia de 2020 se aceptan en el reporte (R1).
5. **Importes de ganancia de C02**: siguen siendo los de C01.
