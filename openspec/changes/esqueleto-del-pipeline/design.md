# Design

## Context

Motivación y alcance en `proposal.md`; la consigna, en `docs/CONSIGNA.md`. Lo que condiciona el diseño:

- **15 minutos por mes** en una `n2-highmem-8`; la consigna recomienda la nube con entornos estándar.
- **La corrida en clase y el examen son el mismo encuentro, el 10-dic**: mientras corren los meses, cada integrante
  responde por el código.
- **Tres integrantes**, cada uno operando solo, y un **examen individual sin conexión ni LLM** sobre el código.
- **El pipeline ya existe** en `MLDEVGIT/dmeyf-pipeline` (revisión del 27-nov, commit `5d85631`): unas 3.000 líneas en
  `pipeline_competencia02/`, pruebas, experimentos sobre 2019 y cuatro corridas de la secuencia 202001–202006. Está
  verificado en una sola máquina (Windows, Python 3.12), y los modelos y el Parquet de 2019 solo existen ahí.
- **Nube disponible**: proyecto `proj-uba-261012163242176`, región `northamerica-northeast2`, cuota de 32 vCPU de
  Compute Engine (4 VMs de 8), bucket `gs://agustinarazanov_buckito2026/` en la misma región. Crédito del período de
  prueba: US$ 256 al 23-nov-2026, vence el 10-ene-2027.
- **Datos medidos** (23-nov, dataset completo): 124.000 a 165.000 clientes por mes, 150 variables; leer los 32 meses
  del CSV comprimido con DuckDB tarda 18 s. Hay meses con variables rotas: 9 en 201905 y en 201910 (rentabilidad,
  comisiones, márgenes), 30 en 202006 (casi todos los contadores de transacciones) e `internet` en cero desde 202010.
  El pipeline del equipo, con otra regla (todos los observados en cero), cuenta 6 en 202002 y 47 en 202006.
- **Tiempos medidos en la notebook de Martín** (8 hilos, 16 GB): 135–194 s por mes con 5 + 5 semillas, 432–730 s con
  20 + 20 y 347–476 s con 20 + 10. La inferencia es el 80 % del mes. En la VM no se midió.
- **Clases**: la clase de M se conoce al llegar M+2. 201910 es el último mes con clase dentro de 2019.
- **Criterio para decidir** (27-nov): cada decisión se toma por lo que es mejor para el pipeline y para poder
  explicarlo; el plazo no es argumento para descartar una opción.
- Antecedentes: `docs/antecedentes/competencia-1/` (postmortem, backlog, podio) y Sampling_1.

## Goals / Non-Goals

**Goals:**

- Un camino único de código para producción, ensayo y pruebas; lo único que cambia es la carpeta de ejecución y el
  tamaño.
- Un integrante con su cuenta de Google y el README puede crear una VM, bajar el catálogo, procesar un mes y abrir el
  reporte.
- Cada etapa es una función chica, con entradas y salidas guardadas, que se puede correr, probar y reemplazar por
  separado.
- Lo que se escribe durante la corrida y lo que lee el tablero están separados, y lo segundo se regenera de lo primero.
- Una VM se puede borrar sin perder nada: el estado durable está en la base y en el bucket.
- Cualquiera de los tres puede reentrenar el catálogo desde el dataset crudo.
- Cada parte del código que se adopta se puede explicar a mano en el examen.

**Non-Goals:**

- Mejorar la ganancia: el reordenamiento en etapas y la migración del registro no cambian ningún número. Lo único
  que cambia scores a propósito es el tratamiento de variables rotas, que obliga a reentrenar el catálogo (decisión 8).
- Tolerar archivos con otro esquema: la cátedra confirmó que los archivos de clase traen las mismas columnas.
- Orquestador externo (Airflow, Dagster, Prefect), Kubernetes, contenedores para el pipeline.
- Programación automática de corridas: se inician a mano, como pide la consigna.
- Mejorar la ganancia: hiperparámetros, variables nuevas y estrategias nuevas van en los cambios siguientes.

## Decisions

### 1. Se adopta el pipeline del equipo y se reordena en una función por etapa

El código es `pipeline_competencia02/` de `dmeyf-pipeline`: el contrato de entrada y salida, las variables, la
inferencia, las dos estrategias, la publicación todo o nada y el ensayo ya están y se conservan. Lo que cambia es la
forma de la corrida mensual. Hoy `mensual.py` es una función principal de 260 líneas, con las etapas como bloques
seguidos y un cronómetro alrededor de cada uno, que además importa validación, candado y publicación de
`ejecutar_mes.py`, el pipeline anterior de un solo modelo.

Pasa a ser:

- **Un ejecutor** (`ejecutor.py`, unas decenas de líneas): recibe la lista de etapas, las corre en orden, registra de
  cada una inicio, fin, estado, filas y error, corta en la primera falla y deja las siguientes como omitidas.
- **Una función por etapa**, cada una en su módulo, que recibe un contexto (mes, carpeta, conexión al registro,
  resultados de las etapas anteriores) y deja su resultado guardado: `recepcion` → `validacion` → `perfil` → `calidad`
  → `features` → `verificar_features` → `inferencia` → `estrategias` → `escritura` → `publicacion` →
  `respaldo_datos` → `agregados_y_reporte` → `respaldo`. `respaldo_datos` copia al bucket la salida y la historia del
  mes apenas se publican, para que un mes publicado no viva solo en una VM descartable; `respaldo`, al final, copia el
  registro y el reporte.
