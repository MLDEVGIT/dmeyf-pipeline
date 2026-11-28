"""Construye clase_ternaria / clase_binaria para competencia_02 con datos de 2019.

Regla (la de la competencia 1): estructura de monday/z101_target_sql.ipynb
(celda 27) y convención de horizonte observada en la salida oficial de
arboles/z0333_OptimizacionHiperparametros.ipynb (celda 19).

Sobre la grilla clientes x meses consecutivos:
  mes_0 = 1 si el cliente está en foto_mes t, 0 si no
  mes_1 = lead(mes_0, 1), mes_2 = lead(mes_0, 2)   (NULL fuera del período)

Para cada fila presente (mes_0 = 1):
  mes_1 = 0                  -> BAJA+1
  mes_1 = 1 y mes_2 = 0      -> BAJA+2
  mes_1 = 1 y mes_2 = 1      -> CONTINUA
  cualquier otro caso        -> NULL (falta horizonte)

Con datos hasta 201912, esto deja:
  201901..201910: etiqueta completa
  201911: sólo BAJA+1 (ausente en 201912); el resto NULL
  201912: todo NULL

clase_binaria (target de entrenamiento): 1 si BAJA+1 o BAJA+2, 0 si
CONTINUA, NULL si clase_ternaria es NULL.

Sólo lee numero_de_cliente y foto_mes del Parquet de 2019, sin modificarlo.
Escribe las etiquetas en un archivo aparte (temporal -> validación ->
publicación, sin sobrescribir). No informa distribuciones de 201910
(test reservado) ni de 201911.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import duckdb
import numpy as np
import psutil

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline_competencia02.config import RUTAS, mostrar  # noqa: E402

SRC = RUTAS.historico_2019
DST = RUTAS.target_2019
DATA_DIR = DST.parent
TMP = DATA_DIR / f"{DST.name}.tmp-{os.getpid()}"
OUT = RUTAS.datos / "reportes" / "03_target_resumen.json"

EXPECTED_MONTHS = [201901 + i for i in range(12)]
ULTIMO_COMPLETO = 201910
TRAIN = [201903, 201904, 201905, 201906]
VALID = [201908]
RESERVADOS = [201910]            # no se informa ninguna distribución
CLASES = {"CONTINUA", "BAJA+1", "BAJA+2"}

SQL_TARGET = """
WITH crudo AS (
    SELECT numero_de_cliente, foto_mes FROM read_parquet(?)
), periodos AS (
    SELECT DISTINCT foto_mes FROM crudo
), clientes AS (
    SELECT DISTINCT numero_de_cliente FROM crudo
), todo AS (
    SELECT numero_de_cliente, foto_mes FROM clientes CROSS JOIN periodos
), presencia AS (
    SELECT
        t.numero_de_cliente
        , t.foto_mes
        , if(c.numero_de_cliente IS NULL, 0, 1) AS mes_0
    FROM todo t
    LEFT JOIN crudo c USING (numero_de_cliente, foto_mes)
), clase AS (
    SELECT
        *
        , lead(mes_0, 1) OVER (PARTITION BY numero_de_cliente ORDER BY foto_mes) AS mes_1
        , lead(mes_0, 2) OVER (PARTITION BY numero_de_cliente ORDER BY foto_mes) AS mes_2
    FROM presencia
)
SELECT
    numero_de_cliente
    , foto_mes
    , CASE
        WHEN mes_1 = 0 THEN 'BAJA+1'
        WHEN mes_1 = 1 AND mes_2 = 0 THEN 'BAJA+2'
        WHEN mes_1 = 1 AND mes_2 = 1 THEN 'CONTINUA'
        ELSE NULL
      END AS clase_ternaria
    , CASE
        WHEN mes_1 = 0 OR (mes_1 = 1 AND mes_2 = 0) THEN 1
        WHEN mes_1 = 1 AND mes_2 = 1 THEN 0
        ELSE NULL
      END::TINYINT AS clase_binaria
    , (mes_1 IS NOT NULL AND mes_2 IS NOT NULL) AS horizonte_completo
