"""Verifica que los scores del pipeline mensual coincidan con los modelos ORIGINALES de E01.

Para un mes completado de una carpeta de ejecución:
  1. carga los modelos originales de E01 (ejecuciones/e01/<marca>/modelos, sin nombres de features), según el
     campo `origen` de cada modelo del catálogo, y comprueba su sha256;
  2. los aplica a diagnosticos/<mes>/features_<mes>.parquet (BIGINT -> float64 exacto, NULL -> NaN);
  3. compara bit a bit cada semilla y el ensamble (np.mean, en el orden del catálogo) con predicciones_<mes>.parquet;
  4. recalcula las decisiones con la fracción del catálogo y las compara con decisiones_<mes>.csv y con
     output/churn_<mes>.csv (probabilidad y enviar de la recomendación).

Los CSV se leen con float_precision="round_trip": el parser por defecto de pandas puede diferir en 1 ulp.

Uso: python scripts/verificar_scores.py --ejecucion <carpeta> --mes 202001
Código de salida 0 si todo coincide.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import duckdb
import lightgbm as lgb
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ejecucion", type=Path, required=True)
    ap.add_argument("--mes", type=int, required=True)
    a = ap.parse_args(argv)
    env, mes = a.ejecucion.resolve(), a.mes
    cat = json.loads((env / "modelos" / "estrategias.json").read_text(encoding="utf-8"))
    pred = [c for c, _ in json.loads((env / "modelos" / "predictores.json").read_text(encoding="utf-8"))["predictores"]]
    diag = env / "diagnosticos" / str(mes)
    con = duckdb.connect()
    tipos = {c: t for c, t, *_ in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{(diag / f'features_{mes}.parquet').as_posix()}')").fetchall()}
    expr = ", ".join(f'CAST("{c}" AS DOUBLE) AS "{c}"' if tipos[c] == "BIGINT" else f'"{c}"' for c in pred)
    f = con.execute(f"SELECT numero_de_cliente, {expr} FROM read_parquet('{(diag / f'features_{mes}.parquet').as_posix()}') "
                    f"ORDER BY numero_de_cliente").df()
    clientes = f["numero_de_cliente"].to_numpy(np.int64)
    X = f[pred].to_numpy(np.float64, na_value=np.nan)
    del f
    p = con.execute(f"SELECT * FROM read_parquet('{(diag / f'predicciones_{mes}.parquet').as_posix()}') "
                    f"ORDER BY numero_de_cliente").df()
    con.close()
    dec = pd.read_csv(diag / f"decisiones_{mes}.csv", float_precision="round_trip").sort_values("numero_de_cliente", kind="stable")
    churn = pd.read_csv(env / "output" / f"churn_{mes}.csv", float_precision="round_trip").sort_values("numero_de_cliente", kind="stable")
    res = {"clientes_iguales": bool(np.array_equal(clientes, p["numero_de_cliente"].to_numpy())
                                   and np.array_equal(clientes, dec["numero_de_cliente"].to_numpy())
                                   and np.array_equal(clientes, churn["numero_de_cliente"].to_numpy())),
           "estrategias": {}}
    for e in cat["estrategias"]:
        r = {"semillas_identicas": [], "sha256_original_ok": []}
        preds = []
        for m in e["modelos"]:
            orig = RAIZ / m["origen"]
            r["sha256_original_ok"].append(sha256(orig) == m["sha256_origen"])
            b = lgb.Booster(model_file=str(orig))
            pr = b.predict(X, num_threads=4)
            pr = pr if e["columna_score"] is None else pr[:, e["columna_score"]]
            preds.append(pr)
            r["semillas_identicas"].append(bool(np.array_equal(pr, p[f"{e['id']}__semilla_{m['semilla']}"].to_numpy())))
        ens = np.mean(preds, axis=0)
        r["ensamble_identico"] = bool(np.array_equal(ens, p[f"{e['id']}__ensamble"].to_numpy()))
        r["probabilidad_en_decisiones_identica"] = bool(np.array_equal(ens, dec[f"probabilidad_{e['id']}"].to_numpy()))
        k = math.ceil(e["corte"]["fraccion"] * len(clientes))
        orden = np.lexsort((clientes, -ens))
        enviar = np.zeros(len(clientes), np.int8)
        enviar[orden[:k]] = 1
        r["envios_esperados"] = k
        r["decisiones_identicas"] = bool(np.array_equal(enviar, dec[f"enviar_{e['id']}"].to_numpy()))
        if e["rol"] == "recomendacion_provisional":
            r["salida_oficial_probabilidad_identica"] = bool(np.array_equal(ens, churn["probabilidad"].to_numpy()))
            r["salida_oficial_enviar_identico"] = bool(np.array_equal(enviar, churn["enviar"].to_numpy()))
        r["ok"] = all(all(v) if isinstance(v, list) else v for k2, v in r.items() if k2 != "envios_esperados")
        res["estrategias"][e["id"]] = r
    res["ok"] = res["clientes_iguales"] and all(r["ok"] for r in res["estrategias"].values())
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
