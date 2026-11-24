# dmeyf-pipeline-equipo333

Pipeline mensual de la **competencia 02 de DMEyF 2026** (Martín, Agustina y José).
Recibe el CSV crudo de un mes, sin targets, y produce `churn_<yyyymm>.csv` con
`numero_de_cliente,probabilidad,enviar`, más un reporte acumulativo.

> Estado (24-nov-2026): **base mínima**. El circuito de inferencia mensual funciona
> de punta a punta con un modelo **diagnóstico** (LightGBM por defecto, entrenado con
> 201903–201906) y cortes **diagnósticos**. Falta el modelo definitivo, el corte elegido
> con 2019 y la segunda estrategia real. Brechas y orden: [docs/TAREAS.md](docs/TAREAS.md).
> Requisitos y puntos pendientes (target de 201912): [docs/CONSIGNA.md](docs/CONSIGNA.md).
> Pruebas: E01 (binario contra multiclase), E02 (peso de BAJA+1) y T01 (tiempos de inferencia) ejecutadas;
> referencia vigente: binario;
> resultados y plan incremental en [docs/PLAN_PRUEBAS.md](docs/PLAN_PRUEBAS.md). Ganancia: [docs/GANANCIA.md](docs/GANANCIA.md).

## Puesta en marcha

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
copy config.ejemplo.toml config.toml        # y editar las rutas
.venv/Scripts/python.exe -m pipeline_competencia02.config   # muestra qué rutas resolvió y si existen
```

Los datos **no** se versionan. `config.toml` (local) dice dónde están; cada ruta se
puede pisar con una variable de entorno (`DMEYF_DATOS`, `DMEYF_ENTORNOS`, …).

## Uso

```powershell
# 1. (fuera del tiempo mensual) cortar el crudo en un CSV por mes
python -m pipeline_competencia02.preparar_insumos --desde 202001 --hasta 202006

# 2. crear un entorno aislado: historia hasta el mes anterior + copia del modelo
python -m pipeline_competencia02.entorno --nombre ensayo_X --hasta 201912 --modelo-desde <carpeta con modelo.txt, predictores.json, configuracion.json>

# 3a. un mes
python -m pipeline_competencia02.ejecutar_mes --entorno ejecuciones/entornos/ensayo_X `
    --entrada <ruta>/202001.csv --mes 202001 `
    --estrategia cupo_fijo:1000 --estrategia porcentaje:1 --principal cupo_fijo

# 3b. varios meses seguidos, con comprobaciones
python -m pipeline_competencia02.correr_meses --entorno ejecuciones/entornos/ensayo_X `
    --desde 202001 --hasta 202006 --estrategia cupo_fijo:1000 --estrategia porcentaje:1 --principal cupo_fijo

# 4. verificar una salida (independiente del pipeline)
python scripts/verificar_salida.py ejecuciones/entornos/ensayo_X/output/churn_202001.csv --entrada <ruta>/202001.csv --envios 1000

# pruebas rápidas
python -m unittest pipeline_competencia02.pruebas_unitarias -v
python -m unittest discover -s pruebas -t . -v

# experimentos (sólo 2019; octubre bloqueado)
python -m experimentos.e01_binario_vs_multiclase --semillas 5 --rondas 300
python -m experimentos.e02_peso_baja1 --e01 ejecuciones/e01/<marca>
python -m experimentos.t01_tiempo_inferencia --e01 ejecuciones/e01/<marca>
```

Salidas de cada entorno: `output/churn_AAAAMM.csv` (oficial),
`diagnosticos/AAAAMM/` (features, decisiones de todas las estrategias, `reporte.json`) y
`registro/reporte_acumulado.csv` (una fila por ejecución). Códigos de salida:
0 completado, 2 fallido, 4 mes ya completado.

## Estructura

| Ruta | Qué es |
|---|---|
| `pipeline_competencia02/` | Inferencia mensual: validación, features (lag/delta 1 y 2), inferencia, estrategias, publicación todo-o-nada, incidentes y reporte. |
| `pipeline_competencia02/config.py` | Resolución de rutas desde `config.toml` / variables de entorno. |
| `scripts/verificar_salida.py` | Chequeo independiente de un `churn_<yyyymm>.csv`. |
| `evaluacion/` | Ganancia (premio bruto, costo, neta; `docs/GANANCIA.md`), curvas, corte por fracción con arrepentimiento mínimo, y particiones temporales que **bloquean por código** la lectura de etiquetas fuera de lo permitido. |
| `experimentos/` | Pruebas incrementales del `docs/PLAN_PRUEBAS.md`: `e01_binario_vs_multiclase.py`, `e02_peso_baja1.py`, `t01_tiempo_inferencia.py`. Salidas completas en `ejecuciones/` (no versionado). |
| `resultados/` | Resúmenes versionados de cada experimento, sin datos por cliente (p. ej. `e02_peso_baja1.json`). |
| `pruebas/` | Pruebas unitarias de `evaluacion/` (`python -m unittest discover -s pruebas -t .`). |
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
