# Proposal

## Why

La Segunda Competencia (comisión lunes) evalúa un pipeline que recibe un mes crudo, entrega scores y actualiza un
reporte en menos de 15 minutos, operado en clase frente al tutor (ver `docs/consigna.md`). El equipo ya tiene ese
pipeline funcionando en `MLDEVGIT/dmeyf-pipeline` (Martín, 24/25-nov): dos estrategias, la secuencia 202001–202006
corrida y verificada, reintentos probados. Este cambio adopta ese repo como el único del equipo y cierra lo que le
falta para la clase y el examen: que lo opere cualquiera de los tres en la nube, que trate las variables rotas, y que
el reporte se pueda leer.

## What Changes

- **Un solo repo**: el código es el de `dmeyf-pipeline`; de este repo se llevan la consigna, los antecedentes de la
  Primera Competencia, la puesta en marcha en la nube y OpenSpec. Este repo se archiva.
- **Nube**: VMs `n2-highmem-8` a pedido, una instancia chica de Cloud SQL (Postgres) para el registro y el bucket como
  copia durable del catálogo de modelos, la historia y los reportes; scripts para crear la VM y dar acceso; el tiempo
  por mes medido en la VM.
- **Una función por etapa**: la corrida mensual, hoy una función larga, se reordena en etapas que un ejecutor corre en
  orden y registra una por una, sin cambiar ningún resultado.
- **Registro en una base**: el registro de corridas, hoy repartido en archivos, se migra a Postgres: corridas, etapas
  y eventos, escritos en el momento.
- **Fábrica desde cero**: la historia, la clase y todos los modelos se generan en una VM a partir del dataset del
  curso, con un comando. No se usa ningún archivo de la notebook de Martín: de su trabajo se toman el código, las
  semillas, los hiperparámetros y los cortes, que están en el repo.
- **Calidad de datos**: además de detectar las variables rotas, tratarlas; el tratamiento (faltante o último valor)
  se elige inyectando el patrón en meses de 2019.
- **Reporte y tablero en vivo**: tablas agregadas que se actualizan al cerrar cada etapa y un tablero que las lee. La
  vista de corridas tiene la forma de GitHub Actions: lista de corridas, etapas con estado y duración, eventos de cada
  etapa y reintentos. Corre en Cloud Run, así que se abre con un enlace desde cualquier navegador. Además, la evolución
  por estrategia, las curvas de ganancia y la calidad de datos por mes, y una copia `reporte/index.html` en el bucket,
  también con su enlace.
- **Pruebas a fondo**: por etapa, por falla (matar o romper cada etapa y reintentar) y por cada problema de datos que
  se sabe que puede pasar, empezando por las variables rotas. La cátedra confirmó que los archivos no traen columnas de
  más ni de menos: un archivo con otro esquema se rechaza.
- **Ensayo por integrante**: una muestra chica para probar en la notebook, el candado de los meses de 202007 en
  adelante y el recorrido del README repetido por cada uno, solo, en una VM nueva.

Queda afuera de este cambio: las estrategias nuevas, que se planifican cuando el pipeline esté estable y con
resultados medidos. Cada una tiene su propio cambio ya creado en `openspec/changes/`, con lo que el plan original
decía de ella:

| Cambio | Qué es |
| --- | --- |
| `busqueda-de-hiperparametros` | Optuna sobre el 10 % al azar, más rondas, validación en varios meses |
| `reajuste-mensual` | la estrategia que se reentrena cada mes con las clases que maduran |
| `modelo-de-respaldo` | un modelo sin variables históricas para los meses con muchas variables rotas |
| `variables-de-tendencia-y-evento` | pendientes, ventanas, lags por calendario |
| `estrategias-del-podio` | multiclase con segunda etapa, un modelo por profundidad de historia, rangos de cero fijo |
| `correccion-por-inflacion` | montos deflactados o en escala por mes |

## Capabilities

### New Capabilities

- `corrida-mensual`: el contrato de entrada y salida de un mes, las estrategias que corren, la recomendación única y
  el límite de tiempo.
- `historia-y-features`: cómo se guarda la historia mes a mes y cómo se garantiza que entrenamiento y producción
  calculen las mismas variables.
- `calidad-de-datos`: detección y tratamiento de variables rotas o con cambio de régimen en un mes entrante y en la
  historia.
- `fabrica-de-modelos`: el entrenamiento fuera de línea, qué meses puede usar y qué deja en el catálogo.
- `registro-de-corridas`: el registro transaccional de corridas, etapas y eventos, su consulta en vivo y su
  recuperación.
- `reporte-de-seguimiento`: las tablas agregadas, el tablero en vivo y la copia que se actualiza con cada mes.
- `ensayo-y-meses-reservados`: el ensayo mes a mes, la muestra de prueba y la regla sobre los meses que no se usan para
  decidir.

### Modified Capabilities

Ninguna: no hay specs archivadas todavía.

## Impact

- **Código**: se trabaja sobre `pipeline_competencia02/`, `evaluacion/`, `experimentos/` y `pruebas/` del repo del
  equipo, con commits directos a `main` y las pruebas corriendo en cada push (sin PR: nadie los revisa). `mensual.py` se reordena en etapas y
  `ejecutar_mes.py` y `entorno.py`, el pipeline anterior de un solo modelo, se retiran. `docs/antecedentes/competencia-1/codigo/` sigue
  siendo solo referencia.
- **Dependencias**: las de su `requirements.txt` (Python 3.12, LightGBM, DuckDB, pandas, scikit-learn), con versiones
  fijadas, más el cliente de Postgres y el conector de Cloud SQL; Docker solo para las pruebas locales. Se verifica
  que todo corra en Linux y en macOS, no solo en Windows.
- **Nube**: proyecto `proj-uba-261012163242176`: una instancia chica de Cloud SQL siempre encendida, el tablero en Cloud Run,
  el bucket como copia durable y VMs `n2-highmem-8` a pedido. Hay que habilitar la API de Cloud SQL y dar acceso al proyecto a los
  otros dos integrantes.
- **Datos**: `competencia_02_crudo.csv.gz` y los modelos, fuera del repo.
- **Equipo**: tres integrantes; cada uno tiene que poder instalar, ensayar y operar el pipeline solo, y explicarlo en
  el examen individual.
