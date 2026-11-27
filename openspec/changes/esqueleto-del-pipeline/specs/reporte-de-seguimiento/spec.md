# Spec Delta

## Purpose

Muestra, mes tras mes, cómo se comportan los modelos y los datos en producción y cómo va cada corrida, para que quien
lo mire pueda decidir si confiar en los scores, cambiar de estrategia o reentrenar.

## ADDED Requirements

### Requirement: Reporte acumulativo actualizado en cada corrida
El sistema SHALL actualizar el reporte como parte de la corrida mensual, de modo que al terminar un mes el reporte
incluya ese mes y todos los anteriores, y SHALL dejar una copia en un único archivo que se abre sin servidor ni conexión.

#### Scenario: Después de seis meses
- **WHEN** se procesaron 202001 a 202006
- **THEN** el reporte muestra los seis meses en cada serie y la corrida no terminó hasta que estuvo actualizado

#### Scenario: Copia sin servidor
- **WHEN** se abre el archivo del reporte en una máquina sin conexión
- **THEN** se ven las mismas métricas que en el tablero, con sus gráficos

### Requirement: Lectura desde tablas agregadas
El reporte SHALL leer solo tablas agregadas, derivadas del registro y de los datos guardados, que se actualizan una
vez publicado el mes y únicamente para los meses que cambiaron: el que se procesó y el que maduró su clase.

#### Scenario: Reconstrucción completa
- **WHEN** se ejecuta el comando que vacía y reconstruye las tablas agregadas
- **THEN** el contenido es igual al que dejaron las actualizaciones incrementales

#### Scenario: Actualización repetida
- **WHEN** la actualización de las tablas agregadas se vuelve a ejecutar para el mismo mes
- **THEN** las tablas no tienen filas duplicadas y el contenido es el mismo

#### Scenario: Corrida que falla
- **WHEN** una corrida falla antes de publicar
- **THEN** las tablas agregadas no tienen ninguna fila de ese mes

#### Scenario: Reporte coherente con lo publicado
- **WHEN** el reporte incluye un mes
- **THEN** la salida y la historia de ese mes existen y coinciden con la huella registrada

### Requirement: Tablero con dirección fija
El tablero SHALL poder abrirse desde cualquier navegador con un enlace, sin acceso a la VM ni herramientas instaladas,
y SHALL mostrar solo agregados y eventos, nunca datos por cliente. La copia guardada del reporte SHALL tener también su
enlace.

#### Scenario: Alguien de afuera del equipo
- **WHEN** el tutor abre el enlace del tablero desde su máquina
- **THEN** ve las corridas y el reporte sin iniciar sesión ni instalar nada

#### Scenario: Error que nombra a un cliente
- **WHEN** una corrida falla con un mensaje que incluye un número de cliente, o registra quién la corrió
- **THEN** el tablero público no muestra el número de cliente, el detalle del error ni datos de la persona

#### Scenario: Datos privados
- **WHEN** alguien sin sesión pide la historia, las salidas o la exportación del registro
- **THEN** el pedido se rechaza

#### Scenario: Sin VM
- **WHEN** no hay ninguna VM de trabajo encendida
- **THEN** el tablero sigue mostrando las corridas y el reporte de los meses procesados

### Requirement: Estado de las corridas en vivo
El tablero SHALL mostrar la lista de corridas y, para cada una, sus etapas en orden con estado, duración y eventos,
actualizándose solo mientras la corrida avanza, sin intervenir en ella.

#### Scenario: Corrida en curso
- **WHEN** hay una corrida en curso y el tablero está abierto
- **THEN** la etapa actual figura en curso y pasa a exitosa o fallida en cuanto el registro cambia, sin recargar la
  página

#### Scenario: Sin actividad
- **WHEN** no hay ninguna corrida en curso y el tablero está abierto
- **THEN** el tablero no consulta el registro hasta que algo cambia

#### Scenario: Actualización en vivo no disponible
- **WHEN** el tablero no logra mantener la actualización en vivo durante una corrida
- **THEN** la página sigue mostrando el avance, con unos segundos de demora, indica que está en ese modo y vuelve a la
  actualización en vivo cuando se recupera

#### Scenario: Conexión cortada
- **WHEN** el navegador pierde la conexión con el tablero durante una corrida y la recupera
- **THEN** la página muestra el estado actual, incluidos los cambios que ocurrieron mientras estuvo desconectada

#### Scenario: Eventos de una etapa
- **WHEN** se despliega una etapa de una corrida
- **THEN** se ven sus eventos en orden, y si la etapa está en curso los nuevos aparecen sin recargar

#### Scenario: Etapa larga
- **WHEN** una etapa tarda varios minutos
- **THEN** sus eventos muestran el avance dentro de la etapa

