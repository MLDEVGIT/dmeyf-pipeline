# Relevamiento (24-nov-2026)

## 1. Repo local `C:\dev\DMEyF`

Rama `feature/competencia02-sampling-pipeline`. Todo lo de competencia 02 está **sin
commitear** (`pipeline_competencia02/`, `experimento_sampling/`, `competencia_01_final/`,
`monday/z618–z637`, `data/`). Conviene versionarlo antes de seguir iterando allá.

### Circuito, etapa por etapa

| Etapa | Dónde | Estado |
|---|---|---|
| Carga y tipado | `experimento_sampling/01`, `02` (CSV → Parquet 2019); `pipeline_competencia02/ejecutar_mes.py::validar_entrada` | Funciona. Tipado sin redondeos; esquema exacto obligatorio. |
| Insumos mensuales | `pipeline_competencia02/preparar_insumos.py` | Funciona. 202001–202006 (y 201908) ya cortados. |
| Target | `experimento_sampling/03_construir_target.py` | Sólo 2019. BAJA+1/BAJA+2 por presencia en t+1, t+2; 201911 parcial y 201912 sin etiqueta (ver CONSIGNA § Contradicción). Por R1 no se usan etiquetas de 2020 para decidir. |
| Features | `pipeline_competencia02/features.py` (compartido con `04`) | 152 originales + lag1, delta1, lag2, delta2 = 760. |
| Entrenamiento | `experimento_sampling/05_baseline_inicial.py` | **Diagnóstico**: LightGBM por defecto (100 árboles), train 201903–201906, sin Optuna, sin reentrenar con 07–08. |
| Predicción | `ejecutar_mes.py::inferir` | Funciona. Bit a bit igual a 05 en 201908. |
| Selección de envíos | `estrategias.py` | `cupo_fijo:1000` (principal) y `porcentaje:1`. **Ambas provisionales, sin optimización por ganancia.** |
| Reporte | `ejecutar_mes.py::registrar` | `reporte.json` por mes + `reporte_acumulado.csv`. Sin ganancia (no hay etiquetas). |
| Robustez / incidentes | `incidentes.py`, `politica_incidentes.json` y pruebas | Funciona; ver README del pipeline original. |

### Comandos verificados

- `python -m unittest pipeline_competencia02.pruebas_unitarias` → 12 OK (0,2 s), en ambos repos.
- `entorno` + `ejecutar_mes` sobre 202001 → completado (ver § 4).
- Corridas previas del 2-nov: secuencia 202001–202006 completa (43–52 s/mes),
  equivalencia con 201908, robustez e incidentes.

### Disponibilidad temporal y meses faltantes

- **Sin fuga hacia adelante.** El entorno exige que la historia termine exactamente en el
  mes anterior y que no tenga meses ≥ al procesado; el target no se lee nunca.
- **Lags por fila, no por calendario.** `lag(x, k) OVER (PARTITION BY cliente ORDER BY foto_mes)`
  toma la k-ésima *observación* previa. Si un cliente falta en t−1, su `lag1` es el valor
  de t−2 (o anterior) **sin indicador**. Competencia 01 (FULL762) usaba lags de calendario
  más `lag1_disponible`/`lag2_disponible`. No es fuga, pero mezcla antigüedades; decidir con
  2019 (R1) si conviene pasar a calendario (cambia los predictores ⇒ reentrenar).
- **Mes faltante en la serie global** (p. ej. no llega 202008): la ejecución de 202009 se
  **rechaza** (`mes_fuera_de_secuencia`). No hay modo degradado. Para el vivo hay que
  definir qué hacer (procesar con historia incompleta y lags de calendario NULL, o abortar).
- **Clientes sin historia**: lags NULL → NaN, LightGBM los trata como faltantes. 727–4.165 por mes.
- **Historia del vivo**: `entorno.py` sólo copia historia del Parquet de 2019. Para 202007
  hace falta historia 202001–202006: hoy sólo se consigue corriendo los seis meses de
  ensayo en el mismo entorno (≈ 5–9 min, antes del vivo). Falta una opción para armar la
  historia desde los insumos.
- **202006 anómalo**: 47 columnas con todos los observados en 0 (33 sin precedente en
  2019), score medio ×3. Relacionado con `monday/z701_drifting.ipynb` del curso.

### Competencia 01 vs competencia 02

| Desarrollo | Aplica a C02 | Cómo |
|---|---|---|
| `competencia_01_final/` (Z636, C25 = 0,75 LGBM FULL762 + 0,25 CatBoost FULL457, 5 semillas, 98,6 M public) | **Ideas, no el código tal cual** | Otro dataset (meses 2021), entrega de 12.000 IDs sin probabilidad, 3 h 04 min de corrida: no entra en 15 min si hay que reentrenar. |
| Lags de calendario + indicadores de disponibilidad | Sí | Candidato a reemplazar los lags por fila. |
| Multiclase y extraer P(BAJA+2) | Sí, a evaluar | El baseline C02 usa binario BAJA+1 ∪ BAJA+2. |
| Ensamble por rangos de dos familias | Sí | Base natural para "dos estrategias/modelos" con una recomendación. |
| `monday/z618–z637` (reconstrucciones, auditorías, ensambles de C01) | No directamente | Exploración de C01. |
| `experimento_sampling/` y pipeline mensual | Sí | Es la base de este repo. |
| Repo de sampling (`comun/ganancia.py`, curvas de corte, H3: optimizar sobre muestra) | Sí | Ganancia y corte por curva; H3 si hay que reoptimizar dentro de 15 min. |

## 2. Repos de la competencia 01 (relevamiento del 24-nov-2026)

### 2.1 Fuente y cobertura

**Cobertura: 46 repos encontrados en GitHub, reconciliados el 28-nov-2026 con la matriz de los 66 repos.**

**Reconciliación con los antecedentes.** La fuente principal de los repos de C01 es la matriz de técnicas y las
fichas de los 66 repos (`docs/antecedentes/competencia-1/postmortem_vercel/matriz.csv` y `fichas.csv`, lectura
automática de Emmanuel Valdez [Zulip 204115]), con el postmortem y el backlog que salen de ella
(`docs/antecedentes/competencia-1/`). Este relevamiento no la repite: agrega el commit revisado, el tipo de lags, la
relevancia para C02 y la ganancia pública declarada (§ 2.2), y las ideas verificadas con `archivo:línea` (§ 2.4–2.5).

| | Repos |
|---|---|
| En los dos (columna «En la matriz» de § 2.2) | 43 |
| Solo acá: `JFormoso/competencia1-dmeyf`, `jlazcanosimoniello/DMEyF-2026`, `marcostrigueros99/churn-bancario-dmeyf` (sus fichas siguen en el Anexo A) | 3 |
| Solo en la matriz, sin relevar acá: `AgustinBerna/dmeyf2026`, `AnaBe00/dmeyf2026`, `BrunoMicali/comp.1`, `ClariRZ/Primera-compentencia`, `ernestoatmo/prediccion_final_competencia1`, `esqale/dmeyf2026`, `FSteeb1/dmeyf2026`, `Guille70/dmeyf2026`, `hmijal/dmeyf2026`, `jgjuara/dmeyf2026`, `JuanDUrbano/dmeyf2026`, `lulimontero/maestria-data-mining-2026`, `MLDEVGIT/dmeyf2026-competencia-01` (el nuestro, § 1), `pedro-bosch/dmeyf2026`, `rflorenciad/dmeyf2026`, `segunmo/DM-EyF-2026`, `SofiaForni/primera_entrega_EYF`, `ssmito/dmeyf2026`, `thenseler-gmail/dmeyf2026`, `tobiartinian/Econom-a-y-Finanzas`, `TURRIvalentin/dmeyf2026`, `urbdaniel86/DMEyF`, `VeroQ00/Churn_Prediction_1` | 23 |

