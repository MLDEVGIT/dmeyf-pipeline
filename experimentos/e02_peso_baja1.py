"""E02 — peso de BAJA+1 en el objetivo multiclase: 1 (= E01) contra 0,5 (docs/PLAN_PRUEBAS.md § 4 y § 7).

Igual que E01 (no cambia nada más): las 760 features de experimento_sampling/04, train 201903–201906,
desarrollo 201908 y 201909 (octubre bloqueado por evaluacion/particiones.py), las 5 semillas, los
hiperparámetros, 300 rondas, el mismo binado (max_bin 255, data_random_seed 1), 8 hilos para entrenar y
4 para predecir. Score = P(BAJA+2).

Brazos:
  - multiclase_p1  : peso 1 para todas las clases. **Se reutiliza E01** (son los mismos modelos), sólo si
                     pasa las comprobaciones de compatibilidad; si no, se reentrena.
  - multiclase_p05 : BAJA+1 con peso 0,5 en el Dataset; CONTINUA y BAJA+2 con peso 1. Se entrena acá.
  - binario        : referencia del proyecto (E01), reutilizado con las mismas comprobaciones.

Comprobaciones de compatibilidad con E01 (todas deben dar igual):
  1. filas, clases y clientes de desarrollo idénticos a meta_<mes>.npz de E01;
  2. los modelos guardados de E01, vueltos a predecir sobre las features cargadas acá, dan exactamente
     las predicciones guardadas por E01 (float32);
  3. evaluar esas predicciones con evaluacion.comparacion reproduce las cifras de resultados.json de E01.

Uso: python -m experimentos.e02_peso_baja1 --e01 ejecuciones/e01/<marca>
Salida: ejecuciones/e02/<marca>/ y el resumen versionado resultados/e02_peso_baja1.json.
"""
from __future__ import annotations

import argparse
import hashlib
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

from evaluacion import comparacion as C
from evaluacion import ganancia as G
from evaluacion import particiones as P
from experimentos.e01_binario_vs_multiclase import CLASES, FRACCIONES, PARAMS, SEMILLAS, cargar, mem
from pipeline_competencia02.config import RAIZ, RUTAS, mostrar

