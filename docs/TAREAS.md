# Brechas (historia)

**El plan ya no vive acá.** Desde el 28-nov-2026 el plan del equipo son los cambios de OpenSpec (`openspec list`):
`esqueleto-del-pipeline` (en curso, con sus tareas en `openspec/changes/esqueleto-del-pipeline/tasks.md`) y los que
siguen, cada uno con su propuesta en `openspec/changes/`. El orden de implementación y el reparto que había acá
(T1–T13) se retiraron; lo que seguía pendiente quedó en esas tareas. Este archivo conserva, como historia, la
corrección del plan del 24-nov y la tabla de brechas con su avance, y dice qué cambio cubre cada brecha abierta.
Requisitos R1–R9 y fuentes en [CONSIGNA.md](CONSIGNA.md).

## Brechas abiertas y el cambio que las cubre

| Brecha | Cambio | Dónde |
|---|---|---|
| B4 entrenamiento offline con 2019 | `esqueleto-del-pipeline` | grupo 3, fábrica desde cero: historia, target y catálogo desde el dataset del curso, con el candado de meses (3.7) |
| B8 reporte acumulativo (falta el drift contra 2019) | `esqueleto-del-pipeline` | PSI por variable en `control_calidad` (7.2) y tablas agregadas, tablero y `reporte/index.html` (grupo 8) |
| B10 mes faltante o datos anómalos | `esqueleto-del-pipeline` | grupo 7, calidad de datos: detección y tratamiento de variables rotas elegido con 2019. Los lags por calendario van en `variables-de-tendencia-y-evento` y un modelo para meses con muchas rotas en `modelo-de-respaldo` |
| B11 reentrenamiento mensual | `reajuste-mensual` | la estrategia que se reentrena cada mes con las clases que maduran |
| B13 criterios de evaluación | `esqueleto-del-pipeline` | transcriptos en `CONSIGNA.md` § Evaluación (1.2); calidad de scores → vista de estrategias (8.6), exploración → los cambios de estrategias nuevas, medición → reporte y tablero (grupo 8), industrialización → etapas, registro, pruebas y recorrido por integrante (grupos 4, 5, 6 y 10.3) |

Las provisionales (B5, B6, B7: dos modelos sin optimizar, recomendación y cortes) se revisan en
`busqueda-de-hiperparametros` y `estrategias-del-podio`; el catálogo de la clase se congela en
`esqueleto-del-pipeline` (7.7).

## Corrección del plan anterior

El plan del 24-nov (primera versión) proponía elegir modelos y cortes con etiquetas de
los meses de ensayo 202001–202006. **Eso contradice R1** y queda descartado.

| Uso | Meses permitidos |
|---|---|
| Selección de modelos, hiperparámetros, features y cortes; definición de estrategias | **201901–201912** (R1): entrenamiento 201903–201906, **desarrollo y cortes en 201908–201909**, **201910 reservado** para una evaluación final única (ya usado como test en el experimento de sampling: `PLAN_PRUEBAS.md` § 2). 201911–201912 sólo como historia mientras no se aclare su etiqueta. |
| Ensayos 202001–202006 | Sólo **prueba operativa**: tiempos, esquema, salida, reporte, incidentes y continuidad de la historia. **No se calcula ganancia ni AUC con sus etiquetas para decidir nada.** |
| Vivo 202007–202009 | Sólo ejecución. |
| Exploración de meses posteriores | Observación separada, con alcance a aclarar (CONSIGNA § Observación de clase). No entra en decisiones. |

## Lo que se conserva como diagnóstico

| Elemento | Estado |
|---|---|
| Modelo de `05_baseline_inicial` (LightGBM por defecto, train 201903–201906) | **Diagnóstico.** Entrenado dentro del período autorizado, pero sin optimizar ni elegir. Sirve para probar el circuito. |
| `cupo_fijo:1000` y `porcentaje:1` | **Cortes diagnósticos.** No se eligieron con datos. No son la recomendación final. |
| Corridas del 2-nov y del 24-nov sobre 202001–202006 | Evidencia operativa (tiempos, integridad). No son evidencia de desempeño. |

## Brechas del pipeline actual

