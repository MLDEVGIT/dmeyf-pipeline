# Spec Delta

## Purpose

Permite ensayar el pipeline igual que se va a operar en clase, probarlo rápido en una notebook, y garantiza que los
meses que no deben influir en las decisiones se miren pocas veces y quede constancia de cada vez.

## ADDED Requirements

### Requirement: Ensayo mes a mes
El sistema SHALL ofrecer un comando que, a partir del dataset del curso, genera los archivos mensuales sin clase, los
copia de a uno en `input/` y ejecuta la corrida mensual de cada uno, en orden, por el mismo camino que una corrida real.

#### Scenario: Ensayo de la consigna
- **WHEN** se ejecuta el ensayo de 202001 a 202006 desde un estado limpio
- **THEN** quedan seis archivos de salida, seis corridas exitosas y el reporte con seis meses

#### Scenario: Archivos sin clase
- **WHEN** el ensayo genera el archivo de un mes
- **THEN** el archivo no tiene columna de clase ni ninguna columna derivada de meses posteriores

### Requirement: El ensayo no define nada
El sistema SHALL tratar las métricas con clase de 202001–202006 como seguimiento, y SHALL NOT usar esos meses para
elegir modelos, variables, hiperparámetros ni cortes.

#### Scenario: Cambio de un corte
- **WHEN** se cambia el corte de una estrategia del catálogo
- **THEN** el catálogo cita como fuente un resultado calculado solo con meses de 2019

#### Scenario: Ganancia del ensayo
- **WHEN** el reporte muestra la ganancia realizada de un mes del ensayo
- **THEN** la corrida de ese mes y las siguientes usan los mismos modelos y cortes que antes de conocerla

### Requirement: Muestra de prueba
El sistema SHALL poder ejecutar el ensayo y la fábrica sobre una muestra reducida de clientes, con el mismo código y la
misma configuración que la versión completa salvo el tamaño.

#### Scenario: Ensayo corto
- **WHEN** se ejecuta el ensayo con la muestra de prueba en una notebook de 16 GB
- **THEN** termina en pocos minutos y pasa por todas las etapas

### Requirement: Entorno reproducible para cada integrante
El sistema SHALL poder instalarse y ensayarse desde una copia limpia del repo con los comandos documentados en el
README, sin rutas ni credenciales propias de una persona.

#### Scenario: Integrante nuevo en una VM limpia
- **WHEN** un integrante sigue el README en una VM recién creada
- **THEN** completa la instalación, la descarga del catálogo y el ensayo de 202001 a 202006 sin ayuda

### Requirement: Meses reservados
El sistema SHALL negarse a procesar meses de 202007 en adelante tomados del dataset del curso, salvo por el comando de
medición eventual; los archivos entregados en `input/` por la cátedra se procesan normalmente.

#### Scenario: Ensayo que pasa de 202006
- **WHEN** se pide un ensayo que incluye 202007
- **THEN** el comando termina con error e indica que ese mes es reservado

### Requirement: Mediciones eventuales contadas
El sistema SHALL registrar cada medición eventual sobre meses reservados con su fecha, quién la corrió, la versión del
código, los meses mirados y el motivo declarado antes de correrla, y SHALL rechazarla cuando se alcanzó el máximo
configurado.

#### Scenario: Medición declarada
- **WHEN** se ejecuta una medición eventual con un motivo y el código commiteado
- **THEN** corre sobre un entorno aparte, queda registrada y el reporte muestra cuántas mediciones se hicieron y cuándo

#### Scenario: Medición sin motivo o con código sin commitear
- **WHEN** se ejecuta una medición eventual sin motivo o con cambios sin commitear
- **THEN** el comando termina con error y no mira ningún mes reservado

#### Scenario: Tope alcanzado
- **WHEN** ya se hizo el máximo de mediciones configurado
- **THEN** el comando termina con error

### Requirement: Mediciones separadas de producción
El sistema SHALL mantener los resultados de ensayos y de mediciones eventuales separados del estado de producción, de
modo que no cambien la historia, las salidas ni el reporte de las corridas reales.

#### Scenario: Medición eventual y luego corrida real
- **WHEN** se hace una medición eventual sobre 202010 y después se procesa en producción un mes anterior
- **THEN** la corrida real no usa nada generado por la medición
