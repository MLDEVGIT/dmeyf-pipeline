# El podio de la Primera Competencia

Fichas completas de los tres primeros, copiadas sin editar de `postmortem_vercel/fichas.csv` (lectura automática de
los repos que publicó Emmanuel Valdez, Zulip 204115). Los puntajes son los de la nota de clase. Los mecanismos leídos
del código están en `backlog.md` § «Tres mecanismos de los que pasaron».

## 1.º — Emmanuel Valdez (~364)

Repo: `emavaldez/primeracompetencia` · Python · LightGBM

**Clase objetivo.** prepare.py arma clase_ternaria según la presencia del cliente en los dos meses siguientes. Modelo general: tres clases (CONTINUA = 0, BAJA+1 = 1, BAJA+2 = 2) y la probabilidad que se usa es P(BAJA+1) + P(BAJA+2). Especialista de deudores: binaria, positivo = BAJA+1 o BAJA+2. Segunda etapa: binaria, BAJA+2 contra CONTINUA, sin las filas BAJA+1.

**Meses entrenamiento.** 202104, 202105, 202106

**Meses validacion.** —

**Meses prediccion.** 202108

**Submuestreo.** En el modelo general se conserva el 20% de las filas CONTINUA (UNDERSAMPLING = 0,2), sorteadas con un generador sembrado con la semilla de la corrida, y todas las BAJA+1 y BAJA+2. El especialista de deudores se entrena sin submuestreo y su probabilidad se transforma con p / (p + 0,2 (1 − p)). La segunda etapa no submuestrea.

**Calidad de datos.** ccajas_depositos se pasa a NA en 202105 (tabla ROTAS) antes de calcular lags y deltas. prepare.py exige con un assert que la cantidad de BAJA+2 por mes coincida con una tabla escrita en el código (202103: 960, 202104: 1139, 202105: 870, 202106: 1098).

**Drifting.** 14 montos (lista PERCENTIL_CERO_FIJO) se reemplazan por su percentil dentro del mes en escala −100 a 100, con positivos y negativos ordenados por separado y el cero en 0; sus lags y deltas se calculan sobre el percentil. A Visa_fultimo_cierre y Master_fultimo_cierre se les resta la moda del mes. Las cinco columnas de internet (cruda, 2 lags, 2 deltas) se ponen en 0 en los meses de entrenamiento anteriores al último. Los lags, deltas, razones y ventanas de las variables Visa_* y Master_* no entran a los modelos.

**Variables intra mes.** No se observa en el código: no se crean variables nuevas por combinación de variables del mismo mes. Las transformaciones dentro del mes (percentil de 14 montos y resta de la moda en dos fechas) reemplazan a la variable original.

**Variables historicas.** Para todas las columnas salvo numero_de_cliente y foto_mes: lag 1, lag 2, delta 1 y delta 2 por cliente. Para las variables de monto o conteo (nombre que empieza con m o c, con o sin prefijo Visa_/Master_, menos 6 excepciones): razón contra el lag 1, promedio, mínimo y máximo de la ventana de 3 meses (mes actual, lag 1 y lag 2) y razón contra el promedio y contra el máximo. Para las variables con lag que no son Visa_*, Master_* ni internet: pendiente por cuadrados mínimos de los tres valores (_tend3) y, donde no existe _avg3, el promedio de la ventana (_avg3p).

**Seleccion de variables.** El especialista de deudores elige sus variables durante la corrida: agrega 50 columnas de números al azar (canaritos), entrena 5 veces con 200 rondas, promedia la importancia "gain" y conserva las variables cuya importancia media supera la del canarito de mayor importancia (mínimo 5). Según el README quedan 24 de 1.160 para 202106 y 20 de 1.160 para 202104. El modelo general usa todas las columnas menos clase_ternaria, numero_de_cliente y la historia de Visa_*/Master_*. La segunda etapa usa una lista de 25 variables escrita en el código (VARIABLES_2); el comentario indica que se eligió con canaritos y el código de esa selección no está en el repositorio.

**Optimizacion de hiperparametros.** No se observa en el código: los hiperparámetros están escritos como constantes.

**Hiperparametros finales.** General (multiclass, 3 clases): learning_rate 0,027, num_leaves 31, min_data_in_leaf 200, feature_fraction 0,5, max_bin 255, 500 rondas. Especialista (binary): learning_rate 0,03, num_leaves 15, min_data_in_leaf 50, feature_fraction 0,3, max_bin 255, 200 rondas. Segunda etapa (binary): learning_rate 0,03, num_leaves 4, min_data_in_leaf 200, feature_fraction 0,3, lambda_l2 20, max_bin 63, 100 rondas.

