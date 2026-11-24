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

**Cobertura: 46 repos encontrados en GitHub, pendiente de reconciliar con Zulip.**

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

**46 repos y 48 fichas.** El Anexo A tiene 48 fichas: las 46 de los repos de C01 revisados más **dos fichas de una línea** de repos descartados, `wujparker/dmeyf` y `vmalsam/dmeyf2026-predfinal-victor_malsam`. Se conservan porque registran por qué se descartaron. La de `vmalsam` conserva además un dato técnico usado en la comparación con 202006 (12 columnas que ese workflow pone en NA en 202006). Los otros tres descartados (dos vacíos y `MarcosFedericoRios/enlacesDMEyF`, que solo contiene un enlace) no tienen ficha, y nuestro repo tampoco.

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

| Repo (github.com/…) | Commit | Lags | Relevancia C02 | Público declarado (M) |
|---|---|---|---|---|
| aaav13/Competencia_01_DMEyF | f18361a | — | ninguna | — |
| agustinarazanov/dmeyf | 11ff484 | fila | alta | 103,79 |
| agustinlovrich/dmeyf-primera-competencia | 6ef281f | calendario | alta | 107,44 |
| Ani-victoria/dmeyf2026-competencia01 | 21e0aaf | fila | alta | 110,47 |
| ArielRojasV/PrediccionBajas_DMEyF | 9f30b84 | fila | baja | — |
| BustosMaxx/datamining_ecoyfin (MIT) | 04e56b0 | — | baja | — |
| CVFH/DMEYF_CVFH | 0539e93 | fila | media | — |
| emavaldez/primeracompetencia | ec1fa75 | fila | alta | — |
| ezequielabregu/DMEyF_competencia_1 | bc9f2a9 | fila | alta | 110,25 |
| farpp8/dmeyf2026-competencia01 | fd33f7d | calendario ✔ | alta | 102,60 |
| germandasr/DMEyF---1ra-Competencia | f0ff0ad | — | ninguna | — |
| gromadzyn/dmeyfCompetencia1 | ac82cca | calendario | baja | — |
| iespinozahDM/primeracompetencia-dmeyf | 9f73fa5 | fila | baja | 95,78 |
| JaquelineGirabel/dmeyf2026 | be0ed8b | calendario | alta | — |
| JFormoso/competencia1-dmeyf | 90740d0 | calendario | baja | — |
| jlazcanosimoniello/DMEyF-2026 | 4ffdbb8 | fila | ninguna | — |
| keilazavaglia/DMEyF_ksz | 5dbdef6 | fila | media | 104,61 |
| kevinlpagnotta/DMEyF---Primera-Competencia | 391d0f9 | calendario | baja | — |
| kformoso/Competencia1 | 56a820f | calendario | baja | — |
| la-laguinge/dmeyf-2026-competencia-01 | 715cddf | fila; no carga 202107 ✔ | baja | 103,7 |
| laupasq1967/Entrega-final-DMEyF | 395462d | fila | alta | 119,38 |
| lsaldeco/Entrega_Competencia01 | 4bfbb08 | fila | baja | — |
| LuisDanielSuarez/dmeyf-competencia1 | a48ed1e | calendario | media | — |
| lvergini/dmeyf2026-competencia1 | 60033c0 | calendario | alta | — |
| MarcosFedericoRios/primeracompetenciadmeyf | a29db2f | fila | baja | — |
| marcostrigueros99/churn-bancario-dmeyf | cfc465c | fila | baja | 87,07 |
| mariofreites/dmeyf-primera-competencia | d9e572e | fila | alta | 106,21 |
| mbellesi01/dmeyf2026-Competencia-1 | 407407d | fila | baja | — |
| micaelarr/primeracompetencia | ebe30f0 | calendario | alta | — |
| mmfiora/dmeyf2026-competencia-01 | 631d8a3 | calendario | alta | 105,02 |
| montagnaflor/DMEyF-Competencia-01 | c9a71f6 | fila | alta | 101,12 |
| nicobaranek/dmeyf-competencia-01 | 88ed240 | calendario | alta | 106,40 |
| nicolasmatayoshi-code/dmeyf2026-competencia1-entrega | 37d68bc | calendario | media | — |
| nicozare/primera-competencia-dmeyf | 0fc28e8 | fila | media | 93,3–96,6 |
| pablogarciaparisi/dmeyf2026-competencia1 | bd3a731 | calendario | media | — |
| patriciojarmoluk/dmeyf2026-competencia01 | 4b1e2fa | calendario | media | — |
| pfranzd/dmeyf2026-entregas | 8f5e659 | calendario ✔ | alta | 110,17 |
| RodPalDS/DMEF-Primera-Competencia-2026 | 28be952 | fila | alta | 95,59 |
| SerenaDituro/Competencia1_DMEyF_2026 | 31d13c4 | calendario | media | — |
| sgonzalezr96/DMFyE_C1 | 7390f7a | calendario | media | 101,42 o 100,43 (README y JSON no coinciden) |
| SnehitDua/Churn-Prediction-DMEyF | b0f3d74 | calendario | baja | — |
| tahiel53/DMEyF-competencia_1 | f7cd493 | fila | baja | — |
| tomasfarias-hub/DMEYF | c1ef1a9 | — | baja | — |
| tomasroel/DMeyf_Competencias | ab5eb70 | calendario | baja | — |
| veritomonzon/dmeyf2026-personal | 279d520 | fila | media | 93,78 (entrega final); 103,18 (otro envío) |
| vmanuelmarasco/dmeyf_2c_2026 | 5290716 | calendario | alta | — |

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

48 fichas por repositorio (46 de C01 y 2 descartados; ver § 2.1), en lenguaje descriptivo. Marcas: **[declarado]** (README, comentarios u outputs guardados del autor), **[código]** (verificado leyendo el código en el commit indicado), **[no encontrado]**. Las rutas `archivo:línea` son relativas a cada repo en ese commit. La relevancia se refiere al pipeline de C02 (criterio en § 2.4), no a la calidad del trabajo. Revisión de solo lectura: no se ejecutó código externo.

### Lote propio — fichas (sesión principal)

#### emavaldez/primeracompetencia — commit ec1fa75 (2026-10-10)
- URL: https://github.com/emavaldez/primeracompetencia
- Licencia: sin archivo de licencia ⇒ todos los derechos reservados; solo ideas.
- Cobertura: completa (8 archivos; el CSV entregado no se revisó en detalle).
- Modelo y objetivo **[código]** (`codigo/modelos/tips_ale_bolano_fe.py`): LightGBM **multiclase** (CONTINUA/BAJA+1/BAJA+2), score = P(BAJA+1)+P(BAJA+2), BAJA+1 con peso 0,5 (`PESO_BAJA1`), undersampling 0,2 de CONTINUA. Agrega un **especialista** binario para el segmento `internet>=1` (último mes con clase) y una **segunda etapa** de 4 hojas que reordena los puestos 8.000–30.000.
- Features **[código]**: lags/deltas 1–2 **por fila** (`groupby.shift`); ventana de 3 (avg, min, max, ratios contra lag1/avg3/max3); "FE histórico de la cátedra" (tendencia por mínimos cuadrados y promedio de 3, `fe_historico_catedra`). Excluye la historia de las variables del resumen de tarjeta (`historia_de_resumen`) porque dependen del día de cierre.
- Monetarias y drift **[código]**: (1) `ROTAS`: variable con valores anómalos en un mes ⇒ NA en ese mes **antes** de los lags; (2) `PERCENTIL_CERO_FIJO`: 14 montos elegidos por drift de cuartiles (>25 %) y PSI, pasados a percentil con signo dentro del mes (el cero queda en 0); (3) `RESTAR_MODA` para `*_fultimo_cierre`; (4) `internet` se enmascara en 0 en los meses de train salvo el último (cambio de régimen).
- Validación **[declarado + código]**: train 202104–06 para el final; la segunda etapa usa mayo–junio puntuados por un modelo entrenado con marzo–abril. Hiperparámetros fijos (lr 0,027, 31 hojas, 500 rondas). Sin BO en la corrida.
- Corte: cantidad fija, 11.250 **[código]** `reproducir.py:49`. No se documenta cómo se eligió.
- Semillas: 25, promedio de probabilidades.
- Resultados: el README no informa ganancia pública **[no encontrado]**. Huellas sha256 por semilla en `esperado.json` **[declarado: reproducción idéntica en la máquina del autor]**.
- Reproducibilidad: un comando, versiones exactas, sha256 del dataset; resultado sensible al orden de filas/columnas **[declarado]**.
- Tiempos **[declarado]**: ~20 min las 25 semillas en Mac M5 Max de 18 núcleos (75 s la primera, ~40 s cada una).
- Aprovechable para C02: tabla de variables con valores anómalos por mes aplicada antes de los lags; percentil con signo dentro del mes para montos con drift; restar la moda a fechas de cierre; multiclase con BAJA+1 a medio peso; canaritos para selección.
- Relevancia para el pipeline de C02: alta — tratamiento de columnas anómalas por mes antes de los lags (caso 202006) y normalización de montos por mes frente a la inflación 2019–2021.

#### sgonzalezr96/DMFyE_C1 — commit 7390f7a (2026-10-11)
- URL: https://github.com/sgonzalezr96/DMFyE_C1
- Licencia: sin archivo ⇒ todos los derechos reservados; solo ideas.
- Cobertura: README, `registro/*.json`; las notebooks no se leyeron celda por celda.
- Modelo y objetivo **[declarado + `registro/configuracion_corrida.json`]**: LightGBM binario, positivo solo BAJA+2 (BAJA+1 = 0).
- Features **[declarado]**: lags 1 y 2 **por calendario** y deltas; **normalización por máximo absoluto dentro del mes** (`*_norm_mes`); tendencia y promedio con ≥ 2 valores; `ccajas_depositos` de mayo a NA; excluye préstamos personales; selección por canaritos (400 variables).
- Validación: Optuna con train 202103–04, valid 202106, AUC, **5 trials** **[declarado: con 5 trials el TPE no sale de la fase aleatoria]**. Final con 202103–06.
- Corte: 12.500 (ganancia 1.072.500 / costo 27.500 en la config). Se eligió mirando la validación de junio **y el público de agosto** **[declarado]**.
- Semillas: 10, promedio de probabilidades, desempate por ID.
- Resultados **[declarado]**, con dos fuentes que no coinciden: el README dice envío `sofia13`, 101,42; `registro/envio_final.json` dice `sofia9`, 100,43, con el mismo CSV de 12.500. El README también llama "candidato final" al `_top13000`.
- Reproducibilidad: versiones registradas; el README declara que no se re-ejecutó.
- Aprovechable para C02: normalización por máximo absoluto dentro del mes como alternativa de menor costo al percentil; lags de calendario; selección con canaritos.
- Relevancia para el pipeline de C02: media — lags por calendario y normalización de montos por mes; la implementación no se verificó en código (solo **[declarado]**).

#### BustosMaxx/datamining_ecoyfin — commit 04e56b0 (2026-10-11)
- URL: https://github.com/BustosMaxx/datamining_ecoyfin
- Licencia: **MIT** (aviso de copyright 2026 del autor) ⇒ se puede reusar código conservando el aviso. Entre los 46 repos relevados, es el único con archivo de licencia.
- Cobertura: script R y README; el notebook (1 MB) no se bajó, igual que salidas pesadas (`.pbix`, CSV de 23 MB).
- Modelo **[código]** `src/optimizacion_hiperparamentros.R`: LightGBM con BO (mlrMBO) maximizando **AUC** en CV; `PARAM$hyperparametertuning$iteraciones <- 1` (una sola iteración); train 202103–04; final 202103–06; `ccajas_depositos` de 202105 a NA; cortes evaluados de 4.000 a 19.000 cada 500.
- Resultados: no se informan **[no encontrado]**.
- Relevancia para el pipeline de C02: baja — coincide con la plantilla de la cátedra; no agrega tratamientos de lags, columnas por mes ni corte distintos de los ya relevados.

### Lote A — fichas

Base de rutas: `repos_externos/<owner>_<repo>/`. Ningún repo del lote tiene archivo LICENSE ⇒ **todos sin licencia: todos los derechos reservados; no copiar código, solo ideas**.
Ganancia por envío (verificada en cada repo): 4 de 5 usan **+1.072.500 / −27.500**; farpp8 usa **+1.100.000 / −27.500**. Ninguno usa 780.000/20.000.

---

#### RodPalDS/DMEF-Primera-Competencia-2026 — commit 28be952 (2026-10-11)
- URL: https://github.com/RodPalDS/DMEF-Primera-Competencia-2026
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: 22 scripts .py, configs JSON, informe_tecnico.md y README leídos (los principales en detalle). Omitidos por tamaño 20 CSV de `exp/` (mitades de junio, probabilidades por semilla/mitad B); no afectan la lectura del método.
- Modelo y objetivo: LightGBM binario. Entrena con `clase_binaria2` (BAJA+1 ∪ BAJA+2), y la ganancia siempre se mide con BAJA+2 **[declarado + código]** (README §2). Sin undersampling en el final.
- Features: 152 crudas + lag1/lag2/delta1/delta2 de todas; **después todas se reemplazan por rank con cero fijo dentro del mes** (positivos (0,1], negativos [−1,0), 0=0, NA=NA) **[código]** `03c_fe_extra.py:119-131`. Lags: por fila **validados por calendario**: el lag k es NA si la fila k posiciones arriba no es el mismo cliente exactamente k meses antes **[código]** `03c_fe_extra.py:104-117`. Con un hueco se pierde el lag aunque el mes t−k exista (esquema híbrido). Hay 6 variables del "proceso de muerte": `n_apagados` (cuántos de 16 productos clave están en 0/NA) y sus deltas, `n_dejo_de_usar`, `ctrx_quarter_rel_max3`, `mcaja_ahorro_rel_max3` **[código]** `03c_fe_extra.py:146-167`.
- Monetarias/drift: el rank por mes "corrige inflación y aguinaldo" **[declarado]**. Diagnóstico de lift de BAJA+2 según el valor sea NA/cero/negativo/positivo **[código]** `02b_diagnostico_ceros_na.py`. Identificó `Master/Visa_Finiciomora` y `*_fultimo_cierre` con "ceros inyectados" en 202105/06/08. Sacarlas dio 94,35 en el público, menor que la versión que las conserva, así que no se sacaron **[declarado]** README §7 (5023). Probó `ccajas_depositos`=NA en 202105, sin mejora **[declarado]**.
- Validación: fuera de tiempo, entrena 202103+202104 y mide en 202106 (mantiene el gap de 2 meses). **Junio partido en mitades fijas estratificadas**: la BO elige con la mitad A y confirma con la B **[código]** `08_bo_fuera_de_tiempo.py:134-150`. La métrica es la "meseta": ganancia promedio entre 12.000 y 17.000 envíos. Optuna sobre lr, num_leaves, min_data_in_leaf, feature_fraction, bagging_fraction y lambdas. Reglas R1–R9 fijadas de antemano, con bootstrap pareado o Wilcoxon **[declarado]**.
- Corte: fijo en 12.500, un punto medio entre el público (~12.000) y la meseta de junio (12.500–15.000) **[declarado]** README §5.
- Semillas/ensamble: 50 semillas con promedio de probabilidades **[declarado]**. El ensamble de 12 hiperparámetros por AUC (estrategia 1.7) perdió 52 M en junio y no se adoptó **[declarado]**.
- Resultados: público 95,59 con 12.500 y 96,11 con 12.000 **[declarado]**. Los CSV de probabilidades no se bajaron, así que no se pudo corroborar.
- Reproducibilidad: un config JSON por experimento y un `exp_utils.py` que registra PARAM y resultados en `exp/<id>/`. Usa `DMEYF_ROOT` con fallback a una ruta absoluta de la máquina del autor (Windows) **[código]** `exp_utils.py:33`. requirements con versiones pero marcado "reemplazar" **[declarado]**. Lotes .bat reanudables.
- Tiempos: FE ds3003 en ~1–2 min y ~5 GB **[declarado]** `03c_fe_extra.py:25-27`. Final + entrega entre 1 y 2 h (50 semillas) **[declarado]**.
- Otros detalles: `min_data_in_leaf` se escala por la cantidad de filas (×4 en el final) **[código]** `07_modelo_final.py:186-190`. Según el README, el modelo resultante tiene árboles de ~5 hojas **[declarado]**. El README recomienda para C02 validar con más meses antes de fijar la regularización (README §9).
- **Aprovechable para C02:**
  1. Variables de "proceso de muerte" (`n_apagados`, `n_dejo_de_usar`, `rel_max3`), de bajo costo y calculables por mes en producción: `03c_fe_extra.py:146-167`.
  2. Rank con cero fijo por mes frente a inflación y drift (aplicable a 2019→2021 y a 202006): `03c_fe_extra.py:119-131`.
  3. Mitades A/B fijas del mes de validación y métrica de meseta en vez del máximo: `08_bo_fuera_de_tiempo.py:134-150`.
- Relevancia para el pipeline de C02: alta — protocolo de validación con mitades A/B y variables de abandono calculables por mes; los lags son por fila con validación de calendario (no calendario puro) y el corte es un valor intermedio fijado manualmente.

