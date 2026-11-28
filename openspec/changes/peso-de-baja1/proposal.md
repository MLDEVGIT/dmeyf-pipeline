# Proposal

## Why

El binario del catálogo trata igual a BAJA+1 y a BAJA+2 (las dos son positivas con peso 1), pero la ganancia paga solo
BAJA+2. En el experimento de autoresearch de la comisión del lunes (589 pruebas, seis corridas de agentes,
`resumen-experimentos.pdf` del 27-nov-2026), darle menos peso a BAJA+1 fue el cambio que más sumó en validación 201908
(+8,06 M con peso 0,3, contra el modelo vigente de esa corrida), y se mantuvo en las cinco corridas que lo probaron. En
el test 201910, los tres modelos finales que le ganaron al baseline entrenan con BAJA+1 a menor peso que BAJA+2; los
que entrenan solo con BAJA+2 o con pesos iguales quedaron abajo. El propio resumen lo matiza: «con seis modelos es una
pista, no una prueba», y la mediana de todas las pruebas de esa familia (clase y pesos, 26) fue −0,30 M. Nuestro E02
probó el peso 0,5 solo en el multiclase, y no se adoptó; el binario con peso nunca se midió acá.

Es barato: no cambia variables, ni la corrida mensual, ni el tiempo de inferencia; cambia solo cómo se entrenan los
modelos del catálogo.

## What Changes

- Un experimento con protocolo escrito antes de correr (en `docs/PLAN_PRUEBAS.md`, como E02): binario con el peso de
  las filas BAJA+1 en el `Dataset` de entrenamiento en **{0,3; 0,5; 1}**, con CONTINUA y BAJA+2 en 1. El brazo de peso
  1 es el binario vigente (se reutiliza si pasa las comprobaciones de reproducción, como en E02).
- Todo lo demás idéntico al catálogo vigente: 760 variables, train 201903–201906, hiperparámetros y rondas, semillas y
  tamaño del ensamble, binado, y el procedimiento de corte vigente (mínimo volumen equivalente, `PLAN_PRUEBAS.md`
  § 13–15). Desarrollo en 201908 y 201909; 201910 sigue bloqueado; nada de 2020.
- Regla de adopción escrita antes de correr, con el protocolo del catálogo vigente (no el de E01 con 5 semillas y la
  mejor fracción elegida en los mismos meses). Con tres pesos se declaran de antemano las comparaciones (cada peso
  contra 1) para no elegir el mejor de tres por azar.
- Se baja el peso de BAJA+1 y no se sube el de BAJA+2. El cociente BAJA+2 : BAJA+1 es exactamente el mismo en los dos
  casos; lo que cambia es el peso de los positivos contra CONTINUA. Bajar BAJA+1 deja CONTINUA y BAJA+2 exactamente
  como en el catálogo vigente, así la única diferencia con el brazo de peso 1 son las filas BAJA+1.
- **El significado del score cambia.** Hoy la columna `probabilidad` de la salida es P(BAJA+1 ∪ BAJA+2) (decisión 9 de
  `esqueleto-del-pipeline` y el campo `score` del catálogo). Con BAJA+1 a 0,3 deja de serlo: es un score de un objetivo
  ponderado, más bajo. El corte por fracción de clientes no depende de la escala, pero los cortes se vuelven a derivar,
  y la salida, el reporte y el catálogo tienen que decir qué significa el score.
- Si se adopta, el binario con peso reemplaza al binario en el catálogo y el multiclase se vuelve a comparar contra el
  nuevo binario. Que el binario con peso pase a ser la **alternativa** en vez del multiclase es una decisión aparte: en
  autoresearch el multiclase perdió entre 5,8 y 7,5 M contra el binario en las tres pruebas (validación 201908).
- **Registro de la mejora**: el resultado se agrega como una fila al registro común de mejoras (ver Impact), se adopte
  o no.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `fabrica-de-modelos`: el entrenamiento del binario admite un peso por clase declarado en el catálogo.
- `corrida-mensual`: el significado de la columna `probabilidad` y del score en el reporte pasa a salir del catálogo.

Las dos capacidades las crea `esqueleto-del-pipeline`; este cambio se especifica cuando ese esté archivado.

## Impact

- **Código**: el armado del `Dataset` binario (hoy `experimentos/ce02_entrenar.py`, con `label=(ctr > 0)`) recibe
  `weight`; el manifiesto del catálogo gana un campo `pesos_clase` y actualiza `score`. La corrida mensual no cambia de
  cálculo: los pesos solo existen al entrenar.
- **Tiempo**: el de entrenar dos brazos nuevos en la VM; la inferencia es la misma.
- **Riesgo de interpretación**: `min_data_in_leaf` cuenta filas, no pesos; el hiperparámetro que mira pesos es
  `min_sum_hessian_in_leaf`. Con hiperparámetros fijos, un peso distinto podría pedir otros (limitación declarada, igual
  que en E02).
- **Congelamiento**: un catálogo nuevo invalida los tiempos, los cortes y el ensayo 202001–202006 (decisión 9 y tarea
  7.7 de `esqueleto-del-pipeline`). Este cambio entra antes del congelamiento o después, repitiendo cortes, tiempo y
  ensayo; se decide al priorizarlo.

## Registro de mejoras (común a todos los cambios)

Para ver qué mejoró el modelo, cada cambio que se mide deja una fila en `docs/MEJORAS.md`. Lo crea el primer cambio
que se aplique; como es común a todos, conviene que el formato pase a `esqueleto-del-pipeline` o a una spec propia.

- **Fila 0**: el catálogo de partida, con su ganancia en 201908 y 201909. Es el catálogo congelado por la tarea 7.7 de
  `esqueleto-del-pipeline` (con el tratamiento de variables rotas); hasta que exista, el vigente, nombrado.
- **Un protocolo para todas las filas**: el del catálogo vigente (tamaño del ensamble, semillas, procedimiento de corte
  de `PLAN_PRUEBAS.md` § 13–15, meses 201908 y 201909). Si el protocolo cambia, se vuelve a medir la fila 0 y se abre
  una sección nueva: diferencias medidas con protocolos distintos no se suman.
- **Columnas**: cambio y experimento; catálogo de referencia y candidato; ganancia del ensamble y su diferencia en
  201908 y en 201909; semillas con diferencia pareada positiva; diferencia de AUC de BAJA+2; diferencia de tiempo de
  la corrida; adoptado (sí/no); sumable (sí/no); archivo de `resultados/` que lo respalda.
- **En orden, no en paralelo**: la diferencia es siempre contra el catálogo vigente en ese momento. Si dos candidatos
  se miden contra la misma referencia y se adoptan los dos, el segundo se vuelve a medir sobre el primero antes de
  anotarlo como sumable. Así la suma de las filas adoptadas y sumables, en orden, es la mejora total.
- **No sumables**: las mediciones que no son «el catálogo con un cambio más» (meses con variables rotas inyectadas,
  reajuste simulado, diagnósticos) quedan con `sumable = no`.
