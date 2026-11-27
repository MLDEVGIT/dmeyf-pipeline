# Proposal

## Why

El criterio de exploración pide estrategias propias y justificadas, lejos de la receta del baseline. Las dos del
catálogo son un binario y un multiclase con variables básicas. `docs/antecedentes/competencia-1/podio.md` y
`backlog.md` tienen leídos del código los mecanismos de los tres primeros de la Primera Competencia. Quedó afuera de
`esqueleto-del-pipeline` desde la primera versión.

## What Changes

Candidatas, a elegir una o dos y medir con 2019 contra el catálogo vigente, con semillas pareadas:

- **Multiclase con segunda etapa** y BAJA+1 y BAJA+2 tratadas distinto. El equipo ya midió una variante (multiclase con
  BAJA+1 a peso 0,5 contra 1, prueba E02) y no la adoptó.
- **Un modelo por profundidad de historia**: los clientes sin lags o con pocos meses van a un modelo propio.
- **Rangos de cero fijo** por mes para los montos (positivos en (0,1], negativos en [−1,0), el cero queda cero).
  Se superpone con `correccion-por-inflacion`: decidir cuál de las dos.
- **Ensamble por rango** de 20 o más semillas, en vez de promedio de probabilidades.
- **Submuestreo de CONTINUA distinto por semilla** (`pos_bagging_fraction` / `neg_bagging_fraction`).
- **El corte por la meseta y no por el pico**, la «regla del margen» del postmortem: no pasar de la última banda de
  1.000 clientes cuya tasa de BAJA+2, con cota inferior entre meses, supera 2,5 %. Era la política de corte del plan
  original; el equipo usa una fracción por arrepentimiento mínimo. Compararlas con las curvas de 2019.
- **Umbral sobre probabilidad calibrada** en vez de fracción fija: en 202002, con pocas bajas, la fracción envió cuatro
  veces más que el mejor corte posible.

Cada estrategia nueva tiene que entrar en el tiempo de la corrida y traer su política de corte.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `fabrica-de-modelos`: estrategias y políticas de corte nuevas en el catálogo.
- `corrida-mensual`: más de dos estrategias por corrida.

Las dos capacidades las crea `esqueleto-del-pipeline`.

## Impact

- **Código**: el catálogo y `mensual.py`, que hoy exigen exactamente una recomendación y una alternativa.
- **Referencia**: `docs/antecedentes/competencia-1/codigo/` y las fichas de `postmortem_vercel/`.
