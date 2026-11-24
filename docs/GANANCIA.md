# Ganancia

## Fórmula

Para un mes, si se envía el estímulo a los *k* clientes de mayor score y *TP(k)* de ellos son BAJA+2:

    G(k) = PREMIO_BRUTO · TP(k) − COSTO_ENVIO · k

| Concepto | Valor | Qué es |
|---|---|---|
| **Premio bruto** por acierto | 1.100.000 | Lo que vale retener a un BAJA+2 estimulado (2,2 M de valor anual del cliente × 50 % de aceptación) |
| **Costo por envío** | 27.500 | Lo que cuesta cada estímulo, a cualquier cliente, acierte o no |
| **Ganancia neta por acierto** | 1.072.500 | Premio bruto − costo del propio envío |
| Pérdida por envío errado | −27.500 | BAJA+1 o CONTINUA estimulado: solo el costo |

Las dos formas son la misma cuenta:

    G(k) = 1.100.000 · TP − 27.500 · k  =  1.072.500 · TP − 27.500 · (k − TP)

El error que hay que evitar es mezclarlas: usar **1.072.500 como premio bruto y además cobrar 27.500 a
todos los envíos**, lo que descuenta dos veces el costo de los aciertos. La implementación está en
`evaluacion/ganancia.py` y `pruebas/test_evaluacion.py` comprueba la equivalencia.

**Umbral de equilibrio** sobre una probabilidad calibrada de BAJA+2:
p* = 27.500 / 1.100.000 = **0,025** (1/40). Con ese p, el valor esperado del envío es 0:
0,025 · 1.072.500 − 0,975 · 27.500 = 0. Los notebooks del curso usan justamente ese umbral, lo que
confirma que 1.072.500 es la ganancia **neta**.

Solo BAJA+2 paga. BAJA+1 (se va el mes siguiente) cuenta como envío errado, aunque el modelo del
baseline lo use como positivo para entrenar.

## Fuentes y verificación

| Fuente | Qué dice | Alcance |
|---|---|---|
| Notebooks del curso, repo `dmecoyfin/dmeyf2026` (`arboles/z0201`, `z0290`, `z0312`, `z0333`; `ensembles/z420`, `z440`, `z470`; `zero2hero/zero2hero_01`) | `ifelse(clase_ternaria == "BAJA+2", 1072500, -27500)`; `z0333` decide con probabilidad > 0,025 | Dataset de la competencia 01 |
| `monday/z701_drifting.ipynb` (upstream, nov-2026) | `ganancia_acierto = 1_072_500`, `costo_estimulo = 27_500` | Lee `competencia_01.parquet` |
| `dmeyf-experimento-sampling/comun/ganancia.py` | Mismos valores; comentario con el desglose 2,2 M × 50 % − 27.500, "copiados de `competencia-2/src/fe_panel.py`" | Ese repo no está en esta máquina; el desglose no se pudo ver en su fuente original |
| Repos de alumnos de C01 (§ 2.1 de `RELEVAMIENTO.md`) | 1.072.500 / −27.500 en el código; `farpp8` usa la forma bruta 1,1·TP − 0,0275·N; algunos README dicen 780.000 / −20.000 (misma razón 1/40, otra escala) | C01 |
| Consigna de C02 (F1) y presentación (F2) | F2 no menciona importes. F1 sin transcribir | **C02: sin fuente propia** |

**Estado para C02: pendiente de verificación.** Los importes de C02 no tienen fuente disponible
propia. Se usan los de C01 y se registran en cada corrida (`resultados.json` → `ganancia`).

**Qué cambia si C02 usa otros importes.** La elección del corte (fracción o cantidad que maximiza
G) solo depende de la razón costo/premio. Si cambia la escala pero no la razón, cambian los
montos informados, pero no los cortes ni las decisiones. Si cambia la razón, hay que recalcular las
curvas guardadas; no hace falta reentrenar.