#### Scenario: Reintentos de un mes
- **WHEN** un mes tuvo más de un intento
- **THEN** la corrida del mes muestra cada intento con su estado y cuál es el vigente

#### Scenario: Tiempo que queda
- **WHEN** se mira una corrida en curso
- **THEN** se ve el tiempo transcurrido contra el límite de 15 minutos

#### Scenario: Tablero caído
- **WHEN** el tablero se cierra o falla durante una corrida
- **THEN** la corrida termina igual y deja la copia del reporte

### Requirement: Errores y avisos a la vista
El tablero SHALL mostrar los errores y los avisos de cada corrida con su nivel, su etapa y la regla que los produjo, y
SHALL resumir cuántos hubo por regla en cada mes.

#### Scenario: Etapa que falla
- **WHEN** una etapa falla
- **THEN** la corrida figura fallida y al abrirla se ve en qué etapa fue, el mensaje y el detalle del error

#### Scenario: Corrida rechazada
- **WHEN** una corrida se rechaza (mes ya procesado, fuera de orden, archivo que no corresponde)
- **THEN** figura en la lista como rechazada con su motivo

#### Scenario: Aviso que se repite
- **WHEN** una misma regla dispara avisos en varios meses
- **THEN** se ve la cantidad de cada mes, una al lado de la otra

#### Scenario: Corrida con avisos pero exitosa
- **WHEN** una corrida termina bien con avisos
- **THEN** la lista de corridas muestra cuántos avisos tuvo, sin tener que abrirla

### Requirement: Estado general de un vistazo
El tablero SHALL abrir con un resumen: el último mes procesado y su estado, su tiempo contra el límite, los avisos y
errores recientes, la ganancia acumulada y si el último respaldo salió bien.

#### Scenario: Respaldo que falló
- **WHEN** el respaldo del último mes no terminó
- **THEN** el resumen lo muestra como un problema, aunque la salida del mes esté publicada

### Requirement: Modelos y operación
El reporte SHALL mostrar, por mes, qué catálogo de modelos se usó, con sus cortes y la fuente de cada uno, y los datos
de operación de la corrida: quién la inició, con qué versión del código, en qué máquina, cuánta memoria usó y cuántas
filas entraron y salieron de cada etapa.

#### Scenario: Cambio de catálogo
- **WHEN** dos meses se procesaron con catálogos distintos
- **THEN** el reporte muestra en qué mes cambió

### Requirement: Tiempo de cada corrida
El reporte SHALL mostrar, para cada mes, la duración de cada etapa y el total contra el límite de 15 minutos.

#### Scenario: Presupuesto de tiempo
- **WHEN** se mira un mes del reporte
- **THEN** se ve cuánto tardó cada etapa, el total y cuánto margen quedó contra el límite

### Requirement: Métricas disponibles sin la clase
El reporte SHALL mostrar para cada mes y estrategia, el mismo día de la corrida: cantidad de clientes y de envíos,
distribución de los puntajes, probabilidad mínima enviada, coincidencia entre las listas de envío de las estrategias y
entre las semillas de cada una, clientes nuevos sin historia y cambio respecto del mes anterior.

#### Scenario: Mes recién procesado
- **WHEN** termina la corrida del mes M
- **THEN** esas métricas de M están en el reporte para cada estrategia

### Requirement: Métricas que llegan con la clase
El reporte SHALL completar la ganancia, la curva de ganancia, el AUC, la captura y el lift de cada estrategia para un
mes cuando madura su clase, y hasta entonces SHALL mostrarlas como pendientes.

#### Scenario: Maduración
- **WHEN** se procesa el mes M
- **THEN** el mes M−2 pasa de pendiente a tener ganancia realizada por estrategia, y M y M−1 siguen pendientes

#### Scenario: Corte realizado contra el mejor corte
- **WHEN** un mes tiene su clase madura
- **THEN** el reporte muestra, por estrategia, la ganancia con los envíos que se hicieron y la del mejor corte posible

### Requirement: Calidad de datos por mes
El reporte SHALL mostrar un mapa de variables por mes con la proporción de ceros y de faltantes, la cantidad de
variables rotas por mes, los meses degradados, las variables con cambio de régimen y qué tratamiento se aplicó.

#### Scenario: Mes con variables rotas
- **WHEN** se procesó un mes con variables rotas
- **THEN** el mapa las destaca en ese mes y se indica cuántas se trataron y qué meses siguientes heredan variables
  históricas faltantes

### Requirement: Señales para decidir
El reporte SHALL mostrar por mes la tasa de bajas observada, el corrimiento de las variables más importantes de cada
modelo y qué estrategia fue la recomendada.

#### Scenario: Vista de decisión
- **WHEN** alguien abre el reporte después de varios meses
- **THEN** ve en una sola vista la ganancia realizada por estrategia, el corrimiento de las variables y la estrategia
  usada en cada mes
