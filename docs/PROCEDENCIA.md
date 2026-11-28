# Procedencia del código

Copiado el 24-nov-2026 desde `C:\dev\DMEyF` (repo `MLDEVGIT/dmeyf2026`, rama
`feature/competencia02-sampling-pipeline`). **Los archivos de origen no estaban
commiteados** en ese repo (aparecen como no versionados), así que la referencia es la
ruta, la fecha de modificación y el sha256 (primeros 16 caracteres) del original.

**Fines de línea:** los sha256 de la tabla son de los archivos originales en disco, varios con CRLF. En este repo todo el texto se guarda con LF (`.gitattributes`), así que una copia "sin cambios" puede diferir del original solo en los fines de línea.

Autoría: Martín López. No se incorporó código de terceros; si se incorpora, agregar
acá URL, commit, licencia y atribución, y conservar el encabezado original.

| Archivo en este repo | Origen | Fecha | sha256 origen | Cambios |
|---|---|---|---|---|
| `pipeline_competencia02/__init__.py` | `pipeline_competencia02/__init__.py` | 2026-11-02 | 533b7b43c9788f5d | ninguno |
| `pipeline_competencia02/features.py` | `pipeline_competencia02/features.py` (antes en `experimento_sampling/04`) | 2026-11-02 | 9d10ed150eeacbbc | ninguno |
| `pipeline_competencia02/estrategias.py` | ídem | 2026-11-02 | 9dddc065db00b74a | ninguno |
| `pipeline_competencia02/incidentes.py` | ídem | 2026-11-02 | 5bdcbf7a010b26a0 | ninguno |
| `pipeline_competencia02/politica_incidentes.json` | ídem | 2026-11-02 | 63d05cf384539932 | ninguno |
| `pipeline_competencia02/ejecutar_mes.py` | ídem | 2026-11-02 | 8b6d9ab802eb246b | ninguno |
| `pipeline_competencia02/pruebas_unitarias.py` | ídem | 2026-11-02 | 7d657d6e273d95f5 | ninguno |
| `pipeline_competencia02/entorno.py` | ídem | 2026-11-02 | a3b5d46dbd9b9076 | rutas desde `config.py` |
| `pipeline_competencia02/correr_meses.py` | ídem | 2026-11-02 | a8673e27888062ce | rutas desde `config.py`; `--entorno` relativo al directorio actual |
| `pipeline_competencia02/preparar_insumos.py` | ídem | 2026-11-02 | dbc8f46416a2a6b4 | rutas desde `config.py`; auditoría 2019 desde `referencia/` |
| `entrenamiento/legado/01_auditar_datos.py` | `experimento_sampling/01_auditar_datos.py` | 2026-11-02 | 68718cc968e3cdde | ninguno |
| `entrenamiento/legado/02_convertir_parquet.py` | `experimento_sampling/02_convertir_parquet.py` | 2026-11-02 | cb46935acf25bd29 | ninguno |
| `entrenamiento/legado/03_construir_target.py` | `experimento_sampling/03_construir_target.py` | 2026-11-02 | 72a1b60904cd7140 | ninguno |
| `entrenamiento/legado/04_generar_features.py` | `experimento_sampling/04_generar_features.py` | 2026-11-02 | b9dca1f24e101f25 | ninguno |
| `entrenamiento/legado/05_baseline_inicial.py` | `experimento_sampling/05_baseline_inicial.py` | 2026-11-02 | 6bb7d99461bad6d1 | ninguno |
| `referencia/01_filas_por_mes.csv` | `experimento_sampling/reportes/01_filas_por_mes.csv` | 2026-11-02 | 2ae25c8750510576 | ninguno |

Nuevos en este repo (sin código de terceros): `pipeline_competencia02/config.py`,
`scripts/verificar_salida.py`, `evaluacion/*`, `experimentos/*`, `pruebas/*`, `README.md`, `docs/*`,
`config.ejemplo.toml`, `requirements.txt`, `.gitignore`. La forma de la curva de ganancia, el
suavizado de 501 y el corte por arrepentimiento mínimo siguen ideas citadas en § Ideas de terceros
(`agustinarazanov/dmeyf`, `farpp8/dmeyf2026-competencia01`, `mariofreites/dmeyf-primera-competencia`),
reimplementadas.

