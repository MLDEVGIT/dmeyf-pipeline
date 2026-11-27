# Backlog para la Segunda Competencia

Ideas propias y de compañeros, priorizadas por la evidencia que hay **en el privado** (no solo en el público).
Fuentes: `notebooks/n00_postmortem_c1.ipynb` (§ = sección), la matriz y las fichas de los 66 repos de Vercel
(`docs/postmortem_vercel/`, lectura automática de Emmanuel Valdez [204115]) y el Zulip. La «tasa de Purgatorio»
compara, entre los 66 repos, a quienes tienen la técnica **en la entrega** contra quienes no (tasa base 39/66 = 59%);
con 66 repos casi todo cabe en el azar, salvo donde se indica.

Regla para todo lo que sigue: hipótesis escrita antes de enviar, 20 archivos por submit, comparación pareada por
semilla contra la referencia, y nada se decide con diferencias públicas de ±2.

## Prioridad 1: lo que el privado respalda

| Idea | Evidencia | Cómo |
| --- | --- | --- |
| **Hipótesis: el corte por la meseta, no por el pico** (a validar con walk-forward sobre muchos meses) | Pico público de `c201` en 14.000, pico privado en 10.000 (302,3 vs 289,0, 20 archivos por punto, §1d). Los 40 del Purgatorio con archivo ordenado por score tenían el pico privado en 10.008 (mediana, §5). Lovrich y Freites (vivos) eligieron con la meseta de junio | en la 1 habría servido la curva de ganancia de cada mes local + el público para descartar, eligiendo dentro de la meseta común del lado de menor regret; con ~36 meses, medir con walk-forward si eso le gana al argmax |
| **Confirmación externa del corte: la tabla del profesor** | `J-Clase 09 > punto de corte` [204989]/[204990], reproducida exacta desde los HTML del Purgatorio y el Zielo (n00 §10c): archivos con público > 100 que **fracasaron**, mediana **12.250** envíos (media 12.227); con público > 105, 12.000. Los que **pasaron**: 11.000 (media 11.292) y 11.300. Entregas: los que pasaron cortaron en 10.000–12.500 (mediana 11.175), nadie pasó con más de 12.500. Y los que pasaron frenaron con la última banda de 1.000 todavía en 3,2% de BAJA+2 (Purgatorio 2,6%; equilibrio 2,5%, n00 §10e) | es el mismo procedimiento del margen (§5c): frenar con la banda final claramente arriba del 2,5% en vez de extender hasta el cruce. El 10.500–11.500 es de agosto 2021 con 6 meses; lo que se lleva a la 2 es la hipótesis, a medir con walk-forward |
| **Variables de tendencia** (pendiente sobre ventanas de 3–6 meses) | La única técnica que pasa Bonferroni en la matriz: 6/21 en el Purgatorio contra 33/45 (Fisher p = 0,001, §7). La exploramos y no la entregamos | `regr_slope` contra `foto_mes` (no contra `cliente_antiguedad`, que se resetea), redondeada (ver la nota de `pend_ctrx` en dmeyf2026) |
| **Más rondas, medidas sin reentrenar** | 2.000 vs 1.000 rondas: +6,8 privado pareado, 19 de 20 semillas, p < 0,001 (§3); 3.000 no mejoró en el público (−1,7, 5 semillas) | `Booster.predict(num_iteration=k)`: un modelo de 3.000 da las curvas de 1.000–3.000 (es idéntico a entrenar k rondas, ver `docs/optuna_y_lightgbm.md`) |
| **Ensamble por rango de 20+ semillas** | En el privado el ensamble le ganó a la semilla media: +2,8 en `c201`, +0,8 en `c241` (§4). Los tres vivos de los cinco que seguimos usaron 40–60 semillas | 40 semillas si el tiempo alcanza; el ensamble va al bot, la media de 20 archivos es la referencia |
| **Ids en orden de score** | Nuestra curva del profesor salió una recta (§1c) | ya está en `src/competencia.py` |

## Prioridad 2: evidencia pública o de compañeros, sin confirmación privada

