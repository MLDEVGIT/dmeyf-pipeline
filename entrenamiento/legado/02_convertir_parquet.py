"""Convierte competencia_02_2019.csv.gz a Parquet y verifica la equivalencia.

Pasos:
  1. Esquema: lee el CSV como texto (duckdb, en streaming) y tipa cada columna
     como BIGINT si todos sus valores no vacíos son enteros literales
     (regex, sin redondeos) o como DOUBLE en caso contrario. Nunca float32.
  2. Conversión: COPY en streaming a un archivo temporal, con el esquema fijo,
     celdas vacías como NULL y grupos de filas de 200.000. No corrige ceros ni
     agrega features.
  3. Verificación por bloques: pandas relee el CSV de forma independiente y lo
     compara con el Parquet leído por duckdb, celda por celda. Compara columnas,
     filas por mes, claves, valores exactos y posiciones de nulos.
  4. Publicación: sólo si todo pasa, renombra el temporal al destino final.
     Nunca sobrescribe un archivo existente.

Uso:
    .venv/Scripts/python.exe experimento_sampling/02_convertir_parquet.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import psutil

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "competencia_02"
SRC = DATA_DIR / "competencia_02_2019.csv.gz"
DST = DATA_DIR / "competencia_02_2019.parquet"
TMP = DATA_DIR / f"{DST.name}.tmp-{os.getpid()}"
DUCK_TMP = DATA_DIR / f".duckdb_tmp-{os.getpid()}"
OUT_DIR = ROOT / "experimento_sampling" / "reportes"
REPORT = OUT_DIR / "02_conversion_parquet.json"

EXPECTED_ROWS = 1_563_565
EXPECTED_NCOLS = 154
EXPECTED_MONTHS = [201901 + i for i in range(12)]
KEYS = ["numero_de_cliente", "foto_mes"]
CHUNK_ROWS = 200_000
INT_RE = r"-?[0-9]+"
MAX_EXACT = 2**53


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def varchar_spec(columns: list[str]) -> str:
    """Todas las columnas como texto: el tipado lo decide el esquema, no duckdb."""
    return "{" + ", ".join(f"'{c}': 'VARCHAR'" for c in columns) + "}"


def posix(p: Path) -> str:
    return p.as_posix()


class Recursos:
    def __init__(self):
        self.proc = psutil.Process()
        self.t0 = time.perf_counter()
        self.rss_peak = 0.0
        self.fases = {}

    def mark(self, fase: str, t_start: float):
        self.rss_peak = max(self.rss_peak, self.proc.memory_info().rss / 2**20)
        self.fases[fase] = round(time.perf_counter() - t_start, 1)
        print(f"[{fase}] {self.fases[fase]:.1f}s | RSS {self.proc.memory_info().rss / 2**20:,.0f} MB",
              flush=True)

    def sample(self):
        self.rss_peak = max(self.rss_peak, self.proc.memory_info().rss / 2**20)

    def resumen(self) -> dict:
        peak_os = getattr(self.proc.memory_info(), "peak_wset", None)
        return {
            "tiempo_total_s": round(time.perf_counter() - self.t0, 1),
            "tiempo_por_fase_s": self.fases,
            "rss_pico_muestreado_mb": round(self.rss_peak, 1),
            "pico_working_set_so_mb": round(peak_os / 2**20, 1) if peak_os else None,
        }


def inferir_esquema(con, columns: list[str]) -> tuple[dict, dict]:
    """Devuelve {columna: 'BIGINT'|'DOUBLE'} y estadísticas de texto."""
    exprs = []
    for i, c in enumerate(columns):
        lit = f"regexp_full_match({q(c)}, '{INT_RE}')"
        dbl = f"try_cast({q(c)} AS DOUBLE)"
        # Entero exacto escrito como real (p. ej. '1.1e+08' de R/fwrite)
        intdbl = f"({dbl} = trunc({dbl}) AND abs({dbl}) <= {MAX_EXACT})"
        exprs += [
            f"count({q(c)}) AS nn_{i}",
            f"count(*) FILTER (WHERE {q(c)} IS NOT NULL AND NOT {lit} AND NOT coalesce({intdbl}, false)) AS noint_{i}",
            f"count(*) FILTER (WHERE {q(c)} IS NOT NULL AND NOT {lit} AND coalesce({intdbl}, false)) AS intdbl_{i}",
            f"count(*) FILTER (WHERE {q(c)} IS NOT NULL AND regexp_full_match({q(c)}, '{INT_RE}') "
            f"AND try_cast({q(c)} AS BIGINT) IS NULL) AS overflow_{i}",
            f"count(*) FILTER (WHERE {q(c)} IS NOT NULL AND try_cast({q(c)} AS DOUBLE) IS NULL) AS nonum_{i}",
        ]
    row = con.execute(
        f"SELECT count(*) AS n, {', '.join(exprs)} FROM read_csv(?, header=true, "
        f"nullstr='', auto_detect=false, columns={varchar_spec(columns)})",
        [posix(SRC)],
    ).fetchone()
    names = [d[0] for d in con.description]
    r = dict(zip(names, row))
    schema, stats = {}, {"filas": int(r["n"])}
    for i, c in enumerate(columns):
        if r[f"nonum_{i}"] or r[f"overflow_{i}"]:
            raise RuntimeError(f"columna {c}: {r[f'nonum_{i}']} valores no numéricos, "
                               f"{r[f'overflow_{i}']} enteros fuera de int64")
        schema[c] = "BIGINT" if r[f"noint_{i}"] == 0 else "DOUBLE"
        stats[c] = {"no_nulos": int(r[f"nn_{i}"]), "nulos": int(r["n"] - r[f"nn_{i}"]),
                    "enteros_no_literales": int(r[f"intdbl_{i}"])}
    for k in KEYS:
        if schema[k] != "BIGINT":
            raise RuntimeError(f"la clave {k} no es entera")
    return schema, stats


def convertir(con, columns: list[str], schema: dict):
    def cast(c: str) -> str:
        if schema[c] == "DOUBLE":
            return f"CAST({q(c)} AS DOUBLE)"
        # Literal entero: cast directo (exacto). Si no, pasa por DOUBLE, ya
        # validado como entero exacto con |x| <= 2^53 en inferir_esquema.
        return (f"CASE WHEN regexp_full_match({q(c)}, '{INT_RE}') THEN CAST({q(c)} AS BIGINT) "
                f"ELSE CAST(CAST({q(c)} AS DOUBLE) AS BIGINT) END")

    select = ", ".join(f"{cast(c)} AS {q(c)}" for c in columns)
    con.execute(
        f"COPY (SELECT {select} FROM read_csv(?, header=true, nullstr='', auto_detect=false, "
        f"columns={varchar_spec(columns)})) TO '{posix(TMP)}' "
        f"(FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE {CHUNK_ROWS})",
        [posix(SRC)],
    )


def verificar(con, columns: list[str], schema: dict, rec: Recursos) -> dict:
    res = {"errores": []}
    err = res["errores"]

    # Esquema del Parquet
    pq_cols = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{posix(TMP)}')").fetchall()
    pq_names = [r[0] for r in pq_cols]
    pq_types = {r[0]: r[1] for r in pq_cols}
    if pq_names != columns:
        err.append("nombres/orden de columnas distintos")
    bad_types = {c: pq_types.get(c) for c in columns if pq_types.get(c) != schema[c]}
    if bad_types:
        err.append(f"tipos distintos: {bad_types}")
    meta = con.execute(
        f"SELECT count(DISTINCT row_group_id), sum(row_group_num_rows) / {len(columns)} "
        f"FROM parquet_metadata('{posix(TMP)}')").fetchone()
    res["row_groups"] = int(meta[0])

    # Celda por celda: CSV (pandas) vs Parquet (duckdb)
    dtypes = {c: ("Int64" if schema[c] == "BIGINT" else "float64") for c in columns}
    reader = pd.read_csv(
        SRC, compression="gzip", chunksize=CHUNK_ROWS, dtype=dtypes,
        keep_default_na=False, na_values=[""], float_precision="round_trip",
    )
    sel = ", ".join(q(c) for c in columns)
    offset = 0
    csv_months, csv_nulls = Counter(), Counter()
    celdas = 0
    diff_vals, diff_nulls = Counter(), Counter()
    for i, chunk in enumerate(reader):
        tb = time.perf_counter()
        n = len(chunk)
        if chunk.columns.tolist() != columns:
            err.append(f"bloque {i}: columnas del CSV distintas")
        pq = con.execute(
            f"SELECT {sel} FROM read_parquet('{posix(TMP)}', file_row_number=true) "
            f"WHERE file_row_number >= {offset} AND file_row_number < {offset + n} "
            f"ORDER BY file_row_number").fetchnumpy()
        if len(pq[columns[0]]) != n:
            err.append(f"bloque {i}: {n} filas CSV vs {len(pq[columns[0]])} Parquet")
            break
        for c in columns:
            s = chunk[c]
            m_csv = s.isna().to_numpy()
            a = pq[c]
            m_pq = np.ma.getmaskarray(a)
            nd = int((m_csv != m_pq).sum())
            if nd:
                diff_nulls[c] += nd
            keep = ~(m_csv | m_pq)
            if schema[c] == "BIGINT":
                v_csv = s.to_numpy(dtype=np.int64, na_value=0)
                v_pq = np.ma.getdata(a).astype(np.int64, copy=False)
            else:
                v_csv = s.to_numpy(dtype=np.float64)
                v_pq = np.ma.getdata(a).astype(np.float64, copy=False)
            nv = int((v_csv[keep] != v_pq[keep]).sum())
            if nv:
                diff_vals[c] += nv
            csv_nulls[c] += int(m_csv.sum())
        csv_months.update(chunk["foto_mes"].astype("int64").value_counts().to_dict())
        celdas += n * len(columns)
        offset += n
        del chunk, pq
        rec.sample()
        print(f"  verificación bloque {i}: {offset:>9,} filas | {time.perf_counter() - tb:5.1f}s",
              flush=True)

    if diff_vals:
        err.append(f"valores distintos: {dict(diff_vals)}")
    if diff_nulls:
        err.append(f"posiciones de nulos distintas: {dict(diff_nulls)}")
    res["celdas_comparadas"] = celdas
    res["filas_csv"] = offset
    res["celdas_valor_distinto"] = int(sum(diff_vals.values()))
    res["celdas_nulo_distinto"] = int(sum(diff_nulls.values()))
    res["nulos_totales"] = int(sum(csv_nulls.values()))
    res["columnas_con_nulos"] = int(sum(1 for v in csv_nulls.values() if v))

    # Agregados sobre el Parquet
    n_pq = con.execute(f"SELECT count(*) FROM read_parquet('{posix(TMP)}')").fetchone()[0]
    pq_months = dict(con.execute(
        f"SELECT foto_mes, count(*) FROM read_parquet('{posix(TMP)}') GROUP BY 1").fetchall())
    k = con.execute(
        f"SELECT count(*) FILTER (WHERE numero_de_cliente IS NULL OR foto_mes IS NULL), "
        f"count(*) - count(DISTINCT (numero_de_cliente, foto_mes)) "
        f"FROM read_parquet('{posix(TMP)}')").fetchone()
    res["filas_parquet"] = int(n_pq)
    res["filas_por_mes"] = {int(m): int(pq_months.get(m, 0)) for m in sorted(set(pq_months) | set(csv_months))}
    res["claves_nulas"] = int(k[0])
    res["claves_duplicadas_filas_exceso"] = int(k[1])

    checks = {
        "columnas_y_orden": pq_names == columns and len(columns) == EXPECTED_NCOLS,
        "tipos_esperados": not bad_types,
        "filas_csv_1563565": offset == EXPECTED_ROWS,
        "filas_parquet_igual_csv": n_pq == offset,
        "meses_esperados": sorted(pq_months) == EXPECTED_MONTHS,
        "filas_por_mes_igual_csv": {int(m): int(v) for m, v in pq_months.items()}
                                   == {int(m): int(v) for m, v in csv_months.items()},
        "claves_sin_nulos": k[0] == 0,
        "claves_sin_duplicados": k[1] == 0,
        "valores_identicos": not diff_vals,
        "nulos_misma_posicion": not diff_nulls,
    }
    res["checks"] = checks
    res["ok"] = all(checks.values()) and not err
    return res


def main() -> int:
    rec = Recursos()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not SRC.exists():
        print(f"ERROR: no existe {SRC.relative_to(ROOT)}")
        return 1
    if DST.exists():
        print(f"ERROR: {DST.relative_to(ROOT)} ya existe; no se sobrescribe. Borralo a mano para regenerarlo.")
        return 1

    DUCK_TMP.mkdir()
    con = duckdb.connect()
    con.execute(f"SET temp_directory = '{posix(DUCK_TMP)}'")
    con.execute("SET memory_limit = '4GB'")
    con.execute("SET threads = 4")
    con.execute("SET preserve_insertion_order = true")

    report = {
        "origen": SRC.relative_to(ROOT).as_posix(),
        "destino": DST.relative_to(ROOT).as_posix(),
        "motor": f"duckdb {duckdb.__version__} (escritura) / pandas {pd.__version__} (relectura CSV)",
        "compresion": "zstd",
        "row_group_size": CHUNK_ROWS,
    }
    status = 2
    try:
        columns = pd.read_csv(SRC, nrows=0, compression="gzip").columns.tolist()

        t = time.perf_counter()
        schema, stats = inferir_esquema(con, columns)
        rec.mark("esquema", t)
        report["esquema"] = {
            "BIGINT": [c for c in columns if schema[c] == "BIGINT"],
            "DOUBLE": [c for c in columns if schema[c] == "DOUBLE"],
        }
        report["enteros_no_literales_por_columna"] = {
            c: s["enteros_no_literales"] for c, s in stats.items()
            if isinstance(s, dict) and s["enteros_no_literales"]}
        print(f"  {len(report['esquema']['BIGINT'])} BIGINT, {len(report['esquema']['DOUBLE'])} DOUBLE | "
              f"enteros no literales: {report['enteros_no_literales_por_columna']}")

        t = time.perf_counter()
        convertir(con, columns, schema)
        rec.mark("conversion", t)

        t = time.perf_counter()
        ver = verificar(con, columns, schema, rec)
        rec.mark("verificacion", t)
        report["verificacion"] = ver

        report["tamano_mb"] = {
            "csv_gz": round(SRC.stat().st_size / 2**20, 1),
            "parquet": round(TMP.stat().st_size / 2**20, 1),
        }
        if ver["ok"]:
            con.close()
            if DST.exists():  # alguien lo creó mientras tanto
                raise RuntimeError("el destino apareció durante la ejecución; no se sobrescribe")
            os.rename(TMP, DST)  # en Windows falla si DST existe
            report["publicado"] = True
            status = 0
        else:
            report["publicado"] = False
            report["temporal_conservado"] = TMP.relative_to(ROOT).as_posix()
    except Exception as e:  # noqa: BLE001
        report["error"] = f"{type(e).__name__}: {e}"
        report["publicado"] = False
        if TMP.exists():
            report["temporal_conservado"] = TMP.relative_to(ROOT).as_posix()
        print(f"ERROR: {report['error']}")
    finally:
        try:
            con.close()
        except Exception:  # noqa: BLE001
            pass
        shutil.rmtree(DUCK_TMP, ignore_errors=True)
        report["recursos"] = rec.resumen()
        REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    v = report.get("verificacion", {})
    print("\n== Checks ==")
    for k, ok in v.get("checks", {}).items():
        print(f"  {'PASS' if ok else 'FAIL'}  {k}")
    for e in v.get("errores", []):
        print(f"  ERROR {e}")
    if v:
        print(f"\nCeldas comparadas: {v['celdas_comparadas']:,} | valores distintos: "
              f"{v['celdas_valor_distinto']} | nulos distintos: {v['celdas_nulo_distinto']} | "
              f"nulos totales: {v['nulos_totales']:,} en {v['columnas_con_nulos']} columnas")
    print(f"Tamaño: {report.get('tamano_mb')}")
    print(f"Publicado: {report['publicado']} -> {report['destino'] if report['publicado'] else report.get('temporal_conservado')}")
    r = report["recursos"]
    print(f"Tiempo total {r['tiempo_total_s']}s {r['tiempo_por_fase_s']} | RSS pico "
          f"{r['rss_pico_muestreado_mb']:,.0f} MB | pico SO {r['pico_working_set_so_mb']} MB")
    print(f"Reporte: {REPORT.relative_to(ROOT).as_posix()}")
    return status


if __name__ == "__main__":
    sys.exit(main())