- **Dos estados distintos**: el de la corrida (un intento) y el del mes. El mes pasa a `publicado` cuando termina
  `publicacion`, y a `completado` cuando terminan las dos etapas siguientes. Si `agregados_y_reporte` o `respaldo`
  fallan, la corrida queda fallida pero el mes sigue publicado: el reintento retoma desde la primera etapa que falta y
  nunca vuelve a puntuar. El mes siguiente se acepta recién con el anterior `completado`.
- **Hilos configurables**: hoy la inferencia usa 4 hilos fijos; la VM tiene 8.
- **`mensual.py`** queda como la lista de etapas y los argumentos del comando. Lo que hoy se importa de
  `ejecutar_mes.py` se muda al módulo de su etapa; `ejecutar_mes.py` y `entorno.py` se retiran.

Los comandos no cambian: `preparar_ejecucion`, `mensual --ejecucion <carpeta> --mes <yyyymm>` y `correr_meses`.

*Por qué:* una etapa que es una función se prueba sola, se explica sola en el examen y se reemplaza sin tocar el resto,
que es literalmente el criterio de industrialización. El ejecutor es además el único lugar que sabe de estados y
tiempos, así que el registro por etapa y la vista en vivo salen de ahí y no de marcas repartidas por el código.

*Red de seguridad:* el reordenamiento no puede cambiar ningún número. Antes y después se corre la secuencia
202001–202006 y se comparan las salidas byte a byte; `verificar_scores.py`, `verificar_salida.py` y
`probar_reintentos.py` tienen que seguir pasando.

*Alternativas:* dejar la función larga y agregar una llamada al empezar cada bloque da los estados con veinte líneas,
pero las etapas siguen sin poder probarse ni reemplazarse por separado. Dagster da la vista de corridas hecha, pero
suma una dependencia grande que hay que poder explicar y no cubre el reporte de negocio. La consigna dice que una
secuencia de scripts es una elección excelente.

### 2. Dónde vive cada cosa

```
 notebook de cada integrante                     Google Cloud (northamerica-northeast2)
 +---------------------------+      ssh / IAP    +--------------------------------------------+
 | gcloud, git               | ----------------> | VM de trabajo (n2-highmem-8, se crea y se  |
 | tablero (lee la base)     |                   | borra): repo, carpeta de ejecución,     |
 | copia del reporte         |                   | disco local con los Parquet                |
 +---------------------------+                   +---------+------------------+---------------+
              |                                            |                  |
              | conector de Cloud SQL                      v                  v
              +----------------------------------> Cloud SQL (Postgres)    Bucket
                                                   registro + tablas       historia, features,
                                                   agregadas, un esquema   puntajes, catálogo,
                                                   por entorno             reportes, respaldos
```

- **Cómputo:** VMs a pedido (STANDARD, no *spot*), descartables.
- **Base:** una instancia chica de Cloud SQL, siempre encendida, compartida por todas las VMs y las notebooks.
- **Archivos:** el bucket es la copia durable; el disco de la VM es la copia de trabajo.
- **Código:** GitHub, en el repo público del equipo. Para el examen alcanza con el clon del repo en la notebook.

### 3. Entornos por nombre

Un entorno (`produccion`, `ensayo`, `medicion_<n>`, `pruebas_<usuario>`) es una carpeta de ejecución creada por
`preparar_ejecucion` (`input/`, `output/`, `historia/`, `diagnosticos/`, `modelos/`), un esquema de Postgres y un
prefijo en el bucket, los tres con el mismo nombre. El comando recibe el entorno; el código es el mismo.

*Por qué:* ensayar es idéntico a producir (mismo comando, otro nombre) y una medición no puede contaminar producción.

### 4. Parquet por mes para la historia, DuckDB para leerla

`historia/foto_mes=<yyyymm>.parquet`, con el esquema de la historia inicial de 2019. Durante la corrida se lee y se
escribe en el disco de la VM; la publicación es todo o nada (se escribe aparte y se renombra, la salida oficial al
final). Al cerrar el mes, la etapa `respaldo` sincroniza la carpeta de ejecución con el bucket, y una VM nueva empieza bajándola. Un mes
corregido reemplaza su archivo y el anterior se conserva aparte.

*Alternativas:* leer y escribir directo en el bucket desde DuckDB funciona, pero cada lectura pasa por la red y pone en
riesgo los 15 minutos.

### 5. El registro pasa de archivos a Postgres en Cloud SQL

Hoy el registro son cuatro clases de archivo dentro de la carpeta de ejecución. Se migra entero a una instancia de
Cloud SQL para PostgreSQL en la región de las VMs, que pasa a ser la única fuente de verdad del estado. Las conexiones
usan el conector de Cloud SQL con la identidad de Google de quien corre (o de la cuenta de servicio de la VM), sin
contraseñas en el repo.