| Idea | Evidencia | Notas |
| --- | --- | --- |
| **Lag 2 selectivo** (78 variables estables) | Ani-victoria: 99,8 → 109,6 público con lag 2/delta 2 sobre una lista de 78 (el salto lo contó ella durante la competencia; no figura en la ficha, que confirma la lista de 78 «escrita en el código, sale de un notebook de diagnóstico») | Ani-victoria es Ana Dominguez en el txt: **murió** (295,4) y es uno de los «casos tristes» de overfitting [204268]. La idea puede ser buena; su corte y su elección por el público no |
| **Ranks con cero fijo** por mes (positivos en (0,1], negativos en [−1,0), 0 queda 0) | 29 repos lo mencionan; matriz: 16/32 en el Purgatorio contra 23/34 (p = 0,21). Abregú (vivo, ~110) calcula lags y deltas de montos sobre `rk0_` | nosotras lo exploramos (c167) con hiperparámetros viejos; volver a medirlo con la receta |
| **Submuestreo de CONTINUA distinto por semilla** | Matriz: 8/20 en el Purgatorio contra 31/46 (p = 0,056) | `pos_bagging_fraction`/`neg_bagging_fraction` con `bagging_freq > 0`: no toca el dataset y cambia con la semilla |
| **Canaritos para podar** | Freites (vivo, ~106): 760 → 128 columnas con 152 canaritos en c9920 (elegida por ganancia pareada en junio, t ≥ 2 sobre 5 semillas), 299 con su historia. Matriz: 3/8 contra 36/58 (p = 0,26) | a nosotras la poda por importancia nos perdió en el público (−3,5 con 392 columnas, §3, y +1,0 en el privado: ruido) |
| **Promedios / mín / máx de ventana** | Matriz: promedios 10/23 contra 29/43 (p = 0,07); mín/máx 4/10 | van con las tendencias |
| **Aguinaldo** | Ani-victoria: `mpayroll_sin_sac` (mpayroll / 1,5 en junio y diciembre) y flags de aguinaldo; Bernacchia: flags con sus lags | nuestro `c253` (aguinaldo corregido) dio +0,8 privado pareado, 2 de 5: ruido. Revisar solo si cambia el mes de junio en la 2 |
| **Hiperparámetros de Abregú** | ~110 público y vivo: 36 hojas, `min_data_in_leaf` 1.855, lr 0,042, feature_fraction 0,40, bagging 0,93, 637 iteraciones, 40 semillas, corte 12.000 | otra región del espacio (hojas grandes en datos, lr alto): un trial en la bayesiana |
| **Cortes alrededor de 11.000** | Lovrich, Freites y farpp cortaron en 11.000, Abregú en 12.000; la mediana de los 40 picos privados del Purgatorio es 10.008 | consecuencia de la prioridad 1, no una regla |
| **Préstamos personales congelados como cohorte de junio** (farpp) | farpp (Federico Ramirez en el txt) **murió** (284,6); el profesor dijo que sacar préstamos «funciona peor» | baja |
| **`path_smooth`, `refit`** | no probados por nadie de los cinco | ver `docs/optuna_y_lightgbm.md` |
| **Bayesiana sobre el público** (método del profesor) | [203439]: 20–25 iteraciones, el mejor público gana | `src/bayesiana_publico.py`; con el corte fijado por la meseta, no optimizado |
| **Walk-forward en varios meses** | el profesor lo adelantó para la 2 [203566] | para hiperparámetros y corte, en vez del público |

## Lo que falló (en nosotras o en otros)

- **Validación cruzada aleatoria**: 8 de 10 en el Purgatorio (matriz). Mezcla meses.
- **Target solo BAJA+2**: 9 de 12 en el Purgatorio (matriz). Ojo: nuestro `c213` (solo BAJA+2, 1.000 rondas) dio −5,3
  en el público y **+4,5 en el privado**, 5 de 5 semillas (§3). Vale una medición con 20 semillas antes de descartarlo.
- **Horizonte 1 solo**: −5,6 público, −13,3 privado (§3). La mezcla con horizonte 1 a peso 0,3–0,5: +3,7 privado,
  4 de 5 (sugerente, no concluyente).
- **Sacar familias importantes**: sin las 10 top, −18 público / −46 privado; sin `ctrx_quarter`, −2,8 / −5,1.
- **Hessiano × 2**: −4,0 público, −3,2 privado, 0 de 5 en las dos.
- Mencionado en la exploración de compañeros y **no verificado** en las fichas: `extra_trees` (−24 M), mezclar
  configuraciones, cascada BAJA+1 → BAJA+2, multiclase sola. La multiclase aparece en dos fichas (kformoso, segunmo)
  sin resultado declarado.

