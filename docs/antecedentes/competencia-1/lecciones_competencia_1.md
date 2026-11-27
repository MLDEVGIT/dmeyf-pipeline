# Lecciones de la Primera Competencia

Resumen en prosa de `notebooks/n00_postmortem_c1.ipynb`, para quien no abra el notebook. Los números salen del
privado que publicó el profesor el 13-oct-2026 (`PrimeraDetalle.txt`, Zulip [204258]) cargado en el ledger por
`scripts/p100_privado.py`.

**Es un postmortem, no un reglamento.** La Segunda Competencia usa ~36 meses de datos; lo de acá es de un panel de 6
meses y de agosto 2021. Los cortes, las bandas y los folds no se trasladan como números: lo que sobrevive es el
método (cota inferior de la tasa marginal, peor mes como escenario, el público solo para descartar, diversidad de
semillas, BAJA+1 tratada distinto), como procedimiento candidato a re-evaluar con walk-forward. Los procedimientos
de medición (ledger con hipótesis, 20 archivos por submit, pareado por semilla, ids por score) siguen vigentes
porque no dependen del dataset.

## Qué pasó

Quedamos en el **Purgatorio**, 10.ª de 43, con **296,615** en el privado (la línea de muerte era 300). La entrega,
`c241_rondas2000_ens20_14000`, tenía 103,785 de público. En 822 archivos y 103 batches mandamos tres batches
arriba de 300; los tres eran la receta con lags a **10.000 envíos** (`c201_lags_10000` 302,35, `c201_lags20_10000`
302,30, `c201_lags_11500` 300,10). La entrega quedó 5,7 M debajo del mejor privado que llegamos a medir.

## La causa principal: elegimos el corte por el pico del público

Cada corte se midió con 20 archivos, así que tenemos la curva de corte real en las dos partes. Con la misma receta
(`c201`), el público picaba en 14.000 (103,0) y el privado en 10.000 (302,3); a 14.000 el privado era 289,0. Es lo
que el profesor explicó después [203241]: público y privado suman la curva total, que es la más suave; donde una
tiene un pico, la otra tiene un valle. Los 40 compañeros del Purgatorio que entregaron su archivo ordenado por score
tenían el pico de su privado en la posición 10.008 (mediana) y entregaron 11.300. Nosotras, 14.000.

Los folds locales tampoco lo veían (el minimax de `c216` daba 13.500): empujaban en la misma dirección que el
público. **Lo que habría funcionado acá era elegir el corte por la meseta** de las curvas reales de los meses
locales, con minimax del regret entre ellos si no coincidían, en vez del argmax de una curva sola (un mes o el
público).

- **El pico público era ruido de partición, y no se podía ver desde el público.** Con T = público + privado, el
  residuo P − T/4 de `c201` pasa de −0,6 a 10.000 a +5,0 desde 14.000: ~5 fugados de la banda 10.000–14.000 cayeron
  de más en el público y el privado (= 3·T/4 − residuo) los perdió. La banda tiene ~91 fugados, así que el azar de
  la partición da ±4,5 M; el +5,5 observado son 1,2 desvíos. Ninguna semilla achica ese ruido y suavizar la curva
  pública tampoco: el residuo es un paseo al azar en K y queda como escalón (n00 §5b).
- **Junio solo no nos salvaba; el minimax entre mayo y junio sí.** Con los modelos cacheados de la 1, junio (`c216`,
  3 semillas) picaba en 14.000, igual que el público; mayo (`c222`, 1 semilla) en 7.750; el agosto total de `c201`,
  en 10.000. El minimax del regret entre las dos curvas reales daba 10.500, al lado del 11.000 que usábamos con
  `c107` antes de perseguir el pico público. Lo que falló fue asumir que agosto se parecía a junio y reescalar su
  curva por prevalencia en vez de usar la de mayo (n00 §5b).
