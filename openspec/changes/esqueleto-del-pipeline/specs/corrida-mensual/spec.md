# Spec Delta

## Purpose

Define qué pasa cuando llega un mes nuevo: qué archivo entra, qué archivo sale, qué estrategias corren y en cuánto
tiempo, de modo que cualquier integrante pueda procesar un mes con un solo comando.

## ADDED Requirements

### Requirement: Entrada mensual
El sistema SHALL procesar un mes a partir de un archivo `input/<yyyymm>.csv` separado por comas, con encabezado y sin
columna de clase, iniciando la corrida con un único comando que recibe el mes.

#### Scenario: Mes válido
- **WHEN** existe `input/202001.csv` y se ejecuta el comando de corrida para 202001
- **THEN** la corrida termina con estado exitoso y deja la salida y el reporte de ese mes

#### Scenario: Falta el archivo
- **WHEN** se ejecuta el comando para un mes cuyo archivo no está en `input/`
- **THEN** la corrida termina con error, el mensaje nombra el archivo esperado y no se escribe ninguna salida

#### Scenario: El archivo tiene otro esquema
- **WHEN** al archivo le sobra o le falta una columna respecto de la historia, o las trae en otro orden
- **THEN** la corrida se rechaza sin publicar nada y el mensaje nombra las columnas que difieren

#### Scenario: El archivo no es el del mes
- **WHEN** el archivo está vacío, trae otro mes en `foto_mes` o tiene clientes repetidos
- **THEN** la corrida se rechaza sin publicar nada y el mensaje dice qué encontró

### Requirement: Archivo de salida
El sistema SHALL escribir `output/churn_<yyyymm>.csv` separado por comas y con encabezado, con una fila por cada
cliente del archivo de entrada y las columnas `numero_de_cliente`, `probabilidad` y `enviar` (1 o 0), en un orden fijo.

#### Scenario: Una fila por cliente
- **WHEN** termina la corrida de un mes con N clientes en la entrada
- **THEN** la salida tiene N filas, sin clientes repetidos ni faltantes, y `enviar` solo toma los valores 0 y 1

#### Scenario: Salida completa o ninguna
- **WHEN** la corrida falla antes de terminar de puntuar
- **THEN** no queda un `output/churn_<yyyymm>.csv` parcial

### Requirement: Varias estrategias, una recomendación
El sistema SHALL puntuar cada mes con al menos dos estrategias y publicar en la salida la de una sola, la estrategia
recomendada, guardando los puntajes y los envíos de todas para compararlas en el reporte.

#### Scenario: Estrategias alternativas guardadas
- **WHEN** termina la corrida de un mes
- **THEN** están guardados los puntajes y la marca de envío de cada estrategia para ese mes, y la salida coincide con
  los de la recomendada

#### Scenario: Misma recomendada todos los meses
- **WHEN** un mes llega con muchas variables rotas
- **THEN** la salida sigue siendo la de la estrategia recomendada y `probabilidad` significa lo mismo que en los demás
  meses

### Requirement: Cada mes se procesa una sola vez
El sistema SHALL negarse a procesar un mes que ya está completado y SHALL exigir que los meses se procesen en orden.

#### Scenario: Segunda corrida del mismo mes
- **WHEN** se ejecuta el comando para un mes ya completado
- **THEN** la corrida no hace nada, informa que el mes ya fue procesado y la salida existente queda intacta

#### Scenario: Mes fuera de orden
- **WHEN** se pide procesar 202003 y 202002 todavía no fue procesado
- **THEN** la corrida termina con error y nombra el mes que falta

#### Scenario: Reintento después de una falla
- **WHEN** una corrida falló a mitad de camino y se vuelve a ejecutar el mismo mes
- **THEN** la corrida se completa y el resultado es igual al de una corrida sin fallas

#### Scenario: El proceso muere después de publicar
- **WHEN** el proceso muere con la salida ya publicada y el mes sin marcar como completado
- **THEN** el mes siguiente se rechaza hasta reintentar ese mes, y el reintento reconoce lo publicado, comprueba que
  está íntegro y sigue sin volver a calcular

#### Scenario: Falla después de publicar
- **WHEN** la salida del mes ya está publicada y falla la actualización del reporte o la copia de respaldo
- **THEN** la salida queda como está, y al reintentar el mes solo se ejecuta lo que faltaba

### Requirement: Corrida por etapas
El sistema SHALL ejecutar la corrida de un mes como una secuencia declarada de etapas, cada una con sus entradas y sus
salidas guardadas, de modo que una etapa se pueda ejecutar, probar y reemplazar sin modificar las demás.

#### Scenario: Etapa probada sola
- **WHEN** se ejecuta una etapa con las salidas guardadas de las anteriores
- **THEN** produce lo mismo que dentro de la corrida completa

#### Scenario: Mismos resultados que antes de ordenar en etapas
- **WHEN** se corre 202001–202006 con el mismo catálogo que la línea de base guardada antes de ordenar en etapas
- **THEN** las seis salidas son idénticas byte a byte a las de la línea de base

### Requirement: Límite de tiempo
El sistema SHALL completar la corrida de un mes, desde el inicio del comando hasta tener la salida y el reporte
actualizados, en menos de 15 minutos en una VM `n2-highmem-8`, y SHALL medir y guardar la duración de cada etapa.

#### Scenario: Corrida dentro del límite
- **WHEN** se procesa un mes del ensayo en una `n2-highmem-8`
- **THEN** la duración total registrada es menor que 15 minutos

#### Scenario: Catálogo elegido con margen
- **WHEN** se elige el catálogo de modelos para la corrida en clase
- **THEN** su tiempo por mes medido en una `n2-highmem-8` no supera la mitad del límite

### Requirement: Resultados reproducibles
El sistema SHALL producir la misma salida al procesar un mes en otro entorno con la misma entrada, la misma historia,
el mismo catálogo de modelos y la misma configuración.

#### Scenario: Mismo mes en dos entornos
- **WHEN** se procesa un mes en dos entornos sin cambiar entrada, historia, catálogo ni configuración
- **THEN** el archivo de salida es idéntico byte a byte al anterior

### Requirement: Resultado del comando
El sistema SHALL terminar cada corrida con un código de salida que distingue completado, fallido, rechazado, registro
inalcanzable y corrida reemplazada, y con un mensaje que dice qué hacer.

#### Scenario: Operador sin el tablero
- **WHEN** una corrida termina y el tablero no está disponible
- **THEN** el código de salida y el mensaje alcanzan para saber qué pasó y cuál es el comando siguiente

### Requirement: Producción con versión congelada
El sistema SHALL negarse a procesar un mes en el entorno de producción cuando el código tiene cambios sin commitear o
no corresponde a una versión etiquetada, y SHALL comprobar al empezar que la carpeta de trabajo y el registro son del
mismo entorno.

#### Scenario: Cambios sin commitear en producción
- **WHEN** se inicia una corrida de producción con cambios sin commitear
- **THEN** la corrida se rechaza sin procesar nada

#### Scenario: Carpeta de un entorno contra el registro de otro
- **WHEN** se inicia una corrida con una carpeta que no corresponde al registro al que se conectó
- **THEN** la corrida se rechaza sin procesar nada
