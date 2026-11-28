# Nube: crédito, gasto y acceso

Proyecto `proj-uba-261012163242176`, región `northamerica-northeast2` (Toronto), bucket de datos
`gs://agustinarazanov_buckito2026/`. Lo que se crea y por qué está en el diseño del cambio `esqueleto-del-pipeline`
(decisiones 2, 5, 11 y 12).

## Crédito

| | |
| --- | --- |
| Saldo | **US$ 256** al 23-nov-2026 (crédito del período de prueba, cuenta de Agustina) |
| Vencimiento | **10-ene-2027**. Con él se van la base, el tablero y los enlaces: antes de esa fecha se bajan el bucket de datos, la última exportación de la base y el reporte (tarea 2.9) |
| Regla | El gasto de cómputo dentro del crédito no se consulta; se anota en la tabla de abajo |

## Estimación (28-nov-2026)

Precios de lista aproximados de la región, sin descuentos por uso sostenido; se corrigen con la primera factura.

| Qué | Cómo se usa | Precio aproximado | Hasta el 10-ene |
| --- | --- | --- | --- |
| Cloud SQL para PostgreSQL, instancia chica (núcleo compartido, 10 GB SSD, copias automáticas) | siempre encendida desde que se crea (≈ 1,5 meses) | US$ 12–15 por mes | US$ 20–25 |
| VM `n2-highmem-8` a pedido (STANDARD) | se crea, se usa y se borra | ≈ US$ 0,55 por hora | ver abajo |
| Fábrica: catálogos de 5 + 5, 20 + 20 y 20 + 10 semillas desde cero | 20 binarios (130–200 s cada uno) y 20 multiclase (330–600 s) medidos con 8 hilos en la notebook de Martín (`PLAN_PRUEBAS.md`), más la historia y el target: ≈ 4 h de VM | | US$ 2–3 |
| Experimento de tratamiento (7.4) y reentrenamiento del catálogo congelado (7.7) | modelos reentrenados con el tratamiento en tres tamaños, más un catálogo completo: ≈ 15 h de VM | | US$ 8–10 |
| Ensayos y mediciones (secuencias de 6 meses, tiempos, plan B, recorrido de cada integrante, ensayo general) | ≈ 1 h por secuencia; unas 30 secuencias | | US$ 15–20 |
| Discos de las VMs (100 GB SSD mientras existen) y VM de la clase apagada unos días | | US$ 0,20 por día por disco | US$ 5 |
| Cloud Run (tablero) | escala a cero; una instancia siempre encendida el día de la clase | | US$ 2–5 |
| Bucket (historia, catálogos, exportaciones, reporte; unos pocos GB) | | US$ 0,02 por GB y mes | < US$ 1 |
| **Total estimado** | | | **US$ 55–70**, un cuarto del crédito |

El margen cubre repetir la fábrica entera dos o tres veces. La alerta de presupuesto (2.9) avisa al 50 % y al 80 %.

## Gasto real

Una fila por tanda: qué se corrió, cuánto duró y el gasto que muestra la facturación del proyecto al día siguiente.

| Fecha | Tanda | Recursos | Horas | Gasto (US$) | Saldo después (US$) | Quién |
| --- | --- | --- | --- | --- | --- | --- |
| | | | | | | |