**Semillas.** 25 semillas escritas en la lista SEMILLAS de reproducir.py (de 800029 a 801197). Cada una se usa para el sorteo del submuestreo y como seed de los tres LightGBM de esa corrida. El modelo que puntúa 202105 y 202106 para la segunda etapa usa la semilla 800011; la selección con canaritos usa seeds 9000 a 9004 y generadores cuya semilla depende del mes y de la repetición.

**Cantidad de semillas.** 25

**Ensamble.** Dentro de cada semilla: en los clientes con internet >= 1 se combinan el general y el especialista (los valores son el máximo de los dos, ordenado, y se asignan según la suma de los logit de ambos); después una segunda etapa reordena los puestos 8.000 a 30.000 de los clientes con internet = 0. Entre semillas: promedio de las probabilidades de las 25 corridas.

**Corte.** Cantidad fija: los 11.250 clientes de mayor probabilidad promedio (CORTE = 11250), con orden estable ante empates. No se observa en el código cómo se eligió esa cantidad.

**Validacion.** No se observa en el código medición de ganancia ni partición de validación. Lo que hay: un assert que compara la cantidad de BAJA+2 por mes con una tabla de referencia; la comparación del sha256 de cada lista con esperado.json y el conteo de clientes en común con la lista incluida en el repositorio; y, en la segunda etapa, las probabilidades de 202105 y 202106 obtenidas con un modelo entrenado con 202103 y 202104, que se usan como entrada de entrenamiento y no como medición. Los comentarios citan mediciones (PSI, KS, tasas de baja por mes) cuyo cálculo no está en el repositorio.

**Salidas.** En codigo/salida/: competencia_01.parquet (dataset con la clase), parcial/ids.npy y parcial/<semilla>.npy (probabilidades por semilla), semilla_<semilla>.csv (lista de cada semilla) y TipsAleBolanoFE_final.csv (lista final, un numero_de_cliente por línea, sin encabezado). Por pantalla: las variables elegidas por el especialista, el tiempo de cada semilla, el sha256 de la lista final y su comparación con esperado.json.

## 2.º — Carolina Franco (~315)

Repo: `CVFH/DMEYF_CVFH` · Python, SQL · LightGBM

**Clase objetivo.** Binaria clase_binaria12: positivo = BAJA+1 o BAJA+2. La ganancia en validación se mide sólo contra BAJA+2. La clase ternaria se construye en el notebook a partir de la presencia del cliente en el mes siguiente y en el subsiguiente.

**Meses entrenamiento.** 202103, 202104, 202105, 202106

**Meses validacion.** 202106

**Meses prediccion.** 202108

**Submuestreo.** En los modelos de validación: todas las filas cuya clase no es CONTINUA y una muestra al azar del 20% de las CONTINUA (random_state = 42), por separado en cada uno de los tres subconjuntos. Los modelos finales se entrenan con todas las filas, sin submuestreo.

**Calidad de datos.** En el notebook, ccajas_depositos pasa a NULL en los meses en que todos sus valores son 0 o NULL. Las fechas de alta de tarjeta que no son mayores que 0 quedan en NULL al calcular la antigüedad. No se observa otro tratamiento en el código.

**Drifting.** Cada columna numérica cuyo nombre empieza con m minúscula (incluidos sus lags y deltas) se divide, dentro de cada foto_mes, por el máximo del mes, o por el máximo valor absoluto del mes si hay valores negativos; el cero queda en cero. La columna escalada reemplaza a la original y se renombra con el sufijo _norm0.

**Variables intra mes.** 21 variables calculadas en SQL sobre el mes: seis sumas Visa+Master (consumo, transacciones, saldo total, límite de compra, pago mínimo, pagado), saldo_liquido_total, deuda_prestamos_total, trx_digitales, trx_fisicas, un flag de cliente sin saldo ni consumo de tarjetas, sin descubierto preacordado y sin préstamos, cinco cocientes (utilización del límite, pagado sobre saldo, pagado sobre pago mínimo, liquidez sobre deuda, proporción de transacciones digitales), tres tickets promedio (Visa, Master, débito) y la antigüedad en meses de Visa y de Master.

**Variables historicas.** Lag 1, lag 2, delta 1 y delta 2 de cada columna numérica de la tabla con las variables del mes (todas menos foto_mes, numero_de_cliente y clase_ternaria), tomando la fila anterior y la de dos filas atrás del mismo cliente ordenado por foto_mes; se calculan en bloques de 25 columnas. En el script, las columnas con lag1 o delta1 alimentan el modelo hist1 y las de lag2 o delta2 el modelo hist2.

**Seleccion de variables.** No se observa selección por importancia en el código. Las columnas se reparten por nombre en tres subconjuntos (sin lag ni delta; lag1 y delta1; lag2 y delta2) y se quitan las que contienen prestamos_personales. Según el README se probaron versiones que excluían variables de baja relevancia; ese código no está en la carpeta posteada.

