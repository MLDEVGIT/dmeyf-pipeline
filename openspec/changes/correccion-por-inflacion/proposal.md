# Proposal

## Why

Los montos están en pesos corrientes y el modelo se entrena con 2019 para puntuar hasta 202009: la misma cifra no
significa lo mismo veinte meses después. Las láminas de la cátedra lo plantean como pregunta («¿qué hago con el drift
en pesos?») y mencionan datos externos (IPC). Quedó afuera de `esqueleto-del-pipeline` desde la primera versión.

**Evidencia en contra (experimentos del lunes, nov-2026).** Tres grupos lo probaron por separado y ninguno ganó plata
(Inflación_1 e inflacion2 en test 201910; autoresearch en validación 201908):

- Inflación_1: un deflactor por grupo de variables contra IPC único y contra no deflactar: no mejora la ganancia, solo
  estabiliza los resultados entre semillas; el mes base del índice no cambia nada.
- inflacion2: IPC fue lo peor (unos 8 M menos que no corregir); dividir por la mediana del mes o pasar a ranking no le
  ganó a no corregir, aunque baja mucho el corrimiento (PSI).
- autoresearch: reemplazar los montos por su percentil dentro del mes empeoró en las cuatro corridas que lo hicieron
  (−3,10 a −12,20 M); dividir límites por la mediana, −2,05 M. Como **complemento** sí sumó: agregar el percentil sin
  sacar el nominal, +0,37 M; promediar 50/50 los rangos del modelo vigente y uno igual con percentiles, +3,94 M.

Por eso este cambio queda **al final de la cola** y con el alcance reducido: no se reemplazan montos; a lo sumo se
agregan versiones por mes junto al nominal, o se ensambla un modelo con montos por mes. Si no hay tiempo, se descarta
citando esta evidencia.

## What Changes

- Medir primero cuánto hay: el PSI de los montos contra 2019, que el reporte de `esqueleto-del-pipeline` ya guarda.
- Alternativas a comparar con 2019 (entrenar en los primeros meses, evaluar en los últimos):
  - **deflactar** con un índice externo (IPC), que en producción tiene que estar disponible para el mes que llega;
  - **escala por mes** sin datos externos: rangos de cero fijo o percentil con signo (ver `estrategias-del-podio`);
  - **razones** entre montos del mismo mes.
- La transformación entra en la única definición de variables y se aplica igual en entrenamiento y en producción.
- Si usa un dato externo, el pipeline no puede caerse cuando el dato del mes falta: regla de qué se usa entonces.
- **Registro de la mejora**: cada alternativa medida es una fila del registro común de mejoras (`docs/MEJORAS.md`,
  definido en `peso-de-baja1`), se adopte o no; un «no mejora» bien medido también queda.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `historia-y-features`: los montos pasan por una transformación de escala antes de las variables derivadas.

La capacidad la crea `esqueleto-del-pipeline`.

## Impact

- **Código**: `features.py`; todos los modelos se reentrenan.
- **Datos**: eventualmente una tabla de IPC versionada en el repo.
