# Proposal

## Why

La consigna permite reentrenar dentro del pipeline si entra en el tiempo, y un modelo entrenado solo con 2019 envejece:
en la clase se procesan 202007–202009. El plan original de `esqueleto-del-pipeline` tenía una segunda estrategia que se
reentrena cada mes con las clases que van madurando. Se sacó de ese cambio porque la inferencia ya ocupa el 80 % del
mes; es además una de las pocas ideas del plan que se aleja de la receta del baseline, que es lo que mide el criterio
de exploración.

## What Changes

- Una estrategia **`reajuste`**: mismos hiperparámetros que la estática, reentrenada cada mes con una ventana que
  termina en M−2, con todas las bajas y una fracción de CONTINUA con peso compensado (en Sampling_1, conservar todas las
  bajas y la mitad de CONTINUA con peso 2 no perdió; acá es hipótesis a medir) y pocas semillas.
- **Presupuesto de tiempo propio**: si el reajuste lo excede, se interrumpe limpio, la estrategia queda marcada como no
  disponible para el mes y la corrida termina con las demás.
- La fábrica fija la **receta** (hiperparámetros, ventana de meses, fracción de CONTINUA y su peso, cantidad de
  semillas) y la ensaya sobre 2019 midiendo el tiempo en la VM; en producción no se busca nada.
- En el catálogo entra como una tercera estrategia, alternativa; pasa a recomendada solo con evidencia de 2019
  (simulando la llegada de los meses dentro de 2019).
- **Registro de la mejora**: la comparación simulada en 2019 contra la estática es una fila del registro común de
  mejoras (`docs/MEJORAS.md`, definido en `peso-de-baja1`), con el tiempo de reentrenamiento medido en la VM y
  `sumable = no` (es una simulación, no el catálogo con un cambio más).
- Antes de implementarla hay que medir cuánto tarda entrenar una semilla con la ventana elegida en una `n2-highmem-8`:
  es la condición para que el cambio exista.

Tareas del plan original que vienen acá: 6.4 (receta y ensayo sobre 2019 con el tiempo) y 7.2 (reajuste con
presupuesto e interrupción limpia; prueba con presupuesto mínimo).

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `fabrica-de-modelos`: se agrega la receta de la estrategia de reajuste.
- `corrida-mensual`: se agrega el reentrenamiento con presupuesto de tiempo.

Las dos capacidades las crea `esqueleto-del-pipeline`; los requisitos que ese cambio tenía sobre el reajuste están en
`specs/` de este cambio, tal como estaban.

## Impact

- **Código**: una etapa nueva en la corrida mensual, entre las features y las estrategias; la receta en el catálogo.
- **Tiempo**: es el riesgo principal; el límite de 15 minutos no se negocia.
- **Datos**: la corrida necesita guardar las features de los meses de la ventana, no solo las del mes.
