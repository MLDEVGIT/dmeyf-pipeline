# Spec Delta

## Purpose

Guarda de forma transaccional todo lo que ocurre en cada corrida y en cada una de sus etapas, para poder mirar una
corrida mientras avanza y reconstruir después qué pasó y con qué código.

## ADDED Requirements

### Requirement: Registro de cada corrida
El sistema SHALL registrar cada corrida con su mes, su tipo (mensual, fábrica o ensayo), quién la inició, la versión
del código, la huella del catálogo, de la configuración y del archivo de entrada, sus horas de inicio y de fin y su estado.

#### Scenario: Corrida terminada
- **WHEN** termina una corrida mensual
- **THEN** existe un registro con todos esos datos y estado completado, fallido o rechazado

#### Scenario: Código sin commitear
- **WHEN** se inicia una corrida con cambios sin commitear
- **THEN** el registro lo indica junto con la versión del código

### Requirement: Registro de cada etapa
El sistema SHALL registrar cada etapa de una corrida con su estado (pendiente, en curso, exitosa, fallida u omitida),
sus horas de inicio y de fin, las filas de entrada y de salida y el mensaje de error si falló.

#### Scenario: Etapa que falla
- **WHEN** una etapa lanza un error
- **THEN** la etapa queda fallida con el mensaje, las etapas siguientes quedan omitidas, la corrida queda fallida y no
  se publica nada del mes

#### Scenario: Etapas de una corrida exitosa
- **WHEN** termina una corrida exitosa
- **THEN** todas sus etapas figuran exitosas u omitidas y la suma de sus duraciones no supera la duración de la corrida

### Requirement: Eventos durante la ejecución
El sistema SHALL registrar eventos con hora, corrida, etapa, nivel y datos, en el momento en que ocurren y no al final
de la etapa.

#### Scenario: Consulta en vivo
- **WHEN** otra persona o proceso consulta el registro mientras una corrida está en curso
- **THEN** ve la etapa actual y los eventos ya emitidos sin bloquear ni demorar la corrida

### Requirement: Registro que solo agrega
El sistema SHALL agregar filas al registro y cambiar únicamente el estado y la hora de fin de corridas y etapas; SHALL
NOT borrar ni reescribir eventos, ni siquiera al reprocesar un mes.

#### Scenario: Reintento de un mes
- **WHEN** se reintenta un mes
- **THEN** el registro conserva la corrida anterior y agrega una nueva, y se sabe cuál es la vigente

### Requirement: Corridas interrumpidas
El sistema SHALL reconocer como interrumpida una corrida que quedó en curso sin proceso que la ejecute, y SHALL
permitir reintentarla.

#### Scenario: Proceso muerto
- **WHEN** el proceso de una corrida muere y se inicia otra corrida del mismo mes
- **THEN** la corrida anterior queda marcada como interrumpida y la nueva se ejecuta

#### Scenario: Reintento inmediato en la misma máquina
- **WHEN** el proceso de una corrida muere y se reintenta el mes en la misma máquina
- **THEN** el reintento empieza enseguida, sin esperar

#### Scenario: Corrida en otra máquina
- **WHEN** una corrida iniciada en otra máquina figura en curso y dejó de dar señales por más tiempo que el configurado
- **THEN** se da por interrumpida

#### Scenario: Señales durante una etapa larga
- **WHEN** una etapa tarda varios minutos
- **THEN** la corrida sigue dando señales y no se da por interrumpida

#### Scenario: Corrida dada por interrumpida que seguía viva
- **WHEN** una corrida fue reemplazada por otra del mismo mes y después intenta publicar
- **THEN** no publica nada y termina con error

#### Scenario: Publicación a medias
- **WHEN** un reintento encuentra piezas publicadas del mes que faltan o no coinciden con su huella registrada
- **THEN** las aparta sin borrarlas, deja constancia y recalcula el mes

### Requirement: Una sola corrida por mes a la vez
El sistema SHALL impedir que dos corridas del mismo mes y entorno estén en curso a la vez, también cuando se inician
desde máquinas distintas.

#### Scenario: Dos corridas simultáneas
- **WHEN** se inicia una corrida de un mes que ya tiene otra en curso y con señales recientes
- **THEN** la segunda se rechaza, queda registrada como rechazada y no toca ningún archivo

### Requirement: Corrida colgada
El sistema SHALL permitir a un operador tomar por la fuerza un mes cuya corrida sigue viva pero no avanza, con un
motivo que queda registrado.

#### Scenario: Toma forzada
- **WHEN** un operador libera un mes con una corrida colgada y lo reintenta
- **THEN** la corrida colgada no puede publicar, la nueva se ejecuta y el registro guarda quién liberó y por qué

### Requirement: Consulta del estado sin el tablero
El sistema SHALL ofrecer un comando que muestra el estado de cada mes y de la corrida en curso.

#### Scenario: Tablero no disponible
- **WHEN** el tablero no responde durante una corrida
- **THEN** el operador ve con un comando en qué etapa está

### Requirement: Registro inalcanzable
El sistema SHALL reintentar la conexión al registro un número acotado de veces y, si no lo logra, SHALL terminar sin
dejar el mes en un estado que no se pueda reintentar.

#### Scenario: Sin registro antes de publicar
- **WHEN** el registro deja de responder antes de la publicación
- **THEN** la corrida termina con error, no publica nada y el mes se puede reintentar

#### Scenario: Motivo de la falla sin registro
- **WHEN** el registro no responde durante una corrida
- **THEN** los eventos de la corrida, incluido el error, quedan en un archivo junto a los datos

#### Scenario: Sin registro después de publicar
- **WHEN** el registro deja de responder con la salida ya publicada
- **THEN** el reintento, con el registro otra vez disponible, reconoce lo publicado y completa el mes sin recalcular

### Requirement: Registro compartido y durable
El sistema SHALL guardar el registro fuera de la VM que corre, en un lugar que ven todos los integrantes y todas las
VMs, y SHALL dejar ahí también la historia, las salidas y el reporte de cada mes completado.

#### Scenario: VM borrada
- **WHEN** se borra la VM después de completar un mes y se crea otra
- **THEN** la VM nueva recupera el estado y procesa el mes siguiente con el mismo resultado que la anterior

#### Scenario: Otro integrante
- **WHEN** un integrante consulta el registro desde su notebook
- **THEN** ve las corridas de todos, sin copiar archivos

#### Scenario: Copia fuera de la base
- **WHEN** se completa un mes
- **THEN** queda una exportación del registro junto a los datos, suficiente para reconstruirlo en otra base
