"""Verifica un churn_<yyyymm>.csv sin usar etiquetas.

Chequeos:
  - nombre del archivo churn_<yyyymm>.csv;
  - cabecera exacta: numero_de_cliente,probabilidad,enviar;
  - numero_de_cliente entero, no nulo y sin duplicados;
  - probabilidad finita y en [0, 1];
  - enviar en {0, 1}, con al menos un envío;
  - coherencia de la selección: toda probabilidad enviada >= toda probabilidad no enviada;
  - con --entrada: los clientes son exactamente los del CSV del mes (y su foto_mes coincide);
  - con --envios N: la cantidad de envíos es N.

Uso:
  python scripts/verificar_salida.py <churn_AAAAMM.csv> [--entrada <AAAAMM.csv>] [--envios N]
Código de salida: 0 si pasan todos, 1 si alguno falla.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

COLUMNAS = ["numero_de_cliente", "probabilidad", "enviar"]


def verificar(salida: Path, entrada: Path | None = None, envios: int | None = None) -> dict:
    checks: dict[str, bool] = {}
    info: dict = {"archivo": str(salida)}
    m = re.fullmatch(r"churn_(\d{6})\.csv", salida.name)
    checks["nombre_churn_yyyymm"] = m is not None
    mes = int(m.group(1)) if m else None

    with open(salida, encoding="utf-8") as f:
        cabecera = f.readline().rstrip("\r\n").split(",")
    checks["cabecera_exacta"] = cabecera == COLUMNAS
    info["cabecera"] = cabecera

    df = pd.read_csv(salida, dtype={"numero_de_cliente": "Int64"})
    info["filas"] = len(df)
    cli = df["numero_de_cliente"] if "numero_de_cliente" in df else pd.Series(dtype="Int64")
    prob = pd.to_numeric(df.get("probabilidad", pd.Series(dtype=float)), errors="coerce").to_numpy(float)
    env = df.get("enviar", pd.Series(dtype=float))

    checks["clientes_no_nulos"] = len(df) > 0 and not cli.isna().any()
    info["clientes_duplicados"] = int(cli.duplicated().sum())
    checks["clientes_sin_duplicados"] = info["clientes_duplicados"] == 0
    checks["probabilidad_finita_en_0_1"] = bool(len(prob) and np.isfinite(prob).all()
                                                and (prob >= 0).all() and (prob <= 1).all())
    checks["enviar_binario"] = bool(len(env) and env.isin([0, 1]).all())
    n_env = int((env == 1).sum())
    info["envios"] = n_env
    info["proporcion_envios"] = round(n_env / len(df), 6) if len(df) else None
    checks["al_menos_un_envio"] = n_env > 0
    if checks["enviar_binario"] and 0 < n_env < len(df) and np.isfinite(prob).all():
        e = env.to_numpy() == 1
        checks["envios_son_los_de_mayor_probabilidad"] = bool(prob[e].min() >= prob[~e].max())
        info["umbral_efectivo"] = float(prob[e].min())
    info["probabilidad"] = {q: float(np.quantile(prob, q)) for q in (0, 0.5, 0.99, 1)} if len(prob) else {}

    if envios is not None:
        checks["envios_igual_al_esperado"] = n_env == envios
    if entrada is not None:
        ent = pd.read_csv(entrada, usecols=["numero_de_cliente", "foto_mes"])
        checks["cobertura_igual_a_la_entrada"] = (set(ent["numero_de_cliente"]) == set(cli.dropna().astype(int))
                                                   and len(ent) == len(df))
        if mes is not None:
            checks["foto_mes_de_la_entrada_igual_al_nombre"] = set(ent["foto_mes"].unique()) == {mes}

    return {"ok": all(checks.values()), "mes": mes, "checks": checks, "info": info}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("salida", type=Path)
    ap.add_argument("--entrada", type=Path)
    ap.add_argument("--envios", type=int)
    a = ap.parse_args(argv)
    r = verificar(a.salida, a.entrada, a.envios)
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
