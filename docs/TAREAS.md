# Brechas, orden de implementación y tareas

Actualizado el 24-nov-2026. Requisitos R1–R8 y fuentes en [CONSIGNA.md](CONSIGNA.md).

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
| B8 reporte acumulativo | **Resuelta**: una fila por mes, derivada; métricas con target completadas a posteriori (`retrospectiva.py`). Además, tablero HTML de seguimiento interactivo y autocontenido que se regenera con cada mes (`registro/reporte_seguimiento.html`, `PLAN_PRUEBAS.md` § 21–22). Falta el drift contra 2019 (PSI) |
| B9 historia para el vivo | **Resuelta** y ensayada en secuencia 202001–202006: la historia crece sólo con los meses recibidos |
| Reintentos consistentes | **Resuelta** y probada aislada (`scripts/probar_reintentos.py`) y dentro de la secuencia (202003; el mes siguiente se rechaza hasta reconciliar) |
| B10 anomalías | 202006 diagnosticado (`resultados/i02_columnas_en_cero_202006.json`). **E06 ejecutada** (`PLAN_PRUEBAS.md` § 19–20): detector: en 2019 sólo marca los incidentes de 201904 y 201905 (tasa de falsas alarmas sin estimar), integrado como alerta `cero_anomalo`; N y L no cumplen el criterio (L pierde > 2 BAJA+2 en la propagación y con tres meses seguidos), así que el pipeline sigue advirtiendo sin tratar |
| Target consistente | **Resuelta en este repo** (`martin/target-consistente`): regla única `evaluacion/target.py`, target 2019 regenerado, candidatos reentrenados (TC01), catálogo `tc01` activo y secuencia repetida. Falta coordinar el repo de sampling |
| Corte del binario `tc01` | **Candidato ensayado, falta decidir la activación**. CE02 (2019): ensambles de 20 y cortes de 2,35 % / 2,725 %. CA01: el catálogo `ce02` pasa las verificaciones en 202001–202006, pero tarda 432–730 s por mes en esta laptop. CA02: `ce02_b20m10` (corte multiclase respaldado con las semillas 0–9 en 2019) pasa las verificaciones en 202001–202006 y tarda 347–476 s por mes (900 s cumplido; 450 s excedido sólo en 202002). Es el catálogo de trabajo local; falta medir en GCP y que el grupo decida |
| B11, B13 | Sin cambios |

## Orden de implementación propuesto

1. **Contrato de entrada/salida y reloj (B1, B2, B3).** Es barato y lo necesitan todos los ensayos. Se puede probar con el modelo diagnóstico.
2. **Historia continua y política de faltantes (B9, B10).** Sin esto no se puede correr 202007.
3. **Entrenamiento offline reproducible con 2019 (B4).** Particiones de `PLAN_PRUEBAS.md` § 1 (`evaluacion/particiones.py`); 201911–201912 quedan para cuando se aclare.
4. **Cortes y recomendación con 2019 (B7, B6).** Reemplazan los cortes diagnósticos.
5. **Segundo modelo (B5),** sobre la misma infraestructura.
6. **Reporte acumulativo completo (B8)** y mapeo a los criterios de evaluación (B13).
7. **Ensayo operativo 202001–202006** de punta a punta, cronometrado en la máquina del vivo.
8. **Reentrenamiento mensual (B11),** sólo si sobra tiempo y está justificado.

Entre 1 y 3 hay que resolver en Zulip: el target de 201912, el alcance de la observación sobre meses posteriores y la transcripción de F1 y R8.

## Reparto — propuesta para acordar entre Martín, Agustina y José

> **Propuesta, no acordada.** Se reasigna en la próxima reunión.

| # | Tarea | Brechas | Propuesta | Entregable |
|---|---|---|---|---|
| T1 | Transcribir F1 y los criterios de R8 con el id del mensaje; preguntar en Zulip por el target de 201912 y el alcance de la observación de clase | — | quien tenga la sesión de Zulip | `CONSIGNA.md` sin pendientes |
| T2 | Acordar la cuenta propietaria en GitHub, publicar y proteger `main` | — | grupo | remoto y regla de rama |
| T3 | Comando único `input/` → `output/` con reloj de punta a punta | B1–B3 | Martín | comando y prueba con 202001 |
| T4 | Historia continua y política ante mes faltante o anómalo | B9, B10 | Martín | entorno listo hasta 202006 y prueba |
| T5 | `entrenar.py` offline con config, ventanas de 2019 y control de fechas | B4, B12 | José | modelo con hash, fuera del repo |
| T6 | Curva de ganancia y corte en 2019; regla de recomendación | B6, B7 | Agustina | estrategia nueva en `estrategias.py` |
| T7 | Segundo modelo (Optuna según 208135, o ideas de C01: lags de calendario, multiclase, ensamble por rangos) | B5 | Agustina + Martín | artefactos y comparación en 2019 |
| T8 | Reporte acumulativo y mapeo a criterios | B8, B13 | José | reporte con 6 meses de ensayo |
| T9 | Reconciliar el relevamiento de C01 (46 repos hallados en GitHub, `RELEVAMIENTO.md` § 2) con los enlaces de Zulip; relevar los que falten | — | quien tenga Zulip | inventario con id de mensaje |
| T10 | Simulacro cronometrado de 3 meses seguidos, desde un clon limpio, en la máquina del vivo | todas | los tres, antes del 3-dic | checklist del día |
| T11 | Pruebas incrementales E03–E06 (`PLAN_PRUEBAS.md` § 4; E01 y E02 ejecutadas, referencia: binario), desarrollo en 201908–201909; congelar protocolo y correr F01 en 201910 una vez | B4–B7, B10 | Agustina + José | resultados en `PLAN_PRUEBAS.md` y tag `protocolo-final` |
| T12 | Repetir T01 en la máquina del vivo y fijar el tope de árboles × semillas (`PLAN_PRUEBAS.md` § 6) | B3 | Martín | tope por estrategia |
| T13 | Confirmar con la cátedra los importes de ganancia de C02 (`GANANCIA.md`) | — | quien tenga Zulip | fuente registrada |