Todos los repos de `PROCEDENCIA.md` § Ideas de terceros están en la matriz. Lo que sigue de § 2.1 es la búsqueda
original del 24-nov.

Zulip requiere login y no hay credenciales en esta máquina: **no se leyó ningún mensaje con
enlaces**. El inventario no proviene de Zulip. Falta la columna "mensaje de origen" y no se sabe
qué repos enlazados en Zulip faltan acá (privados, borrados o con nombres que la búsqueda no
encuentra).

**Búsqueda.** API pública de GitHub sin autenticar: 15 consultas, 4 cortadas por límite de uso y
repetidas. Repos creados desde el 1-sep-2026 que mencionan DMEyF, competencia 01, BAJA+2 o churn.

| | Cantidad |
|---|---|
| Candidatos clonados (superficial, sin archivos > 1 MB, sin ejecutar nada) | 51 |
| Descartados: sin contenido de la materia (`wujparker/dmeyf`), otra competencia (`vmalsam/dmeyf2026-predfinal-victor_malsam`, Kaggle UTN 2026), vacíos (`AgustinBerna/DMEYF`, `DAD1990/DMEYF-2026`), sólo un enlace (`MarcosFedericoRios/enlacesDMEyF`) | 5 |
| **Repos de C01 2026 encontrados en GitHub y revisados** | **46** |
| … lectura completa | 35 |
| … lectura parcial (archivos > 1 MB sin bajar, notebooks sin outputs o carpetas borradas): `pfranzd` (72 omitidos), `JaquelineGirabel` (57), `tahiel53` (50), `vmanuelmarasco` (22), `RodPalDS` (20), `nicozare` (15), `CVFH` (13), `SnehitDua` (18 zips de modelos), `marcostrigueros99` (notebook de features), `BustosMaxx` (notebook), `Ani-victoria` (carpeta de entrega borrada en el último commit) | 11 |
| Nuestro (`MLDEVGIT/dmeyf2026-competencia-01`), no re-relevado: ver § 1 | 1 |

**46 repos y 48 fichas.** El Anexo A tenía 48 fichas (hoy quedan las 5 que la matriz no tiene): las 46 de los repos de C01 revisados más **dos fichas de una línea** de repos descartados, `wujparker/dmeyf` y `vmalsam/dmeyf2026-predfinal-victor_malsam`. Se conservan porque registran por qué se descartaron. La de `vmalsam` conserva además un dato técnico usado en la comparación con 202006 (12 columnas que ese workflow pone en NA en 202006). Los otros tres descartados (dos vacíos y `MarcosFedericoRios/enlacesDMEyF`, que solo contiene un enlace) no tienen ficha, y nuestro repo tampoco.

**Para reconciliar con Zulip** (tarea T9): pegar cada enlace con su id de mensaje y cruzarlo con
§ 2.2. Fuera de alcance, pero relevantes para C02 (experimentos colaborativos, no C01):
`nicozare/experimento-inflacion-dmeyf`, `ezequielabregu/DMEyF-2026-experi-colab-feature_historico`,
`germandasr/DMEyF_Exp_Colaborativos`, `mariofreites/dmeyf-experimentos-colaborativos`,
`esqale/dmeyf2026-experimento` y `tobiartinian/dmeyf-2026-experimentos`.

**Método.** Cinco revisores en paralelo (agentes) y la sesión principal, con una ficha estándar
por repo y lectura de código sin ejecutarlo. Cada dato se marca **[declarado]** (README,
comentarios u outputs guardados), **[código]** (verificado en el commit indicado) o
**[no encontrado]**. Lo que sostiene § 2.5 se volvió a verificar en la sesión principal, en el
archivo y las líneas citadas (✔ en § 2.4).

**Licencias.** Sólo `BustosMaxx/datamining_ecoyfin` tiene licencia (MIT). Los otros 45 no tienen:
por defecto, todos los derechos reservados. No se copia código ajeno. Las ideas se reimplementan
citando la fuente (`PROCEDENCIA.md` § Ideas de terceros). El repo de Agustina se puede reusar con
su acuerdo.

**Ganancia en los repos.** El código usa +1.072.500 por BAJA+2 enviado y −27.500 por cualquier
otro envío (ganancia **neta** por acierto). `farpp8` usa la forma con premio **bruto**:
1.100.000 · TP − 27.500 · envíos. Es la misma cuenta. Algunos README dicen 780.000 / −20.000: misma
razón 1/40, otra escala. Desglose y fuentes: `GANANCIA.md`.

### 2.2 Inventario

Orden alfabético. **Relevancia C02** = relación con un problema concreto de nuestro pipeline
(criterio en § 2.4). No es una evaluación de la calidad del trabajo. **Público declarado** =
ganancia pública informada por el autor, en millones; ninguna se verificó. Con el desvío entre
semillas que documenta `agustinarazanov/dmeyf` (1,8–2,5 M por archivo), diferencias de pocos
millones no son concluyentes.

