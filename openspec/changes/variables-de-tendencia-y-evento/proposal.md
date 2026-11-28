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
- **Evidencia de los experimentos del lunes (nov-2026; hipótesis, no hechos).** En autoresearch (validación 201908,
  contra el modelo vigente de cada corrida), casi todo lo agregado empeoró (5 de 160 pruebas se mantuvieron):
  - En contra: promedio, máximo y mínimo de 3 meses −4,75 M; lag 3 y medias móviles −1,19 a −2,93 M; combinar dos
    bloques que solos daban poco −9,05 M. Las ventanas de **nivel** (promedio, mínimo, máximo) pasan a la cola; las de
    **variabilidad** (desvío, coeficiente de variación) siguen como candidatas por lo que sigue.
  - A favor: cambio relativo contra 1 y 2 meses antes, (x − x₋ₖ) / (|x₋ₖ| + 1), +2,95 M; coeficiente de variación de 3
    meses de los montos +2,76 M; cuántas veces subió contra 1 y 2 meses antes +2,68 M; desvío de 3 meses de los montos
    +1,71 M; 23 razones del mismo mes (sumas Visa + Master, saldo/límite, consumo/límite, pagado/saldo, totales de
    productos) +3,22 M. Se suman como candidatas junto a la tendencia.
  - Sacar variables en masa empeoró (mediana −5,96 M en 242 recortes; sacar las de más PSI −2,99 M); solo funcionó,
    en una corrida, quedarse con las que acumulan el 95 % de la importancia calculada con validación interna (+2,36 M)
    o el 99 % (+1,35 M). Los canaritos
    se miden, no se asumen.
  - Features Históricos: una historia curada de 30 variables elegida por importancia; el grupo dejó pendiente volver a
    elegirla en cada reentrenamiento. Es la variante del «lag 2 selectivo».
- **Registro de la mejora**: cada familia se agrega y se mide por separado, en orden, y cada una es una fila del
  registro común de mejoras (`docs/MEJORAS.md`, definido en `peso-de-baja1`), se adopte o no.

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
