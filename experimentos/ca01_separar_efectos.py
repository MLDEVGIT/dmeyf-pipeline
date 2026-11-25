"""CA01 — separa el efecto del ensamble y del corte entre tc01 y el candidato ce02, con predicciones guardadas.

EXPLORATORIO (2020). Nada de esto cambia el tamaño, los cortes ni los roles, elegidos sólo con 201908–201909 (R1).
Protocolo: docs/PLAN_PRUEBAS.md § 15. No reentrena ni vuelve a predecir: usa
  - diagnosticos/<mes>/predicciones_<mes>.parquet del candidato (cada una de las 20 semillas por objetivo) y
  - el de tc01 (ensamble de 5 publicado).

Por mes:
  1. identidad: promedio de las semillas 0–4 del candidato == ensamble publicado por tc01 (bit a bit), y el
     ensamble del candidato == promedio de sus 20 semillas;
  2. grilla ensamble × corte (envíos = techo(f · n), orden = probabilidad desc., cliente asc.):
       binario     ensambles 5 y 20; cortes 4,475 % (tc01), 2,35 % (candidato), 3,675 % (minimax de 20, referencia)
       multiclase  ensambles 5, 10 y 20; cortes 2,8 % (tc01), 2,725 % (candidato)
     por celda: envíos y Jaccard contra la selección publicada por tc01; con target completo, BAJA+2 enviados y
     ganancia (y la celda tc01 y la del candidato se contrastan con la retrospectiva de cada corrida);
  3. efectos (target completo): ensamble con el corte fijo, corte con el ensamble fijo, total e interacción.
Etiquetas: evaluacion.target.etiquetar con la presencia en la historia del candidato (meses recibidos), la misma
regla y fuente que la retrospectiva.

Uso: python -m experimentos.ca01_separar_efectos --tc01 <carpeta> --candidato <carpeta> [--salida <json>]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb
import numpy as np

from evaluacion.ganancia import COSTO_ENVIO, PREMIO_BRUTO, curva, envios, orden
from pipeline_competencia02 import retrospectiva as R
from pipeline_competencia02.config import RAIZ, mostrar

CORTES = {"binario": {"tc01": 0.04475, "candidato": 0.0235, "minimax_20": 0.03675},
          "multiclase_p1": {"tc01": 0.028, "candidato": 0.02725}}
ENSAMBLES = {"binario": (5, 20), "multiclase_p1": (5, 10, 20)}
NOTA = ("EXPLORATORIO: resultados de 2020; no cambian tamaño, cortes ni roles, elegidos sólo con 201908–201909 "
        "(R1, PLAN_PRUEBAS.md § 15)")


def leer_pred(env: Path, mes: int) -> dict:
    p = (env / "diagnosticos" / str(mes) / f"predicciones_{mes}.parquet").as_posix()
    return duckdb.connect().execute(f"SELECT * FROM read_parquet('{p}') ORDER BY numero_de_cliente").fetchnumpy()


def ids(env: Path) -> dict:
    cat = json.loads((env / "modelos" / "estrategias.json").read_text(encoding="utf-8"))
    out = {}
    for e in cat["estrategias"]:
        brazo = "binario" if e["objetivo"] == "binary" else "multiclase_p1"
        out[brazo] = {"id": e["id"], "semillas": [m["semilla"] for m in e["modelos"]],
                      "fraccion": e["corte"]["fraccion"]}
    return out


def seleccion(score: np.ndarray, cli: np.ndarray, f: float) -> np.ndarray:
    s = np.zeros(len(cli), bool)
    s[orden(score, cli)[:envios(f, len(cli))]] = True
    return s


def jaccard(a: np.ndarray, b: np.ndarray) -> float:
    return round(float((a & b).sum() / (a | b).sum()), 4)


def etiquetas(env: Path, mes: int, cli: np.ndarray) -> tuple[dict, np.ndarray | None]:
    disp = R.disponibilidad(env / "historia", mes)
    if disp["estado"] != "completa":
        return disp, None
    con = duckdb.connect()
    m1, m2 = disp["requiere"]
    en1 = np.isin(cli, R.presentes(con, env / "historia" / f"foto_mes={m1}.parquet"))
    en2 = np.isin(cli, R.presentes(con, env / "historia" / f"foto_mes={m2}.parquet"))
    con.close()
    return disp, R.etiquetar(en1, en2) == "BAJA+2"


def ganancia(sel: np.ndarray, b2: np.ndarray) -> int:
    return int(PREMIO_BRUTO * int((sel & b2).sum()) - COSTO_ENVIO * int(sel.sum()))


def retro(env: Path, mes: int, rol_id: str) -> int | None:
    r = R.cargar(env, mes) or {}
    return next((e["ganancia"] for e in r.get("estrategias", []) if e["id"] == rol_id and "ganancia" in e), None)


def analizar_mes(tc: Path, ca: Path, mes: int) -> dict:
    it, ic = ids(tc), ids(ca)
    pt, pc = leer_pred(tc, mes), leer_pred(ca, mes)
    cli = pc["numero_de_cliente"].astype(np.int64)
    if not np.array_equal(cli, pt["numero_de_cliente"].astype(np.int64)):
        raise SystemExit(f"{mes}: clientes distintos entre corridas")
    disp, b2 = etiquetas(ca, mes, cli)
    out = {"clientes": int(len(cli)), "target": disp["estado"], "identidad": {}, "brazos": {}}
    for brazo in ("binario", "multiclase_p1"):
        semillas = np.vstack([pc[f"{ic[brazo]['id']}__semilla_{s}"] for s in ic[brazo]["semillas"]])
        tc_ens = pt[f"{it[brazo]['id']}__ensamble"]
        scores = {n: np.mean(list(semillas[:n]), axis=0) for n in ENSAMBLES[brazo]}
        out["identidad"][brazo] = {
            "semillas_tc01_iguales_a_las_primeras_5": it[brazo]["semillas"] == ic[brazo]["semillas"][:5],
            "promedio_semillas_0_4_igual_a_tc01_publicado": bool(np.array_equal(scores[5], tc_ens)),
            "ensamble_candidato_igual_a_promedio_de_20": bool(np.array_equal(scores[20],
                                                                             pc[f"{ic[brazo]['id']}__ensamble"]))}
        sel_tc = seleccion(tc_ens, cli, it[brazo]["fraccion"])
        celdas = {}
        for n, sc in scores.items():
            for nombre, f in CORTES[brazo].items():
                s = seleccion(sc, cli, f)
                c = {"ensamble": n, "corte": nombre, "fraccion": f, "envios": int(s.sum()),
                     "jaccard_con_tc01_publicado": jaccard(s, sel_tc)}
                if b2 is not None:
                    c.update(baja2_enviados=int((s & b2).sum()), ganancia=ganancia(s, b2))
                celdas[f"e{n}_{nombre}"] = c
        b = {"celdas": celdas}
        if b2 is not None:
            b["baja2_mes"] = int(b2.sum())
            b["auc_baja2"] = {str(n): round(R.auc(sc, b2), 6) for n, sc in scores.items()}
            b["ganancia_maxima_ex_post"] = {str(n): int(curva(sc, b2, cli).max()) for n, sc in scores.items()}
            G = {k: v["ganancia"] for k, v in celdas.items()}
            b["efectos"] = {
                "total_candidato_menos_tc01": G["e20_candidato"] - G["e5_tc01"],
                "ensamble_con_corte_tc01": G["e20_tc01"] - G["e5_tc01"],
                "ensamble_con_corte_candidato": G["e20_candidato"] - G["e5_candidato"],
                "corte_con_ensamble_5": G["e5_candidato"] - G["e5_tc01"],
                "corte_con_ensamble_20": G["e20_candidato"] - G["e20_tc01"],
                "interaccion": G["e20_candidato"] - G["e20_tc01"] - G["e5_candidato"] + G["e5_tc01"]}
            b["contraste_con_retrospectiva"] = {
                "tc01": retro(tc, mes, it[brazo]["id"]) == G["e5_tc01"],
                "candidato": retro(ca, mes, ic[brazo]["id"]) == G["e20_candidato"]}
        out["brazos"][brazo] = b
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tc01", type=Path, required=True)
    ap.add_argument("--candidato", type=Path, required=True)
    ap.add_argument("--salida", type=Path, default=RAIZ / "resultados" / "ca01_separacion_efectos.json")
    a = ap.parse_args(argv)
    tc, ca = a.tc01.resolve(), a.candidato.resolve()
    meses = sorted(int(p.name) for p in (ca / "diagnosticos").iterdir() if p.name.isdigit())
    res = {"experimento": "CA01 separación de efectos ensamble × corte", "exploratorio": True, "nota": NOTA,
           "tc01": mostrar(tc), "candidato": mostrar(ca), "cortes": CORTES, "ensambles": ENSAMBLES, "meses": {}}
    for m in meses:
        res["meses"][str(m)] = r = analizar_mes(tc, ca, m)
        print(m, r["target"], json.dumps(r["identidad"]), flush=True)
        for brazo, b in r["brazos"].items():
            print("  ", brazo, {k: (v["envios"], v.get("ganancia")) for k, v in b["celdas"].items()},
                  b.get("efectos"), b.get("contraste_con_retrospectiva"), flush=True)
    completos = [m for m, r in res["meses"].items() if r["target"] == "completa"]
    res["acumulado_target_completo"] = {"meses": completos, **{brazo: {
        k: sum(res["meses"][m]["brazos"][brazo]["celdas"][k]["ganancia"] for m in completos)
        for k in res["meses"][completos[0]]["brazos"][brazo]["celdas"]} for brazo in CORTES}} if completos else {}
    res["verificaciones"] = {
        "identidad": all(all(v.values()) for r in res["meses"].values() for v in r["identidad"].values()),
        "contraste_con_retrospectiva": all(all(b["contraste_con_retrospectiva"].values())
                                           for r in res["meses"].values() for b in r["brazos"].values()
                                           if "contraste_con_retrospectiva" in b)}
    a.salida.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("verificaciones", res["verificaciones"], "->", mostrar(a.salida))
    return 0 if all(res["verificaciones"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