| Repo (github.com/…) | Commit | Lags | Relevancia C02 | Público declarado (M) | En la matriz |
|---|---|---|---|---|---|
| aaav13/Competencia_01_DMEyF | f18361a | — | ninguna | — | sí |
| agustinarazanov/dmeyf | 11ff484 | fila | alta | 103,79 | sí |
| agustinlovrich/dmeyf-primera-competencia | 6ef281f | calendario | alta | 107,44 | sí |
| Ani-victoria/dmeyf2026-competencia01 | 21e0aaf | fila | alta | 110,47 | sí |
| ArielRojasV/PrediccionBajas_DMEyF | 9f30b84 | fila | baja | — | sí |
| BustosMaxx/datamining_ecoyfin (MIT) | 04e56b0 | — | baja | — | sí |
| CVFH/DMEYF_CVFH | 0539e93 | fila | media | — | sí |
| emavaldez/primeracompetencia | ec1fa75 | fila | alta | — | sí |
| ezequielabregu/DMEyF_competencia_1 | bc9f2a9 | fila | alta | 110,25 | sí |
| farpp8/dmeyf2026-competencia01 | fd33f7d | calendario ✔ | alta | 102,60 | sí |
| germandasr/DMEyF---1ra-Competencia | f0ff0ad | — | ninguna | — | sí |
| gromadzyn/dmeyfCompetencia1 | ac82cca | calendario | baja | — | sí |
| iespinozahDM/primeracompetencia-dmeyf | 9f73fa5 | fila | baja | 95,78 | sí |
| JaquelineGirabel/dmeyf2026 | be0ed8b | calendario | alta | — | sí |
| JFormoso/competencia1-dmeyf | 90740d0 | calendario | baja | — | **no** |
| jlazcanosimoniello/DMEyF-2026 | 4ffdbb8 | fila | ninguna | — | **no** |
| keilazavaglia/DMEyF_ksz | 5dbdef6 | fila | media | 104,61 | sí |
| kevinlpagnotta/DMEyF---Primera-Competencia | 391d0f9 | calendario | baja | — | sí |
| kformoso/Competencia1 | 56a820f | calendario | baja | — | sí |
| la-laguinge/dmeyf-2026-competencia-01 | 715cddf | fila; no carga 202107 ✔ | baja | 103,7 | sí |
| laupasq1967/Entrega-final-DMEyF | 395462d | fila | alta | 119,38 | sí |
| lsaldeco/Entrega_Competencia01 | 4bfbb08 | fila | baja | — | sí |
| LuisDanielSuarez/dmeyf-competencia1 | a48ed1e | calendario | media | — | sí |
| lvergini/dmeyf2026-competencia1 | 60033c0 | calendario | alta | — | sí |
| MarcosFedericoRios/primeracompetenciadmeyf | a29db2f | fila | baja | — | sí |
| marcostrigueros99/churn-bancario-dmeyf | cfc465c | fila | baja | 87,07 | **no** |
| mariofreites/dmeyf-primera-competencia | d9e572e | fila | alta | 106,21 | sí |
| mbellesi01/dmeyf2026-Competencia-1 | 407407d | fila | baja | — | sí |
| micaelarr/primeracompetencia | ebe30f0 | calendario | alta | — | sí |
| mmfiora/dmeyf2026-competencia-01 | 631d8a3 | calendario | alta | 105,02 | sí |
| montagnaflor/DMEyF-Competencia-01 | c9a71f6 | fila | alta | 101,12 | sí |
| nicobaranek/dmeyf-competencia-01 | 88ed240 | calendario | alta | 106,40 | sí |
| nicolasmatayoshi-code/dmeyf2026-competencia1-entrega | 37d68bc | calendario | media | — | sí |
| nicozare/primera-competencia-dmeyf | 0fc28e8 | fila | media | 93,3–96,6 | sí |
| pablogarciaparisi/dmeyf2026-competencia1 | bd3a731 | calendario | media | — | sí |
| patriciojarmoluk/dmeyf2026-competencia01 | 4b1e2fa | calendario | media | — | sí |
| pfranzd/dmeyf2026-entregas | 8f5e659 | calendario ✔ | alta | 110,17 | sí |
| RodPalDS/DMEF-Primera-Competencia-2026 | 28be952 | fila | alta | 95,59 | sí |
| SerenaDituro/Competencia1_DMEyF_2026 | 31d13c4 | calendario | media | — | sí |
| sgonzalezr96/DMFyE_C1 | 7390f7a | calendario | media | 101,42 o 100,43 (README y JSON no coinciden) | sí |
| SnehitDua/Churn-Prediction-DMEyF | b0f3d74 | calendario | baja | — | sí |
| tahiel53/DMEyF-competencia_1 | f7cd493 | fila | baja | — | sí |
| tomasfarias-hub/DMEYF | c1ef1a9 | — | baja | — | sí |
| tomasroel/DMeyf_Competencias | ab5eb70 | calendario | baja | — | sí |
| veritomonzon/dmeyf2026-personal | 279d520 | fila | media | 93,78 (entrega final); 103,18 (otro envío) | sí |
| vmanuelmarasco/dmeyf_2c_2026 | 5290716 | calendario | alta | — | sí |

### 2.3 Hallazgos transversales

| Tema | Qué se vio en los 46 repos |
|---|---|
| Modelo y objetivo | Casi todos LightGBM binario. Positivo BAJA+2 solo (p. ej. `sgonzalezr96`, `laupasq1967`) o BAJA+1 ∪ BAJA+2 (`Ani-victoria`, baseline 208135). Multiclase en `emavaldez` (BAJA+1 a peso 0,5) y `kformoso`. Undersampling de CONTINUA (0,1–0,25) con probabilidad corregida en `JaquelineGirabel`, `vmanuelmarasco` y `emavaldez`. |
| Lags | 21 por calendario, 21 por fila y 4 sin lags o sin determinar. Efecto de los lags por fila cuando falta un mes en la carga: `la-laguinge` ✔ (`03_entrenar_y_predecir_M4_final.py:53`) no carga 202107, y en 202108 el `lag1` toma junio. |
| Monetarias y drift | Tres familias: (a) **escala dentro del mes**: rank con cero fijo (`pfranzd`, `RodPalDS`, `agustinlovrich`, `veritomonzon`), percentil con signo solo para montos con drift (`emavaldez`), max-abs (`sgonzalezr96`); (b) **IPC** (`micaelarr`, que conserva nominales los límites de tarjeta); (c) **anular la columna rota del mes antes de lags** (`agustinarazanov` ✔, `lvergini` ✔ detección automática, `vmanuelmarasco` ✔ más PSI, `emavaldez`). **Hay evidencia en contra** [declarado]: rank por mes −19 M (`keilazavaglia`); rankear y después lags peor que lags sobre crudos (`veritomonzon`); deflactar todos los montos pierde (`agustinarazanov`). |
| Validación | Casi todos optimizan con train 202103–04/05 y validan en 202106. Variantes: varios cortes temporales (`farpp8`), mitades A/B fijas de junio (`RodPalDS`), mes de hueco (`lvergini`). Comportamientos que el pipeline de C02 no replica: validación cruzada con filas del mismo mes en train y validación; selección de variables y validación en el mismo mes; `bagging_fraction` sin `bagging_freq` (sin efecto en LightGBM). Varios declaran haber elegido variante o corte con la ganancia pública [declarado]. |
| Métrica de optimización | Mayoría AUC. Ganancia suavizada en `micaelarr`, `Ani-victoria` e `iespinozah`. Para decidir variables, `ezequielabregu` usa 10 semillas, ganancia suavizada y Wilcoxon pareado. |
| Corte | Cantidad fija elegida con el público (mayoría); meseta de curva suavizada (`mariofreites`, `pfranzd`, `lvergini`); **arrepentimiento mínimo entre meses** (`farpp8` ✔, `agustinarazanov` ✔, `keilazavaglia`); **proporción de la cartera** (`montagnaflor`, `tomasfarias-hub`, `pfranzd` con reescalado); umbral teórico 1/40 (`vmanuelmarasco`). |
| Semillas y ensambles | 5 a 100 semillas. Promedio de probabilidades o de rankings; ensamble por rango de dos familias en `pfranzd` y `laupasq1967`; especialista por segmento en `emavaldez`; tres modelos por historia disponible en `CVFH`. |
| Meses sin etiqueta | Solo `nicobaranek` ✔ usa pseudoetiquetas ("docente", top-k). En producción etiqueta también el mes que predice, 202108. `LuisDanielSuarez` lo probó sin usarlo. |
| Tiempos [declarado] | Inferencia con modelos ya entrenados: < 10 s (`la-laguinge`), ~1 h (`pfranzd`, muchos modelos). Entrenamiento: de 4 min (`farpp8`, base) a 18 h (`tahiel53`). Por semilla: 7–35 s por modelo de backtest (`ezequielabregu`), ~40 s (`emavaldez`, 18 núcleos). |
| Reproducibilidad | Con sha256 del dataset y de la salida (`emavaldez`, `farpp8`, `pfranzd`, `agustinarazanov`, `nicobaranek`). En otros: rutas absolutas, versiones sin fijar o notebooks sin outputs. |

### 2.4 Selección para revisión en profundidad

Criterio: resolver un problema concreto de nuestro pipeline (B1–B13 de `TAREAS.md`), ser
aplicable mes a mes sin mirar el futuro y poder validarse con 201901–201912.

