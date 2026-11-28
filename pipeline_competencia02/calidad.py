"""Calidad de datos: cada variable del mes contra su propia historia (diseño, decisión 8).

El problema conocido son variables que llegan rotas: están en el archivo pero vienen todas en cero (7 en 201905 y 10 en
201910 según esta regla, resultados/c01_calidad_2019.json; unas 30 en 202006). La detección no depende de una lista de variables: para cada variable mide, en el mes, la
proporción de ceros y la de faltantes, y la compara con la mediana de esas proporciones en los meses anteriores.

La proporción de ceros se mide sobre los valores observados (no nulos) y la de faltantes sobre todas las filas: una
variable que vale NULL hasta un mes y desde ahí trae valores (cmobile_app_trx desde 201907) no está rota, y medida
sobre todas las filas su proporción de ceros saltaría de 0 a 45 %. Un mes sin ningún valor observado no tiene
proporción de ceros y no entra en la mediana.

Una variable está **rota** en el mes cuando, para ceros o para faltantes:
  - casi todo el mes es eso (más de `casi_todo`, 99,9 %) y en su historia no lo era (mediana menor que `mediana_max`,
    95 %): así una variable que siempre fue casi toda cero no se marca; o
  - la proporción sube más de `salto` (30 puntos) respecto de la mediana de su historia.
Solo cuenta la suba: una variable que pasa de casi toda cero a tener valores no está rota.

Los umbrales están en `politica_incidentes.json` (sección `calidad`), calibrados solo con 201901–201912
(`scripts/calibrar_calidad.py`, resultado en `resultados/c01_calidad_2019.json`).
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import median

POLITICA = Path(__file__).with_name("politica_incidentes.json")
CLAVES = ("numero_de_cliente", "foto_mes")


def umbrales(path: Path = POLITICA) -> dict:
    pol = json.loads(path.read_text(encoding="utf-8"))
    return {"version_politica": pol["version"], **pol["calidad"]}


def proporciones_por_mes(con, fuente: str, columnas: list[str]) -> dict[int, dict[str, dict]]:
    """{foto_mes: {variable: {"ceros": p | None, "nulos": p}}}: ceros sobre los observados (None si no hay ninguno),
    nulos sobre todas las filas. `fuente` es SQL de DuckDB (una tabla, o read_parquet(...)) con la columna foto_mes."""
    columnas = [c for c in columnas if c not in CLAVES]
    partes = []
    for c in columnas:
        q = f'"{c}"'
        partes.append(f"avg(CASE WHEN {q} = 0 THEN 1.0 WHEN {q} IS NOT NULL THEN 0.0 END)")  # avg ignora NULL
        partes.append(f"avg(CASE WHEN {q} IS NULL THEN 1.0 ELSE 0.0 END)")
    filas = con.execute(f"SELECT foto_mes, {', '.join(partes)} FROM {fuente} GROUP BY foto_mes ORDER BY foto_mes").fetchall()
    out = {}
    for fila in filas:
        valores = fila[1:]
        out[int(fila[0])] = {c: {"ceros": None if valores[2 * i] is None else float(valores[2 * i]),
                                 "nulos": float(valores[2 * i + 1])} for i, c in enumerate(columnas)}
    return out


def detectar(mes: dict[str, dict], anteriores: list[dict[str, dict]], u: dict) -> dict[str, dict]:
    """Decisión por variable del mes. `mes` = {variable: {"ceros", "nulos"}}; `anteriores`, lo mismo para cada mes previo.
    Sin meses anteriores no hay contra qué comparar: ninguna variable se marca."""
    out = {}
    for var, p in mes.items():
        previas = [a[var] for a in anteriores if var in a]
        d = {"ceros": p["ceros"], "nulos": p["nulos"], "rota": False, "motivo": None}
        if previas:
            for medida in ("ceros", "nulos"):
                historia = [x[medida] for x in previas if x[medida] is not None]
                if p[medida] is None or not historia:
                    continue
                mediana = median(historia)
                d[f"mediana_{medida}"] = mediana
                if d["rota"]:
                    continue
                if p[medida] > u["casi_todo"] and mediana < u["mediana_max"]:
                    d["rota"], d["motivo"] = True, f"{medida}_casi_todo"
                elif p[medida] - mediana > u["salto"]:
                    d["rota"], d["motivo"] = True, f"{medida}_salto"
        out[var] = d
    return out


def rotas(decisiones: dict[str, dict]) -> list[str]:
    return sorted(v for v, d in decisiones.items() if d["rota"])


def detectar_historia(props: dict[int, dict[str, dict]], u: dict) -> dict[int, list[str]]:
    """Corre la detección mes a mes, cada mes contra todos los anteriores: {mes: variables rotas}."""
    meses = sorted(props)
    return {m: rotas(detectar(props[m], [props[a] for a in meses[:i]], u)) for i, m in enumerate(meses) if i > 0}
