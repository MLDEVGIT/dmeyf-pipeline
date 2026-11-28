# Consigna de la competencia 02 (comisión lunes)

Actualizado el 28-nov-2026. Une la consigna del equipo (24-nov) con el resumen de `dmeyf-competencia-2`
(`docs/consigna.md`, 27-nov). Ante la duda manda el mensaje de Zulip de F1.

## Fuentes

| Id | Fuente | Fecha | Cómo se accedió |
|---|---|---|---|
| **F1** | Consigna de Alejandro Bolaños, `Pipeline > Consigna` (Zulip 208498) | 30-oct-2026 | Resumida por Agustina desde el mensaje; el resumen está en § Qué se entrega y § Evaluación. |
| **F2** | Presentación `pipeline-competencia-2.html` «El pipeline de la Competencia 2» (clase del 2-nov, Zulip 210002), compartida por Joaquín Aramendía | 4-nov-2026 | Archivo local `Downloads/pipeline-competencia-2.html` (sha256 `559a307b2854ed3a…`, 13 diapositivas). No se copia al repo porque es material de la cátedra; las citas de abajo son textuales. |
| F3 | Aclaraciones del baseline del experimento grupal (Zulip 208135, 211210, 211718, 212043, 212249) | 28-oct a 12-nov | `dmeyf-experimento-sampling` (bitácora). Son del experimento de sampling, no de esta competencia. |
| F4 | Libro de la Asignatura | — | Fechas del cierre de la Última Competencia. |
| F5 | Respuestas de la cátedra transmitidas por Agustina | 27-nov-2026 | Esquema de los archivos de clase; corrida y examen el mismo día. |

## Qué se entrega

Un pipeline que procesa los datos mes a mes y produce los scores para marketing y un reporte de seguimiento (F1).

| | |
| --- | --- |
| Entrada | `input/<yyyymm>.csv`, separador `,`, con encabezado, sin clase. Cada archivo se procesa una sola vez; la corrida se puede iniciar a mano |
| Salida | `output/churn_<yyyymm>.csv`, separador `,`, con encabezado: `numero_de_cliente`, `probabilidad`, `enviar` (1 o 0); columnas opcionales con valor comercial |
| Estrategias | al menos dos modelos o estrategias por corrida; una sola recomendación por cliente; las demás se comparan en el reporte |
| Tiempo | 15 minutos por mes, desde que se copia el archivo hasta que están la salida y el reporte actualizado |
| Reporte | acumulativo, se actualiza con cada mes y muestra la evolución del modelo en «producción» |
| Datos de diseño | estrategias y modelos se definen solo con 201901–201912 (201912 no tiene clase; 201911 solo BAJA+1). Se puede reentrenar dentro del pipeline mes a mes si entra en el tiempo |
| Stack | libre; «un script, o una secuencia de scripts, es una excelente elección» |

**Antes de la clase:** entorno probado, la secuencia completa 202001–202006 corrida, y el repo de GitHub compartido
con un README claro. **En la clase:** la cátedra entrega archivos equivalentes a 202007, 202008 y 202009; se copian de a
uno y se procesan mientras el tutor revisa el código, mira los reportes y pregunta por las decisiones de arquitectura.

## Evaluación

40 % de la nota de la segunda competencia, en cuatro criterios; uno puede compensar a otro (F1).

1. **Calidad de los scores**: qué tan buenos y estables; curvas de ganancia y recomendaciones.
2. **Exploración**: originalidad de las estrategias y su justificación, lejos de la receta del baseline.
3. **Medición**: qué informa el reporte y cómo. Lo estético no importa.
4. **Industrialización**: claridad del proceso, facilidad para reemplazar una parte o escalar; todo el equipo lo
   entiende y lo opera.

Además, evaluación individual de autoría: oral o escrita, sin conexión y sin LLM, con preguntas sobre el código y las
decisiones. Es el mismo encuentro que la corrida en clase, el jueves 10-dic (F5).

## Fechas

| Fecha | Qué |
| --- | --- |
| 24-nov | Presentación de experimentos en clase |
| 30-nov | Clase de dudas |
| 9-dic 23:59 | Cierre de la Última Competencia (F4) |
| 10-dic | Corrida en clase y examen individual: son el mismo encuentro (F5) |
| 13-dic | Video a Michelina Porto |

## Cuándo se conoce cada cosa