| Hoy, en archivos | En la base |
| --- | --- |
| `registro/ejecuciones.jsonl` (una línea por intento) | `corrida`: una fila por intento, con mes, tipo, quién, versión del código, huellas, inicio, fin y estado |
| `registro/meses/<yyyymm>.json` (estado del mes) | se deriva de `corrida`: la vigente es la última completada del mes |
| archivo de candado por mes, con el pid | índice único: a lo sumo una corrida en curso por mes y entorno; cada corrida actualiza su latido |
| `registro/log_<ejecución>.txt` | `evento`: hora, corrida, etapa, nivel y datos, escritos en el momento |
| tiempos e incidentes dentro de `reporte.json` | `etapa` (estado, inicio, fin, filas, error) y `evento` |
| perfil de columnas dentro de `reporte.json` | `control_calidad` (variable × mes) |
| envíos por estrategia dentro de `reporte.json` | `envios` (estrategia × mes: cantidad, corte, probabilidad mínima) |
| `integridad` (sha256) dentro de `reporte.json` | `publicacion`: sha256 de la salida, la historia y las decisiones del mes |
| — | `medicion_eventual` |

Solo se agrega; lo único que se actualiza es el estado, el fin y el latido de corridas y etapas.

**Lo que la base no resuelve sola.** Los archivos del mes (salida, historia, diagnóstico) se publican en disco, fuera
de cualquier transacción. Sigue pudiendo pasar que el proceso muera después de publicar y antes de marcar el mes. Se
conserva la reconciliación que el equipo ya probó, ahora en dos pasos: la corrida escribe `publicacion` con los sha256 y
estado `publicando`, publica los archivos y recién entonces marca el mes publicado. Un reintento que encuentra
`publicando` compara los archivos con esos sha256: si coinciden, sigue sin recalcular; si no, los aparta y recalcula.

**Una sola corrida por mes, y corridas interrumpidas.**
- Cada corrida guarda máquina, pid y hora de creación del proceso. En la misma máquina, una corrida en curso cuyo
  proceso ya no existe se toma de inmediato, como hoy.
- Entre máquinas se usa un latido, que escribe un hilo aparte cada pocos segundos (la inferencia ocupa el hilo
  principal durante minutos). Un latido más viejo que el umbral configurado = corrida interrumpida.
- Antes de publicar, la corrida confirma en la misma transacción que sigue siendo la vigente
  (`UPDATE … WHERE id = … AND estado = 'en_curso'`). Una corrida dada por muerta que seguía viva no puede publicar.

**Base inalcanzable.** La conexión reintenta un número acotado de veces. Si falla antes de publicar, la corrida termina
con error y sin publicar nada. Si falla después de publicar, los archivos y sus sha256 ya están en disco y la corrida se
reconcilia al volver la base.

**El log no vive solo en la base.** Cada corrida escribe además un archivo de log en la carpeta de ejecución, con los
mismos registros que manda a `evento`. Si la base no responde, el motivo queda ahí.

**Respaldo de la base.** La instancia se crea con copias automáticas, recuperación a un punto en el tiempo, protección
contra borrado y una ventana sin mantenimiento que cubre el 10-dic. Además, la etapa `respaldo` exporta el esquema del
entorno al bucket al cerrar cada mes, con un `COPY` de cada tabla a CSV por la conexión que ya tiene abierta (la
exportación de `gcloud` es una operación de la instancia que tarda más de lo que el reloj permite, y un volcado con
`pg_dump` arrastra permisos que no existen en el Postgres local): las copias de Cloud SQL se van con la
instancia y con el período de prueba, la exportación no. Con la carpeta de ejecución y esa exportación, el bucket
alcanza para reconstruir todo.

**Plan B, de ida y de vuelta.** Un Postgres local en Docker en la VM, de la misma versión mayor, cargado con la última
exportación. Mientras se usa, el tablero público queda atrasado y se mira el tablero local. Al volver Cloud SQL, los
meses procesados en el plan B se cargan en él con la misma exportación, y recién entonces se sigue.

**Carpeta y base tienen que ser del mismo entorno.** `preparar_ejecucion` escribe en la carpeta un `entorno.json`
(entorno, esquema, huella del catálogo). Cada corrida, al empezar, comprueba que la base a la que se conectó es la de
ese entorno y que el último mes publicado coincide en sha256 con el de la carpeta; si no, se rechaza. El comando sigue
recibiendo la carpeta (`--ejecucion`); el entorno y el esquema salen de ese archivo.

**Usuarios.** La autenticación por identidad de Google necesita, además de los roles del proyecto, un usuario de base
por integrante y por cuenta de servicio, y permisos sobre cada esquema. Los nombres de entorno usan guion bajo
(`pruebas_<usuario>`, `medicion_<n>`) para ser nombres de esquema válidos sin comillas.

Las migraciones son archivos SQL numerados, solo hacia adelante, que se aplican igual en Cloud SQL y en el Postgres
local, que también es el de las pruebas automáticas. Cada esquema guarda qué migraciones tiene aplicadas, la corrida se
niega a correr contra un esquema de otra versión, y antes de migrar se exporta. Las horas se guardan con zona y el
latido se compara con el reloj de la base, no con el de cada VM.

*Por qué una base y no los archivos:* el estado de una corrida es un conjunto de hechos relacionados (corrida, etapas,
eventos) que hoy está repartido entre un JSONL, un JSON por mes, un candado y un log de texto, en el disco de una
máquina. Un pipeline productivo separa el cómputo, que es descartable, del estado, que va a una base: el cambio de
estado es una transacción, el candado es una restricción, el tablero consulta en vez de interpretar archivos, lo ven los
tres integrantes y todas las VMs, y sobrevive a la VM.