FROM clase
WHERE mes_0 = 1
ORDER BY foto_mes, numero_de_cliente
"""


def p(path: Path) -> str:
    return path.as_posix()


def etiquetas_numpy(cli: np.ndarray, mes: np.ndarray) -> np.ndarray:
    """Implementación independiente (sin ventanas SQL) para contrastar."""
    idx = {m: i for i, m in enumerate(EXPECTED_MONTHS)}
    mi = np.vectorize(idx.__getitem__)(mes)
    presentes = [set(cli[mi == i].tolist()) for i in range(len(EXPECTED_MONTHS))]
    out = np.empty(len(cli), dtype=object)
    for r, (c, i) in enumerate(zip(cli.tolist(), mi.tolist())):
        en1 = presentes[i + 1].__contains__(c) if i + 1 < len(presentes) else None
        en2 = presentes[i + 2].__contains__(c) if i + 2 < len(presentes) else None
        if en1 is False:
            out[r] = "BAJA+1"
        elif en1 and en2 is False:
            out[r] = "BAJA+2"
        elif en1 and en2:
            out[r] = "CONTINUA"
        else:
            out[r] = None
    return out


def distribucion(con, meses: list[int]) -> dict:
    rows = con.execute(
        f"SELECT foto_mes, clase_ternaria, count(*) FROM read_parquet('{p(TMP)}') "
        f"WHERE foto_mes IN ({', '.join(map(str, meses))}) GROUP BY ALL ORDER BY ALL").fetchall()
    out = {}
    for m, c, n in rows:
        out.setdefault(str(m), {})[c] = int(n)
    tot = {}
    for d in out.values():
        for c, n in d.items():
            tot[c] = tot.get(c, 0) + n
    for d in [*out.values(), tot]:
        n = sum(d.values())
        d["total"] = n
        d["tasa_positiva_binaria"] = round((d.get("BAJA+1", 0) + d.get("BAJA+2", 0)) / n, 6)
    if len(meses) > 1:
        out["total"] = tot
    return out


def main() -> int:
    t0 = time.perf_counter()
    proc = psutil.Process()
    if not SRC.exists():
        print(f"ERROR: no existe {mostrar(SRC)}")
        return 1
    if DST.exists():
        print(f"ERROR: {mostrar(DST)} ya existe; no se sobrescribe.")
        return 1
    src_stat = SRC.stat()

    con = duckdb.connect()
    con.execute("SET memory_limit = '2GB'")
    con.execute("SET threads = 4")

    meses = [r[0] for r in con.execute(
        f"SELECT DISTINCT foto_mes FROM read_parquet('{p(SRC)}') ORDER BY 1").fetchall()]
    if meses != EXPECTED_MONTHS:
        print(f"ERROR: meses inesperados {meses}; lead() asume meses consecutivos")
        return 1

    con.execute(f"COPY ({SQL_TARGET}) TO '{p(TMP)}' (FORMAT parquet, COMPRESSION zstd)", [p(SRC)])
    t_build = time.perf_counter() - t0

    # --- Validaciones -------------------------------------------------------
    chk = {}
    n_src = con.execute(f"SELECT count(*) FROM read_parquet('{p(SRC)}')").fetchone()[0]
    n_tgt, n_keys = con.execute(
        f"SELECT count(*), count(DISTINCT (numero_de_cliente, foto_mes)) FROM read_parquet('{p(TMP)}')").fetchone()
    chk["claves_unicas"] = n_tgt == n_keys
    falt, sobr = con.execute(f"""
        SELECT
          (SELECT count(*) FROM read_parquet('{p(SRC)}') s ANTI JOIN read_parquet('{p(TMP)}') t
             USING (numero_de_cliente, foto_mes)),
          (SELECT count(*) FROM read_parquet('{p(TMP)}') t ANTI JOIN read_parquet('{p(SRC)}') s
             USING (numero_de_cliente, foto_mes))""").fetchone()
    chk["cobertura_igual_a_origen"] = n_tgt == n_src and falt == 0 and sobr == 0

    clases = {r[0] for r in con.execute(
        f"SELECT DISTINCT clase_ternaria FROM read_parquet('{p(TMP)}') WHERE clase_ternaria IS NOT NULL").fetchall()}
    chk["clases_admitidas"] = clases <= CLASES

    cob = con.execute(f"""
        SELECT foto_mes, count(*) AS filas, count(clase_ternaria) AS etiquetadas,
               count(*) FILTER (WHERE clase_ternaria NOT IN ('BAJA+1') ) AS no_baja1,
               bool_and(horizonte_completo) AS completo
        FROM read_parquet('{p(TMP)}') GROUP BY 1 ORDER BY 1""").fetchall()
    cob = {m: dict(filas=f, etiquetadas=e, no_baja1=nb, completo=c) for m, f, e, nb, c in cob}
    chk["completo_hasta_201910"] = all(
        v["filas"] == v["etiquetadas"] and v["completo"] for m, v in cob.items() if m <= ULTIMO_COMPLETO)
    chk["201911_solo_baja1_o_nulo"] = cob[201911]["no_baja1"] == 0 and not cob[201911]["completo"]
    chk["201912_todo_nulo"] = cob[201912]["etiquetadas"] == 0
    bin_bad = con.execute(f"""
        SELECT count(*) FROM read_parquet('{p(TMP)}')
        WHERE clase_binaria IS DISTINCT FROM
              CASE clase_ternaria WHEN 'CONTINUA' THEN 0 WHEN 'BAJA+1' THEN 1 WHEN 'BAJA+2' THEN 1 END
    """).fetchone()[0]
    chk["binaria_consistente"] = bin_bad == 0

    # BAJA+2 en t implica BAJA+1 en t+1 (mismo cliente)
    b2_bad = con.execute(f"""
        WITH t AS (SELECT * FROM read_parquet('{p(TMP)}'))
        SELECT count(*) FROM t a LEFT JOIN t b
          ON b.numero_de_cliente = a.numero_de_cliente
         AND b.foto_mes = CAST(strftime(strptime(CAST(a.foto_mes AS VARCHAR), '%Y%m') + INTERVAL 1 MONTH, '%Y%m') AS INTEGER)
        WHERE a.clase_ternaria = 'BAJA+2' AND b.clase_ternaria IS DISTINCT FROM 'BAJA+1'""").fetchone()[0]
    chk["baja2_t_implica_baja1_t_mas_1"] = b2_bad == 0

    # Implementación independiente
    arr = con.execute(
        f"SELECT numero_de_cliente, foto_mes, clase_ternaria FROM read_parquet('{p(TMP)}')").fetchnumpy()
    alt = etiquetas_numpy(np.asarray(arr["numero_de_cliente"]), np.asarray(arr["foto_mes"]))
    sql_lab = np.asarray(arr["clase_ternaria"], dtype=object)
    sql_lab = np.where(np.ma.getmaskarray(arr["clase_ternaria"]), None, sql_lab)
    n_diff = int(sum(a != b for a, b in zip(alt.tolist(), sql_lab.tolist())))
    chk["coincide_implementacion_independiente"] = n_diff == 0
    del arr, alt, sql_lab

    chk["origen_sin_modificar"] = SRC.stat().st_mtime_ns == src_stat.st_mtime_ns and SRC.stat().st_size == src_stat.st_size
    ok = all(chk.values())

    # --- Reporte (sin 201910 ni 201911) ---------------------------------------
    # Retorno: 1 si falta en t+1 pero está en t+2 (se etiqueta BAJA+1, como en la regla)
    retornos = dict(con.execute(f"""
        WITH s AS (SELECT numero_de_cliente c, foto_mes m FROM read_parquet('{p(SRC)}')),
        nxt AS (SELECT c, m, CAST(strftime(strptime(CAST(m AS VARCHAR), '%Y%m') + INTERVAL 1 MONTH, '%Y%m') AS INTEGER) m1,
                      CAST(strftime(strptime(CAST(m AS VARCHAR), '%Y%m') + INTERVAL 2 MONTH, '%Y%m') AS INTEGER) m2 FROM s)
        SELECT n.m, count(*) FROM nxt n
        WHERE n.m IN ({', '.join(map(str, TRAIN + VALID))})
          AND NOT EXISTS (SELECT 1 FROM s WHERE s.c = n.c AND s.m = n.m1)
          AND EXISTS (SELECT 1 FROM s WHERE s.c = n.c AND s.m = n.m2)
        GROUP BY 1 ORDER BY 1""").fetchall())

    report = {
        "origen": mostrar(SRC),
        "destino": mostrar(DST),
        "columnas": ["numero_de_cliente", "foto_mes", "clase_ternaria", "clase_binaria", "horizonte_completo"],
        "regla": {
            "BAJA+1": "presente en t y ausente en t+1",
            "BAJA+2": "presente en t y t+1, ausente en t+2",
            "CONTINUA": "presente en t, t+1 y t+2",
            "NULL": "sin horizonte suficiente (201911 salvo BAJA+1; 201912 completo)",
            "clase_binaria": "1 = BAJA+1 o BAJA+2; 0 = CONTINUA; NULL si clase_ternaria es NULL",
        },
        "referencias": [
            "monday/z101_target_sql.ipynb celda 27 (grilla clientes x periodos, mes_0, lead 1 y 2)",
            "arboles/z0333_OptimizacionHiperparametros.ipynb celda 19 (convención: anteúltimo mes sólo BAJA+1/NA, último mes NA)",
            "monday/z601_clases.ipynb celda 49 (clase_binaria2 = BAJA+1 o BAJA+2); difiere de la celda 4 (sólo BAJA+2)",
        ],
        "checks": chk,
        "ok": ok,
        "filas": int(n_tgt),
        "cobertura_por_mes": {
            str(m): ({"filas": v["filas"], "etiquetadas": v["etiquetadas"], "horizonte_completo": v["completo"]}
                     if m not in RESERVADOS + [201911] else
                     {"filas": v["filas"], "horizonte_completo": v["completo"],
                      "nota": "distribución no informada (reservado)" if m in RESERVADOS else
                              "etiqueta parcial: sólo BAJA+1 o NULL; distribución no informada"})
            for m, v in cob.items()},
        "distribucion_train_201903_201906": distribucion(con, TRAIN),
        "distribucion_validacion_201908": distribucion(con, VALID),
        "ausente_t1_presente_t2_etiquetados_baja1": {str(k): int(v) for k, v in retornos.items()},
        "recursos": {
            "tiempo_construccion_s": round(t_build, 1),
            "tiempo_total_s": round(time.perf_counter() - t0, 1),
            "pico_working_set_so_mb": round(getattr(proc.memory_info(), "peak_wset", 0) / 2**20, 1),
        },
    }
    con.close()

    if ok:
        if DST.exists():
            raise RuntimeError("el destino apareció durante la ejecución; no se sobrescribe")
        os.rename(TMP, DST)
        report["publicado"] = True
        report["tamano_mb"] = round(DST.stat().st_size / 2**20, 2)
    else:
        report["publicado"] = False
        report["temporal_conservado"] = mostrar(TMP)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("== Checks ==")
    for k, v in chk.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print("\nTrain 201903-201906:")
    print(json.dumps(report["distribucion_train_201903_201906"], indent=2))
    print("Validación 201908:")
    print(json.dumps(report["distribucion_validacion_201908"], indent=2))
    print(f"Ausente t+1 / presente t+2 (etiquetados BAJA+1): {report['ausente_t1_presente_t2_etiquetados_baja1']}")
    print(f"\nPublicado: {report['publicado']} | {report['recursos']}")
    print(f"Reporte: {mostrar(OUT)}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
