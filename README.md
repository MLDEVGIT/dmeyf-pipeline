# dmeyf-pipeline-equipo333

Pipeline mensual de la **competencia 02 de DMEyF 2026** (Martín, Agustina y José).
Recibe el CSV crudo de un mes, sin targets, y produce `churn_<yyyymm>.csv` con
`numero_de_cliente,probabilidad,enviar`, más un reporte acumulativo.

> Estado (25-nov-2026): **pipeline mensual con dos estrategias, target unificado (regla oficial) y ensayado en secuencia 202001–202006**
> ([docs/INTEGRACION.md](docs/INTEGRACION.md)).
> - **Target único** (`evaluacion/target.py`) para entrenamiento, evaluación y retrospectiva: presente en *t+2* → CONTINUA;
>   presente en *t+1* y ausente en *t+2* → BAJA+2; ausente en ambos → BAJA+1. Los candidatos se reentrenaron con él (TC01).
> - **Catálogo activo `tc01`**:
>   - **recomendación provisional** (salida oficial): binario corregido, score = **P(BAJA+1 ∪ BAJA+2)**, corte **4,475 %**;
>   - **alternativa** (reporte): multiclase corregido de peso 1, score = **P(BAJA+2)**, corte 2,8 %.
>
>   **El corte del binario está en revisión**: cayó en el borde de una meseta y en 2020 envía de más (pendiente 0 de `INTEGRACION.md`).
>   El catálogo anterior, `e01` (corte del binario 2,9 %), se conserva.
> - Las dos son candidatos de 300 rondas **sin optimización**, con 5 semillas promediadas.
> - **Ensayo secuencial** (un archivo por vez, reintento provocado en 202003), con `e01` y con `tc01`:
>   - 135–194 s por mes, contando el arranque del proceso;
>   - los 6 meses verificados, con scores idénticos bit a bit a los modelos originales;
>   - métricas con target retrospectivas completas para 202001–202004; 202005 sin clases definitivas (sólo provisionales) y 202006 pendiente.
>   - **Regla de target**: la que reproduce las etiquetas oficiales de C01. El cliente ausente en *t+1* que vuelve en *t+2* es CONTINUA; se corrigió el 24-nov (3 clientes reclasificados, ninguna ganancia cambia).
> - **202006** llega con 47 columnas en cero: los scores se corren hacia arriba y la coincidencia entre
>   estrategias baja a 0,46. Hoy el pipeline advierte y no trata.
>
> Pendientes: criterio de corte robusto con 2019, tratamiento de columnas en cero (E06), corte y prevalencia,
> modelos optimizados, lags por calendario (E05), interpretación de la probabilidad con la cátedra, y la
> actualización del target en el repo grupal de sampling.
> Brechas y orden: [docs/TAREAS.md](docs/TAREAS.md). Consigna: [docs/CONSIGNA.md](docs/CONSIGNA.md).
> Pruebas E01, E02 y T01: [docs/PLAN_PRUEBAS.md](docs/PLAN_PRUEBAS.md). Ganancia: [docs/GANANCIA.md](docs/GANANCIA.md).

## Puesta en marcha

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
copy config.ejemplo.toml config.toml        # y editar las rutas
.venv/Scripts/python.exe -m pipeline_competencia02.config   # muestra qué rutas resolvió y si existen
```

Los datos **no** se versionan. `config.toml` (local) dice dónde están; cada ruta se
puede pisar con una variable de entorno (`DMEYF_DATOS`, `DMEYF_ENTORNOS`, …).

## Uso: ejecución mensual con dos estrategias

```powershell
# 0. (una vez) catálogo de estrategias desde los modelos de E01: copia los 10 modelos con nombres de
#    features a la ruta `modelos` de config.toml y escribe catalogo/estrategias.json (versionado)
python -m pipeline_competencia02.catalogo --catalogo tc01 --modelos-de ejecuciones/tc01/<marca>   # activo
python -m pipeline_competencia02.catalogo --catalogo e01  --modelos-de ejecuciones/e01/<marca>    # anterior

