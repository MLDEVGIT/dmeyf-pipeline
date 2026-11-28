"""Compara un catálogo fabricado (entrenamiento.fabrica) con el del equipo: sha256 por modelo y, por estrategia, las
métricas del ensamble en 201908 y 201909 contra las versionadas en resultados/ (tarea 3.4 de esqueleto-del-pipeline).

Métricas, iguales a las del equipo (experimentos/e01_binario_vs_multiclase.evaluar_mes y evaluacion/ganancia.py):
AUC de BAJA+2, ganancia máxima de la curva suavizada y el corte minimax entre 201908 y 201909 en la grilla de E01.
Referencia: tc01 -> resultados/tc01_target_corregido.json (ensamble y corte); ce02* -> resultados/ce02_ensambles_20.json
(minimax del ensamble anidado del mismo tamaño). Octubre no se lee (evaluacion/particiones.py).

Uso: python scripts/comparar_fabrica.py --catalogo <RUTAS.modelos>/estrategias_tc01.json [--salida resumen.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import duckdb  # noqa: E402
import lightgbm as lgb  # noqa: E402
import numpy as np  # noqa: E402

from evaluacion import ganancia as G  # noqa: E402
from evaluacion import particiones as P  # noqa: E402
from experimentos.e01_binario_vs_multiclase import FRACCIONES, cargar, evaluar_mes  # noqa: E402
from pipeline_competencia02.config import RUTAS, mostrar  # noqa: E402

BRAZO = {"binary": "binario", "multiclass": "multiclase_p1"}


def referencia(nombre: str, brazo: str, n_semillas: int) -> dict:
    if nombre == "tc01":
        r = json.loads((RAIZ / "resultados" / "tc01_target_corregido.json").read_text(encoding="utf-8"))["resultados"]
        e = r[brazo]["ensamble"]
        return {"fuente": "resultados/tc01_target_corregido.json", "corte_minimax": r[brazo]["corte"]["fraccion"],
                **{m: {"auc_baja2": e[m]["auc_baja2"], "g_max_suav": e[m]["g_max_suav"]} for m in ("201908", "201909")}}
    r = json.loads((RAIZ / "resultados" / "ce02_ensambles_20.json").read_text(encoding="utf-8"))
    return {"fuente": "resultados/ce02_ensambles_20.json",
            "corte_minimax": r["ganancia_y_corte"][brazo]["minimax"].get(str(n_semillas))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalogo", type=Path, required=True, help="estrategias_<nombre>.json de la fábrica")
    ap.add_argument("--hilos", type=int, default=8)
    ap.add_argument("--salida", type=Path)
    a = ap.parse_args(argv)
    cat = json.loads(a.catalogo.read_text(encoding="utf-8"))
    nombre = cat["nombre"]
    raiz_modelos = a.catalogo.parent
    pred = [c for c, _ in json.loads((RAIZ / "catalogo" / "predictores.json").read_text(encoding="utf-8"))["predictores"]]
    con = duckdb.connect()
    dev = {m: cargar(con, (m,), pred, RUTAS.target_2019_v2) for m in P.DESARROLLO}
    con.close()
    out = {"catalogo": mostrar(a.catalogo), "nombre": nombre, "estrategias": []}
    for e in cat["estrategias"]:
        brazo = BRAZO[e["objetivo"]]
        modelos = [{"archivo": m["archivo"], "igual_al_equipo": m["sha256"] == m.get("sha256_equipo", m["sha256"])}
                   for m in e["modelos"]]
        scores = {}
        for m, (X, clase, cli, _) in dev.items():
            ps = []
            for mod in e["modelos"]:
                b = lgb.Booster(model_file=str(raiz_modelos / mod["archivo"]))
                p = b.predict(X, num_threads=a.hilos)
                ps.append(p if e["columna_score"] is None else p[:, e["columna_score"]])
            scores[m] = (np.mean(ps, axis=0), clase, cli)
        ev = {m: evaluar_mes(*v) for m, v in scores.items()}
        fr, _ = G.corte_minimax({m: x["gs"] for m, x in ev.items()}, {m: x["n"] for m, x in ev.items()}, FRACCIONES)
        obtenido = {"corte_minimax": float(fr),
                    **{str(m): {"auc_baja2": x["auc_baja2"], "g_max_suav": x["g_max_suav"]} for m, x in ev.items()}}
        ref = referencia(nombre, brazo, len(e["modelos"]))
        dif = {"corte_minimax": None if ref["corte_minimax"] is None else round(fr - ref["corte_minimax"], 6)}
        for m in ("201908", "201909"):
            if m in ref:
                dif[m] = {k: obtenido[m][k] - ref[m][k] for k in ("auc_baja2", "g_max_suav")}
        out["estrategias"].append({"id": e["id"], "semillas": len(e["modelos"]),
                                   "modelos_iguales_al_equipo": sum(x["igual_al_equipo"] for x in modelos),
                                   "obtenido": obtenido, "referencia": ref, "diferencia": dif})
    texto = json.dumps(out, indent=2, ensure_ascii=False) + "\n"
    if a.salida:
        a.salida.write_text(texto, encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