| # | Requisito | Hoy | Brecha |
|---|---|---|---|
| B1 | R2 entrada `input/<yyyymm>.csv` | `--entrada` acepta cualquier ruta y copia al entorno. `correr_meses` busca `competencia_02_<mes>_crudo.csv`. | Leer `input/<yyyymm>.csv` por convención y adaptar `correr_meses` al nombre. |
| B2 | R2 salida `output/churn_<yyyymm>.csv` | Se escribe en `<entorno>/output/churn_<yyyymm>.csv` con el esquema correcto (verificado). | Publicar también, o sólo, en `output/` del directorio de trabajo pedido, conservando la escritura atómica. |
| B3 | R3 15 min desde la copia hasta salida y reporte | `ejecutar_mes` mide sus etapas: 202001 en 57 s (modelo de 300 árboles, T01) y en 93 s (modelo diagnóstico, con más carga en la máquina), sin la copia previa ni el cierre del reporte. | Un comando único con reloj de punta a punta, desde la llegada del archivo hasta el reporte, con alarma si se acerca a 15 min. |
| B4 | R1 entrenamiento con 201901–201912 | El entrenamiento legado usa rutas fijas, train 201903–201906, valida 201908, sin Optuna. | `entrenar.py` offline con `config.py`, ventanas configurables y verificación de que ningún dato posterior a 201912 entra. Etiquetas de 201911–201912 pendientes de aclaración. |
| B5 | R4 al menos dos modelos o estrategias | Dos cortes sobre un único score. | Al menos un segundo modelo y estrategias definidas con 2019. |
| B6 | R4 recomendación por cliente | `enviar` sale de la estrategia principal, elegida sin datos. | Elegir con 2019 la estrategia recomendada y documentar la regla. `enviar` = recomendación. Las demás quedan en diagnósticos. |
| B7 | R1 cortes definidos con 2019 | Cupo fijo de 1.000, sin optimizar. | Corte por fracción de clientes con arrepentimiento mínimo en 201908–201909 (implementado en `evaluacion/ganancia.py`; en E01 quedó entre 2,8 % y 2,9 %). |
| B8 | Reporte acumulativo (R3, F2 pregunta 5) | `reporte_acumulado.csv` con tiempos, scores, envíos, alertas y solapamiento. | Comparación de estrategias por mes, drift contra 2019 y lugar para métricas diferidas (con alcance a aclarar; no se usan para decidir). Formato pedido: pendiente. |
| B9 | R7 historia para el vivo | `entorno.py` sólo copia historia de 2019. Se exige que la historia termine en el mes anterior. | Armar la historia 202001–202006 corriendo los ensayos en el mismo entorno, o con una opción para construirla desde los insumos. |
| B10 | Mes faltante o datos anómalos | Un mes faltante se rechaza. 202006 tiene 47 columnas en cero y sólo se advierte. | Política explícita: definir qué hacer y con qué features (lags de calendario más indicador de disponibilidad). |
| B11 | R6 reentrenamiento mensual opcional | No existe. | Sólo si entra en 15 min y si lo justifica la evaluación en 2019. Prioridad baja. |
| B12 | Consistencia entre entrenamiento y producción (F2 pregunta 2) | `features.py` compartido. Igualdad bit a bit verificada en 201908. | Mantener una sola implementación para cualquier feature nueva y repetir la prueba de equivalencia. |
| B13 | R8 criterios de evaluación | Desconocidos en detalle. | Transcribirlos y mapear cada uno a un entregable. |

## Avance de la integración (24-nov, ramas `martin/integracion-estrategias` y `martin/ensayo-secuencia`)

Detalle en `INTEGRACION.md`.

| Brecha | Estado |
|---|---|
| B1 entrada `input/<yyyymm>.csv` | **Resuelta** en `mensual.py` y en `correr_meses.py` |
| B2 salida `output/churn_<yyyymm>.csv` | **Resuelta**, en la carpeta de ejecución |
| B3 reloj de 15 min | **Resuelta**: 172–194 s por mes en la secuencia 202001–202006, con el arranque del proceso. Falta medir en la máquina del vivo (T12) |
| B5 dos modelos | **Resuelta en forma provisional**: binario y multiclase de E01, sin optimizar |
| B6 recomendación por cliente | **Provisional**: binario; el multiclase queda como alternativa en el reporte |
| B7 cortes con 2019 | **Resuelta**: fracción por estrategia, de E01 (201908–201909) |
| B8 reporte acumulativo | **Resuelta**: una fila por mes, derivada; métricas con target completadas a posteriori (`retrospectiva.py`). Falta el drift contra 2019 (PSI) |
| B9 historia para el vivo | **Resuelta** y ensayada en secuencia 202001–202006: la historia crece sólo con los meses recibidos |
| Reintentos consistentes | **Resuelta** y probada aislada (`scripts/probar_reintentos.py`) y dentro de la secuencia (202003; el mes siguiente se rechaza hasta reconciliar) |
| B10 anomalías | 202006 diagnosticado (`resultados/i02_columnas_en_cero_202006.json`); el tratamiento queda para E06 con 2019 |
| Target consistente | **Resuelta en este repo** (`martin/target-consistente`): regla única `evaluacion/target.py`, target 2019 regenerado, candidatos reentrenados (TC01), catálogo `tc01` activo y secuencia repetida. Falta coordinar el repo de sampling |
| Corte del binario `tc01` | **Candidato ensayado, falta decidir la activación**. CE02 (2019): ensambles de 20 y cortes de 2,35 % / 2,725 %. CA01: el catálogo `ce02` pasa las verificaciones en 202001–202006, pero tarda 432–730 s por mes en esta laptop. CA02: `ce02_b20m10` (corte multiclase respaldado con las semillas 0–9 en 2019) pasa las verificaciones en 202001–202006 y tarda 347–476 s por mes (900 s cumplido; 450 s excedido sólo en 202002). Es el catálogo de trabajo local; falta medir en GCP y que el grupo decida |
| B11, B13 | Sin cambios |
