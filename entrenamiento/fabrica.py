"""Fábrica de modelos: entrena un catálogo completo desde la historia de 2019 y el target versión 2, sin reutilizar nada.

Entrada (la arman, en este orden, entrenamiento/legado/02, 03, 04 y experimentos/tc01_target_2019 desde el dataset del
curso): las features de 2019 (RUTAS.features_2019) y el target versión 2 (RUTAS.target_2019_v2). De cada catálogo
versionado (catalogo/estrategias_<nombre>.json) se toman las estrategias, las semillas, los hiperparámetros, las
rondas y los cortes del equipo: la fábrica no decide nada, solo rehace los modelos (diseño, decisión 10).

Entrenamiento igual al de TC01/CE02 (experimentos/ce02_entrenar.py): train 201903–201906, un Dataset binado por
objetivo (max_bin y data_random_seed del catálogo), `deterministic=True`, una semilla por modelo. El modelo se guarda
con los nombres de las 760 features. Como es determinista, el sha256 de cada modelo se compara con el del catálogo
del equipo: si coincide, es el mismo modelo; si no, queda anotado (tarea 3.4 compara las métricas).

Reanudable por modelo: cada modelo se escribe aparte y se renombra al terminar; al relanzar, los modelos que ya
están no se reentrenan. Un modelo compartido por dos catálogos (ce02 y ce02_b20m10) se entrena una sola vez.

Salida, en RUTAS.modelos (o --modelos):
  <archivo de cada modelo, como en el catálogo>   p. ej. binario_ce02_20s/semilla_20261124.txt
  estrategias_<nombre>.json                       el catálogo con el sha256 de los modelos fabricados; es el que se
                                                  usa con `preparar_ejecucion --catalogo <esta ruta>`
  fabrica_<nombre>.json                           modelo por modelo: sha256 obtenido y del equipo, tiempo, versiones
Con --subir, la carpeta se copia a gs://<bucket>/catalogo/<nombre>/ (gcloud storage rsync).

Uso: python -m entrenamiento.fabrica --catalogo ce02 [--hilos 8] [--modelos DIR] [--subir]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

import duckdb
import lightgbm as lgb
import numpy as np

from evaluacion import particiones as P
from pipeline_competencia02 import catalogo as K
from pipeline_competencia02.config import RUTAS, mostrar

CLASES = {"CONTINUA": 0, "BAJA+1": 1, "BAJA+2": 2}
BUCKET = os.environ.get("DMEYF_BUCKET", "gs://agustinarazanov_buckito2026")
LOTE = 100
ULTIMO_MES_PERMITIDO = 201912   # CONSIGNA R1: estrategias y modelos solo con 201901–201912


class MesNoPermitido(ValueError):
    pass


def comprobar_meses(meses) -> tuple[int, ...]:
    """Candado de la fábrica: ningún mes posterior a 201912 entra al entrenamiento. Corre antes de leer nada."""
    meses = tuple(int(m) for m in meses)
    fuera = [m for m in meses if m > ULTIMO_MES_PERMITIDO]
    if fuera:
        raise MesNoPermitido(f"meses posteriores a {ULTIMO_MES_PERMITIDO} en la configuración: {fuera}")
    return meses


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def cargar_entrenamiento(predictores: list[str], meses=P.ENTRENAMIENTO) -> tuple[np.ndarray, np.ndarray]:
    """X (float64, NULL -> NaN) y clase (0, 1, 2) de los meses (201903–201906), ordenados por mes y cliente."""
    meses = comprobar_meses(meses)
    feats = ", ".join(f"'{(RUTAS.features_2019 / f'features_{m}.parquet').as_posix()}'" for m in meses)
    con = duckdb.connect()
    try:
        tgt = P.leer_target(con, RUTAS.target_2019_v2.as_posix(), meses).df()  # control de meses: antes de leer
        con.execute(f"CREATE TEMP VIEW f AS SELECT * FROM read_parquet([{feats}])")
        con.register("tgt_df", tgt)
        con.execute("CREATE TEMP TABLE j AS SELECT f.numero_de_cliente, f.foto_mes, tgt_df.clase_ternaria, "
                    "row_number() OVER (ORDER BY f.foto_mes, f.numero_de_cliente) - 1 AS fila "
                    "FROM f JOIN tgt_df USING (numero_de_cliente, foto_mes)")
        n_f = con.execute("SELECT count(*) FROM f").fetchone()[0]
        n, nulos = con.execute("SELECT count(*), count(*) FILTER (WHERE clase_ternaria IS NULL) FROM j").fetchone()
        if n != n_f or nulos:
            raise RuntimeError(f"features {n_f} filas, con target {n}, target nulo {nulos}")
        clase = np.array([CLASES[c] for c in con.execute("SELECT clase_ternaria FROM j ORDER BY fila")
                          .fetchnumpy()["clase_ternaria"]], dtype="int8")
        X = np.empty((n, len(predictores)), dtype="float64")
        for i in range(0, len(predictores), LOTE):
            cols = predictores[i:i + LOTE]
            sel = ", ".join(f'CAST(f."{c}" AS DOUBLE) AS "{c}"' for c in cols)
            df = con.execute(f"SELECT {sel} FROM f JOIN j USING (numero_de_cliente, foto_mes) ORDER BY j.fila").df()
            X[:, i:i + len(cols)] = df.to_numpy(dtype="float64", na_value=np.nan)
        return X, clase
    finally:
        con.close()


def parametros(base: dict, semilla: int, objetivo: str, num_class: int | None, hilos: int) -> dict:
    p = {**base, "seed": semilla, "num_threads": hilos, "objective": objetivo}
    if objetivo == "multiclass":
        p["num_class"] = num_class
    return p


def plan(cat: dict) -> list[dict]:
    """Un renglón por modelo distinto del catálogo, en el orden del catálogo."""
    out, vistos = [], set()
    for e in cat["estrategias"]:
        for m in e["modelos"]:
            if m["archivo"] in vistos:
                continue
            vistos.add(m["archivo"])
            out.append({"estrategia": e["id"], "objetivo": e["objetivo"], "num_class": e.get("num_class"),
                        "params": e["params"], "rondas": e["rondas"], "semilla": m["semilla"],
                        "archivo": m["archivo"], "sha256_equipo": m["sha256"]})
    return out


def entrenar(renglones: list[dict], X: np.ndarray, clase: np.ndarray, predictores: list[str], destino: Path,
             hilos: int, al_terminar: Callable[[dict], None] | None = None) -> list[dict]:
    """Entrena los modelos que faltan en `destino`; los que ya están se dejan como están (reanudar)."""
    faltan = [r for r in renglones if not (destino / r["archivo"]).exists()]
    datasets: dict = {}
    for r in faltan:  # un Dataset binado por objetivo, solo si hace falta entrenar alguno
        clave = (r["objetivo"], r["params"].get("max_bin"), r["params"].get("data_random_seed"))
        if clave not in datasets:
            etiqueta = (clase > 0).astype("int8") if r["objetivo"] == "binary" else clase
            datasets[clave] = lgb.Dataset(X, label=etiqueta, feature_name=predictores, free_raw_data=False,
                                          params={"max_bin": clave[1], "data_random_seed": clave[2],
                                                  "verbosity": -1}).construct()
    hechos = []
    for r in renglones:
        ruta = destino / r["archivo"]
        info = {**r}
        if ruta.exists():
            info["origen"] = "reanudado"
        else:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            clave = (r["objetivo"], r["params"].get("max_bin"), r["params"].get("data_random_seed"))
            t = time.perf_counter()
            b = lgb.train(parametros(r["params"], r["semilla"], r["objetivo"], r["num_class"], hilos),
                          datasets[clave], num_boost_round=r["rondas"])
            tmp = ruta.with_name(ruta.name + f".tmp-{os.getpid()}")
            b.save_model(str(tmp))
            os.replace(tmp, ruta)
            info.update({"origen": "fabrica", "entrenar_s": round(time.perf_counter() - t, 1)})
        info["sha256"] = sha256(ruta)
        info["igual_al_equipo"] = info["sha256"] == r["sha256_equipo"]
        hechos.append(info)
        if al_terminar:
            al_terminar(info)
    return hechos


def manifiesto(cat: dict, hechos: list[dict], nombre: str) -> dict:
    """El catálogo del equipo con el sha256 de los modelos fabricados."""
    sha = {h["archivo"]: h["sha256"] for h in hechos}
    out = json.loads(json.dumps(cat))
    for e in out["estrategias"]:
        for m in e["modelos"]:
            m["sha256_equipo"] = m["sha256"]
            m["sha256"] = sha[m["archivo"]]
            m["entrenado_en"] = "fábrica (entrenamiento.fabrica)"
    out["fabrica"] = {"catalogo_del_equipo": mostrar(K.archivo(nombre)), "todos_iguales_al_equipo":
                      all(h["igual_al_equipo"] for h in hechos), "fabricado": time.strftime("%Y-%m-%dT%H:%M:%S")}
    return out


def subir(destino: Path, nombre: str) -> str:
    url = f"{BUCKET}/catalogo/{nombre}/"
    subprocess.run(["gcloud", "storage", "rsync", "--recursive", str(destino), url], check=True)
    return url


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Entrena un catálogo completo desde la historia de 2019 (fábrica).")
    ap.add_argument("--catalogo", choices=sorted(K.CATALOGOS), required=True)
    ap.add_argument("--hilos", type=int, default=8)
    ap.add_argument("--modelos", type=Path, default=RUTAS.modelos, help="carpeta de los modelos (RUTAS.modelos)")
    ap.add_argument("--meses", type=int, nargs="+", default=list(P.ENTRENAMIENTO),
                    help="meses de entrenamiento (por defecto 201903–201906; nunca posteriores a 201912)")
    ap.add_argument("--subir", action="store_true", help=f"copiar la carpeta a {BUCKET}/catalogo/<nombre>/")
    a = ap.parse_args(argv)
    meses = comprobar_meses(a.meses)  # antes de leer ningún dato
    cat = K.cargar(K.archivo(a.catalogo))
    if cat.get("target_version") != 2:
        raise SystemExit(f"{a.catalogo}: la fábrica entrena con el target versión 2")
    # tc01 no guarda el target en su catálogo: es el del resumen versionado de experimentos/tc01_target_2019
    sha_target = (cat.get("target") or {}).get("sha256") or json.loads(
        (K.RAIZ / "resultados" / "tc01_target_2019_v2.json").read_text(encoding="utf-8"))["salida"]["sha256"]
    predictores = [c for c, _ in json.loads(K.PREDICTORES.read_text(encoding="utf-8"))["predictores"]]
    destino = a.modelos.resolve()
    destino.mkdir(parents=True, exist_ok=True)
    renglones = plan(cat)
    t0 = time.perf_counter()
    rep = {"catalogo": a.catalogo, "inicio": time.strftime("%Y-%m-%dT%H:%M:%S"), "modelos": len(renglones),
           "destino": mostrar(destino), "hilos": a.hilos, "meses": list(meses),
           "entradas": {"features_2019": mostrar(RUTAS.features_2019),
                        "target_2019_v2": {"archivo": mostrar(RUTAS.target_2019_v2),
                                           "sha256": sha256(RUTAS.target_2019_v2),
                                           "sha256_equipo": sha_target}},
           "maquina": {"plataforma": platform.platform(), "python": platform.python_version(),
                       "lightgbm": lgb.__version__, "duckdb": duckdb.__version__, "numpy": np.__version__,
                       "cpu": os.cpu_count()}}
    if rep["entradas"]["target_2019_v2"]["sha256"] != sha_target:
        raise SystemExit("el target versión 2 no es el del catálogo; rehacerlo con experimentos.tc01_target_2019")
    faltan = sum(not (destino / r["archivo"]).exists() for r in renglones)
    print(f"{a.catalogo}: {len(renglones)} modelos, {faltan} por entrenar, en {destino}", flush=True)
    if faltan:
        t = time.perf_counter()
        X, clase = cargar_entrenamiento(predictores, meses)
        rep["carga_s"] = round(time.perf_counter() - t, 1)
        rep["clases_train"] = {k: int((clase == v).sum()) for k, v in CLASES.items()}
    else:
        X = clase = None

    def avisar(info: dict):
        print(f"  {info['archivo']}: {info['origen']} {info.get('entrenar_s', '')} "
              f"{'= equipo' if info['igual_al_equipo'] else '≠ equipo'}", flush=True)

    hechos = entrenar(renglones, X, clase, predictores, destino, a.hilos, avisar)
    rep["resultado"] = hechos
    rep["iguales_al_equipo"] = sum(h["igual_al_equipo"] for h in hechos)
    man = manifiesto(cat, hechos, a.catalogo)
    (destino / f"estrategias_{a.catalogo}.json").write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n",
                                                           encoding="utf-8")
    rep["segundos"] = round(time.perf_counter() - t0, 1)
    if a.subir:
        rep["bucket"] = subir(destino, a.catalogo)
    (destino / f"fabrica_{a.catalogo}.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n",
                                                       encoding="utf-8")
    print(f"listo en {rep['segundos']} s: {rep['iguales_al_equipo']}/{len(hechos)} iguales al equipo; "
          f"catálogo {mostrar(destino / f'estrategias_{a.catalogo}.json')}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
