# Proposal

## Why

`esqueleto-del-pipeline` tiene una regla de degradación: si las variables rotas que usa la estrategia recomendada
superan un límite, la recomendación pasa a la de respaldo. En ese cambio el respaldo es la otra estrategia, que usa las
mismas variables y se rompe igual: en 202006 la coincidencia entre las dos cayó de 0,72 a 0,46 y los scores de ambas se
corrieron hacia arriba. Un respaldo de verdad no puede depender de lo que se rompió.

## What Changes

- Un modelo **sin variables históricas** (sin lags ni deltas): un mes roto no le contamina M+1 ni M+2.
- Evaluar con 2019, inyectando el patrón de variables rotas, si conviene además un modelo entrenado **sin las variables
  que alguna vez llegaron rotas** (rentabilidad, comisiones, márgenes, contadores de transacciones).
- La regla de degradación apunta a este modelo; el límite que la dispara se calibra con 2019.
- El reporte muestra, en los meses degradados, qué habría recomendado la estrategia normal.
- **Registro de la mejora**: el respaldo se mide en dos situaciones, meses sanos y meses con variables rotas inyectadas,
  y cada una es una fila del registro común de mejoras (`docs/MEJORAS.md`, definido en `peso-de-baja1`): lo que pierde
  en meses sanos y lo que salva en los rotos. La de meses rotos queda con `sumable = no`.
- Relacionado: «un modelo por profundidad de historia» (`estrategias-del-podio`) resuelve el caso del cliente sin
  historia con la misma idea; conviene decidir los dos juntos.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `calidad-de-datos`: la estrategia de respaldo deja de compartir variables con la recomendada.
- `fabrica-de-modelos`: el catálogo gana el modelo de respaldo.

Las dos capacidades las crea `esqueleto-del-pipeline`.

## Impact

- **Código**: una tercera entrada en el catálogo (hoy `mensual.py` exige exactamente una recomendación y una
  alternativa) y su conjunto de variables.
- **Tiempo**: un modelo más para puntuar, salvo que se puntúe solo cuando hay degradación.
