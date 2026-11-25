"""CE01 — estabilidad del corte en 201908–201909, sobre los modelos ya entrenados (docs/PLAN_PRUEBAS.md § 11).

Protocolo escrito antes de calcular un corte nuevo (se registra el sha256 de PLAN_PRUEBAS.md al inicio). No reentrena:
vuelve a predecir con los modelos guardados de E01 (anteriores, target versión 1) y TC01 (corregidos, target versión 2),
y evalúa todo con el target versión 2 de 2019. Octubre bloqueado (evaluacion/particiones.py). La revisión la motivó
el ensayo exploratorio de 2020; ningún dato de 2020 se lee acá.

Uso: python -m experimentos.ce01_estabilidad_corte --e01 ejecuciones/e01/<marca> --tc01 ejecuciones/tc01/<marca>
Salida: resultados/ce01_estabilidad_corte.json y docs/figuras/ce01_*.png.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import duckdb
import lightgbm as lgb
import numpy as np

from evaluacion import ganancia as G
from evaluacion import particiones as P
from experimentos.e01_binario_vs_multiclase import FRACCIONES, cargar
from experimentos.e02_peso_baja1 import sha256
from pipeline_competencia02.config import RAIZ, RUTAS, mostrar

MESES = tuple(P.DESARROLLO)
TAUS = [0.0, 0.0025, 0.005, 0.01, 0.015, 0.02, 0.03, 0.05]
CORTES = [0.028, 0.029, 0.04475]
# objetivo -> (archivo de modelo, columna del score, npz de E01, npz de TC01, clave de resultados E01, clave TC01)
OBJETIVOS = {"binario": ("binario", None, "pred_binario.npz", "pred_binario.npz", "binario", "binario"),
             "multiclase_p1": ("multiclase", 2, "pred_multiclase.npz", "pred_multiclase_p1.npz", "multiclase",
                               "multiclase_p1")}
FIGURAS = RAIZ / "docs" / "figuras"
COLOR = {"anterior": "#2a78d6", "corregido": "#eb6834"}  # categóricos 1 y 2 de la paleta validada
TEXTO, TEXTO2, GRIS, FONDO = "#0b0b0b", "#52514e", "#8a8984", "#fcfcfb"


def M(x) -> float:
    return round(float(x) / 1e6, 2)


def idx(f: float) -> int:
    return int(np.argmin(np.abs(FRACCIONES - f)))


# ---------------------------------------------------------------- curvas y reglas
def curvas(preds: list[np.ndarray], clase: np.ndarray, cli: np.ndarray) -> dict:
    b2 = clase == 2
    ens = np.mean(preds, axis=0)
    g = G.curva(ens, b2, cli)
    gss = [G.suavizar(G.curva(p, b2, cli)) for p in preds]
    return {"g": g, "gs": G.suavizar(g), "g_sem": [G.curva(p, b2, cli) for p in preds], "gs_sem": gss, "n": len(cli)}


def arrep(gs: dict, n: dict) -> dict:
    return G.arrepentimiento(gs, n, FRACCIONES)  # mes -> array sobre FRACCIONES


def peor(r: dict) -> np.ndarray:
    return np.max(np.vstack(list(r.values())), axis=0)


def elegir(p: np.ndarray, tau: float) -> float:
    """MVE: menor f con p(f) <= min p + tau. Con tau = 0 es el minimax (primer mínimo = menor f)."""
    return float(FRACCIONES[int(np.argmax(p <= np.nanmin(p) + tau + 1e-15))])


def tramos(mascara: np.ndarray) -> list[list[float]]:
    out, ini = [], None
    for i, v in enumerate(mascara):
        if v and ini is None:
            ini = i
        if (not v or i == len(mascara) - 1) and ini is not None:
            fin = i if v else i - 1
            out.append([float(FRACCIONES[ini]), float(FRACCIONES[fin])])
            ini = None
    return out


def tau_ruido(c: dict, f: float) -> float:
    vals = []
    for m, x in c.items():
        k = G.envios(f, x["n"])
        sem = np.array([gs[k - 1] for gs in x["gs_sem"]])
        vals.append(sem.std(ddof=1) / (math.sqrt(len(sem)) * np.nanmax(x["gs"])))
    return float(np.mean(vals))


def traslado(c: dict, tau: float) -> dict:
    out = {}
    for elegido in MESES:
        for medido in MESES:
            if elegido == medido:
                continue
            r1 = arrep({elegido: c[elegido]["gs"]}, {elegido: c[elegido]["n"]})[elegido]
            f = elegir(r1, tau)
            k = G.envios(f, c[medido]["n"])
            x = c[medido]
            out[f"{elegido}->{medido}"] = {"fraccion": f, "envios": k, "ganancia": M(x["g"][k - 1]),
                                            "ganancia_suav": M(x["gs"][k - 1]),
                                            "arrepentimiento": round(float(1 - x["gs"][k - 1] / np.nanmax(x["gs"])), 5)}
    return out


def por_semilla(c: dict, tau: float) -> list[float]:
    S = len(c[MESES[0]]["gs_sem"])
    fs = []
    for s in range(S):
        r = arrep({m: c[m]["gs_sem"][s] for m in MESES}, {m: c[m]["n"] for m in MESES})
        fs.append(elegir(peor(r), tau))
    return fs


def en_corte(c: dict, f: float) -> dict:
    out = {}
    for m, x in c.items():
        k = G.envios(f, x["n"])
        sem = [int(g[k - 1]) for g in x["g_sem"]]
        out[m] = {"envios": k, "ganancia": M(x["g"][k - 1]), "ganancia_suav": M(x["gs"][k - 1]),
                  "semillas_media": M(np.mean(sem)), "semillas_desvio": M(np.std(sem, ddof=1))}
    return out


# ---------------------------------------------------------------- figuras
def estilo(ax):
    ax.set_facecolor(FONDO)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRIS)
    ax.tick_params(colors=TEXTO2, labelsize=9)
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.8)
    ax.set_axisbelow(True)


def figuras(cur: dict, sel: dict) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIGURAS.mkdir(parents=True, exist_ok=True)
    x = FRACCIONES * 100
    rango = (x >= 1.0) & (x <= 8.0)
    hechos = []

    # 1. ganancia suavizada por mes y objetivo
    fig, axs = plt.subplots(2, 2, figsize=(11, 7.5), facecolor=FONDO, sharex=True)
    for i, obj in enumerate(OBJETIVOS):
        for j, m in enumerate(MESES):
            ax = axs[i, j]
            estilo(ax)
            for mod in ("anterior", "corregido"):
                c = cur[mod][obj][m]
                y = np.array([c["gs"][G.envios(f, c["n"]) - 1] for f in FRACCIONES]) / 1e6
                ax.plot(x[rango], y[rango], color=COLOR[mod], linewidth=2, label=mod)
            for f, et in sorted({(0.029, "2,9 %"), (0.04475, "4,475 %"), (sel[obj]["mve"], "MVE corregido")}):
                ax.axvline(f * 100, color=GRIS, linewidth=1, linestyle=(0, (3, 3)))
                ax.text(f * 100, ax.get_ylim()[0], f" {et}", color=TEXTO2, fontsize=8, va="bottom", rotation=90)
            ax.set_title(f"{obj} · {m}", color=TEXTO, fontsize=10, loc="left")
            if j == 0:
                ax.set_ylabel("ganancia suavizada del ensamble (M)", color=TEXTO2, fontsize=9)
            if i == 1:
                ax.set_xlabel("fracción de clientes enviados (%)", color=TEXTO2, fontsize=9)
    h, l = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, ["anteriores (E01)", "corregidos (TC01)"], loc="upper right", frameon=False, fontsize=9)
    fig.suptitle("CE01 · curvas de ganancia en 201908 y 201909 (target versión 2)", color=TEXTO, fontsize=11, x=0.01,
                 ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    p = FIGURAS / "ce01_curvas_ganancia.png"
    fig.savefig(p, dpi=130, facecolor=FONDO)
    plt.close(fig)
    hechos.append(p)

    # 2. peor arrepentimiento y banda de tolerancia
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.2), facecolor=FONDO, sharey=True)
    for ax, obj in zip(axs, OBJETIVOS):
        estilo(ax)
        for mod in ("anterior", "corregido"):
            pe = sel[obj]["peor"][mod] * 100
            ax.plot(x[rango], pe[rango], color=COLOR[mod], linewidth=2,
                    label=f"{mod} (τ = {sel[obj]['tau'][mod] * 100:.2f} %)")
            f_mm, f_mve, t = sel[obj]["minimax"][mod], sel[obj]["mve_por_modelo"][mod], sel[obj]["tau"][mod]
            ax.axhline((np.nanmin(sel[obj]["peor"][mod]) + t) * 100, color=COLOR[mod], linewidth=1, linestyle=(0, (1, 2)))
            ax.plot([f_mm * 100], [sel[obj]["peor"][mod][idx(f_mm)] * 100], "o", color=COLOR[mod], markersize=8,
                    markeredgecolor=FONDO, markeredgewidth=2)
            ax.plot([f_mve * 100], [sel[obj]["peor"][mod][idx(f_mve)] * 100], "s", color=COLOR[mod], markersize=8,
                    markeredgecolor=FONDO, markeredgewidth=2)
        ax.set_ylim(0, 10)
        ax.set_title(f"{obj}: peor arrepentimiento entre meses", color=TEXTO, fontsize=10, loc="left")
        ax.set_xlabel("fracción (%)   ● minimax   ■ MVE   ··· mínimo + τ", color=TEXTO2, fontsize=9)
        ax.legend(frameon=False, fontsize=8, loc="upper right")
    axs[0].set_ylabel("peor arrepentimiento (%)", color=TEXTO2, fontsize=9)
    fig.tight_layout()
    p = FIGURAS / "ce01_peor_arrepentimiento.png"
    fig.savefig(p, dpi=130, facecolor=FONDO)
    plt.close(fig)
    hechos.append(p)

    # 3. sensibilidad: fracción elegida según τ
    fig, ax = plt.subplots(figsize=(7.5, 4), facecolor=FONDO)
    estilo(ax)
    for obj, ls in (("binario", "-"), ("multiclase_p1", (0, (4, 2)))):
        for mod in ("anterior", "corregido"):
            fs = [sel[obj]["sensibilidad"][mod][str(t)]["fraccion"] * 100 for t in TAUS]
            ax.step([t * 100 for t in TAUS] + [5.5], fs + fs[-1:], where="post", color=COLOR[mod], linestyle=ls,
                    linewidth=2, label=f"{obj} {mod}")
            tc = sel[obj]["tau"][mod]
            ax.plot([tc * 100], [sel[obj]["mve_por_modelo"][mod] * 100], "o" if obj == "binario" else "s",
                    color=COLOR[mod], markersize=8, markeredgecolor=FONDO, markeredgewidth=2)
    ax.set_xlim(0, 5.5)
    ax.set_xlabel("tolerancia τ (%)   ● ■ τ calculado con el ruido entre semillas", color=TEXTO2, fontsize=9)
    ax.set_ylabel("fracción elegida (%)", color=TEXTO2, fontsize=9)
    ax.set_title("Sensibilidad del corte MVE a la tolerancia", color=TEXTO, fontsize=10, loc="left")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    p = FIGURAS / "ce01_sensibilidad_tau.png"
    fig.savefig(p, dpi=130, facecolor=FONDO)
    plt.close(fig)
    hechos.append(p)
    return [mostrar(h) for h in hechos]


# ---------------------------------------------------------------- principal
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--e01", type=Path, required=True)
    ap.add_argument("--tc01", type=Path, required=True)
    ap.add_argument("--hilos", type=int, default=4)
    a = ap.parse_args(argv)
    t0 = time.perf_counter()
    dirs = {"anterior": a.e01.resolve(), "corregido": a.tc01.resolve()}
    res = {"experimento": "CE01 estabilidad del corte", "inicio": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "plan_pruebas_sha256_al_inicio": sha256(RAIZ / "docs" / "PLAN_PRUEBAS.md"),
           "motivacion": ("revisión motivada por el ensayo exploratorio de 2020 (secuencia con tc01); ningún dato de "
                          "2020 se usa: todo con 201908 y 201909, target versión 2; octubre bloqueado"),
           "modelos": {k: mostrar(v) for k, v in dirs.items()}, "meses": list(MESES),
           "target": mostrar(RUTAS.target_2019_v2), "grilla": [float(FRACCIONES[0]), float(FRACCIONES[-1]), 0.00025],
           "ventana_suavizado": G.VENTANA_SUAVIZADO, "verificaciones": {}}
    cfg = {k: json.loads((v / "resultados.json").read_text(encoding="utf-8")) for k, v in dirs.items()}

    pred_cols = json.loads((RUTAS.features_2019 / "manifiesto.json").read_text(encoding="utf-8"))["predictores"]
    con = duckdb.connect()
    con.execute("SET threads = 8")
    dev = {m: cargar(con, (m,), pred_cols, RUTAS.target_2019_v2) for m in MESES}
    con.close()
    meta_ok = True
    for m, (_, clase, cli, _) in dev.items():
        z = np.load(dirs["corregido"] / f"meta_{m}.npz")
        meta_ok &= bool(np.array_equal(z["clase"], clase) and np.array_equal(z["clientes"], cli))
    res["verificaciones"]["desarrollo_igual_a_tc01"] = meta_ok

    cur = {mod: {} for mod in dirs}
    iguales = {}
    for mod, d in dirs.items():
        for obj, (arch, col, npz_e01, npz_tc01, _, _) in OBJETIVOS.items():
            guard = np.load(d / (npz_e01 if mod == "anterior" else npz_tc01))
            preds = {m: [] for m in MESES}
            ok = True
            for i, s in enumerate(cfg[mod]["semillas"]):
                b = lgb.Booster(model_file=str(d / "modelos" / f"{arch}_{s}.txt"))
                for m, (X, _, _, _) in dev.items():
                    pr = b.predict(X, num_threads=a.hilos)
                    pr = pr if col is None else pr[:, col]
                    ok &= bool(np.array_equal(pr.astype("float32"), guard[str(m)][i]))
                    preds[m].append(pr)
            iguales[f"{mod}/{obj}"] = ok
            cur[mod][obj] = {m: curvas(preds[m], dev[m][1], dev[m][2]) for m in MESES}
            print(f"{mod} {obj}: predicciones iguales a las guardadas {ok}", flush=True)
    del dev
    res["verificaciones"]["predicciones_iguales_a_las_guardadas"] = iguales

    # ---- 2. minimax vigente, reproducido
    sel, revision, descomp = {}, {}, {}
    for obj in OBJETIVOS:
        sel[obj] = {"peor": {}, "minimax": {}, "tau": {}, "mve_por_modelo": {}, "sensibilidad": {}}
        revision[obj] = {}
        for mod in dirs:
            c = cur[mod][obj]
            n = {m: c[m]["n"] for m in MESES}
            r = arrep({m: c[m]["gs"] for m in MESES}, n)
            p = peor(r)
            f_mm = elegir(p, 0.0)
            f_lib, _ = G.corte_minimax({m: c[m]["gs"] for m in MESES}, n, FRACCIONES)
            clave = OBJETIVOS[obj][4 if mod == "anterior" else 5]
            f_reg = cfg[mod]["resultados"][clave]["corte"]["fraccion"]
            res["verificaciones"][f"minimax_reproduce/{mod}/{obj}"] = bool(f_mm == f_lib == f_reg)
            res["verificaciones"][f"ganancias_reproducen/{mod}/{obj}"] = all(
                int(c[m]["g"][G.envios(f_reg, c[m]["n"]) - 1]) == cfg[mod]["resultados"][clave]["corte"][m_s]["ganancia"]
                for m, m_s in ((x, str(x)) for x in MESES))
            tau = tau_ruido(c, f_mm)
            sel[obj]["peor"][mod], sel[obj]["minimax"][mod], sel[obj]["tau"][mod] = p, f_mm, tau
            sel[obj]["mve_por_modelo"][mod] = elegir(p, tau)
            orden = np.argsort(p, kind="stable")[:10]
            maximos = {}
            for m in MESES:
                x = c[m]
                ks, kr = int(np.nanargmax(x["gs"])) + 1, int(np.argmax(x["g"])) + 1
                maximos[str(m)] = {"max_suav": M(np.nanmax(x["gs"])), "k_max_suav": ks,
                                   "fraccion_max_suav": round(ks / x["n"], 5), "max_sin_suavizar": M(x["g"].max()),
                                   "k_max_sin_suavizar": kr, "fraccion_max_sin_suavizar": round(kr / x["n"], 5)}
            mesetas = {}
            for t in TAUS:
                mask = p <= np.nanmin(p) + t + 1e-15
                tr = tramos(mask)
                fs = FRACCIONES[mask]
                mesetas[str(t)] = {
                    "tramos": tr, "contigua": len(tr) == 1, "fracciones": int(mask.sum()),
                    "rango_fraccion": [float(fs.min()), float(fs.max())],
                    "por_mes": {str(m): {"envios": [G.envios(fs.min(), c[m]["n"]), G.envios(fs.max(), c[m]["n"])],
                                         "ganancia_suav_min_max": [M(min(c[m]["gs"][G.envios(f, c[m]["n"]) - 1] for f in fs)),
                                                                   M(max(c[m]["gs"][G.envios(f, c[m]["n"]) - 1] for f in fs))]}
                                for m in MESES}}
            revision[obj][mod] = {
                "fraccion_minimax": f_mm, "fraccion_registrada": f_reg, "peor_en_minimax": round(float(p[idx(f_mm)]), 5),
                "arrepentimiento_por_mes_en_minimax": {str(m): round(float(r[m][idx(f_mm)]), 5) for m in MESES},
                "mes_que_define_el_peor": str(max(MESES, key=lambda m: r[m][idx(f_mm)])),
                "maximos_por_mes": maximos,
                "top10": [{"fraccion": float(FRACCIONES[i]), "peor": round(float(p[i]), 5),
                           **{str(m): round(float(r[m][i]), 5) for m in MESES}} for i in orden],
                "en_2_9": {"peor": round(float(p[idx(0.029)]), 5), **{str(m): round(float(r[m][idx(0.029)]), 5) for m in MESES}},
                "mesetas": mesetas}
            # ---- 3. sensibilidad
            sens = {}
            for t in TAUS + [tau]:
                f = elegir(p, t)
                fs_sem = por_semilla(c, t)
                tras = traslado(c, t)
                sens[str(t)] = {"fraccion": f, "seleccion": {"peor_arrepentimiento": round(float(p[idx(f)]), 5),
                                                              "por_mes": en_corte(c, f)},
                                "evaluacion": {"traslado": tras,
                                               "traslado_peor": max(v["arrepentimiento"] for v in tras.values()),
                                               "fraccion_por_semilla": fs_sem,
                                               "rango_semillas": [min(fs_sem), max(fs_sem)],
                                               "desvio_semillas": round(float(np.std(fs_sem, ddof=1)), 5)}}
            sens["tau_calculado"] = tau
            sel[obj]["sensibilidad"][mod] = sens
        sel[obj]["mve"] = sel[obj]["mve_por_modelo"]["corregido"]
        # ---- 1. descomposición
        d = {}
        for f in CORTES:
            d[str(f)] = {mod: en_corte(cur[mod][obj], f) for mod in dirs}
        efectos = {}
        for m in MESES:
            ms = str(m)
            g = {(mod, f): d[str(f)][mod][m]["ganancia"] for mod in dirs for f in (0.029, 0.04475)}
            efectos[ms] = {"reentrenamiento_en_2_9": round(g[("corregido", 0.029)] - g[("anterior", 0.029)], 2),
                           "reentrenamiento_en_4_475": round(g[("corregido", 0.04475)] - g[("anterior", 0.04475)], 2),
                           "corte_con_anteriores": round(g[("anterior", 0.04475)] - g[("anterior", 0.029)], 2),
                           "corte_con_corregidos": round(g[("corregido", 0.04475)] - g[("corregido", 0.029)], 2),
                           "interaccion": round(g[("corregido", 0.04475)] - g[("corregido", 0.029)]
                                                - g[("anterior", 0.04475)] + g[("anterior", 0.029)], 2)}
        descomp[obj] = {"celdas": d, "efectos_ensamble_sin_suavizar_M": efectos}

    # ---- 5. criterio de recomendación (binario corregido)
    s = sel["binario"]["sensibilidad"]["corregido"]
    tau = s["tau_calculado"]
    mm, mve = s["0.0"], s[str(tau)]
    ancho = lambda x: x["evaluacion"]["rango_semillas"][1] - x["evaluacion"]["rango_semillas"][0]
    cond = {"1_rango_semillas_no_mayor": ancho(mve) <= ancho(mm) + 1e-12,
            "2_traslado_peor_no_supera_en_mas_de_tau": mve["evaluacion"]["traslado_peor"] <= mm["evaluacion"]["traslado_peor"] + tau,
            "3_envia_menos": mve["fraccion"] < mm["fraccion"]}
    recomendacion = {"condiciones": cond, "tau": tau, "minimax": mm["fraccion"], "mve": mve["fraccion"],
                     "recomienda": "MVE" if all(cond.values()) else "discutir / conservar minimax",
                     "activa": False, "nota": "no activa ningún corte; tc01 y las corridas existentes no cambian"}

    res["descomposicion"] = descomp
    res["revision_minimax"] = revision
    res["sensibilidad"] = {obj: sel[obj]["sensibilidad"] for obj in OBJETIVOS}
    res["tau_calculado"] = {obj: sel[obj]["tau"] for obj in OBJETIVOS}
    res["mve"] = {obj: sel[obj]["mve_por_modelo"] for obj in OBJETIVOS}
    res["recomendacion_binario_corregido"] = recomendacion
    res["figuras"] = figuras(cur, sel)
    res["verificaciones"]["todas"] = all(v if isinstance(v, bool) else all(v.values())
                                         for v in res["verificaciones"].values())
    res["segundos"] = round(time.perf_counter() - t0, 1)
    destino = RAIZ / "resultados" / "ce01_estabilidad_corte.json"
    destino.write_text(json.dumps(res, indent=2, ensure_ascii=False, default=float) + "\n", encoding="utf-8",
                       newline="\n")
    print(json.dumps({"verificaciones": res["verificaciones"], "tau": res["tau_calculado"], "mve": res["mve"],
                      "recomendacion": recomendacion}, indent=1, ensure_ascii=False, default=float))
    return 0 if res["verificaciones"]["todas"] else 1


if __name__ == "__main__":
    sys.exit(main())
