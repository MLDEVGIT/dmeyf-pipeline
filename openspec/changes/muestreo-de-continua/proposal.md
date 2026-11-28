# Proposal

## Why

Todos los cambios que siguen a `esqueleto-del-pipeline` reentrenan el catálogo, y cada brazo de cada experimento es
entrenar 5 o más semillas sobre ~507.000 filas (train 201903–201906), de las que más del 99 % son CONTINUA. Un
entrenamiento más barato se paga en todos los experimentos que vienen después, en el crédito de las VMs y en el tiempo
hasta la clase, y es la condición para que exista `reajuste-mensual`, que reentrena dentro de los 15 minutos.

En Sampling_1 (repo `../experimento-sampling`, `experimentos/sampling_1/README.md` y `h4/README.md`), el final con
**todas las bajas y una fracción f de CONTINUA con peso 1/f** no perdió contra el control en f = 0,5; 0,25 y 0,1, y
perdió en 0,05 (`H4O-*`: −0,30 M$ en 0,25 y −2,25 M$ en 0,1, con aceleraciones de 3,65 y 5,29 contando la búsqueda).
Muestrear al azar todas las filas (`U*`) o achicar dentro de LightGBM (`B*`, GOSS) perdió o no llegó a 2×. Son
hipótesis a volver a medir, no hechos:

- se midió con otro protocolo (Optuna propio, final 201903–201908, test 201910 con 20 semillas, N\* = 3.300);
- las variantes de H4 salieron de un exploratorio que miró 201910, que acá está reservado;
- el catálogo del equipo no tiene búsqueda: lo que se mide acá es solo el final.

## What Changes

- **Muestreo del final**: el `Dataset` de entrenamiento conserva todas las filas BAJA+1 y BAJA+2 y una fracción f de
  CONTINUA elegida al azar, con peso 1/f en las CONTINUA conservadas, para que la proporción ponderada de clases sea la
  del train completo. Vale igual para el binario y el multiclase del catálogo.
- **La muestra depende de la semilla**: cada semilla del ensamble ve otra muestra de CONTINUA (semilla de la muestra =
  semilla del modelo), así que el ensamble no pierde la diversidad de las filas descartadas. Queda escrito como decisión;
  la alternativa (una muestra fija para todas las semillas) se mide solo si la principal pierde.
- **Experimento con protocolo escrito antes de correr** (en `docs/PLAN_PRUEBAS.md`, como E02): brazos f ∈ {**0,5**;
  **0,25**} contra f = 1 (el catálogo vigente, reutilizado si pasa las comprobaciones de reproducción de E02). Todo lo
  demás idéntico al catálogo vigente: 760 variables, train 201903–201906, hiperparámetros, 300 rondas, semillas, binado.
  Desarrollo en 201908 y 201909; 201910 sigue bloqueado; nada de 2020. f = 0,1 queda fuera: con dos brazos ya hay dos
  comparaciones declaradas, y 0,1 se mira solo si 0,25 no pierde, como exploratorio.
- **Regla de adopción distinta a E01/E02**, porque acá no se busca ganar sino **no perder** y ahorrar tiempo:
  - la ganancia del ensamble en su fracción no cae más que un margen δ fijado antes de correr, en 201908 **y** en
    201909 (δ se toma del ruido entre semillas del vigente, a declarar en el protocolo);
  - el peor caso de transferencia del corte no es peor que el del vigente por más de δ;
  - el tiempo de entrenamiento por semilla, medido en la `n2-highmem-8`, baja al menos 1,5×.

  De los brazos que cumplen se adopta el de f más chico.
- **Fidelidad del muestreo como banco de pruebas**: si se adopta, los experimentos siguientes pueden entrenar sus brazos
  con muestreo, y solo el catálogo final con todas las filas o con el f adoptado. Para eso, un control: repetir E02
  (multiclase con BAJA+1 en 0,5 contra 1) con el f adoptado y comprobar que la conclusión es la misma que con el train
  completo (mismo signo de la diferencia del ensamble en cada mes). Si no coincide, el muestreo sirve para el catálogo
  pero no para comparar brazos.
- **Más tiempo, no más modelos**: si el ahorro es grande, el tiempo liberado puede ir a más semillas en el ensamble
  (Sampling_1 encontró ganancia a tiempo igual). Eso es una medición aparte, no parte de la regla de adopción.
- **Registro de la mejora**: el resultado es una fila de `docs/MEJORAS.md` (formato en `peso-de-baja1`), se adopte o no,
  con la diferencia de tiempo en su columna.

## Orden respecto de los otros cambios

- **Depende de** `esqueleto-del-pipeline` (la fábrica reproducible y el catálogo congelado como fila 0).
- **Va antes de** `peso-de-baja1`: con CONTINUA a peso 1/f, el peso de BAJA+1 se declara relativo al de CONTINUA, y
  conviene medirlo ya sobre el régimen de entrenamiento que va a quedar.
- **Habilita** `reajuste-mensual` (receta de muestreo para reentrenar dentro del presupuesto) y le da a
  `busqueda-de-hiperparametros` el final ya definido; la búsqueda sobre el 10 % al azar es de ese cambio, no de este.
- **Se superpone** con «submuestreo de CONTINUA distinto por semilla» de `estrategias-del-podio`
  (`neg_bagging_fraction`): si este cambio se adopta con la muestra por semilla, esa candidata sale del podio.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `fabrica-de-modelos`: el entrenamiento admite una fracción de CONTINUA y su peso, declarados en el catálogo, con la
  muestra derivada de la semilla.

La capacidad la crea `esqueleto-del-pipeline`; este cambio se especifica cuando ese esté archivado.

## Impact

- **Código**: el armado del `Dataset` en la fábrica (`entrenamiento/fabrica.py` y los scripts de experimentos) recibe la
  fracción y arma `weight`; el manifiesto del catálogo gana `muestreo_continua` (f y regla de la semilla). La corrida
  mensual no cambia: el muestreo solo existe al entrenar, y la inferencia es la misma.
- **Riesgo de interpretación**: `min_data_in_leaf` (200 en el catálogo) cuenta filas, no pesos; con la mitad de CONTINUA
  las hojas permitidas cambian de tamaño ponderado. El hiperparámetro que mira pesos es `min_sum_hessian_in_leaf`. Con
  hiperparámetros fijos es una limitación declarada, igual que en E02.
- **Reproducibilidad**: el sha256 de cada modelo ya depende de la máquina (`scripts/comparar_fabrica.py`); la muestra
  tiene que salir solo de la semilla y del orden de las filas de la historia, para que dos fábricas elijan las mismas
  filas.
- **Congelamiento**: como `peso-de-baja1`, un catálogo nuevo invalida tiempos, cortes y el ensayo 202001–202006
  (tarea 7.7 de `esqueleto-del-pipeline`); se decide al priorizarlo si entra antes o después del congelamiento.
