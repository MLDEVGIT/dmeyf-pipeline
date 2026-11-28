# dmeyf-pipeline — mapa y reglas

Segunda Competencia de DMEyF 2026, comisión lunes (Martín, Agustina y José): un **pipeline productivo** de churn
(BAJA+2), no un submit. Recibe el CSV crudo de un mes, sin targets, y produce `churn_<yyyymm>.csv` más un reporte
acumulativo. Este es el único repo del equipo desde el 27-nov-2026; `agustinarazanov/dmeyf-competencia-2` se archiva.
El plan es el cambio de OpenSpec `esqueleto-del-pipeline`; los cambios siguientes ya tienen su propuesta en
`openspec/changes/`.

- `pipeline_competencia02/`: el pipeline mensual (`preparar_ejecucion`, `mensual`, `correr_meses`, `catalogo`, …).
- `catalogo/`: manifiestos de los catálogos de estrategias (`estrategias_<nombre>.json`, con el sha256 de cada modelo).
- `entrenamiento/legado/`, `evaluacion/` (target, ganancia, particiones), `experimentos/` (sobre 2019),
  `resultados/` (lo que dejó cada experimento), `referencia/`, `scripts/` (verificaciones y mediciones).
- `pruebas/`: `python -m unittest discover -s pruebas -t .`
- `docs/`: `CONSIGNA.md`, `TAREAS.md` (brechas, como historia; el plan es OpenSpec), `PLAN_PRUEBAS.md`, `INTEGRACION.md`, `GANANCIA.md`, `PROCEDENCIA.md`,
  `RELEVAMIENTO.md`.
- `docs/antecedentes/competencia-1/`: postmortem (`lecciones_competencia_1.md`), `backlog.md`, `podio.md` (las fichas
  de los tres primeros), `optuna_y_lightgbm.md`, la matriz y las fichas de los 66 repos (`postmortem_vercel/`) y
  `codigo/` (`fe_panel.py`, `competencia.py`, `v_estilo.py` de la 1: referencia para copiar, no se importa).
- `openspec/`: specs y cambios (`openspec list`). Comandos `/opsx:*` y skills en `.claude/`.

Git: remoto `origin` = `MLDEVGIT/dmeyf-pipeline` en GitHub, **público**.

## Reglas de trabajo

- **Cada cambio de OpenSpec en su rama** (con el nombre del cambio) y un **PR a `main`** al cerrarlo. La rama se
  pushea recién cuando hace falta en GitHub (una VM que la clona, las pruebas de GitHub Actions, otro integrante);
  desde ahí, cada commit se pushea. Nunca commits ni push directos a `main`. Las pruebas tienen que pasar antes de
  cada commit.
- **Operable por cualquiera de los tres integrantes, solo.** Nada depende de la máquina, las credenciales ni la
  memoria de una persona: un comando para levantar el entorno, un comando para procesar un mes, README que alcance.
- **El examen es individual, sin conexión y sin LLM**, con preguntas sobre cada parte del código y cada decisión.
  Preferir código corto y explicable a mano antes que un framework; cada decisión queda escrita con su porqué.
- **Meses.** Las estrategias y los modelos se definen solo con 201901–201912 (clase BAJA+2 hasta 201910). 202001–202006
  es el ensayo que pide la consigna. De 202007 en adelante solo hay **mediciones eventuales**, declaradas de antemano
  y contadas: no se elige ni se ajusta nada con esos meses.
- Decir **validación** y **test** por su nombre, con el mes.
- **Salidas largas a archivo, nunca al chat.** Lo repetido va a scripts. Las corridas pesadas las hace la VM.
- **Commitear sin pedir permiso** al cerrar una tarea, con mensaje descriptivo y sin `Co-Authored-By` ni pie de
  Claude.
- **El repo es público**: nada del dataset, ni modelos, ni credenciales, ni `config.toml`.
- **Zulip**: no escribir, mandar ni redactar mensajes; el archivo (`../zulip/`) se lee solo cuando Agustina lo pide.
- **VMs a pedido** (STANDARD, no spot), `n2-highmem-8`, de a 4 por proyecto (cuota de 32 vCPU); borrar al terminar.
  El gasto de cómputo dentro del crédito no se consulta; se anota.

## Hechos que no están en el código

- Dataset: `https://storage.googleapis.com/open-courses/dmeyf2026-9c6f/competencia_02_crudo.csv.gz` (201901–202108),
  fuera del repo. Las rutas salen de `config.toml` (copia local de `config.ejemplo.toml`), cada una se puede pisar con
  una variable `DMEYF_*`; `python -m pipeline_competencia02.config` muestra qué resolvió.
- gcloud: cuenta de Agustina, proyecto `proj-uba-261012163242176`, región `northamerica-northeast2`, bucket
  `gs://agustinarazanov_buckito2026/`. Crédito del período de prueba: US$ 256 al 23-nov-2026, vence el 10-ene-2027.
- Entorno: Python 3.12 (`.python-version`), dependencias en `requirements.txt`. El pipeline se verificó en Windows
  (notebook de Martín); en la Mac (M1, 16 GB) LightGBM necesita `brew install libomp`.
- Experimento Sampling_1 (repo `../experimento-sampling`, sobre 2019 con test 201910): correr Optuna sobre el 10 % al
  azar y entrenar el final con todo no pierde y es ~8× más rápido; conservar todas las bajas y la mitad de CONTINUA con
  peso 2 tampoco pierde. Acá son hipótesis a volver a medir, no hechos.
- El `competencia-2/` viejo (postmortem de la 1 con su historia de git y los HTML del profesor) se archivó el
  23-nov-2026 en `~/datos/archivo/competencia-2-2026-11-23.tar.gz`.
