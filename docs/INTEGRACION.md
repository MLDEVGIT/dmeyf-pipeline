# Pipeline mensual con dos estrategias

Rama `martin/integracion-estrategias`, 24-nov-2026. Código: `pipeline_competencia02/mensual.py`,
`preparar_ejecucion.py` y `catalogo.py`. Verificadores: `scripts/verificar_scores.py`,
`scripts/verificar_salida.py` y `scripts/probar_reintentos.py`.

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
   el proceso y la entrada ya en `input/`.
5. **Probabilidad de la salida oficial = P(BAJA+1 ∪ BAJA+2).** Si la consigna exige P(BAJA+2) en la
   columna `probabilidad`, la recomendación tendría que pasar al multiclase o cambiar la columna
   (pendiente de la transcripción de la consigna, F1).
6. **Métricas con target pendientes.** La etiqueta de un mes necesita la lista de clientes de los dos
   meses siguientes. La ganancia, el AUC y los aciertos figuran como `pendiente` hasta tener etiquetas
   válidas y aceptadas según R1.

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

Métricas con target: **pendientes**. La etiqueta de 202001 necesita las listas de 202002 y 202003.

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

## Pendientes para ensayar 202001–202006

1. **Secuencia completa**: correr 202001 a 202006 en una sola carpeta, cada mes con
   `--copiar-desde`. Verificar que la historia crece un mes por vez, que el reporte acumulado tiene
   6 filas e `integridad_ok` en todas, y medir los tiempos por mes (la historia crece).
2. **202006**: 47 columnas con todos los observados en 0. Hoy se advierte y no se trata (E06).
   Revisar cómo cambian los scores, los envíos y la coincidencia entre estrategias.
3. **Tiempo**: el multiclase es la etapa más cara (132 s en 202001 con la máquina cargada). Repetir
   T01 y la secuencia en la máquina del vivo (T12). Si sube, una opción es bajar a menos semillas en la
   alternativa, porque no define la salida oficial.
4. **Reintentos dentro de la secuencia**: fallar un mes intermedio, por ejemplo 202003, y comprobar que
   202004 se rechaza por secuencia hasta reintentar 202003.
5. **`correr_meses.py`** sigue usando `ejecutar_mes` (un modelo) e insumos con nombre
   `competencia_02_<mes>_crudo.csv`. Hay que adaptarlo a `mensual.py` y a `input/<yyyymm>.csv`.
6. **Consigna**: confirmar las columnas de la salida y qué probabilidad se espera (supuesto 5) y el
   formato del reporte (R2, R3; T1).