*Alternativas:*
- **Archivos como fuente de verdad y la base como espejo** (lo propuso la revisión del plan): evita depender de la red
  durante la corrida, pero deja el estado real en el disco de una VM y obliga a mantener dos copias de acuerdo.
- **SQLite en el disco de la VM:** da tablas sin servicio, pero cada VM tendría su archivo; las VMs de la fábrica y los
  tres integrantes no verían un registro común, y habría que sincronizarlo con el bucket.
- **Postgres en una VM chica siempre encendida:** gasta 2 de los 32 vCPU de la cuota y hay que mantenerla y respaldarla.

### 6. De lo transaccional a lo agregado: una etapa, después de publicar, solo los meses que cambiaron

Lectura, modelo en estrella: dimensiones `dim_mes`, `dim_estrategia`, `dim_variable`, `dim_etapa`; hechos
`h_estrategia_mes` (envíos, distribución de puntajes y, cuando madura la clase, ganancia, AUC, captura, lift),
`h_curva_ganancia` (estrategia × mes × cantidad de envíos), `h_calidad` (variable × mes), `h_etapa_corrida`
(duraciones, filas y pico de memoria), `h_coincidencia` (pares de estrategias × mes, y semilla contra ensamble) y
`h_incidente` (regla × mes: cantidad y nivel). Reemplazan a `registro/reporte_acumulado.csv`.

La etapa `agregados_y_reporte` corre **después** de `publicacion` y, en una sola transacción, recalcula las filas de
los dos meses que cambiaron: M (lo que se sabe al puntuar) y M−2 (lo que madura con la clase), con
`INSERT … ON CONFLICT DO UPDATE` sobre claves naturales. Las agregaciones por cliente (curvas, distribuciones,
corrimiento) las calcula DuckDB sobre los Parquet y escribe las filas resultantes. Repetir la etapa da el mismo
resultado, y una corrida que falla antes de publicar no deja nada en las tablas de lectura.

`h_estrategia_mes` nace con las métricas de la clase vacías y estado `pendiente`, y se completa dos meses después: es
una foto acumulativa, el patrón clásico para hechos que llegan tarde. La clase se reconstruye por la presencia de cada
cliente en los meses recibidos (`retrospectiva.py`).

`python -m pipeline_competencia02.reconstruir` vacía las tablas de lectura y las regenera completas. No es parte de la
corrida mensual: es la herramienta para cuando cambia la definición de una métrica o hay que reparar algo. Una prueba
compara su resultado con el de las actualizaciones mes a mes.

*Alternativas:* recalcular todo en cada corrida es más simple y a este tamaño tarda poco, pero no es lo que hace un
sistema en producción: el costo crece con la historia y cada corrida reescribe meses que no cambiaron. Actualizar las
tablas al cerrar cada etapa (la primera versión de este diseño) deja filas de corridas que después fallan. Vistas
calculadas en cada lectura hacen lento el tablero cuando crece la historia.

### 7. Variables definidas una sola vez, en SQL

`features.py` genera el SQL de variables (lags y deltas de orden 1 y 2 de las variables originales) y lo usan el
entrenamiento y la corrida mensual. La corrida verifica, antes de puntuar, que nombres, orden y tipos coincidan con
los que declara el catálogo.

Los lags son **por fila**: la k-ésima observación previa del cliente, no el mes calendario M−k. La corrida informa
cuántos clientes tienen la diferencia (14 a 24 por mes en el ensayo). Pasar a lags por calendario exige reentrenar y va
en `variables-de-tendencia-y-evento`.

*Por qué:* es la respuesta a «¿cómo me aseguro de que entrenamiento y producción calculen lo mismo?»; la igualdad está
verificada bit a bit en 201908.

### 8. Calidad de datos: comparar cada variable con su propia historia; el tratamiento se elige con 2019

El problema conocido son variables que llegan rotas: columnas que están en el archivo pero vienen todas en cero en un
mes. La cátedra confirmó que los archivos de clase no traen columnas de más ni de menos; un archivo con otro esquema se
rechaza con un mensaje que nombra las columnas, como hoy.

**Detección.** Hoy la corrida perfila las columnas y advierte cuando todos los observados de una columna son cero, con
umbrales y acciones en `politica_incidentes.json`. La etapa `calidad` extiende esa política: por variable, la proporción
de ceros y de faltantes del mes contra la mediana de sus meses anteriores; rota = más de 99,9 % de ceros (o de
faltantes) cuando la mediana histórica es menor que 95 %, o un salto mayor que 30 puntos. Umbrales calibrados solo con
2019. Para el corrimiento se guarda el PSI de cada variable, en diez intervalos por cuantiles, contra los meses de
entrenamiento (201903–201906).

**Tratamiento.** El diseño original fijaba «faltante en vez de cero». El diagnóstico de 202006 del equipo
(`resultados/i02_columnas_en_cero_202006.json`) lo pone en duda: con los modelos actuales, pasar las 47 columnas a
faltante no deshace el corrimiento de los scores, y arrastrar el último valor conocido sí. Ese diagnóstico es de 2020 y
no decide nada. La decisión sale de un experimento con 2019: inyectar variables rotas en 201908 y 201909 y comparar no
tratar, faltante y último valor, con los modelos actuales y con modelos reentrenados con el tratamiento aplicado a
201905, usando semillas pareadas para separar el efecto del ruido. Se inyectan el patrón real de 2019 (las 9 variables
de 201905 y 201910) y una escala de tamaños (9, 20 y 40 variables); que haga falta probar 40 se sabe por 202006, y eso
se declara al tutor.