| # | Idea | Repos fuente (verificado ✔) | Problema nuestro |
|---|---|---|---|
| I1 | Lags por calendario con indicador de hueco | `farpp8` ✔ `02_variables.py:84-103`, `pfranzd` ✔ `pipeline/features/temporales.py:15-33`, `JaquelineGirabel`, `agustinlovrich`, nuestro C01 | B10, lags que mezclan antigüedades |
| I2 | Columnas rotas: detectar y pasar a NA el mes antes de lags; PSI de entrada | `vmanuelmarasco` ✔ `pipeline/p10_adaptativo.py:879-945`, `lvergini` ✔ `evaluacion_junio/R/fe.R:200`, `agustinarazanov` ✔ `scripts/c200_lags_todo.py:53-59`, `emavaldez` (`ROTAS`) | 202006 (47 columnas en cero), B10 |
| I3 | Escala por mes de los montos | `pfranzd` ✔ `pipeline/features/rankings.py:47-70`, `emavaldez` (`PERCENTIL_CERO_FIJO`), `sgonzalezr96` (max-abs), `micaelarr` (IPC) | Drift en pesos entre 2019 y 2020 |
| I4 | Corte por arrepentimiento mínimo, expresado como proporción | `agustinarazanov` ✔ `src/competencia.py:232-254`, `farpp8` ✔ `origen/regla_n.py`, `montagnaflor` | B6, B7 |
| I5 | Multiclase con BAJA+1 a medio peso | `emavaldez`, `kformoso`, nuestro C01 | Segundo modelo (B5) |
| I6 | Ensamble por rango de dos familias | `pfranzd`, `laupasq1967`, `agustinarazanov` (`ensamble_por_rank`) | Recomendación (B6) |
| I7 | Pseudoetiquetas para meses sin clase | `nicobaranek` ✔ `codigo/motor.R:255-266` | Target de 201911–201912 |
| I8 | Decisión con semillas pareadas | `ezequielabregu` | Método para elegir entre I1–I7 |

### 2.5 Propuestas

Todas se validan **solo con 201901–201912** (R1). **Esquema de validación (V)**, detallado en
`PLAN_PRUEBAS.md` § 1:
- entrenamiento 201903–201906, con 201907 como hueco;
- **desarrollo y elección de cortes en 201908 y 201909**, por separado;
- **201910 reservado** para una única evaluación final con el protocolo congelado.

Octubre ya se usó como test en el experimento de sampling: el antecedente y cómo tratarlo están en
`PLAN_PRUEBAS.md` § 2. La métrica es la ganancia (`GANANCIA.md`) sobre la curva suavizada (media
móvil de 501) en el corte de cada propuesta, más la transferencia del corte entre agosto y
septiembre. Se compara con semillas pareadas (I8). Los meses 202001–202006 sólo sirven para
medir tiempos y comprobar la operación. La numeración de experimentos (E01–E06, T01, F01) está en
`PLAN_PRUEBAS.md` § 4.

**P1 · Lags por calendario + `lagk_disponible` (I1).**
- *Problema:* `features.py` toma la k-ésima observación previa. Si un cliente falta un mes,
  `lag1` es un dato más viejo sin aviso (el mismo efecto que en `la-laguinge`, a nivel de cliente). Además,
  ante un mes faltante en la serie, hoy sólo se puede rechazar.
- *Adaptación:* mismo SQL en DuckDB, pero el lag se une por
  `(cliente, periodo − k)` con `periodo = año·12 + mes` (reimplementado; idea de
  `farpp8`/`pfranzd`). Agrega `lag1_disponible` y `lag2_disponible`. El mismo módulo sirve
  para entrenamiento y producción; repetir la prueba de equivalencia bit a bit. Con esto, un
  mes faltante deja lags NULL en lugar de bloquear: la política de B10 puede elegir
  procesar con aviso.
- *Validación:* E05. V con fila contra calendario. Además, una prueba sintética: borrar 201907 de
  la historia y comparar las dos versiones en 201908.

**P2 · Columnas rotas → NA en ese mes antes de los lags, más el reporte de drift (I2).**
- *Problema:* en 202006 hay 47 columnas con todos los observados en 0. El pipeline advierte
  pero las usa, y la prueba de robustez mostró que una sola variable importante en 0
  cambia el 17–20 % del top-1.000.
- *Adaptación:* regla fijada con 2019: una columna está rota en el mes *t* si es 100 % nula
  o tiene todos los observados en 0, y no lo estaba en la mayoría de los meses anteriores
  (criterio de `vmanuelmarasco`/`lvergini`). En producción se aplica al mes que llega,
  antes de calcular features; se guarda corregida en la historia y se informa en el
  reporte como incidente "corregido". Se suma un PSI por variable contra 2019, con NaN como
  bin aparte (`keilazavaglia`, `montagnaflor`), para el reporte acumulado.
- *Validación:* E06 (`PLAN_PRUEBAS.md` § 3). Separa detección, alerta y tratamiento. La
  sustitución por NA no se adopta sin prueba: en la robustez del 2-nov, `mcaja_ahorro` en NULL
  alteró más la selección que en 0 (800 contra 827 de 1.000 coincidentes). Se compara contra
  "último valor" e inyección del patrón de 202006 en los meses de desarrollo. Caso real en 2019
  para medir falsos positivos de la detección: 201905. 201910 queda reservado.

**P3 · Escala por mes de los montos (I3), como variante, no por defecto.**
- *Problema:* la inflación de 2019–2020 corre los montos. Un corte en pesos aprendido en
  2019 no vale lo mismo en 2020.
- *Adaptación:* tres opciones, todas calculables con el mes solo y por lo tanto seguras en producción.
  Se comparan entre sí, y las escaladas se calculan antes de los lags:
  (a) rank con cero fijo de todos los montos;
  (b) percentil con signo sólo para los montos con drift medido en 2019;
  (c) división por la mediana mensual.
  Descartado: IPC externo, porque agrega un dato que no viene en el CSV y que hay que tener
  para 2020.
- *Validación:* E03. Hay evidencia mixta en los repos (−19 M declarado en `keilazavaglia`), así
  que sólo se adopta si gana en agosto **y** en septiembre y no empeora la transferencia del corte.

**P4 · Corte por proporción con arrepentimiento mínimo (I4).**
- *Problema:* el cupo fijo de 1.000 es diagnóstico. La cantidad de clientes cambia (142 a
  153 mil en 2020) y la prevalencia del mes en vivo es desconocida.
- *Adaptación:* curvas de ganancia en 201908 y 201909, con la cantidad de envíos
  expresada como fracción *f* de los clientes del mes. Se elige el *f* con menor
  arrepentimiento máximo (pérdida relativa al óptimo de cada mes, como en `agustinarazanov`).
  En producción, `enviar` = los ⌈*f*·n⌉ de mayor score. Nueva subclase de `Estrategia`;
  la elección de *f* queda registrada con su fecha y no se toca en vivo.
- *Validación:* transferencia cruzada: elegir *f* en agosto y medir el arrepentimiento en
  septiembre, y al revés (implementado en E01). Comparar con el umbral teórico 1/40 sobre la
  probabilidad calibrada.

**P5 · Multiclase con BAJA+1 a medio peso (I5).**
- *Problema:* el baseline mezcla BAJA+1 y BAJA+2 como positivo, pero solo BAJA+2 paga.
- *Adaptación:* LightGBM multiclase; el score es P(BAJA+2), y P(BAJA+1)+P(BAJA+2) se registra
  como diagnóstico. El pipeline de inferencia tiene que tomar la columna de la clase (hoy espera
  una sola probabilidad).
- *Validación:* en dos pasos separados. **E01**: binario contra multiclase sin pesos, con
  features, hiperparámetros y semillas idénticos. **E02**: peso de BAJA+1 (0,25, 0,5 y 1).

**P6 · Pseudoetiquetas para 201911–201912 (I7), condicionada.**
- *Problema:* la consigna (CONSIGNA § Contradicción) deja a 201911–201912 sin etiqueta
  completa, y son los meses más cercanos a 2020.
