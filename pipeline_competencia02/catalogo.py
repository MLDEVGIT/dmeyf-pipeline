"""Catálogo de estrategias del pipeline mensual, armado a partir de modelos ya entrenados.

Hoy contiene los dos candidatos de E01 (docs/PLAN_PRUEBAS.md § 5 y § 8):
  binario_e01_300r        RECOMENDACIÓN PROVISIONAL. Score = P(BAJA+1 ∪ BAJA+2) (objetivo binario).
  multiclase_p1_e01_300r  ALTERNATIVA. Score = P(BAJA+2) (columna 2 del multiclase; BAJA+1 con peso 1).
Los dos son candidatos de 300 rondas con hiperparámetros fijos, **sin optimización** (E01).

Cada estrategia = 5 modelos (una semilla cada uno) + promedio de probabilidades + corte por fracción
de clientes. La fracción se lee del resumen versionado de E02 (que reproduce E01 exactamente):
resultados/e02_peso_baja1.json → resultados.<brazo>.corte.fraccion.

Los modelos de E01 se guardaron sin nombres de features. Acá se copian con la línea `feature_names`
reemplazada (en bytes, sin tocar los árboles) y se verifica que la copia prediga exactamente igual.
Las copias van a RUTAS.modelos/<id>/ (fuera del repo). El índice versionado es catalogo/estrategias.json
y la lista ordenada de predictores con sus tipos es catalogo/predictores.json.

Uso: python -m pipeline_competencia02.catalogo --e01 ejecuciones/e01/<marca>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import duckdb
import lightgbm as lgb
import numpy as np

from .config import RAIZ, RUTAS, mostrar

CATALOGO = RAIZ / "catalogo" / "estrategias.json"
PREDICTORES = RAIZ / "catalogo" / "predictores.json"
RESUMEN_E02 = RAIZ / "resultados" / "e02_peso_baja1.json"
DEFINICION_FEATURES = ("152 variables crudas + lag1, delta1, lag2, delta2 de cada una (760). lag_k = k-ésima observación "
                       "previa del cliente (por fila, ordenado por foto_mes); delta_k = x − lag_k. Sin imputaciones. "
                       "Igual a experimento_sampling/04 y pipeline_competencia02/features.py.")
ESTRATEGIAS = [
    {"id": "binario_e01_300r", "rol": "recomendacion_provisional", "brazo_e02": "binario", "archivo_e01": "binario",
     "objetivo": "binary", "columna_score": None,
     "score": "P(BAJA+1 ∪ BAJA+2): probabilidad del objetivo binario del baseline 208135 (positivo = BAJA+1 o BAJA+2)"},
    {"id": "multiclase_p1_e01_300r", "rol": "alternativa", "brazo_e02": "multiclase_p1", "archivo_e01": "multiclase",
     "objetivo": "multiclass", "columna_score": 2,
     "score": "P(BAJA+2): columna 2 del multiclase CONTINUA/BAJA+1/BAJA+2 (BAJA+1 con peso 1)"},
]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def sha_lista(nombres: list[str]) -> str:
    return hashlib.sha256("\n".join(nombres).encode("utf-8")).hexdigest()


def copiar_con_nombres(origen: Path, destino: Path, pred: list[str]) -> None:
    """Copia el modelo reemplazando sólo la línea feature_names (bytes: evita \\r\\n en Windows) y verifica."""
    lineas = origen.read_bytes().split(b"\n")
    if sum(1 for l in lineas if l.startswith(b"feature_names=")) != 1:
        raise RuntimeError(f"{origen}: se esperaba exactamente una línea feature_names")
    nombres = b"feature_names=" + " ".join(pred).encode("ascii")
    destino.write_bytes(b"\n".join(nombres if l.startswith(b"feature_names=") else l for l in lineas))
    a, b = lgb.Booster(model_file=str(origen)), lgb.Booster(model_file=str(destino))
    X = np.random.default_rng(0).normal(size=(500, len(pred)))
    X[::7, ::5] = np.nan
    if a.num_trees() != b.num_trees() or b.feature_name() != pred or not np.array_equal(a.predict(X), b.predict(X)):
        raise RuntimeError(f"la copia de {origen.name} no conserva árboles, nombres o predicciones")


def construir(e01: Path) -> dict:
    cfg01 = json.loads((e01 / "resultados.json").read_text(encoding="utf-8"))
    resumen = json.loads(RESUMEN_E02.read_text(encoding="utf-8"))
    if Path(resumen["e01"]).name != e01.name:
        raise ValueError(f"el resumen de E02 corresponde a {resumen['e01']}, no a {e01}")
    if not resumen["compatibilidad_e01"]["compatible"]:
        raise ValueError("E02 no verificó la compatibilidad con E01")
    pred = json.loads((RUTAS.features_2019 / "manifiesto.json").read_text(encoding="utf-8"))["predictores"]
    con = duckdb.connect()
    tipos = {c: t for c, t, *_ in con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{(RUTAS.features_2019 / 'features_201908.parquet').as_posix()}')").fetchall()}
    con.close()
    PREDICTORES.parent.mkdir(exist_ok=True)
    lista = [[c, tipos[c]] for c in pred]
    PREDICTORES.write_text(json.dumps({"definicion": DEFINICION_FEATURES, "sha256_nombres": sha_lista(pred),
                                       "predictores": lista}, indent=1, ensure_ascii=False) + "\n",
                           encoding="utf-8", newline="\n")
    cat = {"version": 1, "creado": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "estado": ("candidatos de E01: 300 rondas, hiperparámetros fijos, sin optimización; "
                      "la recomendación es provisional (PLAN_PRUEBAS.md § 5 y § 8)"),
           "origen": {"e01": mostrar(e01), "resumen": RESUMEN_E02.relative_to(RAIZ).as_posix(),
                      "resumen_sha256": sha256(RESUMEN_E02)},
           "features": {"definicion": DEFINICION_FEATURES, "n": len(pred), "sha256_nombres": sha_lista(pred),
                        "archivo": PREDICTORES.relative_to(RAIZ).as_posix(),
                        "lags": "por fila (k-ésima observación previa), NO por calendario"},
           "promedio": "media aritmética de las probabilidades de las semillas, en el orden de 'modelos'",
           "orden_y_desempate": "probabilidad descendente; a igual probabilidad, numero_de_cliente ascendente",
           "estrategias": []}
    for e in ESTRATEGIAS:
        brazo = resumen["resultados"][e["brazo_e02"]]
        destino = RUTAS.modelos / e["id"]
        destino.mkdir(parents=True, exist_ok=True)
        modelos = []
        for s in cfg01["semillas"]:
            origen = e01 / "modelos" / f"{e['archivo_e01']}_{s}.txt"
            copia = destino / f"semilla_{s}.txt"
            copiar_con_nombres(origen, copia, pred)
            b = lgb.Booster(model_file=str(copia))
            modelos.append({"semilla": s, "archivo": f"{e['id']}/{copia.name}", "sha256": sha256(copia),
                            "origen": mostrar(origen), "sha256_origen": sha256(origen),
                            "rondas": b.current_iteration(), "arboles": b.num_trees()})
        cat["estrategias"].append({
            **{k: e[k] for k in ("id", "rol", "objetivo", "columna_score", "score")},
            "num_class": 3 if e["objetivo"] == "multiclass" else None,
            "candidato": "300 rondas, sin optimización (E01)",
            "params": cfg01["params"], "rondas": cfg01["rondas"],
            "corte": {"tipo": "fraccion_clientes", "fraccion": brazo["corte"]["fraccion"],
                      "redondeo": "techo(fraccion · n) (evaluacion.ganancia.envios)",
                      "fuente": f"{RESUMEN_E02.relative_to(RAIZ).as_posix()} → resultados.{e['brazo_e02']}.corte.fraccion "
                                f"(= E01, PLAN_PRUEBAS.md § 5)",
                      "elegido_con": "201908 y 201909 (menor arrepentimiento máximo del ensamble)"},
            "modelos": modelos})
    CATALOGO.write_text(json.dumps(cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return cat


def cargar(path: Path = CATALOGO) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Arma el catálogo de estrategias desde los modelos de E01.")
    ap.add_argument("--e01", type=Path, required=True)
    a = ap.parse_args(argv)
    cat = construir(a.e01.resolve())
    for e in cat["estrategias"]:
        print(e["id"], e["rol"], e["corte"]["fraccion"], [m["sha256"][:12] for m in e["modelos"]])
    print(f"catálogo: {mostrar(CATALOGO)}; modelos en {RUTAS.modelos}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
