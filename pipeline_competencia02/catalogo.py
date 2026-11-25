"""Catálogo de estrategias del pipeline mensual, armado a partir de modelos ya entrenados.

Catálogos (CATALOGOS), cada uno con un binario y un multiclase de peso 1, 5 semillas, 300 rondas, sin optimización:
  e01   catalogo/estrategias.json       modelos de E01, target versión 1 (experimento_sampling/03). Se conserva.
  tc01  catalogo/estrategias_tc01.json  modelos de TC01, target versión 2 (evaluacion/target.py). ACTIVO.
Roles: binario = RECOMENDACIÓN PROVISIONAL, score P(BAJA+1 ∪ BAJA+2); multiclase = ALTERNATIVA, score P(BAJA+2).
En tc01 los roles salen de la decisión registrada en su resumen (regla de E02 aplicada a los modelos corregidos).

Cada estrategia = 5 modelos (una semilla cada uno) + promedio de probabilidades + corte por fracción
de clientes. La fracción se lee del resumen versionado del experimento: resultados.<brazo>.corte.fraccion
(e01: resultados/e02_peso_baja1.json, que reproduce E01 exactamente; tc01: resultados/tc01_target_corregido.json).

Los modelos de E01 se guardaron sin nombres de features. Acá se copian con la línea `feature_names`
reemplazada (en bytes, sin tocar los árboles) y se verifica que la copia prediga exactamente igual.
Las copias van a RUTAS.modelos/<id>/ (fuera del repo). El índice versionado es catalogo/estrategias.json
y la lista ordenada de predictores con sus tipos es catalogo/predictores.json.

Uso: python -m pipeline_competencia02.catalogo --catalogo tc01 --modelos-de ejecuciones/tc01/<marca>
     python -m pipeline_competencia02.catalogo --catalogo e01 --modelos-de ejecuciones/e01/<marca>
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

CATALOGO = RAIZ / "catalogo" / "estrategias.json"  # e01 (se conserva)
PREDICTORES = RAIZ / "catalogo" / "predictores.json"
RESUMEN_E02 = RAIZ / "resultados" / "e02_peso_baja1.json"
CATALOGOS = {
    "e01": {"archivo": CATALOGO, "resumen": RESUMEN_E02, "sufijo": "e01", "target_version": 1,
            "candidato": "300 rondas, sin optimización (E01)",
            "estado": ("candidatos de E01: 300 rondas, hiperparámetros fijos, sin optimización; target versión 1 "
                       "(experimento_sampling/03); la recomendación es provisional (PLAN_PRUEBAS.md § 5 y § 8)")},
    "tc01": {"archivo": RAIZ / "catalogo" / "estrategias_tc01.json",
             "resumen": RAIZ / "resultados" / "tc01_target_corregido.json", "sufijo": "tc01", "target_version": 2,
             "candidato": "300 rondas, sin optimización (TC01 = E01 con target versión 2)",
             "estado": ("candidatos de TC01: misma configuración que E01 reentrenada con el target versión 2 "
                        "(evaluacion/target.py); la recomendación es provisional (PLAN_PRUEBAS.md § 9 y § 10)")},
}
ACTIVO = "tc01"
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


def archivo(nombre: str | None = None) -> Path:
    return CATALOGOS[nombre or ACTIVO]["archivo"]


def construir(e01: Path, nombre: str = "e01") -> dict:
    """e01 = carpeta del experimento con modelos/<objetivo>_<semilla>.txt y resultados.json (E01 o TC01)."""
    spec = CATALOGOS[nombre]
    cfg01 = json.loads((e01 / "resultados.json").read_text(encoding="utf-8"))
    resumen = json.loads(spec["resumen"].read_text(encoding="utf-8"))
    origen = resumen.get("origen_modelos", resumen.get("e01"))
    if Path(origen).name != e01.name:
        raise ValueError(f"el resumen {spec['resumen'].name} corresponde a {origen}, no a {e01}")
    if not resumen["compatibilidad_e01"]["compatible"] or not all(resumen.get("checks", {}).values()):
        raise ValueError("el resumen no verificó la compatibilidad con E01 o tiene comprobaciones fallidas")
    recomendado = resumen.get("decision", {}).get("recomendacion", "binario")
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
    cat = {"version": 1, "nombre": nombre, "creado": time.strftime("%Y-%m-%dT%H:%M:%S"), "estado": spec["estado"],
           "target_version": spec["target_version"],
           "origen": {"modelos_de": mostrar(e01), "resumen": spec["resumen"].relative_to(RAIZ).as_posix(),
                      "resumen_sha256": sha256(spec["resumen"])},
           "features": {"definicion": DEFINICION_FEATURES, "n": len(pred), "sha256_nombres": sha_lista(pred),
                        "archivo": PREDICTORES.relative_to(RAIZ).as_posix(),
                        "lags": "por fila (k-ésima observación previa), NO por calendario"},
           "promedio": "media aritmética de las probabilidades de las semillas, en el orden de 'modelos'",
           "orden_y_desempate": "probabilidad descendente; a igual probabilidad, numero_de_cliente ascendente",
           "estrategias": []}
    for e0 in ESTRATEGIAS:
        e = {**e0, "id": e0["id"].replace("_e01_", f"_{spec['sufijo']}_"),
             "rol": "recomendacion_provisional" if e0["brazo_e02"] == recomendado else "alternativa"}
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
            "candidato": spec["candidato"], "target_version": spec["target_version"],
            "params": cfg01["params"], "rondas": cfg01["rondas"],
            "corte": {"tipo": "fraccion_clientes", "fraccion": brazo["corte"]["fraccion"],
                      "redondeo": "techo(fraccion · n) (evaluacion.ganancia.envios)",
                      "fuente": f"{spec['resumen'].relative_to(RAIZ).as_posix()} → resultados.{e['brazo_e02']}.corte.fraccion",
                      "elegido_con": "201908 y 201909 (menor arrepentimiento máximo del ensamble)"},
            "modelos": modelos})
    if sorted(x["rol"] for x in cat["estrategias"]) != ["alternativa", "recomendacion_provisional"]:
        raise ValueError("el catálogo debe tener una recomendación y una alternativa")
    spec["archivo"].write_text(json.dumps(cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return cat


def cargar(path: Path | None = None) -> dict:
    return json.loads(Path(path or archivo()).read_text(encoding="utf-8"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Arma un catálogo de estrategias desde los modelos de un experimento.")
    ap.add_argument("--catalogo", choices=sorted(CATALOGOS), default=ACTIVO)
    ap.add_argument("--modelos-de", "--e01", dest="modelos_de", type=Path, required=True)
    a = ap.parse_args(argv)
    cat = construir(a.modelos_de.resolve(), a.catalogo)
    for e in cat["estrategias"]:
        print(e["id"], e["rol"], e["corte"]["fraccion"], [m["sha256"][:12] for m in e["modelos"]])
    print(f"catálogo: {mostrar(CATALOGOS[a.catalogo]['archivo'])}; modelos en {RUTAS.modelos}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