## Lo que hicieron los 27 que pasaron

Fuente: las 27 fichas de `docs/postmortem_vercel/fichas.csv` que no están en el Purgatorio según el mapeo
`TXT_A_SLUG` de `notebooks/n00_postmortem_c1.ipynb` §7, leídas completas, contra las 39 del Purgatorio que sí
tienen repo (nosotras incluidas). Los conteos salen de `matriz.csv` cuando la técnica tiene columna propia y, si no,
de buscar en el texto de las fichas y revisar a mano cada coincidencia. El corte de los muertos es el **tamaño real de
su último archivo** en el txt del profesor; el de los vivos, el que declara la ficha o el README (24 de 27; faltan
`lsaldeco`, `luisdanielsuarez` y `veroq00`).

**Advertencia de tamaño.** Son 27 contra 39. Con esos grupos, una diferencia de 20 puntos porcentuales da p ≈ 0,02–0,1
en Fisher, y acá se prueban unas 45 ideas: al 5% habría que esperar dos falsos positivos. Solo las **tendencias**
(p = 0,001) pasan una corrección por comparaciones múltiples. El resto es un mapa de dónde mirar, no un efecto.

**Quién es «vivo».** Ninguna ficha ni `index.json` dice si alguien no hizo submit final (las 66 lecturas figuran como
«verificada»). Que no estés en el Purgatorio significa que pasaste 300 **o** que no figurás en el txt. Tres fichas no dicen
qué archivo se entregó: `lsaldeco` (el código tiene `CORTE = 1000` y el README dice que el corte final «se definió con el
público», sin el valor), `luisdanielsuarez` («el repositorio no indica qué corte se envió») y `veroq00` (escribe seis
cortes; el bucle de 50 semillas se cortó en la 16). Hay dos casos raros más, pero esos no ponen en duda que hayan
entregado: `la-laguinge` (el modelo guardado usa 415 variables que ningún script crea) y `arielrojasv` (el `2021505` hace
que entrene sin mayo).

### (a) Idea × grupo, ordenada por la diferencia

«Vivos» = de 27, «muertos» = de 39. Nosotras: **sí** = en la entrega, *expl.* = solo explorada.

