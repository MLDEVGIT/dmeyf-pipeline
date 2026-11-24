"""Auditoría del archivo competencia_02_2019.csv.gz (sólo 2019).

Lee por bloques, no imprime registros individuales y guarda resúmenes
agregados en experimento_sampling/reportes/.

Uso (desde cualquier directorio):
    .venv/Scripts/python.exe experimento_sampling/01_auditar_datos.py
"""
from __future__ import annotations

import json
import platform
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import psutil

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "competencia_02" / "competencia_02_2019.csv.gz"
OUT_DIR = ROOT / "experimento_sampling" / "reportes"

EXPECTED_ROWS = 1_563_565
EXPECTED_NCOLS = 154
EXPECTED_MONTHS = [201901 + i for i in range(12)]
KEYS = ["numero_de_cliente", "foto_mes"]
CHUNK_ROWS = 200_000

# Tokens textuales que se consideran candidatos a "faltante". Se cuentan
# todos los tokens no numéricos; sólo éstos se interpretan como NA.
NULL_TOKENS = {"", "NA", "NaN", "nan", "NULL", "null", "None", "N/A", "?", "-"}


def rss_mb(proc: psutil.Process) -> float:
    return proc.memory_info().rss / 2**20


def main() -> int:
    t0 = time.perf_counter()
    proc = psutil.Process()
    rss_start = rss_mb(proc)
    rss_peak = rss_start
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not INPUT.exists():
        print(f"ERROR: no existe {INPUT.relative_to(ROOT)}")
        return 1

    # Encabezado
    header = pd.read_csv(INPUT, nrows=0, compression="gzip").columns.tolist()
    dup_cols = [c for c, n in Counter(header).items() if n > 1]

    # Acumuladores
    rows_by_month: Counter = Counter()
    n_rows = 0
    key_null = Counter()               # claves nulas / no numéricas
    key_cli, key_mes, key_chunk = [], [], []
    tokens = defaultdict(Counter)      # columna -> token no numérico -> n
    na_cm = defaultdict(Counter)       # columna -> foto_mes -> n faltantes
    zero_cm = defaultdict(Counter)     # columna -> foto_mes -> n ceros
    chunk_times = []

    reader = pd.read_csv(
        INPUT,
        compression="gzip",
        chunksize=CHUNK_ROWS,
        na_filter=False,       # no convertir nada a NaN: interpretar tokens a mano
        low_memory=False,
    )
    for i, chunk in enumerate(reader):
        tc = time.perf_counter()
        if chunk.columns.tolist() != header:
            raise RuntimeError(f"bloque {i}: columnas distintas al encabezado")
        n_rows += len(chunk)

        # Claves
        cli = pd.to_numeric(chunk["numero_de_cliente"], errors="coerce")
        mes = pd.to_numeric(chunk["foto_mes"], errors="coerce")
        key_null["numero_de_cliente"] += int(cli.isna().sum())
        key_null["foto_mes"] += int(mes.isna().sum())
        key_null["alguna"] += int((cli.isna() | mes.isna()).sum())
        ok = cli.notna() & mes.notna()
        key_cli.append(cli[ok].to_numpy(np.int64))
        key_mes.append(mes[ok].to_numpy(np.int32))
        key_chunk.append(np.full(int(ok.sum()), i, np.int16))
        rows_by_month.update(mes.fillna(-1).astype(np.int64).value_counts().to_dict())
        mes_key = mes.fillna(-1).astype(np.int64)

        # Faltantes: columnas no numéricas en el bloque contienen tokens textuales
        for col in header:
            s = chunk[col]
            # pandas >= 3 lee texto como StringDtype, no object
            if not pd.api.types.is_numeric_dtype(s):
                num = pd.to_numeric(s, errors="coerce")
                nonnum = num.isna()
                if nonnum.any():
                    tokens[col].update(s[nonnum].value_counts().to_dict())
                    is_na = s.isin(NULL_TOKENS)
                    if is_na.any():
                        na_cm[col].update(mes_key[is_na].value_counts().to_dict())
                is_zero = num.eq(0)
            else:
                is_zero = s.eq(0)
            if is_zero.any():
                zero_cm[col].update(mes_key[is_zero].value_counts().to_dict())

        del chunk
        rss_peak = max(rss_peak, rss_mb(proc))
        chunk_times.append(round(time.perf_counter() - tc, 2))
        print(f"  bloque {i:2d}: {n_rows:>9,} filas acumuladas | "
              f"{chunk_times[-1]:5.1f}s | RSS {rss_mb(proc):,.0f} MB", flush=True)

    t_read = time.perf_counter() - t0

    # Duplicados de clave en todo el archivo (incluye cruces entre bloques)
    keys = pd.DataFrame({
        "cli": np.concatenate(key_cli),
        "mes": np.concatenate(key_mes),
        "chunk": np.concatenate(key_chunk),
    })
    dmask = keys.duplicated(["cli", "mes"], keep=False)
    dups = keys[dmask]
    if len(dups):
        span = dups.groupby(["cli", "mes"])["chunk"].nunique()
        dup_keys = int(len(span))
        dup_cross_chunk = int((span > 1).sum())
        dup_by_month = dups.groupby("mes")[["cli"]].size().to_dict()
    else:
        dup_keys = dup_cross_chunk = 0
        dup_by_month = {}
    dup_excess_rows = int(keys.duplicated(["cli", "mes"]).sum())
    n_clients = int(keys["cli"].nunique())
    clients_by_month = keys.groupby("mes")["cli"].nunique().to_dict()
    rss_peak = max(rss_peak, rss_mb(proc))
    del keys, dups, key_cli, key_mes, key_chunk

    # Tablas de salida
    months_found = sorted(m for m in rows_by_month if m != -1)
    filas_mes = pd.DataFrame({
        "foto_mes": EXPECTED_MONTHS + [m for m in months_found if m not in EXPECTED_MONTHS],
    })
    filas_mes["filas"] = filas_mes["foto_mes"].map(rows_by_month).fillna(0).astype(int)
    filas_mes["clientes_unicos"] = filas_mes["foto_mes"].map(clients_by_month).fillna(0).astype(int)
    filas_mes["esperado"] = filas_mes["foto_mes"].isin(EXPECTED_MONTHS)
    filas_mes.to_csv(OUT_DIR / "01_filas_por_mes.csv", index=False)

    tok_rows = [
        {"columna": c, "token": repr(t), "es_faltante": t in NULL_TOKENS, "n": n}
        for c, cnt in tokens.items() for t, n in cnt.most_common(20)
    ]
    pd.DataFrame(tok_rows, columns=["columna", "token", "es_faltante", "n"]).to_csv(
        OUT_DIR / "01_tokens_no_numericos.csv", index=False)

    denom = filas_mes.set_index("foto_mes")["filas"]
    long = []
    for col in header:
        for m in months_found:
            n_na = na_cm[col].get(m, 0)
            n_zero = zero_cm[col].get(m, 0)
            long.append({"columna": col, "foto_mes": m, "filas": int(denom[m]),
                         "n_faltantes": int(n_na), "prop_faltantes": n_na / denom[m],
                         "n_ceros": int(n_zero), "prop_ceros": n_zero / denom[m]})
    long = pd.DataFrame(long)
    long.to_csv(OUT_DIR / "01_faltantes_ceros_por_columna_mes.csv", index=False)
    long.pivot(index="columna", columns="foto_mes", values="prop_faltantes") \
        .reindex(header).round(6).to_csv(OUT_DIR / "01_faltantes_matriz_columna_mes.csv")

    na_total = long.groupby("columna")["n_faltantes"].sum().reindex(header)
    cols_with_na = na_total[na_total > 0]

    # Señales de variables "rotas": 100% faltante o 100% cero en un mes
    # cuando el resto de los meses no lo está.
    alerts = []
    for metric in ("prop_faltantes", "prop_ceros"):
        p = long.pivot(index="columna", columns="foto_mes", values=metric)
        for col, row in p.iterrows():
            full = row[row >= 0.9999].index.tolist()
            if full and len(full) < len(row) and row.drop(full).max() < 0.99:
                alerts.append({"columna": col, "metrica": metric,
                               "meses_100pct": full,
                               "max_otros_meses": round(float(row.drop(full).max()), 4)})
    pd.DataFrame(alerts, columns=["columna", "metrica", "meses_100pct", "max_otros_meses"]) \
        .to_csv(OUT_DIR / "01_alertas_variables_mes.csv", index=False)

    t_total = time.perf_counter() - t0
    rss_end = rss_mb(proc)
    mi = proc.memory_info()
    peak_os = getattr(mi, "peak_wset", None)  # sólo Windows

    checks = {
        "n_columnas_154": len(header) == EXPECTED_NCOLS,
        "sin_columnas_duplicadas": not dup_cols,
        "claves_presentes": all(k in header for k in KEYS),
        "meses_esperados_12": months_found == EXPECTED_MONTHS,
        "total_filas_1563565": n_rows == EXPECTED_ROWS,
        "sin_claves_nulas": key_null["alguna"] == 0,
        "sin_claves_duplicadas": dup_excess_rows == 0,
        "sin_clase_ternaria": "clase_ternaria" not in header,
    }
    summary = {
        "archivo": INPUT.relative_to(ROOT).as_posix(),
        "tamano_mb_comprimido": round(INPUT.stat().st_size / 2**20, 1),
        "checks": checks,
        "n_columnas": len(header),
        "columnas_duplicadas": dup_cols,
        "filas_total": n_rows,
        "filas_esperadas": EXPECTED_ROWS,
        "diferencia_filas": n_rows - EXPECTED_ROWS,
        "meses_encontrados": months_found,
        "meses_faltantes": [m for m in EXPECTED_MONTHS if m not in months_found],
        "meses_inesperados": [m for m in months_found if m not in EXPECTED_MONTHS],
        "clientes_unicos_total": n_clients,
        "claves_nulas": dict(key_null),
        "duplicados": {
            "filas_en_exceso": dup_excess_rows,
            "claves_distintas_duplicadas": dup_keys,
            "claves_duplicadas_entre_bloques": dup_cross_chunk,
            "filas_duplicadas_por_mes": {int(k): int(v) for k, v in dup_by_month.items()},
        },
        "faltantes": {
            "representacion_interpretada": "celda vacía en el CSV (token '') salvo que "
                                           "01_tokens_no_numericos.csv muestre otros tokens",
            "tokens_considerados_faltantes": sorted(NULL_TOKENS),
            "tokens_no_numericos_encontrados": {
                c: {repr(t): int(n) for t, n in cnt.most_common(5)} for c, cnt in tokens.items()},
            "columnas_con_faltantes": int(len(cols_with_na)),
            "columnas_sin_faltantes": int(len(header) - len(cols_with_na)),
            "top15_prop_faltante_global": (cols_with_na / n_rows).sort_values(ascending=False)
                                          .head(15).round(4).to_dict(),
            "alertas_variable_mes": len(alerts),
        },
        "recursos": {
            "tiempo_total_s": round(t_total, 1),
            "tiempo_lectura_s": round(t_read, 1),
            "tiempo_por_bloque_s": chunk_times,
            "filas_por_bloque": CHUNK_ROWS,
            "rss_inicio_mb": round(rss_start, 1),
            "rss_pico_muestreado_mb": round(rss_peak, 1),
            "rss_fin_mb": round(rss_end, 1),
            "pico_working_set_so_mb": round(peak_os / 2**20, 1) if peak_os else None,
            "ram_total_gb": round(psutil.virtual_memory().total / 2**30, 1),
        },
        "entorno": {"python": sys.version.split()[0], "pandas": pd.__version__,
                    "numpy": np.__version__, "plataforma": platform.platform()},
    }
    (OUT_DIR / "01_auditoria_resumen.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print("\n== Checks ==")
    for k, v in checks.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print(f"\nFilas: {n_rows:,} (esperadas {EXPECTED_ROWS:,})")
    print(filas_mes.to_string(index=False))
    print(f"\nClaves nulas: {dict(key_null)}")
    print(f"Duplicados: {summary['duplicados']}")
    print(f"Tokens no numéricos por columna: {len(tokens)} columnas")
    print(f"Columnas con faltantes: {len(cols_with_na)} / {len(header)}")
    print(f"Alertas variable-mes: {len(alerts)}")
    print(f"\nTiempo total {t_total:.1f}s | RSS pico {rss_peak:,.0f} MB | "
          f"pico SO {summary['recursos']['pico_working_set_so_mb']} MB")
    print(f"Reportes en {OUT_DIR.relative_to(ROOT).as_posix()}/")
    return 0 if all(checks.values()) else 2


if __name__ == "__main__":
    sys.exit(main())