No se copiaron (quedan en `C:\dev\DMEyF`): `prueba_equivalencia_agosto.py`,
`prueba_robustez.py`, `prueba_incidentes.py`, `reclasificar_robustez.py`,
`resumen_alertas.py` (pruebas ya ejecutadas, con rutas fijas a corridas del 2-nov) y
`competencia_01_final/` (ver `RELEVAMIENTO.md` § competencia 01).

## Modelo usado en la verificación

No se versiona. Corrida `experimento_sampling/ejecuciones/05_baseline_inicial/20261102T191851_31980`
de `C:\dev\DMEyF`: `modelo.txt` (399 KB), `predictores.json` (760 predictores),
`configuracion.json`. LightGBM con parámetros por defecto, train 201903–201906, sin Optuna.

## Ideas de terceros (propuestas, todavía no implementadas)

Relevamiento del 24-nov-2026 (`RELEVAMIENTO.md` § 2); todos estos repos están en la matriz de los 66 (`docs/antecedentes/competencia-1/postmortem_vercel/`). Ninguno de estos repos tiene
licencia salvo el indicado: **no se copia código**, se reimplementa la idea y se cita acá
con repo, commit y archivo. Al implementar una idea, agregar el archivo nuestro donde quedó.

| Idea | Repo (github.com/…) | Commit | Archivo de referencia | Licencia | Implementada en |
|---|---|---|---|---|---|
| Lags por mes calendario (unión por cliente y período − k) | farpp8/dmeyf2026-competencia01 | fd33f7d | `02_variables.py:84-103` | ninguna | — |
| Panel denso cliente × mes para lags | pfranzd/dmeyf2026-entregas | 8f5e659 | `competencia_01/competencia_1/pipeline/features/temporales.py:15-33` | ninguna | — |
| Detección de columnas rotas por mes y PSI | vmanuelmarasco/dmeyf_2c_2026 | 5290716 | `pipeline/p10_adaptativo.py:879-945` | ninguna | — |
| Variable todo-cero en un mes ⇒ NA antes de lags | lvergini/dmeyf2026-competencia1 | 60033c0 | `evaluacion_junio/R/fe.R:200` | ninguna | — |
| Anular columna rota antes de lags | agustinarazanov/dmeyf (integrante del equipo) | 11ff484 | `scripts/c200_lags_todo.py:53-59` | ninguna; reusable con acuerdo de la autora | — |
| Corte por arrepentimiento mínimo entre meses | agustinarazanov/dmeyf | 11ff484 | `src/competencia.py:232-254` | ídem | — |
| Corte por arrepentimiento mínimo con escenarios | farpp8/dmeyf2026-competencia01 | fd33f7d | `origen/regla_n.py` | ninguna | — |
| Escala por mes de montos (rank cero fijo) | pfranzd/dmeyf2026-entregas | 8f5e659 | `competencia_01/competencia_1/pipeline/features/rankings.py:47-70` | ninguna | — |
| Percentil con signo para montos con drift; tabla de columnas rotas | emavaldez/primeracompetencia | ec1fa75 | `codigo/modelos/tips_ale_bolano_fe.py` (`PERCENTIL_CERO_FIJO`, `ROTAS`) | ninguna | — |
| Multiclase con BAJA+1 a peso 0,5 | emavaldez/primeracompetencia | ec1fa75 | ídem (`PESO_BAJA1`) | ninguna | — |
| Pseudoetiquetas para meses sin clase | nicobaranek/dmeyf-competencia-01 | 88ed240 | `codigo/motor.R:255-266` | ninguna | — |
| Decisión con semillas pareadas y Wilcoxon | ezequielabregu/DMEyF_competencia_1 | bc9f2a9 | ficha en `docs/antecedentes/competencia-1/postmortem_vercel/fichas.csv` | ninguna | — |
| Corte como proporción de la cartera | montagnaflor/DMEyF-Competencia-01 | c9a71f6 | notebook, celda 37 | ninguna | — |