| Idea | Vivos | Muertos | Dif. | p | Nosotras | ¿En el backlog? | Fichas vivas de ejemplo |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| **Tendencia (pendiente) de ventana de 3** | 15 (56%) | 6 (15%) | +40 pp | 0,001 | *expl.* | sí, P1 | `agustinlovrich`, `patriciojarmoluk`, `luisdanielsuarez`, `mariofreites`, `kformoso` |
| **Corte entre 10.000 y 11.500** | 18/24 (75%) | 18 (46%) | +29 pp | 0,04 | no (14.000) | sí, P1–P2 | 11.000: `agustinlovrich`, `mariofreites`, `fsteeb1`, `turrivalentin`, `hmijal`, `snehitdua` |
| **Promedio de ventana de 3** | 13 (48%) | 10 (26%) | +23 pp | 0,07 | no | sí, P2 | `agustinlovrich`, `patriciojarmoluk`, `kformoso`, `veroq00`, `tomasroel` |
| Lag 2 / delta 2 de casi todas las variables | 21 (78%) | 22 (56%) | +21 pp | 0,11 | **sí** | sí (base) | casi todos |
| **Señales de evento** (perdió el sueldo, empezó a pagar comisión, perdió productos; sin contar rachas, que tienen además 2 muertos) | 6 (22%) | 1 (3%) | +20 pp | 0,02 | *expl.* (c111, c115) | **no** | `ezequielabregu` B3, `fsteeb1`, `jaquelinegirabel`, `mariofreites`, `pfranzd` e034, `tomasroel` |
| **Submuestreo de CONTINUA distinto por semilla** en el modelo final | 6 (22%) | 1 (3%) | +20 pp | 0,02 | no | sí, P2 | `kformoso` (0,2 × 60 semillas), `tomasroel` (0,1 × 50), `segunmo`, `jaquelinegirabel`, `emavaldez`, `nicozare` |
| Rank con cero fijo por mes | 16 (59%) | 16 (41%) | +18 pp | 0,21 | *expl.* (c167) | sí, P2 | `agustinlovrich`, `patriciojarmoluk`, `ezequielabregu`, `mariofreites` |
| Sumas y cocientes del mes (Visa+Master, patrimonio, uso del límite) | 16 (59%) | 16 (41%) | +18 pp | 0,21 | *expl.* (c260, c261) | **no** | `tomasroel` (78 `new_*`), `pedro-bosch`, `segunmo`, `cvfh`, `mariofreites` |
| **Préstamos fuera de la BO, adentro del modelo final** | 7 (26%) | 3 (8%) | +18 pp | 0,08 | no hubo BO | **no** | `agustinlovrich`, `patriciojarmoluk`, `hmijal`, `nicobaranek`, `luisdanielsuarez` |
| Selección por importancia (top-N o canaritos) | 7 (26%) | 3 (8%) | +18 pp | 0,08 | *expl.* (c161, c165) | sí (canaritos) | `mariofreites` (760 → 128), `laupasq1967` (576), `mbellesi01` (top 300), `segunmo` (top 150) |
| Submuestreo de CONTINUA en el modelo final (cualquiera) | 7 (26%) | 3 (8%) | +18 pp | 0,08 | no | sí, P2 | ver arriba, más `snehitdua` (0,1, la misma muestra en todas las semillas) |
| 40 semillas o más | 9 (33%) | 8 (21%) | +13 pp | 0,27 | no (20) | sí, P1 | `laupasq1967` 100 × 2, `kformoso` 60, `mariofreites` 60, `tomasroel` 50, `agustinlovrich` 40 |
| Mín. / máx. de ventana | 6 (22%) | 4 (10%) | +12 pp | 0,30 | *expl.* | sí, P2 | `fsteeb1`, `laupasq1967`, `pfranzd`, `pedro-bosch` |
| Canaritos | 5 (19%) | 3 (8%) | +11 pp | 0,26 | *expl.* | sí, P2 | `mariofreites`, `laupasq1967`, `veroq00`, `segunmo`, `emavaldez` |
| `ccajas_depositos` a NA en 202105 | 23 (85%) | 29 (74%) | +11 pp | 0,37 | **sí** | — | casi todos |
| Flags `_zero` / `missing_` por variable | 3 (11%) | 1 (3%) | +9 pp | 0,30 | no | **no** | `lsaldeco`, `luisdanielsuarez`, `veroq00` |
| Multiclase, score P(B1)+P(B2) o P(B2)/(1−P(B1)) | 3 (11%) | 1 (3%) | +9 pp | 0,30 | no | mencionada | `kformoso`, `emavaldez`, `segunmo` |
| Corrige la probabilidad por el submuestreo | 3 (11%) | 1 (3%) | +9 pp | 0,30 | — | **no** | `jaquelinegirabel`, `snehitdua`, `emavaldez` |
| Saca `F*iniciomora` / `f*ultimo_cierre` | 7 (26%) | 7 (18%) | +8 pp | 0,54 | **sí** | — | `ezequielabregu`, `pfranzd`, `nicozare`, `nicobaranek` |
| Ventana de 6 meses | 2 (7%) | 0 | +7 pp | 0,16 | no | **no** | `fsteeb1` (40 variables), `la-laguinge` (en el modelo guardado) |
| Corte elegido mirando el público | 10 (37%) | 12 (31%) | +6 pp | 0,61 | **sí** | — | `ezequielabregu`, `keilazavaglia`, `turrivalentin`, `laupasq1967` |
| Entrena en 202104–202106, sin marzo | 3 (11%) | 2 (5%) | +6 pp | 0,39 | no | **no** | `kformoso`, `emavaldez`, `pedro-bosch` |
| Receta de la cátedra (lr 0,005, ff 0,5, bynode 0,2, `min_data_in_leaf` 0) | 14 (52%) | 18 (46%) | +6 pp | 0,80 | **sí** | — | — |
| Positivo = BAJA+1 o BAJA+2 | 24 (89%) | 33 (85%) | +4 pp | 0,73 | **sí** | — | — |
| BO de rondas, hojas y hessiano | 11 (41%) | 15 (38%) | +2 pp | 1,0 | no | — | — |
| `min_data_in_leaf` ≥ 200 (hojas grandes en datos, lr 0,01–0,04) | 8 (30%) | 11 (28%) | +2 pp | 1,0 | no | sí (Abregú) | `ezequielabregu`, `cvfh`, `pfranzd`, `laupasq1967`, `kformoso` |
| `num_leaves` final ≥ 200 | 9 (33%) | 13 (33%) | 0 | 1,0 | no (83) | — | — |
| Corte con la curva de junio / *holdout* | 13 (48%) | 19 (49%) | 0 | 1,0 | **sí** | sí, P1 | — |
| Reescalar rondas (× 1,1) o `min_data`/hessiano al reentrenar con más meses | 5 (19%) | 8 (21%) | −2 pp | 1,0 | **sí** (hessiano) | — | `snehitdua`, `pedro-bosch`, `nicozare`, `pfranzd` |
| Ensamble de varias configuraciones o familias de variables | 9 (33%) | 14 (36%) | −3 pp | 1,0 | *expl.* | — | `keilazavaglia` 7 × 10, `turrivalentin` 10 × 1, `fsteeb1`, `laupasq1967`, `cvfh` |
| Quita CONTINUA «dudosos» con un modelo auxiliar | 2 (7%) | 4 (10%) | −3 pp | 1,0 | no | — | `tomasroel`, `veroq00` |
| Pesos por clase (BAJA+1 < 1) | 4 (15%) | 7 (18%) | −3 pp | 1,0 | **sí** (0,25) | — | — |
| Walk-forward en varios meses | 4 (15%) | 7 (18%) | −3 pp | 1,0 | **sí** | sí, P2 | `ezequielabregu`, `pfranzd`, `segunmo`, `pedro-bosch` |
| Aguinaldo | 1 (4%) | 3 (8%) | −4 pp | 0,64 | *expl.* (c253) | sí, P2 | `nicozare` |
| 20–39 semillas | 8 (30%) | 14 (36%) | −6 pp | 0,79 | **sí** | — | — |
| BO o Optuna midiendo AUC | 10 (37%) | 18 (46%) | −9 pp | 0,61 | — | — | — |
| Ensamble por rango o percentil | 5 (19%) | 11 (28%) | −10 pp | 0,40 | **sí** | — | — |
| Solo BAJA+2 de positivo | 3 (11%) | 9 (23%) | −12 pp | 0,33 | *expl.* | «falló» | — |
| Corte entre 11.750 y 12.500 | 4/24 | 11 | −11 pp | 0,24 | no | — | `ezequielabregu`, `kformoso`, `segunmo` (12.000), `tomasroel` (12.500) |
| Particiones aleatorias o CV para optimizar | 5 (19%) | 13 (33%) | −15 pp | 0,26 | no | «falló» | — |
| **Corte arriba de 12.500** | 0/24 | 6 (15%) | −15 pp | 0,07 | **sí (14.000)** | sí, P1 | ninguna |
| **Saca los préstamos personales del modelo final** | 2 (7%) | 12 (31%) | −24 pp | 0,03 | no | sí (baja) | `arielrojasv`, `mbellesi01` |