- *Adaptación:* un modelo entrenado con ≤ 201910 etiqueta 201911–201912 (top-k o umbral)
  y se reentrena sumándolos. **No usa datos de 2020**, así que no depende de la aclaración.
  No se pseudoetiqueta nunca el mes que se predice (diferencia con `nicobaranek`).
- *Validación:* simularlo corrido hacia atrás dentro de 2019, sin tocar octubre:
  - modelo con etiquetas reales de 201903–201904;
  - el mismo más pseudoetiquetas de 201905–201906;
  - el de etiquetas reales de 201903–201906 como cota.

  Los tres se miden en 201908 y 201909. Prioridad baja.

**P7 · Presupuesto de inferencia (transversal).**
- *Problema:* el tiempo de `predict` crece con árboles × semillas × modelos. Hoy son 100
  árboles y 17 s de inferencia en el pipeline. Medición con modelos de 300 rondas y
  estimaciones marcadas como tales: `PLAN_PRUEBAS.md` § 6 (T01).
- *Adaptación:* medir en la máquina del vivo segundos por 1.000 árboles sobre 150 mil filas.
  Con eso se fija un tope de árboles × semillas por estrategia que deje ≥ 5 min de margen
  (la idea de achicar variables con canaritos, de `mariofreites`, baja memoria y entrenamiento,
  no tanto el `predict`).
- *Validación:* cronometrar con un mes de ensayo (operativo, permitido).

### 2.6 Propuesta para nuestras dos estrategias

Ambas se entrenan offline con 2019 y comparten P1 (lags por calendario), P2 (columnas
rotas a NA) y el pipeline de inferencia actual. El corte de cada una se elige con P4.

| | **Estrategia A — "baseline robusto"** | **Estrategia B — "invariante a escala"** |
|---|---|---|
| Objetivo | Binario BAJA+1 ∪ BAJA+2, como el baseline de la cátedra (208135); referencia tras E01 | Multiclase, score P(BAJA+2). E01 no cumplió la regla de adopción (empate en septiembre) y el peso de BAJA+1 se decide en E02 (`PLAN_PRUEBAS.md` § 5) |
| Features | 152 crudas + lag/delta 1–2 por calendario + disponibilidad | Las mismas, con los montos escalados por mes según P3 (la variante que gane en V) |
| Hiperparámetros | Optuna sobre los cinco de 208135, train 201903–201906, valid 201908 | Ídem, estudio propio |
| Semillas | Las que permita el presupuesto de T01 (`PLAN_PRUEBAS.md` § 6), con promedio de probabilidades | Ídem. Un multiclase cuesta ~4 veces más en `predict` |
| Corte | *f*_A por arrepentimiento mínimo en V | *f*_B ídem |
| Qué cubre | Mismo modelo que el resto del curso, interpretable, con el menor riesgo | La deriva de 2020 en pesos, que A no corrige |

**Recomendación por cliente (R4).** La regla se fija antes del vivo con V. Se comparan tres
candidatos: A, B y **A+B por rango** (I6, promedio de rangos, corte *f*_AB). La
recomendación es el candidato con menor arrepentimiento máximo en los dos meses de desarrollo (201908 y 201909).
`enviar` en `churn_<yyyymm>.csv` sale de ese candidato; las decisiones de las otras dos
quedan en `decisiones_<yyyymm>.csv` y en el reporte (solapamiento, Jaccard, drift).
Si no hay diferencia significativa entre A y B, se recomienda A+B, que según
`pfranzd` y `laupasq1967` usan en su entrega final [declarado].

**Qué no se propone y por qué.**
- Especialistas por segmento y segunda etapa (`emavaldez`): demasiadas piezas para validar
  con dos meses de desarrollo.
- Más de ~20 semillas o BO larga: no se descarta para el entrenamiento offline, pero
  la inferencia (P7) manda.
- Elegir con el público o con meses de 2020: lo prohíbe R1.

**Procedencia.** Ninguna propuesta copia código. Las ideas se reimplementan y se citan en
`PROCEDENCIA.md` § Ideas de terceros (repo, commit y archivo:línea).

## 3. Fuentes de las decisiones tomadas en esta base

| Decisión | Fuente |
|---|---|
| Reusar el pipeline de inferencia tal cual | Equivalencia bit a bit con 201908 y 202001 (README del pipeline original; § 4). |
| Rutas por configuración | Pedido del grupo; patrón `DATOS_DIR` del repo de sampling. |
| Mantener estrategias provisionales | No hay decisión de corte tomada con ensayos; no se eligió nada nuevo. |
| Propuestas P1–P7 y estrategias A/B (§ 2.5–2.6) | Repos de C01 citados en § 2.4, con archivo y línea; ninguna está adoptada todavía: cada una espera su validación V con 2019. |

## 4. Primera verificación (24-nov-2026, esta máquina: 8 hilos, 15,7 GB)

Entorno `ejecuciones/entornos/ensayo_202001_20261124T080311` (historia 201901–201912, modelo diagnóstico).

| Chequeo | Resultado |
|---|---|
| Crear entorno (fuera del tiempo mensual) | 60 s |
| `ejecutar_mes` 202001 | completado / con_alertas, **92,9 s** (validación 28,4 · features 44,4 · inferencia 17,3 · estrategias 2,1); pico commit 4,0 GB |
| Esquema de salida | `numero_de_cliente,probabilidad,enviar` exacto |
| Clientes | 142.929, sin duplicados, idénticos a la entrada |
| Probabilidades | finitas, en [0,1]; mediana 2,8e-4, p99 0,22; 7 exactamente en 1 y 1 en 0 |
| Envíos | 1.000 (0,70 %), todos con probabilidad ≥ 0,414 > cualquier no enviado |
| Reproducibilidad | `churn_202001.csv` **idéntico byte a byte** al de la secuencia del 2-nov |

El tiempo duplica el del 2-nov (43 s): probablemente carga de la máquina y el antivirus
(TmCCSF abre los Parquet). Sigue lejos de los 900 s. Si se agrega reentrenamiento, el
presupuesto cambia por completo.

---

## Anexo A · Fichas por repositorio

Las fichas de los repos que están en la matriz de los 66 (`docs/antecedentes/competencia-1/postmortem_vercel/`, § 2.1) **no se repiten acá**: su descripción está en `fichas.csv` y sus técnicas en `matriz.csv`. Quedan solo las 5 fichas que la matriz no tiene (los tres repos de C01 que no figuran en ella y los dos descartados) y, por lote, los enfoques relacionados con el pipeline de C02, que citan commit y `archivo:línea`. Las 48 fichas originales, con esas citas por repo, siguen en la historia de git: `git show 5d85631:docs/RELEVAMIENTO.md`.

Marcas: **[declarado]** (README, comentarios u outputs guardados del autor), **[código]** (verificado leyendo el código en el commit indicado), **[no encontrado]**. Las rutas `archivo:línea` son relativas a cada repo en ese commit. La relevancia se refiere al pipeline de C02 (criterio en § 2.4), no a la calidad del trabajo. Revisión de solo lectura: no se ejecutó código externo.

### Lote A

Base de rutas: `repos_externos/<owner>_<repo>/`. Ningún repo del lote tiene archivo LICENSE ⇒ **todos sin licencia: todos los derechos reservados; no copiar código, solo ideas**.
Ganancia por envío (verificada en cada repo): 4 de 5 usan **+1.072.500 / −27.500**; farpp8 usa **+1.100.000 / −27.500**. Ninguno usa 780.000/20.000.

---

### Lote A — enfoques relacionados con el pipeline de C02