#### farpp8/dmeyf2026-competencia01 — commit fd33f7d (2026-10-12)
- URL: https://github.com/farpp8/dmeyf2026-competencia01
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: todo leído (no hay archivos omitidos). Sin datos ni outputs de corridas; hay huellas SHA y `origen/esperado/*.json` con resultados.
- Modelo y objetivo: LightGBM binario. Clase K2 (BAJA+1 ∪ BAJA+2 contra CONTINUA) y ganancia solo con BAJA+2 **[código]** `06_receta_denicolay.py:41,66`. Comparó K1 (BAJA+2 contra el resto), K2 y K3 (sin las filas BAJA+1): K2 tuvo mayor ganancia en validación local (+28,5 M) y K1 en el público **[declarado]** `DECISIONES.md:74-82`.
- Features: lag1/delta1/lag2/delta2 de todos los predictores (735 columnas). **Lags por calendario exacto** (merge sobre cliente y periodo+k): un mes faltante da NA y el lag2 existe aunque falte t−1 **[código]** `02_variables.py:84-103`. Además rank pct por mes (opcional) y sumas Visa+Master (no adoptadas). Descarta columnas constantes en train **[código]** `06_receta_denicolay.py:63`.
- Monetarias/drift: "reparaciones" con trazabilidad celda por celda **[código]** `01_preparar_datos.py:104-113, 148-204`: une ccajas_depositos+ccajas_otras (reclasificadas entre abril y junio), saca duplicadas (`*_mconsumototal`), pone NA en `mfinanciacion_limite` >10× el límite (diferencia de escala), NA en centinelas de `Fvencimiento` < −1e6, y saca préstamos personales porque cambia su relación con la baja en junio. También identificó una "cohorte de préstamo congelado" que explica 21–23 % de la ganancia de junio **[declarado]** `DECISIONES.md:148-150`. Sin IPC.
- Validación: cortes F1 (03→05), F2 (03-04→06), F3/F4/F5 **[declarado + código]** `origen/regla_n.py:11-17`. Métrica A = media de G(k) para k entre 8.000 y 15.000 (promedio de la curva, no el máximo). Optuna TPE con 40 trials sobre num_leaves, min_sum_hessian y rondas **[declarado]** `DECISIONES.md:86-92`. Regla de reemplazo fijada antes de mirar resultados: +10 M, mejora en F1 y F2 y ≥16/20 semillas a favor **[declarado]** `DECISIONES.md:36-41`.
- Corte: **minimax-regret** sobre 7 escenarios (4 cortes temporales, junio sin la cohorte anómala, TP×0,92 y TP×0,85), en una grilla de 9.000 a 12.000 ⇒ N=11.000 **[código + declarado]** `origen/regla_n.py:18-31`.
- Semillas/ensamble: 20 semillas (5 bases y los 3 primos siguientes de cada una) con promedio de probabilidades. El ensamble K1+K2 por probabilidad o por rango no pasó la regla **[declarado]**.
- Resultados: público 102,60 (N=11.000) y 103,18 (N=11.500) **[declarado]**. Ganancias G por corte en `origen/esperado/regla_n_d10.json` (F2: 475,2 M en 11.000) **[declarado, output guardado]**.
- Reproducibilidad: `reproducir.py` compara SHA en cada etapa, hay tests (`test_02_variables.py`: "historia por mes exacto"), requirements pineados (Python 3.13, LightGBM 4.6.0), `deterministic=True`, la ruta del crudo por variable de entorno y empates resueltos con argsort estable.
- Tiempos: 43 min el total con 20 modelos sobre 4 meses, en un Ryzen de 8 núcleos con ~12 GB; la base sola tarda ~4 min **[declarado]** README:38-41.
- **Aprovechable para C02:**
  1. Función de lag por calendario exacto con merge sobre (cliente, periodo+k), que corresponde a la variante que C02 evalúa. Ver `02_variables.py:60-61,84-103` y su test.
  2. Elegir N por minimax-regret sobre varios meses y escenarios estresados (cohorte quitada, TP degradado), compatible con la producción mensual y el reporte acumulativo: `origen/regla_n.py:18-31`.
  3. Reparaciones con log de celdas modificadas y `exigir()` (asserts que no se desactivan) sobre conteos por mes, aplicables a la detección de columnas en cero como en 202006: `01_preparar_datos.py:57-60,159-204`.
- Relevancia para el pipeline de C02: alta — lags por calendario con test, regla de corte sobre varios meses y escenarios, y controles por mes aplicables a 202006.

#### LuisDanielSuarez/dmeyf-competencia1 — commit a48ed1e (2026-10-12)
- URL: https://github.com/LuisDanielSuarez/dmeyf-competencia1
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: todo leído (no hay omitidos). No hay logs ni outputs de corridas; solo JSON de config e hiperparámetros.
- Modelo y objetivo: LightGBM binario con BAJA+1 ∪ BAJA+2 = 1 **[código]** `L20/codigo/01_preprocesamiento_L20.py:125-128`. Hiperparámetros fijos: lr 0,005, ff 0,5, bynode 0,2, min_data 0, max_bin 31. Mejores hiperparámetros: 1.856 iteraciones, 556 hojas, hessian 0,037 **[declarado, output guardado]** `L22/config.json`.
- Features: para cada columna (salvo 10 "sin historia": edad, antigüedad y fechas) lag1, lag2, delta1, delta2, `tend3` (pendiente MCO) y `avg3`. **Todo por unión con (cliente, mes−k), no por shift de filas** **[código]** `L20/codigo/preproc_comun.py:45-62`. La tendencia usa la posición real del mes y exige ≥2 puntos **[código]** `preproc_comun.py:65-83`. Después aplica rank con cero fijo a los 7 grupos (reemplaza al crudo) y agrega flags `_zero` sin rankear **[código]** `preproc_comun.py:29-42,86-88`.
- Monetarias/drift: `ccajas_depositos`=NA en 202105, con un assert previo de que el mes es todo cero **[código]** `01_preprocesamiento_L20.py:115-123`. Excluye los préstamos personales de la BO pero los incluye en el final **[declarado]**, config.
- Validación: BO entrenando 202103-04 y midiendo **AUC** en 202106. Son 10 trials aleatorios (n_startup 12 > n_trials 10, así que el TPE nunca guía la búsqueda) sobre num_iterations, num_leaves y hessian **[código]** `L20/config_e1.json`. AUC 0,9204 **[declarado, output guardado]** `L22/hiperparametros_origen.json`.
- Experimento de **"clase artificial"** (pseudo-etiquetas): marca como BAJA el top 1,251 % por probabilidad de cada mes sin etiqueta usable y reentrena con esas etiquetas **[código]** `L20/codigo/02_etapa1_L20.py:1-14,36-45`, `03_etapa2_L20.py:1-14`. El README dice que **no se usó en L22**.
- Corte: genera submits de 9.000 a 13.000 de a 500. El elegido no está documentado (el ejemplo usa 10.500) **[no encontrado]**.
- Semillas/ensamble: 45 modelos de una semilla cada uno (33 en L22 y 12 en L22b) con promedio de probabilidades **[declarado]**. Es reanudable por semilla.
- Resultados: **[no encontrado]**, no declara ganancia pública ni privada.
- Reproducibilidad: asume `~/dmeyf/` y un bucket GCS fijo en el código (con flag `--sin_bucket`); cada script guarda copia de sí mismo; LightGBM 4.7.0 y pandas 2.3.3 en config; sin requirements. `comun_L22.py` aparece duplicado en 3 lugares con pequeñas diferencias.
- Tiempos: **[no encontrado]**. Corrió en una VM de 8 núcleos y 60 GB.
- **Aprovechable para C02:**
  1. Lag, tendencia y promedio por calendario con `searchsorted` sobre la clave cliente*100+periodo, alternativa vectorizada al merge: `preproc_comun.py:45-83`.
  2. Pseudo-etiquetas para meses con target incompleto. En C02 aplicaría a 201911 (sin BAJA+2) y 201912; requiere validación offline antes de usarlo: `02_etapa1_L20.py:36-45`.
  3. Flags `_zero` y NA forzado con assert "mes todo cero ⇒ NA", aplicable a 202006: `01_preprocesamiento_L20.py:115-123`.
- Relevancia para el pipeline de C02: media — FE por calendario vectorizado y pseudo-etiquetas para meses sin etiqueta; sin resultados reportados, corte no documentado y BO por AUC con 10 trials aleatorios.

#### mariofreites/dmeyf-primera-competencia — commit d9e572e (2026-10-11)
- URL: https://github.com/mariofreites/dmeyf-primera-competencia
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: 2 notebooks leídos como JSON (**sin outputs**: 0 en ambos), design.md, README y `resultados/` con logs, CSV y JSON de las corridas originales. No hay omitidos.
- Modelo y objetivo: **zLightGBM** (fork de la cátedra con parámetro `canaritos`, que nunca corta por canaritos), con canaritos 1 a 1 **[código]** (celda de verificación "Este lightgbm no parece ser zlightgbm"). Binario con BAJA+1 ∪ BAJA+2 para la BO por AUC. Además AP y ganancia con BAJA+2 **[declarado]** `c9923 design.md`.
- Features: c9920 parte de 760 variables (originales y lag1/2, delta1/2 con rank cero fijo) y selecciona por **canaritos asesinos** (corte media+2σ, la variable debe sobrevivir 2 de 3 repeticiones, entrenado en mayo) ⇒ 128 variables **[declarado]**. c9923 suma 11 atributos nuevos (patrimonio neto, `cproductos_perdidos`, `tperdio_payroll`, `tinicio_comision`, ratio digital, saldo/límite TC) con lags, más `avg3` y `slope3` ⇒ 299 **[declarado + código]**. Lags **por fila** (k-ésima observación previa del cliente) **[código]** (celda de `previous[k]`). La pendiente usa el mes real como x **[código]** (`fill_columns`/`window_stats`).
- Monetarias/drift: rank con cero fijo por mes **[declarado]**. Sin tratamiento de columnas anómalas por mes **[no encontrado]**.
- Validación: BO Optuna TPE multivariado de 25 corridas (1 semilla previa, 10 al azar y 14 guiadas) sobre num_iterations, num_leaves y hessian. Entrena 03-05 y **maximiza AUC de junio** **[declarado]**. Mejor: AUC 0,9245 con ganancia máxima suavizada de 402 M en 12.478 envíos, ~3,2 min por trial **[declarado, output guardado]** `resultados/c9923/mejores_hiperparametros.json`.
- Corte: curva de ganancia **suavizada con media móvil centrada de 501 posiciones** **[código]** (`gain_curve`). La meseta de junio está entre 11.000 y 13.500. Eligió 11.000 por ser el inicio de la meseta y el de mayor ganancia de 4 envíos al público **[declarado]**.
- Semillas/ensamble: 60 semillas con promedio de probabilidades. Rehace los cortes tras cada semilla y se puede parar con un archivo `PARAR` **[declarado]**.
- Resultados: público **106,205** con 11.000 envíos (10.500: 105,4; 11.500: 103,6; 12.000: 103,4) **[declarado]**. Ganancia de junio por corte en `resultados/c9923/ganancia_junio_por_corte.csv` (c9923 vs c9920: +23 M en 11.000) **[declarado, output guardado]**.
- Reproducibilidad: orientada a GCP. Descarga el dataset y compila zLightGBM automáticamente, es reanudable desde el bucket, guarda huellas del orden de clientes y tiene `MODO_PRUEBA` con 5 % de clientes. Depende de rutas de la VM de la cátedra (`~/buckets/b1`). Optuna 5.0.0.
- Tiempos: ~9,5 h en total (c9920 ~3 h con 8 hilos; c9923 ~6,5 h con 12 vCPU y 96 GB) **[declarado]**.
- **Aprovechable para C02:**
  1. Atributos de abandono de producto (`cproductos_perdidos`, `tperdio_payroll`, `tinicio_comision`, `mpatrimonio_neto`) con definición explícita de NA sin historia: `02_c9923_variables_nuevas/design.md` (tabla de variables).
  2. Curva de ganancia suavizada (rolling centrado) para elegir el corte y medir trials: notebook c9923, función `gain_curve`.
  3. Selección por canaritos de 760 a 128 columnas, que reduce el tiempo de inferencia frente al límite de ≤15 min en laptop: `01_c9920_canaritos_asesinos/design.md`.
- Relevancia para el pipeline de C02: alta — features de abandono, selección de variables que reduce el tiempo de inferencia y corte por curva suavizada; los lags son por fila y depende de zLightGBM.

#### nicozare/primera-competencia-dmeyf — commit 0fc28e8 (2026-10-10)
- URL: https://github.com/nicozare/primera-competencia-dmeyf
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: todo el código leído. Omitidos los 15 modelos `modelos/lgb_seed_*_k*.txt` (~3,3 MB c/u). Están `features.txt`, los hiperparámetros, `corte_optimo.txt`, la base de Optuna en SQLite (no abierta) y `prediccion_final.csv`.
- Modelo y objetivo: LightGBM binario con BAJA+1 ∪ BAJA+2 en el entrenamiento **[código]** `scripts/02_entrenar_ensamble.py:224`. La BO usa otro target: positivo = solo BAJA+2 **[código]** `optimizacion_hiperparametros/buscar_hiperparametros.py:363`. Hace undersampling de CONTINUA al 50 % y escala `min_data_in_leaf` en consecuencia **[código]** `02_entrenar_ensamble.py:180-193`. Pasa `bagging_fraction` sin `bagging_freq`; con esa configuración LightGBM no aplica bagging **[código]** `02_entrenar_ensamble.py:180-186`.
- Features: lag1/lag2/delta1/delta2 de todas las numéricas, **por fila** (`lag() over partition by cliente order by foto_mes`) **[código]** `01_feature_engineering.py:100-115`. La clase ternaria sale de la grilla completa cliente×mes (calendario) **[código]** `01_feature_engineering.py:51-64`. Flag `cobra_aguinaldo`: en junio/diciembre, saldo ≥1,4× la media o el máximo previo del cliente; en ese caso el saldo se divide por 1,111 **[código]** `01_feature_engineering.py:66-93`.
- Monetarias/drift: **PSI** para excluir 4 columnas (`*_fultimo_cierre` pasa a ~77 % de ceros en un mes; `*_Finiciomora` tiene >98 % de NA) **[declarado]** README. En el código solo está la lista fija **[código]** `scripts/config.py`. El cálculo de PSI **[no encontrado]**. No hay deflactación.
- Validación: los meses se detectan automáticamente (train = todos menos los 2 últimos; holdout = el último con clase; predicción = el último) **[código]** `scripts/comun.py:7-25`. La BO usa `StratifiedShuffleSplit` 5×30 % (**no temporal**) con feval de ganancia sobre el umbral de equilibrio 27.500/(27.500+1.072.500): Optuna con 30 trials sobre 5 hiperparámetros **[código]** `buscar_hiperparametros.py:372-402`.
- Corte: barrido de 8.000 a 15.000 de a 250 sobre el holdout, promedio entre 5 semillas ⇒ 11.500 (curva plana entre 10.750 y 12.000) **[código + declarado]** `02_entrenar_ensamble.py:206-219`.
- Semillas/ensamble: 5 semillas × 3 submodelos (cada uno con su undersampling) con promedio de probabilidades **[código]**.
- Resultados: holdout 392 M en 11.500 **[declarado]**. Público entre 93,3 y 96,6 según la variante; no queda claro qué número corresponde al archivo entregado **[declarado]**. Hay un SHA-256 del CSV final para verificar.
- Reproducibilidad: `uv`/pyproject (sin lock versionado), rutas relativas, modelos versionados y SHA del entregable.
- Tiempos: **[no encontrado]**.
- **Aprovechable para C02:**
  1. `detectar_meses()` deduce train, holdout y predicción del dataset, sin meses fijos en el código; aplicable a la producción mensual con `input/<yyyymm>.csv`: `scripts/comun.py:7-25`.
  2. Flag de aguinaldo relativo a la historia propia del cliente (junio y diciembre; en C02 aparecen 201906/201912): `01_feature_engineering.py:66-93`.
  3. Separar entrenamiento (guarda modelos, `features.txt` y corte) de scoring (solo carga), patrón compatible con el límite de 15 min: `03_generar_submission.py`.
- Relevancia para el pipeline de C02: media — separación entrenamiento/scoring y detección automática de meses; lags por fila, BO no temporal, bagging sin efecto y targets distintos entre BO y entrenamiento.

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

### Lote B — fichas

Convención: **[declarado]** = README/comentarios/outputs guardados · **[código]** = verificado leyendo código · **[no encontrado]**.
Ganancia C01 en los 4 repos: **+1.072.500 por BAJA+2 / −27.500 por envío errado** (no 780.000/20.000) **[código]**; umbral de equilibrio 0,025. Entrega por bot de Zulip (no Kaggle), 8.000–15.000 ids **[declarado]**.
Ninguno de los 4 repos tiene archivo LICENSE ⇒ **todos los derechos reservados: no copiar código, solo ideas.**

---