Lectura:

- **El corte es lo más claro después de las tendencias.** Mediana del corte vivo: 11.200 (cuartiles 11.000–11.600,
  máximo 12.500). Mediana muerta: 11.500, con cola larga a la derecha (cuartiles 10.600–12.250, seis entre 13.000 y
  14.000). Ningún vivo cortó arriba de 12.500. El 14.000 nuestro estaba fuera del rango de todos los que pasaron.
- **Los préstamos dan el contraste más grande en contra.** Sacarlos del modelo final es cosa de muertos: 12 de 39
  contra 2 de 27. Lo que hicieron los vivos con más frecuencia fue lo de la plantilla de R de la cátedra: sacarlos
  **solo de la BO** (para que el drift de junio no elija los hiperparámetros) y volver a meterlos en el modelo final.
  Cierra con lo que dijo el profesor («funciona peor»).
- **Lo común no separa.** La receta de hiperparámetros, la clase B1+B2, `ccajas` a NA, BO de tres parámetros, ensambles de
  configuraciones, pesos por clase y reescalar al reentrenar están igual de repartidos entre los dos grupos.
- **El público tampoco separa.** Sobrevivientes con público declarado (README o ficha): `laupasq1967` 119,38 (10.600),
  `ezequielabregu` 110,25 (12.000), `pfranzd` 110,17 (10.500), `turrivalentin` 108,57 (11.000), `agustinlovrich`
  107,44 (11.000), `mariofreites` 106,21 (11.000), `keilazavaglia` ~104,6 (11.500, de su tabla de cortes) y `segunmo`
  **103,21** (12.000), que es menos que nuestro 103,785. `patriciojarmoluk` (11.250) y `ernestoatmo` (12.000) no dan el
  número. Ana Dominguez murió con 110,47.

