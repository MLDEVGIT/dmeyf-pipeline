"""Genera lag1, delta1, lag2 y delta2 para competencia_02 (2019).

Definición:
  - Confirmado por Ale: se generan los dos órdenes, lag1, delta1, lag2 y
    delta2.
  - Decisión de implementación: se aplican a las 152 variables originales
    (todas menos numero_de_cliente y foto_mes), que también se conservan.
  - Decisión de implementación: lag_k es el valor de la k-ésima observación
    previa del mismo cliente, con las filas ordenadas por foto_mes. Es
    lag(x, k) OVER (PARTITION BY numero_de_cliente ORDER BY foto_mes), como en
    monday/z402_Feature_Engineering_en_SQL.ipynb (celdas 17-21). Si el
    cliente faltó un mes, se toma la observación anterior disponible, no el
    mes calendario t-k.
  - delta_k = x actual - lag_k (NULL si alguno es NULL).
  - Sin indicadores, imputaciones ni correcciones. Los tipos se conservan
    (BIGINT o DOUBLE).
  - Sólo se miran observaciones previas; nunca futuras.
  - 760 predictores: 152 originales + 152 x {lag1, delta1, lag2, delta2}.

Salida: data/competencia_02/competencia_02_2019_features/ con un Parquet por
mes. Las claves van como columnas de identificación, declaradas en los
metadatos del Parquet y en manifiesto.json. Las etiquetas quedan en
competencia_02_2019_target.parquet (03), por separado.

Se escribe primero en un directorio temporal y sólo se publica si pasan las
validaciones. Nunca se sobrescribe.

Con --validar-existente CARPETA no se recalcula nada: se validan los Parquet
de una generación ya escrita (por ejemplo, el .tmp-<pid> de una corrida
cortada) y, si pasan todos los chequeos, se publica esa carpeta.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

import duckdb
import numpy as np
import psutil

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline_competencia02.config import RUTAS, mostrar  # noqa: E402
from pipeline_competencia02.features import KEYS, SUFIJOS, crear_prev, nombres, q, sql_mes  # noqa: E402

SRC = RUTAS.historico_2019
TARGET = RUTAS.target_2019
DST = RUTAS.features_2019
DATA_DIR = DST.parent
TMP = DATA_DIR / f"{DST.name}.tmp-{os.getpid()}"
DUCK_TMP = DATA_DIR / f".duckdb_tmp-{os.getpid()}"
OUT = RUTAS.datos / "reportes" / "04_features_resumen.json"

TARGET_NAMES = {"clase_ternaria", "clase_binaria", "horizonte_completo"}
N_ORIGINALES = 152
N_PREDICTORES = 760
DEFINICION = {
    "confirmado": "Ale confirmó ambos órdenes: lag1, delta1, lag2 y delta2",
    "decisiones_de_implementacion": [
        "se aplican a las 152 variables originales (todas menos numero_de_cliente y foto_mes)",
        "lag_k = k-ésima observación previa del cliente (lag OVER PARTITION BY numero_de_cliente "
        "ORDER BY foto_mes, como z402), no el mes calendario t-k",
        "delta_k = x - lag_k; NULL si alguno es NULL",
        "sin indicadores, imputaciones ni correcciones; tipos conservados",
    ],
    "target": "se mantiene el de 03 (código docente); la discrepancia de clientes ausentes en t+1 "
              "que vuelven en t+2 sigue pendiente de consultar con el tutor",
}


# --------------------------------------------------------------------------
# Prueba con datos sintéticos: huecos de meses, nulos y valores negativos
# --------------------------------------------------------------------------
SINTETICO = [  # (cliente, mes, a BIGINT, b DOUBLE)
    (1, 201901, 10, 1.5), (1, 201902, 20, None), (1, 201903, None, 4.0), (1, 201904, 25, -0.5),
    (2, 201901, 5, 0.1), (2, 201903, 7, 0.2),                       # falta 201902
    (3, 201902, 100, None),                                          # una sola observación
    (4, 201901, 1, 1.0), (4, 201902, 2, 2.0), (4, 201904, 4, 4.0), (4, 201905, 8, 8.0),
    (5, 201903, -3, 3.0), (5, 201905, 9, None),                      # empieza tarde, con hueco
]


def esperado_python(rows):
    """Implementación de referencia en Python puro, sin SQL."""
    out = {}
    por_cli = {}
    for r in rows:
        por_cli.setdefault(r[0], []).append(r)
    for cli, rs in por_cli.items():
        rs = sorted(rs, key=lambda r: r[1])
        for i, (c, m, a, b) in enumerate(rs):
            fila = {"a": a, "b": b}
            for k in (1, 2):
                prev = rs[i - k] if i - k >= 0 else None
                for name, j in (("a", 2), ("b", 3)):
                    lag = prev[j] if prev else None
                    cur = fila[name]
                    fila[f"{name}_lag{k}"] = lag
                    fila[f"{name}_delta{k}"] = None if lag is None or cur is None else cur - lag
            out[(c, m)] = fila
    return out


def prueba_sintetica() -> dict:
    con = duckdb.connect()
    con.execute("CREATE TABLE syn (numero_de_cliente BIGINT, foto_mes BIGINT, a BIGINT, b DOUBLE)")
    con.executemany("INSERT INTO syn VALUES (?, ?, ?, ?)", SINTETICO)
    crear_prev(con, "syn")
    cols = ["a", "b"]
    names = KEYS + nombres(cols)
    got = {}
    for mes in sorted({r[1] for r in SINTETICO}):
        for row in con.execute(sql_mes("syn", cols, mes)).fetchall():
            d = dict(zip(names, row))
            got[(d["numero_de_cliente"], d["foto_mes"])] = {k: d[k] for k in names[2:]}
    exp = esperado_python(SINTETICO)
    diffs = [(k, c) for k in exp for c in exp[k] if exp[k][c] != got.get(k, {}).get(c, "faltante")]

    # Casos verificados a mano
    manual = {
        "sin_futuro_primer_mes": all(got[(1, 201901)][f"{v}_lag{k}"] is None for v in "ab" for k in (1, 2)),
        "hueco_lag1_es_obs_previa": got[(2, 201903)]["a_lag1"] == 5 and got[(2, 201903)]["a_delta1"] == 2
                                    and got[(2, 201903)]["a_lag2"] is None,
        "hueco_en_medio_lag2": got[(4, 201905)]["a_lag1"] == 4 and got[(4, 201905)]["a_lag2"] == 2
                               and got[(4, 201905)]["a_delta2"] == 6,
        "actual_nulo_delta_nulo": got[(1, 201903)]["a_delta1"] is None and got[(1, 201903)]["a_lag1"] == 20,
        "lag_nulo_delta_nulo": got[(1, 201903)]["b_lag1"] is None and got[(1, 201903)]["b_delta1"] is None
                               and got[(1, 201903)]["b_lag2"] == 1.5 and got[(1, 201903)]["b_delta2"] == 2.5,
        "lag1_nulo_no_se_saltea": got[(1, 201904)]["a_lag1"] is None and got[(1, 201904)]["a_lag2"] == 20
                                  and got[(1, 201904)]["a_delta2"] == 5,
        "negativos": got[(5, 201905)]["a_lag1"] == -3 and got[(5, 201905)]["a_delta1"] == 12,
        "una_sola_observacion": all(got[(3, 201902)][f"a_{s}"] is None for s in SUFIJOS),
    }
    con.close()
    return {"filas": len(SINTETICO), "celdas_comparadas": sum(len(v) for v in exp.values()),
            "diferencias_vs_python": len(diffs), "casos_manuales": manual,
            "ok": not diffs and len(got) == len(exp) and all(manual.values())}


# --------------------------------------------------------------------------
def verificar_numpy(con, glob: str, cols: list[str], tipos: dict) -> dict:
    """Recalcula las 608 derivadas con numpy (shift dentro de cliente) y compara."""
    order_sql = "ORDER BY numero_de_cliente, foto_mes"
    k = con.execute(f"SELECT numero_de_cliente, foto_mes FROM read_parquet('{SRC.as_posix()}') {order_sql}").fetchnumpy()
    cli = np.asarray(k["numero_de_cliente"])
    s1 = np.zeros(len(cli), bool)
    s1[1:] = cli[1:] == cli[:-1]
    s2 = np.zeros(len(cli), bool)
    s2[2:] = (cli[2:] == cli[:-2])
    fk = con.execute(f"SELECT numero_de_cliente, foto_mes FROM read_parquet('{glob}') {order_sql}").fetchnumpy()
    claves_iguales = bool(np.array_equal(cli, np.asarray(fk["numero_de_cliente"]))
                          and np.array_equal(np.asarray(k["foto_mes"]), np.asarray(fk["foto_mes"])))
    diffs = {}
    for c in cols:
        x = con.execute(f"SELECT {q(c)} FROM read_parquet('{SRC.as_posix()}') {order_sql}").fetchnumpy()[c]
        xv, xm = np.ma.getdata(x), np.ma.getmaskarray(x)
        f = con.execute(f"SELECT {', '.join(q(c + '_' + s) for s in SUFIJOS)} FROM read_parquet('{glob}') "
                        f"{order_sql}").fetchnumpy()
        for kk, same in ((1, s1), (2, s2)):
            lv = np.zeros_like(xv)
            lm = np.ones(len(xv), bool)
            lv[kk:] = xv[:-kk]
            lm[kk:] = xm[:-kk]
            lm |= ~same
            dm = lm | xm
            dv = np.where(dm, 0, xv) - np.where(dm, 0, lv)
            for s, (ev, em) in ((f"lag{kk}", (lv, lm)), (f"delta{kk}", (dv, dm))):
                g = f[f"{c}_{s}"]
                gv, gm = np.ma.getdata(g), np.ma.getmaskarray(g)
                n = int((gm != em).sum()) + int((gv[~em & ~gm] != ev[~em & ~gm]).sum())
                if n:
                    diffs[f"{c}_{s}"] = n
    return {"claves_mismo_orden": claves_iguales, "columnas_comparadas": len(cols) * 4,
            "celdas_comparadas": len(cli) * len(cols) * 4, "columnas_con_diferencias": diffs}


def mb(proc) -> float:
    return round(proc.memory_info().rss / 2**20, 1)


def leer_completo(con, carpeta: Path, meses: list[int], out_names: list[str]) -> dict:
    """Decodifica todas las celdas de cada archivo y lo contrasta con sus metadatos.

    bit_xor(hash(col)) obliga a leer cada valor de cada columna; además deja una
    huella por archivo.
    """
    hashes = ", ".join(f"bit_xor(hash({q(c)}))" for c in out_names)
    por_mes = {}
    for m in meses:
        f = (carpeta / f"features_{m}.parquet").as_posix()
        filas_meta, n_rg = con.execute(f"SELECT num_rows, num_row_groups FROM parquet_file_metadata('{f}')").fetchone()
        kv = dict(con.execute(f"SELECT decode(key), decode(value) FROM parquet_kv_metadata('{f}')").fetchall())
        r = con.execute(f"SELECT count(*), min(foto_mes), max(foto_mes), {hashes} FROM read_parquet('{f}')").fetchone()
        huella = 0
        for h in r[3:]:
            huella ^= int(h)
        por_mes[str(m)] = {"filas_leidas": int(r[0]), "filas_metadatos": int(filas_meta), "row_groups": int(n_rg),
                           "foto_mes_min": int(r[1]), "foto_mes_max": int(r[2]), "huella_xor": f"{huella:016x}",
                           "kv_claves": kv.get("claves"), "kv_n_predictores": kv.get("n_predictores")}
    return por_mes


def validar(con, carpeta: Path, cols: list[str], tipos: dict, target_cols: set, pred: list[str],
            meses: list[int], disponibilidad: dict, futuro: int, src_stat: tuple, rep: dict, proc) -> dict:
    """Corre todos los chequeos sobre los Parquet de `carpeta` y devuelve el dict de checks."""
    esperados = {f"features_{m}.parquet" for m in meses}
    presentes = {p.name for p in carpeta.iterdir()}
    rep["archivos"] = {p.name: {"bytes": p.stat().st_size,
                                "modificado": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(p.stat().st_mtime))}
                       for p in sorted(carpeta.iterdir())}
    if presentes != esperados:
        rep["archivos_inesperados"] = sorted(presentes - esperados)
        rep["archivos_faltantes"] = sorted(esperados - presentes)
        return {"archivos_esperados": False}

    glob = (carpeta / "features_*.parquet").as_posix()
    out_cols = con.execute(f"SELECT column_name, column_type FROM (DESCRIBE SELECT * FROM read_parquet('{glob}'))").fetchall()
    out_names = [c for c, _ in out_cols]
    out_types = dict(out_cols)

    # Lectura completa de cada archivo
    t = time.perf_counter()
    lectura = leer_completo(con, carpeta, meses, out_names)
    rep["lectura_completa"] = lectura
    rep["tiempo_lectura_completa_s"] = round(time.perf_counter() - t, 1)
    rep["memoria_mb"]["tras_lectura_completa"] = mb(proc)
    print(f"  lectura completa: {rep['tiempo_lectura_completa_s']}s | RSS {mb(proc):,.0f} MB", flush=True)

    t = time.perf_counter()
    tipos_mal = {c: out_types.get(c) for c in pred
                 if out_types.get(c) != tipos[c.rsplit("_", 1)[0] if c not in tipos else c]}
    n_out, n_k = con.execute(f"SELECT count(*), count(DISTINCT (numero_de_cliente, foto_mes)) FROM read_parquet('{glob}')").fetchone()
    filas_mes = dict(con.execute(f"SELECT foto_mes, count(*) FROM read_parquet('{glob}') GROUP BY 1").fetchall())
    anti = con.execute(f"""SELECT
        (SELECT count(*) FROM src ANTI JOIN read_parquet('{glob}') f USING (numero_de_cliente, foto_mes)),
        (SELECT count(*) FROM read_parquet('{glob}') f ANTI JOIN src USING (numero_de_cliente, foto_mes))""").fetchone()
    # Originales idénticos al origen, mes a mes
    orig_diff = 0
    for m in meses:
        expr = " + ".join(f"count(*) FILTER (WHERE f.{q(c)} IS DISTINCT FROM s.{q(c)})" for c in cols)
        orig_diff += con.execute(
            f"SELECT {expr} FROM read_parquet('{(carpeta / f'features_{m}.parquet').as_posix()}') f "
            f"JOIN src s USING (numero_de_cliente, foto_mes) WHERE s.foto_mes = {m}").fetchone()[0]
    rep["memoria_mb"]["tras_esquema_claves_originales"] = mb(proc)
    print(f"  esquema, claves y originales: {time.perf_counter() - t:.1f}s | RSS {mb(proc):,.0f} MB", flush=True)
    num = verificar_numpy(con, glob, cols, tipos)
    rep["memoria_mb"]["tras_verificacion_numpy"] = mb(proc)
    rep["tiempo_verificacion_s"] = round(time.perf_counter() - t, 1)
    print(f"  numpy: {rep['tiempo_verificacion_s']}s acumulado | RSS {mb(proc):,.0f} MB", flush=True)

    sospechosas = [c for c in out_names if "clase" in c.lower() or c in TARGET_NAMES]
    rep.update({
        "columnas": {"claves": KEYS, "originales": len(cols), "derivadas": len(pred) - len(cols),
                     "predictores": len(pred), "total_archivo": len(out_names)},
        "filas": int(n_out), "disponibilidad_lag_por_mes": disponibilidad,
        "verificacion_numpy": num, "tipos_no_conservados": tipos_mal,
        "columnas_sospechosas_de_target": sospechosas,
    })
    return {
        "archivos_esperados": True,
        "lectura_completa_filas_igual_metadatos": all(v["filas_leidas"] == v["filas_metadatos"] for v in lectura.values()),
        "cada_archivo_un_solo_mes": all(v["foto_mes_min"] == v["foto_mes_max"] == int(m) for m, v in lectura.items()),
        "metadatos_kv_claves": all(v["kv_claves"] == ",".join(KEYS) and v["kv_n_predictores"] == str(N_PREDICTORES)
                                   for v in lectura.values()),
        "columnas_762_claves_mas_760": out_names == KEYS + pred,
        "predictores_760": len(pred) == N_PREDICTORES,
        "sin_target_entre_predictores": not sospechosas and not (set(pred) & (target_cols - set(KEYS))),
        "claves_no_son_predictores": not (set(KEYS) & set(pred)),
        "tipos_conservados": not tipos_mal,
        "filas_igual_origen": n_out == sum(v["filas"] for v in disponibilidad.values())
                              and {str(k): int(v) for k, v in filas_mes.items()}
                              == {m: v["filas"] for m, v in disponibilidad.items()},
        "claves_unicas_y_misma_cobertura": n_out == n_k and anti == (0, 0),
        "originales_identicos": orig_diff == 0,
        "sin_observaciones_futuras": futuro == 0,
        "derivadas_igual_numpy": num["claves_mismo_orden"] and not num["columnas_con_diferencias"],
        "origen_sin_modificar": (SRC.stat().st_size, SRC.stat().st_mtime_ns) == src_stat,
        "origen_anterior_a_los_archivos": all(SRC.stat().st_mtime < (carpeta / f).stat().st_mtime for f in esperados),
    }


def publicar(carpeta: Path, intentos: int = 30, espera_s: float = 2.0) -> int:
    """Renombra `carpeta` a DST. Reintenta si otro proceso (p. ej. el antivirus) tiene un archivo abierto."""
    for i in range(1, intentos + 1):
        if DST.exists():
            raise RuntimeError(f"{mostrar(DST)} ya existe; no se sobrescribe")
        try:
            os.rename(carpeta, DST)
            return i
        except PermissionError:
            if i == intentos:
                raise
            time.sleep(espera_s)
    return intentos


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Genera lag1, delta1, lag2 y delta2 para competencia_02 (2019).")
    ap.add_argument("--validar-existente", type=Path, metavar="CARPETA",
                    help="valida y publica una generación ya escrita, sin recalcular features")
    args = ap.parse_args(argv)
    recuperar = args.validar_existente is not None
    carpeta = (ROOT / args.validar_existente).resolve() if recuperar else TMP

    t0 = time.perf_counter()
    proc = psutil.Process()
    rep = {"modo": "validar_existente" if recuperar else "generar", "definicion": DEFINICION,
           "carpeta": mostrar(carpeta), "memoria_mb": {"inicio": mb(proc)}}

    # 1. Fórmulas sobre datos sintéticos
    t = time.perf_counter()
    rep["prueba_sintetica"] = prueba_sintetica()
    print(f"[prueba sintética] ok={rep['prueba_sintetica']['ok']} {rep['prueba_sintetica']}", flush=True)
    if not rep["prueba_sintetica"]["ok"]:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
        return 2
    rep["tiempo_prueba_s"] = round(time.perf_counter() - t, 1)

    if DST.exists():
        print(f"ERROR: {mostrar(DST)} ya existe; no se sobrescribe.")
        return 1
    if recuperar:
        if carpeta.parent != DATA_DIR or not carpeta.name.startswith(f"{DST.name}.tmp-") or not carpeta.is_dir():
            print(f"ERROR: {carpeta} no es una carpeta temporal de 04 en {mostrar(DATA_DIR)}.")
            return 1
        if (carpeta / "manifiesto.json").exists():
            print("ERROR: la carpeta ya tiene manifiesto.json; no se sobrescribe.")
            return 1
    else:
        TMP.mkdir()
    src_stat = (SRC.stat().st_size, SRC.stat().st_mtime_ns)
    rep["origen"] = {"archivo": mostrar(SRC), "bytes": src_stat[0],
                     "modificado": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(SRC.stat().st_mtime))}
    DUCK_TMP.mkdir()
    con = duckdb.connect()
    con.execute(f"SET temp_directory = '{DUCK_TMP.as_posix()}'")
    con.execute("SET memory_limit = '4GB'")
    con.execute("SET threads = 4")
    con.execute("SET preserve_insertion_order = true")
    try:
        con.execute(f"CREATE VIEW src AS SELECT * FROM read_parquet('{SRC.as_posix()}')")
        tipos = dict(con.execute("SELECT column_name, column_type FROM (DESCRIBE src)").fetchall())
        cols = [c for c in tipos if c not in KEYS]
        target_cols = {r[0] for r in con.execute(
            f"SELECT column_name FROM (DESCRIBE SELECT * FROM read_parquet('{TARGET.as_posix()}'))").fetchall()}
        pred = nombres(cols)
        if len(cols) != N_ORIGINALES or len(pred) != N_PREDICTORES or len(set(pred)) != len(pred):
            raise RuntimeError(f"cantidad de columnas inesperada: {len(cols)} originales, {len(pred)} predictores")

        # 2. Observaciones previas (sólo claves) y garantía de no-futuro
        crear_prev(con, "src")
        futuro = con.execute("SELECT count(*) FROM prev WHERE m1 >= foto_mes OR m2 >= m1").fetchone()[0]
        disponibilidad = {str(m): {"filas": int(n), "con_lag1": int(a), "con_lag2": int(b)}
                          for m, n, a, b in con.execute(
                              "SELECT foto_mes, count(*), count(m1), count(m2) FROM prev GROUP BY 1 ORDER BY 1").fetchall()}
        meses = [int(m) for m in disponibilidad]

        # 3. Un archivo por mes (sólo en modo generar)
        if not recuperar:
            t = time.perf_counter()
            kv = ("{claves: 'numero_de_cliente,foto_mes', n_predictores: '760', "
                  "definicion: 'lag por observaciones previas; delta=x-lag', "
                  "etiquetas: 'competencia_02_2019_target.parquet (separado)'}")
            tiempos = {}
            for m in meses:
                tm = time.perf_counter()
                con.execute(f"COPY ({sql_mes('src', cols, m)}) TO '{(TMP / f'features_{m}.parquet').as_posix()}' "
                            f"(FORMAT parquet, COMPRESSION zstd, KV_METADATA {kv})")
                tiempos[str(m)] = round(time.perf_counter() - tm, 1)
                print(f"  {m}: {tiempos[str(m)]:5.1f}s | RSS {mb(proc):,.0f} MB", flush=True)
            rep["tiempo_generacion_s"] = round(time.perf_counter() - t, 1)
            rep["tiempo_por_mes_s"] = tiempos
            rep["memoria_mb"]["tras_generacion"] = mb(proc)

        # 4. Validaciones
        print("[validación] leyendo y verificando...", flush=True)
        checks = validar(con, carpeta, cols, tipos, target_cols, pred, meses, disponibilidad, futuro,
                         src_stat, rep, proc)
        rep.update({"checks": checks, "ok": all(checks.values())})
        con.close()

        if rep["ok"]:
            manifest = {"claves": KEYS, "predictores": pred, "etiquetas": TARGET.name,
                        "definicion": DEFINICION, "origen": mostrar(SRC),
                        "archivos": {m: {"filas": v["filas_leidas"], "huella_xor": v["huella_xor"]}
                                     for m, v in rep["lectura_completa"].items()},
                        "validacion": mostrar(OUT)}
            if recuperar:
                manifest["nota"] = (f"generado por la corrida {carpeta.name.rsplit('-', 1)[1]}, que se cortó antes de "
                                    "validar; validado y publicado sin recalcular (--validar-existente). Los metadatos "
                                    "KV de cada Parquet dicen 'provisional'; vale la definición de este manifiesto.")
            (carpeta / "manifiesto.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
            try:
                rep["intentos_rename"] = publicar(carpeta)
                rep["publicado"] = mostrar(DST)
                rep["tamano_mb"] = round(sum(p.stat().st_size for p in DST.iterdir()) / 2**20, 1)
            except Exception as e:  # noqa: BLE001
                rep["publicado"] = False
                rep["error_publicacion"] = repr(e)
                rep["temporal_conservado"] = mostrar(carpeta)
        else:
            rep["publicado"] = False
            rep["temporal_conservado"] = mostrar(carpeta)
    finally:
        try:
            con.close()
        except Exception:  # noqa: BLE001
            pass
        shutil.rmtree(DUCK_TMP, ignore_errors=True)
        rep["recursos"] = {"tiempo_total_s": round(time.perf_counter() - t0, 1),
                           "rss_final_mb": mb(proc),
                           "pico_working_set_so_mb": round(getattr(proc.memory_info(), "peak_wset", 0) / 2**20, 1)}
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n== Checks ==")
    for k, v in rep.get("checks", {}).items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print(f"\nColumnas: {rep.get('columnas')} | filas: {rep.get('filas')}")
    num = rep.get("verificacion_numpy", {})
    print(f"Numpy: {num.get('celdas_comparadas')} celdas, diferencias: {num.get('columnas_con_diferencias')}")
    print(f"Publicado: {rep.get('publicado')} | tamaño {rep.get('tamano_mb')} MB | {rep.get('error_publicacion', '')}")
    print(f"Tiempos: generación {rep.get('tiempo_generacion_s')}s, lectura {rep.get('tiempo_lectura_completa_s')}s, "
          f"verificación {rep.get('tiempo_verificacion_s')}s | memoria {rep['memoria_mb']} | {rep['recursos']}")
    print(f"Reporte: {mostrar(OUT)}")
    if not rep.get("ok"):
        return 2
    return 0 if rep.get("publicado") else 3


if __name__ == "__main__":
    sys.exit(main())
