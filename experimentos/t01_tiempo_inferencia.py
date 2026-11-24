"""T01 — tiempo de inferencia con modelos representativos (docs/PLAN_PRUEBAS.md § Tiempos).

No lee etiquetas. Usa los modelos guardados por E01 (63 hojas, 300 rondas) y mide:
  A. `predict` puro sobre las features de 201909 (133.419 filas × 760), con 100/200/300 árboles
     (`num_iteration`), 4 y 8 hilos, binario y multiclase; mediana de 3 repeticiones.
  B. Punta a punta con el pipeline mensual real (`ejecutar_mes`) sobre 202001 (mes de ensayo,
     uso operativo), con el modelo binario de E01 en un entorno nuevo.
Todo lo que se extrapola (más árboles o más semillas) se marca "estimacion" en la salida.

Uso: python -m experimentos.t01_tiempo_inferencia --e01 ejecuciones/e01/<marca>
"""
from __future__ import annotations

import argparse
import json
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

import duckdb
import lightgbm as lgb
import numpy as np
import psutil

from pipeline_competencia02.config import RAIZ, RUTAS, mostrar

MES_FEATURES = 201909
MES_ENSAYO = 202001
REPETICIONES = 3
CONFIG_ESTIMACION = [(arboles, semillas) for arboles in (300, 1000) for semillas in (1, 5, 10, 20)]


def cargar_features(pred: list[str]) -> np.ndarray:
    ruta = (RUTAS.features_2019 / f"features_{MES_FEATURES}.parquet").as_posix()
    con = duckdb.connect()
    sel = ", ".join(f'CAST("{c}" AS DOUBLE) AS "{c}"' for c in pred)
    X = con.execute(f"SELECT {sel} FROM read_parquet('{ruta}') ORDER BY numero_de_cliente").df() \
        .to_numpy(dtype="float64", na_value=np.nan)
    con.close()
    return X


def medir(b: lgb.Booster, X: np.ndarray, it: int, hilos: int) -> float:
    ts = []
    for _ in range(REPETICIONES):
        t = time.perf_counter()
        b.predict(X, num_iteration=it, num_threads=hilos)
        ts.append(time.perf_counter() - t)
    return statistics.median(ts)


def modelo_con_nombres(origen: Path, destino: Path, pred: list[str]):
    """Copia del modelo con la línea feature_names reemplazada; los árboles no cambian.

    Se trabaja en bytes: en Windows, write_text convierte "\\n" en "\\r\\n" y LightGBM no lee los árboles.
    """
    lineas = origen.read_bytes().split(b"\n")
    if sum(1 for l in lineas if l.startswith(b"feature_names=")) != 1:
        raise RuntimeError("el modelo no tiene exactamente una línea feature_names")
    nombres = b"feature_names=" + " ".join(pred).encode("ascii")
    destino.write_bytes(b"\n".join(nombres if l.startswith(b"feature_names=") else l for l in lineas))
    a, b = lgb.Booster(model_file=str(origen)), lgb.Booster(model_file=str(destino))
    if a.num_trees() != b.num_trees() or b.feature_name() != pred:
        raise RuntimeError("la copia del modelo no conserva árboles o nombres")
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, len(pred)))
    if not np.array_equal(a.predict(X), b.predict(X)):
        raise RuntimeError("la copia del modelo no predice igual que el original")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--e01", type=Path, required=True)
    ap.add_argument("--sin-punta-a-punta", action="store_true")
    a = ap.parse_args(argv)
    e01 = a.e01.resolve()
    cfg = json.loads((e01 / "resultados.json").read_text(encoding="utf-8"))
    s0 = cfg["semillas"][0]
    pred = json.loads((RUTAS.features_2019 / "manifiesto.json").read_text(encoding="utf-8"))["predictores"]
    out = RAIZ / "ejecuciones" / "t01" / time.strftime("%Y%m%dT%H%M%S")
    out.mkdir(parents=True)
    rep = {"e01": mostrar(e01), "mes_features": MES_FEATURES, "cpu_logicos": psutil.cpu_count(),
           "lightgbm": lgb.__version__, "predict": {}, "estimacion": {}}

    X = cargar_features(pred)
    rep["filas"] = int(X.shape[0])
    for obj in ("binario", "multiclase"):
        b = lgb.Booster(model_file=str(e01 / "modelos" / f"{obj}_{s0}.txt"))
        rondas = b.current_iteration()
        filas = {}
        for hilos in (4, 8):
            for it in (100, 200, rondas):
                filas[f"{hilos}h_{it}r"] = round(medir(b, X, it, hilos), 2)
                print(obj, hilos, it, filas[f"{hilos}h_{it}r"], flush=True)
        rep["predict"][obj] = {"hojas": cfg["params"]["num_leaves"], "rondas": rondas,
                               "arboles_por_ronda": 1 if obj == "binario" else 3, "segundos": filas}
        # pendiente por ronda con 4 hilos (los del pipeline), ajustada sobre 100/200/rondas
        x = np.array([100, 200, rondas]); y = np.array([filas[f"4h_{i}r"] for i in x])
        pend, ord0 = np.polyfit(x, y, 1)
        rep["predict"][obj]["s_por_ronda_4h"] = float(pend)
        rep["estimacion"][obj] = {
            f"{arb}r_x_{sem}sem": round(float(ord0 + pend * arb) * sem * 153_000 / X.shape[0], 1)
            for arb, sem in CONFIG_ESTIMACION}
    rep["estimacion"]["nota"] = ("ESTIMACION: lineal en rondas y semillas a partir de lo medido, escalada a 153.000 "
                                 "filas (tamaño de 202006); 63 hojas; 4 hilos; sin conversión de datos.")
    del X

    if not a.sin_punta_a_punta:
        nombre = f"t01_{out.name}"
        modelo_dir = out / "modelo"
        modelo_dir.mkdir()
        modelo_con_nombres(e01 / "modelos" / f"binario_{s0}.txt", modelo_dir / "modelo.txt", pred)
        (modelo_dir / "predictores.json").write_text(json.dumps(pred), encoding="utf-8")
        (modelo_dir / "configuracion.json").write_text(json.dumps(
            {"origen": mostrar(e01), "semilla": s0, "objetivo": "binario", "nota": "modelo de E01 para medir tiempos"},
            indent=2), encoding="utf-8")
        py = sys.executable
        subprocess.run([py, "-m", "pipeline_competencia02.entorno", "--nombre", nombre, "--hasta", "201912",
                        "--modelo-desde", str(modelo_dir)], cwd=RAIZ, check=True)
        env = RUTAS.entornos / nombre
        entrada = RUTAS.insumos / f"competencia_02_{MES_ENSAYO}_crudo.csv"
        t = time.perf_counter()
        rc = subprocess.run([py, "-m", "pipeline_competencia02.ejecutar_mes", "--entorno", str(env), "--entrada",
                             str(entrada), "--mes", str(MES_ENSAYO), "--estrategia", "cupo_fijo:1000",
                             "--estrategia", "porcentaje:1", "--principal", "cupo_fijo"], cwd=RAIZ).returncode
        pared = round(time.perf_counter() - t, 1)
        r = json.loads((env / "diagnosticos" / str(MES_ENSAYO) / "reporte.json").read_text(encoding="utf-8")) \
            if rc == 0 else {}
        rep["punta_a_punta"] = {"codigo": rc, "pared_s": pared, "entorno": mostrar(env),
                                "tiempos": r.get("tiempos"), "memoria": r.get("memoria"),
                                "arboles": (r.get("modelo") or {}).get("arboles")}
    (out / "t01.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