### (b) Ideas que no estaban en el backlog

| Idea | Fuente (ficha) | Por qué vale probarla |
| --- | --- | --- |
| **Señales de evento contra el mes anterior**: `perdio_sueldo`, `inicio_comision`, `productos_perdidos`, `cerro_plazo_fijo`, `racha_caida_ctrx`, `meses_desde_max` | `ezequielabregu` (B3: inicio de comisión, meses con sueldo, pérdida de sueldo), `fsteeb1` (corte de sueldo, desarme de plazo fijo, fin de préstamo, racha de caídas, meses desde el máximo), `jaquelinegirabel` (seis flags de cambio y rachas), `mariofreites` (`tperdio_payroll`, `tinicio_comision`, `cproductos_perdidos`), `pfranzd` e034, `tomasroel` (`new2_dejo_sueldo`) | 6/27 contra 1/39 (las rachas solas aparecen también en `micaelarr` y `clarirz`, muertos). Son baratas en SQL y codifican lo mismo que la tipología de Miranda (primacía, «te suelta la mano») |
| **Sumas y cocientes del mes** (Visa+Master, patrimonio neto, uso del límite, pago/mínimo, transacciones digitales/físicas) | `tomasroel`, `pedro-bosch` (42 + 17), `segunmo` (43), `cvfh` (21), `mariofreites` (11) | +18 pp, no significativo. Las exploramos en c260/c261 con la receta vieja; ir **junto con** las tendencias, no solas |
| **Préstamos fuera de la BO, adentro del final** | `agustinlovrich`, `patriciojarmoluk`, `hmijal`, `nicobaranek`, `luisdanielsuarez`, `lsaldeco`, `veroq00` | si hay BO en la 2, que no la decida una variable con *concept drift* en el mes de validación |
| Flags `_zero` por variable | `lsaldeco`, `luisdanielsuarez`, `veroq00` (más `missing_`) | se combinan con el rank de cero fijo (que ya deja el 0 en 0): baja prioridad |
| Ventana de 6 meses (tendencia, mín., máx. y cocientes contra el máximo, en 40 variables) | `fsteeb1` | en la 2 hay más historia; con 6 meses de panel (como en la 1) no se puede |
| Corregir la probabilidad por el submuestreo, `p·r / (p·r + 1 − p)` | `jaquelinegirabel`, `snehitdua`, `emavaldez` | no cambia el orden dentro de un modelo; importa si se promedian modelos con distinta `r` o se corta por umbral |
| Entrenar sin marzo (202104–202106) | `kformoso`, `emavaldez`, `pedro-bosch` | 3 contra 2; una medición barata si la 2 tiene más meses |
| Pseudo público/privado: 1.000 particiones 25/75 de junio para elegir entre trials por *regret* | `pedro-bosch` | herramienta, no técnica: simula la elección público → privado antes de mandar |
| Filtro de PSI solo sobre lags/deltas de orden 2 (PSI > 0,20 entre train y 202108) | `segunmo` (8 columnas) | barato; ningún otro lo hizo |
| Multiclase con score P(BAJA+2)/(1 − P(BAJA+1)) | `segunmo` (componente M2, 2/3 del blend) | distinto del P(B1)+P(B2) de `kformoso`/`emavaldez`; los tres vivieron |

### (c) Lo que ningún sobreviviente hizo

- **Cortar arriba de 12.500.** 0 de 24 con corte conocido; 6 de 39 muertos (13.000 a 14.000, nosotras incluidas).
- **Un modelo que no sea LightGBM en la entrega** (CatBoost, Random Forest, TabPFN): 0 de 27; 3 muertos (`mldevgit`, `clarirz`, `thenseler-gmail`).
- **Cortar por umbral de probabilidad** (0,025 o 0,0275): 0 vivos, 2 muertos (`tobiartinian`, `thenseler-gmail`).
- **Deflación por IPC o mediana mensual**: 0 vivos, 2 muertos (`agustinberna` con IPC, `micaelarr`). Los vivos que corrigen el drift lo
  hacen con el rank de cero fijo.