# 1. (fuera del tiempo mensual) carpeta de ejecución nueva: catálogo verificado + historia 201901..hasta
python -m pipeline_competencia02.preparar_ejecucion --nombre vivo_X --hasta 201912 [--catalogo tc01|e01]

# 2. cada mes: input/<yyyymm>.csv -> output/churn_<yyyymm>.csv + registro/reporte_acumulado.csv
python -m pipeline_competencia02.mensual --ejecucion ejecuciones/entornos/vivo_X --mes 202001 `
    --copiar-desde <ruta>/202001.csv     # o dejar el archivo en input/202001.csv y omitir --copiar-desde

# 2b. ensayo secuencial: un proceso por mes, cada uno con su archivo; carpeta nueva y preparación medida aparte
python -m pipeline_competencia02.correr_meses --nueva ensayo_X --desde 202001 --hasta 202006 --reintento-en 202003

# 3. verificaciones independientes y diagnóstico de columnas en cero
python scripts/analizar_columnas_en_cero.py --ejecucion ejecuciones/entornos/ensayo_X --mes 202006 --salida <json>
python scripts/verificar_salida.py ejecuciones/entornos/vivo_X/output/churn_202001.csv --entrada ejecuciones/entornos/vivo_X/input/202001.csv
python scripts/verificar_scores.py --ejecucion ejecuciones/entornos/vivo_X --mes 202001
python scripts/probar_reintentos.py --mes 202001 --entrada <ruta>/202001.csv   # usa su propia carpeta nueva
```

Códigos de salida de `mensual`: 0 completado (o recuperado), 2 fallido, 4 rechazado (mes completado,
con otro intento en curso, de la historia inicial o con un mes previo procesado sin completar). `output/churn_<yyyymm>.csv` tiene
`numero_de_cliente, probabilidad, enviar`; la probabilidad es la de la recomendación,
**P(BAJA+1 ∪ BAJA+2)**. Las predicciones y decisiones de las dos estrategias quedan en
`diagnosticos/<yyyymm>/`. El reporte acumulado tiene una fila por mes completado, con clientes,
anomalías, distribución de scores, envíos, coincidencia, versiones de modelos y tiempos por etapa.
Las métricas con target (ganancia, aciertos, AUC de BAJA+2) se completan a posteriori cuando llegan
los dos meses siguientes (`retrospectiva.py`; regla en `docs/INTEGRACION.md`). Son monitoreo: no cambian
modelos ni cortes.

## Uso: pipeline de un modelo (legado) y experimentos

```powershell
# 1. (fuera del tiempo mensual) cortar el crudo en un CSV por mes
python -m pipeline_competencia02.preparar_insumos --desde 202001 --hasta 202006

# 2. crear un entorno aislado: historia hasta el mes anterior + copia del modelo
python -m pipeline_competencia02.entorno --nombre ensayo_X --hasta 201912 --modelo-desde <carpeta con modelo.txt, predictores.json, configuracion.json>

# 3a. un mes
python -m pipeline_competencia02.ejecutar_mes --entorno ejecuciones/entornos/ensayo_X `
    --entrada <ruta>/202001.csv --mes 202001 `
    --estrategia cupo_fijo:1000 --estrategia porcentaje:1 --principal cupo_fijo

# 4. verificar una salida (independiente del pipeline)
python scripts/verificar_salida.py ejecuciones/entornos/ensayo_X/output/churn_202001.csv --entrada <ruta>/202001.csv --envios 1000

# pruebas rápidas
python -m unittest pipeline_competencia02.pruebas_unitarias -v
python -m unittest discover -s pruebas -t . -v

# experimentos (sólo 2019; octubre bloqueado)
python -m experimentos.e01_binario_vs_multiclase --semillas 5 --rondas 300
python -m experimentos.e02_peso_baja1 --e01 ejecuciones/e01/<marca>
python -m experimentos.t01_tiempo_inferencia --e01 ejecuciones/e01/<marca>
python -m experimentos.tc01_target_2019                                       # target 2019 versión 2 (no sobrescribe)
python -m experimentos.tc01_target_corregido --e01 ejecuciones/e01/<marca>    # reentrena con target v2 y compara
python scripts/comparar_secuencias.py --anterior <carpeta> --nueva <carpeta> --salida <json>
```

