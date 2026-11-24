"""Diagnóstico de las columnas con todos los observados en 0 de un mes ya publicado (caso 202006).

NO cambia el pipeline ni lo publicado: lee la carpeta de ejecución y escribe un JSON aparte. Sin etiquetas.

1. Columnas: las de categorias_columnas.observados_en_cero del reporte del mes. Para cada una, en la historia de
   la ejecución: en cuántos meses previos ya tuvo todos los observados en 0 ("con precedente") y qué fracción de
   observados distintos de 0 tenía el mes anterior.
2. Peso en los modelos: fracción de la importancia por ganancia (promedio de las 5 semillas) que corresponde a
   features derivadas de esas columnas, separando las del mes (cruda, delta1, delta2: afectadas por el 0) de los
   lags (lag1, lag2: vienen de meses anteriores, no afectadas).
3. Contrafácticos sobre las features publicadas del mes, con los mismos modelos, promedio y corte de cada estrategia:
     A  publicado (las columnas en 0, como llegaron)          -> predicciones_<mes>.parquet
     N  esas columnas como faltantes: cruda, delta1 y delta2 = NaN
     L  último valor: cruda = lag1, delta1 = 0, delta2 = lag1 − lag2 (NaN si falta el lag)
   Para cada uno: distribución del score, probabilidad mínima enviada, coincidencia de la selección con A
   (Jaccard, clientes que entran y salen), correlación de rangos con A y coincidencia entre estrategias.
   Escala de referencia: Jaccard de la selección de cada semilla sola contra la del ensamble, en A.
N y L son contrafácticos para dimensionar el efecto, no tratamientos adoptados: cualquier tratamiento se decide
con E06 en meses de 2019 (R1).

Uso: python scripts/analizar_columnas_en_cero.py --ejecucion <carpeta> --mes 202006 --salida <json>
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

RAIZ = Path(__file__).resolve().parents[1]


def q(c: str) -> str:
    return '"' + c.replace('"', '""') + '"'


def seleccion(clientes, p, fraccion):
    k = math.ceil(fraccion * len(p))
    s = np.zeros(len(p), bool)
    s[np.lexsort((clientes, -p))[:k]] = True
    return s


def rangos(p):
    return np.argsort(np.argsort(-p))


def comparar(a_sel, b_sel, a_p, b_p) -> dict:
    inter, union = int((a_sel & b_sel).sum()), int((a_sel | b_sel).sum())
    return {"jaccard": round(inter / union, 4), "interseccion": inter, "entran": int((b_sel & ~a_sel).sum()),
            "salen": int((a_sel & ~b_sel).sum()),
            "correlacion_de_rangos": round(float(np.corrcoef(rangos(a_p), rangos(b_p))[0, 1]), 4)}


def resumen_score(p, sel) -> dict:
    return {"media": round(float(p.mean()), 6), "p50": float(np.quantile(p, .5)), "p99": float(np.quantile(p, .99)),
            "probabilidad_minima_enviada": float(p[sel].min()), "envios": int(sel.sum())}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ejecucion", type=Path, required=True)
    ap.add_argument("--mes", type=int, required=True)
    ap.add_argument("--salida", type=Path, required=True)
    a = ap.parse_args(argv)
    env, mes = a.ejecucion.resolve(), a.mes
    t0 = time.perf_counter()
    diag = env / "diagnosticos" / str(mes)
    rep = json.loads((diag / "reporte.json").read_text(encoding="utf-8"))
    cat = json.loads((env / "modelos" / "estrategias.json").read_text(encoding="utf-8"))
    pred = [c for c, _ in json.loads((env / "modelos" / "predictores.json").read_text(encoding="utf-8"))["predictores"]]
    cols = rep["categorias_columnas"].get("observados_en_cero", [])
    if not cols:
        print("el mes no tiene columnas con todos los observados en 0")
        return 1
    con = duckdb.connect()
    con.execute("SET threads = 4")

    # 1. precedente en la historia de la ejecución
    hist = sorted((env / "historia").glob("foto_mes=*.parquet"))
    previos = [p for p in hist if int(p.stem.split("=")[1]) < mes]
    precedente = {c: [] for c in cols}
    frac_prev = {}
    for p in previos:
        m = int(p.stem.split("=")[1])
        agg = ", ".join(f"count({q(c)}), count(*) FILTER (WHERE {q(c)} <> 0)" for c in cols)
        fila = con.execute(f"SELECT {agg} FROM read_parquet('{p.as_posix()}')").fetchone()
        for i, c in enumerate(cols):
            nn, nz = fila[2 * i], fila[2 * i + 1]
            if nn and not nz:
                precedente[c].append(m)
            if p == previos[-1]:
                frac_prev[c] = round(nz / nn, 4) if nn else None
    columnas = {c: {"meses_previos_todo_en_cero": precedente[c], "fraccion_no_cero_mes_anterior": frac_prev.get(c)}
                for c in cols}
    sin_precedente = sorted(c for c in cols if not precedente[c])

    # 2. peso en los modelos
    afect = {c for c in cols} | {f"{c}_{s}" for c in cols for s in ("delta1", "delta2")}
    lags = {f"{c}_{s}" for c in cols for s in ("lag1", "lag2")}
    boosters, peso = {}, {}
    for e in cat["estrategias"]:
        boosters[e["id"]] = [lgb.Booster(model_file=str(env / "modelos" / m["archivo"])) for m in e["modelos"]]
        imp = np.mean([b.feature_importance("gain") for b in boosters[e["id"]]], axis=0)
        tot = imp.sum()
        por = dict(zip(pred, imp))
        top = sorted(((f, v / tot) for f, v in por.items() if f in afect), key=lambda x: -x[1])[:10]
        peso[e["id"]] = {"fraccion_ganancia_cruda_y_deltas_del_mes": round(sum(por[f] for f in afect) / tot, 4),
                         "fraccion_ganancia_lags": round(sum(por[f] for f in lags) / tot, 4),
                         "top10_afectadas": [[f, round(v, 4)] for f, v in top]}

    # 3. contrafácticos
    feat = (diag / f"features_{mes}.parquet").as_posix()
    tipos = {c: t for c, t, *_ in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{feat}')").fetchall()}
    expr = ", ".join(f"CAST({q(c)} AS DOUBLE) AS {q(c)}" if tipos[c] == "BIGINT" else q(c) for c in pred)
    df = con.execute(f"SELECT numero_de_cliente, {expr} FROM read_parquet('{feat}') ORDER BY numero_de_cliente").df()
    clientes = df["numero_de_cliente"].to_numpy(np.int64)
    X = np.array(df[pred].to_numpy(np.float64, na_value=np.nan), copy=True)  # escribible: se modifica en el lugar
    del df
    publ = con.execute(f"SELECT * FROM read_parquet('{(diag / f'predicciones_{mes}.parquet').as_posix()}') "
                       f"ORDER BY numero_de_cliente").df()
    con.close()
    if not np.array_equal(publ["numero_de_cliente"].to_numpy(np.int64), clientes):
        raise RuntimeError("clientes de features y predicciones distintos")
    idx = {c: i for i, c in enumerate(pred)}
    original = {f: X[:, idx[f]].copy() for c in cols for f in (c, f"{c}_delta1", f"{c}_delta2")}

    def aplicar(variante: str):
        for c in cols:
            l1, l2 = X[:, idx[f"{c}_lag1"]], X[:, idx[f"{c}_lag2"]]
            if variante == "N":
                X[:, idx[c]] = np.nan
                X[:, idx[f"{c}_delta1"]] = np.nan
                X[:, idx[f"{c}_delta2"]] = np.nan
            elif variante == "L":
                X[:, idx[c]] = l1
                X[:, idx[f"{c}_delta1"]] = np.where(np.isnan(l1), np.nan, 0.0)
                X[:, idx[f"{c}_delta2"]] = l1 - l2
            else:
                for f, v in original.items():
                    X[:, idx[f]] = v

    scores = {"A": {e["id"]: publ[f"{e['id']}__ensamble"].to_numpy() for e in cat["estrategias"]}}
    for v in ("N", "L"):
        aplicar(v)
        scores[v] = {}
        for e in cat["estrategias"]:
            ps = [b.predict(X, num_threads=4) for b in boosters[e["id"]]]
            if e["columna_score"] is not None:
                ps = [p[:, e["columna_score"]] for p in ps]
            scores[v][e["id"]] = np.mean(ps, axis=0)
        aplicar("A")
    if not all(np.array_equal(X[:, idx[f]], v, equal_nan=True) for f, v in original.items()):
        raise RuntimeError("no se restauraron las features")

    frac = {e["id"]: e["corte"]["fraccion"] for e in cat["estrategias"]}
    rol = {e["id"]: e["rol"] for e in cat["estrategias"]}
    ids = sorted(frac, key=lambda i: rol[i] != "recomendacion_provisional")
    sel = {v: {i: seleccion(clientes, scores[v][i], frac[i]) for i in ids} for v in scores}
    variantes = {}
    for v in scores:
        variantes[v] = {"por_estrategia": {i: {**resumen_score(scores[v][i], sel[v][i]),
                                               **({"contra_A": comparar(sel["A"][i], sel[v][i], scores["A"][i],
                                                                        scores[v][i])} if v != "A" else {})}
                                           for i in ids},
                        "coincidencia_entre_estrategias": comparar(sel[v][ids[0]], sel[v][ids[1]],
                                                                   scores[v][ids[0]], scores[v][ids[1]])}
    referencia = {}
    for e in cat["estrategias"]:
        js = []
        for m in e["modelos"]:
            s = seleccion(clientes, publ[f"{e['id']}__semilla_{m['semilla']}"].to_numpy(), frac[e["id"]])
            js.append(comparar(sel["A"][e["id"]], s, scores["A"][e["id"]], scores["A"][e["id"]])["jaccard"])
        referencia[e["id"]] = {"jaccard_semilla_sola_vs_ensamble": [min(js), max(js)]}

    out = {"mes": mes, "ejecucion": env.name, "columnas_observados_en_cero": len(cols),
           "sin_precedente_en_historia": sin_precedente, "con_precedente": sorted(set(cols) - set(sin_precedente)),
           "historia_revisada": f"{previos[0].stem.split('=')[1]}–{previos[-1].stem.split('=')[1]}",
           "columnas": columnas, "peso_en_modelos": peso, "variantes": variantes,
           "referencia_ruido_semillas": referencia,
           "nota": "diagnóstico: A es lo publicado; N y L son contrafácticos, no tratamientos adoptados (E06, R1). "
                   "Sin etiquetas: el efecto en ganancia de 202006 no se puede medir hasta tener 202007 y 202008.",
           "segundos": round(time.perf_counter() - t0, 1)}
    a.salida.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: out[k] for k in ("columnas_observados_en_cero", "sin_precedente_en_historia", "peso_en_modelos",
                                          "referencia_ruido_semillas", "segundos")}, indent=1, ensure_ascii=False))
    for v, d in variantes.items():
        print(v, json.dumps(d, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