- **Corte como proporción de las filas del mes** (llevar el N de junio a agosto en proporción): 0 vivos, 2 muertos
  (`montagnaflor`, `tomasfarias-hub`).
- **Pesos por mes de entrenamiento**: 0 vivos, 1 muerto (`mldevgit`, 202104 a 0,75).
- Casi nadie entre los vivos sacó «outliers» de CONTINUA con un modelo auxiliar (2 vivos contra 4 muertos), validó con
  particiones aleatorias (5 contra 13) ni usó solo BAJA+2 (3 contra 9): no gastar tiempo ahí.

## Tres mecanismos de los que pasaron, leídos del código

Las tablas de arriba cuentan **quién** hizo algo; esto es **cómo**, leído en el código de tres mecanismos que no tienen
equivalente en lo nuestro ni en los notebooks de la cátedra.

**Advertencia.** Son lecturas de código de repos ajenos. Salvo CVFH (que declara la ganancia en junio), nadie publica
cuánto le dio cada pieza: no hay efecto medido, solo el mecanismo. Y «pasó» significa solo **no estar en el txt del
Purgatorio** (ver «Quién es "vivo"» arriba), no que el mecanismo haya sido la causa.

### 1. Un modelo por profundidad de historia (`cvfh`, pasó)

Fuente: `CVFH/DMEYF_CVFH`, `competencia_01/segundo_paso_entrenamiento_competencia_01.py`.

| Idea | Evidencia | Cómo |
| --- | --- | --- |
| **Tres LightGBM, uno por cuánta historia ve, mezclados con pesos elegidos en junio** | `current` sin variables de lag, entrenado en 202103–202106; `hist1` solo con lag1/delta1, en 202104–202106 («no incluimos marzo porque son puros NaN»); `hist2` solo con lag2/delta2, en 202105–202106. Mismos hiperparámetros. Promedio de probabilidades con pesos por grilla de 0,05 que maximizan la ganancia en 202106: 0,35 / 0,30 / 0,35 (por rankings daba 0,15 / 0,20 / 0,65). Declara 430 M en junio; corte 10.500, 16 semillas; el 20% de CONTINUA solo en la validación | con más meses en la 2, cada profundidad de historia tiene su propio conjunto de meses sin nulos, y el ensamble pesado en un mes de validación resuelve el «marzo sin historia» **sin tirar marzo**. Medir contra la receta con lags sobre todos los meses, pareado por semilla; los pesos, en un mes que no sea el de la curva de corte |

Relacionado: `emavaldez`, `kformoso` y `pedro-bosch` (los tres pasaron) entrenan en 202104–202106, sin marzo; `emavaldez`
usa marzo+abril solo para un modelo «sin historia» de segunda etapa (ver 3c). La cátedra no tiene nada para esto: `z701`
entrena por mes, pero solo para medir drift.

### 2. Submuestreo de CONTINUA distinto por semilla, en el modelo final

Fuentes: `z494` (cátedra), Zulip [192767 / 193843], y las fichas y el código de los siete que lo hicieron.

| Idea | Evidencia | Cómo |
| --- | --- | --- |
| **Cada semilla ve otro 10–20% de CONTINUA, también en el modelo final** | La cátedra lo usa al 10% **solo en la bayesiana** (`z494`: `PARAM$trainingstrategy$undersampling <- 0.1`; el final va sin submuestreo y con `min_data_in_leaf / undersampling`), y para la Primera pidió no hacerlo: Denicolay [192767 / 193843] «dejémonos de joder con el 10% de undersampling de los CONTINUA. Ese undersampling recién va a hacer falta para la Segunda Competencia». Aun así, 7 de los 27 que pasaron lo hicieron en el modelo final, contra 1 de 39 muertos | `pos_bagging_fraction` / `neg_bagging_fraction` con `bagging_freq > 0` da el mismo efecto por árbol sin tocar el dataset; o el sorteo por semilla como `kformoso`. Medir pareado por semilla contra la receta, y decidir si se corrige la probabilidad: no hace falta para un top-K de un solo modelo, sí para mezclar modelos con distinta tasa |

Los siete:

