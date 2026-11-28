"""Ejecución mensual con dos estrategias: input/<yyyymm>.csv -> output/churn_<yyyymm>.csv + reporte acumulado.

Estrategias (catálogo copiado en <ejecución>/modelos/estrategias.json; ver catalogo.py):
  recomendacion_provisional  binario_e01_300r        score = P(BAJA+1 ∪ BAJA+2) (objetivo binario)
  alternativa                multiclase_p1_e01_300r  score = P(BAJA+2) (multiclase, BAJA+1 con peso 1)
Cada una promedia las probabilidades de sus semillas (5 en tc01, 20 en ce02) y corta en su propia fracción de clientes.
La salida oficial lleva la recomendación (binario). Las predicciones y decisiones de las dos quedan en
diagnosticos/<mes>/ y se comparan en el reporte. Al publicar, las métricas con target del mes son pendientes; se
completan después en el reporte acumulado (retrospectiva.py) cuando llegan los dos meses siguientes, con la etiqueta
reconstruida por presencia. Son monitoreo: no cambian modelos, cortes ni salidas.

Etapas: recepción -> validación (ejecutar_mes.validar_entrada) -> perfil de columnas -> features del mes (features.py,
la misma definición del entrenamiento) -> verificación de features (nombres, orden, tipos, lags) -> inferencia de las
semillas de las dos estrategias -> estrategias -> escritura -> publicación todo o nada (diagnóstico, historia y, al final, la salida
oficial) -> estado completado -> reporte acumulado regenerado.

Reintentos y consistencia:
  - un mes completado se rechaza (código 4) sin tocar nada; un mes con otro intento vivo, también;
  - un mes se rechaza (código 4) si algún mes anterior ya procesado no está completado (por ejemplo, murió después
    de publicar): primero hay que reintentar ese mes, que se reconcilia;
  - si un intento anterior murió después de publicar, el mes se reconcilia: si diagnóstico, historia y salida
    existen y sus sha256 coinciden con reporte.json, se marca completado sin recalcular; si hay piezas sueltas,
    se mueven a cuarentena y el mes se recalcula;
  - registro/reporte_acumulado.csv no se edita: se regenera desde los meses completados (una fila por mes), así que
    no puede duplicar meses ni quedar desalineado con salida e historia. Los intentos fallidos o rechazados quedan en
    registro/ejecuciones.jsonl.

Uso:
  python -m pipeline_competencia02.mensual --ejecucion <carpeta> --mes 202001 [--copiar-desde <csv>]
  python -m pipeline_competencia02.mensual --ejecucion <carpeta> --solo-reporte
Con --copiar-desde, el reloj arranca antes de copiar el archivo a input/: mide desde la entrada hasta la salida y
el reporte. Sin esa opción, arranca al iniciar el proceso, con el archivo ya en input/.
Códigos de salida: 0 completado (o recuperado), 2 fallido, 4 rechazado.
"""
from __future__ import annotations

import argparse
import csv
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

from . import incidentes as I
from . import reporte_html as H
from . import retrospectiva as R
from . import tratamiento as T
from .ejecutar_mes import (EXIT_DUPLICADO, EXIT_FALLA, HILOS, VECTORES_POR_BLOQUE, Entorno, adquirir, anterior,
                           cerrar, distribucion, escribir_atomico, escribir_csv, memoria, perfil_mes, publicar,
                           sha256, validar_entrada)
from .estrategias import FraccionClientes
from .features import KEYS, crear_prev, nombres, q, sql_mes

log = logging.getLogger("pipeline_competencia02.mensual")
ULTIMO_HTML: dict = {"segundos": None, "error": None}  # medición del último reporte HTML generado
ROL_OFICIAL = "recomendacion_provisional"
ROL_ALTERNATIVA = "alternativa"


def siguiente(m: int) -> int:
    a, mm = divmod(m, 100)
    return a * 100 + mm + 1 if mm < 12 else (a + 1) * 100 + 1


def falla_dura(punto: str):
    """Sólo para pruebas: simula que el proceso muere (sin limpiar ni cerrar el estado)."""
    if os.environ.get("PIPELINE_C02_FALLA") == punto:
        logging.shutdown()
        os._exit(3)


