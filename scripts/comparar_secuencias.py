"""Compara dos carpetas de ejecución del pipeline mensual mes a mes (p. ej. catálogo e01 contra tc01). Sin etiquetas
nuevas: usa lo publicado (decisiones, salida oficial) y la retrospectiva ya calculada en cada carpeta.

Por mes y por rol (recomendación, alternativa): envíos, Jaccard del conjunto enviado entre corridas, correlación de
rangos del score, probabilidad mínima enviada; coincidencia entre estrategias dentro de cada corrida; salida oficial
(Jaccard de enviar=1 y correlación de rangos de la probabilidad); métricas retrospectivas de ambas (misma regla);
distribución del score por rol; estado de calidad y reglas de incidentes (anomalías de la entrada); tiempo del mes
(interno y, si existe pruebas/secuencia_*.json, la pared con arranque) y memoria pico.

Uso: python scripts/comparar_secuencias.py --anterior <carpeta> --nueva <carpeta> --salida <json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROLES = ("recomendacion_provisional", "alternativa")


def rangos(s):
    return np.argsort(np.argsort(-s, kind="stable"), kind="stable").astype(float)


def corr_rangos(a, b) -> float:
    return round(float(np.corrcoef(rangos(a), rangos(b))[0, 1]), 6)


def jaccard(a, b) -> float:
    return round(float((a & b).sum() / (a | b).sum()), 4)


def cargar(env: Path, mes: int) -> dict:
    cat = json.loads((env / "modelos" / "estrategias.json").read_text(encoding="utf-8"))
    dec = pd.read_csv(env / "diagnosticos" / str(mes) / f"decisiones_{mes}.csv", float_precision="round_trip") \
        .sort_values("numero_de_cliente", kind="stable")
    out = pd.read_csv(env / "output" / f"churn_{mes}.csv", float_precision="round_trip") \
        .sort_values("numero_de_cliente", kind="stable")
    rep = json.loads((env / "diagnosticos" / str(mes) / "reporte.json").read_text(encoding="utf-8"))
    est = json.loads((env / "registro" / "meses" / f"{mes}.json").read_text(encoding="utf-8"))
    retro_p = env / "registro" / "retrospectiva" / f"{mes}.json"
    roles = {e["rol"]: e["id"] for e in cat["estrategias"]}
    pared = {}
    for s in sorted((env / "pruebas").glob("secuencia_*.json")) if (env / "pruebas").exists() else []:
        pared.update({x["mes"]: x.get("tiempo_total_s") for x in json.loads(s.read_text(encoding="utf-8"))["meses"]})
    return {"cli": dec["numero_de_cliente"].to_numpy(np.int64),
            "p": {r: dec[f"probabilidad_{i}"].to_numpy(np.float64) for r, i in roles.items()},
            "env": {r: dec[f"enviar_{i}"].to_numpy() == 1 for r, i in roles.items()},
            "ids": roles, "salida_cli": out["numero_de_cliente"].to_numpy(np.int64),
            "salida_p": out["probabilidad"].to_numpy(np.float64), "salida_env": out["enviar"].to_numpy() == 1,
            "rep": rep, "dist": {e["rol"]: e["distribucion"] for e in rep["estrategias"]}, "est": est, "catalogo": cat.get("nombre", "e01"), "pared": pared.get(mes),
            "retro": json.loads(retro_p.read_text(encoding="utf-8")) if retro_p.exists() else None}


def resumen_retro(r: dict | None) -> dict:
    if not r:
        return {"estado": "sin calcular"}
    out = {"estado": r["disponibilidad"]["estado"], "version_regla": r["version"]}
    if r["disponibilidad"]["estado"] == "completa":
        out["clases"] = {k: r["clases"][k] for k in ("BAJA+1", "BAJA+2", "CONTINUA")}
        for e in r["estrategias"]:
            out[e["rol"]] = {k: e[k] for k in ("envios", "baja2_enviados", "ganancia", "auc_baja2",
                                               "ganancia_maxima_ex_post")}
    elif r["disponibilidad"]["estado"] == "parcial":
        out["provisional_ausentes_en_t1"] = r["provisional"]["ausentes_en_t1"]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--anterior", type=Path, required=True)
    ap.add_argument("--nueva", type=Path, required=True)
    ap.add_argument("--salida", type=Path, required=True)
    a = ap.parse_args(argv)
    meses = sorted(int(p.name) for p in (a.nueva / "diagnosticos").iterdir() if p.name.isdigit())
    res = {"anterior": a.anterior.name, "nueva": a.nueva.name, "meses": {}}
    for m in meses:
        x, y = cargar(a.anterior, m), cargar(a.nueva, m)
        if not (np.array_equal(x["cli"], y["cli"]) and np.array_equal(x["salida_cli"], y["salida_cli"])):
            raise SystemExit(f"{m}: clientes distintos entre corridas")
        d = {"clientes": int(len(x["cli"])), "catalogos": [x["catalogo"], y["catalogo"]], "por_rol": {}}
        for r in ROLES:
            d["por_rol"][r] = {
                "ids": [x["ids"][r], y["ids"][r]],
                "envios": [int(x["env"][r].sum()), int(y["env"][r].sum())],
                "jaccard_enviados_entre_corridas": jaccard(x["env"][r], y["env"][r]),
                "solo_anterior": int((x["env"][r] & ~y["env"][r]).sum()),
                "solo_nueva": int((y["env"][r] & ~x["env"][r]).sum()),
                "correlacion_de_rangos_score": corr_rangos(x["p"][r], y["p"][r]),
                "probabilidades_identicas": bool(np.array_equal(x["p"][r], y["p"][r])),
                "probabilidad_minima_enviada": [float(x["p"][r][x["env"][r]].min()), float(y["p"][r][y["env"][r]].min())]}
        d["coincidencia_entre_estrategias"] = [x["rep"]["coincidencia"]["jaccard"], y["rep"]["coincidencia"]["jaccard"]]
        d["salida_oficial"] = {"jaccard_enviar": jaccard(x["salida_env"], y["salida_env"]),
                               "correlacion_de_rangos_probabilidad": corr_rangos(x["salida_p"], y["salida_p"]),
                               "identica": bool(np.array_equal(x["salida_p"], y["salida_p"])
                                                and np.array_equal(x["salida_env"], y["salida_env"]))}
        d["tiempo_total_desde_entrada_s"] = [x["est"].get("total_desde_entrada_s"), y["est"].get("total_desde_entrada_s")]
        d["tiempo_pared_con_arranque_s"] = [x["pared"], y["pared"]]
        d["tiempos_internos"] = [x["rep"]["tiempos"], y["rep"]["tiempos"]]
        d["memoria"] = [x["rep"]["memoria"], y["rep"]["memoria"]]
        d["distribucion"] = {r: [{"media": z["dist"][r]["media"], "mayor_0_5": z["dist"][r]["mayor_0_5"],
                                  **{f"q{q}": z["dist"][r]["cuantiles"][q] for q in ("0.5", "0.9", "0.99", "0.999")}}
                                 for z in (x, y)] for r in ROLES}
        reglas = [sorted({i["regla"] for i in z["rep"]["incidentes"]}) for z in (x, y)]
        d["anomalias"] = {"estado_calidad": [x["rep"]["estado_calidad"], y["rep"]["estado_calidad"]],
                          "reglas": reglas, "iguales": reglas[0] == reglas[1]
                          and x["rep"].get("categorias_columnas") == y["rep"].get("categorias_columnas")}
        d["retrospectiva"] = [resumen_retro(x["retro"]), resumen_retro(y["retro"])]
        res["meses"][str(m)] = d
        print(m, json.dumps({k: d[k] for k in ("por_rol", "coincidencia_entre_estrategias", "salida_oficial")},
                            ensure_ascii=False))
    a.salida.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
