# Optuna y LightGBM: lo que dice la documentación y lo que no probamos

Notas para la Segunda Competencia. El código está en `src/bayesiana_publico.py`.

## Optuna

### Ask-and-tell

La interfaz normal de Optuna (`study.optimize(objective)`) supone que el objetivo es una función que Optuna llama.
Cuando el valor sale de afuera —entrenar, escribir los archivos, mandarlos al bot, esperar la respuesta— se usa
**ask-and-tell**:

```python
trial = study.ask(DISTRIBUCIONES)        # Optuna propone; con fixed_distributions no hace falta suggest_*
...                                      # entrenar, escribir, enviar, leer la respuesta
study.tell(trial, public_gain_mean)      # Optuna aprende
# si algo falla en el medio: study.tell(trial, state=TrialState.FAIL)
```

Es exactamente el método que el profesor contó en `general > jugando con el Public` [203439]: cada iteración de la
bayesiana genera el archivo, se sube, y se le devuelve el valor del Public Leaderboard; su versión lo pedía con
`input(...)` [203443]. `bayesiana_publico.ciclo()` hace las dos cosas (con una función que entrena y envía, o a mano
con `input`). Un trial = un submit de 20 archivos = una unidad del cupo.

### Cargar historia: `create_trial` + `add_trial(s)`

```python
t = optuna.trial.create_trial(params=p, distributions=DISTRIBUCIONES, value=publico,
                              user_attrs={"private_gain_mean": privado, "submit": nombre})
study.add_trials([t, ...])
```

- `create_trial` **valida** cada valor contra su distribución: un `envios` de 15.250 con `step=500` da error.
- Las distribuciones de la historia tienen que ser **las mismas** que las de `ask`. El TPE compara por
  distribución; si cambia el rango o el `step`, el parámetro es otro y la historia no informa.
- Los trials agregados quedan `COMPLETE` y **cuentan para `n_startup_trials`** del `TPESampler` (10 por defecto):
  con 28 trials de la 1 cargados, el primer `ask` ya es bayesiano (en el dry-run propone 1.750 rondas, 116 hojas,
  hessiano 50,7, feature_fraction 0,43, 14.500 envíos).
- **Un study por objetivo.** El público de la 2 es otro mes y otra partición; los valores de la 1 no son
  comparables con los de la 2 aunque el espacio sea el mismo. La historia de la 1 sirve para ensayar el circuito
  (y como prior solo si el dataset y la ganancia son comparables). El privado va en `user_attrs`, nunca como valor.
- No mezclar medias de 5 y de 20 archivos si se puede evitar (`cargar_historia(min_archivos=20)`): tienen distinto
  ruido y el TPE no lo sabe.

### Por qué no `LightGBMTunerCV`

`optuna.integration.lightgbm.LightGBMTunerCV` (`optuna-integration`) afina por etapas (`feature_fraction`,
`num_leaves`, bagging, regularización, `min_child_samples`) con `lgb.cv` sobre **folds del mismo dataset**. Para
esta competencia no sirve:

- la métrica la calcula `lgb.cv` sobre folds aleatorios, que mezclan meses; nuestra validación es temporal;
- ganancia@K (los K mejores de un mes) no es una métrica por fila: se puede escribir como `feval`, pero el K y la
  prevalencia cambian por fold y el resultado no se parece a lo que mide el bot;
- no puede usar el público como objetivo (no hay un `tell`).

## LightGBM: lo que no probamos y vale la pena

Verificado acá con LightGBM 4.7 sobre datos sintéticos donde dice «verificado».

- **`Booster.predict(X, num_iteration=k)`**: predice con los primeros `k` árboles. Con `gbdt` es **idéntico** a
  entrenar `k` rondas (verificado). Un modelo de 2.000 rondas da gratis las curvas de 1.000, 1.250, 1.500, 1.750 y
  2.000: la comparación de rondas del postmortem (+6,8 privado pareado de 2.000 contra 1.000) se puede hacer sin
  reentrenar, y elegir rondas por la meseta igual que el corte.
- **`path_smooth`**: suaviza la salida de cada hoja hacia la de su padre, más cuanto menos datos tiene la hoja. Con
  `min_data_in_leaf = 0` (la receta) es la regularización natural para hojas chicas; no la tocamos nunca.
- **`pos_bagging_fraction` / `neg_bagging_fraction`** (con `bagging_freq > 0`): bagging balanceado, submuestrea
  CONTINUA en cada iteración y distinto por semilla. Es el «submuestreo distinto por semilla» que varios compañeros
  usaron (en la matriz de Vercel, 8 de 20 que submuestrean murieron, contra 31 de 46 que no) sin tocar el dataset.
- **`Booster.refit(X, y, decay_rate=...)`**: conserva la estructura de los árboles y recalcula las salidas de las
  hojas con datos nuevos. Candidato para incorporar el mes más reciente con etiqueta parcial (BAJA+1 de 202107) sin
  reentrenar.
- **Semillas.** `seed` genera las demás (`feature_fraction_seed`, `bagging_seed`, `data_random_seed`, `drop_seed`,
  `extra_seed`…) **salvo que alguna se fije aparte**, en cuyo caso esa manda. Verificado: con `feature_fraction_seed`
  fijo, dos `seed` distintos dan exactamente el mismo modelo cuando no hay bagging. En la receta (sin bagging) toda
  la variación entre semillas es el muestreo de columnas (`feature_fraction` y `feature_fraction_bynode`) más el
  `data_random_seed` del binning, que muestrea 200.000 filas (`bin_construct_sample_cnt`) y por eso importa con
  nuestras 654.066 (la 1 construía un `Dataset` nuevo por semilla). No fijar
  `feature_fraction_seed` en ningún lado, o las 20 semillas dejan de ser 20 modelos.
