"""CA02 — ensayo de ce02_b20m10 (binario de 20 semillas, multiclase de 10). Protocolo: docs/PLAN_PRUEBAS.md § 17.

Dos subcomandos:

  corte      ¿Respalda 2019 el 2,725 % para el multiclase de 10 semillas (0–9)? Usa las predicciones de CE02
             (ejecuciones/ce02/<marca>), 201908 y 201909, target versión 2, y las funciones de CE01/CE02:
             conjunto equivalente del ensamble anidado de 10 con su τ₁₀, minimax₁₀, MVE₁₀, peor arrepentimiento,
             ρ = 0,33, traslado del corte fijo y la regla del § 13 aplicada al tamaño 10. Sin datos de 2020.

  identidad  EXPLORATORIO (2020): compara, mes a mes, las predicciones guardadas de la secuencia ce02_b20m10 con
             las de la secuencia ce02: binario idéntico (semillas, ensamble, envíos, salida oficial) y multiclase
             de 10 idéntico al promedio de las semillas 0–9 guardadas por ce02.

Uso:
  python -m experimentos.ca02_b20m10 corte [--salida resultados/ca02_corte_multiclase_10.json]
  python -m experimentos.ca02_b20m10 identidad --ce02 <carpeta> --b20m10 <carpeta> [--salida <json>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import duckdb
import numpy as np

from evaluacion import ganancia as G
from experimentos import ce01_estabilidad_corte as CE
from experimentos import ce02_analisis as A
from experimentos.ce02_composicion import REGISTRO
from pipeline_competencia02.config import RAIZ, mostrar

CORTE = 0.02725
BRAZO = "multiclase_p1"
N = "10"
RESUMEN_CE02 = RAIZ / "resultados" / "ce02_ensambles_20.json"


# ------------------------------------------------------------------ paso 1: corte (2019)
def corte(salida: Path) -> int:
    ce02 = json.loads(RESUMEN_CE02.read_text(encoding="utf-8"))
    d = RAIZ / ce02["modelos"]
    comp = json.loads(REGISTRO.read_text(encoding="utf-8"))["composiciones"]
    ind = comp["anidados"][N]
    meta = {m: (np.load(d / f"meta_{m}.npz")["clase"], np.load(d / f"meta_{m}.npz")["clientes"]) for m in A.MESES}
    z = np.load(d / f"pred_{BRAZO}.npz")
    P_ = {m: z[str(m)] for m in A.MESES}
    c = A.ens_curvas(P_, meta, ind, True)
    p = A.peor_de(c)
    f_mm = CE.elegir(p, 0.0)
    tau = CE.tau_ruido(c, f_mm)
    f_mve = CE.elegir(p, tau)
    umbral = float(np.nanmin(p) + tau)
    mask = p <= umbral + 1e-15
    peor = lambda f: round(float(p[CE.idx(f)]), 5)  # noqa: E731
    # ρ = 0,33, como en la regla del § 13
    gsr = {m: G.suavizar(A.curva_rho(c[m]["g"], 0.33)) for m in A.MESES}
    arr33 = lambda f: {str(m): round(float(1 - gsr[m][G.envios(f, c[m]["n"]) - 1] / np.nanmax(gsr[m])), 5)  # noqa: E731
                       for m in A.MESES}
    a_mm, a_mve = arr33(f_mm), arr33(f_mve)
    usar_mve = any(a_mm[m] - a_mve[m] > tau for m in a_mm)
    fijo = {}
    for m in A.MESES:
        x = c[m]
        k = G.envios(CORTE, x["n"])
        fijo[str(m)] = {"envios": k, "ganancia": A.M(x["g"][k - 1]), "ganancia_suav": A.M(x["gs"][k - 1]),
                        "max_suav": A.M(np.nanmax(x["gs"])),
                        "arrepentimiento": round(float(1 - x["gs"][k - 1] / np.nanmax(x["gs"])), 5)}
    registrado = ce02["ganancia_y_corte"][BRAZO]["anidados"][N]
    dentro = bool(mask[CE.idx(CORTE)])
    res = {"experimento": "CA02 paso 1: respaldo del corte multiclase de 2,725 % con las semillas 0–9",
           "datos": "201908 y 201909 (desarrollo), target versión 2; octubre bloqueado; sin 2020",
           "fuente": {"predicciones": mostrar(d), "composicion": mostrar(REGISTRO), "resumen_ce02": mostrar(RESUMEN_CE02),
                      "indices": ind, "semillas": [json.loads(REGISTRO.read_text(encoding="utf-8"))["semillas"][i]
                                                   for i in ind]},
           "corte_evaluado": CORTE,
           "minimax_10": f_mm, "tau_10": tau, "mve_10": f_mve,
           "conjunto_equivalente_10": {"umbral_peor_arrepentimiento": round(umbral, 5), "tramos": CE.tramos(mask)},
           "peor_arrepentimiento": {"corte_evaluado": peor(CORTE), "mve_10": peor(f_mve), "minimax_10": peor(f_mm)},
           "arrepentimiento_rho_0_33": {"corte_evaluado": arr33(CORTE), "mve_10": a_mve, "minimax_10": a_mm},
           "regla_s13_tamano_10": {"usar_mve": usar_mve, "corte": f_mve if usar_mve else f_mm,
                                   "procedimiento": "MVE" if usar_mve else "minimax"},
           "corte_fijo_por_mes": fijo,
           "consistencia_con_ce02": {"minimax_10": registrado["fraccion_minimax"] == f_mm,
                                     "tau_10": abs(registrado["tau"] - tau) < 1e-12, "mve_10": registrado["mve"] == f_mve},
           "criterio": "respaldado si el corte evaluado cae dentro del conjunto equivalente del ensamble de 10 "
                       "(peor arrepentimiento <= minimo + tau_10), PLAN_PRUEBAS.md § 17",
           "respaldado": dentro}
    salida.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: res[k] for k in ("minimax_10", "tau_10", "mve_10", "conjunto_equivalente_10",
                                           "peor_arrepentimiento", "arrepentimiento_rho_0_33", "regla_s13_tamano_10",
                                           "corte_fijo_por_mes", "consistencia_con_ce02", "respaldado")},
                     ensure_ascii=False, indent=1))
    return 0 if all(res["consistencia_con_ce02"].values()) else 1


# ------------------------------------------------------------------ paso 2: identidad con ce02 (2020, exploratorio)
def leer_pred(env: Path, mes: int) -> dict:
    p = (env / "diagnosticos" / str(mes) / f"predicciones_{mes}.parquet").as_posix()
    return duckdb.connect().execute(f"SELECT * FROM read_parquet('{p}') ORDER BY numero_de_cliente").fetchnumpy()


def leer_dec(env: Path, mes: int) -> dict:
    p = (env / "diagnosticos" / str(mes) / f"decisiones_{mes}.csv").as_posix()
    return duckdb.connect().execute(f"SELECT * FROM read_csv_auto('{p}') ORDER BY numero_de_cliente").fetchnumpy()


def estrategias(env: Path) -> dict:
    cat = json.loads((env / "modelos" / "estrategias.json").read_text(encoding="utf-8"))
    return {e["objetivo"]: {"id": e["id"], "semillas": [m["semilla"] for m in e["modelos"]],
                            "fraccion": e["corte"]["fraccion"]} for e in cat["estrategias"]}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def identidad(ce02: Path, b: Path, salida: Path) -> int:
    ea, eb = estrategias(ce02), estrategias(b)
    meses = sorted(int(p.name) for p in (b / "diagnosticos").iterdir() if p.name.isdigit())
    res = {"experimento": "CA02 identidad de ce02_b20m10 con ce02 (predicciones guardadas)", "exploratorio": True,
           "nota": "2020: verificación operativa, no criterio de elección (R1)", "ce02": mostrar(ce02),
           "b20m10": mostrar(b), "meses": {}}
    for m in meses:
        pa, pb = leer_pred(ce02, m), leer_pred(b, m)
        da, db = leer_dec(ce02, m), leer_dec(b, m)
        if not np.array_equal(pa["numero_de_cliente"], pb["numero_de_cliente"]):
            raise SystemExit(f"{m}: clientes distintos")
        bi_a, bi_b = ea["binary"], eb["binary"]
        mc_a, mc_b = ea["multiclass"], eb["multiclass"]
        sem10 = mc_b["semillas"]
        prom10 = np.mean([pa[f"{mc_a['id']}__semilla_{s}"] for s in sem10], axis=0)
        r = {
            "binario": {
                "mismo_id_semillas_y_corte": bi_a == bi_b,
                "semillas_identicas": all(np.array_equal(pa[f"{bi_a['id']}__semilla_{s}"],
                                                         pb[f"{bi_b['id']}__semilla_{s}"]) for s in bi_b["semillas"]),
                "ensamble_identico": bool(np.array_equal(pa[f"{bi_a['id']}__ensamble"], pb[f"{bi_b['id']}__ensamble"])),
                "decisiones_identicas": bool(np.array_equal(da[f"enviar_{bi_a['id']}"], db[f"enviar_{bi_b['id']}"])),
                "envios": int(db[f"enviar_{bi_b['id']}"].sum()),
                "salida_oficial_identica": sha(ce02 / "output" / f"churn_{m}.csv") == sha(b / "output" / f"churn_{m}.csv")},
            "multiclase": {
                "semillas_son_las_0_9_de_ce02": sem10 == mc_a["semillas"][:10],
                "semillas_identicas_a_las_de_ce02": all(np.array_equal(pa[f"{mc_a['id']}__semilla_{s}"],
                                                                       pb[f"{mc_b['id']}__semilla_{s}"]) for s in sem10),
                "ensamble_igual_a_promedio_semillas_0_9_de_ce02": bool(np.array_equal(prom10,
                                                                                      pb[f"{mc_b['id']}__ensamble"])),
                "mismo_corte": mc_a["fraccion"] == mc_b["fraccion"] == CORTE,
                "envios": [int(da[f"enviar_{mc_a['id']}"].sum()), int(db[f"enviar_{mc_b['id']}"].sum())]}}
        res["meses"][str(m)] = r
        print(m, json.dumps(r, ensure_ascii=False), flush=True)
    chk = lambda x: all(v for k, v in x.items() if isinstance(v, bool))  # noqa: E731
    res["ok"] = all(chk(r["binario"]) and chk(r["multiclase"]) for r in res["meses"].values())
    salida.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("ok", res["ok"], "->", mostrar(salida))
    return 0 if res["ok"] else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("corte")
    c.add_argument("--salida", type=Path, default=RAIZ / "resultados" / "ca02_corte_multiclase_10.json")
    i = sp.add_parser("identidad")
    i.add_argument("--ce02", type=Path, required=True)
    i.add_argument("--b20m10", type=Path, required=True)
    i.add_argument("--salida", type=Path, default=RAIZ / "resultados" / "ca02_identidad_con_ce02.json")
    a = ap.parse_args(argv)
    if a.cmd == "corte":
        return corte(a.salida)
    return identidad(a.ce02.resolve(), a.b20m10.resolve(), a.salida)


if __name__ == "__main__":
    sys.exit(main())
