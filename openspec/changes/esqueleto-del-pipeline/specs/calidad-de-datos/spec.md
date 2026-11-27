# Spec Delta

## Purpose

Detecta las variables que llegan rotas en un mes (por ejemplo, todas en cero) o que cambian de régimen, las trata de
la misma manera en la historia y en los meses nuevos, y deja evidencia para que el reporte lo muestre.

## ADDED Requirements

### Requirement: Detección de variables rotas
El sistema SHALL medir, para cada variable de cada mes, la proporción de ceros y de faltantes, y SHALL marcar la
variable como rota en ese mes cuando esas proporciones se apartan de las de sus meses anteriores más allá de umbrales
configurados.

#### Scenario: Variable toda en cero
- **WHEN** una variable que en los meses anteriores tenía menos del 95 % de ceros llega con más del 99,9 % de ceros
- **THEN** queda marcada como rota en ese mes

#### Scenario: Variable que siempre fue casi toda cero
- **WHEN** una variable llega casi toda en cero y en sus meses anteriores también lo estaba
- **THEN** no se marca como rota

#### Scenario: Meses conocidos de la historia
- **WHEN** se corre la detección sobre la historia de 2019
- **THEN** quedan marcadas las variables de rentabilidad y comisiones de 201905 y de 201910

### Requirement: Umbrales fijados con 2019
El sistema SHALL tomar los umbrales de detección de una configuración versionada, definida solo con los meses
201901–201912.

#### Scenario: Umbrales versionados
- **WHEN** se consulta qué umbrales usó una corrida
- **THEN** el registro indica la versión de la configuración y esa configuración está en el repositorio

### Requirement: Tratamiento de variables rotas
El sistema SHALL aplicar a los valores de una variable rota, en el mes en que está rota y antes de calcular las
variables derivadas, un único tratamiento (reemplazarlos por faltante o por el último valor conocido del cliente),
elegido con meses de 2019, y SHALL aplicar el mismo tratamiento a la historia que usa la fábrica de modelos.

#### Scenario: Derivadas de una variable rota
- **WHEN** una variable está rota en el mes M
- **THEN** su valor en M y sus variables históricas en M+1 y M+2 que dependen de M se calculan con el valor tratado,
  no con el cero que llegó

#### Scenario: Mismo tratamiento en entrenamiento
- **WHEN** la fábrica de modelos arma el conjunto de entrenamiento con un mes que tiene variables rotas
- **THEN** esas variables figuran tratadas en ese mes, igual que en la corrida mensual

#### Scenario: El mes anterior también está roto
- **WHEN** una variable está rota en M y también lo estaba en M−1
- **THEN** el tratamiento no toma como valor conocido el de un mes roto

#### Scenario: Tratamiento elegido con 2019
- **WHEN** se consulta por qué se aplica ese tratamiento y no otro
- **THEN** hay un experimento versionado que inyecta variables rotas en meses de 2019, compara no tratar, faltante y
  último valor, y tiene la regla de decisión escrita antes de correrlo

### Requirement: La corrida no se detiene por datos rotos
El sistema SHALL completar la corrida aunque haya variables rotas, con la misma estrategia recomendada, y SHALL marcar
el mes como degradado cuando la cantidad de variables rotas que usa esa estrategia supera un límite configurado.

#### Scenario: Pocas variables rotas
- **WHEN** llegan variables rotas por debajo del límite
- **THEN** la corrida termina con la estrategia recomendada y un aviso

#### Scenario: Muchas variables rotas
- **WHEN** las variables rotas superan el límite
- **THEN** la corrida termina con la estrategia recomendada, y el registro y el reporte marcan el mes como degradado
  con la lista de variables

#### Scenario: Variable rota en cualquier columna
- **WHEN** llega rota una variable que nunca lo había estado
- **THEN** se detecta y se trata igual que las que ya se rompieron en la historia

### Requirement: Cambio de régimen
El sistema SHALL distinguir una variable rota en meses aislados de una que queda en el estado nuevo durante varios
meses seguidos, y SHALL marcar a esta última como cambio de régimen.

#### Scenario: Variable que queda en cero
- **WHEN** una variable lleva tres meses seguidos marcada como rota
- **THEN** pasa a figurar como cambio de régimen, deja de arrastrarse un valor anterior y el reporte la lista aparte

### Requirement: Evidencia por variable y mes
El sistema SHALL guardar, para cada variable y mes procesado, la proporción de ceros, la proporción de faltantes, una
medida de corrimiento de la distribución respecto de los meses de referencia y la decisión tomada.

#### Scenario: Consulta de un mes
- **WHEN** se consulta la calidad de datos de un mes procesado
- **THEN** hay una fila por variable con sus proporciones, su corrimiento y si fue tratada
