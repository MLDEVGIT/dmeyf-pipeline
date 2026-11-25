"""E01 — objetivo binario contra multiclase, con features idénticas (docs/PLAN_PRUEBAS.md).

Fijo de antemano (no se ajusta mirando resultados):
  - Features: las 760 de experimento_sampling/04 (152 crudas + lag/delta 1 y 2 por fila), sin cambios.
  - Train 201903–201906 completos; desarrollo 201908 y 201909 (201907 sólo aporta historia a las
    features de agosto). Octubre no se lee: evaluacion/particiones.py lo rechaza.
  - Binario: positivo BAJA+1 ∪ BAJA+2 (baseline 208135). Score = P(positivo).
  - Multiclase: CONTINUA / BAJA+1 / BAJA+2, sin pesos (el peso de BAJA+1 es E02).
    Score principal = P(BAJA+2); se registra también P(BAJA+1)+P(BAJA+2) como diagnóstico.
  - Mismos hiperparámetros, mismas semillas, mismo Dataset binado (max_bin, data_random_seed).
  - Corte: fracción de clientes con menor arrepentimiento máximo entre agosto y septiembre sobre la
    curva suavizada del ensamble de semillas; además, transferencia cruzada (elegido en un mes,
    medido en el otro).

Uso: python -m experimentos.e01_binario_vs_multiclase [--semillas 5] [--rondas 300] [--hilos 8]
Salida: ejecuciones/e01/<marca>/ (config.json, resultados.json, predicciones .npz, modelos .txt).
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path

import duckdb
import lightgbm as lgb
import numpy as np
import psutil
from sklearn.metrics import roc_auc_score

from evaluacion import ganancia as G
from evaluacion import particiones as P
from pipeline_competencia02.config import RAIZ, RUTAS, mostrar

SEMILLAS = [20261124, 20261125, 20261126, 20261127, 20261128, 20261129, 20261130, 20261131, 20261132, 20261133]
PARAMS = dict(learning_rate=0.05, num_leaves=63, min_data_in_leaf=200, feature_fraction=0.5,
              bagging_fraction=1.0, bagging_freq=0, lambda_l2=0.0, max_bin=255, data_random_seed=1,
              deterministic=True, force_col_wise=True, verbosity=-1)
# Grilla 0,25 %–8 %: la prueba de humo (10 rondas) tocó el borde superior de la grilla inicial de 3 %.
FRACCIONES = np.round(np.arange(0.0025, 0.08 + 1e-12, 0.00025), 6)
CLASES = {"CONTINUA": 0, "BAJA+1": 1, "BAJA+2": 2}
LOTE = 100
proc = psutil.Process()


def mem() -> dict:
    mi = proc.memory_info()
    d = {"rss_mb": round(mi.rss / 2**20)}
    if hasattr(mi, "peak_wset"):
        d["pico_working_set_mb"] = round(mi.peak_wset / 2**20)
    return d


def cargar(con, meses, predictores, ruta_target: Path | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """X float64 (BIGINT exacto hasta 2^53, NULL -> NaN), clase, clientes y mes, ordenados por mes y cliente.

    ruta_target: por defecto el target de E01 (RUTAS.target_2019, regla versión 1); TC01 pasa RUTAS.target_2019_v2.
    """
    feats = ", ".join(f"'{(RUTAS.features_2019 / f'features_{m}.parquet').as_posix()}'" for m in meses)
    con.execute(f"CREATE OR REPLACE TEMP VIEW f AS SELECT * FROM read_parquet([{feats}])")
    # el target se lee sólo con la función que controla los meses permitidos
    tgt = P.leer_target(con, Path(ruta_target or RUTAS.target_2019).as_posix(), meses).df()
    con.register("tgt_df", tgt)
    con.execute("CREATE OR REPLACE TEMP TABLE j AS SELECT f.numero_de_cliente, f.foto_mes, tgt_df.clase_ternaria, "
                "row_number() OVER (ORDER BY f.foto_mes, f.numero_de_cliente) - 1 AS fila "
                "FROM f JOIN tgt_df USING (numero_de_cliente, foto_mes)")
    con.unregister("tgt_df")
    n_f = con.execute("SELECT count(*) FROM f").fetchone()[0]
    n, nulos = con.execute("SELECT count(*), count(*) FILTER (WHERE clase_ternaria IS NULL) FROM j").fetchone()
    if n != n_f or nulos:
        raise RuntimeError(f"features {n_f} filas, con target {n}, target nulo {nulos}")
    meta = con.execute("SELECT numero_de_cliente, foto_mes, clase_ternaria FROM j ORDER BY fila").fetchnumpy()
    X = np.empty((n, len(predictores)), dtype="float64")
    for i in range(0, len(predictores), LOTE):
        cols = predictores[i:i + LOTE]
        sel = ", ".join(f'CAST(f."{c}" AS DOUBLE) AS "{c}"' for c in cols)
        df = con.execute(f"SELECT {sel} FROM f JOIN j USING (numero_de_cliente, foto_mes) ORDER BY j.fila").df()
        X[:, i:i + len(cols)] = df.to_numpy(dtype="float64", na_value=np.nan)
    clase = np.array([CLASES[c] for c in meta["clase_ternaria"]], dtype="int8")
    return X, clase, np.asarray(meta["numero_de_cliente"]), np.asarray(meta["foto_mes"])


def evaluar_mes(score, clase, clientes) -> dict:
    b2 = clase == 2
    g = G.curva(score, b2, clientes)
    gs = G.suavizar(g)
    k = int(np.nanargmax(gs)) + 1
    return {"g": g, "gs": gs, "k_max_suav": k, "g_max_suav": float(np.nanmax(gs)),
            "auc_baja2": float(roc_auc_score(b2, score)), "n": len(score), "baja2": int(b2.sum())}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--semillas", type=int, default=5)
    ap.add_argument("--rondas", type=int, default=300)
    ap.add_argument("--hilos", type=int, default=8)
    ap.add_argument("--hilos-prediccion", type=int, default=4, help="los del pipeline mensual (ejecutar_mes.HILOS)")
    a = ap.parse_args(argv)
    marca = time.strftime("%Y%m%dT%H%M%S") + f"_{os.getpid()}"
    out = RAIZ / "ejecuciones" / "e01" / marca
    (out / "modelos").mkdir(parents=True)
    semillas = SEMILLAS[:a.semillas]
    t0 = time.perf_counter()
    rep = {"experimento": "E01 binario vs multiclase", "marca": marca, "semillas": semillas, "rondas": a.rondas,
           "params": PARAMS, "hilos_entrenamiento": a.hilos, "hilos_prediccion": a.hilos_prediccion,
           "particiones": {"train": P.ENTRENAMIENTO, "desarrollo": P.DESARROLLO, "no_leido": P.EVALUACION_FINAL},
           "ganancia": {"premio_bruto": G.PREMIO_BRUTO, "costo_envio": G.COSTO_ENVIO,
                        "neta_por_acierto": G.GANANCIA_NETA_ACIERTO, "ventana_suavizado": G.VENTANA_SUAVIZADO},
           "maquina": {"cpu_logicos": psutil.cpu_count(), "ram_gb": round(psutil.virtual_memory().total / 2**30, 1),
                       "plataforma": platform.platform(), "python": platform.python_version(),
                       "lightgbm": lgb.__version__, "duckdb": duckdb.__version__},
           "tiempos_s": {}, "memoria": {}}
    (out / "config.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")

    manifiesto = json.loads((RUTAS.features_2019 / "manifiesto.json").read_text(encoding="utf-8"))
    pred = manifiesto["predictores"]
    con = duckdb.connect()
    con.execute(f"SET threads = {a.hilos}")
    t = time.perf_counter()
    Xtr, ctr, _, _ = cargar(con, P.ENTRENAMIENTO, pred)
    dev = {m: cargar(con, (m,), pred) for m in P.DESARROLLO}
    con.close()
    rep["tiempos_s"]["carga"] = round(time.perf_counter() - t, 1)
    rep["memoria"]["tras_carga"] = mem()
    rep["filas"] = {"train": int(len(ctr)), **{str(m): int(len(d[1])) for m, d in dev.items()}}
    rep["clases_train"] = {k: int((ctr == v).sum()) for k, v in CLASES.items()}
    print(f"carga {rep['tiempos_s']['carga']}s {rep['filas']} {mem()}", flush=True)

    t = time.perf_counter()
    ds = {"binario": lgb.Dataset(Xtr, label=(ctr > 0).astype("int8"), params={"max_bin": PARAMS["max_bin"],
                                 "data_random_seed": 1, "verbosity": -1}, free_raw_data=True).construct(),
          "multiclase": lgb.Dataset(Xtr, label=ctr, params={"max_bin": PARAMS["max_bin"], "data_random_seed": 1,
                                    "verbosity": -1}, free_raw_data=True).construct()}
    del Xtr
    rep["tiempos_s"]["binado"] = round(time.perf_counter() - t, 1)
    rep["memoria"]["tras_binado"] = mem()

    preds = {obj: {m: [] for m in P.DESARROLLO} for obj in ds}
    preds["multiclase_b1b2"] = {m: [] for m in P.DESARROLLO}
    tiempos = {obj: {"entrenar_s": [], "predecir_s_por_mes": []} for obj in ds}
    for s in semillas:
        for obj in ds:
            p = {**PARAMS, "seed": s, "num_threads": a.hilos}
            p.update({"objective": "binary"} if obj == "binario" else {"objective": "multiclass", "num_class": 3})
            t = time.perf_counter()
            b = lgb.train(p, ds[obj], num_boost_round=a.rondas)
            tiempos[obj]["entrenar_s"].append(round(time.perf_counter() - t, 1))
            b.save_model(str(out / "modelos" / f"{obj}_{s}.txt"))
            for m, (X, _, _, _) in dev.items():
                t = time.perf_counter()
                pr = b.predict(X, num_threads=a.hilos_prediccion)
                tiempos[obj]["predecir_s_por_mes"].append(round(time.perf_counter() - t, 2))
                if obj == "binario":
                    preds["binario"][m].append(pr)
                else:
                    preds["multiclase"][m].append(pr[:, 2])
                    preds["multiclase_b1b2"][m].append(pr[:, 1] + pr[:, 2])
            print(f"semilla {s} {obj}: entrenar {tiempos[obj]['entrenar_s'][-1]}s, "
                  f"predecir {tiempos[obj]['predecir_s_por_mes'][-2:]}s {mem()}", flush=True)
    rep["tiempos_s"]["modelos"] = tiempos
    rep["memoria"]["tras_entrenar"] = mem()

    resultados = {}
    for obj, por_mes in preds.items():
        r = {"por_semilla": {}, "ensamble": {}}
        curvas_ens, n = {}, {}
        for m, lista in por_mes.items():
            _, clase, cli, _ = dev[m]
            n[m] = len(clase)
            ev_s = [evaluar_mes(sc, clase, cli) for sc in lista]
            ens = evaluar_mes(np.mean(lista, axis=0), clase, cli)
            curvas_ens[m] = ens["gs"]
            r["ensamble"][str(m)] = {k: v for k, v in ens.items() if k not in ("g", "gs")}
            r["por_semilla"][str(m)] = [{k: v for k, v in e.items() if k not in ("g", "gs")} for e in ev_s]
            r.setdefault("_curvas_semilla", {})[m] = ev_s
            r.setdefault("_ens", {})[m] = ens
        f, tabla = G.corte_minimax(curvas_ens, n, FRACCIONES)
        r["corte"] = {"fraccion": f, "arrepentimiento_max": float(tabla["peor_caso"][list(FRACCIONES).index(f)])}
        for m in P.DESARROLLO:
            k = G.envios(f, n[m])
            ens = r["_ens"][m]
            r["corte"][str(m)] = {
                "envios": k, "ganancia": int(ens["g"][k - 1]), "ganancia_suav": float(ens["gs"][k - 1]),
                "ganancia_max_suav": ens["g_max_suav"], "k_max_suav": ens["k_max_suav"],
                "por_semilla": [int(e["g"][k - 1]) for e in r["_curvas_semilla"][m]]}
            ps = np.array(r["corte"][str(m)]["por_semilla"], dtype=float)
            r["corte"][str(m)]["semillas_media"] = float(ps.mean())
            r["corte"][str(m)]["semillas_desvio"] = float(ps.std(ddof=1)) if len(ps) > 1 else None
        # transferencia: elegido en un mes, medido en el otro
        r["transferencia"] = {}
        for elegido, medido in ((P.DESARROLLO[0], P.DESARROLLO[1]), (P.DESARROLLO[1], P.DESARROLLO[0])):
            fe, _ = G.corte_minimax({elegido: curvas_ens[elegido]}, {elegido: n[elegido]}, FRACCIONES)
            k = G.envios(fe, n[medido])
            gm = r["_ens"][medido]
            r["transferencia"][f"{elegido}->{medido}"] = {
                "fraccion": fe, "envios": k, "ganancia": int(gm["g"][k - 1]),
                "arrepentimiento": float(1 - gm["gs"][k - 1] / gm["g_max_suav"])}
        np.savez_compressed(out / f"pred_{obj}.npz", **{str(m): np.vstack(l).astype("float32") for m, l in por_mes.items()})
        for k in ("_curvas_semilla", "_ens"):
            r.pop(k)
        resultados[obj] = r
    for m in P.DESARROLLO:
        _, clase, cli, _ = dev[m]
        np.savez_compressed(out / f"meta_{m}.npz", clase=clase, clientes=cli)

    rep["resultados"] = resultados
    rep["tiempos_s"]["total"] = round(time.perf_counter() - t0, 1)
    rep["memoria"]["final"] = mem()
    (out / "resultados.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
    print(f"listo en {rep['tiempos_s']['total']}s -> {mostrar(out)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
