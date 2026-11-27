# Proposal

## Why

El pipeline calcula solo lags y deltas de orden 1 y 2. En el postmortem de la Primera Competencia, las variables de
tendencia fueron la única técnica que pasó la corrección por comparaciones múltiples: 6 de 21 en el Purgatorio contra
33 de 45 (`docs/antecedentes/competencia-1/backlog.md`, prioridad 1). Quedó afuera de `esqueleto-del-pipeline` desde
la primera versión.

## What Changes

- **Tendencia**: pendiente sobre ventanas de 3 a 6 meses (`regr_slope` contra `foto_mes`, no contra
  `cliente_antiguedad`, que se resetea), redondeada.
- **Ventana**: promedios, mínimos y máximos (van con las tendencias; evidencia más débil).
- **Evento**: meses desde el último movimiento, primera vez en cero, aguinaldo en junio y diciembre (en la Primera el
  aguinaldo corregido dio ruido; revisar solo si junio importa).
- **Lags por mes calendario** en vez de por fila: hoy un cliente con un mes salteado recibe como lag 1 su observación
  de dos meses atrás (14 a 24 clientes por mes en el ensayo). Es la prueba E05 del plan del equipo y exige reentrenar.
- **Lag 2 selectivo** sobre una lista de variables estables (backlog, prioridad 2).
- **Canaritos** para podar las variables que no aportan, si la cantidad pone en riesgo el tiempo.
- Todo dentro de la única definición de variables (`features.py`), con la prueba de igualdad entre entrenamiento y
  producción repetida, y el tratamiento de variables rotas aplicado antes: una ventana de 6 meses hereda un mes roto
  durante 6 meses.
- Las ventanas largas cambian cuánta historia lee la corrida y cuánto tarda: medirlo en la VM.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `historia-y-features`: más familias de variables y lags por calendario.
- `calidad-de-datos`: cuántos meses hereda una ventana el tratamiento de una variable rota.

Las dos capacidades las crea `esqueleto-del-pipeline`.

## Impact

- **Código**: `features.py` y la lista de predictores del catálogo; todos los modelos se reentrenan.
- **Referencia**: `docs/antecedentes/competencia-1/codigo/fe_panel.py` (se copia lo que sirva, no se importa).