1. **Lags por calendario exacto** — problema de C02: lags por calendario con meses faltantes.
   - farpp8/dmeyf2026-competencia01 (fd33f7d), `02_variables.py:84-103`: lag k = mes t−k exacto, NA si falta, con test (`test_02_variables.py`).
   - LuisDanielSuarez/dmeyf-competencia1 (a48ed1e), `preproc_comun.py:45-83`: versión vectorizada vía `searchsorted`, con tendencia y promedio de 3 meses también por calendario.
2. **Elección de N sobre varios meses y escenarios** — problema de C02: corte estable frente al drift mensual de producción.
   - farpp8/dmeyf2026-competencia01 (fd33f7d), `origen/regla_n.py:18-31`: minimax-regret sobre cortes temporales y escenarios estresados.
3. **Reparaciones con log y controles por mes** — problema de C02: detección y neutralización de columnas en cero en 202006.
   - farpp8/dmeyf2026-competencia01 (fd33f7d), `01_preparar_datos.py:57-60,159-204`.
4. **Rank con cero fijo por mes y variables de abandono de productos** — problema de C02: inflación 2019–2021 sin IPC y FE calculable con el mes actual y 2 previos dentro de ≤15 min.
   - RodPalDS/DMEF-Primera-Competencia-2026 (28be952), `03c_fe_extra.py:119-131` (rank) y `03c_fe_extra.py:146-167` (`n_apagados`/`n_dejo_de_usar`).
   - mariofreites/dmeyf-primera-competencia (d9e572e), `02_c9923_variables_nuevas/design.md` (`cproductos_perdidos`/`tperdio_payroll`); selección por canaritos a 128 variables (`01_c9920_canaritos_asesinos/design.md`), que reduce la latencia. Público declarado: 106,2.
5. **Protocolo de validación con reglas fijadas a priori** — problema de C02: entrenamiento offline 201901–201912 (por ejemplo, entrenar hasta 201908 y validar 201910 con mitades).
   - RodPalDS/DMEF-Primera-Competencia-2026 (28be952), `08_bo_fuera_de_tiempo.py:134-150`: mitades A/B y meseta.
   - farpp8/dmeyf2026-competencia01 (fd33f7d), `DECISIONES.md:36-41`: regla de reemplazo; métrica = media de la curva en vez del máximo.
   - 201911 y 201912 tienen target incompleto. La pseudo-etiqueta de LuisDanielSuarez/dmeyf-competencia1 (`02_etapa1_L20.py:36-45`) es una variante a probar, sin validación en el repo.

### Lote B

Convención: **[declarado]** = README/comentarios/outputs guardados · **[código]** = verificado leyendo código · **[no encontrado]**.
Ganancia C01 en los 4 repos: **+1.072.500 por BAJA+2 / −27.500 por envío errado** (no 780.000/20.000) **[código]**; umbral de equilibrio 0,025. Entrega por bot de Zulip (no Kaggle), 8.000–15.000 ids **[declarado]**.
Ninguno de los 4 repos tiene archivo LICENSE ⇒ **todos los derechos reservados: no copiar código, solo ideas.**

---

### Lote B — enfoques relacionados con el pipeline de C02

1. **Lags por calendario con huecos explícitos + anulación de la columna anómala antes de los lags** — problema de C02: columnas en cero de 202006; con lags por fila o sin anular, los deltas de 202007/202008 heredan los ceros, y con lag por calendario + NULL en el mes anómalo el lag queda NaN.
   - JaquelineGirabel/dmeyf2026 (be0ed8b), `generate_features_extendido.py:638-699` + `flag_gap_mes` (:308-318).
   - agustinarazanov/dmeyf (11ff484), `c200_lags_todo.py:56-60`.
2. **Corte robusto a prevalencia desconocida** — problema de C02: regla de "enviar" estable mes a mes y columna `probabilidad` calibrada.
   - agustinarazanov/dmeyf (11ff484), `src/competencia.py:232-254` (minimax regret entre meses) y :226-229 (ensamble por rango, un `Dataset` por semilla).
   - keilazavaglia/DMEyF_ksz (5dbdef6), z021 (minimax entre dos meses).
   - JaquelineGirabel/dmeyf2026 (be0ed8b), `undersampling.py:28-33` y umbral 0,025/s en `particiones.py:30-37` (probabilidad corregida por undersampling).
3. **≥2 estrategias con fallback por disponibilidad de historia + PSI por columna** — problema de C02: requisito de ≥2 modelos/estrategias y elección en producción del modelo por cliente o mes.
   - CVFH/DMEYF_CVFH (0539e93), script:135-146 (current/hist1/hist2 con ventanas propias).
   - keilazavaglia/DMEyF_ksz (5dbdef6), z008 celda 2 (PSI automático por columna).
4. **Uso del target incompleto de fin de 2019** — problema de C02: meses 201911/201912 sin etiqueta completa.
   - agustinarazanov/dmeyf (11ff484), `scripts/c271_mezcla_h1.py` (modelo de horizonte 1 con BAJA+1).
   - CVFH/DMEYF_CVFH (0539e93), FE celda 6 (clase con `LEAD` + NULL).

### Lote C

Convenciones: **[declarado]** = README/comentarios/outputs guardados; **[código]** = verificado leyendo código; **[no encontrado]**.
Rutas relativas a la raíz de cada repo. Ningún repo del lote tiene archivo LICENSE ⇒ **todos los derechos reservados: no copiar código, solo ideas**.
Ganancia: en el código de todos los repos C01 la constante es **+1.072.500 (BAJA+2) / −27.500** (umbral 1/40 = 0,025), no 780.000/−20.000. Solo el README de pfranzd dice 780.000/−20.000 (el umbral es el mismo, 1/40).

---

#### wujparker/dmeyf — commit 9728a69 (2026-09-24)
Descartado. Contenido sin relación con la materia: 500 archivos `.md` sobre otro tema (lotería "快3"); un solo commit; sin código.

---

#### vmalsam/dmeyf2026-predfinal-victor_malsam — commit 35c7e86 (2026-09-22)
Descartado. Corresponde a otra competencia: workflow "Gerencial" z719 de Kaggle `utn-2026-virtual-mgr`, dataset `gerencial_competencia_2026.csv.gz` del bucket `itba2026`, futuro = 202109, cortes de 800 a 1.300 y score público 25.318 [notebook, celdas 0, 7, 9; `Validacion_Victor/README.md`]. Dato técnico conservado para C02: el dataset **incluye 202006** y la celda 26 pone en NA para ese mes esta lista de columnas: `internet`, `mrentabilidad`, `mrentabilidad_annual`, `mcomisiones`, `mactivos_margen`, `mpasivos_margen`, `mcuentas_saldo`, `ctarjeta_visa_transacciones`, `mtarjeta_visa_consumo`, `mtarjeta_master_consumo`, `ccallcenter_transacciones`, `chomebanking_transacciones`; permite contrastar el detector propio. También declara que una media móvil de 6 meses (ma6) "casi" iguala a la referencia y que lag4 da menor resultado (README). Lags con `shift` por fila. Relevancia para el pipeline de C02: baja — solo por la lista de columnas de 202006.

---

### Lote C — enfoques relacionados con el pipeline de C02

1. **Panel denso con lags por calendario + montos por mes antes de lags + ensamble de rankings** — problemas de C02: lags por calendario con historia faltante, inflación 2019–2021 sin IPC externo y requisito de ≥2 modelos/estrategias.
   - pfranzd/dmeyf2026-entregas (8f5e659): CROSS JOIN cliente×mes (`temporales.py:15-33`); `rank_cero_fijo`/`deflactado` (`rankings.py:47-70`); promedio de rankings normalizados con Jaccard de top-N (`ensamble.py`).
   - veritomonzon/dmeyf2026-personal (279d520) reporta que rank→lags dio menor ganancia que lags sobre crudos (M3 385 M vs M1 407 M en 202106) **[declarado]**; ambos órdenes requieren medición.
