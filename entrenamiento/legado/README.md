# Entrenamiento legado

Scripts `01`–`05` de `C:\dev\DMEyF\experimento_sampling` (procedencia en `docs/PROCEDENCIA.md`). Produjeron el
modelo diagnóstico del pipeline.

`02`, `03` y `04` ya toman sus rutas de `pipeline_competencia02/config.py` (tarea 3.1 de `esqueleto-del-pipeline`) y
arman la historia de 2019 desde el dataset del curso, sin archivos previos:

```bash
python entrenamiento/legado/02_convertir_parquet.py   # crudo (201901–202108) -> historico_2019, solo 2019
python entrenamiento/legado/03_construir_target.py    # historico_2019 -> target_2019 (regla v1)
python entrenamiento/legado/04_generar_features.py    # historico_2019 + target_2019 -> features_2019
```

Los reportes van a `<datos>/reportes/`. `02` verifica celda por celda contra el CSV y compara las filas por mes con
`referencia/01_filas_por_mes.csv`. Medido en la Mac (M1, 16 GB, 28-nov-2026): 218 s, 2 s y 77 s.

`01` y `05` siguen con las rutas de la notebook de Martín: **no correrlos desde este repo**.