#### agustinarazanov/dmeyf — commit 11ff484 (2026-10-10)
- URL: https://github.com/agustinarazanov/dmeyf (repo de un integrante del equipo: la reutilización de código requiere su autorización)
- Licencia: sin licencia (ver arriba); al ser del equipo, la reutilización se coordina con el autor.
- Cobertura: los 1087 archivos son casi todos `experimentos/*/` (CSV de envíos, logs). Lo relevante: `README.md`, `reproducir.py`, `src/` (competencia.py, fe_panel.py), `scripts/c1xx–c2xx`, `docs/` (diario de 2.000+ líneas, backlog, diagnóstico FE), `ledger/*.csv`. Los modelos y parquets están en .gitignore. No se leyó el diario completo.
- Modelo y objetivo: LightGBM binario; positivo = BAJA+1 ∪ BAJA+2 con **peso 0,25 para BAJA+1** (`target='pesos'`, `src/competencia.py:65-88`) **[código]**. Según lo declarado, BAJA+2 solo perdió 5,3 pts públicos y los pesos 0,5/1 también perdieron (`README.md:20`) **[declarado]**. Hiperparámetros: la "receta" del profesor (lr 0,005, 83 hojas, max_bin 31, ff 0,5, ff_bynode 0,2, min_data_in_leaf 0, hessiano escalado por filas, 2.000 rondas) **[declarado]**.
- Features: 150 crudas + lag1, delta1, lag2, delta2 de todas (750 col). **Lags por fila**: `lag(x,k) over (partition by cliente order by foto_mes)` (`scripts/c200_lags_todo.py:46-51`, `src/fe_panel.py:216-228`) **[código]**. Los clientes con meses salteados no se tratan aparte **[código]**. Se probaron proporciones, sumas, conteos, rachas y tendencias: todas quedaron dentro del ruido (`README.md:90-99`) **[declarado]**.
- Monetarias/drift: deflactar todos los montos (c127) da menor ganancia y se descarta **[declarado]**. Deflactar solo las comisiones por la mediana mensual entre los que pagan da +0,7, dentro de la franja de ruido (`scripts/c250_comision_deflactada.py:1-12`) **[código + declarado]**. Probó lags sobre percent_rank por mes (`scripts/c202_lags_rank.py:1-10`), con resultado neutro. **Detección de columnas anómalas por mes**: `ccajas_depositos` → NULL en 202105 *antes* de calcular los lags (c200:56-60). También anotó que en 202106 está "casi muerta" e infla el delta2 (c200:1-4). `Visa/Master_Finiciomora` quedan fuera del modelo por "ceros inyectados" en 202105/202108 (`src/competencia.py:44`). `cliente_vip` y `Visa_delinquency` se corrigen por artefactos de calendario (`scripts/c254_calendario.py:15-21, 43-44`) **[código]**.
- Validación: folds temporales A `[03]→05`, B `[03,04]→06`, C `[03,04,05]→07` (C a horizonte 1). El README describe dos esquemas que filtran información: el CV dentro del mes, porque el BAJA+2 de t reaparece como BAJA+1 en t+1, y la cadena a horizonte 1 (`README.md:115-119`) **[declarado]**. Hubo BO por AUC (c220/c222), con menor ganancia que los hiperparámetros fijos **[declarado]**. La métrica final es la ganancia pública promediada sobre 20 archivos.
- Corte: **minimax regret entre meses de validación** con distinta prevalencia (`regret`/`corte_minimax`, `src/competencia.py:232-254`). También usa la meseta de la curva media entre semillas (`meseta`, :116-127) y simula la partición público/privado (:130-147) **[código]**. Entrega 14.000 **[declarado]**.
- Semillas/ensamble: 20 semillas, **promedio de rangos percentiles** (`src/competencia.py:226-229`) **[código]**. Un `lgb.Dataset` nuevo por semilla, con deterministic=True y force_col_wise (`README.md:39-43`; `reproducir.py:80`) **[código]**. Mezcla con un modelo de horizonte 1 (BAJA+1, entrenado hasta 07) por rango, peso 0,15–0,5: +0,2, indistinguible del ruido (`scripts/c271_mezcla_h1.py`; `docs/backlog_ideas.md:98`) **[declarado]**.
- Resultados: entrega 103,79 público; media de 20 archivos 103,85; desvío entre semillas 1,8–2,5 por archivo (`README.md:24, 60-62`) **[declarado]**. Hay SHA-256 reproducido bit a bit **[declarado]**. Los outputs no se corroboraron.
- Reproducibilidad: `reproducir.py` va de punta a punta, con versiones fijadas en el README (Py 3.14, duckdb 1.5.5, lgbm 4.7.0), semillas fijas, un ledger Postgres exportado a CSV y caché de modelos por hash de configuración (`src/competencia.py:150-157`). Depende de un symlink `data/` y de Postgres para el ledger.
- Tiempos: ~4 h para 20 semillas × 2.000 rondas en 8 cores (`README.md:32`) **[declarado]**. La inferencia no está medida aparte.
- **Aprovechable para C02**:
  1. Anular las columnas anómalas de un mes (NULL) **antes** de calcular lags y deltas (`c200_lags_todo.py:56-60`). Corresponde al caso de 202006 en C02: sin esto, delta1/delta2 de 202007/202008 heredan el cero.
  2. Cortar por minimax regret sobre varios meses de validación con distinta prevalencia (`src/competencia.py:232-254`). En C02 la prevalencia del mes de producción es desconocida; esta regla no depende del pico de un solo mes.
  3. Ensamble por rango + un Dataset por semilla + caché por hash de configuración (`src/competencia.py:150-229`). Un miembro de horizonte 1 (BAJA+1, que con datos hasta 201912 permite usar 201911) sirve como "segunda estrategia" de bajo costo. En C01 no sumó ganancia, y hasta peso 0,5 tampoco la redujo.
- Relevancia para el pipeline de C02: alta — anulación de columnas anómalas antes de los lags (202006), corte por minimax regret con prevalencia desconocida y documentación de esquemas de validación que filtran información entre BAJA+2 y BAJA+1.

#### JaquelineGirabel/dmeyf2026 — commit be0ed8b (2026-10-12)
- URL: https://github.com/JaquelineGirabel/dmeyf2026
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: se leyó `competencia_uno/comp/*.py`, `main.py`, `generate_features_extendido.py` (7.464 líneas, casi todas una referencia de orden embebida) y el notebook 007 (con outputs). **Faltan 57 archivos >1 MB**: los notebooks 001/006/008–012 (incluido el 010, que es el de la entrega), modelos .txt y predicciones .npy. No hay `resultados/` ni `submits/` en el clon.
- Modelo y objetivo: LightGBM binario. Config final: positivo = BAJA+1 ∪ BAJA+2 ("modelo B"), **undersampling 10% de la clase 0** con corrección de probabilidad `p·r/(p·r+1−p)` (`comp/undersampling.py:28-33`). El umbral de decisión se ajusta a `0,025/s`, con s = BAJA+2/positivos (`comp/particiones.py:30-37`); `main.py` CONFIG:28-55 **[código]**.
- Features: dataset "extendido" = 40 variables propias (flags de mora, pérdida de sueldo, rachas, ctrx_quarter_slope_3 con `regr_slope` en DuckDB contra `cliente_antiguedad`) + rank + lags/deltas 1 y 2 de las 152 originales. **Lags por calendario**: `posiciones_previas` hace merge con la clave (cliente, foto_mes−k) y deja vacío si el cliente no estaba ese mes (`generate_features_extendido.py:638-644, 692-699`) **[código]**. Las variables propias exigen mes previo consecutivo y marcan `flag_gap_mes` (:308-318) **[código]**. Sin lag3 porque quedaría vacío en el train (:27-28).
- Monetarias/drift: `<var>_rank` = percentil dentro del mes **con cero fijo** (positivos en (0,1], negativos en [−1,0), 0 → 0, NaN → NaN), agregado como columna extra (:620-631, 686-688) **[código]**. No hay detección de columnas en cero **[no encontrado]**.
- Validación: Optuna con **ganancia** (umbral, umbral ajustado o "franja" = promedio top 5–9%) sobre 5 particiones 70/30 dentro de los meses de train (`comp/optimizacion_optuna.py`, `comp/metricas.py:22-31`). Las particiones dentro de los mismos meses corresponden al esquema que agustinarazanov/dmeyf (`README.md:115-119`) describe como filtración entre BAJA+1/BAJA+2 de un mismo cliente. Para test temporal usa 202106 con train 03–05 y emite un **aviso de la regla M−2** (`comp/particiones.py:1-9`; output del notebook 007) **[código + declarado]**. El espacio `it01_bordes` busca 7 hiperparámetros (hojas 4–64, lr 0,003–0,1, min_data 200–8000, ff, bagging, l1, l2) con early stopping hasta 3.000; N_TRIALS=60 (`config.py:76`) **[código]**. El notebook 007 muestra 23 trials **[declarado]**.
- Corte: fijo en 12.058 envíos (= los que superan el umbral ajustado en test; p mínima 0,0321) (`registro.md`) **[declarado]**. El modelo se elige por "semillas": la caja de ganancias por semilla con mayor Q1 **[código]**.
- Semillas/ensamble: 20 semillas, **promedio de probabilidades** corregidas; cada semilla usa su propia muestra de undersampling (`comp/ensamble.py:12-33`) **[código]**.
- Resultados: en el notebook 007, ganancia en test 202106 = 357,97 M (trial 21) **[declarado, output guardado]**. Ganancia pública **[no encontrado]**.
- Reproducibilidad: paquete `comp/`, CLI `main.py` con caché en db/modelos/resultados, comparación con el submit y `requirements.txt` con versiones mínimas (no fijadas). Los outputs guardados contienen rutas absolutas de la máquina del autor. El repo incluye .pyc y .db de Optuna.
- Tiempos: **[no encontrado]**. El generador declara un pico de ~6 GB de RAM (:14).
- **Aprovechable para C02**:
  1. **Lags por calendario vía self-join (cliente, mes−k)** (`generate_features_extendido.py:638-699`), con huecos → NaN y `flag_gap_mes` (:308-318); corresponde a la variante que C02 evalúa.
  2. Rank por mes con cero fijo frente a la inflación (:624-631), aplicable fila a fila en producción si se guardan los cortes del mes de referencia (o recalculado sobre el input mensual).
  3. Undersampling con corrección de probabilidad + umbral ajustado por s (`undersampling.py:28-33`, `particiones.py:30-37`): reduce el tiempo de entrenamiento y mantiene calibrada la columna `probabilidad` del output.
- Relevancia para el pipeline de C02: alta — lags por calendario con indicador de hueco y corrección de probabilidad por undersampling; la BO usa particiones dentro de los mismos meses de train.

#### CVFH/DMEYF_CVFH — commit 0539e93 (2026-10-11)
- URL: https://github.com/CVFH/DMEYF_CVFH
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: se leyó `competencia_01/README.md`, `segundo_paso_entrenamiento_competencia_01.py` (682 líneas), el notebook de FE (14 celdas, 5 outputs) y `bitacora/*.csv`. **Faltan 13 archivos >1 MB**: modelos RF/LGBM, notebooks de clase y `scripts_competencia/workflow_competencia_1_entrenamiento.ipynb` (la búsqueda de hiperparámetros). El README menciona `modelo_final.py`, pero el archivo se llama `segundo_paso_...py`.
- Modelo y objetivo: LightGBM binario con positivo BAJA+1 ∪ BAJA+2 (`clase_binaria12`) y ganancia evaluada solo con BAJA+2 (script:48-49) **[código]**. Son **tres modelos por conjunto de variables y ventana**: `current` (solo variables del mes, train 03–05 / final 03–06), `hist1` (**solo** lag1+delta1, 04–05 / 04–06) y `hist2` (**solo** lag2+delta2, 05 / 05–06) (script:83-111, 135-146, 378-396) **[código]**. Los tres comparten hiperparámetros (hojas 18, lr 0,00625, min_data 1748, 4.928 iteraciones) **[declarado]**.
- Features: FE en SQL (agregados de tarjetas, patrimonio, deuda, ratios) + lag1/lag2/delta1/delta2 de todas las numéricas. **Lags por fila** (`LAG() over partition by cliente order by foto_mes`) procesados en bloques de 25 columnas por memoria (notebook FE, celda 10) **[código]**. Clase ternaria con `LEAD` sobre los meses distintos: el último mes queda NULL y el anteúltimo solo marca BAJA+1 (celda 6) **[código]**.
- Monetarias/drift: montos `m*` divididos por el máximo (o el máx |x| si hay negativos) del mes, conservando el cero: `_norm0` (script:52-71) **[código]**. Excluye préstamos personales (script:120-131). No hay detección de drift **[no encontrado]**.
- Validación: test 202106. Búsqueda en grilla de pesos del ensamble (paso 0,05, suma 1) × envíos 8.000–15.000 maximizando la ganancia de junio (script:279-280). Compara ensamble de probabilidades vs de rankings (proba 0,35/0,30/0,35 → 13.000, 430,1 M; rank 0,15/0,20/0,65 → 12.000, 429,0 M) **[declarado]**. Undersampling al 20% de CONTINUA solo en validación (script:160-189). La BO quedó fuera del pipeline; la bitácora muestra trials con valor_cv y ganancia_test **[declarado]**.
- Corte: 10.500 fijo para agosto, sin justificación en el código (script:27, con un "TODO: confirmar") **[código]**.
- Semillas/ensamble: 16 semillas sorteadas con seed 42. Hay dos niveles: el ensamble entre modelos por semilla y luego el promedio de rangos percentiles entre semillas. Guarda checkpoint por semilla y retoma (script:432-613, 626-665) **[código]**.
- Resultados: validación 202106 ≈ 430 M **[declarado]**. La ganancia pública **[no encontrado]**: solo dice que el ensamble de probabilidades fue "consistentemente mejor en el público".
- Reproducibilidad: `requirements.txt` con versiones exactas, README paso a paso, semillas fijas, checkpoints. El FE depende de JupySQL dentro de un notebook. El repo incluye archivos temporales de Office (`~$...docx`).
- Tiempos: **[no encontrado]**.
- **Aprovechable para C02**:
  1. **Modelos especializados por disponibilidad de historia** (current / hist1 / hist2, cada uno con la ventana de meses donde sus lags existen; script:135-146). Cubre el requisito de "≥2 modelos/estrategias" y ofrece un fallback para clientes sin historia o con el mes previo anómalo (202006).
  2. Grilla conjunta de pesos × cantidad de envíos (script:279-300) para elegir la recomendación final de forma auditable.
  3. Clase ternaria calculada con `LEAD` sobre los meses existentes, que deja NULL lo no observable (FE celda 6). Aplicable a 201911/201912 en C02: entrenar con BAJA+1 en 201911 y no usar 201912.
- Relevancia para el pipeline de C02: media — arquitectura multi-modelo por disponibilidad de historia y clase con NULL en meses sin etiqueta; valida en un solo mes, el corte final es un valor fijo sin justificación en el código y no hay resultado público.

#### keilazavaglia/DMEyF_ksz — commit 5dbdef6 (2026-11-10)
- URL: https://github.com/keilazavaglia/DMEyF_ksz
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: se leyeron `submits/README.md`, el notebook final 45 (código) y el markdown, código y outputs de z003, z007, z008, z009, z011, z014–z016, z021 y z028. Solo falta 1 archivo >1 MB (un PDF de clase). **No hay contenido de C02** en el commit: el commit del 10-nov solo toca `.gitignore` y menciona una rama `undersampling_ksz` con git propio, no incluida. `CLAUDE.md` está en .gitignore (el README remite a él para los submits 16–38).
- Modelo y objetivo: LightGBM binario con target "juntar" (BAJA+1 ∪ BAJA+2 = 1, sin pesos). z009 mide +22 M en validación 04→06, 49/50 shuffle splits, aunque sube el N óptimo **[declarado]**. Hiperparámetros fijos del profesor + `num_leaves`, `min_sum_hessian_in_leaf` y número de árboles de 7 trials de Optuna (notebook 45, celda 1) **[código]**.
- Features: 153 originales (incluye `numero_de_cliente`) + lag/delta 1 y 2 = 761. **Lags por fila** con `groupby(cliente).shift(k)` (notebook 45, celda 2) **[código]**. Media de 3 meses y ratio actual/media3 (z014): +2,5 M, dentro del ruido. Canaritos (z015): con poda agresiva quedan 38 variables y pierde 24 M **[declarado]**.
- Monetarias/drift: **PSI por variable con deciles del mes de referencia y NaN como bin aparte** (z008, celda 2) **[código]**. Rank por mes de los 73 montos (z007): **pierde** 19 M (380,6 vs 399,6; 0/5 semillas) **[declarado]**. Ajustes puntuales de aguinaldo/payroll (z011) neutros; sacar `*_fultimo_cierre` da +1,6 M, dentro del ruido **[declarado]**. `ccajas_depositos` = NA en 202105 (README de submits, paso 3) **[declarado]**.
- Validación: train 04 → valid 06 y control 03 → 05. Optuna z028: 40 trials, **cada trial promedia 5 semillas**, `num_leaves` 8–256 y `min_sum_hessian` 0,001–10, early stopping por AUC (paciencia 200), valor = ganancia máxima con BAJA+2. Revalidación de los top 10 con 10 semillas en dos meses y una regla de aceptación **fijada antes de correr** (≥8/10 semillas en los dos cortes) (z028, markdown) **[declarado]**.
- Corte: z021 promedia curvas de ganancia de 10 modelos en dos meses y calcula la pérdida vs el óptimo de cada mes (minimax, ~12.500) **[declarado]**. La entrega usa el centro de la meseta pública 11.000–12.000 → 11.500 **[declarado]**.
- Semillas/ensamble: 7 trials × 10 semillas = 70 modelos, **promedio simple de probabilidades** (notebook 45, celda 5). Checkpoint por modelo en `.npy` **[código]**.
- Resultados: entrega 104,61 público (máximo 104,80 en 11.000). Evolución 90,83 → 101,92 → 104,61 documentada por submit (`submits/README.md`) **[declarado]**. Corroboración en outputs: z007/z009/z016/z021 tienen tablas guardadas que coinciden con su markdown.
- Reproducibilidad: `requirements.txt` congelado (pip freeze), un notebook por submit que no se modifica una vez enviado, y reproducción byte a byte declarada.
- Tiempos: **~6,7 h desde cero** para 70 modelos (400 min) **[declarado]**. z016: 26,6 s por modelo con el 100% de CONTINUA en un mes, 8,1 s con el 20% (−7 M) **[declarado, output guardado]**.
- **Aprovechable para C02**:
  1. PSI por variable mes contra mes de referencia, con NaN en bin propio (z008 celda 2). Aplicable como **chequeo automático en producción** sobre cada `input/<yyyymm>.csv` para detectar columnas en cero o desplazadas (202006) y alimentar el reporte acumulativo.
  2. Medición del costo/beneficio del undersampling (z016: 3,3× más rápido por −7 M sobre ~400 M), dato directo para el presupuesto de 15 min.
  3. Protocolo de Optuna con varias semillas por trial + revalidación con regla predefinida en dos meses (z028), para elegir hiperparámetros offline con 201901–201912 sin ajustar a un solo mes.
