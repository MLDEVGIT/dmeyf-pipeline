"""CE02 (paso 2) — análisis de ensambles de 5, 10 y 20 semillas (docs/PLAN_PRUEBAS.md § 13).

Lee las predicciones float64 de ejecuciones/ce02/<marca> (paso 1) y la composición registrada antes de entrenar
(resultados/ce02_composicion.json). Todo con 201908 y 201909 (meses de desarrollo; octubre bloqueado), target versión 2.
Reutiliza las reglas de CE01 (experimentos/ce01_estabilidad_corte.py): minimax, MVE, τ y traslado.

Reducción simulada de BAJA+2 (supuestos en § 13): scores fijos; cada BAJA+2 deja de pagar con probabilidad ρ, uniforme
e independiente del score; ganancia esperada exacta E[G_ρ(k)] = 1.100.000·(1−ρ)·TP(k) − 27.500·k.

Uso: python -m experimentos.ce02_analisis --ce02 ejecuciones/ce02/<marca>
Salida: resultados/ce02_ensambles_20.json y docs/figuras/ce02_*.png.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
import time
from pathlib import Path

import duckdb
import lightgbm as lgb
import numpy as np
from sklearn.metrics import roc_auc_score

from evaluacion import ganancia as G
from evaluacion import particiones as P
from experimentos import ce01_estabilidad_corte as CE
from experimentos.ce02_composicion import REGISTRO, SEMILLAS
from experimentos.e01_binario_vs_multiclase import FRACCIONES, cargar
from experimentos.e02_peso_baja1 import sha256
from pipeline_competencia02.config import RAIZ, RUTAS, mostrar

MESES = tuple(P.DESARROLLO)
BRAZOS = {"binario": ("binario", None), "multiclase_p1": ("multiclase", 2)}
RHOS = [0.0, 0.10, 0.20, 0.33, 0.50]
FILAS_MES_2020 = 153_000
LIMITE_INFERENCIA_S = 450.0
UMBRAL_SUBCONJUNTOS = 0.80
SECUENCIA_TC01 = RAIZ / "resultados" / "i04_secuencia_tc01_202001_202006.json"
AZULES = {"5": "#86b6ef", "10": "#2a78d6", "20": "#104281"}  # rampa secuencial (pasos 250, 450, 650)
RHO_COLOR = ["#104281", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4"]


def M(x) -> float:
    return CE.M(x)


# ------------------------------------------------------------------ curvas
def ens_curvas(P_: dict, meta: dict, ind: list[int], con_semillas: bool) -> dict:
    out = {}
    for m in MESES:
        clase, cli = meta[m]
        if con_semillas:
            out[m] = CE.curvas([P_[m][i] for i in ind], clase, cli)
        else:
            g = G.curva(P_[m][ind].mean(axis=0), clase == 2, cli)
            out[m] = {"g": g, "gs": G.suavizar(g), "n": len(cli)}
    return out


def peor_de(c: dict) -> np.ndarray:
    return CE.peor(CE.arrep({m: c[m]["gs"] for m in MESES}, {m: c[m]["n"] for m in MESES}))


def curva_rho(g: np.ndarray, rho: float) -> np.ndarray:
    k = np.arange(1, len(g) + 1, dtype="float64")
    return (1 - rho) * (g + G.COSTO_ENVIO * k) - G.COSTO_ENVIO * k  # TP·PREMIO = g + costo·k


def resumen_dist(fs: list[float]) -> dict:
    a = np.array(fs)
    return {"min": float(a.min()), "p10": float(np.quantile(a, 0.1)), "mediana": float(np.median(a)),
            "p90": float(np.quantile(a, 0.9)), "max": float(a.max()), "desvio": round(float(a.std(ddof=1)), 5)}


def rangos(s: np.ndarray) -> np.ndarray:
    return np.argsort(np.argsort(-s, kind="stable"), kind="stable").astype(float)


def top(score, cli, k) -> np.ndarray:
    s = np.zeros(len(score), bool)
    s[G.orden(score, cli)[:k]] = True
    return s


def jac(a, b) -> float:
    return round(float((a & b).sum() / (a | b).sum()), 4)


# ------------------------------------------------------------------ figuras
def marcas(ax, f20: float, mve20: float):
    """Líneas de corte con etiqueta; las que están a menos de 0,15 pp se agrupan en una sola etiqueta."""
    cortes = sorted([(0.029, "2,9 %"), (0.04475, "4,475 %"), (f20, f"minimax 20 ({f20 * 100:.3f} %)".replace(".", ",")),
                     (mve20, f"MVE 20 ({mve20 * 100:.3f} %)".replace(".", ","))])
    grupos = []
    for f, et in cortes:
        if grupos and f - grupos[-1][-1][0] < 0.0015:
            grupos[-1].append((f, et))
        else:
            grupos.append([(f, et)])
    for g in grupos:
        for f, _ in g:
            ax.axvline(f * 100, color=CE.GRIS, linewidth=1, linestyle=(0, (3, 3)))
        texto = g[0][1] if len(g) == 1 else " · ".join(et.split(" (")[0] for _, et in g)  # agrupadas: sólo nombres
        ax.text(max(f for f, _ in g) * 100, ax.get_ylim()[0], " " + texto, color=CE.TEXTO2, fontsize=8, va="bottom",
                rotation=90)


def figuras(cur: dict, sel: dict, sim: dict) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    CE.FIGURAS.mkdir(parents=True, exist_ok=True)
    x = FRACCIONES * 100
    r = (x >= 1.0) & (x <= 8.0)
    hechas = []

    fig, axs = plt.subplots(2, 2, figsize=(11, 7.5), facecolor=CE.FONDO, sharex=True)
    for i, brazo in enumerate(BRAZOS):
        for j, m in enumerate(MESES):
            ax = axs[i, j]
            CE.estilo(ax)
            for N in ("5", "10", "20"):
                c = cur[brazo][N][m]
                y = np.array([c["gs"][G.envios(f, c["n"]) - 1] for f in FRACCIONES]) / 1e6
                ax.plot(x[r], y[r], color=AZULES[N], linewidth=2, label=f"{N} semillas")
            marcas(ax, sel[brazo]["minimax"]["20"], sel[brazo]["anidados"]["20"]["mve"])
            ax.set_title(f"{brazo} · {m}", color=CE.TEXTO, fontsize=10, loc="left")
            if j == 0:
                ax.set_ylabel("ganancia suavizada del ensamble (M)", color=CE.TEXTO2, fontsize=9)
            if i == 1:
                ax.set_xlabel("fracción de clientes enviados (%)", color=CE.TEXTO2, fontsize=9)
    h, l = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper right", frameon=False, fontsize=9)
    fig.suptitle("CE02 · curvas de ganancia de los ensambles anidados (201908 y 201909, desarrollo)",
                 color=CE.TEXTO, fontsize=11, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    p = CE.FIGURAS / "ce02_curvas_ganancia.png"
    fig.savefig(p, dpi=130, facecolor=CE.FONDO)
    plt.close(fig)
    hechas.append(p)

    fig, axs = plt.subplots(2, 1, figsize=(10, 6.5), facecolor=CE.FONDO, sharex=True)
    bins = np.arange(0.5, 8.01, 0.125)
    for ax, brazo in zip(axs, BRAZOS):
        CE.estilo(ax)
        eq = sel[brazo]["conjunto_equivalente_20"]["tramos"]
        for a_, b_ in eq:
            ax.axvspan(a_ * 100 - 0.0125, b_ * 100 + 0.0125, color="#e6e5e0", zorder=0)
        ax.hist([np.array(sel[brazo]["aleatorios"][N]["fracciones"]) * 100 for N in ("5", "10")], bins=bins,
                color=[AZULES["5"], AZULES["10"]], label=[f"200 ensambles aleatorios de {N}" for N in ("5", "10")],
                edgecolor=CE.FONDO, linewidth=0.5)
        ax.axvline(sel[brazo]["minimax"]["20"] * 100, color=AZULES["20"], linewidth=2, label="minimax del ensamble de 20")
        ax.set_title(f"{brazo}: fracción elegida por el minimax según la composición del ensamble (gris: equivalente a 20 con τ)",
                     color=CE.TEXTO, fontsize=10, loc="left")
        ax.set_ylabel("ensambles", color=CE.TEXTO2, fontsize=9)
        ax.legend(frameon=False, fontsize=8, loc="upper right")
    axs[1].set_xlabel("fracción elegida (%)", color=CE.TEXTO2, fontsize=9)
    axs[1].set_xlim(1.5, 5.5)
    fig.tight_layout()
    p = CE.FIGURAS / "ce02_minimax_composicion.png"
    fig.savefig(p, dpi=130, facecolor=CE.FONDO)
    plt.close(fig)
    hechas.append(p)

    fig, axs = plt.subplots(2, 2, figsize=(11, 7.5), facecolor=CE.FONDO, sharex=True)
    for i, brazo in enumerate(BRAZOS):
        for j, m in enumerate(MESES):
            ax = axs[i, j]
            CE.estilo(ax)
            c = cur[brazo]["20"][m]
            for rho, col in zip(RHOS, RHO_COLOR):
                gs = G.suavizar(curva_rho(c["g"], rho))
                y = np.array([gs[G.envios(f, c["n"]) - 1] for f in FRACCIONES]) / 1e6
                ax.plot(x[r], y[r], color=col, linewidth=2, label=f"ρ = {rho:.2f}".replace(".", ","))
            marcas(ax, sel[brazo]["minimax"]["20"], sel[brazo]["anidados"]["20"]["mve"])
            ax.axhline(0, color=CE.GRIS, linewidth=0.8)
            ax.set_title(f"{brazo} · {m} · ensamble de 20", color=CE.TEXTO, fontsize=10, loc="left")
            if j == 0:
                ax.set_ylabel("ganancia esperada suavizada (M)", color=CE.TEXTO2, fontsize=9)
            if i == 1:
                ax.set_xlabel("fracción de clientes enviados (%)", color=CE.TEXTO2, fontsize=9)
    h, l = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=5, frameon=False, fontsize=9,
               title="ρ = proporción de BAJA+2 que deja de pagar", title_fontsize=8)
    fig.suptitle("CE02 · reducción simulada de BAJA+2 (scores fijos, pérdida uniforme)", color=CE.TEXTO, fontsize=11,
                 x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.07, 1, 0.96))
    p = CE.FIGURAS / "ce02_reduccion_baja2.png"
    fig.savefig(p, dpi=130, facecolor=CE.FONDO)
    plt.close(fig)
    hechas.append(p)
    return [mostrar(h) for h in hechas]


# ------------------------------------------------------------------ principal
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ce02", type=Path, required=True)
    ap.add_argument("--sin-tiempos", action="store_true", help="omite la medición de inferencia (pruebas rápidas)")
    ap.add_argument("--reusar-tiempos", action="store_true",
                    help="toma la medición de inferencia del resultados/ce02_ensambles_20.json existente")
    a = ap.parse_args(argv)
    d = a.ce02.resolve()
    t0 = time.perf_counter()
    reg = json.loads(REGISTRO.read_text(encoding="utf-8"))
    cfg = json.loads((d / "resultados.json").read_text(encoding="utf-8"))
    comp = reg["composiciones"]
    res = {"experimento": "CE02 ensambles de 5, 10 y 20 semillas", "inicio": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "plan_pruebas_sha256": sha256(RAIZ / "docs" / "PLAN_PRUEBAS.md"),
           "composicion_sha256": sha256(REGISTRO), "composicion_sha256_al_entrenar": cfg["composicion_sha256"],
           "modelos": mostrar(d), "meses": list(MESES),
           "meses_nota": "201908 y 201909 son de desarrollo: se elige y se mide en ellos; el traslado es la única medida "
                         "fuera del mes. Octubre bloqueado.",
           "verificaciones": {"composicion_igual_a_la_registrada_antes_de_entrenar":
                              sha256(REGISTRO) == cfg["composicion_sha256"],
                              "checks_entrenamiento": all(cfg["checks"].values()),
                              "semillas": cfg["semillas"] == SEMILLAS == reg["semillas"]}}
    meta = {m: (np.load(d / f"meta_{m}.npz")["clase"], np.load(d / f"meta_{m}.npz")["clientes"]) for m in MESES}

    cur, sel, rank, simul = {}, {}, {}, {}
    for brazo in BRAZOS:
        z = np.load(d / f"pred_{brazo}.npz")
        P_ = {m: z[str(m)] for m in MESES}
        assert all(P_[m].shape[0] == 20 for m in MESES)
        cur[brazo] = {N: ens_curvas(P_, meta, ind, True) for N, ind in comp["anidados"].items()}
        s = {"minimax": {}, "anidados": {}}
        c20 = cur[brazo]["20"]
        p20 = peor_de(c20)
        f20 = CE.elegir(p20, 0.0)
        tau20 = CE.tau_ruido(c20, f20)
        mask = p20 <= np.nanmin(p20) + tau20 + 1e-15
        s["conjunto_equivalente_20"] = {"tau": tau20, "tramos": CE.tramos(mask)}
        # 1. ganancia y curvas de los anidados
        for N, c in cur[brazo].items():
            p = peor_de(c)
            f = CE.elegir(p, 0.0)
            s["minimax"][N] = f
            tauN = CE.tau_ruido(c, f)
            fila = {"fraccion_minimax": f, "peor": round(float(p[CE.idx(f)]), 5),
                    "peor_medido_en_curva_20": round(float(p20[CE.idx(f)]), 5),
                    "dentro_del_conjunto_equivalente_20": bool(mask[CE.idx(f)]), "tau": tauN,
                    "mve": CE.elegir(p, tauN), "traslado_minimax": CE.traslado(c, 0.0),
                    "traslado_mve": CE.traslado(c, tauN), "por_mes": {}}
            for m in MESES:
                x = c[m]
                k = G.envios(f, x["n"])
                ks = int(np.nanargmax(x["gs"])) + 1
                sem = [int(g[k - 1]) for g in x["g_sem"]]
                ens = P_[m][comp["anidados"][N]].mean(axis=0)
                fila["por_mes"][str(m)] = {
                    "envios": k, "ganancia": M(x["g"][k - 1]), "ganancia_suav": M(x["gs"][k - 1]),
                    "max_suav": M(np.nanmax(x["gs"])), "fraccion_max_suav": round(ks / x["n"], 5),
                    "auc_baja2": round(float(roc_auc_score(meta[m][0] == 2, ens)), 5),
                    "semillas_en_el_corte_media": M(np.mean(sem)), "semillas_en_el_corte_desvio": M(np.std(sem, ddof=1))}
            s["anidados"][N] = fila
        # ganancia de las 20 semillas solas en el corte del ensamble de 20
        s["semillas_solas_en_corte_20"] = {str(m): {
            "media": M(np.mean([g[G.envios(f20, c20[m]["n"]) - 1] for g in c20[m]["g_sem"]])),
            "desvio": M(np.std([g[G.envios(f20, c20[m]["n"]) - 1] for g in c20[m]["g_sem"]], ddof=1))} for m in MESES}
        s["fraccion_por_semilla_sola"] = resumen_dist(CE.por_semilla(c20, 0.0))
        s["sensibilidad_tau_20"] = {str(t): CE.elegir(p20, t) for t in CE.TAUS + [tau20]}
        # 2. composición
        s["disjuntos"] = {N: [CE.elegir(peor_de(ens_curvas(P_, meta, ind, False)), 0.0) for ind in grupos]
                          for N, grupos in comp["disjuntos"].items()}
        s["aleatorios"] = {}
        for N, grupos in comp["aleatorios"].items():
            fs = [CE.elegir(peor_de(ens_curvas(P_, meta, ind, False)), 0.0) for ind in grupos]
            dentro = [bool(mask[CE.idx(f)]) for f in fs]
            s["aleatorios"][N] = {"fracciones": fs, "distribucion": resumen_dist(fs),
                                  "proporcion_dentro_del_equivalente_20": round(float(np.mean(dentro)), 4),
                                  "peor_medido_en_curva_20": resumen_dist([float(p20[CE.idx(f)]) for f in fs]),
                                  "zona_baja_menor_3": round(float(np.mean([f < 0.03 for f in fs])), 4),
                                  "zona_alta_mayor_igual_3_5": round(float(np.mean([f >= 0.035 for f in fs])), 4)}
        sel[brazo] = s
        # 3. rankings y clientes
        rk = {}
        for m in MESES:
            clase, cli = meta[m]
            n = len(cli)
            ks = {"k_2_9": G.envios(0.029, n), "k_minimax_20": G.envios(f20, n)}
            ens = {key: P_[m][ind].mean(axis=0) for key, ind in
                   [(f"d5_{i}", g) for i, g in enumerate(comp["disjuntos"]["5"])]
                   + [(f"d10_{i}", g) for i, g in enumerate(comp["disjuntos"]["10"])]
                   + [(f"a{N}", ind) for N, ind in comp["anidados"].items()]}
            r_ = {key: rangos(v) for key, v in ens.items()}
            fila = {}
            for kn, k in ks.items():
                tops = {key: top(v, cli, k) for key, v in ens.items()}
                p5 = [(a_, b_) for a_, b_ in itertools.combinations([f"d5_{i}" for i in range(4)], 2)]
                fila[kn] = {"k": k,
                            "disjuntos_5_jaccard": [jac(tops[a_], tops[b_]) for a_, b_ in p5],
                            "disjuntos_10_jaccard": jac(tops["d10_0"], tops["d10_1"]),
                            "anidado_5_vs_20": jac(tops["a5"], tops["a20"]),
                            "anidado_10_vs_20": jac(tops["a10"], tops["a20"])}
            fila["correlacion_de_rangos"] = {
                "disjuntos_5": [round(float(np.corrcoef(r_[a_], r_[b_])[0, 1]), 5) for a_, b_ in
                                itertools.combinations([f"d5_{i}" for i in range(4)], 2)],
                "disjuntos_10": round(float(np.corrcoef(r_["d10_0"], r_["d10_1"])[0, 1]), 5),
                "anidado_5_vs_20": round(float(np.corrcoef(r_["a5"], r_["a20"])[0, 1]), 5),
                "anidado_10_vs_20": round(float(np.corrcoef(r_["a10"], r_["a20"])[0, 1]), 5)}
            rk[str(m)] = fila
        rank[brazo] = rk
        # 4. reducción simulada de BAJA+2
        candidatos = {"2,9 %": 0.029, "4,475 %": 0.04475, **{f"minimax {N}": s["minimax"][N] for N in ("5", "10", "20")},
                      "MVE 20": s["anidados"]["20"]["mve"]}
        sm = {}
        for N in ("5", "10", "20"):
            c = cur[brazo][N]
            porrho = {}
            for rho in RHOS:
                gr = {m: curva_rho(c[m]["g"], rho) for m in MESES}
                gsr = {m: G.suavizar(gr[m]) for m in MESES}
                pr = CE.peor(CE.arrep(gsr, {m: c[m]["n"] for m in MESES}))
                f_rho = CE.elegir(pr, 0.0)
                cand = {}
                for nombre, f in candidatos.items():
                    cand[nombre] = {"fraccion": f, **{str(m): {
                        "ganancia_esperada": M(gr[m][G.envios(f, c[m]["n"]) - 1]),
                        "ganancia_suav": M(gsr[m][G.envios(f, c[m]["n"]) - 1]),
                        "arrepentimiento": round(float(1 - gsr[m][G.envios(f, c[m]["n"]) - 1] / np.nanmax(gsr[m])), 5)}
                        for m in MESES}}
                porrho[str(rho)] = {"minimax_sobre_curva_rho": f_rho,
                                    "max_suav": {str(m): M(np.nanmax(gsr[m])) for m in MESES},
                                    "fraccion_max_suav": {str(m): round((int(np.nanargmax(gsr[m])) + 1) / c[m]["n"], 5)
                                                          for m in MESES},
                                    "candidatos": cand}
            sm[N] = porrho
        simul[brazo] = sm
        print(f"{brazo}: minimax 5/10/20 = {s['minimax']}; τ20 = {tau20:.4f}; equivalente 20 = {s['conjunto_equivalente_20']['tramos']}; "
              f"aleatorios dentro: { {N: v['proporcion_dentro_del_equivalente_20'] for N, v in s['aleatorios'].items()} }",
              flush=True)

    # 5. tiempos de inferencia
    tiempos = None
    previo = RAIZ / "resultados" / "ce02_ensambles_20.json"
    if a.reusar_tiempos:
        tiempos = json.loads(previo.read_text(encoding="utf-8"))["tiempos_inferencia"]
        tiempos["reutilizado"] = "medición de una corrida anterior del análisis con los mismos modelos"
    elif not a.sin_tiempos:
        pred_cols = json.loads((RUTAS.features_2019 / "manifiesto.json").read_text(encoding="utf-8"))["predictores"]
        con = duckdb.connect()
        con.execute("SET threads = 8")
        X, _, _, _ = cargar(con, (MESES[1],), pred_cols, RUTAS.target_2019_v2)
        con.close()
        tiempos = {"mes": MESES[1], "filas": int(len(X)), "hilos": 4, "por_modelo_s": {}}
        for brazo, (arch, col) in BRAZOS.items():
            bs = [lgb.Booster(model_file=str(d / "modelos" / f"{arch}_{s_}.txt")) for s_ in SEMILLAS]
            bs[0].predict(X[:20000], num_threads=4)  # calentamiento
            ts = []
            for b in bs:
                t = time.perf_counter()
                b.predict(X, num_threads=4)
                ts.append(round(time.perf_counter() - t, 2))
            tiempos["por_modelo_s"][brazo] = ts
        escala = FILAS_MES_2020 / len(X)
        sec = json.loads(SECUENCIA_TC01.read_text(encoding="utf-8"))
        no_inf = []
        for mm in sec["meses"]:
            if len(mm["intentos"]) == 1:
                ti = mm["tiempos_internos"]
                inf = sum(v for k_, v in ti.items() if k_.startswith("inferencia_"))
                no_inf.append(mm["tiempo_total_s"] - inf)
        base = float(np.median(no_inf))
        tiempos["ensambles"] = {}
        for N in ("5", "10", "20"):
            n_ = int(N)
            inf = {b_: round(sum(tiempos["por_modelo_s"][b_][:n_]) * escala, 1) for b_ in BRAZOS}
            tiempos["ensambles"][N] = {"inferencia_estimada_153k_s": inf, "inferencia_ambas_s": round(sum(inf.values()), 1),
                                       "mes_estimado_s": round(base + sum(inf.values()), 1)}
        tiempos["parte_no_inferencial_s"] = {"mediana": round(base, 1), "fuente": mostrar(SECUENCIA_TC01),
                                             "meses": [round(v, 1) for v in no_inf]}
        tiempos["nota"] = ("inferencia medida en 201909 (133.419 filas) y escalada linealmente a 153.000 filas; el mes "
                           "estimado suma la parte no inferencial medida en la secuencia tc01 (pared, con arranque)")

    # regla de recomendación (§ 13)
    rec = {}
    for brazo in BRAZOS:
        cond = {}
        for N in ("5", "10", "20"):
            a_ok = True if N == "20" else sel[brazo]["aleatorios"][N]["proporcion_dentro_del_equivalente_20"] >= UMBRAL_SUBCONJUNTOS
            b_ok = None if tiempos is None else tiempos["ensambles"][N]["inferencia_ambas_s"] <= LIMITE_INFERENCIA_S
            cond[N] = {"a_estabilidad": a_ok, "b_tiempo": b_ok}
        candidatos = [N for N in ("5", "10", "20") if cond[N]["a_estabilidad"] and cond[N]["b_tiempo"] is not False]
        if candidatos:
            N_rec = candidatos[0]
        else:
            factibles = [N for N in ("5", "10", "20") if cond[N]["b_tiempo"] is not False]
            N_rec = factibles[-1] if factibles else "5"
        an = sel[brazo]["anidados"][N_rec]
        s33 = simul[brazo][N_rec]["0.33"]["candidatos"]
        mm_nombre = f"minimax {N_rec}"
        mve_f = an["mve"]
        # arrepentimiento con ρ = 0,33 del minimax contra el MVE del ensamble recomendado
        c = cur[brazo][N_rec]
        gsr = {m: G.suavizar(curva_rho(c[m]["g"], 0.33)) for m in MESES}
        arr = lambda f: {str(m): float(1 - gsr[m][G.envios(f, c[m]["n"]) - 1] / np.nanmax(gsr[m])) for m in MESES}
        a_mm, a_mve = arr(an["fraccion_minimax"]), arr(mve_f)
        usar_mve = any(a_mm[m] - a_mve[m] > an["tau"] for m in a_mm)
        rec[brazo] = {"condiciones_por_tamano": cond, "tamano_recomendado": N_rec,
                      "corte_minimax": an["fraccion_minimax"], "corte_mve": mve_f, "tau": an["tau"],
                      "arrepentimiento_rho_0_33": {"minimax": {k_: round(v, 5) for k_, v in a_mm.items()},
                                                   "mve": {k_: round(v, 5) for k_, v in a_mve.items()}},
                      "corte_recomendado": mve_f if usar_mve else an["fraccion_minimax"],
                      "procedimiento": "MVE" if usar_mve else "minimax", "activa": False}

    res.update({"ganancia_y_corte": sel, "rankings": rank, "reduccion_baja2": {
        "supuestos": ["scores fijos (las predicciones no cambian)", "cada BAJA+2 deja de pagar con probabilidad ρ, uniforme "
                      "e independiente del score", "misma cantidad de clientes, costo 27.500 y premio 1.100.000",
                      "ganancia esperada exacta E[G_ρ(k)] = 1.100.000·(1−ρ)·TP(k) − 27.500·k; sin muestreo"],
        "no_representa": ["cambios en los scores o drift de features", "pérdida concentrada en scores altos o bajos",
                          "cambios en la cantidad de clientes"],
        "grilla": RHOS, "justificacion_grilla": "0,33 = caída máxima de prevalencia de BAJA+2 entre meses permitidos de "
                                                "2019 (0,616 % en 201903 a 0,412 % en 201908); 0,50 = estrés más allá",
        "resultados": simul}, "tiempos_inferencia": tiempos, "recomendacion": rec})
    res["figuras"] = figuras(cur, sel, simul)
    res["verificaciones"]["todas"] = all(res["verificaciones"].values())
    res["segundos"] = round(time.perf_counter() - t0, 1)
    destino = RAIZ / "resultados" / "ce02_ensambles_20.json"
    destino.write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verificaciones": res["verificaciones"], "recomendacion": rec,
                      "tiempos": tiempos and tiempos["ensambles"]}, indent=1, ensure_ascii=False, default=float))
    return 0 if res["verificaciones"]["todas"] else 1


if __name__ == "__main__":
    sys.exit(main())