Reglas que valen para cualquier tratamiento:
- La historia guarda siempre el valor crudo. El tratamiento se aplica al calcular las variables, con la máscara
  variable × mes de `control_calidad`, **antes** de lags y deltas e igual en la fábrica y en la corrida, para que no
  contamine M+1 y M+2.
- «Último valor» es el del último mes en que la variable no estaba rota para ese cliente, hasta tres meses atrás; más
  allá, faltante.
- Tres meses seguidos rota = cambio de régimen: deja de arrastrarse un valor viejo, la variable pasa a faltante y el
  reporte la lista aparte.
- Como el tratamiento se aplica también al entrenamiento, elegirlo obliga a **reentrenar el catálogo**, volver a
  derivar los cortes y volver a medir el tiempo.

**Muchas variables rotas.** La primera versión pasaba la recomendación a «la otra estrategia» al superar un límite. Se
descarta: las dos estrategias usan las mismas 760 variables y se rompen igual, y el cambio alteraría el significado de
`probabilidad` de un mes a otro. La corrida sigue con la recomendada y el reporte marca el mes como degradado, con la
lista de variables. Un respaldo de verdad es el cambio `modelo-de-respaldo`.

*Por qué importa ahora:* 202006 alimenta los lags de 202007 y de 202008, que son dos de los tres meses de la clase.

### 9. Dos estrategias: binario recomendado, multiclase alternativa

- **Recomendada**: LightGBM binario, positivo = BAJA+1 ∪ BAJA+2, ensamble de semillas. La columna `probabilidad` de la
  salida es P(BAJA+1 ∪ BAJA+2).
- **Alternativa**: LightGBM multiclase (CONTINUA, BAJA+1, BAJA+2), score = P(BAJA+2). Se compara en el reporte.

Las dos tienen 300 rondas e hiperparámetros fijos, sin búsqueda (va en `busqueda-de-hiperparametros`). La estrategia
`reajuste` del diseño original no entra: la inferencia ya ocupa el 80 % del mes (va en `reajuste-mensual`).

**Roles de los meses** (los del equipo): entrenamiento 201903–201906, desarrollo y cortes 201908–201909, y 201910
reservado para una evaluación final única con el protocolo congelado. 201911 y 201912 solo como historia.

**Corte:** fracción de los clientes del mes, elegida con las curvas de 201908 y 201909 y verificada contra la
composición del ensamble (con 5 semillas el corte dependía de qué semillas había; con 20, no). Reemplaza la «regla del
margen» del postmortem, que queda como hipótesis en el backlog.

**Catálogo para la clase:** el de 20 + 20 semillas si en la VM entra con margen; si no, 20 + 10. El margen es la mitad
del límite: 450 s. Los catálogos actuales (`ce02`: binario en 2,35 %, multiclase en 2,725 %) sirven para medir y
ensayar; el definitivo es el reentrenado con el tratamiento de la decisión 8, con sus cortes vueltos a derivar. Ese
catálogo se **congela** antes del ensayo completo: un catálogo nuevo invalida los tiempos, los cortes y el ensayo.

**Producción el día de la clase:** el entorno `produccion` es la secuencia 202001–202006 corrida con el catálogo
congelado, y la clase sigue desde ahí con 202007. Así el reporte ya muestra la ganancia realizada de 202001–202004 y
las de 202005, 202006 y 202007 maduran en clase. Los ensayos se hacen en otros entornos.

### 10. Catálogo en el bucket, manifiesto en el repo

`catalogo/estrategias_<nombre>.json` y `catalogo/predictores.json`, versionados, ya listan cada modelo con su sha256,
semilla, rondas, corte con su fuente y significado del score. Falta la otra mitad: los modelos van a
`gs://agustinarazanov_buckito2026/catalogo/<nombre>/` y un comando los baja y verifica contra el manifiesto.

**Todo se genera desde cero.** Los modelos que hay hoy están en una sola notebook, y no se copian: la fábrica rehace la
historia de 2019, la clase y cada modelo en una VM, a partir del dataset del curso, con las semillas, los
hiperparámetros y los cortes que el repo ya tiene versionados. El entrenamiento es determinista (semilla fija,
`deterministic=True`), así que el sha256 de cada modelo nuevo se compara con el del manifiesto del equipo: si coincide,
es el mismo modelo; si no (otra versión, otro sistema, otros hilos), se comparan las métricas de 201908 y 201909 con
las de `resultados/` y la diferencia queda anotada.

*Por qué:* un pipeline que solo corre con archivos que alguien tiene guardados no es reproducible. Generarlos es la
prueba de que la fábrica funciona, y una VM nueva queda lista bajando el catálogo del bucket. Las VMs
de la fábrica escriben su avance en el mismo registro, así que se sigue desde el tablero.

### 11. Tablero con dirección fija: corridas como en GitHub Actions, y una copia guardada

El tablero es un servidor chico de la biblioteca estándar que lee las tablas de lectura y el registro; la página es
HTML y JavaScript sin paso de compilación, con una biblioteca de gráficos copiada en el repo. Solo lee: si se cae, la
corrida no se entera. Los cambios **se empujan** al navegador en vez de que el navegador pregunte cada tanto.

