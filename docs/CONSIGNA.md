# Consigna de la competencia 02

Actualizado el 24-nov-2026.

## Fuentes

| Id | Fuente | Fecha | Cómo se accedió |
|---|---|---|---|
| **F1** | Consigna de Alejandro Bolaños (capturas de Zulip) | 30-oct-2026 | Lectura del grupo, transmitida por Martín el 24-nov. **Falta transcribir el texto literal** con el id del mensaje: no se identificaron las capturas entre los archivos locales. |
| **F2** | Presentación `pipeline-competencia-2.html`, compartida por Joaquín Aramendía | 4-nov-2026 | Archivo local `Downloads/pipeline-competencia-2.html` (sha256 `559a307b2854ed3a…`, 13 diapositivas). No se copia al repo porque es material de la cátedra; las citas de abajo son textuales. |
| F3 | Aclaraciones del baseline del experimento grupal (Zulip 208135, 211210, 211718, 212043, 212249) | 28-oct a 12-nov | `dmeyf-experimento-sampling` (bitácora). Son del experimento de sampling, no de esta competencia. |
| — | Zulip `uba26.zulip.rebelare.com` | — | Sin acceso automático: requiere login y no hay credenciales en esta máquina. |

## Requisitos confirmados

| # | Requisito | Fuente | Notas |
|---|---|---|---|
| R1 | Entrenamiento y definición de estrategias **sólo con datos de 201901–201912** | F1 | Período autorizado para elegir modelos, hiperparámetros y cortes. |
| R2 | Entrada `input/<yyyymm>.csv`; salida `output/churn_<yyyymm>.csv` | F1 | Columnas de salida: `numero_de_cliente,probabilidad,enviar` (verificar el texto literal de F1). F2 habla de `(numero_de_cliente, score)` "para afuera". |
| R3 | **Máximo 15 minutos** desde la copia del archivo de entrada hasta la salida y el reporte actualizados | F1 | F2: "≤ 15 minutos en una laptop". El reloj incluye la actualización del reporte. |
| R4 | Al menos **dos modelos o estrategias** y **una recomendación por cliente** | F1 | F2: "Aplicar N estrategias", "¿Cómo comparo varias estrategias a la vez?". |
| R5 | Entrenamiento y optimización **offline** permitidos | F1, F2 | F2: "Pipeline de entrenamiento · offline · horas o días: no importa"; "Todo lo pesado se hace en entrenamiento". |
| R6 | **Reentrenamiento mensual** permitido si entra en el tiempo | F1 | F2 lo plantea como pregunta: "¿Puedo reentrenar con el mes que acaba de tener clase?". En producción F2 dice: "no optimiza: carga modelos ya hechos (a lo sumo los recalibra)". |
| R7 | Ensayos con **202001–202006**; prueba en vivo con archivos **equivalentes a 202007–202009** | F1 | En vivo el jueves 10-dic-2026 (según el grupo). |
| R8 | Los **cuatro criterios de evaluación** integran el **40 %** de la nota de la segunda competencia | F1 | **Falta transcribir los cuatro criterios** de la captura. |

## Contradicción: el target de 201912

**F1** limita el entrenamiento y la definición de estrategias a datos de 201901–201912.

**F2** propone ("Qué mes se usa para qué"), textual:

> Entrena (201901–201910) · Valida la BO (201911) · Test: rankea estrategias (201912) · Sin BAJA+2 todavía · Solo historia para FE · Mes a predecir
>
> Entrenamiento elige hiperparámetros con validación en 201911, compara estrategias en 201912 (un mes que la BO nunca vio) y recién ahí reentrena con 201901–201912.
>
> Producción recibe 202002 en crudo.

**Por qué choca.** BAJA+2 en el mes *t* se define por la presencia del cliente en *t+1* y su ausencia en *t+2* (`entrenamiento/legado/03_construir_target.py`). Con datos sólo hasta 201912:

| Mes | Etiqueta calculable con 201901–201912 |
|---|---|
| 201901–201910 | completa (BAJA+1, BAJA+2, CONTINUA) |
| 201911 | sólo BAJA+1 (ausentes en 201912); BAJA+2 y CONTINUA necesitan 202001 |
| 201912 | ninguna; necesita 202001 y 202002 |

Validar la BO en 201911, rankear estrategias en 201912 y reentrenar con 201901–201912, como propone F2, requiere etiquetas que dependen de 202001–202002. Bajo F1 esos meses quedan fuera del período autorizado. F2 parece ubicarse en el momento en que llega 202002: 202001 figura como "sin BAJA+2 todavía", así que 201912 ya tendría clase. F1, en cambio, fija el corte en 201912.

**Decisión hasta que la cátedra aclare:** **queda pendiente de aclaración** cualquier esquema de entrenamiento, validación o test que dependa de etiquetas de 201911 o 201912. Mientras tanto, el código deja las ventanas configurables y sólo se trabaja con meses de etiqueta completa dentro de 2019 (201901–201910).

**Qué haría falta exactamente.** Solo la **lista de clientes** (`numero_de_cliente`) de 202001 para noviembre y de 202001–202002 para diciembre, sin ninguna feature de 2020. Detalle por mes en `PLAN_PRUEBAS.md` § 1.

**Pregunta para Zulip:** "Para etiquetar 201911 y 201912, ¿se puede usar solo la presencia de cada cliente en 202001 y 202002, o el período autorizado excluye cualquier información posterior a 201912, incluida esa presencia?"

## Observación de clase sobre meses posteriores (alcance a aclarar)

Se registra aparte porque no está claro cómo se combina con R1. En clase se comentó que se pueden **explorar comportamientos en meses posteriores** a 201912.

| Punto | Estado |
|---|---|
| Autor, fecha y texto literal | **A completar** |
| ¿Exploración descriptiva (drift, distribución de variables, nulos) de 2020 en adelante? | Sin aclarar |
| ¿Puede influir en features, imputaciones o reglas de incidentes? | Sin aclarar |
| ¿Puede influir en la selección de modelos, hiperparámetros o cortes? | **No, por R1**, salvo aclaración explícita en contrario |
| ¿Incluye los meses de ensayo 202001–202006? | Sin aclarar |

Hasta que se aclare, toda exploración posterior a 201912 queda en `docs/` como observación, separada de las decisiones. No se usan etiquetas de 2020.

## Otros puntos sin confirmar

- Si `enviar` es 0/1, el separador y si la salida lleva a todos los clientes o sólo a los enviados (F1 literal).
- Si la entrada del vivo mantiene el esquema y el orden de columnas del crudo (hoy un cambio de orden se rechaza).
- Qué máquina se usa en vivo ("laptop" según F2) y si el entorno se puede preparar antes.
- Datos externos (IPC): F2 los menciona en el mapa ("+ datos externos (IPC)") y pregunta qué hacer con el drift en pesos. No se sabe si son obligatorios.
- **Ganancia de C02 sin fuente propia.** Se usan los importes del material del curso para C01: premio bruto 1.100.000, costo por envío 27.500, ganancia neta por acierto 1.072.500 (`GANANCIA.md`). Si C02 cambia la escala pero no la razón 1/40, los cortes no cambian.
- Los enlaces a los repos de alumnos de la competencia 01 (en Zulip).

## Preguntas de diseño de F2

Las cinco preguntas de la presentación sirven para ordenar el diseño: historia, features, entrenamiento, producción y reporte. Las respuestas se van registrando en `docs/TAREAS.md` § Brechas.