- **El margen, no el máximo (n00 §5c).** Una banda de clientes paga si su tasa marginal de fugados supera
  0,0275/1,1 = 2,5%. La banda 10.000–14.000 estaba en 3,32% en junio (le sumaba +36 M), en 1,77% en mayo y en
  **2,27% en agosto** (restó −10,3 M de ganancia total; los fugados reales salen de `public_b2 + private_b2` de cada
  archivo). Los tres meses se separan 1,5 puntos; el ruido binomial de esa banda es 0,27: lo que cambia de mes a mes
  es la forma de la curva, no la suerte. Tres consecuencias:
  - Una **cota inferior** (tasa − 1 desvío > 2,5%) con el ruido de un solo mes no alcanza: junio solo frena en
    13.500 (296,6 privado con `c241`). Con mayo y junio frena en 7.750: sirve como límite del rango, no como corte.
  - La **prevalencia como distribución** (bajas por mes 874–1.143, P ~ N(1.020, 110)) no mueve el corte de junio:
    su banda cae al 2,5% recién con 826 fugados, y el *regret* esperado sigue mínimo en 14.000. El peor caso entre
    las formas de mayo y junio da 11.250, al lado del minimax de 10.500.
  - El **público por banda** no resuelve el margen: en 10.000→13.000 decía 2,71% ± 0,59 y era 2,21%; ubicó del lado
    correcto del 2,5% 6 de 10 bandas. Solo descarta bandas con Δ público negativo.

  Procedimiento candidato a validar con walk-forward: (a) no pasar del último K cuya banda final de 1.000 supera
  2,5% con cota inferior que incluya la dispersión entre meses locales; (b) dentro de ese rango, el corte que
  minimiza el *regret* en el peor mes, con la prevalencia como distribución; (c) el público solo para descartar.
  Es lo de §5b (meses reales, minimax, nunca el argmax) vuelto procedimiento. Con 6 meses solo se pudo armar
  *ex post* con dos meses locales; con ~36 se puede medir si de verdad elige mejor que el argmax.

- **Los que pasaron tenían la misma curva y cortaron con margen (n00 §10).** El profesor publicó los mismos gráficos
  para los que pasaron, anonimizados («Zielo»): 27 alumnos (28 ids; uno es medio batch), privado mediano 303,85
  contra 292,57 del Purgatorio, y 18 de 27 pasaron por menos de 5 M. De la curva de la entrega abierta por clase
  salen los fugados exactos del top K para los dos grupos: la tasa marginal media de BAJA+2 por banda de 1.000 es
  **la misma** hasta 10.000 (3,09% contra 3,05% en 9.000–10.000). Lo que cambia es dónde frenaron: la última banda
  que agregaron pagaba **3,2%** en la mediana de los que pasaron y 2,6% en el Purgatorio; 23 de 25 de los que
  pasaron cortaron con la última banda todavía arriba del 2,5% (ninguno buscó el borde de la meseta), y 16 de 40
  del Purgatorio cortaron después de su cruce. Ninguno pasó con más de 12.500 envíos. Nuestra `c201` a 10.000 daba
  402,3 de ganancia total, sobre la mediana de los que pasaron (401,5): el modelo alcanzaba; los 4.000 clientes
  siguientes, al 2,2–2,4%, no.
- **Confirmación externa del profesor** (`J-Clase 09 > punto de corte`, [204989]/[204990]), reproducida exacta con
  los archivos de los dos grupos: los archivos con público > 100 que fracasaron tenían mediana de **12.250** envíos;
  los que pasaron, **11.000** (11.300 con público > 105). Y su tabla de [197324] (público 100–105 → 15% de los
  archivos pasa 300; > 105 → 42%) sale igual; sobre la competencia entera, 24% y 47%.
- **BAJA+1, la clase que no paga:** el top 10.000 de cualquiera trae ~980 BAJA+1 (casi todos los del mes) contra
  ~610 BAJA+2: 1,6 por cada BAJA+2, ~27 M de costo. Igual en los dos grupos.

## El público no servía para las decisiones finas

- Entre todos nuestros submits, público y privado correlacionan 0,72: un modelo claramente mejor gana en las dos.
  Pero en las 83 comparaciones que el ledger tenía registradas («esto contra aquello»), **el signo del delta
  público coincidió con el del privado en el 48%**: una moneda.
- Pareando archivo contra archivo por semilla, el público dijo «pierde» a 25 de 29 variantes de 5 semillas y el
  privado solo a 9. Calendario corregido, feature_fraction 0,4 y target solo BAJA+2 tuvieron 5 de 5 semillas a favor
  en el privado y 0–1 de 5 en el público. Con 5 pares el Wilcoxon no baja de p = 0,0625: nada de eso es
  concluyente, pero muestra que variantes de ±2 no se pueden descartar con el público.