| Ficha | Tasa × semillas | Detalle |
| --- | --- | --- |
| `kformoso` | 0,2 × 60 | `KF16.R`: `conservar <- clase_base > 0L \| runif(...) <= UNDERSAMPLING`; multiclase, ranking P(B1)+P(B2), sin corregir |
| `tomasroel` | 0,1 × 50 | — |
| `emavaldez` | 0,2 × 25 | `codigo/modelos/tips_ale_bolano_fe.py` l. 297–298 |
| `jaquelinegirabel` | 0,1 × 20 | corrige con `p·r / (p·r + 1 − p)` antes de promediar |
| `segunmo` | ~0,1 | — |
| `nicozare` | 0,5 × (5 semillas × 3 submodelos) | `scripts/config.py`: 50% de CONTINUA sorteado por semilla, `min_data_in_leaf` 380 → 760. Su README atribuye la mejora a tres cosas juntas: «tratar `BAJA+1` y `BAJA+2` como positivos juntos» (**peso 1**, no 0,25), «submuestrear la clase mayoritaria» y sacar 4 columnas con drift por PSI (`*_fultimo_cierre`, `*_Finiciomora`). El submuestreo **sin** el cambio de etiqueta le dio 93,3 («parecido, sin mejora clara»); con el cambio no publica el número (en vivo contó un salto de ~90 a ~105). Corte 11.500 por la meseta de junio (plana entre 10.750 y 12.000). Lo que le falló: canaritos (66,4), ratios del mes (85–93), random forest (81,6) |
| `snehitdua` | 0,1 | la **misma** muestra para los 18 modelos (no cambia con la semilla) |

El caso de `nicozare` es el que mejor separa las piezas: etiqueta y submuestreo van juntos, y el submuestreo solo no movió nada.

Pesos de clase, en cambio, hay poco y repartido: `laupasq1967` (119 público, el más alto) usa `scale_pos_weight` 0,5
elegido en grilla sobre junio; `la-laguinge` y `pedro-bosch`, `is_unbalance`.

### 3. BAJA+1 y BAJA+2 tratadas distinto (`emavaldez`, pasó)

Fuente: `emavaldez/primeracompetencia` @ `ec1fa75`, `codigo/modelos/tips_ale_bolano_fe.py`.

| Pieza | Qué hace | Líneas |
| --- | --- | --- |
| (a) General **multiclase** | 3 clases, ranking por P(BAJA+1) + P(BAJA+2); BAJA+1 con peso 0,5 («se van en un mes y no pagan; BAJA+2 es la clase que paga») | l. 194, 299, 312, 313 |
| (b) Especialista de `internet >= 1` | binario (BAJA+1 o BAJA+2 contra CONTINUA), entrenado con el último mes etiquetado, sin submuestreo, 24 variables que le ganan a 50 canaritos. Se combina con el general tomando el máximo como valor y la suma de logit como orden | l. 343–346 |
| (c) Segunda etapa BAJA+2 contra CONTINUA | **sin las filas BAJA+1**, solo en la franja de puestos 8.000–30.000 de los clientes con `internet == 0`. Entrenada en 202105–202106 sobre un ranking base fuera de muestra (base entrenada en 202103–202104). LightGBM chico (4 hojas, 100 rondas, 25 variables) con `init_score` = logit de la base calibrado por regresión logística (stacking de residuo). No cambia los valores de probabilidad: reparte los mismos valores por la suma de dos rangos | l. 353–355, 437–438, 442–443, 450–454 |
| (d) Corrección del especialista | lo lleva a la escala del general submuestreado: `p / (p + 0,2·(1−p))` | l. 284 |

**Resultado:** no declara ganancia ni público; entregó 11.250 y pasó. **Origen:** el nombre alude a su tutor Bolaños,
pero en Zulip no hay mensaje de Bolaños con el mecanismo; lo más cercano es [191336] (30-sep): juntar las dos clases es
un problema porque «tienen profit diferente», y el camino es un vector de pesos, «un hack, resuelve una parte». Los
«tips del 5-oct» que cita el código son los del profesor.

**Nosotras:** binario con BAJA+1 a 0,25; `c213` (solo BAJA+2) dio −5,3 público y +4,5 privado pareado (5 de 5);
`c242`/`c243` (pesos 0,5 / 1), nada concluyente.

**Cómo probarlo en la 2:** (i) multiclase con pesos contra nuestro binario, pareado por semilla; (ii) segunda etapa
BAJA+2 contra CONTINUA en la franja del corte, medida por **captura en la franja**, no por ganancia total (la ganancia
total diluye un cambio que solo reordena unos miles de puestos).