`ejecutar_mes` y `entorno` son el pipeline anterior de un solo modelo (diagnóstico):
se conservan porque `mensual.py` reutiliza su validación, su candado y su publicación. Su
`reporte_acumulado.csv` tiene una fila por intento.

## Estructura

| Ruta | Qué es |
|---|---|
| `pipeline_competencia02/` | Inferencia mensual: validación, features (lag/delta 1 y 2), inferencia, estrategias, publicación todo-o-nada, incidentes y reporte. `mensual.py` (dos estrategias), `preparar_ejecucion.py` (carpeta e historia inicial), `catalogo.py` (estrategias desde los modelos de E01), `retrospectiva.py` (métricas con target a posteriori), `correr_meses.py` (ensayo secuencial con comprobaciones). |
| `catalogo/` | Índice versionado de estrategias: modelos con sha256, corte, significado del score y los 760 predictores con su tipo. |
| `pipeline_competencia02/config.py` | Resolución de rutas desde `config.toml` / variables de entorno. |
| `scripts/` | `verificar_salida.py` (chequeo independiente de un `churn_<yyyymm>.csv`), `verificar_scores.py` (scores contra los modelos originales) `probar_reintentos.py` (fallas y reintentos) y `analizar_columnas_en_cero.py` (diagnóstico de 202006). |
| `evaluacion/` | Ganancia (premio bruto, costo, neta; `docs/GANANCIA.md`), curvas, corte por fracción con arrepentimiento mínimo, **definición única del target** (`target.py`), y particiones temporales que **bloquean por código** la lectura de etiquetas fuera de lo permitido. |
| `experimentos/` | Pruebas incrementales del `docs/PLAN_PRUEBAS.md`: `e01_binario_vs_multiclase.py`, `e02_peso_baja1.py`, `t01_tiempo_inferencia.py`, `tc01_target_2019.py`, `tc01_target_corregido.py`. Salidas completas en `ejecuciones/` (no versionado). |
| `resultados/` | Resúmenes versionados de cada experimento, sin datos por cliente (`e02_peso_baja1.json`, `i01_ensayo_202001.json`, `i02_secuencia_202001_202006.json`, `i02_columnas_en_cero_202006.json`, `i03_correccion_target_retrospectivo.json`, `tc01_target_2019_v2.json`, `tc01_target_corregido.json`, `i04_secuencia_tc01_202001_202006.json`, `i05_comparacion_secuencias_e01_tc01.json`). |
| `pruebas/` | Pruebas unitarias de `evaluacion/` y del pipeline mensual (`python -m unittest discover -s pruebas -t .`). |
| `entrenamiento/legado/` | Scripts que produjeron el modelo diagnóstico (copiados sin cambios; todavía usan rutas fijas). |
| `referencia/01_filas_por_mes.csv` | Conteo de filas por mes de 2019 (sin datos de clientes), usado por `preparar_insumos`. |
| `docs/` | Consigna recuperada, relevamiento, procedencia del código y tareas. |

## Forma de trabajo

Igual que en el experimento de sampling: `main` protegida, una rama por tarea
(`<nombre>/<tema>`), PR con revisión de otro integrante. Las decisiones de modelo,
hiperparámetros y corte se toman **sólo con datos de 201901–201912** (consigna, R1); los
meses 202001–202006 son ensayos operativos, no se usan para decidir. Cada decisión se
registra con su fuente en `docs/`. La publicación en GitHub queda pendiente de acordar la
cuenta propietaria.

## Procedencia

El código viene del trabajo de Martín en `C:\dev\DMEyF` (sin licencia de terceros
involucrada). Detalle por archivo, con sha256 del original: [docs/PROCEDENCIA.md](docs/PROCEDENCIA.md).