- Relevancia para el pipeline de C02: media — PSI por variable y medición del tiempo con undersampling; sin contenido de C02, pipeline final de ~6,7 h y lags por fila.

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

### Lote C — fichas

Convenciones: **[declarado]** = README/comentarios/outputs guardados; **[código]** = verificado leyendo código; **[no encontrado]**.
Rutas relativas a la raíz de cada repo. Ningún repo del lote tiene archivo LICENSE ⇒ **todos los derechos reservados: no copiar código, solo ideas**.
Ganancia: en el código de todos los repos C01 la constante es **+1.072.500 (BAJA+2) / −27.500** (umbral 1/40 = 0,025), no 780.000/−20.000. Solo el README de pfranzd dice 780.000/−20.000 (el umbral es el mismo, 1/40).

---

#### wujparker/dmeyf — commit 9728a69 (2026-09-24)
Descartado. Contenido sin relación con la materia: 500 archivos `.md` sobre otro tema (lotería "快3"); un solo commit; sin código.

---

#### pfranzd/dmeyf2026-entregas — commit 8f5e659 (2026-10-11)
- URL: https://github.com/pfranzd/dmeyf2026-entregas
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: se leyó todo el código (pipeline Python + configs YAML + resúmenes de Optuna). Omitidos por tamaño: los 72 modelos LightGBM `competencia_01/competencia_1/definitiva/componentes/*/modelos/t*_s*.txt` (2,7–17 MB). Sin notebooks con outputs relevantes.
- Modelo y objetivo: LightGBM `binary`, positivos = BAJA+1 ∪ BAJA+2, con `peso_baja1` que Optuna puede ajustar. Ganancia y AUC se miden solo sobre BAJA+2 **[código]** `configs/base.yaml:19-22`, `pipeline/metricas.py:13-21`.
- Features **[código]**: intrafila (consolidado TC, fechas, ratios, agregados, flags); sobre campos "curados": lags 1-2, deltas 1-2 (absolutos y %), ventanas de 2-3 meses (avg/max/min/std + ratio contra la media), pendiente `regr_slope`, historia (`meses_en_panel`), deciles por mes. **Los lags son por calendario**: arma un panel denso con un CROSS JOIN cliente×mes y filas fantasma para los meses faltantes, así `lag(x,n)` = n meses atrás (`pipeline/features/temporales.py:1-33`). La familia "comportamiento" (e034) agrega: perdió payroll, productos perdidos, status de TC que sube, recency (meses desde el último payroll/trx/consumo, cuenta meses con un índice de mes continuo), drenaje de saldo contra el máximo de t-2..t, racha de caída de `ctrx_quarter` y RFM por quintiles del mes (`pipeline/features/comportamiento.py:19-94`). Los clientes sin historia quedan en NULL.
- Montos y drift **[código]**: `montos: crudo | rank_cero_fijo | deflactado` aplicado **antes** de lags/deltas. `rank_cero_fijo` = cume_dist por mes y por signo (negativos en [−1,0), cero en 0, positivos en (0,1]); `deflactado` = monto / mediana de los positivos del mes (`pipeline/features/rankings.py:47-70`). Saca 4 columnas por PSI alto (`base.yaml:28-32`). Diagnóstico **[declarado]** `configs/exp/e033...yaml`: inflación ~3 %/mes y aguinaldo de junio (`mpayroll` +48 %).
- Validación: folds temporales con **gap 2**: train [202103]→valid 202105 y train [202103,04]→valid 202106; el modelo final entrena 202103–06 y predice 202108 **[código]** `configs/exp/e032...yaml`. Optuna con objetivo AUC promedio de los folds y MedianPruner por fold; 60 trials por componente (lr, num_leaves 8-256, min_data_in_leaf, feature_fraction, num_iterations). Undersampling 0,25 en la optimización; el final va sin undersampling y reescala `min_data_in_leaf` por filas.
- Elección del corte: `envios: auto` = mediana de los envíos óptimos de validación × (n_target/n_valid), redondeada a 500 (`pipeline/salida.py:100-123`). El óptimo sale de la "meseta": argmax de la curva suavizada con media móvil de 401 (`dmeyf/metrics.py:68-84`). La entrega final fijó 10.500.
- Semillas y ensambles: por componente, top-12 trials × 2 semillas = 24 modelos con promedio de probabilidades. Ensamble final: **promedio de rankings normalizados** de 3 componentes (72 modelos) (`pipeline/ensamble.py:20-63`). Mide el Jaccard del top-N entre componentes para chequear diversidad (`ensamble.py:66-80`).
- Resultados: público **110,165 M** con 10.500 envíos **[declarado]** `README.md` y `definitiva/entrega.json`. AUC de Optuna 0,8986 (e032) **[declarado]** `optimizacion/*/resumen.json`.
- Reproducibilidad: `requirements-lock.txt`, Python 3.11, `deterministic`, `num_threads` fijo, comprobación de sha256 del CSV final, tres modos (predecir/entrenar/completo), configs heredables y `fe_hash` para cachear features.
- Tiempos **[declarado]**: predecir con los modelos ya entrenados ~1 h; reentrenar ~4 h; completo con Optuna ~5 h; features ~10 min y ~10 GB.
- **Aprovechable para C02:**
  1. Panel denso con CROSS JOIN + `lag()` en DuckDB ⇒ lags por calendario, con `mes_0`/`meses_en_panel` como indicador de presencia (`temporales.py:15-33, 108-120`); corresponde a la evaluación por calendario de C02.
  2. `rank_cero_fijo`/`deflactado` por mes **antes** de lags (`rankings.py:47-70`): trata la inflación de 2019–2021 sin IPC externo y es reproducible en producción mes a mes.
  3. Ensamble de rankings normalizados + Jaccard de top-N para documentar "≥2 modelos" (`ensamble.py`), y corte por meseta suavizada (`metrics.py:68-84`).
- Relevancia para el pipeline de C02: alta — pipeline DuckDB/LightGBM con lags por calendario, escala de montos por mes antes de los lags y ensamble de rankings; el tiempo declarado de predicción con modelos entrenados (~1 h) supera el límite de 15 min por mes.

---

#### vmanuelmarasco/dmeyf_2c_2026 — commit 5290716 (2026-10-11)
- URL: https://github.com/vmanuelmarasco/dmeyf_2c_2026
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: 229 archivos (material de clase, EDA, informes, varias versiones). Se leyeron `entregas/v1|v2/README.md`, `pipeline/p00/p01/p10*.py`, el log de `p10_real` y partes de `entregas/v2/competencia_v4.ipynb`. Omitidos por tamaño (22): PDFs de clase, `EDA.ipynb`, `competencia.ipynb`, `Modelo Baseline.ipynb`, z401/z201 de clase, CSVs de predicciones y entregas (`entrega_agosto.csv`, `predicciones_*`, `validacion_ensemble_trial25.csv`, `probabilidades_real_*.csv`) y un modelo `modelo_trial25_semilla_500041.txt`.
- Modelo y objetivo: LightGBM binario. v1 entrena solo con BAJA+2; v2 (la final) con BAJA+1 ∪ BAJA+2, que según el README tuvo mayor ganancia en validación temporal **[declarado]** `entregas/v2/README.md`. La ganancia siempre se calcula desde la clase ternaria **[código]** `pipeline/p10_adaptativo.py:343-347`.
- Features: v1 = 940 (144 crudas + 796 temporales); v2 = 295 (bloques de negocio B1/B4/B6 + lag1/delta1) **[declarado]**. **Lags por calendario** **[código]**: `lag_por_calendario` hace un merge por (cliente, índice de mes + k) en lugar de `shift` (`p10_adaptativo.py:384-398`); el target se arma sobre CROSS JOIN cliente×mes con `mes_0` (`pipeline/p01_base.py:101-150`). En v4, `shift(1)` va enmascarado con `tiene_historia_lag1` (celda 51). Media de 3 meses, ratio y tendencia `(x_t − x_{t−2})/2` (`p10:437-454`).
- Montos y drift **[código]**: etapa de diagnóstico automática con % de ceros y nulos por mes, PSI contra el primer mes y detección de "columnas rotas" (≥99 % ceros/nulos en un mes, normales en el resto y en algún mes previo) (`p10:879-945`). La reparación (poner NULL en ese mes) **no se aplica de forma incondicional**: entra como candidato y compite (`p10:472-481`). Rank por mes como candidato (`p10:457-469`), que se rechazó en la corrida real **[declarado]** `pipeline/salidas/p10_real.log`. Agente aparte: `mpayroll` como posición dentro del mes por el aguinaldo **[declarado]** `agente_churn/README.md`.
- Validación: folds temporales con gap 2 ("mayo": train 202103→valid 202105; "junio": train 202103-04→valid 202106) (`p00_config.py:125+`). Un cambio se acepta solo si gana en **los dos folds** con Wilcoxon apareado por semilla (20 semillas) **[código + declarado]** `p10:1-60`. v2: Optuna con ensamble de 5 semillas por trial, ganancia de validación 285 M (202105) / 369 M (202106) **[declarado]**.
- Elección del corte: v1 umbral teórico 0,025 (9.520 envíos); v2 top 8.750 por probabilidad **[declarado]**. Prueba reglas de corte alternativas "elegidas en un mes y medidas en el otro" y ninguna supera al 0,025 **[declarado, output guardado]**. Corrige la probabilidad por el undersampling antes de aplicar el umbral (`p10:350-362`).
- Semillas y ensambles: 5 semillas con promedio de probabilidades. Hay un ensamble experimental LGBM+XGB+RF fuera del flujo principal (`agente_churn/src/experimental/05_b_multi_model_ensemble.py`).
- Resultados: ganancia pública **[no encontrado]**. Validación **[declarado]**: v1 414 M en 202106; agente 404 M en 202106 con 14.500 envíos.
- Reproducibilidad: README por entrega, semillas fijas y `decisiones.jsonl`/`estado.json` por corrida; la v2 depende de un notebook con `dataset_path` editado a mano y hay varias versiones paralelas.
- Tiempos: corrida completa de `p10` ~14 min (log 22:39→22:53, 238 features) **[declarado, output guardado]**; v1: pipeline ~25 min + entrenamiento ~5 min **[declarado]**; ~3 s por modelo en el banco de mediciones (`banco_medicion/mediciones.csv`).
- **Aprovechable para C02:**
  1. Detector automático de columnas anómalas por mes (ceros/nulos ≥99 % con historia normal) + PSI (`p10_adaptativo.py:906-945`): aplicable a 202006 y a la **validación de cada `input/<yyyymm>.csv` en producción** antes de predecir.
  2. Lag por calendario vía merge sobre índice de mes (`p10:384-398`): implementación pandas para el script de producción.
  3. `corregir_probabilidad` por undersampling (`p10:350-362`): necesario si C02 reporta `probabilidad` y `enviar` con umbral.
- Relevancia para el pipeline de C02: alta — diagnóstico automático de columnas anómalas por mes y PSI, aplicable a 202006 y al control de cada input mensual; lags por calendario.

---

#### veritomonzon/dmeyf2026-personal — commit 279d520 (2026-11-04)
- URL: https://github.com/veritomonzon/dmeyf2026-personal
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: se leyó `Primera competencia/primera_competencia.R` (1.647 líneas, con el historial de experimentos en los comentarios) y `Segunda competencia/Experimentos Colaborativos/README.md`. Omitidos por tamaño: 3 PDFs de bibliografía (`2523813.pdf`, `byrd19a.pdf`, `s12911-024-02428-z.pdf`). No se leyeron los notebooks de tareas (z0290/z0333/z494).
- Modelo y objetivo: LightGBM en R. Probó `baja2` contra `baja12` (BAJA+1∪BAJA+2), y `baja12` obtuvo +17,8 M en las 5 semillas (t apareado p≈0,006) **[declarado]** `primera_competencia.R:87-90`. Final M8: `baja12` **[código]** `:17-20`.
- Features: lag1/2 y delta1/2 con `shift` **por fila** dentro de cada cliente (`:388-394`, `:581-583`). Variantes M1–M8: flags de tenencia, totales Visa+Master, ratios contra lag1, flags `_zero` y tendencia/min/max con ventana 6 (`TendenciaYmuchomas`, `:496-518`).
- Montos y drift: ranking con cero fijo por `foto_mes` (`:399-411`). Pone `ccajas_depositos` de 202105 en NA (columna con valores anómalos) **antes** de los lags (`:337-339`). Detecta automáticamente variables todo-cero por mes (`:230-243`). Saca préstamos personales (M8).
- Validación: BO entrena con 202103+04, deja 202105 de gap y valida en 202106; producción entrena 202103–06 → 202108 (`:23-25`). BO con mlrMBO sobre 3 hiperparámetros (iters, leaves, min_sum_hessian), 50–276 iteraciones según el experimento, con ganancia suavizada ±250 **[declarado]** `:95-110`. Compara modelos con 10 semillas, Wilcoxon y corrección de Holm.
- Elección del corte: grilla de cortes fijos 9.000–14.000 evaluada en el ensamble (`:52`); final c13000.
- Semillas y ensambles: 10 semillas para testeo y 50 para producción, con promedio. **Exclusión de "dudosos"**: CONTINUA con prob > 0,5 según un modelo auxiliar entrenado en el 30 % de los datos (`:731-768`); quitó 195 filas.
- Resultados **[declarado]**: el máximo público fue 103,18 (modelo único, exp03c); el submit final M8 con ensamble de 50 semillas y c13000 dio **93,78** público. Testeo en 202106: M8 468 M, M2 (rank cero fijo sin lags) 440,6 M, M3 (rank → lags) 385 M.
- Reproducibilidad: un solo script R con bloque PARAM y semillas primas reproducibles; bitácora de experimentos en comentarios. Rutas absolutas de la máquina del autor (iCloud/VM).
- Tiempos **[declarado]**: testeo M8 0,39 h; producción con 50 semillas 1,9 h; BO de 200 iteraciones 7,6 h.
- **Aprovechable para C02:**
  1. El README de C02 (`Segunda competencia/.../README.md`, secc. 6-7) describe un diseño para **201901–202104 → gap 202105 → test 202106**, con ponderación temporal por mes (`weight` en `lgb.Dataset`) normalizada a media 1, placebo e invertidos, margen δ = desvío entre semillas, TOST y ESS de Kish. Aplicable como protocolo para decidir si se ponderan meses (p. ej. bajarle el peso a 2020).
  2. Resultado declarado: rankear y **después** calcular lags (M3) dio menor ganancia en 202106 que lags sobre crudos (M1) o rank sin lags (M2) **[declarado]** `:113-117`. El orden rank→lag requiere prueba antes de adoptar el esquema de pfranzd.
  3. Filtro de CONTINUA "dudosos" (`:731-768`) como experimento de bajo costo.
- Relevancia para el pipeline de C02: media — protocolo para ponderar meses y comparación de orden rank→lag; lags por fila e implementación en R.

---

#### vmalsam/dmeyf2026-predfinal-victor_malsam — commit 35c7e86 (2026-09-22)
Descartado. Corresponde a otra competencia: workflow "Gerencial" z719 de Kaggle `utn-2026-virtual-mgr`, dataset `gerencial_competencia_2026.csv.gz` del bucket `itba2026`, futuro = 202109, cortes de 800 a 1.300 y score público 25.318 [notebook, celdas 0, 7, 9; `Validacion_Victor/README.md`]. Dato técnico conservado para C02: el dataset **incluye 202006** y la celda 26 pone en NA para ese mes esta lista de columnas: `internet`, `mrentabilidad`, `mrentabilidad_annual`, `mcomisiones`, `mactivos_margen`, `mpasivos_margen`, `mcuentas_saldo`, `ctarjeta_visa_transacciones`, `mtarjeta_visa_consumo`, `mtarjeta_master_consumo`, `ccallcenter_transacciones`, `chomebanking_transacciones`; permite contrastar el detector propio. También declara que una media móvil de 6 meses (ma6) "casi" iguala a la referencia y que lag4 da menor resultado (README). Lags con `shift` por fila. Relevancia para el pipeline de C02: baja — solo por la lista de columnas de 202006.