**Optimizacion de hiperparametros.** No se observa en el código: los valores están escritos en el script. Según el README provienen de experimentación previa que no forma parte de este pipeline. Lo que el script sí busca es la combinación de pesos del ensamble, en una grilla con paso 0,05, sobre 202106.

**Hiperparametros finales.** Los mismos para los tres modelos: objective = binary, boosting_type = gbdt, metric = auc, max_bin = 31, num_leaves = 18, learning_rate = 0.00625238, min_data_in_leaf = 1748, feature_fraction = 0.939774, bagging_fraction = 0.376689, bagging_freq = 1, boost_from_average = True, feature_pre_filter = False, 4928 iteraciones.

**Semillas.** np.random.seed(42) seguido de np.random.choice(1000000, size=50, replace=False) genera 50 semillas; las primeras 16 se usan en el entrenamiento final. Los modelos de validación usan la primera de la lista. El submuestreo usa random_state = 42.

**Cantidad de semillas.** 16

**Ensamble.** Dos niveles. Por semilla: promedio ponderado de las probabilidades de los tres modelos (current, hist1, hist2) con los pesos de mayor ganancia en 202106; en paralelo, promedio ponderado de los rankings percentiles de los tres modelos con sus propios pesos. Entre semillas: el score de cada semilla se pasa a ranking percentil y se promedian las 16 con igual peso. Según el README se entrega la variante de probabilidades.

**Corte.** Cantidad fija: los 10.500 clientes de mayor score (N_ENVIOS_FINAL = 10500). La grilla de validación recorre de 8.000 a 15.000 envíos de a 1.000, pero la cantidad que surge de ahí no se usa para el archivo final.

**Validacion.** Un mes posterior al entrenamiento: los tres modelos se entrenan con meses hasta 202105 (current 202103-202105, hist1 202104-202105, hist2 202105) y predicen 202106. Sobre 202106 se calcula la ganancia (2.200.000 × 0,5 − 27.500 por acierto y −27.500 por envío sin acierto, contra BAJA+2) para cada combinación de pesos y cada cantidad de envíos. Se usa una sola semilla.

**Salidas.** En resultados/: por cada semilla, cinco Parquet (ranking de current, de hist1, de hist2, del ensamble de probabilidades y del ensamble de rankings); el archivo modelo_final_semillas_completadas.txt con las semillas terminadas; y dos CSV sin encabezado con 10.500 numero_de_cliente: multisemilla_ensemble_proba_10500_nsemillas_16.csv y multisemilla_ensemble_rank_10500_nsemillas_16.csv. El notebook escribe data/competencia_01_fev4.parquet.

## 3.º — Ezequiel Abregú (~300)

Repo: `ezequielabregu/DMEyF_competencia_1` · Python, SQL · LightGBM

**Clase objetivo.** Binaria: positivo = BAJA+1 o BAJA+2, negativo = CONTINUA (esquema 'bajas' de la configuración 'z470_bajas'). clase_ternaria se calcula en SQL en el 01. La ganancia de los backtests cuenta sólo BAJA+2 como acierto.

**Meses entrenamiento.** 202103, 202104, 202105, 202106

**Meses validacion.** 202105, 202106

**Meses prediccion.** 202108

**Submuestreo.** El modelo final entrena con todas las filas con clase de 202103–202106, sin submuestreo. En la búsqueda de Optuna (08) se entrena con todas las bajas y el 20 % de los CONTINUA de 202103–202104, elegidos con un generador de semilla 979201; al pasar a todos los datos, min_data_in_leaf se divide por 0,2.

**Calidad de datos.** El 01 calcula por variable y mes el porcentaje de nulos y de ceros y lista las variables con algún mes a más de 5 puntos de la mediana. La variante V5 del 04 excluye Master_fultimo_cierre, Visa_fultimo_cierre, Master_Finiciomora y Visa_Finiciomora y pasa ccajas_depositos a NA en 202105 (también sus derivadas). No hay imputación de nulos. numero_de_cliente se lee como BIGINT y las 152 variables pasan a float32.

**Drifting.** Los 73 montos (columnas que empiezan con 'm', 'Visa_m' o 'Master_m') se reemplazan por su percent_rank dentro del mes (variables rk_, bloque B4). Los lags y deltas de montos del bloque B5 se calculan sobre el ranking con el cero fijo (rk0_: el 0 queda en 0, los positivos en (0, 1] y los negativos en [−1, 0)). Las variables de B2 y B3 se calculan sobre las columnas originales. foto_mes no entra como variable. La exclusión de los préstamos personales (V1) se evalúa en el 04 y no forma parte de V5.