**Dónde corre:** en Cloud Run, que le da una dirección `https://…run.app` que se abre desde cualquier navegador. No
corre en la VM de trabajo: como el estado está en la base, el tablero no necesita la VM ni un túnel. Se despliega con
`gcloud run deploy --source .` (Google arma la imagen) y se conecta a Cloud SQL con su cuenta de servicio de solo
lectura. Ajustes que el empuje necesita: una sola instancia como máximo (cada instancia ocupa una conexión que
escucha, y la base chica admite pocas), tiempo máximo de pedido de una hora (el valor por defecto corta la conexión a
los cinco minutos), una instancia siempre encendida el día de la clase, un mensaje vacío cada veinte segundos para que
la conexión no se cierre por inactiva, y reconexión del `LISTEN` con estado completo si la base se reinicia. La página
abre la conexión de eventos solo mientras está visible y hay una corrida en curso, para que una pestaña olvidada no
mantenga la instancia facturando.

**Qué puede salir por el tablero público.** Es de solo lectura y cada dirección devuelve una lista cerrada de campos.
Nunca datos por cliente: tampoco dentro de un mensaje de error, que puede nombrar un cliente repetido. La traza
completa de un error, el mail de quien corrió y el nombre de la máquina se ven solo en el tablero local, que cada
integrante puede levantar contra la misma base.

**De dónde salen los datos en vivo:**

```
 VM: ejecutor ──(1) escribe la fila y avisa, en la misma transacción──> Cloud SQL
                                                                           │
                              (2) la base entrega el aviso al confirmar    v
 navegador <──(3) el tablero lo reenvía por una conexión abierta── tablero en Cloud Run
```

1. **Publicar.** Cada vez que el ejecutor escribe en `corrida`, `etapa` o `evento`, emite en la misma transacción un
   aviso de Postgres (`NOTIFY`) con el tipo y el identificador de la fila. Si la transacción no se confirma, el aviso no
   sale.
2. **Suscribirse.** El tablero mantiene una conexión a la base escuchando ese canal (`LISTEN`). Es el patrón
   publicar/suscribir: el que escribe no sabe quién mira.
3. **Empujar.** Cada navegador abre una conexión de *Server-Sent Events* con el tablero (`EventSource`, HTTP común, en
   un solo sentido). Cuando llega un aviso, el tablero lee la fila y la manda por esa conexión; la página actualiza
   solo lo que cambió.

Un aviso se pierde si nadie está escuchando en ese momento, así que los avisos no son la fuente de verdad: al abrir la
página, o al reconectar, el navegador pide el estado completo y después sigue por la conexión. Cada mensaje lleva el
identificador del último evento, y la reconexión automática de `EventSource` lo devuelve para retomar desde ahí. El
aviso lleva solo identificadores, porque Postgres limita su tamaño.

**Si el empuje falla, la página pregunta.** Si la conexión de eventos se corta tres veces seguidas, o pasa un minuto
sin recibir ni el mensaje vacío, la página pasa a pedir el estado completo cada dos segundos, con el mismo pedido que
usa al abrir, y lo indica con una marca («actualizando cada 2 s»). Sigue intentando reconectar en segundo plano y
vuelve al empuje cuando lo logra. Así, una conexión cortada el día de la clase deja el tablero un poco más lento, no
congelado.

*Por qué empujar:* la página cambia en el momento en que cambia la base, y cuando no pasa nada no hay consultas. Hacía
falta de todos modos resolver el estado inicial y la reconexión, así que consultar cada dos segundos no era más simple,
solo más lento. *WebSockets* también empuja, pero es de ida y vuelta y la página no le manda nada al servidor.

**Vista de corridas**, con la forma de GitHub Actions:

- a la izquierda, la lista de corridas: mes, entorno, estado (en curso, completada, fallida, rechazada), duración,
  quién la inició y el commit;
- al abrir una, sus etapas en orden, cada una con su ícono de estado, su duración y sus filas; la etapa en curso gira;
- cada etapa se despliega y muestra sus eventos, que se van agregando mientras corre (la inferencia informa el avance
  por bloque de clientes, porque es el 80 % del mes);
- arriba, la barra del tiempo transcurrido contra los 15 minutos;
- los reintentos de un mes se ven como intentos de la misma corrida, igual que un *re-run*.

Cada evento tiene un nivel (información, aviso, error) y, cuando sale de la política de incidentes, el nombre de su
regla (`clientes_sin_historia`, `lag_fila_distinto_calendario`, `scores_saturados`, variable rota, mes degradado…).
Una etapa fallida muestra el mensaje y la traza del error; una corrida rechazada, el motivo.

**Otras vistas:**

- **Resumen**, lo primero que se ve: último mes procesado y su estado, tiempo contra el límite, avisos y errores sin
  revisar, ganancia acumulada, y si el último respaldo y la comprobación de integridad salieron bien.
- **Avisos y errores**: todos los eventos de nivel aviso o error, filtrables por mes, etapa, nivel y regla; por regla,
  la cantidad de cada mes, para ver si algo empeora.
- **Estrategias**: ganancia realizada y pendiente, por mes y acumulada; distancia al mejor corte posible; curva de
  ganancia; envíos, corte y probabilidad mínima enviada; aciertos, precisión y captura en el corte; distribución de los
  puntajes y su cambio respecto del mes anterior; coincidencia entre estrategias y entre las semillas de cada una;
  tasa de bajas observada; estrategia usada por mes.
