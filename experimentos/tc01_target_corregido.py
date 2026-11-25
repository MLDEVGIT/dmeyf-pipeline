"""TC01 (paso 2) — reentrena los candidatos de E01 con el target corregido (regla versión 2) y los compara.

Protocolo en docs/PLAN_PRUEBAS.md § 9, escrito antes de correr (se registra su sha256 al inicio).
Igual que E01 salvo el target: 760 features, train 201903–201906, desarrollo 201908–201909 (octubre bloqueado por
evaluacion/particiones.py), semillas 20261124–20261128, hiperparámetros, 300 rondas, binado (max_bin 255,
data_random_seed 1), 8 hilos para entrenar y 4 para predecir. Brazos: binario (BAJA+1 ∪ BAJA+2) y multiclase peso 1
(score P(BAJA+2)).

Comprobaciones previas: configuración de E01; train distinto de E01 sólo en BAJA+1 −5 / CONTINUA +5 (las filas que
cambian con la regla); modelos de E01 reproducidos bit a bit (experimentos.e02_peso_baja1.reusar_e01, con las
etiquetas versión 1); cifras de E01 iguales con las etiquetas versión 2 (BAJA+2 idéntico).

Uso: python -m experimentos.tc01_target_corregido --e01 ejecuciones/e01/<marca>
Salida: ejecuciones/tc01/<marca>/ (modelos <objetivo>_<semilla>.txt, predicciones, resultados.json) y el resumen
versionado resultados/tc01_target_corregido.json.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import platform
import sys
import time
from pathlib import Path

import duckdb
import lightgbm as lgb
import numpy as np
import psutil

from evaluacion import comparacion as C
from evaluacion import ganancia as G
from evaluacion import particiones as P
from evaluacion import target as T
from experimentos.e01_binario_vs_multiclase import CLASES, FRACCIONES, PARAMS, SEMILLAS, cargar, mem
from experimentos.e02_peso_baja1 import reusar_e01, sha256
from pipeline_competencia02.config import RAIZ, RUTAS, mostrar

MINIMO_SEMILLAS = 4
UMBRAL_AUC = 0.005
DESVIOS_ALERTA = 2
BRAZOS = {"binario": ("binario", None), "multiclase_p1": ("multiclase", 2)}  # brazo -> (archivo E01, columna)


def clase_alineada(con, ruta: Path, mes: int, clientes: np.ndarray) -> np.ndarray:
    t = P.leer_target(con, ruta.as_posix(), (mes,)).df().sort_values("numero_de_cliente", kind="stable")
    if not np.array_equal(t["numero_de_cliente"].to_numpy(), clientes):
        raise RuntimeError(f"{mes}: clientes del target distintos de las features")
    return np.array([CLASES[c] for c in t["clase_ternaria"]], dtype="int8")


def rangos(s: np.ndarray) -> np.ndarray:
    return np.argsort(np.argsort(-s, kind="stable"), kind="stable").astype(float)


def comparar_scores(a: np.ndarray, b: np.ndarray) -> dict:
    d = np.abs(a - b)
    return {"pearson": round(float(np.corrcoef(a, b)[0, 1]), 6),
            "correlacion_de_rangos": round(float(np.corrcoef(rangos(a), rangos(b))[0, 1]), 6),
            "dif_abs_media": float(d.mean()), "dif_abs_max": float(d.max()),
            "media_anterior": float(a.mean()), "media_corregido": float(b.mean())}


def enviados(score, cli, k) -> np.ndarray:
    s = np.zeros(len(score), bool)
    s[G.orden(score, cli)[:k]] = True
    return s


def jaccard(a: np.ndarray, b: np.ndarray) -> float:
    return round(float((a & b).sum() / (a | b).sum()), 4)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--e01", type=Path, required=True)
    ap.add_argument("--hilos", type=int, default=8)
    ap.add_argument("--hilos-prediccion", type=int, default=4)
    a = ap.parse_args(argv)
    e01 = a.e01.resolve()
    cfg01 = json.loads((e01 / "resultados.json").read_text(encoding="utf-8"))
    distintos = {k: (cfg01[k], v) for k, v in (("params", PARAMS), ("rondas", 300), ("semillas", SEMILLAS[:5]),
                                                ("hilos_entrenamiento", a.hilos),
                                                ("hilos_prediccion", a.hilos_prediccion)) if cfg01[k] != v}
    if distintos:
        raise SystemExit(f"la configuración de E01 no coincide: {distintos}")
    meta_t = json.loads(RUTAS.target_2019_v2.with_suffix(".json").read_text(encoding="utf-8"))
    if sha256(RUTAS.target_2019_v2) != meta_t["salida"]["sha256"] or meta_t["version"] != T.VERSION:
        raise SystemExit("el target versión 2 no coincide con su procedencia")

    marca = time.strftime("%Y%m%dT%H%M%S") + f"_{os.getpid()}"
    out = RAIZ / "ejecuciones" / "tc01" / marca
    (out / "modelos").mkdir(parents=True)
    t0 = time.perf_counter()
    rep = {"experimento": "TC01 target corregido (regla versión 2)", "marca": marca,
           "inicio": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "plan_pruebas_sha256_al_inicio": sha256(RAIZ / "docs" / "PLAN_PRUEBAS.md"),
           "target": {"regla": T.REGLA, "version": T.VERSION, "archivo": mostrar(RUTAS.target_2019_v2),
                      "sha256": meta_t["salida"]["sha256"], "anterior": mostrar(RUTAS.target_2019)},
           "semillas": cfg01["semillas"], "rondas": cfg01["rondas"], "params": PARAMS,
           "hilos_entrenamiento": a.hilos, "hilos_prediccion": a.hilos_prediccion, "e01": mostrar(e01),
           "particiones": {"train": P.ENTRENAMIENTO, "desarrollo": P.DESARROLLO, "no_leido": P.EVALUACION_FINAL},
           "ganancia": {"premio_bruto": G.PREMIO_BRUTO, "costo_envio": G.COSTO_ENVIO,
                        "neta_por_acierto": G.GANANCIA_NETA_ACIERTO, "ventana_suavizado": G.VENTANA_SUAVIZADO},
           "maquina": {"cpu_logicos": psutil.cpu_count(), "ram_gb": round(psutil.virtual_memory().total / 2**30, 1),
                       "plataforma": platform.platform(), "python": platform.python_version(),
                       "lightgbm": lgb.__version__, "duckdb": duckdb.__version__},
           "tiempos_s": {}, "memoria": {}, "checks": {}}
    (out / "config.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")

    pred = json.loads((RUTAS.features_2019 / "manifiesto.json").read_text(encoding="utf-8"))["predictores"]
    con = duckdb.connect()
    con.execute(f"SET threads = {a.hilos}")
    t = time.perf_counter()
    Xtr, ctr, _, _ = cargar(con, P.ENTRENAMIENTO, pred, RUTAS.target_2019_v2)
    dev = {m: cargar(con, (m,), pred, RUTAS.target_2019_v2) for m in P.DESARROLLO}
    clase_v1 = {m: clase_alineada(con, RUTAS.target_2019, m, d[2]) for m, d in dev.items()}
    con.close()
    rep["tiempos_s"]["carga"] = round(time.perf_counter() - t, 1)
    rep["clases_train"] = {k: int((ctr == v).sum()) for k, v in CLASES.items()}
    rep["clases_train_e01"] = cfg01["clases_train"]
    esperado = dict(cfg01["clases_train"])
    esperado["BAJA+1"] -= 5
    esperado["CONTINUA"] += 5
    rep["checks"]["train_difiere_solo_en_las_5_filas"] = rep["clases_train"] == esperado
    rep["clases_desarrollo"] = {str(m): {"v1": {k: int((clase_v1[m] == v).sum()) for k, v in CLASES.items()},
                                         "v2": {k: int((d[1] == v).sum()) for k, v in CLASES.items()}}
                                for m, d in dev.items()}
    rep["checks"]["baja2_desarrollo_identico"] = all(np.array_equal(clase_v1[m] == 2, d[1] == 2) for m, d in dev.items())
    print(f"carga {rep['tiempos_s']['carga']}s {rep['clases_train']} {rep['checks']} {mem()}", flush=True)
    if not all(rep["checks"].values()):
        raise SystemExit(f"comprobaciones previas fallidas: {rep['checks']}")

    # modelos anteriores: reproducidos con las etiquetas versión 1
    t = time.perf_counter()
    dev_v1 = {m: (d[0], clase_v1[m], d[2], d[3]) for m, d in dev.items()}
    anteriores, compat = reusar_e01(e01, cfg01, dev_v1, a.hilos_prediccion)
    del dev_v1
    rep["tiempos_s"]["comprobacion_e01"] = round(time.perf_counter() - t, 1)
    rep["compatibilidad_e01"] = compat
    rep["checks"]["e01_reproducido"] = compat["compatible"]
    print(f"E01 reproducido: {compat['compatible']}", flush=True)
    if not compat["compatible"]:
        raise SystemExit("no se pudieron reproducir los modelos de E01")

    t = time.perf_counter()
    ds = {"binario": lgb.Dataset(Xtr, label=(ctr > 0).astype("int8"), params={"max_bin": PARAMS["max_bin"],
                                 "data_random_seed": 1, "verbosity": -1}, free_raw_data=True).construct(),
          "multiclase": lgb.Dataset(Xtr, label=ctr, params={"max_bin": PARAMS["max_bin"], "data_random_seed": 1,
                                    "verbosity": -1}, free_raw_data=True).construct()}
    del Xtr
    rep["tiempos_s"]["binado"] = round(time.perf_counter() - t, 1)

    corregidos = {b: {m: [] for m in P.DESARROLLO} for b in BRAZOS}
    tiempos = {b: {"entrenar_s": [], "predecir_s_por_mes": []} for b in BRAZOS}
    for s in cfg01["semillas"]:
        for brazo, (obj, col) in BRAZOS.items():
            p = {**PARAMS, "seed": s, "num_threads": a.hilos}
            p.update({"objective": "binary"} if obj == "binario" else {"objective": "multiclass", "num_class": 3})
            t = time.perf_counter()
            b = lgb.train(p, ds[obj], num_boost_round=cfg01["rondas"])
            tiempos[brazo]["entrenar_s"].append(round(time.perf_counter() - t, 1))
            b.save_model(str(out / "modelos" / f"{obj}_{s}.txt"))
            for m, (X, _, _, _) in dev.items():
                t = time.perf_counter()
                pr = b.predict(X, num_threads=a.hilos_prediccion)
                tiempos[brazo]["predecir_s_por_mes"].append(round(time.perf_counter() - t, 2))
                corregidos[brazo][m].append(pr if col is None else pr[:, col])
            print(f"semilla {s} {brazo}: entrenar {tiempos[brazo]['entrenar_s'][-1]}s {mem()}", flush=True)
    rep["tiempos_s"]["modelos"] = tiempos
    rep["memoria"]["tras_entrenar"] = mem()

    meta = {m: (d[1], d[2]) for m, d in dev.items()}
    res = {"anteriores": {b: C.evaluar_brazo(anteriores[b], meta, FRACCIONES) for b in BRAZOS},
           "corregidos": {b: C.evaluar_brazo(corregidos[b], meta, FRACCIONES) for b in BRAZOS}}
    # las cifras de E01 no dependen de la versión del target (BAJA+2 idéntico)
    rep["checks"]["e01_igual_con_target_v2"] = all(
        res["anteriores"][b]["corte"]["fraccion"] == cfg01["resultados"][obj]["corte"]["fraccion"]
        and all(res["anteriores"][b]["corte"][str(m)]["ganancia"] == cfg01["resultados"][obj]["corte"][str(m)]["ganancia"]
                and res["anteriores"][b]["corte"][str(m)]["por_semilla"]
                == cfg01["resultados"][obj]["corte"][str(m)]["por_semilla"] for m in P.DESARROLLO)
        for b, (obj, _) in BRAZOS.items())

    comp, alertas = {}, {}
    for b in BRAZOS:
        ra, rc = res["anteriores"][b], res["corregidos"][b]
        fa, fc = ra["corte"]["fraccion"], rc["corte"]["fraccion"]
        c = {"fraccion": {"anterior": fa, "corregido": fc, "cambia": fa != fc},
             "arrepentimiento_max": {"anterior": ra["corte"]["arrepentimiento_max"],
                                     "corregido": rc["corte"]["arrepentimiento_max"]},
             "transferencia_peor_caso": {"anterior": ra["transferencia_peor_caso"],
                                         "corregido": rc["transferencia_peor_caso"]},
             "fraccion_por_semilla_rango": {"anterior": ra["corte"]["fraccion_por_semilla_rango"],
                                            "corregido": rc["corte"]["fraccion_por_semilla_rango"]},
             "pareadas_corregido_menos_anterior": C.pareadas(rc, ra, P.DESARROLLO), "meses": {}}
        for m in P.DESARROLLO:
            clase, cli = meta[m]
            b2 = clase == 2
            n = len(cli)
            ea, ec = np.mean(anteriores[b][m], axis=0), np.mean(corregidos[b][m], axis=0)
            ga, gc = G.curva(ea, b2, cli), G.curva(ec, b2, cli)
            ka, kc = G.envios(fa, n), G.envios(fc, n)
            sel_a, sel_c = enviados(ea, cli, ka), enviados(ec, cli, kc)
            sel_c_ka = enviados(ec, cli, ka)
            semillas = []
            for sa, sc in zip(anteriores[b][m], corregidos[b][m]):
                semillas.append({**comparar_scores(sa, sc),
                                 "jaccard_top_k_anterior": jaccard(enviados(sa, cli, ka), enviados(sc, cli, ka))})
            ruido = [jaccard(enviados(x, cli, ka), enviados(y, cli, ka))
                     for x, y in itertools.combinations(anteriores[b][m], 2)]
            c["meses"][str(m)] = {
                "ensamble_scores": comparar_scores(ea, ec), "por_semilla_scores": semillas,
                "envios": {"anterior": ka, "corregido": kc},
                "jaccard_enviados_cada_uno_en_su_corte": jaccard(sel_a, sel_c),
                "jaccard_enviados_mismo_k": jaccard(sel_a, sel_c_ka),
                "ruido_jaccard_entre_semillas_anteriores": [min(ruido), round(float(np.mean(ruido)), 4), max(ruido)],
                "ganancia_ensamble": {"anterior": ra["corte"][str(m)]["ganancia"], "corregido": rc["corte"][str(m)]["ganancia"],
                                      "corregido_en_fraccion_anterior": int(gc[ka - 1]),
                                      "anterior_en_fraccion_corregida": int(ga[kc - 1])},
                "auc_baja2_ensamble": {"anterior": ra["ensamble"][str(m)]["auc_baja2"],
                                       "corregido": rc["ensamble"][str(m)]["auc_baja2"]},
                "semillas_desvio_anterior": ra["corte"][str(m)]["semillas_desvio"]}
        caida = all(c["meses"][str(m)]["ganancia_ensamble"]["corregido"] - c["meses"][str(m)]["ganancia_ensamble"]["anterior"]
                    < -DESVIOS_ALERTA * c["meses"][str(m)]["semillas_desvio_anterior"] for m in P.DESARROLLO)
        auc = all(c["meses"][str(m)]["auc_baja2_ensamble"]["corregido"] - c["meses"][str(m)]["auc_baja2_ensamble"]["anterior"]
                  < -UMBRAL_AUC for m in P.DESARROLLO)
        alertas[b] = {"ganancia_cae_mas_de_2_desvios_en_ambos_meses": caida, "auc_cae_mas_de_0005_en_ambos_meses": auc,
                      "alerta": caida or auc}
        comp[b] = c
    roles = C.regla_adopcion(res["corregidos"]["multiclase_p1"], res["corregidos"]["binario"], P.DESARROLLO,
                             MINIMO_SEMILLAS)
    rep["decision"] = {
        "modelos": "los corregidos reemplazan a los anteriores (consistencia de definición, PLAN_PRUEBAS § 9)",
        "alertas": alertas, "catalogo_activo": "no" if any(x["alerta"] for x in alertas.values()) else "sí",
        "roles_regla_e02_multiclase_vs_binario": roles,
        "recomendacion": "multiclase_p1" if roles["adopta"] else "binario",
        "fracciones": {b: res["corregidos"][b]["corte"]["fraccion"] for b in BRAZOS}}
    rep["comparacion"] = comp
    rep["resultados"] = res["corregidos"]
    rep["anteriores"] = res["anteriores"]
    for b in BRAZOS:
        np.savez_compressed(out / f"pred_{b}.npz", **{str(m): np.vstack(l).astype("float32")
                                                       for m, l in corregidos[b].items()})
    for m in P.DESARROLLO:
        np.savez_compressed(out / f"meta_{m}.npz", clase=meta[m][0], clientes=meta[m][1])
    rep["tiempos_s"]["total"] = round(time.perf_counter() - t0, 1)
    rep["memoria"]["final"] = mem()
    rep["fin"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    (out / "resultados.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=float), encoding="utf-8")

    resumen = {k: rep[k] for k in ("experimento", "marca", "inicio", "fin", "plan_pruebas_sha256_al_inicio", "target",
                                   "semillas", "rondas", "params", "hilos_entrenamiento", "hilos_prediccion", "e01",
                                   "particiones", "ganancia", "maquina", "clases_train", "clases_train_e01",
                                   "clases_desarrollo", "checks", "tiempos_s", "memoria", "decision", "comparacion")}
    resumen["origen_modelos"] = mostrar(out)
    resumen["compatibilidad_e01"] = {k: v for k, v in compat.items() if k != "tiempos_reprediccion_s"}
    resumen["resultados"] = {b: {k: v[k] for k in ("corte", "ensamble", "transferencia", "transferencia_peor_caso")}
                             for b, v in res["corregidos"].items()}
    resumen["anteriores"] = {b: {k: v[k] for k in ("corte", "ensamble", "transferencia", "transferencia_peor_caso")}
                             for b, v in res["anteriores"].items()}
    (RAIZ / "resultados" / "tc01_target_corregido.json").write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False, default=float) + "\n", encoding="utf-8", newline="\n")
    print(f"listo en {rep['tiempos_s']['total']}s -> {mostrar(out)}; checks {rep['checks']}; "
          f"decisión {json.dumps({k: v for k, v in rep['decision'].items() if k != 'roles_regla_e02_multiclase_vs_binario'}, ensure_ascii=False)}; "
          f"roles adopta={roles['adopta']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
