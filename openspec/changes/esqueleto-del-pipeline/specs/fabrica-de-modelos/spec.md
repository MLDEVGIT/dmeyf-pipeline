# Spec Delta

## Purpose

Entrena fuera de línea, sin límite de tiempo, los modelos y las políticas de corte que después usa la corrida mensual,
y los deja en un catálogo que cualquier integrante puede descargar.

## ADDED Requirements

### Requirement: Meses permitidos para definir modelos
La fábrica SHALL usar solo los meses 201901–201912 para elegir hiperparámetros, variables, estrategias y políticas de
corte, con BAJA+2 definida hasta 201910.

#### Scenario: Intento de usar 2020
- **WHEN** se configura la fábrica con un mes posterior a 201912
- **THEN** la fábrica termina con error antes de entrenar

#### Scenario: Roles de los meses declarados
- **WHEN** termina una corrida de la fábrica
- **THEN** el catálogo indica qué meses se usaron para entrenar, cuáles para elegir (hiperparámetros y cortes) y cuál
  queda reservado para la evaluación final

#### Scenario: Mes de la evaluación final bloqueado
- **WHEN** un experimento intenta leer la clase del mes reservado para la evaluación final
- **THEN** termina con error, salvo en la evaluación final misma, que se corre una sola vez

### Requirement: Fábrica reproducible por cualquier integrante
La fábrica SHALL poder reconstruir la historia de 2019, la clase y el catálogo completo a partir del dataset del curso
con comandos documentados, sin rutas ni archivos propios de la máquina de una persona.

#### Scenario: Reentrenamiento en una VM limpia
- **WHEN** un integrante ejecuta la fábrica en una VM recién creada, con el dataset del curso
- **THEN** obtiene modelos cuyas predicciones coinciden con las del catálogo publicado, o difieren en una cantidad
  medida y anotada

### Requirement: Catálogo de modelos
La fábrica SHALL publicar cada modelo en un catálogo con un manifiesto que indica su estrategia, sus semillas, sus
hiperparámetros, los meses usados, la versión de variables, la política de corte y la huella de cada archivo.

#### Scenario: Modelo utilizable por producción
- **WHEN** la corrida mensual carga un modelo del catálogo
- **THEN** verifica la huella del archivo contra el manifiesto y falla si no coincide

#### Scenario: Catálogo descargable
- **WHEN** un integrante con una copia limpia del repo ejecuta el comando de descarga del catálogo
- **THEN** obtiene los modelos que el manifiesto del repo declara, sin reentrenar

### Requirement: Estrategias estáticas
La fábrica SHALL producir al menos dos estrategias estáticas con objetivos distintos, cada una un ensamble de modelos
con distintas semillas, entrenado con meses de 2019 que tienen clase, que la corrida mensual aplica sin modificar; el
catálogo SHALL indicar cuál es la recomendada y qué significa el puntaje de cada una.

#### Scenario: Ensamble por semillas
- **WHEN** se entrena una estrategia con N semillas
- **THEN** el catálogo contiene N modelos y el puntaje de la estrategia es el promedio de los N

#### Scenario: Significado del puntaje
- **WHEN** se consulta una estrategia del catálogo
- **THEN** el catálogo dice qué probabilidad es su puntaje (irse en uno o dos meses, o irse en dos meses) y si es la
  recomendada o la alternativa

### Requirement: Política de corte
La fábrica SHALL definir para cada estrategia una política que decide cuántos clientes se marcan con `enviar = 1`,
elegida con varios meses de 2019 y no con el máximo de la curva de un solo mes.

#### Scenario: Corte elegido con varios meses
- **WHEN** se define la política de corte de una estrategia
- **THEN** el catálogo guarda la curva de ganancia de cada mes usado y la regla aplicada

#### Scenario: Corte que no depende de las semillas
- **WHEN** se define la política de corte de una estrategia
- **THEN** hay evidencia guardada de que ensambles con otras semillas eligen un corte equivalente

#### Scenario: Corte aplicado en producción
- **WHEN** la corrida mensual marca los envíos de un mes
- **THEN** usa la política del catálogo y guarda la cantidad de envíos resultante

### Requirement: Fábrica reanudable
La fábrica SHALL poder retomarse después de una interrupción sin repetir el trabajo ya terminado.

#### Scenario: Corte a mitad de camino
- **WHEN** la fábrica se interrumpe y se vuelve a ejecutar con la misma configuración
- **THEN** continúa desde lo último guardado y el catálogo final es igual al de una corrida sin interrupciones