- **Datos**: clientes por mes, nuevos sin historia y con un mes salteado; mapa variable × mes; variables rotas; meses
  degradados; cambio de régimen; PSI de las variables más importantes; meses que heredan valores tratados.
- **Modelos**: catálogo usado en cada mes (nombre, huella, semillas, rondas, cortes y su fuente) y las variables más
  importantes de cada estrategia.
- **Operación**: duración de cada etapa mes a mes, pico de memoria, filas de entrada y de salida por etapa, quién
  corrió, con qué commit y en qué máquina, y los respaldos.
- **Mediciones eventuales.**

Todas las vistas se filtran por entorno (`produccion`, `ensayo`, …).

**Copia guardada.** La etapa `agregados_y_reporte` escribe `reporte/index.html`, la misma página con los datos
incrustados, y la deja en un bucket aparte, público, que solo contiene el reporte: tiene también su enlace, se abre
sin servidor y sigue existiendo cuando se borre la base. El bucket de datos (historia, salidas, exportaciones) no tiene
ningún acceso público.

*Por qué en vivo y con enlace:* la corrida en clase es el examen. Mientras un mes tarda sus minutos, cualquiera, el
tutor incluido, abre el enlace y ve en qué etapa está y cuánto queda del límite.

*Alternativas:* GitHub Pages da un enlace, pero solo sirve archivos: se actualizaría una vez por mes, con el retraso
del despliegue, y no muestra la corrida en curso. El tablero en la VM con un túnel de SSH no le sirve a quien no tiene
`gcloud`. Abrir un puerto de la VM da un enlace que muere con la VM. Streamlit o Superset resuelven los gráficos, pero
no la vista de corridas ni la copia guardada.

### 12. Acceso: tres integrantes, una cuenta para la VM y tres roles en la base

Cada integrante entra con su cuenta de Google, agregada al proyecto con los permisos mínimos: crear y usar VMs, entrar
por IAP, leer y escribir el bucket de datos y conectarse a Cloud SQL. `scripts/vm.sh` crea la VM, instala el intérprete
y las dependencias fijadas, clona el repo y baja el catálogo; `scripts/acceso.sh <email>` otorga los permisos. Nada
depende de la notebook ni de las claves de una persona.

- **La VM corre con una cuenta de servicio propia**, con permisos solo sobre el bucket de datos y la base, no con la
  cuenta por defecto del proyecto.
- **Tres roles en la base:** `operador` (escribe el registro; lo tienen la cuenta de la VM y, en sus esquemas de
  prueba, cada integrante), `lector` (lee todo; los integrantes sobre `produccion`) y `tablero` (lee solo lo que el
  tablero muestra).
- **`produccion` se escribe solo desde la VM.**

### 13. Operación: manual, comandos y versión congelada

**Manual de operación** (`docs/OPERACION.md`): una tabla de síntoma, código de salida y estado en el tablero → causa →
comando exacto. Los códigos de salida son parte del contrato: 0 completado o recuperado, 2 fallido, 4 rechazado (los
del equipo), más uno para base inalcanzable y otro para corrida reemplazada.

**Comandos de operación**, además de procesar un mes:
- `estado`: el estado de cada mes y de la corrida en curso, sin el tablero.
- `liberar`: toma forzada de un mes. El latido prueba que el proceso está vivo, no que avanza: una corrida colgada
  retendría el mes para siempre. Exige motivo y queda registrado.

No hay reproceso de un mes completado: la consigna dice que cada archivo se procesa una sola vez y la cátedra no manda
meses corregidos.

**Versión congelada.** El catálogo se congela (decisión 9); el código y el entorno también:
- un archivo de dependencias con versiones exactas y huellas para Linux y Python 3.12, el mismo intérprete en la
  notebook, en la VM (lo instala `vm.sh`, sin depender del que traiga la imagen del curso) y en Cloud Run;
- cada corrida guarda la versión de Python y de los paquetes;
- una etiqueta de git para la clase; el entorno `produccion` se niega a correr con cambios sin commitear o desde un
  commit sin etiqueta;
- la VM de la clase se crea y se prueba el día anterior y se deja apagada, no borrada: la clase no depende de que
  GitHub y PyPI respondan esa mañana.

**Contrato de cada etapa.** `docs/LECTURA.md` tiene una tabla: etapa → qué lee → qué escribe → si se puede repetir. Y
una prueba lo demuestra: un catálogo con tres estrategias y una etapa reemplazada por otra corren sin tocar el resto.

**Sin alarmas automáticas.** La corrida la inicia una persona que la está mirando; el resumen del tablero y el código
de salida son el aviso. Lo único automático es la alerta de presupuesto de la nube.

### 14. Pruebas: por etapa, por falla y por problema de datos conocido

Tres familias, todas con la muestra chica y el Postgres local, sin nube:

- **Por etapa:** cada función de etapa se prueba sola, a partir de las salidas guardadas de las anteriores.
- **Por falla:** una matriz que mata el proceso, hace fallar la etapa o corta la base en cada etapa de la corrida, y
  comprueba qué quedó publicado, qué dice el registro y que el reintento termina con el mismo resultado que una corrida
  sin fallas.