- De los 18 compañeros del Purgatorio que llegaron a mandar un batch arriba de 300, solo 2 lo habrían elegido
  quedándose con su mejor público. Los cuatro «casos tristes de overfitting» que nombró el profesor [204268] no son
  los de menor correlación público/privado: son los que tuvieron los picos públicos más altos (108–112) y los
  eligieron.

## Lo que sí funcionó

**2.000 rondas.** Pareado con 20 semillas a 14.000: +0,85 en el público (14 de 20 semillas, p = 0,13: no
concluyente ahí) y **+6,8 en el privado** (19 de 20, p < 0,001). Fue la mejor decisión del último tramo y el
privado la confirma con más fuerza que el público. Lo que la arruinó fue el corte.

**El ensamble por rango.** En el privado le gana a la semilla media: +2,8 en `c201` (unos cuatro errores estándar)
y +0,8 en `c241`.

## Semillas y ruido

El desvío por archivo entre semillas es 1,9 en el público y 3,0 en el privado; el cociente (1,77) es casi
exactamente √3, como si fuera ruido de conteo sobre el triple de registros. La media de 20 archivos tiene un error
estándar de ~0,45 en el público y ~0,7 en el privado. Las 5 primeras semillas, que en el público estaban 1,2 y 1,7
por encima de la media de 20, en el privado estuvieron 0,1 y 1,0 por debajo: la suerte de una semilla no se
transfiere. Dentro de un mismo batch la correlación entre el público y el privado de cada archivo es 0,03 (0,03
también en los 8.470 archivos del curso). El −1 que habíamos visto en `z301` era una tautología: con una selección
fija y particiones al azar, lo que gana una parte lo pierde la otra; acá la partición está fija y cambia el modelo.

## Los compañeros

La matriz de técnicas de los 66 repos (Vercel) cruzada con el Purgatorio: con 31 técnicas y 66 repos casi todo cabe
en el azar. Una sola pasa la corrección de Bonferroni: **las variables de tendencia** (pendientes sobre ventanas),
con 29% de Purgatorio entre quienes las entregaron contra 73% entre quienes no (Fisher p = 0,001). Nosotras las
exploramos y no las entregamos. Los seis que no usaron lags murieron todos. De los cinco públicos altos que
seguimos durante la competencia, dos murieron (Ani-victoria = Ana Dominguez, ~110 público; farpp8 = Federico
Ramirez, 103); los tres que pasaron (Abregú, Lovrich, Freites) cortaron en 11.000–12.000 con 40–60 semillas, y dos
de ellos eligieron el corte con junio, no con el público.

## Similaridad de listas (índice del profesor, [204259])

- **Diversidad de semillas:** dos semillas nuestras comparten Jaccard 0,93 (solapamiento 0,96) a 14.000, más que las del modelo «excelente» del profesor (0,78–0,83). Con Jaccard su escala es coherente con lo que medimos, pero no hay fórmula publicada. Hay poca diversidad, así que promediar 20 semillas suma poco: +2,8 en el privado de `c201` y +0,8 en el de `c241`. 2.000 rondas no las hace más parecidas (−0,008), así que eso no explica la diferencia entre los dos. Variantes como comisión deflactada, `feature_fraction` 0,4 o BAJA+1 a 0,5 movieron la lista lo mismo que una semilla: con 5 archivos no podían medirse.
- **Distancia a los que pasaron:** 10 de los 27 sobrevivientes publican su CSV. Recortada a su K, nuestra lista está a Jaccard 0,74–0,86 (mediana 0,79) de cada uno, y entre 92% y 99% de sus clientes estaban en nuestros 14.000. No era «otro modelo» (0,65–0,69 en la escala del profesor): era casi la misma lista con 2.000–3.600 clientes de más en la cola.

## Cosas de procedimiento

- `escribir_envios` escribía los ids ordenados por número de cliente: la curva del profesor salió una recta. Ya
  escribe por score.
- Mandar mucho no es overfitear: dentro del Purgatorio, más archivos se asocia con mejor privado final (Spearman
  0,45). Overfitear es **elegir** por el público.
- El ledger con hipótesis y `delta_contra` es lo que permitió este postmortem: se mantiene.

Las hipótesis que valdría la pena volver a medir en la 2, con su evidencia de la 1, están en `docs/backlog.md`.
