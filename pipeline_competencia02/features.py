"""Lógica de features compartida entre experimento_sampling/04 y el pipeline mensual.

Definición (ver experimento_sampling/README.md, sección 04):
  - lag_k: k-ésima observación previa del cliente,
    lag(x, k) OVER (PARTITION BY numero_de_cliente ORDER BY foto_mes), como z402.
  - delta_k = x - lag_k (NULL si alguno es NULL).
  - Se aplican a las 152 variables originales, que también se conservan.
  - Sin indicadores, imputaciones ni correcciones; sólo observaciones previas.

Este código se movió sin cambios desde 04_generar_features.py; las
features publicadas por 04 se generaron con él.
"""
from __future__ import annotations

KEYS = ["numero_de_cliente", "foto_mes"]
SUFIJOS = ["lag1", "delta1", "lag2", "delta2"]


def q(c: str) -> str:
    return '"' + c.replace('"', '""') + '"'


def nombres(cols: list[str]) -> list[str]:
    return cols + [f"{c}_{s}" for s in SUFIJOS for c in cols]


def crear_prev(con, src: str):
    """Mes de la 1ª y 2ª observación previa de cada fila (sólo claves)."""
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE prev AS
        SELECT numero_de_cliente, foto_mes,
               lag(foto_mes, 1) OVER w AS m1,
               lag(foto_mes, 2) OVER w AS m2
        FROM {src}
        WINDOW w AS (PARTITION BY numero_de_cliente ORDER BY foto_mes)""")


def sql_mes(src: str, cols: list[str], mes: int) -> str:
    derived = []
    for s, alias in (("lag1", "p1"), ("delta1", "p1"), ("lag2", "p2"), ("delta2", "p2")):
        for c in cols:
            if s.startswith("lag"):
                derived.append(f"{alias}.{q(c)} AS {q(c + '_' + s)}")
            else:
                derived.append(f"(c.{q(c)} - {alias}.{q(c)}) AS {q(c + '_' + s)}")
    orig = ", ".join(f"c.{q(c)}" for c in cols)
    return f"""
        WITH k AS (SELECT * FROM prev WHERE foto_mes = {mes}),
        p1 AS (SELECT s.* FROM {src} s
               SEMI JOIN (SELECT numero_de_cliente, m1 AS foto_mes FROM k WHERE m1 IS NOT NULL) x
               USING (numero_de_cliente, foto_mes)),
        p2 AS (SELECT s.* FROM {src} s
               SEMI JOIN (SELECT numero_de_cliente, m2 AS foto_mes FROM k WHERE m2 IS NOT NULL) x
               USING (numero_de_cliente, foto_mes))
        SELECT c.numero_de_cliente, c.foto_mes, {orig}, {', '.join(derived)}
        FROM {src} c
        JOIN k USING (numero_de_cliente, foto_mes)
        LEFT JOIN p1 ON p1.numero_de_cliente = c.numero_de_cliente AND p1.foto_mes = k.m1
        LEFT JOIN p2 ON p2.numero_de_cliente = c.numero_de_cliente AND p2.foto_mes = k.m2
        WHERE c.foto_mes = {mes}
        ORDER BY c.numero_de_cliente"""