- **Por problema de datos conocido:** los que 2019 y el ensayo ya mostraron (variables todas en cero en un mes, en
  meses seguidos, en el mes anterior; clientes nuevos, que saltean un mes, que vuelven; un mes con muy pocas bajas) y los
  que un archivo mal copiado puede traer (vacío, de otro mes, con clientes repetidos, con otro esquema), que se
  rechazan sin publicar nada.

La lista completa de casos, con lo que se espera en cada uno, vive en `docs/pruebas.md` y cada fila nombra su prueba.
Además, una prueba de punta a punta corre tres meses seguidos y compara las salidas con una línea de base.

### 15. Meses reservados con candado en el código

El generador de archivos del ensayo rechaza meses de 202007 en adelante. La única puerta es una medición eventual:
motivo obligatorio, árbol de git limpio, entorno `medicion_<n>` aparte, una fila en `medicion_eventual` y un máximo
en la configuración (3). Los archivos que entregue la cátedra en `input/` no pasan por el generador, así que se procesan
normalmente. Dentro de 2019, `evaluacion/particiones.py` ya bloquea por código la lectura de la clase de 201910.

## Risks / Trade-offs

- **El catálogo de 20 semillas no entra con margen en la VM** → se mide en la primera semana; `ce02_b20m10` es el
  respaldo ya ensayado.
- **El código no corre igual fuera de Windows** → las pruebas y un mes del ensayo se corren en macOS y en la VM antes
  de cualquier otra cosa; los scores se comparan con los publicados.
- **202006 llega con variables rotas y alimenta los lags de 202007 y 202008** → es el punto 8; si el experimento no
  llega a tiempo, la corrida de la clase sale como hoy, advirtiendo, y se dice.
- **Los archivos de clase traen variables rotas que 2019 no anticipa** → es el problema de datos que se cubre: la
  detección no depende de una lista de variables y las pruebas inyectan el caso en cualquier columna. Un archivo con
  otro esquema se rechaza sin publicar.
- **El corte se revisó después de mirar 2020.** El corte de 4,475 % dio ganancia negativa en 202002 y eso motivó
  volver a derivarlo con 2019 (2,35 %). La derivación usa solo 2019, pero el disparador fue 2020: se declara al tutor
  junto con la duda 3 de la consigna.
- **El período de prueba de Google Cloud vence el 10-ene-2027** → cubre la entrega y el video; antes de esa fecha se
  bajan los reportes y el catálogo que se quieran conservar.
- **Presupuesto: US$ 256 al 23-nov-2026** → la instancia chica de la base cuesta pocas decenas de dólares por mes y una
  VM de trabajo, del orden de medio dólar por hora; el gasto se anota en `docs/nube.md` y la base se borra después de la
  entrega.
- **La corrida en clase depende de la red y de Cloud SQL** → la VM y la base están en la misma región; reintentos
  acotados y comportamiento definido si la base no responde (decisión 5); como plan B, el Postgres local en la VM cargado
  con la última exportación, ensayado antes de la clase.
- **El reordenamiento en etapas rompe algo que estaba verificado** → comparación byte a byte de las seis salidas del
  ensayo antes y después, y los verificadores del equipo.
- **Tres motores (DuckDB, Postgres, el bucket)** → cada uno hace una sola cosa; los límites son las etapas
  `agregados_y_reporte` y `respaldo`.
- **Umbrales de calidad calibrados con doce meses** → son configuración visible; el reporte muestra las proporciones
  crudas además de la decisión.
- **Demasiadas piezas para explicar sin conexión** (conector, latido, publicación en dos pasos, avisos empujados,
  tablas agregadas, plan B, Cloud Run) → una función por etapa, el mapa de lectura con el contrato de cada etapa, el
  manual de operación y un recorrido por integrante. La revisión de industrialización recomendó simplificar dos:
  recalcular todas las tablas agregadas en cada corrida y consultar cada dos segundos en vez de empujar. No se adopta:
  son los patrones que usaría un sistema en producción (decisiones 6 y 11), y quedan documentados con su alternativa
  para poder defenderlos.
- **El crédito vence el 10-ene-2027 y con él la base y los enlaces** → alerta de presupuesto al 50 % y al 80 %, y una
  tarea con fecha para bajar el bucket, la exportación y el reporte.
- **Los modelos generados desde cero no salen idénticos a los del equipo** → se sabe modelo por modelo por el sha256;
  si difieren, los cortes se vuelven a derivar con el mismo procedimiento antes de usarlos.
- **Dos planes a la vez** (`docs/TAREAS.md` del equipo y OpenSpec) → `TAREAS.md` queda como historia y apunta a los
  cambios de OpenSpec.

## Open Questions

- Fecha límite del repo y quiénes necesitan acceso (la consigna dice «a definir»). La corrida en clase es el 10-dic,
  el mismo encuentro que el examen individual.
- Si el tutor acepta ajustar algo con el ensayo de 202001–202006, y cómo ve el caso del corte.
- Dónde corre en clase, VM o notebook (duda 5 de la consigna); el diseño supone la VM.
- Las cuentas de Google de los otros dos integrantes, para darles acceso al proyecto.
- Si `probabilidad` puede ser P(BAJA+1 ∪ BAJA+2) o tiene que ser P(BAJA+2).
- Los importes de ganancia de la Segunda Competencia: se usan los de la Primera.