---

#### tahiel53/DMEyF-competencia_1 — commit f7cd493 (2026-10-10)
- URL: https://github.com/tahiel53/DMEyF-competencia_1
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: README, 4 notebooks en R con outputs, log de la BO y resumen de la entrega. Omitidos por tamaño: 50 `exp/modelos/{backtest,final}_set*_s*.txt` (~4,9 MB c/u; según el README son predicciones por modelo).
- Modelo y objetivo: LightGBM binario, positivos = BAJA+1 ∪ BAJA+2 **[declarado]** README.
- Features: lag1/2 y delta1/2 de **todas** las variables con `shift(.SD, k)` **por fila** (`0_preprocesamiento.ipynb` celda 10). Después, ranking con cero fijo por mes que **reemplaza** a los originales, lags y deltas (celda 12). Usa `numero_de_cliente` como feature y no usa `foto_mes` **[declarado]** README.
- Montos y drift: el rank por mes cubre la inflación. Saca `cprestamos_personales`/`mprestamos_personales` por drift y pone en NA `ccajas_depositos` de 202105 **[declarado]**.
- Validación: BO (mlrMBO) con train 202103+04 completo, test 202106 y métrica AUC; **10 iteraciones**, semilla 370003. Optimiza `num_iterations`, `num_leaves` y `min_sum_hessian_in_leaf`, con lr 0,005, ff 0,5 y bynode 0,2 fijos (`exp/BO/BO_log.txt`).
- Elección del corte: curva de ganancia de un backtest (mismos sets entrenados en 202103-04 y aplicados a 202106) más el público de varios cortes ⇒ 11.750 (`3b_...ipynb` celdas 11-13).
- Semillas y ensambles: top-2 sets de la BO × 20 semillas = 40 modelos, con promedio de probabilidades.
- Resultados **[declarado]** `exp/entregas/resumen_10102129.txt`: backtest 202106 456,8 M con 11.750 envíos (máximo 461,7 M con 10.530). Ganancia pública **[no encontrado]**: el campo "ganancia del bot" quedó vacío.
- Reproducibilidad: semillas fijas, `deterministic`, notebooks reanudables (la BO retoma desde el log y el notebook 2 saltea modelos ya hechos) y tres niveles de reproducción documentados. El dataset va en `../`.
- Tiempos **[declarado]**: ~22 min por modelo final (num_leaves ~1.000-1.900, 3.000 iteraciones, lr 0,005); total ~18 h en 12 vCPU; BO ~75 min. El tiempo por modelo (~22 min) y el total (~18 h) superan el límite de 15 min por mes de C02 si el entrenamiento se hiciera en producción.
- **Aprovechable para C02:**
  1. Patrón de checkpoints reanudables (BO_log y modelos ya entrenados que se saltean) para el entrenamiento offline.
  2. Usa `numero_de_cliente` como feature; en C02, entre 2019 y 2021 los IDs nuevos cambian de distribución, por lo que el pipeline no incorpora esa variable.
- Relevancia para el pipeline de C02: baja — lags por fila y tiempos de entrenamiento por encima del límite de 15 min; solo el patrón de checkpoints es aplicable.

---

#### SnehitDua/Churn-Prediction-DMEyF — commit b0f3d74 (2026-10-11)
- URL: https://github.com/SnehitDua/Churn-Prediction-DMEyF
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: parcial. De los 21 archivos de `git ls-tree`, se omitieron 18 por tamaño: `modelos/lgb_seed236983.zip` … `lgb_seed237000.zip` (~69 MB c/u). Están `churn-prediction.ipynb` (con outputs), `output/Optuna.db` y `output/final_submit_20261011.csv` (11.000 IDs).
- Modelo y objetivo: LightGBM binario, positivos = BAJA+1 ∪ BAJA+2 **[código]**, celda 4. La curva de ganancia de validación usa la etiqueta binaria, por lo que los BAJA+1 cuentan como aciertos **[código]**, celda 9; la ganancia de Optuna resultante es ~1.236 M, no comparable con ganancias calculadas solo con BAJA+2. Además toma 1.100.000 como ganancia neta por acierto.
- Features: lags y deltas 1-2 de todas las columnas, **por calendario**: valida mismo cliente y diferencia de índice de mes == k, y si no, NaN (celda 7). 760 features. Pone `ccajas_depositos` de 202105 en NaN.
- Montos y drift: **[no encontrado]** (sin deflactar ni rank).
- Validación: train 202103-05 → valid 202106 (**gap 1**; en producción el gap es 2). Optuna TPE sobre `num_leaves` y `min_sum_hessian`, con el resto fijo (lr 0,005, ff 0,5, bynode 0,2, max_bin 31). Una sola pasada a 2.000 iteraciones, mide la ganancia suavizada (ventana 1.001) cada 32 iteraciones, suaviza la curva por iteración y elige el `best_iter`; 33 trials (celdas 9-13). Función `chequear_bordes`, que avisa si los mejores trials tocan un borde del espacio o si `best_iter` ≈ MAX_ITER (celda 14); en el output avisa que `best_iter` 1.984 ≈ 2.000.
- Elección del corte: umbral 27.500/1.100.000 sobre la probabilidad corregida por el undersampling (`corregir_prob`), acotado a [env_min, env_max]; la entrega fuerza 11.000 (el umbral daba 7.416) (celda 18).
- Semillas y ensambles: 18 semillas con promedio de probabilidades; el modelo final usa iteraciones × 1,1 por tener más datos.
- Resultados: público **[no encontrado]**.
- Reproducibilidad: notebook Kaggle, versiones sin fijar, study en SQLite reanudable.
- Tiempos **[declarado, output guardado]**: ~4-6 min por trial (21:32→21:35→21:41→21:45).
- **Aprovechable para C02:**
  1. Lag por calendario vectorizado en numpy (comparar cliente e índice de mes desplazado k) (celda 7): sin merge, compatible con la producción en ≤15 min.
  2. `chequear_bordes` del espacio de Optuna + selección de `best_iter` por curva suavizada (celdas 13-14).
- Relevancia para el pipeline de C02: baja — lag por calendario vectorizado y chequeo de bordes; la validación usa gap 1 y la métrica de ganancia cuenta BAJA+1 como acierto.

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

### Lote D — fichas

Notas generales del lote:
- **Ganancia de C01 2026 = +1.072.500 por BAJA+2 contactado / −27.500 por cualquier otro envío** (no 780.000/−20.000). Coinciden 8 de los 10 repos: **[código]** lovrich `run_rank_prestamos_junbo_hist.R:337`, laguinge `02_optuna_bimodal_v64.py:93`, montagnaflor (celda c06), nicobaranek `motor.R:129`, y **[declarado]** en los README de marcostrigueros, ezequielabregu y tomasfarias.
- **Licencias:** ninguno de los 10 repos tiene LICENSE (`git ls-tree`; en todo el pool solo BustosMaxx tiene uno) ⇒ **sin licencia: todos los derechos reservados. No copiar código, solo ideas.**
- Meses de C01: 202103–202108. La clase de 202107 está incompleta, la de 202108 es desconocida. Casi todos validan con "train 202103–04 → test 202106" (mismo hueco de 2 meses que junio → agosto).
- Patrón que se repite en el lote: `ccajas_depositos` toda en cero en 202105 → NA. Es el análogo de las columnas en cero de 202006 en C02.

---

#### agustinlovrich/dmeyf-primera-competencia — commit 6ef281f (2026-10-11)
- URL: https://github.com/agustinlovrich/dmeyf-primera-competencia
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: completa. Un script R end-to-end, README, log completo de la BO y CSV de evaluaciones. No faltan archivos.
- Modelo y objetivo: LightGBM binario. Positivo = BAJA+1 ∪ BAJA+2, sin pesos **[código + declarado]**. Hiperparámetros fijos lr 0.005, max_bin 31, min_data_in_leaf 0, ff 0.5, ff_bynode 0.2, deterministic.
- Features **[código]**:
  - **Ranking con signo por mes** sobre las 152 variables (`ranking_signado`, L241-256): 0 queda en 0, positivos en (0,1], negativos en [−1,0), NA queda NA.
  - **Los valores crudos se descartan**: el modelo solo ve variables transformadas.
  - lag1/lag2 y delta1/delta2 sobre los rankings, **por calendario exacto**: `match(cli*1e5 + periodo − k)` (L262-268). Si falta el mes, queda NA.
  - tend3/avg3: pendiente MCO y promedio sobre una ventana de 3 filas del cliente, en C++ (L49-120, L289). Esta ventana es **posicional, no de calendario**.
  - En total 7 columnas por variable, 1064 columnas.
- Monetarias y drift: el ranking por mes hace de deflactor. `ccajas_depositos` pasa a NA en 202105 (dq1). Los préstamos personales quedan fuera de la BO y se reincorporan en el modelo final **[código]**.
- Validación: BO con mlrMBO (Kriging + EI), 10 puntos LHS y hasta 30 iteraciones con tope de 120 min. Optimiza **AUC** con train 202103+04 → valid 202106 **[código]**. Espacio: iter 600–3500, hojas 16–256, hessian 1e-4–0.03. Loguea la correlación AUC↔ganancia.
- Corte: barrido 9000–13000 de a 500. Elige **11000** por la ganancia **media entre semillas** en junio, y lo confirma con el público **[declarado]**.
- Semillas y ensamble: 40 semillas (pool sorteado con la primigenia y un control de reproducibilidad, L175-181). Promedio de probabilidades.
- Resultados **[declarado]**: público 107.44 en corte 11000. Sin el FE histórico daba 104.50. Junio a 11000: 454.96 ± 3.89 M.
- Reproducibilidad: variables de entorno, SHA256 de la entrega, opción para saltear la BO, R 4.6.1 + lightgbm 4.7.0.
- Tiempos **[declarado, output guardado]**: BO ~125 min, entre 112 y 593 s por evaluación (`junbo_hist.log` L39-47). Entrenamiento final de 40 modelos con 1439 árboles: no está desglosado.
- Aprovechable para C02:
  1. Ranking con signo por mes **en lugar de** los montos crudos (L241-256): trata inflación y drift sin IPC.
  2. Lags por calendario vía `match(id, periodo−k)` (L262-268): corresponde al cambio que C02 evalúa, con bajo costo de cómputo.
  3. Elegir el corte con la media entre semillas, no con el pico del ensamble.
- Relevancia para el pipeline de C02: alta — lags por calendario y ranking por mes en reemplazo de montos crudos, compatibles con la producción mensual.

#### la-laguinge/dmeyf-2026-competencia-01 — commit 715cddf (2026-10-11)
- URL: https://github.com/la-laguinge/dmeyf-2026-competencia-01
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: los 3 modelos `.txt` guardados (~8 MB cada uno) no se bajaron. Se leyeron los 4 scripts, el README y `optuna_low.db` (binario, no inspeccionado).
- Modelo y objetivo: LightGBM binario con `is_unbalance=True`, GPU. Entrena con BAJA+1 ∪ BAJA+2 (`clase_peligro`) y valida solo contra BAJA+2 **[código]**.
- Features **[código]**: originales más lag1/lag2/delta1/delta2 de **solo 9 variables "núcleo"**. Los lags son **por fila**: `shift` + chequeo de mismo cliente, sin chequear el mes (`03_entrenar...py:65-77`).
  - El script final carga `foto_mes IN (2021-01..06, 202108)` **sin 202107** (L53). Con lags por fila, en 202108 el "lag1" toma junio (t−2) y el "lag2" toma mayo, mientras que en train el lag1 es t−1.
  - El README declara "verificando estricta contigüidad"; el código chequea mismo cliente pero no el mes.
- Monetarias y drift: solo `ccajas_depositos` pasa a NA en 202105. No hay ranking.
- Validación: Optuna con train 202103–05 → valid 202106 (**hueco de 0 meses**). Objetivo: **ganancia a K = 11500 fijo**. Timeout de 1200 s con n_jobs = 4. Busca n_estimators, hojas 12–35, hessian, ff, ff_bynode, bagging. **Elige el 2.º mejor trial** ("LowTop2", L99-102).
- Corte: fijo en 11500.
- Semillas y ensamble: 3 semillas, promedio de probabilidades.
- Resultados **[declarado]**: público 103.7 M. Lags sobre todas las variables, lag3, ratios y aceleración dieron menor ganancia ("empeoraron").
- Reproducibilidad: guarda los boosters `.txt` para reproducir bit a bit, dado que el entrenamiento en GPU no es determinista. Rutas fijas de Colab. requirements sin versiones.
- Tiempos **[declarado]**: inferencia con modelos guardados en menos de 10 s. BO 20 min.
- Aprovechable para C02:
  1. Caso concreto de lags por fila cuando falta un mes en el input de producción (L53 vs L65-77); aplicable como caso de test del pipeline.
  2. Guardar los boosters entrenados y solo cargarlos en producción mensual (≤ 15 min).
- Relevancia para el pipeline de C02: baja — modelo con lags de 9 variables; el repo documenta el desplazamiento de lags por fila cuando falta un mes en la carga, útil como caso de test.

#### montagnaflor/DMEyF-Competencia-01 — commit c9a71f6 (2026-10-12)
- URL: https://github.com/montagnaflor/DMEyF-Competencia-01
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: notebook completo **sin outputs guardados** y README. Falta `orden_filas.csv.gz` (4.7 MB; solo trae el orden de filas para reproducir).
- Modelo y objetivo: LightGBM binario, positivo BAJA+1 ∪ BAJA+2. Undersampling del 25 % de CONTINUA, con la ganancia corregida por 1/0.25. Tiene además una línea base de RandomForest **[código]**.
- Codificación de la clase en el peso: `1 + 1e-5·clase`, para que el `feval` mida solo BAJA+2 (celda c16).
- Features **[código]**, celda cell-6, DuckDB:
  - delta1/delta2 con `lag() over (partition by cliente order by foto_mes)`, es decir **por fila**.
  - ratio contra la media de 3 meses y `regr_slope` sobre `mes_idx`, con ventana `ROWS 2 PRECEDING` (por fila).
  - `percent_rank` por mes de 13 montos.
  - flags "apagó el producto", `n_productos_apagados` y `meses_sin_payroll_3`.
- Monetarias y drift **[código]**:
  - **PSI junio vs agosto** con un bin extra para nulos (c12). Excluye variables con PSI > 0.25 o con más de 20 pp de diferencia de nulos (c13).
  - Préstamos personales en NaN **solo en junio** porque el dato es anómalo (cell-17). Según el README, eso subió la ganancia de junio de 395 a 449 M.
  - Canaritos: 20 de ruido; descarta toda variable que no supera al mejor canarito (c19).
- Validación: Optuna con 100 trials y CV de 5 folds sobre 202103–04. Métrica: **ganancia suavizada** (máximo de la media móvil de 401) con early stopping. Holdout 202106, que nunca entra a la BO.
  - Control de la maldición del ganador: toma los 5 mejores trials × 10 semillas en junio y elige por media (c32-c33).
- Corte **[código]**, c37: el que maximiza la ganancia **media entre semillas** en junio, trasladado a agosto **como proporción de la cartera** (11000 → 11036).
- Semillas: 20 en el modelo final. `min_data_in_leaf` se escala por la cantidad de filas y el modelo final usa max_bin 255 (c40).
- Resultados **[declarado]**: público 101.12. Hay una tabla de experimentos que incluye variantes con menor ganancia; por ejemplo, el mismo método con otra muestra de CONTINUA dio 92.07.
- Reproducibilidad: versiones exactas, rutas relativas, base de Optuna en SQLite, `registro.json`.
- Tiempos **[declarado]**: ~5 h en una PC de 8 núcleos y 8 GB.
- Aprovechable para C02:
  1. PSI mes-entrenamiento vs mes-a-predecir con bin de nulos (c12-c13) como **chequeo automático de drift en producción**; detectaría columnas en cero como las de 202006.
  2. NaN dirigido a una variable en un mes anómalo (cell-17).
  3. Corte como **proporción de la cartera**, robusto a cambios de tamaño entre meses (c37).
- Relevancia para el pipeline de C02: alta — PSI contra el mes a predecir, NaN dirigido por mes y corte como proporción de cartera; los lags son por fila.

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

