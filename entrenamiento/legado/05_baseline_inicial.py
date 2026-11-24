"""Primera corrida funcional del control: LightGBM sin sampling ni optimización.

Corrida DIAGNÓSTICA, no el baseline optimizado definitivo.

Datos:
  - Features publicadas por 04 (manifiesto.json define los 760 predictores).
  - Target de 03: clase_binaria (BAJA+1/BAJA+2 = 1, CONTINUA = 0).
  - Train 201903-201906 completos; validación 201908. Octubre no se lee.

Modelo: LGBMClassifier con sus defaults (100 árboles, sin early stopping),
objective=binary, metric=auc, semilla 20261102, 4 hilos, bagging_freq=1 y
bagging_fraction=1. Sin sampling externo, pesos de clase ni imputaciones.

Tipos: las columnas BIGINT se convierten a float64 con CAST explícito, después
de verificar que |x| <= 2^53, así que la conversión es exacta. Las DOUBLE
quedan como están. Los NULL pasan a NaN, que LightGBM trata como faltante (no
es una imputación). No se usa float32.

Memoria: las matrices se escriben por bloques de filas en np.memmap respaldados
en disco, dentro de la carpeta de la corrida. LightGBM las lee sin copiarlas y
el sistema puede liberar páginas. Si la corrida termina bien, se borran; si
falla, se conservan para diagnóstico.

Salida: experimento_sampling/ejecuciones/05_baseline_inicial/<marca>/, una
carpeta nueva por corrida que nunca se sobrescribe.
"""
from __future__ import annotations

import gc
import json
import logging
import os
import platform
import shutil
import sys
import time
from pathlib import Path

import duckdb
import lightgbm as lgb
import numpy as np
import pandas as pd
import psutil
import sklearn
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "competencia_02"
FEAT_DIR = DATA_DIR / "competencia_02_2019_features"
TARGET = DATA_DIR / "competencia_02_2019_target.parquet"
RUNS = ROOT / "experimento_sampling" / "ejecuciones" / "05_baseline_inicial"

KEYS = ["numero_de_cliente", "foto_mes"]
TARGET_COLS = {"clase_ternaria", "clase_binaria", "horizonte_completo"}
PARTICIONES = {"train": [201903, 201904, 201905, 201906], "validacion": [201908]}
MES_PROHIBIDO = 201910
SEMILLA = 20261102
HILOS = 4
FILAS_POR_BLOQUE = 8 * 2048  # vectores de duckdb por bloque de escritura
MAX_EXACTO = 2**53

PARAMS = {
    "objective": "binary",
    "metric": "auc",
    "random_state": SEMILLA,
    "n_jobs": HILOS,
    "subsample_freq": 1,   # = bagging_freq
    "subsample": 1.0,      # = bagging_fraction
}

log = logging.getLogger("05")


def q(c: str) -> str:
    return '"' + c.replace('"', '""') + '"'


def memoria(proc) -> dict:
    mi = proc.memory_info()
    return {"rss_mb": round(mi.rss / 2**20, 1),
            "pico_working_set_mb": round(getattr(mi, "peak_wset", 0) / 2**20, 1),
            "pico_commit_privado_mb": round(getattr(mi, "peak_pagefile", 0) / 2**20, 1)}


