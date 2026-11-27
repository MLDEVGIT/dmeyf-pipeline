# Spec Delta

## Purpose

Mantiene la historia de los clientes mes a mes y calcula las variables del modelo de una única manera, para que el
entrenamiento y la producción vean exactamente los mismos números.

## ADDED Requirements

### Requirement: Historia por mes
El sistema SHALL guardar cada mes recibido como una unidad independiente de la historia, con los tipos de columna
fijados, y SHALL poder leer cualquier subconjunto de meses y columnas sin cargar el resto.

#### Scenario: Agregar un mes
- **WHEN** se procesa un mes nuevo
- **THEN** la historia contiene ese mes y los meses anteriores quedan sin modificar

#### Scenario: Carga inicial
- **WHEN** se ejecuta la carga inicial con el dataset del curso hasta 201912
- **THEN** la historia contiene los doce meses de 2019 y ninguno posterior

### Requirement: Esquema de columnas estable
El sistema SHALL comparar las columnas de cada mes entrante con el esquema de la historia y SHALL rechazar el mes,
sin guardar nada, cuando difieren.

#### Scenario: Esquema distinto
- **WHEN** el archivo trae una columna que no está en el esquema, le falta una o las trae en otro orden
- **THEN** el mes no entra en la historia y el registro nombra las columnas que difieren

#### Scenario: Valor crudo en la historia
- **WHEN** un mes llega con variables rotas
- **THEN** la historia guarda los valores tal como llegaron, y el tratamiento se aplica al calcular las variables

### Requirement: Un solo cálculo de variables
El sistema SHALL calcular las variables con una única definición, usada tanto por la fábrica de modelos como por la
corrida mensual, e identificada por una versión que acompaña a cada modelo del catálogo.

#### Scenario: Igualdad entre entrenamiento y producción
- **WHEN** se calculan las variables de un mes de 2019 por el camino de la fábrica y por el de la corrida mensual
- **THEN** los dos resultados son iguales valor por valor

#### Scenario: Variables que no coinciden con el catálogo
- **WHEN** los nombres, el orden o los tipos de las variables calculadas difieren de los que declara el catálogo
- **THEN** la corrida termina con error antes de puntuar y nombra las diferencias

### Requirement: Cálculo incremental
El sistema SHALL calcular las variables solo del mes nuevo, sin recalcular las de los meses ya procesados, y el
resultado SHALL ser igual al de calcular todo desde cero.

#### Scenario: Mes nuevo
- **WHEN** se procesa un mes
- **THEN** solo se calculan y se guardan las variables de ese mes, y son iguales a las de calcular todo desde cero

#### Scenario: Cliente sin historia
- **WHEN** un cliente aparece por primera vez en el mes
- **THEN** sus variables históricas quedan como faltantes y el cliente recibe puntaje igual que el resto

#### Scenario: Cliente con un mes salteado
- **WHEN** a un cliente le falta un mes intermedio en la historia
- **THEN** sus variables históricas usan su observación anterior, como en el entrenamiento, y la corrida informa
  cuántos clientes están en ese caso

### Requirement: Clases que maduran
El sistema SHALL calcular la clase ternaria de cada mes con una única regla, usada en el entrenamiento, la evaluación y
el seguimiento: un cliente del mes M es CONTINUA si está en M+2, BAJA+2 si está en M+1 y no en M+2, y BAJA+1 si no
está en ninguno de los dos. Ninguna clase de M SHALL darse por definitiva antes de recibir M+2.

#### Scenario: Llega el mes M
- **WHEN** se procesa el mes M
- **THEN** quedan definidas las clases del mes M−2 y ningún mes posterior a M−2 figura con clases definitivas

#### Scenario: Cliente que vuelve
- **WHEN** un cliente del mes M falta en M+1 y vuelve en M+2
- **THEN** su clase en M es CONTINUA

#### Scenario: Mes con un solo mes posterior
- **WHEN** de M solo se recibió M+1
- **THEN** los ausentes en M+1 se informan aparte como provisionales y M no tiene clases ni métricas definitivas