2. **Diagnóstico automático por mes (columnas anómalas + PSI) con reparación a NULL que compite como candidato, y corrección de probabilidad por undersampling** — problemas de C02: columnas en cero de 202006 y **control de calidad de cada `input/<yyyymm>.csv` en producción**.
   - vmanuelmarasco/dmeyf_2c_2026 (5290716), `p10_adaptativo.py:879-945, 472-481` y `:350-362`.
   - Contraste con la lista de columnas de 202006 de vmalsam/dmeyf2026-predfinal-victor_malsam (35c7e86), celda 26.
3. **Protocolo para ponderar meses** — problema de C02: decidir si se baja el peso de 2020 en el train 201901–201912 (requiere adaptarlo a esas fechas).
   - veritomonzon/dmeyf2026-personal (279d520), README de Segunda competencia: 201901–202104 / gap 202105 / test 202106, pesos normalizados, placebo, invertidos, TOST con δ = desvío entre semillas.

### Lote D

Notas generales del lote:
- **Ganancia de C01 2026 = +1.072.500 por BAJA+2 contactado / −27.500 por cualquier otro envío** (no 780.000/−20.000). Coinciden 8 de los 10 repos: **[código]** lovrich `run_rank_prestamos_junbo_hist.R:337`, laguinge `02_optuna_bimodal_v64.py:93`, montagnaflor (celda c06), nicobaranek `motor.R:129`, y **[declarado]** en los README de marcostrigueros, ezequielabregu y tomasfarias.
- **Licencias:** ninguno de los 10 repos tiene LICENSE (`git ls-tree`; en todo el pool solo BustosMaxx tiene uno) ⇒ **sin licencia: todos los derechos reservados. No copiar código, solo ideas.**
- Meses de C01: 202103–202108. La clase de 202107 está incompleta, la de 202108 es desconocida. Casi todos validan con "train 202103–04 → test 202106" (mismo hueco de 2 meses que junio → agosto).
- Patrón que se repite en el lote: `ccajas_depositos` toda en cero en 202105 → NA. Es el análogo de las columnas en cero de 202006 en C02.

---

#### marcostrigueros99/churn-bancario-dmeyf — commit cfc465c (2026-10-12)
- URL: https://github.com/marcostrigueros99/churn-bancario-dmeyf
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: falta `06_modelo_v4_submision.ipynb` (1.17 MB), que es el que genera `dataset_fe_v3`. Se leyó `04_fe_modelo_optuna.ipynb` completo, extractos de 07, el README, `docs/resultados.md`, el CSV de métricas y los params.
- Modelo y objetivo: LightGBM binario **solo BAJA+2** (`es_baja2`; las BAJA+1 y los meses sin target quedan en NaN y se excluyen del train). Usa `scale_pos_weight` (también optimizado). Probó una cascada BAJA+1/BAJA+2, que dio 67 M **[declarado]**.
- Features **[código]**, nb04:
  - lag1 y delta1 con `groupby.shift` (**por fila**), y delta relativo recortado a ±10.
  - tend3 con `polyfit` sobre rolling de 3 filas, ratios, flags `primer_mes`, `tiene_visa`, etc.
  - Interpolación lineal de NaN aislados (limit = 1) **con `limit_direction='both'`**: usa el valor del mes siguiente, que en producción no está disponible.
- Monetarias y drift: no hay ranking ni deflactación. Los préstamos se marcaron como "leakage", pero al sacarlos la ganancia bajó **[declarado]**.
- Validación: walk-forward F2/F3/F4 con **hueco 0** (train 202103–05 → test 202106). Optuna TPE con 50 trials (nb04) / 20 trials en el "kitchen sink" (nb07), incluido `n_meses_train` como hiperparámetro. Objetivo: ganancia en el **umbral óptimo**.
- Corte: **umbral de probabilidad**; en el final usa el promedio de los umbrales óptimos de cada fold (nb04 cell-38). Para los submits usó 5 cortes alrededor del N de F4 **[declarado]**.
- Semillas: 4 semillas × 5 cortes por submit **[declarado]**.
- Resultados **[declarado]**: público 87.07 M. F4 431 M.
- Reproducibilidad: rutas de Drive, parquets fuera del repo, seed 42 y falta el notebook que genera el dataset final.
- Aprovechable para C02:
  1. `n_meses_train` como hiperparámetro de la BO (nb07): aplicable a la elección de la ventana dentro de 2019.
  2. El umbral de probabilidad óptimo se desplaza entre folds (0.15–0.85 en `metricas_experimentos.csv`); un corte por cantidad o proporción no depende de ese desplazamiento.
- Relevancia para el pipeline de C02: baja — lags por fila, interpolación que usa el mes siguiente y corte por umbral de probabilidad; aplicable solo `n_meses_train` como hiperparámetro.

### Lote D — enfoques relacionados con el pipeline de C02

1. **Pseudo-etiquetas + lags por calendario** — problema de C02: meses 201911/201912 sin target completo (usarlos con pseudo-etiquetas de un modelo entrenado hasta 201910 en vez de descartarlos).
   - nicobaranek/dmeyf-competencia-01 (88ed240), `motor.R:101-108`, `motor.R:255-266`, `motor_integral.R:56-75`: un docente etiqueta los meses incompletos (top-k) y las etiquetas se suman al train; +16 a +21 M en el backtest de junio. En ese backtest también se pseudo-etiqueta el mes de evaluación; la validación en C02 requiere excluirlo. El repo usa hashes del crudo y de la entrega, aplicables al reporte.
2. **Protocolo de decisión estadístico** — problema de C02: decidir **lags por fila vs por calendario** y qué columnas anular en 202006 con datos 2019.
   - ezequielabregu/DMEyF_competencia_1 (bc9f2a9), `05_variables.ipynb` celdas ca3f5d88/552b2d67; `04_drift.ipynb`: cada bloque de variables o limpieza se adopta con 10 semillas, meseta suavizada (ventana 501) y Wilcoxon pareado; identifica columnas con valores anómalos en un mes y las excluye. Público declarado: 110.25.
3. **Transformación por mes y corte** — problemas de C02: inflación sin IPC, alarma ante columnas en cero en producción y adaptación del corte al tamaño de cada `input/<yyyymm>.csv`.
   - agustinlovrich/dmeyf-primera-competencia (6ef281f), `run_rank_prestamos_junbo_hist.R:241-268`: ranking con signo por mes en reemplazo de los montos crudos, lags y deltas por calendario exacto; corte por la media entre semillas. Público declarado: 107.44.
   - montagnaflor/DMEyF-Competencia-01 (c9a71f6), celdas c12-c13: PSI train vs mes a predecir con bin de nulos; c37: corte como **proporción de la cartera**.

Lags por fila con un mes faltante en la carga: en la-laguinge/dmeyf-2026-competencia-01 (715cddf), 202108 recibe junio como "lag1" porque 202107 no está en la carga (`03_entrenar_y_predecir_M4_final.py:53`). Clasificación del lote: lags por calendario en agustinlovrich, nicobaranek, kevinlpagnotta y tomasroel; por fila en montagnaflor, ezequielabregu, marcostrigueros99, germandasr y tomasfarias-hub.

### Lote E

