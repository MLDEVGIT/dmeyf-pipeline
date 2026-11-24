"""Ejecución mensual: CSV crudo de un mes -> features -> inferencia -> envíos.

Uso:
  python -m pipeline_competencia02.ejecutar_mes --entorno <dir> --entrada <csv> --mes AAAAMM \
      --estrategia cupo_fijo:1000 --estrategia porcentaje:1 --principal cupo_fijo

Etapas:
  1. Recepción: copia el CSV al entorno (entradas/AAAAMM/<ejecucion>/) y registra su sha256.
  2. Validación: esquema igual al crudo del entorno (nombres y orden), sin
     columnas de target, claves no nulas y únicas, un único foto_mes igual a
     --mes, valores numéricos tipables con las reglas de 02, y orden temporal:
     la historia termina justo en el mes anterior y no contiene meses >= --mes.
  3. Features sólo para el mes recibido, con la lógica compartida de 04
     (pipeline_competencia02.features) sobre historia + mes actual.
  4. Inferencia con el modelo guardado en el entorno, por bloques de filas: un
     único score que comparten todas las estrategias.
  5. Estrategias: la principal define output/churn_AAAAMM.csv
     (numero_de_cliente,probabilidad,enviar); las decisiones de todas van a
     diagnosticos/AAAAMM/decisiones_AAAAMM.csv, con seleccionados, proporción
     y solapamiento en el reporte.
  6. Publicación todo o nada de diagnóstico, salida oficial e historia.

Incidentes: cada chequeo registra un incidente con regla, variables y acción
según politica_incidentes.json (rechazar corta sin publicar; advertir
registra y sigue sin cambiar score ni selección). El reporte separa
estado_operativo (completado/fallido) de estado_calidad
(con_alertas/sin_alertas/no_evaluada): "completado" no garantiza calidad
predictiva.

Estados por mes (registro/meses/AAAAMM.json): en_curso, fallido y completado.
  - Todo el intento se prepara en tmp/<ejecucion>/. Sólo al completar se
    publican, con rename y deshaciendo si un paso falla, diagnosticos/AAAAMM/,
    output/churn_AAAAMM.csv e historia/foto_mes=AAAAMM.parquet.
  - Ante un fallo no se publica nada. El intento queda en
    diagnosticos/AAAAMM.fallido-<ejecucion>/ y el mes puede reintentarse.
  - Un mes completado se rechaza. Un mes en curso también, mientras su proceso
    siga vivo; el candado registra PID y hora de creación porque el PID puede
    reutilizarse. Si el proceso murió, el intento se registra como fallido.

Aislamiento: todas las lecturas pasan por Entorno.leer, que rechaza rutas
fuera del entorno y las registra. El entorno sólo contiene la historia que se
copió al crearlo más los meses completados.

Códigos de salida: 0 completado, 2 fallido, 4 rechazado (completado o en curso).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path

import duckdb
import lightgbm as lgb
import numpy as np
import pandas as pd
import psutil

from . import estrategias as E
from . import incidentes as I
from .features import KEYS, crear_prev, nombres, q, sql_mes

INT_RE = r"-?[0-9]+"   # mismas reglas de tipado que experimento_sampling/02
MAX_EXACTO = 2**53
HILOS = 4
VECTORES_POR_BLOQUE = 8   # 8 x 2048 filas por bloque de inferencia
LOTE_COLUMNAS = 50
CUANTILES = [0, 0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 0.999, 1]
EXIT_FALLA, EXIT_DUPLICADO = 2, 4

log = logging.getLogger("pipeline_competencia02")


class Entorno:
    def __init__(self, raiz: Path):
        self.raiz = raiz.resolve()
        if not (self.raiz / "entorno.json").exists():
            raise FileNotFoundError(f"{self.raiz} no es un entorno (falta entorno.json)")
        self.cfg = json.loads((self.raiz / "entorno.json").read_text(encoding="utf-8"))
        self.lecturas: list[str] = []

    def leer(self, p: Path) -> str:
        """Ruta posix para leer, sólo si está dentro del entorno. Queda registrada."""
        p = Path(p).resolve()
        if not p.is_relative_to(self.raiz):
            raise PermissionError(f"lectura fuera del entorno: {p}")
        rel = p.relative_to(self.raiz).as_posix()
        if rel not in self.lecturas:
            self.lecturas.append(rel)
        return p.as_posix()


def anterior(mes: int) -> int:
    a, m = divmod(mes, 100)
    return a * 100 + m - 1 if m > 1 else (a - 1) * 100 + 12


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def memoria(proc) -> dict:
    mi = proc.memory_info()
    return {"rss_mb": round(mi.rss / 2**20, 1),
            "pico_working_set_mb": round(getattr(mi, "peak_wset", 0) / 2**20, 1),
            "pico_commit_privado_mb": round(getattr(mi, "peak_pagefile", 0) / 2**20, 1)}


def agregar(con, tabla: str, exprs: list[str]) -> list:
    out = []
    for i in range(0, len(exprs), LOTE_COLUMNAS):
        out.extend(con.execute(f"SELECT {', '.join(exprs[i:i + LOTE_COLUMNAS])} FROM {tabla}").fetchone())
    return out


# --------------------------------------------------------------------------
def validar_entrada(con, env: Entorno, csv_path: Path, mes: int, trabajo: Path, rep: dict,
                    pol: I.Politica) -> tuple[list[str], dict, Path]:
    esquema = {c: t for c, t in env.cfg["esquema_crudo"]}
    with open(env.leer(csv_path), encoding="utf-8", newline="") as f:
        cab = next(csv.reader(f))

    # Esquema: faltantes, adicionales, repetidas, targets y orden se diagnostican por separado
    diag = I.diagnosticar_esquema(cab, list(esquema))
    rep["esquema"] = diag
    if diag["repetidas"]:
        pol.registrar("columnas_repetidas", diag["repetidas"])
    if diag["targets"]:
        pol.registrar("columnas_de_target", diag["targets"])
    if diag["faltantes"]:
        pol.registrar("columnas_faltantes", diag["faltantes"])
    if [c for c in diag["adicionales"] if c not in diag["targets"]]:
        pol.registrar("columnas_adicionales", [c for c in diag["adicionales"] if c not in diag["targets"]])
    if diag["orden_distinto"]:
        pol.registrar("orden_de_columnas_distinto", diag["columnas_fuera_de_orden"],
                      "las columnas comunes aparecen en otro orden relativo")
    pol.cortar_si_rechazo()
    if not diag["identico"]:
        # Sólo se llega acá si la política advierte en vez de rechazar: no hay normalización de esquema
        raise RuntimeError("el esquema difiere y no hay normalización implementada; configure la regla para rechazar")

    varchar = "{" + ", ".join(f"'{c}': 'VARCHAR'" for c in cab) + "}"
    con.execute(f"CREATE TEMP TABLE crudo AS SELECT * FROM read_csv('{env.leer(csv_path)}', header=true, "
                f"nullstr='', auto_detect=false, columns={varchar})")
    n = con.execute("SELECT count(*) FROM crudo").fetchone()[0]
    if n == 0:
        pol.registrar("entrada_vacia", detalle="0 filas")
        pol.cortar_si_rechazo()

    # Valores tipables con las reglas de 02 (sin redondeos silenciosos)
    def invalido(c: str) -> str:
        dbl = f"try_cast({q(c)} AS DOUBLE)"
        if esquema[c] == "DOUBLE":
            return f"count(*) FILTER (WHERE {q(c)} IS NOT NULL AND {dbl} IS NULL)"
        entero_real = f"coalesce({dbl} = trunc({dbl}) AND abs({dbl}) <= {MAX_EXACTO}, false)"
        literal = f"(regexp_full_match({q(c)}, '{INT_RE}') AND try_cast({q(c)} AS BIGINT) IS NOT NULL)"
        return f"count(*) FILTER (WHERE {q(c)} IS NOT NULL AND NOT {literal} AND NOT {entero_real})"

    inval = dict(zip(cab, agregar(con, "crudo", [invalido(c) for c in cab])))
    inval = {c: int(v) for c, v in inval.items() if v}
    if inval:
        pol.registrar("valores_no_tipables", list(inval), inval)
        pol.cortar_si_rechazo()

    def cast(c: str) -> str:
        if esquema[c] == "DOUBLE":
            return f"CAST({q(c)} AS DOUBLE) AS {q(c)}"
        return (f"CASE WHEN regexp_full_match({q(c)}, '{INT_RE}') THEN CAST({q(c)} AS BIGINT) "
                f"ELSE CAST(CAST({q(c)} AS DOUBLE) AS BIGINT) END AS {q(c)}")

    # El mes tipado va a Parquet, como el histórico que usó 04; así src es un único read_parquet
    actual_pq = trabajo / f"foto_mes={mes}.parquet"
    con.execute(f"COPY (SELECT {', '.join(cast(c) for c in cab)} FROM crudo) TO '{actual_pq.as_posix()}' "
                f"(FORMAT parquet, COMPRESSION zstd)")
    con.execute(f"CREATE VIEW actual AS SELECT * FROM read_parquet('{env.leer(actual_pq)}')")
    no_literales = sum(agregar(con, "crudo", [
        f"count(*) FILTER (WHERE {q(c)} IS NOT NULL AND NOT regexp_full_match({q(c)}, '{INT_RE}'))"
        for c in cab if esquema[c] == "BIGINT"]))
    con.execute("DROP TABLE crudo")

    nulos_k, n_cli, meses = con.execute(
        "SELECT count(*) FILTER (WHERE numero_de_cliente IS NULL OR foto_mes IS NULL), "
        "count(DISTINCT numero_de_cliente), list(DISTINCT foto_mes) FROM actual").fetchone()
    hist_files = sorted((env.raiz / "historia").glob("foto_mes=*.parquet"))
    hist_meses = sorted(int(p.stem.split("=")[1]) for p in hist_files)
    contenido = con.execute(
        f"SELECT list(DISTINCT foto_mes ORDER BY foto_mes) FROM read_parquet({[env.leer(p) for p in hist_files]})"
    ).fetchone()[0]
    tipos_hist = {c: t for c, t, *_ in con.execute(
        f"DESCRIBE SELECT * FROM read_parquet({[env.leer(p) for p in hist_files]})").fetchall()}
    checks = {
        "filas_mayor_a_cero": n > 0,
        "claves_no_nulas": nulos_k == 0,
        "numero_de_cliente_unico": n_cli == n,
        "mes_unico_igual_al_pedido": sorted(meses) == [mes],
        "historia_nombres_igual_contenido": contenido == hist_meses,
        "historia_sin_meses_iguales_o_posteriores": all(m < mes for m in hist_meses),
        "historia_termina_en_mes_anterior": bool(hist_meses) and hist_meses[-1] == anterior(mes),
        "esquema_historia_igual_entrada": tipos_hist == esquema,
    }
    rep["validacion"] = {"filas": int(n), "clientes": int(n_cli), "meses_en_entrada": sorted(meses),
                         "historia_meses": hist_meses, "enteros_no_literales": int(no_literales),
                         "checks": checks}
    if nulos_k:
        pol.registrar("claves_nulas", detalle=f"{nulos_k} filas con clave nula")
    if n_cli != n:
        pol.registrar("claves_duplicadas", ["numero_de_cliente"], f"{n - n_cli} filas repetidas")
    if sorted(meses) != [mes]:
        pol.registrar("mes_distinto_del_pedido", detalle=f"foto_mes en la entrada {sorted(meses)}, pedido {mes}")
    if not (checks["historia_sin_meses_iguales_o_posteriores"] and checks["historia_termina_en_mes_anterior"]):
        pol.registrar("mes_fuera_de_secuencia",
                      detalle=f"historia {hist_meses[:1]}...{hist_meses[-1:]}; se esperaba que terminara en "
                              f"{anterior(mes)} y no tuviera meses >= {mes}")
    if not (checks["historia_nombres_igual_contenido"] and checks["esquema_historia_igual_entrada"]):
        pol.registrar("historia_inconsistente", detalle={k: checks[k] for k in
                                                         ("historia_nombres_igual_contenido",
                                                          "esquema_historia_igual_entrada")})
    pol.cortar_si_rechazo()
    return [env.leer(p) for p in hist_files], esquema, actual_pq


def perfil_mes(con, tabla: str, cols: list[str], hist_ultimo: str, n: int, pol: I.Politica) -> tuple[dict, dict]:
    """Faltantes por columna y monitoreo de calidad del mes. Registra advertencias; no cambia datos.

    Criterio por columna (categorías disjuntas, ver incidentes.clasificar_columna):
      columna_100_nula     todas las filas NULL
      observados_en_cero   >= 1 no nulo y todos los no nulos = 0
      constante_no_nula    >= 1 no nulo y todos los no nulos iguales y != 0
    Ninguna se interpreta como error: puede ser un producto sin uso, una
    variable sin movimiento o un problema de carga. Sólo se informa.
    """
    stats = agregar(con, tabla, [e for c in cols for e in (f"count({q(c)})", f"count(*) FILTER (WHERE {q(c)} = 0)",
                                                           f"count(DISTINCT {q(c)})", f"min({q(c)})")])
    nn = {c: int(stats[4 * i]) for i, c in enumerate(cols)}
    nulos = {c: n - nn[c] for c in cols}
    categorias = {}
    for i, c in enumerate(cols):
        cat = I.clasificar_columna(n, nn[c], int(stats[4 * i + 1]), int(stats[4 * i + 2]))
        if cat:
            categorias.setdefault(cat, {})[c] = None if cat == "nula_100" else float(stats[4 * i + 3])
    for cat, columnas in categorias.items():
        pol.registrar(I.REGLA_POR_CATEGORIA[cat], sorted(columnas),
                      {"valores": columnas} if cat == "constante_no_nula" else None)

    n_prev = con.execute(f"SELECT count(*) FROM read_parquet('{hist_ultimo}')").fetchone()[0]
    nulos_prev = dict(zip(cols, map(int, agregar(con, f"read_parquet('{hist_ultimo}')",
                                                  [f"count(*) - count({q(c)})" for c in cols]))))
    umbral = pol.umbrales["cambio_tasa_nulos"]
    cambio = {c: round(nulos[c] / n - nulos_prev[c] / n_prev, 4) for c in cols
              if abs(nulos[c] / n - nulos_prev[c] / n_prev) > umbral}
    if cambio:
        pol.registrar("cambio_tasa_nulos", sorted(cambio), {"umbral": umbral, "cambio": cambio})
    pol.calidad_evaluada = True
    faltantes = {"celdas": sum(nulos.values()), "columnas_con_faltantes": sum(1 for v in nulos.values() if v),
                 "por_columna": {c: v for c, v in nulos.items() if v}}
    return faltantes, {k: sorted(v) for k, v in categorias.items()}


def inferir(con, env: Entorno, feat: Path, pred: list[str], rep: dict) -> tuple[np.ndarray, np.ndarray]:
    booster = lgb.Booster(model_file=env.leer(env.raiz / "modelo" / "modelo.txt"))
    if booster.feature_name() != pred or booster.num_feature() != len(pred):
        raise ValueError("los predictores del modelo no coinciden con las features calculadas")
    tipos = {c: t for c, t, *_ in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{env.leer(feat)}')").fetchall()}
    otros = sorted({tipos[c] for c in pred} - {"BIGINT", "DOUBLE"})
    if otros:
        raise ValueError(f"tipos no previstos en las features: {otros}")
    expr = ", ".join(f"CAST({q(c)} AS DOUBLE) AS {q(c)}" if tipos[c] == "BIGINT" else q(c) for c in pred)
    con.execute("SET threads = 1")  # flujo secuencial: orden del archivo y poca memoria
    rel = con.execute(f"SELECT numero_de_cliente, {expr} FROM read_parquet('{env.leer(feat)}')")
    clientes, probs = [], []
    while True:
        df = rel.fetch_df_chunk(VECTORES_POR_BLOQUE)
        if df.empty:
            break
        X = df[pred].to_numpy(dtype=np.float64, na_value=np.nan)
        clientes.append(df["numero_de_cliente"].to_numpy(np.int64))
        probs.append(booster.predict(X, num_threads=HILOS))
        del df, X
    del rel
    con.execute(f"SET threads = {HILOS}")
    rep["modelo"] = {"arboles": booster.num_trees(), "predictores": booster.num_feature(),
                     "sha256": sha256(env.raiz / "modelo" / "modelo.txt"),
                     "conversion": "BIGINT -> float64 (CAST, exacto); DOUBLE sin cambios; NULL -> NaN"}
    return np.concatenate(clientes), np.concatenate(probs)


def distribucion(prob: np.ndarray) -> dict:
    return {"cuantiles": {str(c): float(v) for c, v in zip(CUANTILES, np.quantile(prob, CUANTILES))},
            "media": float(prob.mean()), "exactamente_0": int((prob == 0).sum()),
            "exactamente_1": int((prob == 1).sum()), "mayor_0_5": int((prob > 0.5).sum())}


def escribir_csv(path: Path, clientes: np.ndarray, prob: np.ndarray, columnas: dict[str, np.ndarray]):
    """CSV con coma, ordenado por numero_de_cliente: numero_de_cliente, probabilidad y columnas de decisión."""
    orden = np.argsort(clientes, kind="stable")
    df = pd.DataFrame({"numero_de_cliente": clientes[orden], "probabilidad": prob[orden],
                       **{k: v[orden].astype(np.int8) for k, v in columnas.items()}})
    df.to_csv(path, sep=",", index=False, lineterminator="\n")


def comparar_estrategias(decisiones: dict[str, np.ndarray], principal: str, n: int) -> dict:
    """Seleccionados, proporción y solapamiento de cada estrategia contra la principal."""
    p = decisiones[principal]
    out = {}
    for nombre, d in decisiones.items():
        inter = int((d & p).sum())
        union = int((d | p).sum())
        out[nombre] = {"seleccionados": int(d.sum()), "proporcion": round(float(d.sum()) / n, 6),
                       "interseccion_con_principal": inter, "solo_esta": int((d & ~p).sum()),
                       "solo_principal": int((p & ~d).sum()), "jaccard_con_principal": round(inter / union, 6),
                       "anidada_con_principal": bool(inter == min(int(d.sum()), int(p.sum())))}
    return out


# --------------------------------------------------------------------------
# Registro: estado por mes (en_curso / fallido / completado) y candado del intento
def escribir_atomico(path: Path, data: dict):
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def proceso_vivo(info: dict) -> bool:
    """El PID puede reutilizarse: se exige además la misma hora de creación del proceso."""
    try:
        return abs(psutil.Process(info["pid"]).create_time() - info["creado"]) < 1e-3
    except (psutil.NoSuchProcess, KeyError):
        return False


def adquirir(reg: Path, mes: int, ejecucion: str, proc) -> tuple[bool, str, dict]:
    """Toma el candado del mes y lo pasa a en_curso. Rechaza meses completados o con un intento vivo."""
    candado = reg / "meses" / f"{mes}.lock"
    yo = {"pid": os.getpid(), "creado": proc.create_time(), "ejecucion": ejecucion}
    for _ in range(2):
        try:
            with open(candado, "x", encoding="utf-8") as f:
                json.dump(yo, f)
            break
        except FileExistsError:
            otro = json.loads(candado.read_text(encoding="utf-8"))
            if proceso_vivo(otro):
                return False, f"en_curso por la ejecución {otro['ejecucion']}", otro
            # Intento interrumpido (proceso muerto): queda registrado como fallido
            estado_path = reg / "meses" / f"{mes}.json"
            if estado_path.exists():
                est = json.loads(estado_path.read_text(encoding="utf-8"))
                if est.get("estado") == "en_curso":
                    est.update({"estado": "fallido", "motivo": f"interrumpida (candado huérfano de {otro['ejecucion']})"})
                    escribir_atomico(estado_path, est)
            candado.unlink()
    else:
        return False, "no se pudo tomar el candado", {}
    estado_path = reg / "meses" / f"{mes}.json"
    est = json.loads(estado_path.read_text(encoding="utf-8")) if estado_path.exists() else {"mes": mes, "intentos": []}
    if est.get("estado") == "completado":
        candado.unlink()
        return False, f"completado por la ejecución {est['ejecucion']}", est
    est.update({"estado": "en_curso", "ejecucion": ejecucion, "inicio": time.strftime("%Y-%m-%dT%H:%M:%S")})
    est["intentos"].append({"ejecucion": ejecucion, "estado": "en_curso"})
    escribir_atomico(estado_path, est)
    return True, "", est


def cerrar(reg: Path, mes: int, est: dict, estado: str, motivo: str = ""):
    est.update({"estado": estado, "fin": time.strftime("%Y-%m-%dT%H:%M:%S"), "motivo": motivo})
    est["intentos"][-1]["estado"] = estado
    escribir_atomico(reg / "meses" / f"{mes}.json", est)
    (reg / "meses" / f"{mes}.lock").unlink(missing_ok=True)


def falla_inyectada(punto: str):
    """Sólo para pruebas: PIPELINE_C02_FALLA=<punto> provoca una falla controlada en ese punto."""
    if os.environ.get("PIPELINE_C02_FALLA") == punto:
        raise RuntimeError(f"falla inyectada para prueba: {punto}")


def publicar(movimientos: list[tuple[Path, Path]]):
    """Renombra todo o nada: si un paso falla, deshace los anteriores."""
    for _, dst in movimientos:
        if dst.exists():
            raise FileExistsError(f"{dst} ya existe; no se sobrescribe")
    hechos = []
    try:
        for src, dst in movimientos:
            os.rename(src, dst)
            hechos.append((src, dst))
            falla_inyectada("durante_publicacion")
    except Exception:
        for src, dst in reversed(hechos):
            os.rename(dst, src)
        raise


def registrar(env: Entorno, rep: dict):
    reg = env.raiz / "registro"
    with open(reg / "ejecuciones.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rep, ensure_ascii=False, default=str) + "\n")
    if rep.get("estado") not in ("completado", "fallido"):
        return
    d = rep.get("distribucion_scores", {}).get("cuantiles", {})
    comp = rep.get("comparacion_estrategias", {})
    fila = {"ejecucion": rep["ejecucion"], "mes": rep["mes"], "inicio": rep["inicio"], "fin": rep.get("fin"),
            "estado_operativo": rep["estado"], "estado_calidad": rep.get("estado_calidad"),
            "reglas_activadas": ";".join(f"{i['regla']}:{i['accion']}:{len(i['variables'])}"
                                         for i in rep.get("incidentes", [])),
            "rechazo": ";".join(i["regla"] for i in rep.get("rechazo", [])),
            "clientes": rep.get("validacion", {}).get("clientes"),
            "clientes_sin_historia": rep.get("features", {}).get("clientes_sin_historia"),
            "celdas_faltantes": rep.get("faltantes", {}).get("celdas"),
            "columnas_con_faltantes": rep.get("faltantes", {}).get("columnas_con_faltantes"),
            "prob_min": d.get("0"), "prob_p50": d.get("0.5"), "prob_p99": d.get("0.99"), "prob_max": d.get("1"),
            "prob_media": rep.get("distribucion_scores", {}).get("media"),
            "principal": rep.get("principal"),
            "envios": ";".join(f"{k}={v['seleccionados']}" for k, v in comp.items()),
            "proporcion": ";".join(f"{k}={v['proporcion']}" for k, v in comp.items()),
            "interseccion_con_principal": ";".join(f"{k}={v['interseccion_con_principal']}" for k, v in comp.items()),
            "salida_oficial": rep.get("salida_oficial"),
            "tiempo_total_s": rep.get("tiempos", {}).get("total_s"),
            "pico_working_set_mb": rep.get("memoria", {}).get("pico_working_set_mb"),
            "pico_commit_privado_mb": rep.get("memoria", {}).get("pico_commit_privado_mb"),
            "error": rep.get("error", "")}
    acum = reg / "reporte_acumulado.csv"
    nuevo = not acum.exists()
    with open(acum, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fila))
        if nuevo:
            w.writeheader()
        w.writerow(fila)


def estados(rep: dict, pol: I.Politica):
    """Estado operativo y de calidad por separado, con cada incidente: variables, regla y acción."""
    rep["estado_operativo"] = rep["estado"]
    rep["estado_calidad"] = pol.estado_calidad()
    rep["incidentes"] = pol.incidentes
    rep["alertas"] = pol.textos()
    rep["aviso"] = I.AVISO


# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ejecución mensual del pipeline de la competencia 02.")
    ap.add_argument("--entorno", type=Path, required=True)
    ap.add_argument("--entrada", type=Path, required=True, help="CSV crudo del mes, sin targets")
    ap.add_argument("--mes", type=int, required=True)
    ap.add_argument("--estrategia", action="append", required=True, help="nombre:parametro, p. ej. cupo_fijo:1000")
    ap.add_argument("--principal", required=True, help="estrategia que define la salida oficial (elegida de antemano)")
    a = ap.parse_args(argv)

    t0 = time.perf_counter()
    proc = psutil.Process()
    env = Entorno(a.entorno)
    estrategias = [E.construir(s) for s in a.estrategia]
    nombres_e = [e.nombre for e in estrategias]
    if len(set(nombres_e)) != len(nombres_e) or a.principal not in nombres_e:
        raise ValueError(f"estrategias repetidas o principal {a.principal!r} fuera de {nombres_e}")
    mes = a.mes
    ejecucion = f"{mes}_{time.strftime('%Y%m%dT%H%M%S')}_{os.getpid()}"
    reg = env.raiz / "registro"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S",
                        handlers=[logging.FileHandler(reg / f"log_{ejecucion}.txt", encoding="utf-8"),
                                  logging.StreamHandler(sys.stdout)])
    pol = I.Politica()
    rep = {"ejecucion": ejecucion, "mes": mes, "inicio": time.strftime("%Y-%m-%dT%H:%M:%S"), "pid": os.getpid(),
           "entorno": env.cfg["nombre"], "entrada_original": str(a.entrada), "principal": a.principal,
           "estrategias_configuradas": [e.describir() for e in estrategias], "politica_incidentes": pol.resumen()}

    ok, motivo, info = adquirir(reg, mes, ejecucion, proc)
    if not ok:
        rep.update({"estado": "rechazada", "motivo": motivo, "estado_existente": info})
        registrar(env, rep)
        log.error("Mes %s rechazado: %s.", mes, motivo)
        return EXIT_DUPLICADO
    est = info

    tiempos = {}
    trabajo = env.raiz / "tmp" / ejecucion          # todo el intento se prepara acá
    diag = trabajo / "diagnostico"
    duck_tmp = trabajo / "duckdb"
    oficial = env.raiz / "output" / f"churn_{mes}.csv"
    con = None
    codigo = EXIT_FALLA
    try:
        diag.mkdir(parents=True)
        log.info("Ejecución %s | entorno %s | principal %s | estrategias %s", ejecucion, env.cfg["nombre"],
                 a.principal, rep["estrategias_configuradas"])
        if (env.raiz / "diagnosticos" / str(mes)).exists() or oficial.exists() \
                or (env.raiz / "historia" / f"foto_mes={mes}.parquet").exists():
            raise FileExistsError("hay salidas o historia publicadas para este mes sin estado completado")

        # 1. Recepción
        t = time.perf_counter()
        destino = env.raiz / "entradas" / str(mes) / ejecucion
        destino.mkdir(parents=True)
        csv_path = destino / a.entrada.name
        shutil.copy2(a.entrada, csv_path)
        rep["entrada"] = {"archivo": csv_path.relative_to(env.raiz).as_posix(), "bytes": csv_path.stat().st_size,
                          "sha256": sha256(csv_path)}
        tiempos["recepcion_s"] = round(time.perf_counter() - t, 1)

        # 2. Validación
        t = time.perf_counter()
        con = duckdb.connect()
        con.execute(f"SET threads = {HILOS}")
        con.execute("SET memory_limit = '4GB'")  # como 04; desborda a disco en tmp/ del intento
        con.execute("SET preserve_insertion_order = true")
        con.execute(f"SET temp_directory = '{duck_tmp.as_posix()}'")
        hist, esquema, actual_pq = validar_entrada(con, env, csv_path, mes, trabajo, rep, pol)
        cols = [c for c in esquema if c not in KEYS]
        n = rep["validacion"]["filas"]
        rep["faltantes"], rep["categorias_columnas"] = perfil_mes(con, "actual", cols, hist[-1], n, pol)
        pol.cortar_si_rechazo()
        tiempos["validacion_s"] = round(time.perf_counter() - t, 1)
        log.info("[validación] %s | %s", rep["validacion"], memoria(proc))

        # 3. Features sólo del mes recibido
        t = time.perf_counter()
        pred = nombres(cols)
        pred_modelo = json.loads(Path(env.leer(env.raiz / "modelo" / "predictores.json")).read_text(encoding="utf-8"))
        if pred != pred_modelo:
            raise ValueError("los predictores calculables no coinciden con predictores.json del modelo")
        con.execute(f"CREATE VIEW src AS SELECT * FROM read_parquet({hist + [env.leer(actual_pq)]})")
        crear_prev(con, "src")
        futuro, n_k, con_l1, con_l2 = con.execute(
            f"SELECT (SELECT count(*) FROM prev WHERE m1 >= foto_mes OR m2 >= m1), count(*), count(m1), count(m2) "
            f"FROM prev WHERE foto_mes = {mes}").fetchone()
        if futuro:
            raise RuntimeError("hay observaciones previas con mes >= al actual")
        feat = diag / f"features_{mes}.parquet"
        kv = (f"{{claves: '{','.join(KEYS)}', n_predictores: '{len(pred)}', "
              f"definicion: 'lag por observaciones previas; delta=x-lag', ejecucion: '{ejecucion}'}}")
        con.execute(f"COPY ({sql_mes('src', cols, mes)}) TO '{feat.as_posix()}' "
                    f"(FORMAT parquet, COMPRESSION zstd, KV_METADATA {kv})")
        n_feat = con.execute(f"SELECT count(*) FROM read_parquet('{env.leer(feat)}')").fetchone()[0]
        if n_feat != n or n_k != n:
            raise RuntimeError(f"features con {n_feat} filas para {n} clientes")
        rep["features"] = {"archivo": f"diagnosticos/{mes}/{feat.name}", "filas": int(n_feat),
                           "predictores": len(pred), "con_lag1": int(con_l1), "con_lag2": int(con_l2),
                           "clientes_sin_historia": int(n_k - con_l1)}
        tiempos["features_s"] = round(time.perf_counter() - t, 1)
        log.info("[features] %s | %s", rep["features"], memoria(proc))

        # 4. Inferencia (un único score, compartido por todas las estrategias)
        t = time.perf_counter()
        clientes, prob = inferir(con, env, feat, pred, rep)
        if not (len(prob) == n and np.isfinite(prob).all() and ((prob >= 0) & (prob <= 1)).all()):
            raise RuntimeError("probabilidades no finitas, fuera de [0,1] o en cantidad distinta de los clientes")
        if len(np.unique(clientes)) != n:
            raise RuntimeError("clientes repetidos en las predicciones")
        rep["probabilidades_validas"] = True
        rep["distribucion_scores"] = distribucion(prob)
        if rep["distribucion_scores"]["exactamente_0"] or rep["distribucion_scores"]["exactamente_1"]:
            pol.registrar("scores_saturados", detalle={"iguales_a_0": rep["distribucion_scores"]["exactamente_0"],
                                                       "iguales_a_1": rep["distribucion_scores"]["exactamente_1"]})
        if rep["features"]["clientes_sin_historia"]:
            pol.registrar("clientes_sin_historia", detalle=rep["features"]["clientes_sin_historia"])
        pol.cortar_si_rechazo()
        pdf = pd.DataFrame({"numero_de_cliente": clientes, "foto_mes": np.full(len(clientes), mes, np.int64),
                            "probabilidad": prob})
        con.register("pdf", pdf)
        con.execute(f"COPY (SELECT * FROM pdf) TO '{(diag / f'predicciones_{mes}.parquet').as_posix()}' "
                    f"(FORMAT parquet, COMPRESSION zstd)")
        con.unregister("pdf")
        del pdf
        tiempos["inferencia_s"] = round(time.perf_counter() - t, 1)
        log.info("[inferencia] %s | %s", rep["distribucion_scores"], memoria(proc))

        # 5. Estrategias: mismo score, sólo cambia la selección
        t = time.perf_counter()
        decisiones = {e.nombre: e.seleccionar(clientes, prob) for e in estrategias}
        rep["comparacion_estrategias"] = comparar_estrategias(decisiones, a.principal, n)
        for e in estrategias:
            d = decisiones[e.nombre]
            umbral = float(prob[d].min()) if d.any() else None
            rep["comparacion_estrategias"][e.nombre].update({
                **e.describir(), "probabilidad_minima_enviada": umbral,
                "empates_en_el_corte": int((prob == umbral).sum()) if umbral is not None else 0})
            if e.provisional:
                pol.registrar("estrategia_provisional", [e.nombre], e.nota)
        rep["nota_estrategias"] = ("todas las estrategias comparten el mismo score y el mismo orden; sólo difieren en "
                                   "la cantidad seleccionada. No se comparan por AUC: el score es idéntico.")
        rep["cumple_requisito_estrategias"] = len(estrategias) >= E.ESTRATEGIAS_REQUERIDAS
        if not rep["cumple_requisito_estrategias"]:
            pol.registrar("estrategias_insuficientes", detalle=f"{len(estrategias)} de {E.ESTRATEGIAS_REQUERIDAS}")
        pol.cortar_si_rechazo()
        escribir_csv(diag / f"decisiones_{mes}.csv", clientes, prob,
                     {f"enviar_{k}": v for k, v in decisiones.items()})
        oficial_tmp = trabajo / oficial.name
        escribir_csv(oficial_tmp, clientes, prob, {"enviar": decisiones[a.principal]})
        tiempos["estrategias_s"] = round(time.perf_counter() - t, 1)
        log.info("[estrategias] %s", rep["comparacion_estrategias"])

        # 6. Publicación todo-o-nada: diagnóstico, salida oficial e historia
        con.close()
        con = None
        shutil.rmtree(duck_tmp, ignore_errors=True)
        rep["salida_oficial"] = oficial.relative_to(env.raiz).as_posix()
        rep["historia_agregada"] = f"historia/foto_mes={mes}.parquet"
        rep["lecturas"] = env.lecturas
        rep["estado"] = "completado"
        estados(rep, pol)
        rep["fin"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        tiempos["total_s"] = round(time.perf_counter() - t0, 1)
        rep["tiempos"], rep["memoria"] = tiempos, memoria(proc)
        (diag / "reporte.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        publicar([(diag, env.raiz / "diagnosticos" / str(mes)), (oficial_tmp, oficial),
                  (actual_pq, env.raiz / "historia" / f"foto_mes={mes}.parquet")])
        codigo = 0
        shutil.rmtree(trabajo, ignore_errors=True)  # ya vacío; no debe poder marcar como fallido algo publicado
    except Exception as e:  # noqa: BLE001
        rep["estado"] = "fallido"
        rep["error"] = repr(e)
        if isinstance(e, I.Rechazo):
            rep["rechazo"] = e.incidentes
            log.error("Entrada rechazada por la política de incidentes: %s", e)
        else:
            log.exception("La ejecución falló; no se publicó nada")
    finally:
        if con is not None:
            con.close()
        rep["lecturas"] = env.lecturas
        estados(rep, pol)
        rep.setdefault("fin", time.strftime("%Y-%m-%dT%H:%M:%S"))
        tiempos.setdefault("total_s", round(time.perf_counter() - t0, 1))
        rep["tiempos"] = tiempos
        rep.setdefault("memoria", memoria(proc))
        if rep["estado"] == "fallido" and trabajo.exists():
            # Se conserva el diagnóstico del intento, fuera de las rutas publicadas
            shutil.rmtree(duck_tmp, ignore_errors=True)
            fallido = env.raiz / "diagnosticos" / f"{mes}.fallido-{ejecucion}"
            try:
                os.rename(trabajo, fallido)
                (fallido / "reporte.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str),
                                                      encoding="utf-8")
                rep["diagnostico_fallido"] = fallido.relative_to(env.raiz).as_posix()
            except OSError as e2:
                rep["diagnostico_fallido"] = f"quedó en {trabajo.relative_to(env.raiz).as_posix()} ({e2!r})"
        registrar(env, rep)
        cerrar(reg, mes, est, rep["estado"], rep.get("error", ""))
        log.info("Estado operativo %s | calidad %s | incidentes %s | tiempos %s | memoria %s", rep["estado"],
                 rep["estado_calidad"], [(i["regla"], i["accion"], len(i["variables"])) for i in pol.incidentes],
                 tiempos, rep["memoria"])
    return codigo


if __name__ == "__main__":
    sys.exit(main())
