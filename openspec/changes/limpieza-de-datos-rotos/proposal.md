# Proposal

## Why

`esqueleto-del-pipeline` (decisión 8) detecta y trata un solo patrón de dato roto: la columna que llega toda en cero en
un mes. En el experimento de autoresearch de la comisión del lunes (`resumen-experimentos.pdf`, 27-nov-2026) los
agentes encontraron en 2019 otros dos patrones que ese detector no ve. Los arreglos de datos rotos se mantuvieron 8 de
12 veces, aunque 4 de esos 8 bajaron la validación 201908 y se mantuvieron solo por la regla del agente. Todos los
números son de validación 201908, contra el modelo vigente de cada corrida:

- **Saltos de cierre de trimestre**: en marzo y junio, `Visa_mpagado`, `Visa_delinquency`, `Master_mpagado` y
  `Master_delinquency` saltan y vuelven al mes siguiente. Reemplazarlos por el valor del mes anterior dio +1,87 M
  (Visa) y +2,23 M (Master).
- **Cambios de definición**: pago de servicios y `pagomiscuentas` cambian de definición en 201906; poner en nulo los
  meses anteriores dio +2,00 M. Dos arreglos parecidos perdieron: transferencias recibidas antes de 201906 y mobile app
  antes de 201907 en nulo (−1,51 M), y poner en nulo los meses en que una variable todavía no se medía (−0,53 M).

La corrida que más limpió (Flor guiado) llegó así a su mejor modelo en 201908, pero ese modelo quedó último en el test
201910 (289,0 M, −1,0 % contra el baseline). El tercer arreglo que sumó (+1,38 M: las columnas en cero de 201905 y
201904 reemplazadas por el valor del cliente en el mes anterior) es el «último valor» que la decisión 8 ya tiene como
candidato; este cambio no lo repite.

Cada número es de una sola corrida, con un ruido de ±4,6 M entre dos modelos en un mes. Son hipótesis a medir con
nuestros meses, no hechos.

## What Changes

- Verificar primero con nuestros datos que los dos patrones existen: series mensuales de 2019 de las columnas nombradas
  (media, ceros y faltantes por mes). Mirar un salto no usa la clase, así que entran los cuatro cierres de 2019
  (201903, 201906, 201909 y 201912). Si un patrón no aparece, sale del cambio.
- **Saltos de cierre de trimestre**: regla por calendario, que en producción no necesita ver el mes siguiente: en los
  meses 03, 06, 09 y 12 esas columnas toman el valor del cliente en el mes anterior. La lista de columnas sale solo de
  2019 y queda escrita con su evidencia.
- **Cambios de definición**: las columnas afectadas pasan a faltante en los meses anteriores al cambio. Solo toca el
  entrenamiento (2019); en producción todos los meses son posteriores. Como los arreglos parecidos perdieron, cada
  columna entra solo si el cambio de definición se ve en la serie.
- Igual que la decisión 8: la historia guarda el valor crudo y el tratamiento se aplica al calcular las variables,
  antes de lags y deltas, igual en la fábrica y en la corrida.
- Medición en orden, un patrón por vez (primero los saltos, después los cambios de definición sobre el resultado del
  primero), contra el catálogo vigente, con semillas pareadas en 201908 y 201909 y el protocolo del registro de
  mejoras. Cada patrón se adopta o no por su cuenta.
- **Registro de la mejora**: cada patrón medido es una fila del registro común de mejoras (`docs/MEJORAS.md`, definido
  en `peso-de-baja1`), se adopte o no.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `calidad-de-datos`: dos tratamientos más, por calendario y por cambio de definición, además del de columnas en cero.
- `historia-y-features`: los tratamientos se aplican antes de lags y deltas.

Las dos capacidades las crea `esqueleto-del-pipeline`.

## Impact

- **Código**: `features.py` (el tratamiento) y la política de calidad; todos los modelos se reentrenan y los cortes se
  vuelven a derivar.
- **Dependencia**: conviene decidirlo después del experimento de la decisión 8 de `esqueleto-del-pipeline`, para medir
  cada tratamiento sobre el anterior y no mezclar efectos.
- **Congelamiento**: igual que cualquier reentrenamiento, entra antes del congelamiento del catálogo (tarea 7.7 de
  `esqueleto-del-pipeline`) o después, repitiendo cortes, tiempo y ensayo.
- **Riesgo**: una regla por calendario aprendida con cuatro cierres de 2019 puede no valer en 2020; el reporte mensual
  tiene que mostrar el tamaño del salto en cada cierre para verlo.
