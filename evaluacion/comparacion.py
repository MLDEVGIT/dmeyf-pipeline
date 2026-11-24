"""Evaluación de un "brazo" (objetivo o variante) y comparación pareada entre brazos.

`evaluar_brazo` reproduce exactamente la evaluación de experimentos/e01_binario_vs_multiclase.py:
  - ensamble = promedio de probabilidades de las semillas;
  - fracción de corte con menor arrepentimiento máximo entre los meses, sobre la curva suavizada
    del ensamble;
  - ganancia sin suavizar en ⌈f·n⌉ para el ensamble y para cada semilla sola;
  - transferencia del corte entre meses.
Agrega, para medir la estabilidad del corte, la fracción que elegiría cada semilla sola.
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import roc_auc_score

from . import ganancia as G


def evaluar_mes(score, clase, clientes) -> dict:
    b2 = clase == 2
    g = G.curva(score, b2, clientes)
    gs = G.suavizar(g)
    k = int(np.nanargmax(gs)) + 1
    return {"g": g, "gs": gs, "k_max_suav": k, "g_max_suav": float(np.nanmax(gs)),
            "auc_baja2": float(roc_auc_score(b2, score)), "n": len(score), "baja2": int(b2.sum())}


def _sin_curvas(e: dict) -> dict:
    return {k: v for k, v in e.items() if k not in ("g", "gs")}


def evaluar_brazo(preds: dict, meta: dict, fracciones: np.ndarray) -> dict:
    """preds[mes] = lista de vectores de score (una por semilla); meta[mes] = (clase, clientes)."""
    meses = list(preds)
    n = {m: len(meta[m][0]) for m in meses}
    ev_s = {m: [evaluar_mes(s, *meta[m]) for s in preds[m]] for m in meses}
    ens = {m: evaluar_mes(np.mean(preds[m], axis=0), *meta[m]) for m in meses}
    f, tabla = G.corte_minimax({m: ens[m]["gs"] for m in meses}, n, fracciones)
    r = {"ensamble": {str(m): _sin_curvas(ens[m]) for m in meses},
         "por_semilla": {str(m): [_sin_curvas(e) for e in ev_s[m]] for m in meses},
         "corte": {"fraccion": f, "arrepentimiento_max": float(tabla["peor_caso"][list(fracciones).index(f)])}}
    for m in meses:
        k = G.envios(f, n[m])
        ps = [int(e["g"][k - 1]) for e in ev_s[m]]
        r["corte"][str(m)] = {
            "envios": k, "ganancia": int(ens[m]["g"][k - 1]), "ganancia_suav": float(ens[m]["gs"][k - 1]),
            "ganancia_max_suav": ens[m]["g_max_suav"], "k_max_suav": ens[m]["k_max_suav"], "por_semilla": ps,
            "semillas_media": float(np.mean(ps)),
            "semillas_desvio": float(np.std(ps, ddof=1)) if len(ps) > 1 else None}
    r["transferencia"] = {}
    for elegido in meses:
        for medido in meses:
            if elegido == medido:
                continue
            fe, _ = G.corte_minimax({elegido: ens[elegido]["gs"]}, {elegido: n[elegido]}, fracciones)
            k = G.envios(fe, n[medido])
            r["transferencia"][f"{elegido}->{medido}"] = {
                "fraccion": fe, "envios": k, "ganancia": int(ens[medido]["g"][k - 1]),
                "arrepentimiento": float(1 - ens[medido]["gs"][k - 1] / ens[medido]["g_max_suav"])}
    r["transferencia_peor_caso"] = max(t["arrepentimiento"] for t in r["transferencia"].values())
    # estabilidad del corte: fracción que elegiría cada semilla sola (mismo criterio que el ensamble)
    fs = []
    for i in range(len(preds[meses[0]])):
        fi, _ = G.corte_minimax({m: ev_s[m][i]["gs"] for m in meses}, n, fracciones)
        fs.append(fi)
    r["corte"]["fraccion_por_semilla"] = fs
    r["corte"]["fraccion_por_semilla_rango"] = [min(fs), max(fs)]
    return r


def pareadas(candidato: dict, referencia: dict, meses) -> dict:
    """Diferencias por semilla (candidato − referencia), cada brazo en su propia fracción de corte."""
    out = {}
    for m in meses:
        c = np.array(candidato["corte"][str(m)]["por_semilla"], dtype=float)
        r = np.array(referencia["corte"][str(m)]["por_semilla"], dtype=float)
        d = c - r
        out[str(m)] = {"diferencias": [float(x) for x in d], "positivas": int((d > 0).sum()),
                       "negativas": int((d < 0).sum()), "media": float(d.mean()),
                       "desvio": float(d.std(ddof=1)) if len(d) > 1 else None,
                       "ensamble": candidato["corte"][str(m)]["ganancia"] - referencia["corte"][str(m)]["ganancia"]}
    return out


def regla_adopcion(candidato: dict, referencia: dict, meses, minimo_semillas: int) -> dict:
    """Regla de PLAN_PRUEBAS.md § 4 (fijada antes de E01): las tres condiciones deben cumplirse."""
    par = pareadas(candidato, referencia, meses)
    c1 = all(par[str(m)]["ensamble"] > 0 for m in meses)
    c2 = all(par[str(m)]["positivas"] >= minimo_semillas for m in meses)
    c3 = candidato["transferencia_peor_caso"] <= referencia["transferencia_peor_caso"]
    return {"1_ensamble_mayor_en_todos_los_meses": c1, "2_semillas_a_favor_en_cada_mes": c2,
            "3_transferencia_no_empeora": c3, "adopta": bool(c1 and c2 and c3), "pareadas": par}