Cuando llega el mes M: se puntúa M (sin clase), se conoce BAJA+1 de M−1 y BAJA+2 de M−2. En la clase se procesan
202007, 202008 y 202009, así que la ganancia real se ve para 202005, 202006 y 202007.

## Requisitos confirmados

| # | Requisito | Fuente | Notas |
|---|---|---|---|
| R1 | Entrenamiento y definición de estrategias **sólo con datos de 201901–201912** | F1 | Período autorizado para elegir modelos, hiperparámetros y cortes. |
| R2 | Entrada `input/<yyyymm>.csv`; salida `output/churn_<yyyymm>.csv` con `numero_de_cliente,probabilidad,enviar` | F1 | Separador `,`, con encabezado, `enviar` en 1 o 0. F2 habla de `(numero_de_cliente, score)` "para afuera". |
| R3 | **Máximo 15 minutos** desde la copia del archivo de entrada hasta la salida y el reporte actualizados | F1 | F2: "≤ 15 minutos en una laptop". El reloj incluye la actualización del reporte. |
| R4 | Al menos **dos modelos o estrategias** y **una recomendación por cliente** | F1 | F2: "Aplicar N estrategias", "¿Cómo comparo varias estrategias a la vez?". |
| R5 | Entrenamiento y optimización **offline** permitidos | F1, F2 | F2: "Pipeline de entrenamiento · offline · horas o días: no importa"; "Todo lo pesado se hace en entrenamiento". |
| R6 | **Reentrenamiento mensual** permitido si entra en el tiempo | F1 | F2 lo plantea como pregunta: "¿Puedo reentrenar con el mes que acaba de tener clase?". En producción F2 dice: "no optimiza: carga modelos ya hechos (a lo sumo los recalibra)". |
| R7 | Ensayos con **202001–202006**; prueba en vivo con archivos **equivalentes a 202007–202009** | F1 | En vivo el jueves 10-dic-2026, junto con el examen (F5). |
| R8 | Los **cuatro criterios de evaluación** integran el **40 %** de la nota de la segunda competencia | F1 | Los criterios están en § Evaluación. |
| R9 | Los archivos de clase traen **las mismas columnas**: ni de más ni de menos | F5 | Sí puede haber variables rotas (todas en cero), como en 201905, 201910 y 202006. Un archivo con otro esquema se rechaza. |

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

## Dudas abiertas con el tutor

1. Fecha límite del repo (la consigna dice «a definir») y quiénes necesitan acceso. La corrida en clase es el 10-dic,
   junto con el examen.
2. Las láminas usan 201911 como validación y 201912 como test; la consigna dice que esos meses no tienen clase
   utilizable (§ Contradicción).
3. Si ajustar algo mirando el ensayo 202001–202006 cuenta como definir la estrategia con datos de 2020. Incluye el caso
   del corte del binario: se volvió a derivar solo con 2019 (2,35 %), pero lo disparó la ganancia negativa del 4,475 %
   en 202002.
4. ~~Si los «archivos equivalentes» pueden traer columnas cambiadas.~~ Respondida (F5, 27-nov): no van a traer
   columnas de más ni de menos (R9).
5. Dónde corre en clase: VM o notebook personal ("laptop" según F2), y si el entorno se puede preparar antes.
6. Si `probabilidad` puede ser P(BAJA+1 ∪ BAJA+2), como da el binario recomendado, o tiene que ser P(BAJA+2).
7. Si la salida lleva a todos los clientes del mes o sólo a los enviados (el pipeline escribe a todos).

## Otros puntos sin confirmar

- Datos externos (IPC): F2 los menciona en el mapa ("+ datos externos (IPC)") y pregunta qué hacer con el drift en pesos. No se sabe si son obligatorios.
- **Ganancia de C02 sin fuente propia.** Se usan los importes del material del curso para C01: premio bruto 1.100.000, costo por envío 27.500, ganancia neta por acierto 1.072.500 (`GANANCIA.md`). Si C02 cambia la escala pero no la razón 1/40, los cortes no cambian.
- Los enlaces a los repos de alumnos de la competencia 01 (en Zulip); la matriz de 66 fichas está en
  `docs/antecedentes/competencia-1/postmortem_vercel/`.

## Preguntas de diseño de F2

Las cinco preguntas de la presentación sirven para ordenar el diseño: historia, features, entrenamiento, producción y reporte. Las respuestas se van registrando en `docs/TAREAS.md` § Brechas.