**Variables intra mes.** En la combinación entregada: el reemplazo de cada monto por su ranking dentro del mes (B4) y el indicador tiene_caja_ahorro (mcaja_ahorro > 0) del bloque B3. El bloque B1 (dos cocientes consumo/límite de tarjeta, suma de saldos de tarjetas, cociente saldo/rentabilidad anual y dos rankings) está definido en el 05 y no integra la combinación B2+B3+B4+B5.

**Variables historicas.** B2 (56): lag 1, lag 2, delta 1, promedio, mínimo, máximo y pendiente (regr_slope contra cliente_antiguedad) sobre los últimos 3 meses, para 8 variables. B3 (17): inicio del pago de comisión, meses con comisión y con sueldo en 3 meses, lags de cpayroll_trx y mpayroll, pérdida de sueldo, consumo Visa sobre el promedio de los 3 meses anteriores, caída de saldo, caja de ahorro en el mes anterior y deltas de transacciones de tarjeta, consultas en caja y call center. B5 (293): lag 1 y delta 1 del resto de las variables.

**Seleccion de variables.** No se observa selección por importancia. La lista de variables se arma por bloques: base V5 con los montos reemplazados por su ranking, más B2, B3 y B5, sin las derivadas de columnas excluidas; según el README, 507 variables. numero_de_cliente queda entre las variables. Cada bloque y combinación se compara contra la base con backtests pareados por semilla (Wilcoxon) en el 05.

**Optimizacion de hiperparametros.** Optuna con TPESampler (semilla 979201), N_PRUEBAS = 50, estudio guardado en SQLite. Maximiza la ganancia de meseta de la prueba A (entrena 202103–202104 submuestreado, predice 202106 completo) con una semilla de LightGBM. Espacio: num_leaves 8–512, min_data_in_leaf 10–2.000, learning_rate 0,01–0,1 y num_iterations 200–1.500 en escala logarítmica; feature_fraction 0,2–1,0; bagging_fraction 0,4–1,0. La prueba 0 son los valores de z470. Las 3 de mayor ganancia se validan con todos los datos y 5 semillas en A y C contra z470 (t pareado y Wilcoxon).

**Hiperparametros finales.** Prueba 42 de Optuna (exp/08_optuna/hiperparametros_p42.json): objective binary, boosting gbdt, max_bin 31, num_leaves 36, min_data_in_leaf 1.855, learning_rate 0,0423, feature_fraction 0,4027, bagging_fraction 0,9291, bagging_freq 1, num_iterations 637, lambda_l1 0, lambda_l2 0, min_gain_to_split 0, feature_pre_filter false.

**Semillas.** Semilla primigenia 979201. Juego 1: 20 primos de 6 dígitos sorteados sin reemplazo con numpy.random.default_rng(979201) (02). Juego 2: otros 20 primos, sin repetir los del juego 1, con default_rng([979201, 2]) (03). Los backtests usan las primeras 10 del juego 1 y la validación del 08, las primeras 5. El mismo número alimenta el sampler de Optuna, el submuestreo del 08 y el sorteo del 07.

**Cantidad de semillas.** 40

**Ensamble.** Promedio de las probabilidades de 40 modelos LightGBM con los mismos hiperparámetros y variables y distinta semilla: dos corridas del 03 de 20 semillas cada una, promediadas en el 07. El 07 arma además 20 promedios de 20 modelos sorteados entre los 40 (archivos Dist), que no son el archivo entregado.

**Corte.** Cantidad fija: los 12.000 clientes de mayor probabilidad promedio (N_ENVIOS = 12_000 en el 03, N = 12_000 en el 07). Según el README, N se eligió con el leaderboard público. El 03 tiene un modo 'auto' que toma el promedio de los N de meseta de los backtests A y B, redondeado a 500 y acotado a 8.000–15.000.

**Validacion.** Backtests con dos meses entre entrenamiento y predicción: A (entrena 202103–202104, predice 202106) y B (entrena 202103, predice 202105); C (entrena 202103–202105, predice 202106) como referencia para variables con historia. 10 semillas por configuración; la métrica es la ganancia en el máximo de la curva promedio suavizada con media móvil centrada de 501; las alternativas se comparan semilla por semilla con Wilcoxon. Según el README, también se usa el leaderboard público con 20 semillas.

**Salidas.** En el repositorio: entrega_final/final01fe03x40N12000/final01fe03x40N12000_locro.csv (12.000 líneas, un numero_de_cliente por línea, sin encabezado) y su .sha256. Al correr, los notebooks escriben data/ (parquets base y de variables), exp/ (curvas .npz, probabilidades .npy por semilla, JSON de configuración, CSV de resumen y comparación) y entregas/ (CSV por semilla, de semillerío, del promedio final, 20 ensambles y registro_submits.md); esas carpetas no están versionadas.
