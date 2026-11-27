# Proposal

## Why

Las dos estrategias del catálogo tienen 300 rondas e hiperparámetros fijos, sin ninguna búsqueda, y «calidad de los
scores» es uno de los cuatro criterios de evaluación. El plan original de `esqueleto-del-pipeline` incluía la búsqueda
(decisión 9 y tarea 6.2); se sacó de ese cambio para dejarlo en operar el pipeline entre los tres. Es el primer cambio a
encarar después: solo necesita la fábrica reproducible (grupo 3 de `esqueleto-del-pipeline`).

## What Changes

- Búsqueda de hiperparámetros con Optuna para cada objetivo del catálogo (binario y multiclase), **sobre una muestra al
  azar del 10 %** de las filas y con el modelo final entrenado con todas. En Sampling_1 (2019, test 201910) eso no
  perdió y fue unas 8 veces más rápido; acá es una hipótesis a volver a medir, no un hecho.
- El estudio es **reanudable**: interrumpirlo y retomarlo no repite pruebas (requisito «Fábrica reanudable»).
- Meses: solo 201901–201912, con los roles del equipo (entrenamiento 201903–201906, elección en 201908–201909, 201910
  reservado). El plan original validaba en 201908 y usaba 201910 como test; hay que decidir si la búsqueda valida en
  un mes o en los dos, y si se amplía el entrenamiento a más meses de 2019.
- **Más rondas, medidas sin reentrenar**: `Booster.predict(num_iteration=k)` da la curva de 300 a 3.000 rondas con un
  solo modelo. En la Primera Competencia 2.000 contra 1.000 rondas dio +6,8 en el privado, pareado, 19 de 20 semillas
  (`docs/antecedentes/competencia-1/backlog.md`, prioridad 1; `optuna_y_lightgbm.md`).
- La región de hiperparámetros de Abregú (hojas grandes, `min_data_in_leaf` alto, lr 0,042) como un punto inicial de
  la búsqueda (backlog, prioridad 2).
- Comparación contra el catálogo vigente con semillas pareadas, y el corte vuelto a derivar con el procedimiento de
  `PLAN_PRUEBAS.md` (los cortes dependen del modelo).
- El catálogo nuevo tiene que entrar en el tiempo: más rondas multiplican la inferencia, que ya es el 80 % del mes.
- Cómputo: hasta 4 VMs `n2-highmem-8` a la vez; el costo se anota en `docs/nube.md`.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `fabrica-de-modelos`: los hiperparámetros del catálogo pasan a salir de una búsqueda declarada y reanudable. La
  capacidad la crea `esqueleto-del-pipeline`; este cambio se especifica cuando ese esté archivado.

## Impact

- **Código**: un módulo de búsqueda en `experimentos/` o en la fábrica; el catálogo gana un campo con la fuente de los
  hiperparámetros.
- **Dependencias**: Optuna.
- **Tiempo de la corrida mensual**: hay que volver a medirlo con el catálogo nuevo.
