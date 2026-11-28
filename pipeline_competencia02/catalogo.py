"""Catálogo de estrategias del pipeline mensual, armado a partir de modelos ya entrenados.

Catálogos (CATALOGOS), cada uno con un binario y un multiclase de peso 1, 300 rondas, sin optimización:
  e01          catalogo/estrategias.json             E01, 5 semillas, target versión 1 (experimento_sampling/03). Se conserva.
  tc01         catalogo/estrategias_tc01.json        TC01, 5 semillas, target versión 2 (evaluacion/target.py). ACTIVO.
  ce02         catalogo/estrategias_ce02.json        CE02, 20 + 20 semillas, cortes MVE 2,35 % / 2,725 %. CANDIDATO.
  ce02_b20m10  catalogo/estrategias_ce02_b20m10.json CE02, binario 20 + multiclase 10 (semillas 0–9). Respaldo de tiempo.
Roles: binario = RECOMENDACIÓN PROVISIONAL, score P(BAJA+1 ∪ BAJA+2); multiclase = ALTERNATIVA, score P(BAJA+2).
En tc01 los roles salen de la decisión registrada en su resumen (regla de E02 aplicada a los modelos corregidos);
CE02 no los reevaluó y los conserva.

Cada estrategia = N modelos (una semilla cada uno) + promedio de probabilidades + corte por fracción de clientes.
La fracción se lee del resumen versionado del experimento:
  e01, tc01: resultados.<brazo>.corte.fraccion (minimax; e01: resultados/e02_peso_baja1.json, que reproduce E01;
             tc01: resultados/tc01_target_corregido.json);
  ce02*:     recomendacion.<brazo>.corte_recomendado de resultados/ce02_ensambles_20.json (mínimo volumen equivalente
             del ensamble de 20, PLAN_PRUEBAS.md § 13–14). El minimax queda registrado al lado (binario 3,675 %).
Las semillas de ce02* son un prefijo de la lista registrada antes de entrenar (resultados/ce02_composicion.json,
ensambles anidados): 20 = índices 0–19, 10 = índices 0–9.

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
    "ce02": {"archivo": RAIZ / "catalogo" / "estrategias_ce02.json",
             "resumen": RAIZ / "resultados" / "ce02_ensambles_20.json", "sufijo": "ce02", "target_version": 2,
             "semillas": {"binario": 20, "multiclase_p1": 20},
             "candidato": "300 rondas, sin optimización (CE02: ensamble de 20 semillas, target versión 2)",
             "estado": ("CANDIDATO, no activo: 20 semillas por objetivo y cortes por mínimo volumen equivalente "
                        "(CE02, PLAN_PRUEBAS.md § 13–15); la recomendación es provisional")},
    "ce02_b20m10": {"archivo": RAIZ / "catalogo" / "estrategias_ce02_b20m10.json",
                    "resumen": RAIZ / "resultados" / "ce02_ensambles_20.json", "sufijo": "ce02", "target_version": 2,
                    "semillas": {"binario": 20, "multiclase_p1": 10},
                    "candidato": "300 rondas, sin optimización (CE02: binario 20 semillas, multiclase 10)",
                    "estado": ("RESPALDO DE TIEMPO, no activo: binario de 20 semillas y multiclase de 10 (semillas "
                               "0–9), cortes de CE02; se mide sólo si el de 20 + 20 no entra en el tiempo del vivo "
                               "(PLAN_PRUEBAS.md § 15)")},
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


def corte_minimax(resumen: dict, brazo: str, spec: dict) -> dict:
    return {"fraccion": resumen["resultados"][brazo]["corte"]["fraccion"],
            "fuente": f"{spec['resumen'].relative_to(RAIZ).as_posix()} → resultados.{brazo}.corte.fraccion",
            "elegido_con": "201908 y 201909 (menor arrepentimiento máximo del ensamble)"}


def corte_ce02(resumen: dict, brazo: str, spec: dict) -> dict:
    r = resumen["recomendacion"][brazo]
    if r["tamano_recomendado"] != "20" or r["procedimiento"] != "MVE":
        raise ValueError(f"CE02 no recomendó 20 semillas con MVE para {brazo}: {r}")
    g = resumen["ganancia_y_corte"][brazo]
    extra = {} if spec["semillas"][brazo] == 20 else {
        "nota_tamano": (f"corte elegido sobre el ensamble de 20 y aplicado al de {spec['semillas'][brazo]}: en CE02 "
                        "el corte del multiclase es estable con cualquier tamaño (2,7–3,0 %); configuración sólo "
                        "para medir tiempo")}
    return {"fraccion": r["corte_recomendado"], **extra,
            "procedimiento": ("mínimo volumen equivalente (MVE) del ensamble de 20: la menor fracción cuyo peor "
                              "arrepentimiento entre 201908 y 201909 queda a τ₂₀ del mínimo; elegido por el criterio "
                              "de robustez ante una reducción simulada de BAJA+2 (PLAN_PRUEBAS.md § 11, § 13 y § 14)"),
            "minimax_ensamble_20": r["corte_minimax"], "minimax_ensamble_5": g["minimax"]["5"],
            "nota_minimax": "el minimax original del ensamble de 20 da la fracción minimax_ensamble_20; no es la usada",
            "tau_20": r["tau"], "tramos_equivalentes_20": g["conjunto_equivalente_20"]["tramos"],
            "arrepentimiento_rho_0_33": r["arrepentimiento_rho_0_33"],
            "fuente": f"{spec['resumen'].relative_to(RAIZ).as_posix()} → recomendacion.{brazo}.corte_recomendado",
            "elegido_con": "201908 y 201909 (desarrollo; octubre bloqueado; nada de 2020)"}


def archivo(nombre: str | None = None) -> Path:
    """Catálogo versionado por nombre, o la ruta de un catálogo fabricado (entrenamiento.fabrica)."""
    if nombre and nombre.endswith(".json"):
        return Path(nombre).expanduser().resolve()
    return CATALOGOS[nombre or ACTIVO]["archivo"]


def construir(e01: Path, nombre: str = "e01") -> dict:
    """e01 = carpeta del experimento con modelos/<objetivo>_<semilla>.txt y resultados.json (E01, TC01 o CE02)."""
    spec = CATALOGOS[nombre]
    cfg01 = json.loads((e01 / "resultados.json").read_text(encoding="utf-8"))
    resumen = json.loads(spec["resumen"].read_text(encoding="utf-8"))
    es_ce02 = "semillas" in spec
    origen = resumen["modelos"] if es_ce02 else resumen.get("origen_modelos", resumen.get("e01"))
    if Path(origen).name != e01.name:
        raise ValueError(f"el resumen {spec['resumen'].name} corresponde a {origen}, no a {e01}")
    if es_ce02:
        if not (resumen["verificaciones"]["todas"] and all(cfg01["checks"].values())):
            raise ValueError("CE02 tiene verificaciones o comprobaciones de entrenamiento fallidas")
    elif not resumen["compatibilidad_e01"]["compatible"] or not all(resumen.get("checks", {}).values()):
        raise ValueError("el resumen no verificó la compatibilidad con E01 o tiene comprobaciones fallidas")
    composicion = None
    if es_ce02:
        from experimentos import ce02_composicion as C
        reg = json.loads(C.REGISTRO.read_text(encoding="utf-8"))
        if sha256(C.REGISTRO) != resumen["composicion_sha256"] or reg["semillas"] != cfg01["semillas"]:
            raise ValueError("la composición registrada no coincide con la de CE02")
        composicion = {"registro": C.REGISTRO.relative_to(RAIZ).as_posix(), "sha256": sha256(C.REGISTRO),
                       "tipo": "anidado: prefijo de la lista de semillas registrada antes de entrenar",
                       "por_estrategia": {}}
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
    if es_ce02:
        cat["target"] = {**cfg01["target"], "version": spec["target_version"]}
        cat["composicion"] = composicion
    for e0 in ESTRATEGIAS:
        n_sem = spec["semillas"][e0["brazo_e02"]] if es_ce02 else len(cfg01["semillas"])
        semillas = cfg01["semillas"][:n_sem]
        e = {**e0, "id": (f"{e0['id'].split('_e01_')[0]}_{spec['sufijo']}_{n_sem}s" if es_ce02
                          else e0["id"].replace("_e01_", f"_{spec['sufijo']}_")),
             "rol": "recomendacion_provisional" if e0["brazo_e02"] == recomendado else "alternativa"}
        if es_ce02:
            if reg["composiciones"]["anidados"][str(n_sem)] != list(range(n_sem)):
                raise ValueError(f"el ensamble anidado de {n_sem} no es el prefijo registrado")
            composicion["por_estrategia"][e["id"]] = {"tamano": n_sem, "indices": list(range(n_sem)),
                                                     "semillas": semillas}
        destino = RUTAS.modelos / e["id"]
        destino.mkdir(parents=True, exist_ok=True)
        modelos = []
        for s in semillas:
            origen = e01 / "modelos" / f"{e['archivo_e01']}_{s}.txt"
            copia = destino / f"semilla_{s}.txt"
            copiar_con_nombres(origen, copia, pred)
            b = lgb.Booster(model_file=str(copia))
            modelos.append({"semilla": s, "archivo": f"{e['id']}/{copia.name}", "sha256": sha256(copia),
                            "origen": mostrar(origen), "sha256_origen": sha256(origen),
                            "rondas": b.current_iteration(), "arboles": b.num_trees()})
            if es_ce02:
                modelos[-1]["entrenado_en"] = ("TC01 (copiado byte a byte por CE02)"
                                               if s in cfg01["reutilizadas_de_tc01"] else "CE02")
        corte = (corte_ce02 if es_ce02 else corte_minimax)(resumen, e["brazo_e02"], spec)
        cat["estrategias"].append({
            **{k: e[k] for k in ("id", "rol", "objetivo", "columna_score", "score")},
            "num_class": 3 if e["objetivo"] == "multiclass" else None,
            "candidato": spec["candidato"], "target_version": spec["target_version"],
            "params": cfg01["params"], "rondas": cfg01["rondas"],
            "corte": {"tipo": "fraccion_clientes", "fraccion": corte["fraccion"],
                      "redondeo": "techo(fraccion · n) (evaluacion.ganancia.envios)",
                      **{k: v for k, v in corte.items() if k != "fraccion"}},
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