# --------------------------------------------------------------------------
# Estrategias del catálogo
def objetivo_del_modelo(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        for _ in range(40):
            linea = f.readline()
            if linea.startswith("objective="):
                return linea.split("=", 1)[1].split()[0]
    raise ValueError(f"{path}: sin línea objective")


def cargar_estrategias(env: Entorno) -> tuple[dict, list[dict]]:
    cat = json.loads(Path(env.leer(env.raiz / "modelos" / "estrategias.json")).read_text(encoding="utf-8"))
    if sha256(env.raiz / "modelos" / "estrategias.json") != env.cfg["catalogo"]["sha256"]:
        raise RuntimeError("el catálogo de la ejecución cambió desde que se preparó")
    pred = [c for c, _ in json.loads(Path(env.leer(env.raiz / "modelos" / "predictores.json"))
                                     .read_text(encoding="utf-8"))["predictores"]]
    roles = sorted(e["rol"] for e in cat["estrategias"])
    if roles != sorted([ROL_OFICIAL, ROL_ALTERNATIVA]):
        raise ValueError(f"el catálogo debe tener una recomendación y una alternativa; tiene {roles}")
    out = []
    for e in cat["estrategias"]:
        boosters = []
        for m in e["modelos"]:
            p = env.raiz / "modelos" / m["archivo"]
            if sha256(p) != m["sha256"]:
                raise RuntimeError(f"{m['archivo']}: sha256 distinto del catálogo")
            b = lgb.Booster(model_file=env.leer(p))
            obj = objetivo_del_modelo(str(p))
            if b.feature_name() != pred or b.num_trees() != m["arboles"] or obj != e["objetivo"]:
                raise ValueError(f"{m['archivo']}: nombres, árboles u objetivo distintos del catálogo")
            boosters.append(b)
        out.append({**e, "boosters": boosters,
                    "estrategia": FraccionClientes(e["corte"]["fraccion"], nombre=e["id"],
                                                   nota=f"{e['candidato']}; corte de {e['corte']['fuente']}")})
    out.sort(key=lambda e: e["rol"] != ROL_OFICIAL)  # la recomendación primero
    return cat, out


# --------------------------------------------------------------------------
# Detección de columnas anómalas (E06): sólo alerta, el dato recibido se conserva
def detectar_cero_anomalo(con, hist: list[str], mes: int, categorias: dict, pol: I.Politica) -> dict:
    """Regla cero_anomalo (tratamiento.detectar) sobre las columnas con todos los observados en 0.

    Sólo usa el mes recibido y la historia de la ejecución (t-1 a t-3). Registra un incidente de tipo calidad_datos
    con acción advertir: no cambia features, score ni selección. Sin candidatas no lee la historia.
    """
    u = pol.umbrales.get("cero_anomalo", {})
    params = {**T.PARAMS, **{k: u[k] for k in ("esperados_min", "meses_referencia") if k in u}}
    candidatas = list(categorias.get("observados_en_cero", []))
    out = {"regla": "cero_anomalo", "parametros": params, "candidatas": len(candidatas), "detectadas": [],
           "no_detectadas": [], "tratamiento": "ninguno: se conserva el dato recibido (política advertir; E06)"}
    if not candidatas:
        return out
    por_mes = {int(Path(h).stem.split("=")[1]): h for h in hist}
    perfil_hist = {m: T.perfil(con, f"read_parquet('{por_mes[m]}')", candidatas)
                   for m in (T.mes_menos(mes, k) for k in range(1, params["meses_referencia"] + 1)) if m in por_mes}
    det = T.detectar(T.perfil(con, "actual", candidatas), perfil_hist, mes, params)
    out.update(det)
    if det["detectadas"]:
        pol.registrar("cero_anomalo", [d["columna"] for d in det["detectadas"]],
                      {d["columna"]: {"esperados_no_cero": d["esperados_no_cero"], "mes_referencia": d["mes_referencia"]}
                       for d in det["detectadas"]})
    return out


# --------------------------------------------------------------------------
# Verificación de features contra lo que esperan los modelos
def verificar_features(con, env: Entorno, feat: Path, pred_calc: list[str], mes: int, pol: I.Politica) -> dict:
    esperado = json.loads(Path(env.leer(env.raiz / "modelos" / "predictores.json")).read_text(encoding="utf-8"))
    nombres_esp = [c for c, _ in esperado["predictores"]]
    tipos_esp = dict(esperado["predictores"])
    tipos = {c: t for c, t, *_ in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{env.leer(feat)}')").fetchall()}
    columnas = [c for c in tipos if c not in KEYS]
    distintos = {c: (tipos.get(c), tipos_esp[c]) for c in nombres_esp if tipos.get(c) != tipos_esp[c]}
    # lags: los modelos usan la k-ésima observación previa; se cuenta cuándo difiere del mes calendario t-k
    m1, m2 = anterior(mes), anterior(anterior(mes))
    n, l1, l2, dif1, dif2, dif = con.execute(
        f"SELECT count(*), count(m1), count(m2), count(*) FILTER (WHERE m1 IS NOT NULL AND m1 <> {m1}), "
        f"count(*) FILTER (WHERE m2 IS NOT NULL AND m2 <> {m2}), "
        f"count(*) FILTER (WHERE (m1 IS NOT NULL AND m1 <> {m1}) OR (m2 IS NOT NULL AND m2 <> {m2})) "
        f"FROM prev WHERE foto_mes = {mes}").fetchone()
    checks = {"nombres_y_orden_iguales_al_modelo": pred_calc == nombres_esp and columnas == nombres_esp,
              "tipos_iguales_al_entrenamiento": not distintos,
              "lags_definidos_por_fila_como_el_entrenamiento": True}
    rep = {"checks": checks, "tipos_distintos": distintos, "definicion": esperado["definicion"],
           "lags": {"clientes": int(n), "con_lag1": int(l1), "con_lag2": int(l2),
                    "lag1_no_es_mes_calendario_anterior": int(dif1), "lag2_no_es_dos_meses_calendario_antes": int(dif2),
                    "clientes_con_algun_lag_distinto_del_calendario": int(dif),
                    "nota": "el lag por fila coincide con el calendario cuando el cliente estuvo en t-1 y t-2"}}
    if dif:
        pol.registrar("lag_fila_distinto_calendario", detalle={"clientes": int(dif), "lag1": int(dif1), "lag2": int(dif2)})
    if not all(checks.values()):
        raise ValueError(f"las features no coinciden con las del entrenamiento: {checks} {distintos}")
    return rep


# --------------------------------------------------------------------------
def inferir(con, env: Entorno, feat: Path, pred: list[str], estrategias: list[dict], tiempos: dict) -> tuple:
    """Lee las features por bloques (como ejecutar_mes.inferir) y predice con todas las semillas de cada estrategia.

    El ensamble se calcula como en E01: np.mean de las semillas, en el orden del catálogo.
    """
    tipos = {c: t for c, t, *_ in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{env.leer(feat)}')").fetchall()}
    expr = ", ".join(f"CAST({q(c)} AS DOUBLE) AS {q(c)}" if tipos[c] == "BIGINT" else q(c) for c in pred)
    con.execute("SET threads = 1")
    rel = con.execute(f"SELECT numero_de_cliente, {expr} FROM read_parquet('{env.leer(feat)}')")
    clientes, por_semilla = [], {e["id"]: [[] for _ in e["boosters"]] for e in estrategias}
    t_pred = {e["id"]: 0.0 for e in estrategias}
    t0 = time.perf_counter()
    while True:
        df = rel.fetch_df_chunk(VECTORES_POR_BLOQUE)
        if df.empty:
            break
        X = df[pred].to_numpy(dtype=np.float64, na_value=np.nan)
        clientes.append(df["numero_de_cliente"].to_numpy(np.int64))
        for e in estrategias:
            t = time.perf_counter()
            for i, b in enumerate(e["boosters"]):
                p = b.predict(X, num_threads=HILOS)
                por_semilla[e["id"]][i].append(p if e["columna_score"] is None else p[:, e["columna_score"]])
            t_pred[e["id"]] += time.perf_counter() - t
        del df, X
    del rel
    con.execute(f"SET threads = {HILOS}")
    total = time.perf_counter() - t0
    for e in estrategias:
        tiempos[f"inferencia_{e['id']}_s"] = round(t_pred[e["id"]], 1)
    tiempos["lectura_y_conversion_s"] = round(total - sum(t_pred.values()), 1)
    semillas = {k: [np.concatenate(v) for v in listas] for k, listas in por_semilla.items()}
    ensamble = {k: np.mean(v, axis=0) for k, v in semillas.items()}
    return np.concatenate(clientes), semillas, ensamble


def coincidencia(a: np.ndarray, b: np.ndarray, sa: np.ndarray, sb: np.ndarray) -> dict:
    inter, union = int((a & b).sum()), int((a | b).sum())
    ra, rb = np.argsort(np.argsort(-sa)), np.argsort(np.argsort(-sb))
    return {"interseccion": inter, "solo_recomendacion": int((a & ~b).sum()), "solo_alternativa": int((b & ~a).sum()),
            "jaccard": round(inter / union, 6) if union else None,
            "correlacion_de_rangos": round(float(np.corrcoef(ra, rb)[0, 1]), 6)}


# --------------------------------------------------------------------------
# Reconciliación y reporte acumulado
def rutas_mes(env: Entorno, mes: int) -> dict:
    return {"diagnostico": env.raiz / "diagnosticos" / str(mes), "historia": env.raiz / "historia" / f"foto_mes={mes}.parquet",
            "salida": env.raiz / "output" / f"churn_{mes}.csv"}


def integridad(env: Entorno, mes: int, rep: dict) -> bool:
    r = rutas_mes(env, mes)
    esp = rep.get("integridad", {})
    try:
        return (sha256(r["salida"]) == esp.get("salida") and sha256(r["historia"]) == esp.get("historia")
                and sha256(r["diagnostico"] / f"decisiones_{mes}.csv") == esp.get("decisiones"))
    except FileNotFoundError:
        return False


def reconciliar(env: Entorno, mes: int, ejecucion: str, pol: I.Politica) -> str:
    """'nada' (no hay nada publicado), 'recuperado' (publicado e íntegro) o 'cuarentena' (piezas sueltas movidas)."""
    r = rutas_mes(env, mes)
    presentes = {k: p for k, p in r.items() if p.exists()}
    if not presentes:
        return "nada"
    rep_path = r["diagnostico"] / "reporte.json"
    if len(presentes) == 3 and rep_path.exists():
        rep = json.loads(rep_path.read_text(encoding="utf-8"))
        if rep.get("estado") == "completado" and integridad(env, mes, rep):
            pol.registrar("mes_recuperado", detalle={"ejecucion_que_publico": rep.get("ejecucion")})
            return "recuperado"
    cuarentena = env.raiz / "diagnosticos" / f"{mes}.cuarentena-{ejecucion}"
    cuarentena.mkdir(parents=True)
    for k, p in presentes.items():
        os.rename(p, cuarentena / p.name)
    pol.registrar("publicacion_parcial_en_cuarentena", sorted(presentes),
                  {"cuarentena": cuarentena.relative_to(env.raiz).as_posix()})
    return "cuarentena"


def fila_reporte(env: Entorno, mes: int, est: dict, retro: dict | None = None) -> dict:
    rep = json.loads((rutas_mes(env, mes)["diagnostico"] / "reporte.json").read_text(encoding="utf-8"))
    e = {x["rol"]: x for x in rep["estrategias"]}
    rec, alt = e[ROL_OFICIAL], e[ROL_ALTERNATIVA]
    cat = rep.get("categorias_columnas", {})
    t = rep.get("tiempos", {})
    fila = {"mes": mes, "ejecucion": rep["ejecucion"], "estado_operativo": est.get("estado"),
            "recuperado": est.get("recuperado", False), "estado_calidad": rep.get("estado_calidad"),
            "integridad_ok": integridad(env, mes, rep),
            "clientes": rep["validacion"]["clientes"], "clientes_sin_historia": rep["features"]["clientes_sin_historia"],
            "clientes_lag_fila_distinto_calendario":
                rep["verificacion_features"]["lags"]["clientes_con_algun_lag_distinto_del_calendario"],
            "reglas_activadas": ";".join(f"{i['regla']}:{i['accion']}:{len(i['variables']) or 1}" for i in rep["incidentes"]),
            "columnas_100_nulas": len(cat.get("nula_100", [])), "columnas_observados_en_cero": len(cat.get("observados_en_cero", [])),
            "columnas_constantes_no_nulas": len(cat.get("constante_no_nula", [])),
            "columnas_cero_anomalo": (len(rep["deteccion_cero_anomalo"]["detectadas"])
                                      if "deteccion_cero_anomalo" in rep else "no_evaluado"),
            "celdas_faltantes": rep["faltantes"]["celdas"]}
    for pref, x in (("rec", rec), ("alt", alt)):
        d = x["distribucion"]
        fila.update({f"{pref}_id": x["id"], f"{pref}_score": x["score_corto"], f"{pref}_p50": d["cuantiles"]["0.5"],
                     f"{pref}_p99": d["cuantiles"]["0.99"], f"{pref}_media": d["media"],
                     f"{pref}_saturados": d["exactamente_0"] + d["exactamente_1"], f"{pref}_fraccion": x["fraccion"],
                     f"{pref}_envios": x["envios"], f"{pref}_prob_minima_enviada": x["probabilidad_minima_enviada"],
                     f"{pref}_modelos_sha12": "|".join(m[:12] for m in x["modelos_sha256"])})
    c = rep["coincidencia"]
    fila.update({"coinc_interseccion": c["interseccion"], "coinc_solo_recomendacion": c["solo_recomendacion"],
                 "coinc_solo_alternativa": c["solo_alternativa"], "coinc_jaccard": c["jaccard"],
                 "coinc_correlacion_rangos": c["correlacion_de_rangos"]})
    # Métricas retrospectivas (retrospectiva.py): sólo cuando ya llegaron los meses que etiquetan este mes
    disp = (retro or {}).get("disponibilidad", {})
    estado_target = "error" if (retro or {}).get("error") else disp.get("estado", rep["metricas_con_target"]["estado"])
    fila.update({"metricas_con_target": estado_target,
                 "etiqueta_falta_lista_de": "|".join(disp.get("falta", [])) if disp else
                 rep["metricas_con_target"]["requiere_listas_de"]})
    # Clases sólo si son definitivas (t+1 y t+2 recibidos); con t+1 solo, los ausentes van aparte como provisionales
    cl = (retro or {}).get("clases", {})
    prov = (retro or {}).get("provisional", {})
    fila.update({"target_regla_version": (retro or {}).get("version", ""),
                 "target_baja1": cl.get("BAJA+1", "pendiente"), "target_baja2": cl.get("BAJA+2", "pendiente"),
                 "target_continua": cl.get("CONTINUA", "pendiente"),
                 "target_retornos_t1_ausente_t2_presente": cl.get("ausentes_en_t1_que_vuelven_en_t2", "pendiente"),
                 "provisional_ausentes_t1": prov.get("ausentes_en_t1", "")})
    por_rol = {x["rol"]: x for x in (retro or {}).get("estrategias", [])}
    for pref, rol in (("rec", ROL_OFICIAL), ("alt", ROL_ALTERNATIVA)):
        r = por_rol.get(rol, {})
        for k in ("baja1_enviados", "baja2_enviados", "ganancia", "auc_baja2", "ganancia_maxima_ex_post",
                  "envios_ganancia_maxima_ex_post"):
            fila[f"{pref}_{k}"] = r.get(k, "pendiente")
        fila[f"{pref}_provisional_ausentes_t1_enviados"] = r.get("provisional_ausentes_en_t1_enviados", "")
    fila["catalogo_sha12"] = rep["catalogo"]["sha256"][:12]
    for k, v in t.items():
        fila[f"t_{k}"] = v
    fila["t_total_desde_entrada_s"] = est.get("total_desde_entrada_s")
    fila["pico_working_set_mb"] = rep["memoria"]["pico_working_set_mb"]
    return fila


def regenerar_reporte(env: Entorno) -> Path:
    """Una fila por mes completado, ordenadas; se reescribe entero (tmp + replace).

    Antes actualiza la retrospectiva (retrospectiva.actualizar) de los meses completados. Si falla, el reporte se
    regenera igual y esas filas quedan con metricas_con_target = error (la salida ya publicada no depende de esto).
    """
    reg = env.raiz / "registro"
    completados = {}
    for p in sorted((reg / "meses").glob("*.json")):
        est = json.loads(p.read_text(encoding="utf-8"))
        if est.get("estado") == "completado":
            completados[int(est["mes"])] = est
    retro_error = None
    try:
        R.actualizar(env.raiz, list(completados))
    except Exception as e:  # noqa: BLE001
        retro_error = repr(e)
        log.warning("No se pudo actualizar la retrospectiva: %s", retro_error)
    filas = []
    for mes, est in sorted(completados.items()):
        retro = {"error": retro_error} if retro_error else R.cargar(env.raiz, mes)
        filas.append(fila_reporte(env, mes, est, retro))
    destino = reg / "reporte_acumulado.csv"
    tmp = destino.with_name(destino.name + f".tmp-{os.getpid()}")
    campos = []
    for f in filas:
        campos += [k for k in f if k not in campos]
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos or ["mes"], lineterminator="\n")
        w.writeheader()
        w.writerows(filas)
    os.replace(tmp, destino)
    # Reporte HTML de seguimiento: derivado de lo publicado, como el CSV. Si falla, la salida y el CSV no cambian.
    t = time.perf_counter()
    try:
        H.generar(env.raiz)
        ULTIMO_HTML["segundos"], ULTIMO_HTML["error"] = round(time.perf_counter() - t, 2), None
    except Exception as e:  # noqa: BLE001
        ULTIMO_HTML["segundos"], ULTIMO_HTML["error"] = round(time.perf_counter() - t, 2), repr(e)
        log.warning("No se pudo generar el reporte HTML: %r", e)
    return destino


def previos_sin_completar(env: Entorno, mes: int) -> list[int]:
    """Meses anteriores a `mes` que están en historia/ o en el registro sin ser historia inicial ni completados.

    Caso típico: un intento murió después de publicar (la historia del mes ya está) y antes de marcarlo completado.
    El mes siguiente no se procesa hasta reintentar (y así reconciliar) ese mes.
    """
    inicial = {int(m) for m in env.cfg["historia"]["meses"]}
    candidatos = {int(p.stem.split("=")[1]) for p in (env.raiz / "historia").glob("foto_mes=*.parquet")}
    candidatos |= {int(p.stem) for p in (env.raiz / "registro" / "meses").glob("*.json")}
    out = []
    for m in sorted(c for c in candidatos if c < mes and c not in inicial):
        est_path = env.raiz / "registro" / "meses" / f"{m}.json"
        est = json.loads(est_path.read_text(encoding="utf-8")) if est_path.exists() else {}
        if est.get("estado") != "completado":
            out.append(m)
    return out


def anotar_intento(env: Entorno, rep: dict):
    with open(env.raiz / "registro" / "ejecuciones.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({k: v for k, v in rep.items() if k not in ("lecturas",)}, ensure_ascii=False, default=str) + "\n")


# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pipeline mensual con dos estrategias (recomendación y alternativa).")
    ap.add_argument("--ejecucion", type=Path, required=True, help="carpeta creada con preparar_ejecucion")
    ap.add_argument("--mes", type=int)
    ap.add_argument("--copiar-desde", type=Path, help="CSV a copiar a input/<mes>.csv; el reloj arranca antes de copiar")
    ap.add_argument("--solo-reporte", action="store_true", help="sólo regenera registro/reporte_acumulado.csv")
    a = ap.parse_args(argv)
    t0 = time.perf_counter()
    env = Entorno(a.ejecucion)
    if a.solo_reporte:
        print(regenerar_reporte(env))
        return 0
    if a.mes is None:
        ap.error("--mes es obligatorio")
    mes = a.mes
    proc = psutil.Process()
    ejecucion = f"{mes}_{time.strftime('%Y%m%dT%H%M%S')}_{os.getpid()}"
    reg = env.raiz / "registro"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S",
                        handlers=[logging.FileHandler(reg / f"log_{ejecucion}.txt", encoding="utf-8"),
                                  logging.StreamHandler(sys.stdout)])
    pol = I.Politica()
    tiempos: dict = {}
    entrada = env.raiz / "input" / f"{mes}.csv"
    rep = {"ejecucion": ejecucion, "mes": mes, "inicio": time.strftime("%Y-%m-%dT%H:%M:%S"), "pid": os.getpid(),
           "entorno": env.cfg["nombre"], "entrada": {"archivo": entrada.relative_to(env.raiz).as_posix()},
           "politica_incidentes": pol.resumen(), "reloj": "desde antes de copiar la entrada" if a.copiar_desde else
           "desde el inicio del proceso (entrada ya presente en input/)"}

    # 0. Recepción: input/<mes>.csv
    t = time.perf_counter()
    if a.copiar_desde:
        if entrada.exists() and sha256(entrada) != sha256(a.copiar_desde):
            rep.update({"estado": "rechazada", "motivo": f"{entrada.name} ya existe con otro contenido"})
            anotar_intento(env, rep)
            log.error(rep["motivo"])
            return EXIT_DUPLICADO
        if not entrada.exists():
            tmp = entrada.with_name(entrada.name + f".tmp-{os.getpid()}")
            shutil.copyfile(a.copiar_desde, tmp)
            os.replace(tmp, entrada)
        rep["entrada"]["copiado_desde"] = str(a.copiar_desde)
    if not entrada.exists():
        rep.update({"estado": "rechazada", "motivo": f"no existe {rep['entrada']['archivo']}"})
        anotar_intento(env, rep)
        log.error(rep["motivo"])
        return EXIT_FALLA
    st = entrada.stat()
    rep["entrada"].update({"bytes": st.st_size, "sha256": sha256(entrada),
                           "creado_o_copiado": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_ctime)),
                           "modificado": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime))})
    tiempos["recepcion_s"] = round(time.perf_counter() - t, 1)

    if str(mes) in env.cfg["historia"]["meses"]:
        rep.update({"estado": "rechazada", "motivo": f"{mes} es parte de la historia inicial de la ejecución"})
        anotar_intento(env, rep)
        log.error(rep["motivo"])
        return EXIT_DUPLICADO
    pendientes = previos_sin_completar(env, mes)
    if pendientes:
        rep.update({"estado": "rechazada", "motivo": f"meses previos procesados sin estado completado: {pendientes}; "
                                                     f"reintentá esos meses primero"})
        anotar_intento(env, rep)
        log.error(rep["motivo"])
        return EXIT_DUPLICADO
    ok, motivo, est = adquirir(reg, mes, ejecucion, proc)
    if not ok:
        rep.update({"estado": "rechazada", "motivo": motivo})
        anotar_intento(env, rep)
        log.error("Mes %s rechazado: %s.", mes, motivo)
        return EXIT_DUPLICADO

    trabajo = env.raiz / "tmp" / ejecucion
    diag = trabajo / "diagnostico"
    con = None
    codigo = EXIT_FALLA
    try:
        situacion = reconciliar(env, mes, ejecucion, pol)
        rep["reconciliacion"] = situacion
        if situacion == "recuperado":
            rep.update({"estado": "completado", "incidentes": pol.incidentes})
            est["recuperado"] = True
            cerrar(reg, mes, est, "completado", "recuperado: publicado e íntegro por un intento anterior")
            regenerar_reporte(env)
            codigo = 0
            log.info("Mes %s recuperado sin recalcular.", mes)
            return codigo
        diag.mkdir(parents=True)
        log.info("Ejecución %s | %s | entrada %s", ejecucion, env.cfg["nombre"], rep["entrada"])

        # 1. Validación y perfil del mes
        t = time.perf_counter()
        con = duckdb.connect()
        con.execute(f"SET threads = {HILOS}")
        con.execute("SET memory_limit = '4GB'")
        con.execute("SET preserve_insertion_order = true")
        con.execute(f"SET temp_directory = '{(trabajo / 'duckdb').as_posix()}'")
        hist, esquema, actual_pq = validar_entrada(con, env, entrada, mes, trabajo, rep, pol)
        tiempos["validacion_s"] = round(time.perf_counter() - t, 1)
        t = time.perf_counter()
        cols = [c for c in esquema if c not in KEYS]
        n = rep["validacion"]["filas"]
        rep["faltantes"], rep["categorias_columnas"] = perfil_mes(con, "actual", cols, hist[-1], n, pol)
        pol.cortar_si_rechazo()
        tiempos["perfil_s"] = round(time.perf_counter() - t, 1)
        t = time.perf_counter()
        rep["deteccion_cero_anomalo"] = detectar_cero_anomalo(con, hist, mes, rep["categorias_columnas"], pol)
        tiempos["deteccion_cero_anomalo_s"] = round(time.perf_counter() - t, 2)
        log.info("[validación] %s", rep["validacion"])

        # 2. Features del mes, con la definición del entrenamiento
        t = time.perf_counter()
        pred = nombres(cols)
        con.execute(f"CREATE VIEW src AS SELECT * FROM read_parquet({hist + [env.leer(actual_pq)]})")
        crear_prev(con, "src")
        futuro, n_k, con_l1, con_l2 = con.execute(
            f"SELECT (SELECT count(*) FROM prev WHERE m1 >= foto_mes OR m2 >= m1), count(*), count(m1), count(m2) "
            f"FROM prev WHERE foto_mes = {mes}").fetchone()
        if futuro:
            raise RuntimeError("hay observaciones previas con mes >= al actual")
        feat = diag / f"features_{mes}.parquet"
        con.execute(f"COPY ({sql_mes('src', cols, mes)}) TO '{feat.as_posix()}' (FORMAT parquet, COMPRESSION zstd)")
        n_feat = con.execute(f"SELECT count(*) FROM read_parquet('{env.leer(feat)}')").fetchone()[0]
        if n_feat != n or n_k != n:
            raise RuntimeError(f"features con {n_feat} filas para {n} clientes")
        rep["features"] = {"archivo": f"diagnosticos/{mes}/{feat.name}", "filas": int(n_feat), "predictores": len(pred),
                           "con_lag1": int(con_l1), "con_lag2": int(con_l2), "clientes_sin_historia": int(n_k - con_l1)}
        tiempos["features_s"] = round(time.perf_counter() - t, 1)

        t = time.perf_counter()
        rep["verificacion_features"] = verificar_features(con, env, feat, pred, mes, pol)
        tiempos["verificacion_features_s"] = round(time.perf_counter() - t, 1)
        log.info("[features] %s | lags %s", rep["features"], rep["verificacion_features"]["lags"])

        # 3. Modelos e inferencia
        t = time.perf_counter()
        cat, estrategias = cargar_estrategias(env)
        tiempos["carga_modelos_s"] = round(time.perf_counter() - t, 1)
        rep["catalogo"] = {"sha256": env.cfg["catalogo"]["sha256"], "version": cat["version"], "estado": cat["estado"]}
        clientes, semillas, ensamble = inferir(con, env, feat, pred, estrategias, tiempos)
        if len(clientes) != n or len(np.unique(clientes)) != n:
            raise RuntimeError("clientes faltantes o repetidos en las predicciones")
        for k, v in list(semillas.items()) + list(ensamble.items()):
            for arr in (v if isinstance(v, list) else [v]):
                if not (len(arr) == n and np.isfinite(arr).all() and ((arr >= 0) & (arr <= 1)).all()):
                    raise RuntimeError(f"{k}: probabilidades no finitas, fuera de [0,1] o incompletas")
        if rep["features"]["clientes_sin_historia"]:
            pol.registrar("clientes_sin_historia", detalle=rep["features"]["clientes_sin_historia"])

        # 4. Estrategias
        t = time.perf_counter()
        decisiones, rep["estrategias"] = {}, []
        for e in estrategias:
            prob = ensamble[e["id"]]
            d = e["estrategia"].seleccionar(clientes, prob)
            decisiones[e["id"]] = d
            dist = distribucion(prob)
            if dist["exactamente_0"] or dist["exactamente_1"]:
                pol.registrar("scores_saturados", [e["id"]], {"iguales_a_0": dist["exactamente_0"],
                                                               "iguales_a_1": dist["exactamente_1"]})
            pol.registrar("estrategia_provisional", [e["id"]], e["estrategia"].nota)
            umbral = float(prob[d].min())
            rep["estrategias"].append({
                "id": e["id"], "rol": e["rol"], "objetivo": e["objetivo"], "score": e["score"],
                "score_corto": "P(BAJA+1∪BAJA+2)" if e["columna_score"] is None else "P(BAJA+2)",
                "candidato": e["candidato"], "semillas": [m["semilla"] for m in e["modelos"]],
                "modelos_sha256": [m["sha256"] for m in e["modelos"]], "corte": e["corte"],
                "fraccion": e["corte"]["fraccion"], "envios": int(d.sum()), "proporcion": round(float(d.sum()) / n, 6),
                "probabilidad_minima_enviada": umbral, "empates_en_el_corte": int((prob == umbral).sum()),
                "distribucion": dist})
        rec, alt = estrategias[0], estrategias[1]
        rep["coincidencia"] = coincidencia(decisiones[rec["id"]], decisiones[alt["id"]], ensamble[rec["id"]],
                                           ensamble[alt["id"]])
        rep["salida_oficial"] = {"archivo": f"output/churn_{mes}.csv", "estrategia": rec["id"],
                                 "columnas": "numero_de_cliente, probabilidad (= " + rec["score"] + "), enviar"}
        rep["metricas_con_target"] = {
            "estado": "pendiente", "requiere_listas_de": f"{siguiente(mes)} y {siguiente(siguiente(mes))}",
            "metricas": ["ganancia por estrategia", "AUC de BAJA+2", "aciertos en el corte"],
            "motivo": "la etiqueta de este mes depende de la presencia de cada cliente en los dos meses siguientes; "
                      "se calcula cuando lleguen y si su uso es válido (CONSIGNA R1, PLAN_PRUEBAS § 1)"}
        pol.cortar_si_rechazo()
        tiempos["estrategias_s"] = round(time.perf_counter() - t, 1)

        # 5. Escritura en el área de trabajo
        t = time.perf_counter()
        orden = np.argsort(clientes, kind="stable")
        tabla = {"numero_de_cliente": clientes[orden], "foto_mes": np.full(n, mes, np.int64)}
        for e in estrategias:
            for m, arr in zip(e["modelos"], semillas[e["id"]]):
                tabla[f"{e['id']}__semilla_{m['semilla']}"] = arr[orden]
            tabla[f"{e['id']}__ensamble"] = ensamble[e["id"]][orden]
        pdf = pd.DataFrame(tabla)
        con.register("pdf", pdf)
        con.execute(f"COPY (SELECT * FROM pdf) TO '{(diag / f'predicciones_{mes}.parquet').as_posix()}' "
                    f"(FORMAT parquet, COMPRESSION zstd)")
        con.unregister("pdf")
        del pdf, tabla
        dec = pd.DataFrame({"numero_de_cliente": clientes[orden],
                            **{c: v for e in estrategias for c, v in
                               ((f"probabilidad_{e['id']}", ensamble[e["id"]][orden]),
                                (f"enviar_{e['id']}", decisiones[e["id"]][orden].astype(np.int8)))}})
        dec.to_csv(diag / f"decisiones_{mes}.csv", index=False, lineterminator="\n")
        oficial_tmp = trabajo / f"churn_{mes}.csv"
        escribir_csv(oficial_tmp, clientes, ensamble[rec["id"]], {"enviar": decisiones[rec["id"]]})
        tiempos["escritura_s"] = round(time.perf_counter() - t, 1)
        con.close()
        con = None
        shutil.rmtree(trabajo / "duckdb", ignore_errors=True)

        # 6. Publicación todo o nada; la salida oficial va última
        rutas = rutas_mes(env, mes)
        rep["integridad"] = {"salida": sha256(oficial_tmp), "historia": sha256(actual_pq),
                             "decisiones": sha256(diag / f"decisiones_{mes}.csv")}
        rep["lecturas"] = env.lecturas
        rep["estado"] = "completado"
        rep["estado_operativo"], rep["estado_calidad"] = "completado", pol.estado_calidad()
        rep["incidentes"], rep["alertas"], rep["aviso"] = pol.incidentes, pol.textos(), I.AVISO
        tiempos["total_hasta_publicacion_s"] = round(time.perf_counter() - t0, 1)
        rep["tiempos"], rep["memoria"] = tiempos, memoria(proc)
        rep["fin"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        (diag / "reporte.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        t = time.perf_counter()
        publicar([(diag, rutas["diagnostico"]), (actual_pq, rutas["historia"]), (oficial_tmp, rutas["salida"])])
        shutil.rmtree(trabajo, ignore_errors=True)
        falla_dura("tras_publicacion")
        cerrar(reg, mes, est, "completado")
        regenerar_reporte(env)
        tiempos["publicacion_y_reporte_s"] = round(time.perf_counter() - t, 1)
        est["total_desde_entrada_s"] = round(time.perf_counter() - t0, 1)
        est["tiempos_finales"] = {"publicacion_y_reporte_s": tiempos["publicacion_y_reporte_s"],
                                  "reporte_html_s": ULTIMO_HTML["segundos"], "reporte_html_error": ULTIMO_HTML["error"]}
        escribir_atomico(reg / "meses" / f"{mes}.json", est)
        t = time.perf_counter()
        regenerar_reporte(env)  # incorpora el tiempo total al reporte acumulado (y al HTML)
        # esta segunda regeneración queda fuera de total_desde_entrada_s: se registra aparte
        est["tiempos_finales"]["regeneracion_final_s"] = round(time.perf_counter() - t, 2)
        est["tiempos_finales"]["reporte_html_final_s"] = ULTIMO_HTML["segundos"]
        escribir_atomico(reg / "meses" / f"{mes}.json", est)
        codigo = 0
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
        rep.setdefault("incidentes", pol.incidentes)
        rep["tiempos"] = tiempos
        rep.setdefault("memoria", memoria(proc))
        rep["total_desde_entrada_s"] = round(time.perf_counter() - t0, 1)
        if rep.get("estado") == "fallido":
            if trabajo.exists():
                shutil.rmtree(trabajo / "duckdb", ignore_errors=True)
                fallido = env.raiz / "diagnosticos" / f"{mes}.fallido-{ejecucion}"
                try:
                    os.rename(trabajo, fallido)
                    (fallido / "reporte.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str),
                                                          encoding="utf-8")
                    rep["diagnostico_fallido"] = fallido.relative_to(env.raiz).as_posix()
                except OSError as e2:
                    rep["diagnostico_fallido"] = f"quedó en tmp ({e2!r})"
            cerrar(reg, mes, est, "fallido", rep.get("error", ""))
        anotar_intento(env, rep)
        log.info("Estado %s | calidad %s | tiempos %s | total desde la entrada %s s", rep.get("estado"),
                 rep.get("estado_calidad"), tiempos, rep["total_desde_entrada_s"])
    return codigo


if __name__ == "__main__":
    sys.exit(main())
