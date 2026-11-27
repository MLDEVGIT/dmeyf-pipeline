# Spec Delta

## ADDED Requirements

### Requirement: Estrategia de reajuste mensual
La fábrica SHALL fijar los hiperparámetros, las variables y la regla de muestreo de una estrategia que la corrida
mensual reentrena cada mes con las clases ya maduras, sin buscar hiperparámetros en producción.

#### Scenario: Receta de reajuste en el catálogo
- **WHEN** termina la fábrica
- **THEN** el catálogo contiene la receta del reajuste (hiperparámetros, ventana de meses, fracción de CONTINUA y su
  peso, cantidad de semillas) y el tiempo que tardó al ensayarla sobre 2019

#### Scenario: Reajuste en producción
- **WHEN** la corrida mensual procesa el mes M
- **THEN** la estrategia de reajuste entrena con meses que no pasan de M−2 y con la receta del catálogo, sin cambios
