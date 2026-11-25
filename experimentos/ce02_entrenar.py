"""CE02 (paso 1) — 20 semillas por objetivo con el target corregido (docs/PLAN_PRUEBAS.md § 13).

Reutiliza los 5 modelos de TC01 (semillas 20261124–20261128) y entrena 15 nuevos por objetivo (20261129–20261143),
con la configuración de E01/TC01: 760 features, train 201903–201906 (target versión 2), hiperparámetros, 300 rondas,
binado (max_bin 255, data_random_seed 1), 8 hilos para entrenar y 4 para predecir. Predice 201908 y 201909 (octubre
bloqueado por evaluacion/particiones.py).

Compatibilidad, antes de entrenar las nuevas (si falla, se detiene):
  1. configuración y semillas de TC01 iguales a las de este protocolo; target versión 2 con el mismo sha256;
  2. clases del train iguales a las de TC01;
  3. los 10 modelos de TC01 reproducen sus predicciones guardadas (float32);
  4. el binario de la semilla 20261124, reentrenado acá, predice exactamente igual que el de TC01 (float64).
Reanudable: con --reanudar <carpeta>, los modelos ya guardados se cargan en lugar de entrenarse.
Mantiene la máquina despierta durante la corrida (Windows: SetThreadExecutionState).

Uso: python -m experimentos.ce02_entrenar --tc01 ejecuciones/tc01/<marca> [--reanudar ejecuciones/ce02/<marca>]
Salida: ejecuciones/ce02/<marca>/ (modelos de las 20 semillas, pred_<brazo>.npz en float64, meta_<mes>.npz,
resultados.json).
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import time
from pathlib import Path

import duckdb
import lightgbm as lgb
import numpy as np
import psutil

from evaluacion import particiones as P
from experimentos.ce02_composicion import REGISTRO, SEMILLAS, SEMILLAS_NUEVAS, SEMILLAS_TC01
from experimentos.e01_binario_vs_multiclase import CLASES, PARAMS, cargar, mem
from experimentos.e02_peso_baja1 import sha256
from pipeline_competencia02.config import RAIZ, RUTAS, mostrar

BRAZOS = {"binario": ("binario", None), "multiclase_p1": ("multiclase", 2)}  # brazo -> (archivo, columna del score)
NPZ_TC01 = {"binario": "pred_binario.npz", "multiclase_p1": "pred_multiclase_p1.npz"}


def despierto(activar: bool):
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | (0x00000001 if activar else 0))


def parametros(s: int, obj: str, hilos: int) -> dict:
    p = {**PARAMS, "seed": s, "num_threads": hilos}
    p.update({"objective": "binary"} if obj == "binario" else {"objective": "multiclass", "num_class": 3})
    return p


def predecir(b: lgb.Booster, col, X, hilos) -> np.ndarray:
    pr = b.predict(X, num_threads=hilos)
    return pr if col is None else pr[:, col]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tc01", type=Path, required=True)
    ap.add_argument("--reanudar", type=Path)
    ap.add_argument("--hilos", type=int, default=8)
    ap.add_argument("--hilos-prediccion", type=int, default=4)
    a = ap.parse_args(argv)
    tc = a.tc01.resolve()
    cfg_tc = json.loads((tc / "resultados.json").read_text(encoding="utf-8"))
    meta_t = json.loads(RUTAS.target_2019_v2.with_suffix(".json").read_text(encoding="utf-8"))
    checks = {"configuracion_igual_a_tc01": cfg_tc["params"] == PARAMS and cfg_tc["rondas"] == 300
              and cfg_tc["semillas"] == SEMILLAS_TC01 and cfg_tc["hilos_entrenamiento"] == a.hilos
              and cfg_tc["hilos_prediccion"] == a.hilos_prediccion,
              "target_v2_igual_a_tc01": sha256(RUTAS.target_2019_v2) == meta_t["salida"]["sha256"]
              == cfg_tc["target"]["sha256"]}
    if not all(checks.values()):
        raise SystemExit(f"compatibilidad con TC01 fallida: {checks}")

    if a.reanudar:
        out = a.reanudar.resolve()
        marca = out.name
    else:
        marca = time.strftime("%Y%m%dT%H%M%S") + f"_{os.getpid()}"
        out = RAIZ / "ejecuciones" / "ce02" / marca
        (out / "modelos").mkdir(parents=True)
    t0 = time.perf_counter()
    rep = {"experimento": "CE02 paso 1: 20 semillas con target versión 2", "marca": marca,
           "inicio": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "plan_pruebas_sha256_al_inicio": sha256(RAIZ / "docs" / "PLAN_PRUEBAS.md"),
           "composicion_sha256": sha256(REGISTRO), "semillas": SEMILLAS, "reutilizadas_de_tc01": SEMILLAS_TC01,
           "nuevas": SEMILLAS_NUEVAS, "tc01": mostrar(tc), "params": PARAMS, "rondas": 300,
           "target": {"archivo": mostrar(RUTAS.target_2019_v2), "sha256": meta_t["salida"]["sha256"]},
           "particiones": {"train": P.ENTRENAMIENTO, "desarrollo": P.DESARROLLO, "no_leido": P.EVALUACION_FINAL},
           "hilos_entrenamiento": a.hilos, "hilos_prediccion": a.hilos_prediccion,
           "maquina": {"cpu_logicos": psutil.cpu_count(), "ram_gb": round(psutil.virtual_memory().total / 2**30, 1),
                       "plataforma": platform.platform(), "lightgbm": lgb.__version__, "duckdb": duckdb.__version__},
           "checks": checks, "tiempos_s": {}, "reanudado": bool(a.reanudar)}
    (out / "config.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    despierto(True)
    try:
        pred_cols = json.loads((RUTAS.features_2019 / "manifiesto.json").read_text(encoding="utf-8"))["predictores"]
        con = duckdb.connect()
        con.execute(f"SET threads = {a.hilos}")
        t = time.perf_counter()
        Xtr, ctr, _, _ = cargar(con, P.ENTRENAMIENTO, pred_cols, RUTAS.target_2019_v2)
        dev = {m: cargar(con, (m,), pred_cols, RUTAS.target_2019_v2) for m in P.DESARROLLO}
        con.close()
        rep["tiempos_s"]["carga"] = round(time.perf_counter() - t, 1)
        rep["clases_train"] = {k: int((ctr == v).sum()) for k, v in CLASES.items()}
        checks["train_igual_a_tc01"] = rep["clases_train"] == cfg_tc["clases_train"]
        print(f"carga {rep['tiempos_s']['carga']}s {rep['clases_train']} {mem()}", flush=True)

        # modelos de TC01: reproducen sus predicciones y se copian
        preds = {b: {m: {} for m in P.DESARROLLO} for b in BRAZOS}
        tiempos = {b: {} for b in BRAZOS}
        repro = True
        for brazo, (arch, col) in BRAZOS.items():
            guard = np.load(tc / NPZ_TC01[brazo])
            for i, s in enumerate(SEMILLAS_TC01):
                origen = tc / "modelos" / f"{arch}_{s}.txt"
                destino = out / "modelos" / origen.name
                if not destino.exists():
                    shutil.copy2(origen, destino)
                repro &= sha256(destino) == sha256(origen)
                b = lgb.Booster(model_file=str(destino))
                for m, (X, _, _, _) in dev.items():
                    pr = predecir(b, col, X, a.hilos_prediccion)
                    repro &= bool(np.array_equal(pr.astype("float32"), guard[str(m)][i]))
                    preds[brazo][m][s] = pr
                tiempos[brazo][s] = {"origen": "TC01"}
        checks["tc01_reproduce_predicciones"] = repro

        t = time.perf_counter()
        ds = {"binario": lgb.Dataset(Xtr, label=(ctr > 0).astype("int8"), params={"max_bin": PARAMS["max_bin"],
                                     "data_random_seed": 1, "verbosity": -1}, free_raw_data=True).construct(),
              "multiclase": lgb.Dataset(Xtr, label=ctr, params={"max_bin": PARAMS["max_bin"], "data_random_seed": 1,
                                        "verbosity": -1}, free_raw_data=True).construct()}
        del Xtr
        rep["tiempos_s"]["binado"] = round(time.perf_counter() - t, 1)

        # compatibilidad: reentrenar el binario de la primera semilla de TC01
        t = time.perf_counter()
        b = lgb.train(parametros(SEMILLAS_TC01[0], "binario", a.hilos), ds["binario"], num_boost_round=300)
        checks["reentreno_semilla_tc01_identico"] = all(
            np.array_equal(predecir(b, None, X, a.hilos_prediccion), preds["binario"][m][SEMILLAS_TC01[0]])
            for m, (X, _, _, _) in dev.items())
        rep["tiempos_s"]["comprobacion_reentreno"] = round(time.perf_counter() - t, 1)
        del b
        print(f"compatibilidad {checks}", flush=True)
        if not all(checks.values()):
            raise SystemExit(f"compatibilidad fallida: {checks}")

        for s in SEMILLAS_NUEVAS:
            for brazo, (arch, col) in BRAZOS.items():
                ruta = out / "modelos" / f"{arch}_{s}.txt"
                t = time.perf_counter()
                if ruta.exists():
                    b = lgb.Booster(model_file=str(ruta))
                    tiempos[brazo][s] = {"origen": "reanudado"}
                else:
                    b = lgb.train(parametros(s, arch, a.hilos), ds[arch], num_boost_round=300)
                    tmp = ruta.with_name(ruta.name + ".tmp")
                    b.save_model(str(tmp))
                    os.replace(tmp, ruta)
                    tiempos[brazo][s] = {"origen": "CE02", "entrenar_s": round(time.perf_counter() - t, 1)}
                for m, (X, _, _, _) in dev.items():
                    preds[brazo][m][s] = predecir(b, col, X, a.hilos_prediccion)
                print(f"semilla {s} {brazo}: {tiempos[brazo][s]} {mem()}", flush=True)
        rep["tiempos_s"]["modelos"] = tiempos

        for brazo in BRAZOS:
            np.savez_compressed(out / f"pred_{brazo}.npz",
                                **{str(m): np.vstack([preds[brazo][m][s] for s in SEMILLAS]) for m in P.DESARROLLO})
        for m, (_, clase, cli, _) in dev.items():
            np.savez_compressed(out / f"meta_{m}.npz", clase=clase, clientes=cli)
        rep["modelos_sha256"] = {p.name: sha256(p) for p in sorted((out / "modelos").glob("*.txt"))}
        rep["tiempos_s"]["total"] = round(time.perf_counter() - t0, 1)
        rep["memoria"] = mem()
        rep["fin"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        (out / "resultados.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"listo en {rep['tiempos_s']['total']}s -> {mostrar(out)}; checks {checks}", flush=True)
    finally:
        despierto(False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
