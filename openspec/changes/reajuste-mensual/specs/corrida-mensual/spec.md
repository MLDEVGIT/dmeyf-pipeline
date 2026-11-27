# Spec Delta

## ADDED Requirements

### Requirement: Reajuste dentro del límite de tiempo
El sistema SHALL dar al reajuste mensual un presupuesto de tiempo propio, menor que el límite de la corrida, y SHALL
terminar la corrida con las demás estrategias cuando el reajuste lo supera.

#### Scenario: Reajuste que no entra en el tiempo
- **WHEN** el reajuste mensual supera su presupuesto de tiempo
- **THEN** se interrumpe, esa estrategia queda marcada como no disponible para el mes y la corrida termina con las
  demás