Método: solo lectura (README, código R/py, notebooks .ipynb leídos como JSON; no se ejecutó nada).
Convenciones: **[declarado]** = README/comentarios/outputs guardados; **[código]** = verificado leyendo código; **[no encontrado]**.
"celda N" = índice 0-based de celda en el .ipynb. Ningún repo del lote tiene archivo LICENSE ⇒ **sin licencia: todos los derechos reservados; solo ideas** (vale para las 19 fichas). Ningún archivo del lote supera 1 MB (máx. `bayesiana.RDATA` 764 KB), así que no hubo omisiones por tamaño.
Ganancia: casi todos usan +1.072.500 / −27.500 (ratio 39). Ani-victoria usa 780.000/−20.000 y mbellesi 273.000/−7.000: mismo ratio 39 ⇒ mismo orden y mismo corte óptimo. iespinozah usa 117.500/−27.500, pero con K fijo (10.000) la suma es monótona en aciertos ⇒ elige el mismo modelo.

---

#### JFormoso/competencia1-dmeyf — commit 90740d0 (2026-10-12)
- https://github.com/JFormoso/competencia1-dmeyf · sin licencia · Cobertura: 3 scripts R; **falta `tendencia.R`**, que `optimizacion-hiperparam.R:182` carga con `source`; BO cortada (25/30) y BO_log no incluido **[declarado]**.
- Modelo: LightGBM binario BAJA+1+2, sin undersampling, lr 0,005 e hiperparámetros de la cátedra.
- Features: **lags/deltas 1–2 por calendario** con *update join* sobre `periodo0+k` (`prediccion-agosto-v2.R:207-225`, `optimizacion-hiperparam.R:157-178`) + `TendenciaYmuchomas` (ventana 3, por fila) + `_zero` + rank cero fijo `dense` por mes.
- Orden de operaciones en la BO **[código]**: el filtro `meses_usados <- c(202103,202104,202106)` se aplica **antes** de calcular los lags (`optimizacion-hiperparam.R:143`); con ese orden, todos los lags de 202106 quedan en NA. Además valida 70/30 dentro de 03–04 (no out-of-time).
- Corte: 11.750 fijo. Semillas: 20 previstas, solo 2 corridas (las que entraron en la entrega) **[declarado]**.
- Resultados: **[no encontrado]**. Reproducibilidad: `here::here()`, `deterministic=TRUE`, avance reanudable con "firma" **[código]**.
- **Aprovechable C02**: patrón de lag por calendario con join (`prediccion-agosto-v2.R:207-225`).
- Relevancia para el pipeline de C02: baja — implementación de lag por calendario con join; la BO calcula los lags después de filtrar meses y valida dentro de los meses de train.

#### jlazcanosimoniello/DMEyF-2026 — commit 4ffdbb8 (2026-10-11)
- https://github.com/jlazcanosimoniello/DMEyF-2026 · sin licencia · Cobertura: 2 scripts R + `entrega_05.csv`; README vacío.
- Modelo: LightGBM binario BAJA+1+2, una semilla; BO mlr3mbo 20 evaluaciones, métrica `average_precision`, undersampling 0,1 sin normalizar `min_data_in_leaf`.
- Definiciones en el código **[código]**: `delta2 = lag1 − lag2` (`1-Preprocesamiento.R:94-95`), es decir, la diferencia entre t−1 y t−2; `numero_de_cliente` y `foto_mes` quedan como features; **el corte se elige en 202106 con el modelo final entrenado incluyendo 202106** (in-sample, `...Bayen.R:361-385`). Lags por fila.
- Corte: argmax en validación. Resultados: **[no encontrado]**. Rutas absolutas de la máquina del autor.
- **Aprovechable C02**: ninguno; documenta un caso de corte elegido in-sample que el pipeline de C02 no replica.
- Relevancia para el pipeline de C02: ninguna — lags por fila, IDs y mes como features y corte elegido sobre un mes incluido en el entrenamiento.

### Lote E — enfoques relacionados con el pipeline de C02

1. **Lags SQL por calendario, IPC, PSI con propagación, pesos por recencia y objetivo de BO por ganancia** — problemas de C02: lags por calendario sin densificar el panel, inflación, columnas anómalas de 202006 que entran por un lag, y gap de 2 meses.
   - micaelarr/primeracompetencia (ebe30f0), mismo stack (Python + DuckDB + LightGBM):
     - `LAG()` con chequeo de distancia en periodos == k (celda 18);
     - deflactación por IPC con índice acumulado (celda 7);
     - PSI entre train y el mes a aplicar, con exclusión propagada a lags/deltas (celdas 26–27);
     - pesos por recencia, decay 0,8 (celda 32);
     - objetivo de BO = ganancia suavizada promediada en 3 semillas, en lugar de AUC;
     - ensamble de las top-6 configuraciones;
     - análisis del gap de 2 meses (celda ~49).
   - Tiempo declarado: ~40 min de entrenamiento; con producción solo de scoring, compatible con ≤15 min por mes.
2. **Detección automática de variable×mes en cero con paso a NA antes de los lags** — problemas de C02: 202006 y guardia contra cargas anómalas en `input/<yyyymm>.csv`.
   - lvergini/dmeyf2026-competencia1 (60033c0), `evaluacion_junio/R/fe.R:200` (`fe_anti_imputacion`); valida dejando un mes de hueco (gap de producción); corte con curva suavizada ±500 (`evaluacion_junio/curva_por_corte.R:22`); descarte de semillas con predicciones duplicadas (`02_prediccion_final.R:35`).
3. **Corrección de efectos de calendario** — problema de C02: el train 2019 contiene 201906 y 201912 (aguinaldo).
   - Ani-victoria/dmeyf2026-competencia01 (21e0aaf), 2_modelo celda 27: bandera de aguinaldo y `mpayroll_sin_sac`; celda 31: lag2 solo para las variables que no se distorsionan en el mes a predecir.
4. **Dos modelos combinados por promedio de percentiles y re-evaluación multi-semilla del top-K de la BO** — problema de C02: requisito de ≥2 modelos/estrategias con una recomendación, sin calibrar probabilidades.
   - laupasq1967/Entrega-final-DMEyF (395462d), celda 18; re-evaluación en notebooks z601. Public declarado: 119,38.

Implementaciones de lag por calendario (como referencia de ideas):
- pandas: mmfiora/dmeyf2026-competencia-01 (631d8a3), celda 10 (merge en `periodo0+k`);
- R: nicolasmatayoshi-code/dmeyf2026-competencia1-entrega (37d68bc) `modelo_final.R:139` y patriciojarmoluk/dmeyf2026-competencia01 (4b1e2fa) `competencia01_final.R:292-306` (`match(clave−k, clave)`);
- DuckDB: micaelarr/primeracompetencia (ebe30f0), celda 18;
- target incompleto: la grilla `CROSS JOIN` de lsaldeco/Entrega_Competencia01 (4bfbb08) (`01_target.py:20-45`) deja NULL, no CONTINUA, donde el futuro no se conoce (201911/201912).

Comportamientos observados que el pipeline de C02 no replica:
- corte elegido sobre un mes incluido en el entrenamiento (jlazcanosimoniello/DMEyF-2026, `...Bayen.R:361-385`);
- imputación con el valor del mes siguiente (lsaldeco/Entrega_Competencia01, `02_limpieza_fe.py:37-41`);
- selección de variables en el mismo mes que valida la BO (mbellesi01/dmeyf2026-Competencia-1, celdas 7 y 8);
- entrenamiento con un mes sin etiqueta tratado como negativo (aaav13/Competencia_01_DMEyF, src01 celda 1);
- literal `2021505` en la lista de meses de train, que deja 202105 fuera (ArielRojasV/PrediccionBajas_DMEyF, Modelo_Final celda 22).