PESO_BAJA1 = 0.5
MINIMO_SEMILLAS = 4
REGLA = ("Se adopta multiclase con peso de BAJA+1 = 0,5 frente a peso 1 (E01) sólo si se cumplen las tres: "
         "(1) mayor ganancia del ensamble de probabilidades en su propia fracción, en 201908 y en 201909; "
         "(2) diferencia pareada por semilla positiva en al menos 4 de 5 semillas en cada mes; "
         "(3) peor caso de transferencia del corte no mayor que el de peso 1. Si no, queda peso 1. "
         "Después, el multiclase que quede se compara con el binario de E01 con la misma regla; si la cumple, "
         "pasa a ser la referencia del proyecto; si no, el binario sigue de referencia.")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def reusar_e01(e01: Path, cfg: dict, dev: dict, hilos: int) -> tuple[dict, dict]:
    """Repredice con los modelos de E01 y comprueba que todo coincida. Devuelve preds float64 y el informe."""
    inf = {"meta_identica": {}, "predicciones_identicas": {}, "metricas_identicas": {}}
    for m, (_, clase, cli, _) in dev.items():
        z = np.load(e01 / f"meta_{m}.npz")
        inf["meta_identica"][str(m)] = bool(np.array_equal(z["clase"], clase) and np.array_equal(z["clientes"], cli))
    preds, tiempos = {}, {}
    for obj, col in (("binario", None), ("multiclase", 2)):
        guardadas = np.load(e01 / f"pred_{obj}.npz")
        preds[obj] = {m: [] for m in dev}
        tiempos[obj] = []
        iguales = True
        for i, s in enumerate(cfg["semillas"]):
            b = lgb.Booster(model_file=str(e01 / "modelos" / f"{obj}_{s}.txt"))
            for m, (X, _, _, _) in dev.items():
                t = time.perf_counter()
                pr = b.predict(X, num_threads=hilos)
                tiempos[obj].append(round(time.perf_counter() - t, 2))
                pr = pr if col is None else pr[:, col]
                iguales &= bool(np.array_equal(pr.astype("float32"), guardadas[str(m)][i]))
                preds[obj][m].append(pr)
        inf["predicciones_identicas"][obj] = iguales
        inf.setdefault("tiempos_reprediccion_s", {})[obj] = tiempos[obj]
    meta = {m: (d[1], d[2]) for m, d in dev.items()}
    evaluados = {obj: C.evaluar_brazo(preds[obj], meta, FRACCIONES) for obj in preds}
    for obj, ev in evaluados.items():
        orig = cfg["resultados"][obj]
        ok = ev["corte"]["fraccion"] == orig["corte"]["fraccion"]
        for m in dev:
            a, b = ev["corte"][str(m)], orig["corte"][str(m)]
            ok &= a["envios"] == b["envios"] and a["ganancia"] == b["ganancia"] and a["por_semilla"] == b["por_semilla"]
        ok &= all(ev["transferencia"][k]["ganancia"] == v["ganancia"] for k, v in orig["transferencia"].items())
        inf["metricas_identicas"][obj] = bool(ok)
    inf["compatible"] = (all(inf["meta_identica"].values()) and all(inf["predicciones_identicas"].values())
                         and all(inf["metricas_identicas"].values()))
    return {"binario": preds["binario"], "multiclase_p1": preds["multiclase"]}, inf


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--e01", type=Path, required=True)
    ap.add_argument("--hilos", type=int, default=8)
    ap.add_argument("--hilos-prediccion", type=int, default=4)
    a = ap.parse_args(argv)
    e01 = a.e01.resolve()
    cfg01 = json.loads((e01 / "resultados.json").read_text(encoding="utf-8"))
    # misma configuración que E01, comprobada antes de entrenar
    distintos = {k: (cfg01[k], v) for k, v in (("params", PARAMS), ("rondas", 300), ("semillas", SEMILLAS[:5]),
                                                ("hilos_entrenamiento", a.hilos),
                                                ("hilos_prediccion", a.hilos_prediccion)) if cfg01[k] != v}
    if distintos:
        raise SystemExit(f"la configuración de E01 no coincide con la de E02: {distintos}")

    marca = time.strftime("%Y%m%dT%H%M%S") + f"_{os.getpid()}"
    out = RAIZ / "ejecuciones" / "e02" / marca
    (out / "modelos").mkdir(parents=True)
    t0 = time.perf_counter()
    plan = RAIZ / "docs" / "PLAN_PRUEBAS.md"
    rep = {"experimento": "E02 peso de BAJA+1 en multiclase", "marca": marca, "inicio": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "regla_adopcion": REGLA, "plan_pruebas_sha256_al_inicio": sha256(plan),
           "peso_baja1": PESO_BAJA1, "semillas": cfg01["semillas"], "rondas": cfg01["rondas"], "params": PARAMS,
           "hilos_entrenamiento": a.hilos, "hilos_prediccion": a.hilos_prediccion, "e01": mostrar(e01),
           "particiones": {"train": P.ENTRENAMIENTO, "desarrollo": P.DESARROLLO, "no_leido": P.EVALUACION_FINAL},
           "ganancia": {"premio_bruto": G.PREMIO_BRUTO, "costo_envio": G.COSTO_ENVIO,
                        "neta_por_acierto": G.GANANCIA_NETA_ACIERTO, "ventana_suavizado": G.VENTANA_SUAVIZADO},
           "maquina": {"cpu_logicos": psutil.cpu_count(), "ram_gb": round(psutil.virtual_memory().total / 2**30, 1),
                       "plataforma": platform.platform(), "python": platform.python_version(),
                       "lightgbm": lgb.__version__, "duckdb": duckdb.__version__},
           "tiempos_s": {}, "memoria": {}}
    (out / "config.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")

    pred = json.loads((RUTAS.features_2019 / "manifiesto.json").read_text(encoding="utf-8"))["predictores"]
    con = duckdb.connect()
    con.execute(f"SET threads = {a.hilos}")
    t = time.perf_counter()
    Xtr, ctr, _, _ = cargar(con, P.ENTRENAMIENTO, pred)
    dev = {m: cargar(con, (m,), pred) for m in P.DESARROLLO}
    con.close()
    rep["tiempos_s"]["carga"] = round(time.perf_counter() - t, 1)
    rep["memoria"]["tras_carga"] = mem()
    rep["clases_train"] = {k: int((ctr == v).sum()) for k, v in CLASES.items()}
    if rep["clases_train"] != cfg01["clases_train"]:
        raise SystemExit(f"el train no coincide con E01: {rep['clases_train']} vs {cfg01['clases_train']}")
    print(f"carga {rep['tiempos_s']['carga']}s {mem()}", flush=True)

    t = time.perf_counter()
    reus, compat = reusar_e01(e01, cfg01, dev, a.hilos_prediccion)
    rep["tiempos_s"]["comprobacion_e01"] = round(time.perf_counter() - t, 1)
    rep["compatibilidad_e01"] = compat
    print(f"compatibilidad con E01: {compat['compatible']} {({k: v for k, v in compat.items() if k != 'tiempos_reprediccion_s'})}",
          flush=True)
    if not compat["compatible"]:
        raise SystemExit("E01 no es reutilizable tal cual: reentrenar los brazos de referencia (ver config.json)")

    t = time.perf_counter()
    peso = np.where(ctr == CLASES["BAJA+1"], PESO_BAJA1, 1.0)
    ds = lgb.Dataset(Xtr, label=ctr, weight=peso, params={"max_bin": PARAMS["max_bin"], "data_random_seed": 1,
                                                          "verbosity": -1}, free_raw_data=True).construct()
    del Xtr
    rep["tiempos_s"]["binado"] = round(time.perf_counter() - t, 1)
    rep["memoria"]["tras_binado"] = mem()
    rep["suma_pesos_train"] = float(peso.sum())

    preds = {m: [] for m in P.DESARROLLO}
    tiempos = {"entrenar_s": [], "predecir_s_por_mes": []}
    for s in cfg01["semillas"]:
        p = {**PARAMS, "seed": s, "num_threads": a.hilos, "objective": "multiclass", "num_class": 3}
        t = time.perf_counter()
        b = lgb.train(p, ds, num_boost_round=cfg01["rondas"])
        tiempos["entrenar_s"].append(round(time.perf_counter() - t, 1))
        b.save_model(str(out / "modelos" / f"multiclase_p05_{s}.txt"))
        for m, (X, _, _, _) in dev.items():
            t = time.perf_counter()
            preds[m].append(b.predict(X, num_threads=a.hilos_prediccion)[:, 2])
            tiempos["predecir_s_por_mes"].append(round(time.perf_counter() - t, 2))
        print(f"semilla {s} multiclase_p05: entrenar {tiempos['entrenar_s'][-1]}s, "
              f"predecir {tiempos['predecir_s_por_mes'][-2:]}s {mem()}", flush=True)
    rep["tiempos_s"]["multiclase_p05"] = tiempos
    rep["tiempos_s"]["e01"] = cfg01["tiempos_s"]["modelos"]
    rep["memoria"]["tras_entrenar"] = mem()

    meta = {m: (d[1], d[2]) for m, d in dev.items()}
    brazos = {"binario": reus["binario"], "multiclase_p1": reus["multiclase_p1"], "multiclase_p05": preds}
    res = {k: C.evaluar_brazo(v, meta, FRACCIONES) for k, v in brazos.items()}
    decision = {"p05_vs_p1": C.regla_adopcion(res["multiclase_p05"], res["multiclase_p1"], P.DESARROLLO, MINIMO_SEMILLAS)}
    elegido = "multiclase_p05" if decision["p05_vs_p1"]["adopta"] else "multiclase_p1"
    decision["multiclase_elegido"] = elegido
    decision[f"{elegido}_vs_binario"] = C.regla_adopcion(res[elegido], res["binario"], P.DESARROLLO, MINIMO_SEMILLAS)
    decision["referencia_del_proyecto"] = elegido if decision[f"{elegido}_vs_binario"]["adopta"] else "binario"
    # diagnóstico, no decide: el otro multiclase contra el binario
    otro = "multiclase_p1" if elegido == "multiclase_p05" else "multiclase_p05"
    decision[f"diagnostico_{otro}_vs_binario"] = C.regla_adopcion(res[otro], res["binario"], P.DESARROLLO, MINIMO_SEMILLAS)

    np.savez_compressed(out / "pred_multiclase_p05.npz", **{str(m): np.vstack(l).astype("float32") for m, l in preds.items()})
    rep["resultados"] = res
    rep["decision"] = decision
    rep["tiempos_s"]["total"] = round(time.perf_counter() - t0, 1)
    rep["memoria"]["final"] = mem()
    rep["fin"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    (out / "resultados.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=float), encoding="utf-8")

    # resumen versionado: sin datos por cliente
    resumen = {k: rep[k] for k in ("experimento", "marca", "inicio", "fin", "regla_adopcion", "plan_pruebas_sha256_al_inicio",
                                   "peso_baja1", "semillas", "rondas", "params", "hilos_entrenamiento",
                                   "hilos_prediccion", "e01", "particiones", "ganancia", "maquina", "clases_train",
                                   "suma_pesos_train", "compatibilidad_e01", "tiempos_s", "memoria", "decision")}
    resumen["resultados"] = {k: {"corte": v["corte"], "ensamble": v["ensamble"], "transferencia": v["transferencia"],
                                 "transferencia_peor_caso": v["transferencia_peor_caso"]} for k, v in res.items()}
    destino = RAIZ / "resultados" / "e02_peso_baja1.json"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(json.dumps(resumen, indent=2, ensure_ascii=False, default=float) + "\n", encoding="utf-8",
                       newline="\n")
    print(f"listo en {rep['tiempos_s']['total']}s -> {mostrar(out)}; referencia: {decision['referencia_del_proyecto']}",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