#### ezequielabregu/DMEyF_competencia_1 — commit bc9f2a9 (2026-10-07)
- URL: https://github.com/ezequielabregu/DMEyF_competencia_1
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: completa. 7 notebooks **con outputs**, README, requirements con versiones y JSON de hiperparámetros.
- Modelo y objetivo: LightGBM gbdt binario, BAJA+1 ∪ BAJA+2; la ganancia se mide solo con BAJA+2 **[código + declarado]**.
- Features **[código]**, `05_variables.ipynb` celda ca3f5d88, bloques comparados por separado:
  - B2: lag1/lag2/delta1/avg3/min3/max3 y slope3 de 8 variables, en DuckDB. La pendiente es `regr_slope(x, cliente_antiguedad)`.
  - B3: flags de "empieza a pagar comisión", "perdió sueldo", "cae saldo", contadores de 3 meses (NULL si hay menos de 3 meses de historia) y consumo vs promedio de los 3 meses previos.
  - B4: `percent_rank` por mes de 73 montos, **reemplazando** al monto.
  - B5: lag1/delta1 de todas las variables; para los montos, sobre su ranking con el cero fijo.
  - Lags **por fila**: lo declara así ("en los intermitentes, el último mes en que estuvieron"). En total 507 variables.
- Monetarias y drift **[código]**, `04_drift`:
  - variantes V0–V5 comparadas con Wilcoxon pareado sobre 10 semillas.
  - V5 saca `Master/Visa_fultimo_cierre` (**valores anómalos en 202106**) y `Finiciomora` (PSI 3–6), y pasa `ccajas_depositos` a NA en 202105.
  - Sacar los préstamos aumentaba la ganancia en junio pero **restó 4.5 en el público**, así que se conservaron.
- Validación: prueba A (03–04 → 06), B (03 → 05) y C (03–05 → 06, solo de referencia). Ganancia en la meseta suavizada (ventana 501), 10 semillas por variante y **regla de adopción** con Wilcoxon (celda 552b2d67).
  - Optuna: 50 pruebas en A con 20 % de CONTINUA. Elige la prueba 42 y la valida con 5 semillas en A y C (`hiperparametros_p42.json`).
- Corte: N = 12000, elegido con el público. La meseta de 11500–12500 es más larga que la de los backtests **[declarado]**.
- Semillas: 40 (dos juegos de 20 primos). Promedio de probabilidades. "Más diversidad (bagging, ff 0.4) ⇒ el semillerío suma +6.8" **[declarado]**.
- Resultados **[declarado]**: público **110.25**. Hay una tabla de contribución por paso.
- Reproducibilidad: controles con `assert` (lags vacíos donde no hay historia, orden de filas, SHA256), versiones fijadas y modo rápido.
- Tiempos: 7–35 s por modelo de backtest (celda b5269bc0) **[declarado, output guardado]**. ~21 min por 20 semillas finales **[declarado]**.
- Aprovechable para C02:
  1. Protocolo de adopción de features y limpiezas: 10 semillas, meseta suavizada y Wilcoxon pareado por semilla. Aplicable a "lags por fila vs calendario" con 2019.
  2. Asserts de integridad de las features (celda 27fbe33d): lags NA en el primer mes, chequeo manual de un cliente, rankings en rango.
  3. Señales de comportamiento B3 (comisión, pérdida de sueldo).
- Relevancia para el pipeline de C02: alta — protocolo estadístico de adopción (Wilcoxon por semilla sobre meseta suavizada) aplicable a la comparación de lags por fila vs calendario y a la elección de columnas a anular en 202006.

#### germandasr/DMEyF---1ra-Competencia — commit f0ff0ad (2026-10-11)
- URL: https://github.com/germandasr/DMEyF---1ra-Competencia
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: falta `probabilidades_20_semillas.txt`. Notebooks R sin outputs de resultados; el de ensamble contiene una celda de texto que falla al ejecutarse.
- Modelo y objetivo: plantilla de la cátedra. LightGBM binario BAJA+1 ∪ BAJA+2; lr 0.005, min_data_in_leaf 0, ff 0.5 **[código]**.
- Features: originales + lag1/lag2/delta1/delta2 con `shift` por cliente, **por fila** (cell-35). Saca los préstamos personales "por drift visual" y pasa `ccajas_depositos` a NA en 202105.
- Validación: BO mlr3mbo con **10 iteraciones**, métrica **AUC**, partición aleatoria 70/30 de 202103+04 (sin validación temporal). Busca iter, hojas y hessian.
- Corte: 11100 fijo **[código]**. "El ensamble mejor obtenido es de 11100" **[declarado]**; la curva o evaluación que lo respalda **[no encontrado]**.
- Semillas: 20, promedio simple.
- Resultados: **[no encontrado]**.
- Reproducibilidad: rutas absolutas de la máquina del autor (Windows) e `install.packages` dentro del notebook.
- Aprovechable para C02: sin elementos adicionales a la plantilla de la cátedra.
- Relevancia para el pipeline de C02: ninguna — coincide con la plantilla de la cátedra; lags por fila y BO sin validación temporal.

#### kevinlpagnotta/DMEyF---Primera-Competencia — commit 391d0f9 (2026-10-11)
- URL: https://github.com/kevinlpagnotta/DMEyF---Primera-Competencia
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: faltan `filtro_canaritos_etapa1/2.csv` (~3 MB cada uno). El notebook R está **sin outputs**. Se leyeron `BO_log.txt` (50 iteraciones) y `campos_finales.csv` (5199 variables).
- Modelo y objetivo: LightGBM binario BAJA+1 ∪ BAJA+2; ensamble de 5 "recetas" (top 5 de la BO) **[código]**: `n_recetas <- 5`. El encabezado del notebook y el README dicen 10 y 5 respectivamente; se toma el valor del código.
- Features **[código]**:
  - percentil por mes con el cero fijo para todas las variables (12 excepciones quedan en crudo).
  - lags 1–3, deltas 1–3 y acumulado; los lags son **por calendario**: `shift` + validación `pe == periodo − k` (~L510-527 del JSON).
  - tend3/avg3.
  - Ronda 1 de interacciones de todas contra todas (×, ÷): ~33.500 columnas. Luego canarito, ronda 2 (21.870 más), canarito 2 y 5199 finales.
- Limpieza: "limpieza cruzada A/B": un modelo entrenado con una mitad puntúa a la otra y se **eliminan los CONTINUA con prob > 0.5** (`umbral_prob30`).
- Validación: BO AUC con 5 semillas y 50 iteraciones (reutilizada de FV4). Prueba: 202103–04 → 202106.
- Corte: 15 archivos de 8000 a 15000. El elegido no está documentado.
- Resultados: **[no encontrado]**.
- Reproducibilidad y tiempos **[declarado]**: VM de **256 GB de RAM**, pico de 117 GB, canaritos ~8 h. Tiene checkpoints.
- Aprovechable para C02:
  1. Validación de lag por calendario sobre `shift`, alternativa de menor costo al `match`.
  2. Eliminar CONTINUA con score alto según un modelo cruzado. El repo no muestra evidencia de mejora **[no encontrado]**.
- Relevancia para el pipeline de C02: baja — los requisitos declarados (pico de 117 GB de RAM, canaritos ~8 h) superan la laptop y el límite de 15 min por mes si se ejecutaran en producción; no reporta resultados.

#### nicobaranek/dmeyf-competencia-01 — commit 88ed240 (2026-10-12)
- URL: https://github.com/nicobaranek/dmeyf-competencia-01
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: faltan 2 `CURVA_JUNIO.csv` (2.6 MB). Se leyeron el código R (`codigo/`), el CSV de evidencia, `ESTADO_VALIDACION.json` y extractos del notebook. No hay README.
- Modelo y objetivo: LightGBM binario BAJA+1 ∪ BAJA+2 (`final.R:17`). Hiperparámetros de la BO: 1907 iter, 77 hojas, hessian 2.837 (`preparacion.R:11-13`).
- Features **[código]**, `motor.R:101-108`: originales + lag1/lag2 + delta **por calendario exacto**: `match(paste(id, periodo−l))`, con el comentario "no confundo una ausencia mensual con lag1".
  - El final excluye `Visa/Master_fultimo_cierre` y sus lags (`final.R:8-9`). Esa ablación está en `evidencia/SIN_CIERRES_*`.
  - Experimentos en la evidencia: `rank_cero` (`motor.R:37-39`), tend3 y vinculación.
- Monetarias y drift: `ccajas_depositos` 202105 → NA, con auditoría de ceros (`motor.R:71-73`). El ranking total se probó; en el CSV queda +8.8 a 9000 envíos pero −1.1 a 5000.
- **Pseudo-etiquetas** **[código]**, `motor.R:255-266` y `motor_integral.R:56-75`: un "docente" de 10 semillas etiqueta los meses sin clase (en el backtest 202105/06, en producción **202107/08**) con la regla top-k = 10500 y se agregan al train.
  - En junio sumó **+16.5 a +20.9 M a 9000 envíos** (`evidencia/ARTIFICIALES_RANK_H/COMPARACION_RECETAS.csv`) pero **no se adoptó** en el final (`SW$artificiales_* = FALSE`).
  - En el backtest, 202106 (mes de evaluación) también recibe pseudo-etiquetas (esquema transductivo).
- Validación: BO mlrMBO con 12 evaluaciones (4 iniciales). Objetivo: **ganancia a K = 11500 en 202106**, train 202103–04 (`configuracion.R:2-12`, `motor.R:188-193`).
- Corte **[código + declarado]**: **10375**, por la meseta ±250 en junio y el ensamble (`cortes.R:15`, `evidencia/CIERRE_CORTES_SINCIERRES_V1/COMPARACION_CORTES.csv`), contrastado con el público.
- Semillas: 10, promedio de probabilidades. Compara promedio de prob vs de "raw" (`motor.R:268-286`).
- Resultados **[declarado]** `ESTADO_VALIDACION.json`: público **106.40** con K = 10375. Réplica desde el crudo "SHA256 exacto".
- Reproducibilidad: hashes del crudo y de la entrega, versiones exigidas con `stopifnot`, firmas de caché, escritura atómica.
- Aprovechable para C02:
  1. **Pseudo-etiquetas para meses con target incompleto**. Aplicable a 201911/201912: etiquetar con un docente entrenado hasta 201910 y medir con la regla del lote.
  2. Lags por calendario con `match` (`motor.R:101-108`).
  3. Elegir el corte por la meseta ±250 en lugar del pico.
- Relevancia para el pipeline de C02: alta — pseudo-etiquetas para meses sin etiqueta completa con medición cuantitativa (+16.5 a +20.9 M) y lags por calendario.

#### tomasroel/DMeyf_Competencias — commit ab5eb70 (2026-10-11)
- URL: https://github.com/tomasroel/DMeyf_Competencias
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: notebook R **sin outputs**, README y `BO_log.txt` (20 evaluaciones). No faltan archivos.
- Modelo y objetivo: plantilla de la cátedra extendida. LightGBM binario BAJA+1 ∪ BAJA+2 con undersampling 0.1 **[código]**.
- Features **[código]**:
  - ~40 variables `new_*` (sumas por producto y canal, `canales_usados`, `cant_anclas`, deuda/payroll).
  - lag1/lag2 y deltas de **todas** las variables, **por calendario** con un `merge` por `(cliente, periodo + k)`.
  - tend3/avg3 de las variables importantes y "ranking cero fijo" de todo.
  - `PARAM$rotas` (variable → meses a NA) se aplica **antes** del FE para que el valor anómalo no se propague a los lags.
- Limpieza: outliers = CONTINUA con prob > 0.5 según un detector cruzado (mismo esquema que kevinlpagnotta/DMEyF---Primera-Competencia).
- Validación: BO AUC con 20 evaluaciones, 70/30 sobre 202103+04. Testing de 10 semillas en 202106.
- Corte: m12500 **[declarado]**. No hay curva documentada.
- Semillas: 50, promedio.
- Resultados: **[no encontrado]**.
- Tiempos **[declarado]**: 7.5 h en una VM de 8 vCPU y 62 GB.
- Aprovechable para C02:
  1. Diccionario `rotas` (variable → meses) aplicado antes de los lags; mecanismo para declarar las columnas en cero de 202006.
  2. Lags por calendario con un `merge` sobre `periodo + k`.
- Relevancia para el pipeline de C02: baja — diccionario de columnas por mes aplicado antes de los lags; sin resultados y la BO usa partición 70/30 sin validación temporal.

#### tomasfarias-hub/DMEYF — commit c1ef1a9 (2026-10-11)
- URL: https://github.com/tomasfarias-hub/DMEYF
- Licencia: sin licencia ⇒ todos los derechos reservados; no copiar código, solo ideas.
- Cobertura: los archivos están en la raíz **sin extensión** (`notebook` = ipynb con outputs, `reproducibilidad`, `resultados`, `Requirements`, `dataset`). No coincide con la estructura que describe el README. No faltan archivos.
- Modelo y objetivo: LightGBM binario **solo BAJA+2** **[código + declarado]**.
- Features: `tc_consumo_total` + delta1 de 17 variables con `groupby.shift` (**por fila**). Son 170 variables.
- Validación: Optuna (15 trials, **sin semilla en el sampler**) con `StratifiedShuffleSplit` 5×30 % sobre 202103–04. Métrica: ganancia con prob ≥ 0.025, escalada por 1/0.3. Test 202106.
- Corte **[declarado]**: la proporción de cartera óptima de la curva de junio **suavizada** (ventana 500), trasladada a agosto: 11972 = 7.27 %.
- Semillas: 5 en el final, max_bin 255.
- Resultados **[declarado]**: junio 356 M. No reporta el público.
- Extra: análisis de hojas, probabilidad empírica vs predicha (calibración).
- Reproducibilidad: solo Colab y versiones sin completar.
- Aprovechable para C02: el umbral de equilibrio 0.025 como referencia para la columna `enviar` (mismo costo/beneficio en C02, a verificar).
- Relevancia para el pipeline de C02: baja — lags por fila sobre 17 variables y BO sin validación temporal; solo el umbral de equilibrio y el corte por proporción de cartera son aplicables.

---

### Lote D — enfoques relacionados con el pipeline de C02

1. **Pseudo-etiquetas + lags por calendario** — problema de C02: meses 201911/201912 sin target completo (usarlos con pseudo-etiquetas de un modelo entrenado hasta 201910 en vez de descartarlos).
   - nicobaranek/dmeyf-competencia-01 (88ed240), `motor.R:101-108`, `motor.R:255-266`, `motor_integral.R:56-75`: un docente etiqueta los meses incompletos (top-k) y las etiquetas se suman al train; +16 a +21 M en el backtest de junio. En ese backtest también se pseudo-etiqueta el mes de evaluación; la validación en C02 requiere excluirlo. El repo usa hashes del crudo y de la entrega, aplicables al reporte.
2. **Protocolo de decisión estadístico** — problema de C02: decidir **lags por fila vs por calendario** y qué columnas anular en 202006 con datos 2019.
   - ezequielabregu/DMEyF_competencia_1 (bc9f2a9), `05_variables.ipynb` celdas ca3f5d88/552b2d67; `04_drift.ipynb`: cada bloque de variables o limpieza se adopta con 10 semillas, meseta suavizada (ventana 501) y Wilcoxon pareado; identifica columnas con valores anómalos en un mes y las excluye. Público declarado: 110.25.
3. **Transformación por mes y corte** — problemas de C02: inflación sin IPC, alarma ante columnas en cero en producción y adaptación del corte al tamaño de cada `input/<yyyymm>.csv`.
   - agustinlovrich/dmeyf-primera-competencia (6ef281f), `run_rank_prestamos_junbo_hist.R:241-268`: ranking con signo por mes en reemplazo de los montos crudos, lags y deltas por calendario exacto; corte por la media entre semillas. Público declarado: 107.44.
   - montagnaflor/DMEyF-Competencia-01 (c9a71f6), celdas c12-c13: PSI train vs mes a predecir con bin de nulos; c37: corte como **proporción de la cartera**.

Lags por fila con un mes faltante en la carga: en la-laguinge/dmeyf-2026-competencia-01 (715cddf), 202108 recibe junio como "lag1" porque 202107 no está en la carga (`03_entrenar_y_predecir_M4_final.py:53`). Clasificación del lote: lags por calendario en agustinlovrich, nicobaranek, kevinlpagnotta y tomasroel; por fila en montagnaflor, ezequielabregu, marcostrigueros99, germandasr y tomasfarias-hub.

### Lote E — fichas

Método: solo lectura (README, código R/py, notebooks .ipynb leídos como JSON; no se ejecutó nada).
Convenciones: **[declarado]** = README/comentarios/outputs guardados; **[código]** = verificado leyendo código; **[no encontrado]**.
"celda N" = índice 0-based de celda en el .ipynb. Ningún repo del lote tiene archivo LICENSE ⇒ **sin licencia: todos los derechos reservados; solo ideas** (vale para las 19 fichas). Ningún archivo del lote supera 1 MB (máx. `bayesiana.RDATA` 764 KB), así que no hubo omisiones por tamaño.
Ganancia: casi todos usan +1.072.500 / −27.500 (ratio 39). Ani-victoria usa 780.000/−20.000 y mbellesi 273.000/−7.000: mismo ratio 39 ⇒ mismo orden y mismo corte óptimo. iespinozah usa 117.500/−27.500, pero con K fijo (10.000) la suma es monótona en aciertos ⇒ elige el mismo modelo.

---