class Estado:
    """Guarda en estado.json la etapa en curso, para poder saber dónde quedó una corrida cortada."""

    def __init__(self, path: Path, proc):
        self.path, self.proc, self.d = path, proc, {"pid": os.getpid(), "etapas": {}}

    def marcar(self, etapa: str, **extra):
        self.d["etapa_actual"] = etapa
        self.d["etapas"][etapa] = {"hora": time.strftime("%Y-%m-%dT%H:%M:%S"), **memoria(self.proc), **extra}
        self.path.write_text(json.dumps(self.d, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("[%s] %s", etapa, memoria(self.proc))


def archivos(meses: list[int]) -> list[str]:
    assert MES_PROHIBIDO not in meses
    return [(FEAT_DIR / f"features_{m}.parquet").as_posix() for m in meses]


def validar_union(con, meses: list[int]) -> dict:
    """Relación 1:1 features-target, cobertura completa y etiquetas no nulas, en SQL."""
    f, lista = archivos(meses), ", ".join(str(m) for m in meses)
    r = con.execute(f"""
        WITH f AS (SELECT numero_de_cliente, foto_mes FROM read_parquet({f})),
             t AS (SELECT * FROM read_parquet('{TARGET.as_posix()}') WHERE foto_mes IN ({lista}))
        SELECT
          (SELECT count(*) FROM f),
          (SELECT count(DISTINCT (numero_de_cliente, foto_mes)) FROM f),
          (SELECT count(*) FROM t),
          (SELECT count(DISTINCT (numero_de_cliente, foto_mes)) FROM t),
          (SELECT count(*) FROM f JOIN t USING (numero_de_cliente, foto_mes)),
          (SELECT count(*) FROM f ANTI JOIN t USING (numero_de_cliente, foto_mes)),
          (SELECT count(*) FROM t ANTI JOIN f USING (numero_de_cliente, foto_mes)),
          (SELECT count(*) FROM t WHERE clase_binaria IS NULL OR clase_ternaria IS NULL),
          (SELECT count(*) FROM t WHERE clase_binaria IS DISTINCT FROM
                 CASE clase_ternaria WHEN 'CONTINUA' THEN 0 WHEN 'BAJA+1' THEN 1 WHEN 'BAJA+2' THEN 1 END),
          (SELECT count(*) FROM t WHERE NOT horizonte_completo)""").fetchone()
    n_f, nk_f, n_t, nk_t, n_join, f_sin_t, t_sin_f, nulos, mal, sin_horiz = map(int, r)
    checks = {"features_claves_unicas": n_f == nk_f, "target_claves_unicas": n_t == nk_t,
              "union_1a1_cobertura_completa": n_join == n_f == n_t and f_sin_t == 0 and t_sin_f == 0,
              "sin_etiquetas_nulas": nulos == 0, "binaria_coherente_con_ternaria": mal == 0,
              "horizonte_completo": sin_horiz == 0}
    return {"filas_features": n_f, "filas_target": n_t, "filas_union": n_join,
            "features_sin_target": f_sin_t, "target_sin_features": t_sin_f, "etiquetas_nulas": nulos,
            "binaria_incoherente": mal, "sin_horizonte_completo": sin_horiz, "checks": checks}


def agregar(con, f: list[str], exprs: list[str], lote: int = 100) -> list:
    """Evalúa agregados por lotes de columnas: 760 a la vez exceden el límite de memoria de duckdb."""
    out = []
    for i in range(0, len(exprs), lote):
        out.extend(con.execute(f"SELECT {', '.join(exprs[i:i + lote])} FROM read_parquet({f})").fetchone())
    return out


def perfil_tipos(con, meses: list[int], pred: list[str], tipos: dict) -> dict:
    """Máximo |x| de las BIGINT (para la conversión exacta) y no finitos de las DOUBLE."""
    f = archivos(meses)
    big = [c for c in pred if tipos[c] == "BIGINT"]
    dbl = [c for c in pred if tipos[c] == "DOUBLE"]
    otros = sorted({tipos[c] for c in pred} - {"BIGINT", "DOUBLE"})
    if otros:
        raise RuntimeError(f"tipos no previstos entre los predictores: {otros}")
    r = agregar(con, f, [f"max(abs({q(c)}))" for c in big])
    max_abs = {c: (None if v is None else int(v)) for c, v in zip(big, r)}
    r = agregar(con, f, [f"count(*) FILTER (WHERE isnan({q(c)}) OR isinf({q(c)}))" for c in dbl])
    no_finitos = {c: int(v) for c, v in zip(dbl, r) if v}
    nulos = sum(agregar(con, f, [f"count(*) - count({q(c)})" for c in pred]))
    peor = max((v for v in max_abs.values() if v is not None), default=0)
    return {"bigint": len(big), "double": len(dbl), "max_abs_bigint": peor,
            "bigint_exacto_en_float64": peor <= MAX_EXACTO,
            "double_no_finitos": no_finitos, "celdas_null_a_nan": int(nulos)}


def cargar(con, meses: list[int], pred: list[str], tipos: dict, destino: Path) -> tuple[np.memmap, np.ndarray, np.ndarray]:
    """Escribe la matriz float64 (filas x 760) en un memmap, por bloques, sin ordenar ni copiar todo en RAM.

    El orden de filas es el de los archivos, leídos en secuencia. Las claves se
    leen en el mismo flujo y después se alinean con el target.
    """
    f = archivos(meses)
    n = con.execute(f"SELECT count(*) FROM read_parquet({f})").fetchone()[0]
    X = np.lib.format.open_memmap(destino, mode="w+", dtype=np.float64, shape=(n, len(pred)))
    expr = ", ".join(f"CAST({q(c)} AS DOUBLE) AS {q(c)}" if tipos[c] == "BIGINT" else q(c) for c in pred)
    con.execute("SET threads = 1")  # flujo secuencial: menos memoria y orden de archivos garantizado
    rel = con.execute(f"SELECT numero_de_cliente, foto_mes, {expr} FROM read_parquet({f})")
    cli = np.empty(n, np.int64)
    mes = np.empty(n, np.int64)
    i, b, t = 0, 0, time.perf_counter()
    while True:
        df = rel.fetch_df_chunk(FILAS_POR_BLOQUE // 2048)
        if df.empty:
            break
        k = len(df)
        cli[i:i + k] = df["numero_de_cliente"].to_numpy(np.int64)
        mes[i:i + k] = df["foto_mes"].to_numpy(np.int64)
        bloque = df[pred].to_numpy(dtype=np.float64, na_value=np.nan)
        if bloque.dtype != np.float64:
            raise RuntimeError(f"tipo inesperado en el bloque: {bloque.dtype}")
        X[i:i + k] = bloque
        i, b = i + k, b + 1
        del df, bloque
        if b % 8 == 0 or i == n:
            log.info("  %s: %s/%s filas (%.0f%%) en %.0fs", destino.name, f"{i:,}", f"{n:,}", 100 * i / n,
                     time.perf_counter() - t)
    if i != n:
        raise RuntimeError(f"se leyeron {i} filas de {n}")
    del rel
    con.execute(f"SET threads = {HILOS}")
    X.flush()
    return X, cli, mes


def etiquetas(con, meses: list[int], cli: np.ndarray, mes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Alinea clase_binaria y clase_ternaria con el orden de las filas de X, por ambas claves."""
    lista = ", ".join(str(m) for m in meses)
    t = con.execute(f"SELECT numero_de_cliente, foto_mes, clase_binaria, clase_ternaria "
                    f"FROM read_parquet('{TARGET.as_posix()}') WHERE foto_mes IN ({lista}) "
                    f"ORDER BY foto_mes, numero_de_cliente").fetchnumpy()
    if cli.max() >= 10**10 or np.asarray(t["numero_de_cliente"]).max() >= 10**10:
        raise RuntimeError("numero_de_cliente no entra en la clave compuesta")
    clave_t = np.asarray(t["foto_mes"], np.int64) * 10**10 + np.asarray(t["numero_de_cliente"], np.int64)
    clave_x = mes * 10**10 + cli
    pos = np.searchsorted(clave_t, clave_x)
    pos = np.minimum(pos, len(clave_t) - 1)
    if not (np.all(np.diff(clave_t) > 0) and len(clave_t) == len(clave_x) and np.array_equal(clave_t[pos], clave_x)
            and len(np.unique(pos)) == len(pos)):
        raise RuntimeError("las claves de features y target no se alinean 1:1")
    yb = np.asarray(t["clase_binaria"])
    if np.ma.is_masked(yb):
        raise RuntimeError("hay etiquetas nulas")
    return np.asarray(yb, np.int8)[pos], np.asarray(t["clase_ternaria"], object)[pos]


def parametros_efectivos(modelo: lgb.LGBMClassifier) -> dict:
    """Sección 'parameters:' del modelo guardado: todos los parámetros que usó LightGBM, con defaults."""
    txt = modelo.booster_.model_to_string()
    ini, fin = txt.find("parameters:\n"), txt.find("end of parameters")
    out = {}
    for linea in txt[ini:fin].splitlines()[1:]:
        if linea.startswith("[") and ": " in linea:
            k, v = linea[1:-1].split(": ", 1)
            out[k] = v
    return out


def main() -> int:
    t0 = time.perf_counter()
    proc = psutil.Process()
    run = RUNS / f"{time.strftime('%Y%m%dT%H%M%S')}_{os.getpid()}"
    run.mkdir(parents=True, exist_ok=False)
    mats = run / "matrices_tmp"
    mats.mkdir()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S",
                        handlers=[logging.FileHandler(run / "log.txt", encoding="utf-8"),
                                  logging.StreamHandler(sys.stdout)])
    estado = Estado(run / "estado.json", proc)
    tiempos, rep = {}, {"corrida": run.relative_to(ROOT).as_posix(),
                        "naturaleza": "diagnóstica; no es el baseline optimizado definitivo"}
    rep["versiones"] = {"python": sys.version.split()[0], "plataforma": platform.platform(),
                        "lightgbm": lgb.__version__, "sklearn": sklearn.__version__, "numpy": np.__version__,
                        "pandas": pd.__version__, "duckdb": duckdb.__version__, "psutil": psutil.__version__}
    rep["ram_sistema_al_inicio_gb"] = {"total": round(psutil.virtual_memory().total / 2**30, 1),
                                       "disponible": round(psutil.virtual_memory().available / 2**30, 1)}
    log.info("Corrida %s | %s", run.relative_to(ROOT).as_posix(), rep["versiones"])
    estado.marcar("inicio")

    con = duckdb.connect()
    con.execute(f"SET threads = {HILOS}")
    con.execute("SET memory_limit = '1GB'")
    con.execute("SET preserve_insertion_order = true")
    con.execute(f"SET temp_directory = '{(mats / 'duckdb').as_posix()}'")

    # 1. Predictores y validación de la unión ------------------------------
    t = time.perf_counter()
    manifest = json.loads((FEAT_DIR / "manifiesto.json").read_text(encoding="utf-8"))
    pred = manifest["predictores"]
    target_cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{TARGET.as_posix()}')").fetchall()}
    meses_todos = sorted(m for ms in PARTICIONES.values() for m in ms)
    cols = con.execute(f"DESCRIBE SELECT * FROM read_parquet({archivos(meses_todos)})").fetchall()
    tipos = {c: ty for c, ty, *_ in cols}
    checks_pred = {
        "predictores_760": len(pred) == 760 and len(set(pred)) == 760,
        "archivos_claves_mas_predictores": [c for c, *_ in cols] == KEYS + pred,
        "sin_claves_entre_predictores": not set(KEYS) & set(pred),
        "sin_target_entre_predictores": not (set(pred) & (TARGET_COLS | target_cols))
                                        and not any("clase" in c.lower() for c in pred),
        "octubre_excluido": MES_PROHIBIDO not in meses_todos,
    }
    rep["predictores"] = {"cantidad": len(pred), "checks": checks_pred}
    (run / "predictores.json").write_text(json.dumps(pred, indent=1, ensure_ascii=False), encoding="utf-8")
    if not all(checks_pred.values()):
        raise RuntimeError(f"chequeos de predictores fallidos: {checks_pred}")
    rep["union"] = {p: validar_union(con, ms) for p, ms in PARTICIONES.items()}
    for p, u in rep["union"].items():
        log.info("unión %s: %s", p, u)
        if not all(u["checks"].values()):
            raise RuntimeError(f"unión {p} inválida: {u['checks']}")
    rep["tipos"] = {p: perfil_tipos(con, ms, pred, tipos) for p, ms in PARTICIONES.items()}
    log.info("tipos: %s", rep["tipos"])
    for p, ti in rep["tipos"].items():
        if not ti["bigint_exacto_en_float64"]:
            raise RuntimeError(f"{p}: hay BIGINT con |x| > 2^53; la conversión a float64 no sería exacta")
    rep["tipos"]["conversion"] = ("BIGINT -> float64 con CAST explícito (exacto: |x| <= 2^53 verificado); "
                                  "DOUBLE sin cambios; NULL -> NaN (faltante nativo de LightGBM, sin imputar); "
                                  "matriz float64 en C-order; etiqueta int8")
    tiempos["validacion_union_s"] = round(time.perf_counter() - t, 1)
    estado.marcar("union_validada")

    # 2. Carga: matrices por partición -------------------------------------
    datos = {}
    t = time.perf_counter()
    for p, ms in PARTICIONES.items():
        X, cli, mes = cargar(con, ms, pred, tipos, mats / f"X_{p}.npy")
        datos[p] = {"X": X, "cli": cli, "mes": mes}
        estado.marcar(f"cargada_{p}", filas=len(cli))
    tiempos["carga_s"] = round(time.perf_counter() - t, 1)

    # 3. Preparación: etiquetas alineadas y conteos ------------------------
    t = time.perf_counter()
    rep["particiones"] = {}
    for p, ms in PARTICIONES.items():
        d = datos[p]
        d["y"], d["ternaria"] = etiquetas(con, ms, d["cli"], d["mes"])
        terna = {k: int(v) for k, v in zip(*np.unique(d["ternaria"].astype(str), return_counts=True))}
        rep["particiones"][p] = {"meses": ms, "filas": int(len(d["y"])), "positivos": int(d["y"].sum()),
                                 "tasa_positivos": round(float(d["y"].mean()), 6), "ternaria": terna,
                                 "filas_por_mes": {str(m): int((d["mes"] == m).sum()) for m in ms},
                                 "dtype_X": str(d["X"].dtype), "forma_X": list(d["X"].shape)}
        log.info("partición %s: %s", p, rep["particiones"][p])
    con.close()
    tiempos["preparacion_s"] = round(time.perf_counter() - t, 1)
    estado.marcar("preparado")

    # 4. Entrenamiento ------------------------------------------------------
    modelo = lgb.LGBMClassifier(**PARAMS)
    log.info("entrenando LGBMClassifier %s", modelo.get_params())
    t = time.perf_counter()
    modelo.fit(datos["train"]["X"], datos["train"]["y"], feature_name=pred)
    tiempos["entrenamiento_s"] = round(time.perf_counter() - t, 1)
    gc.collect()
    estado.marcar("entrenado", arboles=modelo.booster_.num_trees())
    modelo.booster_.save_model(str(run / "modelo.txt"))

    # 5. Predicción -----------------------------------------------------------
    rep["metricas"], rep["probabilidades"] = {}, {}
    for p in PARTICIONES:
        t = time.perf_counter()
        prob = modelo.predict_proba(datos[p]["X"])[:, 1]
        tiempos[f"prediccion_{p}_s"] = round(time.perf_counter() - t, 1)
        rep["probabilidades"][p] = {"finitas": bool(np.isfinite(prob).all()),
                                    "en_0_1": bool(((prob >= 0) & (prob <= 1)).all()),
                                    "min": float(prob.min()), "max": float(prob.max()), "media": float(prob.mean()),
                                    "dtype": str(prob.dtype)}
        rep["metricas"][f"auc_{p}"] = round(float(roc_auc_score(datos[p]["y"], prob)), 6)
        log.info("%s: AUC %.6f | %s", p, rep["metricas"][f"auc_{p}"], rep["probabilidades"][p])
        if p == "validacion":
            pred_df = pd.DataFrame({"numero_de_cliente": datos[p]["cli"], "foto_mes": datos[p]["mes"],
                                    "prob_baja": prob, "clase_binaria": datos[p]["y"],
                                    "clase_ternaria": datos[p]["ternaria"].astype(str)})
            c2 = duckdb.connect()
            c2.register("pred_df", pred_df)
            c2.execute(f"COPY (SELECT * FROM pred_df) TO '{(run / 'predicciones_201908.parquet').as_posix()}' "
                       f"(FORMAT parquet, COMPRESSION zstd)")
            c2.close()
            del pred_df
        del prob
        estado.marcar(f"predicho_{p}")

    # 6. Configuración, parámetros y reporte ----------------------------------
    rep["parametros"] = {"pasados": PARAMS, "sklearn_get_params": modelo.get_params(),
                         "lightgbm_efectivos": parametros_efectivos(modelo),
                         "arboles": modelo.booster_.num_trees(), "early_stopping": False,
                         "sampling_externo": False, "pesos_de_clase": None, "imputacion": False}
    config = {"datos": {"features": FEAT_DIR.relative_to(ROOT).as_posix(), "target": TARGET.relative_to(ROOT).as_posix(),
                        "particiones": PARTICIONES, "excluido": MES_PROHIBIDO,
                        "target_binario": "BAJA+1/BAJA+2 = 1; CONTINUA = 0 (clase_binaria de 03)"},
              "modelo": "lightgbm.LGBMClassifier", "parametros": PARAMS, "semilla": SEMILLA, "hilos": HILOS}
    (run / "configuracion.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    for p in PARTICIONES:
        del datos[p]["X"]
    del datos
    gc.collect()
    for intento in range(1, 16):  # el antivirus puede tener abierto un .npy recién escrito
        try:
            shutil.rmtree(mats)
            rep["matrices_tmp"] = f"borradas al terminar bien (intento {intento})"
            break
        except OSError as e:
            rep["matrices_tmp"] = f"no se pudieron borrar: {e!r}"
            time.sleep(2)
    else:
        log.warning("matrices_tmp: %s", rep["matrices_tmp"])

    tiempos["total_s"] = round(time.perf_counter() - t0, 1)
    rep["tiempos"] = tiempos
    rep["memoria"] = memoria(proc)
    rep["archivos"] = sorted(p.name for p in run.iterdir())
    (run / "reporte.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    estado.marcar("terminado")
    log.info("AUC train %.6f | AUC validación %.6f | tiempos %s | memoria %s",
             rep["metricas"]["auc_train"], rep["metricas"]["auc_validacion"], tiempos, rep["memoria"])
    log.info("Reporte: %s", (run / "reporte.json").relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log.exception("la corrida falló; matrices_tmp y estado.json quedan para diagnóstico")
        raise
