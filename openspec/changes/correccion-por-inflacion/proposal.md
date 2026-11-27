# Proposal

## Why

Los montos están en pesos corrientes y el modelo se entrena con 2019 para puntuar hasta 202009: la misma cifra no
significa lo mismo veinte meses después. Las láminas de la cátedra lo plantean como pregunta («¿qué hago con el drift
en pesos?») y mencionan datos externos (IPC). Quedó afuera de `esqueleto-del-pipeline` desde la primera versión.

## What Changes

- Medir primero cuánto hay: el PSI de los montos contra 2019, que el reporte de `esqueleto-del-pipeline` ya guarda.
- Alternativas a comparar con 2019 (entrenar en los primeros meses, evaluar en los últimos):
  - **deflactar** con un índice externo (IPC), que en producción tiene que estar disponible para el mes que llega;
  - **escala por mes** sin datos externos: rangos de cero fijo o percentil con signo (ver `estrategias-del-podio`);
  - **razones** entre montos del mismo mes.
- La transformación entra en la única definición de variables y se aplica igual en entrenamiento y en producción.
- Si usa un dato externo, el pipeline no puede caerse cuando el dato del mes falta: regla de qué se usa entonces.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `historia-y-features`: los montos pasan por una transformación de escala antes de las variables derivadas.

La capacidad la crea `esqueleto-del-pipeline`.

## Impact

- **Código**: `features.py`; todos los modelos se reentrenan.
- **Datos**: eventualmente una tabla de IPC versionada en el repo.