#### Ani-victoria/dmeyf2026-competencia01 — commit 21e0aaf (2026-10-10)
- https://github.com/Ani-victoria/dmeyf2026-competencia01 · sin licencia · Cobertura: 3 notebooks R + BO_log + README completos; el último commit **borró `entrega_final/`** (el CSV entregado no está).
- Modelo: LightGBM binario, `clase01` = BAJA+1+BAJA+2; ganancia en BAJA+2 con 780.000/−20.000 **[código]**, 2_modelo celda ~23.
- Features: lag1/delta1 de todo + lag2/delta2 **solo para 78 variables "que no mienten en agosto"** elegidas con un diagnóstico de cuánto se aparta agosto de un mes normal (notebook de diagnóstico no incluido) **[declarado + código]**, celda 31. Lags **por fila** (`shift(..., by=numero_de_cliente)`) **[código]**, celda 29.
- Calendario: bandera `cobra_aguinaldo` (mes 6/12 y payroll/promedio(lag1,lag2) entre 1,3 y 2,0) y `mpayroll_sin_sac = mpayroll/1,5` **[código]**, celda 27; 60.151 clientes con la bandera en 202106 **[declarado, output guardado]**.
- Monetarias: 62 `rk_*` "rank cero fijo" por `foto_mes` (pos→(0,1], neg→[−1,0), 0→0) **[código]**, celda 33. Sin IPC.
- Validación/BO: mlrMBO 30 iter (el log llega a iter 44), train 202103–05 con 25% de CONTINUA, ganancia en 202106; mejor y=303,8 M (`BO_log.txt`) **[código]** **[declarado, output guardado]**.
- Corte: cantidad fija 11.000 ("el mejor en todos los modelos entre 9.500 y 14.000") **[declarado]**.
- Semillas: 20 + 20 bolsas, **cada bolsa con su propio 25% de CONTINUA** (undersampling distinto por semilla) **[código]**, celda ~35; promedio de 40.
- Resultados **[declarado]**: tabla de 16 experimentos en Public (6018 = 112,39; final 6019x40 = 110,47). Conclusiones declaradas: lag2 sobre todas las variables da menor ganancia (delta2 de agosto compara contra junio con aguinaldo); el rank por mes subió +2 M.
- Reproducibilidad: rutas GCP `~/buckets/b1`, ~1,5–2,5 h por notebook, semillas fijas, reanudable por bolsa.
- **Aprovechable C02**: bandera de aguinaldo y payroll sin SAC (201906 y 201912 están en el train de C02) (2_modelo celda 27); lag2 selectivo según diagnóstico de mes anómalo (celda 31); undersampling distinto por semilla (celda ~35).
- Relevancia para el pipeline de C02: alta — corrección de efectos de calendario (aguinaldo) aplicable a 201906/201912 y selección de lags según el mes a predecir; los lags son por fila.

#### ArielRojasV/PrediccionBajas_DMEyF — commit 9f30b84 (2026-10-11)
- https://github.com/ArielRojasV/PrediccionBajas_DMEyF · sin licencia · Cobertura: 3 notebooks (FE en DuckDB/SQL en Colab, BO y modelo final en R).
- Modelo: LightGBM binario BAJA+1+2, sin undersampling.
- Features: SQL `lag(x,k) over (partition by cliente order by foto_mes)` para ~30 variables elegidas manualmente (**por fila**) + `mpayroll/avg(mpayroll del mes)`, flag de payroll > 95% del máximo del mes **[código]**, FE celda 7.
- Literales en el código **[código]**: el filtro de meses usa `train_final <- c(202103, 202104, 2021505, 202106)` (Modelo_Final celda 22); con el literal `2021505`, 202105 no queda incluido en el entrenamiento. La exclusión usa `"ccajas_depositos "` con un espacio final; con ese literal, la columna `ccajas_depositos` no se excluye.
- BO: 12 iteraciones, train 202103–04 con 70/30, AUC; corte mirando la curva de 202106 **[declarado + código]**.
- Corte: muestra 12.500 y exporta `exp_final_115.csv` = 11.500 **[código]**, celda 40. Semillas: 5 promediadas.
- Resultados: **[no encontrado]**. Reproducibilidad: rutas de Drive/Colab.
- **Aprovechable C02**: monto relativo a la media del mes como deflactor de bajo costo (FE celda 7).
- Relevancia para el pipeline de C02: baja — lags por fila sobre ~30 variables; aplicable solo la normalización por media del mes.

#### JFormoso/competencia1-dmeyf — commit 90740d0 (2026-10-12)
- https://github.com/JFormoso/competencia1-dmeyf · sin licencia · Cobertura: 3 scripts R; **falta `tendencia.R`**, que `optimizacion-hiperparam.R:182` carga con `source`; BO cortada (25/30) y BO_log no incluido **[declarado]**.
- Modelo: LightGBM binario BAJA+1+2, sin undersampling, lr 0,005 e hiperparámetros de la cátedra.
- Features: **lags/deltas 1–2 por calendario** con *update join* sobre `periodo0+k` (`prediccion-agosto-v2.R:207-225`, `optimizacion-hiperparam.R:157-178`) + `TendenciaYmuchomas` (ventana 3, por fila) + `_zero` + rank cero fijo `dense` por mes.
- Orden de operaciones en la BO **[código]**: el filtro `meses_usados <- c(202103,202104,202106)` se aplica **antes** de calcular los lags (`optimizacion-hiperparam.R:143`); con ese orden, todos los lags de 202106 quedan en NA. Además valida 70/30 dentro de 03–04 (no out-of-time).
- Corte: 11.750 fijo. Semillas: 20 previstas, solo 2 corridas (las que entraron en la entrega) **[declarado]**.
- Resultados: **[no encontrado]**. Reproducibilidad: `here::here()`, `deterministic=TRUE`, avance reanudable con "firma" **[código]**.
- **Aprovechable C02**: patrón de lag por calendario con join (`prediccion-agosto-v2.R:207-225`).
- Relevancia para el pipeline de C02: baja — implementación de lag por calendario con join; la BO calcula los lags después de filtrar meses y valida dentro de los meses de train.

#### MarcosFedericoRios/primeracompetenciadmeyf — commit a29db2f (2026-10-11)
- https://github.com/MarcosFedericoRios/primeracompetenciadmeyf · sin licencia · Cobertura: 2 notebooks R de Colab, con outputs.
- Modelo: LightGBM binario BAJA+1+2; BO con 20% de CONTINUA y `min_data_in_leaf` normalizado al final.
- Features: **solo deltas 1–2** (`x − shift(x)` sobre todo el dataset ordenado, enmascarando cuando cambia el cliente: **por fila**) **[código]**, celda 16. Sin rank ni IPC.
- BO: mlrMBO 20 iter, 5 hiperparámetros (lr, leaves, ff, mdil, iters), AUC con CV de 5 folds sobre 202103–06 (y≈0,938) **[código]** **[declarado, output guardado]**.
- Corte: genera 11.500–12.500 para el bot; el final no se declara **[código]**. Semillas: 20 promediadas (~17 min cada una) **[declarado, output guardado]**.
- **Aprovechable C02**: sin elementos adicionales a los de otras fichas.
- Relevancia para el pipeline de C02: baja — solo deltas por fila y CV dentro de los meses de train.

#### SerenaDituro/Competencia1_DMEyF_2026 — commit 31d13c4 (2026-10-11)
- https://github.com/SerenaDituro/Competencia1_DMEyF_2026 · sin licencia · Cobertura: notebook de BO + notebook de entrega + logs de BO; el último commit borró `HTC1_E012/`, pero sus logs quedan en `exp/`.
- Modelo: LightGBM binario BAJA+1+2, sin undersampling.
- Features: lag/delta 1–2 con `shift` global + máscara `mismo cliente & periodo0 diff == k` ⇒ **por calendario** **[código]**, entrega celdas 18 y 20; después rank cero fijo por mes de **todas** las columnas (incluidos lags y deltas) [celda 22].
- Drift: `ccajas_depositos` en NA en 202105. Sin IPC (lo reemplaza el rank).
- BO: mlrMBO, **k-fold 5 estratificado sobre 202103–05, AUC**, 16 evaluaciones (12 iniciales + 4), ~50–110 min cada una; mejor AUC 0,9434 (2891 árboles, 1056 hojas) **[declarado, output guardado]**.
- Corte: test 202106 (train 03–04, 5 semillas) ⇒ máximo en 11.000 **[declarado, output guardado]**, celda ~27; se entregaron 12.000 **[declarado]**.
- Semillas: 20 primos fijos, promedio. Reproducibilidad: rutas `~/buckets/b1`, `.fst` en cache.
- **Aprovechable C02**: lag por calendario con shift + máscara (celdas 18 y 20).
- Relevancia para el pipeline de C02: media — lag por calendario con shift + máscara y rank por mes; la BO usa k-fold dentro de los meses de train.

#### aaav13/Competencia_01_DMEyF — commit f18361a (2026-10-11)
- https://github.com/aaav13/Competencia_01_DMEyF · sin licencia · Cobertura: 3 notebooks (DuckDB FE, Optuna, entrenamiento) + CSV.
- Modelo: `LGBMClassifier` (500 árboles, lr 0,09, depth 7), target BAJA+1+2.
- Meses de entrenamiento y métrica **[código]**, src01 celda 1: entrena con 202103–**202107**; 202107 tiene la clase casi toda en NA (solo BAJA+1), por lo que esas filas sin etiqueta entran como negativos. Optuna usa CV estratificado por AUC; la ganancia se calcula como `tp * (ganancia_acierto - costo_estimulo) - fp * costo_estimulo` con `ganancia_acierto=1_072_500` (`Model_Creation.ipynb`, función `calcular_ganancia`) **[código]**: cada acierto suma 1.045.000, 27.500 menos que la ganancia neta por acierto del material del curso (ver `GANANCIA.md`).
- Features: ratios intra-mes (uso de límite de tarjeta, share digital, cheques rechazados). Sin lags, sin rank.
- Corte: 9.300 fijo. Semillas: una (42). Resultados: **[no encontrado]**. Rutas absolutas de la máquina del autor (Windows).
- **Aprovechable C02**: sin elementos adicionales a los de otras fichas.
- Relevancia para el pipeline de C02: ninguna — sin lags ni tratamiento por mes; el train incluye un mes sin etiqueta tratado como negativo.

#### gromadzyn/dmeyfCompetencia1 — commit ac82cca (2026-10-12)
- https://github.com/gromadzyn/dmeyfCompetencia1 · sin licencia · Cobertura: un notebook de Colab con outputs.
- Modelo: LightGBM binario BAJA+1+2, sin undersampling, hiperparámetros de la cátedra (lr 0,005, ff 0,5, bynode 0,2).
- Features: lag/delta 1–2 con shift + máscara de cliente y `mes − mes_anterior == orden` ⇒ **por calendario** **[código]**, celda 37; rank cero fijo de todo por mes (760 features).
- BO: mlrMBO 30 iter, train 202103–04 → valida 202106, AUC calculado en el notebook **[código]**, celda 46.
- Ensamble: **las 10 mejores configuraciones de la BO × una semilla cada una** **[código]**, celda 51 y siguientes; corte 11.000 (genera 10.000–12.000) **[declarado]**.
- Resultados: **[no encontrado]**. Reproducibilidad: Drive/Colab, semillas fijas.
- **Aprovechable C02**: ensamble de top-K configuraciones como "segundo modelo" de bajo costo (celda 51).
- Relevancia para el pipeline de C02: baja — lag por calendario con máscara y ensamble de configuraciones; sin resultados reportados.

#### iespinozahDM/primeracompetencia-dmeyf — commit 9f73fa5 (2026-10-11)
- https://github.com/iespinozahDM/primeracompetencia-dmeyf · sin licencia · Cobertura: un notebook R, ejecutado solo hasta el paso 3 (no hay outputs de BO ni de producción).
- Modelo: LightGBM binario con **target solo BAJA+2**; borra préstamos personales.
- Features: lag1/delta1 por fila (`shift by cliente`) **[código]**, celda 2. Lag2 sobre todo: OOM con 60 GB **[declarado]**.
- BO: mlrMBO 20 LHS + 30 EI sobre iters/leaves/hessian, train 03–04 → 202106, ganancia en top 10.000 con **117.500** por acierto (valor distinto de 1.072.500; con K fijo no cambia la elección) **[código]**, celda 3.
- Corte: 10.000 fijo. Semillas: 5. Resultados **[declarado]**: 95,78 M (EXP-02) en el Public.
- **Aprovechable C02**: dato de memoria: lag2 de todas las variables con 100% de los datos supera 60 GB.
- Relevancia para el pipeline de C02: baja — lags por fila; aplicable solo el dato de memoria de lag2.

#### jlazcanosimoniello/DMEyF-2026 — commit 4ffdbb8 (2026-10-11)
- https://github.com/jlazcanosimoniello/DMEyF-2026 · sin licencia · Cobertura: 2 scripts R + `entrega_05.csv`; README vacío.
- Modelo: LightGBM binario BAJA+1+2, una semilla; BO mlr3mbo 20 evaluaciones, métrica `average_precision`, undersampling 0,1 sin normalizar `min_data_in_leaf`.
- Definiciones en el código **[código]**: `delta2 = lag1 − lag2` (`1-Preprocesamiento.R:94-95`), es decir, la diferencia entre t−1 y t−2; `numero_de_cliente` y `foto_mes` quedan como features; **el corte se elige en 202106 con el modelo final entrenado incluyendo 202106** (in-sample, `...Bayen.R:361-385`). Lags por fila.
- Corte: argmax en validación. Resultados: **[no encontrado]**. Rutas absolutas de la máquina del autor.
- **Aprovechable C02**: ninguno; documenta un caso de corte elegido in-sample que el pipeline de C02 no replica.
- Relevancia para el pipeline de C02: ninguna — lags por fila, IDs y mes como features y corte elegido sobre un mes incluido en el entrenamiento.

#### kformoso/Competencia1 — commit 56a820f (2026-10-11)
- https://github.com/kformoso/Competencia1 · sin licencia · Cobertura: `KF16.R` + CSV entregado (12.000 filas).
- Modelo: **LightGBM multiclass (3 clases)**, ranking por P(BAJA+1)+P(BAJA+2) (`KF16.R:62, 411`); 500 rondas, lr 0,027, 31 hojas, mdil 200.
- Features: lag/delta 1–2 con shift + máscara por cliente y periodo ⇒ **por calendario** (`KF16.R:320-340`); `TendenciaYmuchomas` en Rcpp (tend3, avg3, por fila); `ccajas_depositos` NA (forzado + autodetección "todo cero en el mes"). `numero_de_cliente` y `foto_mes` entran como features (`KF16.R:374`).
- Validación: **ninguna** (hiperparámetros fijados manualmente, sin BO, sin curva) **[código]**.
- Semillas: 60 primos desde 100003, cada una con su propio 20% de CONTINUA; reanudable con "firma" de parámetros **[código]**.
- Corte: 12.000 fijo. Resultados: **[no encontrado]**.
- **Aprovechable C02**: multiclase como segunda estrategia (diversidad); autodetección de mes "todo cero" para una variable.
- Relevancia para el pipeline de C02: baja — multiclase como estrategia alternativa y detección de mes todo cero; sin validación.

#### laupasq1967/Entrega-final-DMEyF — commit 395462d (2026-10-10)
- https://github.com/laupasq1967/Entrega-final-DMEyF · sin licencia · Cobertura: notebook final + 16 notebooks de "procesamiento previo" + logs (BO_log, PARAM, RDATA, listas de canaritos).
- Modelo: **2 modelos LightGBM** (A'plus: 576 variables elegidas con canaritos + `gen_1`; B: 760 variables completas), target BAJA+2, lr 0,02, 600 iter, scale_pos_weight 0,5, max_bin 31.
- Features: lag/delta 1–2 por fila (`shift by cliente`, celda 8); rank cero fijo por mes **escalado 1–100** (celda 10); históricas de 3 meses (prom, máx, mín, ratios, tendencia); `gen_1 = ctrx_quarter + cpayroll_trx_min3` hallada con un **algoritmo genético** (AUC univariado). Excluye `*_fultimo_cierre` y `Visa_mpagado` por tener un mes anómalo.
- Selección: canaritos asesinos (20% de ruido, corte en media + 2 desvíos), intersección de dos semillas **[código]**, z_canaritos_*.
- BO: mlrMBO, 11 hiperparámetros, 100 iter, 5 folds, solo 202104 con 10% de CONTINUA, ganancia; luego **re-evalúa el top 3/5 con 10 semillas en 202106** y elige el trial 2 (no el 1) **[declarado + código]**, notebooks z601; grillas de lr×spw y de min_data_in_leaf.
- Ensamble: **promedio de percentiles** `frank(prob)/n` por semilla → por modelo → `(rA+rB)/2` **[código]**, celda 18. 100 semillas por modelo (~11 h).
- Corte: 10.600 fijo. Resultados **[declarado]**: Public **119,3775**; seed 585581 reproducida idéntica.
- **Aprovechable C02**: ensamble de 2 modelos por rank-percentil (≥2 modelos con recomendación única) (celda 18); re-evaluar el top-K de la BO con varias semillas antes de elegir.
- Relevancia para el pipeline de C02: alta — combinación de 2 modelos por promedio de percentiles (requisito de ≥2 modelos con una recomendación) y re-evaluación multi-semilla del top-K; lags por fila y tiempo declarado de ~11 h.

#### lsaldeco/Entrega_Competencia01 — commit 4bfbb08 (2026-10-12)
- https://github.com/lsaldeco/Entrega_Competencia01 · sin licencia · Cobertura: 7 scripts .py completos; `07_cortes_media.py` trae `CORTE = 1000` (placeholder; el corte real salió del bot) **[código]**.
- Modelo: LightGBM binario con **target solo BAJA+2**.
- Target: DuckDB con **grilla clientes × periodos (CROSS JOIN)** + LEAD, y NULL donde el futuro no se conoce (`01_target.py:20-45`).
- Imputación con datos de t+1 **[código]**: imputa NaN con el promedio del mes **previo y el siguiente** (`02_limpieza_fe.py:37-41`, `shift(-1)`); en producción el mes siguiente no está disponible. Lags por fila (`groupby.shift`); rank pct por mes donde **NaN pasa a 0**; flags `_zero`.
- BO: Optuna 60 trials, `lgb.cv` con StratifiedShuffleSplit sobre 03–04 (no out-of-time), métrica = ganancia con umbral 0,025; validación en 202106 con 20 semillas y curvas.
- Producción: 70 semillas, train 03–06. Resultados: **[no encontrado]**.
- **Aprovechable C02**: la grilla densa cliente×mes resuelve tanto los lags por calendario como el target incompleto (201911/201912 ⇒ NULL, no CONTINUA) (`01_target.py:20-45`).
- Relevancia para el pipeline de C02: baja — la grilla cliente×mes con NULL en meses sin etiqueta es aplicable; la imputación usa t+1 y los lags son por fila.

#### lvergini/dmeyf2026-competencia1 — commit 60033c0 (2026-10-11)
- https://github.com/lvergini/dmeyf2026-competencia1 · sin licencia · Cobertura: pipeline R modular completo (`00_pipeline.R`, `R/*.R`, `renv.lock`, BO_log, semillas, evaluación en junio con Rmd).
- Modelo: LightGBM binario BAJA+1+2, sin undersampling, lr 0,005 e hiperparámetros de la cátedra.
- Features (entrega FE026): **lags/deltas 1–2 por mes calendario** con join en `periodo+k` (`R/datasets.R:52-65`), después rank cero fijo de todo por mes (`R/datasets.R:67-85`). Nota: la librería experimental `evaluacion_junio/R/fe.R:98` calcula lags **por fila**.
- Drift (librería experimental, no usada en FE026): **`fe_anti_imputacion`** detecta variable×mes con todos los registros en 0 cuando hay datos en otros meses y los pasa a NA antes de los lags (`evaluacion_junio/R/fe.R:200`); `fe_payroll_binaria` porque en meses de aguinaldo hay 2 acreditaciones (`fe.R:450`); cocientes de negocio "que no identifican el mes" (`fe.R:421`).
- BO: mlr3mbo kriging+EI, train 03–04 → **valida 202106 dejando 202105 como hueco** para imitar el gap de producción; AUC; 12 evaluaciones (mejor 0,92064).
- Corte: **curva suavizada ±500 envíos** sobre 20 semillas en 202106; 11.750 (`evaluacion_junio/curva_por_corte.R:22`).
- Semillas: primos de 6 cifras, 4 sublistas paralelas; **descarta semillas con predicciones idénticas** (`02_prediccion_final.R:35`). ~25 min por semilla; reanudable.
- Resultados: **[no encontrado]**.
- **Aprovechable C02**: `fe_anti_imputacion` aplicable a 202006 (`fe.R:200`); validación con gap (`README`/`R/parametros.R`); corte suavizado; descarte de semillas duplicadas.
- Relevancia para el pipeline de C02: alta — detección automática de variable×mes en cero con paso a NA antes de los lags (202006), lags por calendario y validación con gap de producción.

#### mbellesi01/dmeyf2026-Competencia-1 — commit 407407d (2026-10-11)
- https://github.com/mbellesi01/dmeyf2026-Competencia-1 · sin licencia · Cobertura: un notebook Python de Colab con outputs; el blend final se hizo fuera del notebook **[declarado]**.
- Modelo: LightGBM binario BAJA+1+2; hiperparámetros "de la cátedra para 6 meses" **[declarado]**. `MESES_TRAIN` incluye 202101–02, que no están en el dataset **[código]**, celda 3.
- Features: lags 1–3, delta1/3, delta relativo, enmascarados por cliente (**por fila**) [celda 6]; `tend3`/`avg3` con **Numba** [celda 6]; rank cero fijo; montos de tarjeta 0→NaN; `flag_abril_2021` [celda 5].
- Selección y validación en el mismo mes **[código]**: la selección Top-300 por gain se entrena **en 202106** y la BO valida en 202106 (celdas 7 y 8). La métrica de la BO cuenta BAJA+1+2 como acierto.
- BO: Optuna 30 trials, early stopping sobre 202106 (315,28 M) **[declarado, output guardado]**.
- Ensamble: rank-consenso 50/50 entre 5 semillas y 20 semillas; corte 11.000 **[declarado]**.
- **Aprovechable C02**: `fhist_numba` (tendencia en Python compilada con Numba) (celda 6).
- Relevancia para el pipeline de C02: baja — lags por fila; selección de variables y validación de la BO en el mismo mes (202106); aplicable solo la tendencia con Numba.

#### mmfiora/dmeyf2026-competencia-01 — commit 631d8a3 (2026-10-12)
- https://github.com/mmfiora/dmeyf2026-competencia-01 · sin licencia · Cobertura: notebook final + versión ejecutada + BO ejecutada + `bo_resultados.csv` + `requirements.txt` + CSV entregado.
- Modelo: LightGBM binario BAJA+1+2, sin undersampling; ganancia 1.072.500/−27.500.
- Features: **lags/deltas 1–2 por calendario en pandas** con merge en `(cliente, periodo0+k)` (`competencia_FINAL.ipynb` celda 10), calculados **después** del rank.
- Monetarias/drift: rank mensual de las 41 `m*` (cero fijo si hay negativos); **elimina las 10 variables con mayor KS entre 202103–05 y 202108** + préstamos (celda 2; el cálculo del KS **[no encontrado]** en el repo).
- BO: Optuna TPE 30 trials, AUC, train 03–05 → 202106; trial 27: 1050 iter, 171 hojas, hessian 7,29.
- Corte: 13.000 elegido en el pseudo-Kaggle (12.500–14.500). Semillas: 20 en 2 tandas de `Dataset` (el binning depende de la primera semilla) **[declarado]**.
- Resultados **[declarado, output guardado]**: Public 105,0225; reproducción **byte a byte** (MD5) en 2 h 24 min.
- **Aprovechable C02**: función de lags por calendario en pandas (celda 10); filtro de drift por KS contra el mes a predecir (celda 2).
- Relevancia para el pipeline de C02: alta — lags por calendario en pandas y filtro de drift contra el mes a predecir.

#### nicolasmatayoshi-code/dmeyf2026-competencia1-entrega — commit 37d68bc (2026-10-11)
- https://github.com/nicolasmatayoshi-code/dmeyf2026-competencia1-entrega · sin licencia · Cobertura: 2 scripts R + logs originales + CSV con MD5/SHA256.
- Modelo: LightGBM binario BAJA+1+2, valores crudos (sin rank), 254 hojas, 2000 árboles, sin BO **[declarado + código]**.
- Features: **lag por calendario con `match(clave − k, clave)`**, donde `clave = cliente*1e5 + periodo` (`02_modelo_final/modelo_final.R:135-140`). 760 columnas.
- Elección de árboles: un modelo de 4000 árboles evaluado en 1000…4000 en 202106 (train 03–04), con la **meseta 9.000–14.000** ⇒ 2000 = centro de la meseta, no el pico (`log_original/pseudo_profundo_por_arboles.csv`).
- Corte: 10.000 fijo, elegido manualmente. Semillas: 50 primos; reanudable; 12–15 min por modelo.
- Resultados: **[no encontrado]**. Verificación: 2 modelos reproducidos con el mismo MD5 **[declarado]**.
- **Aprovechable C02**: lag por calendario en una línea (`modelo_final.R:139`); elegir num_iterations con un solo modelo largo evaluado en varios cortes de iteración.
- Relevancia para el pipeline de C02: media — lag por calendario con `match` y elección de iteraciones por meseta; sin resultados reportados.

#### pablogarciaparisi/dmeyf2026-competencia1 — commit bd3a731 (2026-10-11)
- https://github.com/pablogarciaparisi/dmeyf2026-competencia1 · sin licencia · Cobertura: 3 notebooks R (SAFE P2/P3 HNC, E012, meta-ensambles) sin outputs de corrida; README mínimo.
- Modelos: SAFE P2 (train mayo+junio) y P3 (03–06), E012 (**solo junio** como train, `numero_de_cliente`/`foto_mes` como features).
- Features: por mes, `match` contra el mes `m−1` y `m−2` ⇒ **por calendario** (`1-C01_SAFE...` celda 6); signed rank por mes de current/lag/delta.
- **HNC (hard-negative cleaning)**: OOF de 5 folds agrupados por cliente sobre mayo+junio; se retira el 5% de CONTINUA con mayor score OOF **[declarado + código]**.
- BO: 10 LHS + 10 EI, AUC, 03–04 → 06; "GainBand" = media de la ganancia en 11.500–13.500.
- Meta-ensamble: **promedio de rankings** P2 50% + E012 50%, TOP 12.500 (`3-...` celda 2).
- Infraestructura: checkpoints atómicos con MD5 y respaldo en GCS, firmas de configuración.
- Resultados: **[no encontrado]**.
- **Aprovechable C02**: lag mensual con `match` (celda 6); limpieza de negativos difíciles como estrategia alternativa; meta-ensamble por rank.
- Relevancia para el pipeline de C02: media — lag por calendario, limpieza de negativos difíciles y meta-ensamble por rank; sin resultados reportados.

#### patriciojarmoluk/dmeyf2026-competencia01 — commit 4b1e2fa (2026-10-11)
- https://github.com/patriciojarmoluk/dmeyf2026-competencia01 · sin licencia · Cobertura: un script R + README.
- Modelo: LightGBM binario BAJA+1+2, sin undersampling; préstamos fuera de la BO y reincorporados en producción.
- Features: rank cero fijo de las 152 variables por mes y **después** lag/delta 1–2 **por calendario** con `match(clave−1, clave)` (`competencia01_final.R:292-306`) + tend3/avg3; el modelo no ve pesos (1.064 variables).
- BO: mlr3mbo, solo las 12 evaluaciones del diseño inicial, 03–04 → 06, AUC 0,91854.
- Corte: 11.250 = medio de la meseta del Public (11.000–11.500) y de junio (10.500–14.000) **[declarado]**. Semillas: 30 de 50 primos sorteados.
- Reproducibilidad: `deterministic=TRUE`, `force_row_wise`, "no depende de los núcleos" **[declarado]**; ~9 h; reanudable.
- **Aprovechable C02**: lag por calendario con `match` sobre la versión rankeada (`competencia01_final.R:292-306`).
- Relevancia para el pipeline de C02: media — lag por calendario sobre variables rankeadas por mes; tiempo declarado ~9 h.

#### micaelarr/primeracompetencia — commit ebe30f0 (2026-10-10)
- https://github.com/micaelarr/primeracompetencia · sin licencia · Cobertura: notebook final (Python + DuckDB) + estudios de Optuna (.db) + notebooks de BO con outputs. El README cita las carpetas `01_prediccion_final/` y `02_optimizacion_bayesiana/`, pero el repo trae `prediccion_final/` y `optimizacion_bayesiana/`, y el nombre del CSV final no coincide **[código]**.
- Modelo: LightGBM binario BAJA+1+2, sin undersampling (con `assert`); **ensamble de 6 configuraciones × 2 semillas** (top-6 de Optuna).
- Features: **SQL `LAG()` con chequeo de distancia en periodos == k** (`churn_pipeline_final` celda 18) para 15 variables + delta1 de todas; historia de 3 meses consecutivos (m3, s3, mn3, mx3, cv3, xvsm3, racha3) sobre 25 variables (celda ~33); ratios; KMeans k=5 ajustado solo en train.
- Monetarias/drift: **deflactación por IPC INDEC** con índice acumulado (celda 7); límites de tarjeta en nominal; **PSI train vs 202108** que excluye >0,25 y propaga la exclusión a lags/deltas (celdas 26–27); excluye payroll por aguinaldo.
- Pesos: **decay por mes 0,8^(meses hasta el último mes de train)** (`pesos_df`, celda 32): +3,4 BAJA+2 **[declarado]**.
- BO: Optuna TPE (seed 17), 60 trials, objetivo = **máximo de la curva de ganancia suavizada (ventana 401) en 202106 con 3 semillas**, warm start desde estudios previos **[declarado + .db]**.
- Corte: curva suavizada (óptimo 12.720 en junio); se entregó 11.500 por el Public. Análisis explícito del **gap** 1 vs 2 meses (celda ~49) **[código]**.
- Resultados **[declarado]**: tabla de descartes (canaritos −24 a −36 BAJA+2, hiperparámetros de la cátedra −21, RF −40). Tiempo ~40 min de entrenamiento + ETL.
- **Aprovechable C02**: usa Python + DuckDB + LightGBM, el mismo stack del pipeline de C02; lags SQL por calendario (celda 18), IPC (celda 7), PSI con propagación (celda 27), decay (celda 32), objetivo de BO por ganancia suavizada multi-semilla, ensamble de configuraciones.
- Relevancia para el pipeline de C02: alta — lags SQL por calendario, PSI con propagación a lags, pesos por recencia y análisis del gap de 2 meses, en el mismo stack del pipeline.

---

### Tabla resumen — Lote E

| repo | modelo | lags | monetarias | validación | corte | semillas | resultado declarado | relevancia C02 |
|---|---|---|---|---|---|---|---|---|
| Ani-victoria | LGBM bin B1+B2, 25% CONT por bolsa | fila; lag2 selectivo (78) | rank cero fijo 62 + aguinaldo | BO ganancia 03–05→06 | 11.000 fijo | 40 (20+20) | Public 110,47 (máx. 112,39) | alta |
| ArielRojasV | LGBM bin | fila (SQL lag) | /media mes | BO AUC 70/30 | 11.500 | 5 | — | baja |
| JFormoso | LGBM bin | **calendario (join)** | rank dense | BO AUC 70/30 (filtro de meses antes de los lags) | 11.750 | 2 de 20 | — | baja |
| MarcosFedericoRios | LGBM bin, US 0,2 | fila (solo deltas) | — | BO AUC CV5 | 11.500–12.500 | 20 | — | baja |
| SerenaDituro | LGBM bin | **calendario (máscara)** | rank todo | BO AUC kfold5 03–05 | 12.000 (test 11.000) | 20 | — | media |
| aaav13 | LGBMClassifier | no | no | Optuna CV AUC (train con 202107 sin etiqueta) | 9.300 | 1 | — | ninguna |
| gromadzyn | LGBM bin | **calendario (máscara)** | rank todo | BO AUC 03–04→06 | 11.000 | top-10 config ×1 | — | baja |
| iespinozahDM | LGBM bin B2 | fila (lag1) | — | BO ganancia@10k 03–04→06 | 10.000 | 5 | Public 95,78 M | baja |
| jlazcanosimoniello | LGBM bin | fila (delta2 = lag1 − lag2) | — | BO AP; corte in-sample | argmax | 1 | — | ninguna |
| kformoso | LGBM **multiclass** | **calendario (máscara)** + tend | — | ninguna | 12.000 | 60 (US por semilla) | — | baja |
| laupasq1967 | 2×LGBM (A'plus+B) B2 | fila | rank 1–100 + canaritos | BO 202104 + top-K re-eval 10 semillas en 06 | 10.600 | 100+100, rank-avg | Public 119,38 | alta |
| lsaldeco | LGBM bin B2 | fila (imputación con t+1) | rank pct (NaN→0) | Optuna CV 03–04 + junio 20 sem | bot | 70 | — | baja |
| lvergini | LGBM bin | **calendario (join)** | rank todo; anti-imputación (exp.) | BO AUC 03–04→06 con gap | 11.750 curva ±500 | ~90 (dedupe) | — | alta |
| mbellesi01 | LGBM bin | fila (1–3) + numba tend | rank + tarjeta 0→NaN | Optuna en 06 (selección de variables en 06) | 11.000 | 5+20 rank | — | baja |
| mmfiora | LGBM bin | **calendario (merge pandas)** | rank m* + KS-drop 10 | Optuna AUC 03–05→06 | 13.000 | 20 | Public 105,02 | alta |
| nicolasmatayoshi | LGBM bin crudo | **calendario (match)** | — | meseta de árboles 03–04→06 | 10.000 | 50 | — | media |
| pablogarciaparisi | LGBM P2/P3/E012 + HNC | **calendario (match)** | signed rank | BO AUC + GainBand | 12.500 | 10+ rank-meta | — | media |
| patriciojarmoluk | LGBM bin | **calendario (match)** sobre rank | rank todo | BO AUC 12 evals 03–04→06 | 11.250 meseta | 30 | — | media |
| micaelarr | 6 config × 2 semillas | **calendario (SQL LAG + chequeo)** + historia | **IPC** + PSI + decay 0,8 | Optuna ganancia suavizada 3 semillas, 03–05→06 | 11.500 (curva 12.720) | 12 | — | alta |

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
