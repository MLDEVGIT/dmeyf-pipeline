"""Ensayo secuencial del pipeline mensual con dos estrategias (mensual.py): un proceso por mes, y comprobación de cada uno.

Por mes, en orden:
  1. verifica el insumo (sha256 contra su .json) ANTES de arrancar el reloj;
  2. lanza `python -m pipeline_competencia02.mensual --mes M --copiar-desde <insumo>` y mide la PARED del proceso:
     desde antes de lanzarlo (arranque del intérprete, imports, copia a input/<M>.csv) hasta que termina (salida
     oficial publicada y reporte acumulado regenerado). También guarda el total interno del proceso;
  3. comprueba el mes (comprobar), sin leer etiquetas:
     - estado completado, integridad (sha256 de salida, historia y decisiones = reporte.json);
     - salida oficial: cabecera exacta, mismos clientes que input/<M>.csv, probabilidades en [0,1], igual a la
       recomendación de decisiones_<M>.csv (probabilidad y enviar);
     - decisiones de las DOS estrategias: envíos = techo(fracción · n) y selección = prefijo del orden
       (probabilidad descendente, numero_de_cliente ascendente);
     - historia: historia/foto_mes=<M> con los clientes de la entrada; la historia es la inicial más los meses
       completados, sin huecos; el mes sólo leyó su entrada, la historia anterior completa y los modelos;
     - reporte acumulado: una fila por mes completado, en orden, con integridad_ok y los envíos del reporte;
     - retrospectiva: cada mes completado tiene el estado de etiqueta que corresponde a los meses ya recibidos.
  Se detiene ante el primer mes que no pase.

Reintento provocado (--reintento-en M, un mes intermedio):
  a. M con PIPELINE_C02_FALLA=tras_publicacion: el proceso muere después de publicar y antes de marcar completado
     (código 3). Se comprueba: todo publicado, estado en_curso, candado huérfano, reporte sin la fila de M;
  b. el mes siguiente se rechaza (código 4) porque M no está completado, sin cambiar nada publicado ni el registro;
  c. reintento de M: reconcilia (hashes íntegros) y lo marca completado SIN recalcular (código 0);
  d. otro intento de M: rechazado (código 4), sin cambios.
  El tiempo del mes M es la suma de los intentos a y c.

Uso:
  python -m pipeline_competencia02.correr_meses --nueva <nombre> --desde 202001 --hasta 202006 [--reintento-en 202003]
  python -m pipeline_competencia02.correr_meses --ejecucion <carpeta> --desde 202001 --hasta 202006
Con --nueva, prepara la carpeta (preparar_ejecucion, historia hasta el mes anterior a --desde, con el catálogo
--catalogo; por defecto el activo) y mide esa preparación por separado: no forma parte del tiempo mensual.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from evaluacion.ganancia import envios as envios_fraccion

from . import catalogo as K
from . import retrospectiva as R
from .config import RAIZ, RUTAS, mostrar
from .ejecutar_mes import anterior
from .estrategias import orden_por_score

REC, ALT = "recomendacion_provisional", "alternativa"


def meses_entre(desde: int, hasta: int) -> list[int]:
    out, m = [], desde
    while m <= hasta:
        out.append(m)
        m = R.siguiente(m)
    return out


def sha(p: Path) -> str | None:
    if not p.is_file():
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def insumo(mes: int) -> Path:
    p = RUTAS.insumos / f"competencia_02_{mes}_crudo.csv"
    meta = json.loads(p.with_suffix(".json").read_text(encoding="utf-8"))
    if sha(p) != meta["sha256"]:
        raise RuntimeError(f"{p.name}: sha256 distinto del registrado al prepararlo")
    return p


def foto(env: Path) -> dict:
    """sha256 de lo publicado y del registro (sin logs ni ejecuciones.jsonl, que crecen con cada intento)."""
    out = {}
    for patron in ("output/*", "historia/*", "diagnosticos/*/reporte.json", "diagnosticos/*/decisiones_*.csv",
                   "registro/meses/*", "registro/retrospectiva/*", "registro/reporte_acumulado.csv"):
        for p in env.glob(patron):
            if p.is_file():
                out[p.relative_to(env).as_posix()] = sha(p)
    return out


def diferencias(a: dict, b: dict) -> list[str]:
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def condiciones() -> dict:
    """Estado de la máquina alrededor de cada proceso mensual (§ 17). En Windows, psutil puede informar la frecuencia
    nominal en lugar de la instantánea: se registra igual, junto con la carga, la RAM libre, la batería y el plan."""
    try:
        import psutil
    except ImportError:
        return {"disponible": False}
    f, bat = psutil.cpu_freq(), psutil.sensors_battery()
    plan = None
    if sys.platform == "win32":
        try:
            out = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, text=True, timeout=10).stdout
            plan = out[out.rfind("(") + 1:out.rfind(")")] or None
        except (OSError, subprocess.SubprocessError):
            pass
    return {"momento": time.strftime("%Y-%m-%dT%H:%M:%S"), "frecuencia_mhz": round(f.current) if f else None,
            "frecuencia_max_mhz": round(f.max) if f else None, "carga_cpu_pct": psutil.cpu_percent(interval=1),
            "ram_libre_gb": round(psutil.virtual_memory().available / 2**30, 2),
            "enchufada": bat.power_plugged if bat else None, "bateria_pct": bat.percent if bat else None,
            "plan_energia": plan, "procesos": len(psutil.pids())}


def despierto(activar: bool) -> None:
    """Evita la suspensión mientras corre la secuencia (ES_CONTINUOUS | ES_SYSTEM_REQUIRED)."""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | (0x00000001 if activar else 0))


def lanzar(env: Path, mes: int, origen: Path, falla: str | None = None) -> dict:
    cmd = [sys.executable, "-m", "pipeline_competencia02.mensual", "--ejecucion", str(env), "--mes", str(mes),
           "--copiar-desde", str(origen)]
    entorno = {k: v for k, v in os.environ.items() if k != "PIPELINE_C02_FALLA"}
    if falla:
        entorno["PIPELINE_C02_FALLA"] = falla
    antes = condiciones()  # fuera del reloj
    t = time.perf_counter()
    rc = subprocess.run(cmd, cwd=RAIZ, env=entorno, stdout=subprocess.DEVNULL).returncode
    pared = round(time.perf_counter() - t, 1)
    return {"codigo": rc, "pared_s": pared, "falla_inyectada": falla,
            "maquina": {"antes": antes, "despues": condiciones()}}


def leer_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def acumulado(env: Path) -> list[dict]:
    p = env / "registro" / "reporte_acumulado.csv"
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def completados(env: Path) -> list[int]:
    return sorted(int(p.stem) for p in (env / "registro" / "meses").glob("*.json")
                  if leer_json(p).get("estado") == "completado")


def clientes_parquet(con, p: Path) -> np.ndarray:
    return np.sort(con.execute(f"SELECT numero_de_cliente FROM read_parquet('{p.as_posix()}')").fetchnumpy()[
        "numero_de_cliente"].astype(np.int64))


def comprobar(env: Path, mes: int, inicial: set[int]) -> dict:
    diag = env / "diagnosticos" / str(mes)
    rep = leer_json(diag / "reporte.json")
    est = leer_json(env / "registro" / "meses" / f"{mes}.json")
    cat = leer_json(env / "modelos" / "estrategias.json")
    entrada = pd.read_csv(env / "input" / f"{mes}.csv", usecols=["numero_de_cliente"], dtype=str)
    # algunos ids vienen en notación científica; Decimal los convierte sin pasar por float
    cli_entrada = np.array(sorted(int(Decimal(c)) for c in entrada["numero_de_cliente"]), np.int64)
    salida_txt = (env / "output" / f"churn_{mes}.csv").read_text(encoding="utf-8")
    o = pd.read_csv(env / "output" / f"churn_{mes}.csv", float_precision="round_trip").sort_values(
        "numero_de_cliente", kind="stable")
    d = pd.read_csv(diag / f"decisiones_{mes}.csv", float_precision="round_trip").sort_values(
        "numero_de_cliente", kind="stable")
    cli = o["numero_de_cliente"].to_numpy(np.int64)
    prob = o["probabilidad"].to_numpy(np.float64)
    n = len(cli)
    con = duckdb.connect()
    cli_hist = clientes_parquet(con, env / "historia" / f"foto_mes={mes}.parquet")
    cli_feat = clientes_parquet(con, diag / f"features_{mes}.parquet")
    con.close()

    estr = {}
    for e in cat["estrategias"]:
        p = d[f"probabilidad_{e['id']}"].to_numpy(np.float64)
        env_ = d[f"enviar_{e['id']}"].to_numpy() == 1
        k = envios_fraccion(e["corte"]["fraccion"], n)
        esperado = np.zeros(n, bool)
        esperado[orden_por_score(cli, p)[:k]] = True
        estr[e["rol"]] = {"id": e["id"], "envios": int(env_.sum()), "envios_esperados": k,
                          "seleccion_es_prefijo_del_orden": bool(np.array_equal(env_, esperado)),
                          "probabilidades_validas": bool(np.isfinite(p).all() and ((p >= 0) & (p <= 1)).all()),
                          "envios_igual_reporte": int(env_.sum()) == next(
                              x["envios"] for x in rep["estrategias"] if x["id"] == e["id"])}
    rec_id = estr[REC]["id"]

    hist_meses = sorted(int(p.stem.split("=")[1]) for p in (env / "historia").glob("foto_mes=*.parquet"))
    comp = completados(env)
    lect = rep.get("lecturas", [])
    hist_leida = sorted(int(p.split("foto_mes=")[1][:6]) for p in lect if p.startswith("historia/"))
    permitidas = all(p == f"input/{mes}.csv" or p.startswith((f"tmp/{rep['ejecucion']}/", "historia/", "modelos/"))
                     for p in lect)
    filas = acumulado(env)
    filas_por_mes = {int(f["mes"]): f for f in filas}
    retro_ok = {}
    for m in comp:
        disp = R.disponibilidad(env / "historia", m)
        r = R.cargar(env, m) or {}
        fila = filas_por_mes.get(m, {})
        ok = r.get("disponibilidad") == disp and fila.get("metricas_con_target") == disp["estado"]
        if disp["estado"] == "completa":
            cl = r["clases"]
            ok = (ok and cl["BAJA+1"] + cl["BAJA+2"] + cl["CONTINUA"] == cl["clientes"]
                  and fila.get("rec_ganancia") not in (None, "", "pendiente"))
        retro_ok[m] = ok

    checks = {
        "completado": est.get("estado") == "completado" and rep.get("estado") == "completado",
        "integridad_sha256": rep.get("integridad", {}) == {
            "salida": sha(env / "output" / f"churn_{mes}.csv"),
            "historia": sha(env / "historia" / f"foto_mes={mes}.parquet"),
            "decisiones": sha(diag / f"decisiones_{mes}.csv")},
        "salida_cabecera_exacta": salida_txt.split("\n", 1)[0] == "numero_de_cliente,probabilidad,enviar",
        "salida_clientes_igual_entrada": np.array_equal(cli, cli_entrada) and len(np.unique(cli)) == n,
        "features_decisiones_historia_igual_entrada": np.array_equal(cli_feat, cli_entrada)
        and np.array_equal(d["numero_de_cliente"].to_numpy(np.int64), cli) and np.array_equal(cli_hist, cli_entrada),
        "salida_probabilidades_en_0_1": bool(np.isfinite(prob).all() and ((prob >= 0) & (prob <= 1)).all()),
        "salida_es_la_recomendacion": bool(np.array_equal(prob, d[f"probabilidad_{rec_id}"].to_numpy(np.float64))
                                           and np.array_equal(o["enviar"].to_numpy(), d[f"enviar_{rec_id}"].to_numpy())),
        "decisiones_dos_estrategias": all(v["envios"] == v["envios_esperados"] and v["seleccion_es_prefijo_del_orden"]
                                          and v["probabilidades_validas"] and v["envios_igual_reporte"]
                                          for v in estr.values()),
        "historia_inicial_mas_completados_sin_huecos": hist_meses == sorted(inicial | set(comp))
        and hist_meses == meses_entre(hist_meses[0], hist_meses[-1]),
        "lee_solo_entrada_historia_previa_y_modelos": permitidas and hist_leida == [m for m in hist_meses if m < mes],
        "reporte_una_fila_por_completado": [int(f["mes"]) for f in filas] == comp
        and all(f["integridad_ok"] == "True" for f in filas)
        and int(filas_por_mes[mes]["rec_envios"]) == estr[REC]["envios"]
        and int(filas_por_mes[mes]["alt_envios"]) == estr[ALT]["envios"],
        "retrospectiva_segun_meses_recibidos": all(retro_ok.values()),
    }
    cat_col = rep.get("categorias_columnas", {})
    return {
        "mes": mes, "ok": all(checks.values()), "checks": checks, "clientes": n,
        "envios": {"recomendacion": estr[REC]["envios"], "alternativa": estr[ALT]["envios"]},
        "probabilidad_minima_enviada": {x["rol"]: x["probabilidad_minima_enviada"] for x in rep["estrategias"]},
        "distribucion": {x["rol"]: x["distribucion"] for x in rep["estrategias"]},
        "coincidencia": rep["coincidencia"], "estado_calidad": rep.get("estado_calidad"),
        "anomalias": {"clientes_sin_historia": rep["features"]["clientes_sin_historia"],
                      "lag_fila_distinto_calendario":
                          rep["verificacion_features"]["lags"]["clientes_con_algun_lag_distinto_del_calendario"],
                      "columnas_100_nulas": cat_col.get("nula_100", []),
                      "columnas_observados_en_cero": cat_col.get("observados_en_cero", []),
                      "columnas_constantes_no_nulas": cat_col.get("constante_no_nula", []),
                      "cambio_tasa_nulos": next((i["variables"] for i in rep["incidentes"]
                                                 if i["regla"] == "cambio_tasa_nulos"), []),
                      "reglas": sorted({i["regla"] for i in rep["incidentes"]})},
        "historia_leida": f"{hist_leida[0]}-{hist_leida[-1]} ({len(hist_leida)} meses)",
        "tiempos_internos": rep["tiempos"], "total_interno_desde_entrada_s": est.get("total_desde_entrada_s"),
        "memoria": rep["memoria"], "reconciliacion": rep.get("reconciliacion"), "recuperado": est.get("recuperado", False),
    }


def provocar_reintento(env: Path, mes: int, origen: Path, proximo: tuple[int, Path]) -> tuple[list, dict]:
    """Pasos a–d del docstring. Devuelve (intentos que cuentan para el tiempo del mes, detalle de la prueba)."""
    filas_antes = [int(f["mes"]) for f in acumulado(env)]
    a = lanzar(env, mes, origen, falla="tras_publicacion")
    est = leer_json(env / "registro" / "meses" / f"{mes}.json")
    publicado = {k: (env / p).exists() for k, p in (("salida", f"output/churn_{mes}.csv"),
                                                    ("historia", f"historia/foto_mes={mes}.parquet"),
                                                    ("diagnostico", f"diagnosticos/{mes}/reporte.json"))}
    paso_a = {**a, "esperado": 3, "publicado": publicado, "estado": est.get("estado"),
              "candado_huerfano": (env / "registro" / "meses" / f"{mes}.lock").exists(),
              "reporte_sin_el_mes": [int(f["mes"]) for f in acumulado(env)] == filas_antes}
    paso_a["ok"] = (a["codigo"] == 3 and all(publicado.values()) and paso_a["estado"] == "en_curso"
                    and paso_a["candado_huerfano"] and paso_a["reporte_sin_el_mes"])
    detalle = {"mes": mes, "a_muere_tras_publicar": paso_a}

    antes = foto(env)
    b = lanzar(env, proximo[0], proximo[1])
    cambios = diferencias(antes, foto(env))
    ultimo = (env / "registro" / "ejecuciones.jsonl").read_text(encoding="utf-8").strip().split("\n")[-1]
    detalle["b_mes_siguiente_rechazado"] = {**b, "mes": proximo[0], "esperado": 4, "cambios": cambios,
                                            "motivo": json.loads(ultimo).get("motivo"),
                                            "ok": b["codigo"] == 4 and not cambios}
    # El intento rechazado ya había copiado input/<proximo>.csv (la recepción es lo primero). Se quita para que,
    # en la secuencia, ese mes vuelva a medirse desde la copia.
    (env / "input" / f"{proximo[0]}.csv").unlink(missing_ok=True)

    features = env / "diagnosticos" / str(mes) / f"features_{mes}.parquet"
    mtime = features.stat().st_mtime_ns
    antes = foto(env)
    c = lanzar(env, mes, origen)
    est = leer_json(env / "registro" / "meses" / f"{mes}.json")
    despues = foto(env)
    publicados_iguales = all(antes.get(k) == despues.get(k) for k in antes
                             if k.startswith(("output/", "historia/", f"diagnosticos/{mes}/")))
    sin_recalcular = features.stat().st_mtime_ns == mtime and publicados_iguales
    detalle["c_reintento_recupera"] = {
        **c, "esperado": 0, "estado": est.get("estado"), "recuperado": est.get("recuperado", False),
        "sin_recalcular": sin_recalcular, "intentos": [i["estado"] for i in est.get("intentos", [])],
        "ok": c["codigo"] == 0 and est.get("estado") == "completado" and est.get("recuperado", False) and sin_recalcular}

    antes = foto(env)
    dd = lanzar(env, mes, origen)
    cambios = diferencias(antes, foto(env))
    detalle["d_repetir_rechazado"] = {**dd, "esperado": 4, "cambios": cambios, "ok": dd["codigo"] == 4 and not cambios}
    detalle["ok"] = all(v["ok"] for v in detalle.values() if isinstance(v, dict))
    return [a, c], detalle


def preparar(nombre: str, hasta: int, catalogo: str) -> tuple[Path, dict]:
    t = time.perf_counter()
    rc = subprocess.run([sys.executable, "-m", "pipeline_competencia02.preparar_ejecucion", "--nombre", nombre,
                         "--hasta", str(hasta), "--catalogo", catalogo], cwd=RAIZ).returncode
    pared = round(time.perf_counter() - t, 1)
    if rc != 0:
        raise RuntimeError(f"preparar_ejecucion terminó con código {rc}")
    env = RUTAS.entornos / nombre
    cfg = leer_json(env / "entorno.json")
    return env, {"pared_s": pared, "interno_s": cfg["preparacion_s"], "historia": cfg["historia"]["cobertura"],
                 "catalogo": cfg["catalogo"],
                 "incluye": "copia y verificación de modelos y catálogo; historia inicial desde el Parquet de 2019 "
                            "controlada contra la auditoría de filas; validación de cobertura"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ensayo secuencial del pipeline mensual con dos estrategias.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--nueva", help="nombre de una carpeta de ejecución nueva (se prepara y se mide aparte)")
    g.add_argument("--ejecucion", type=Path, help="carpeta ya preparada")
    ap.add_argument("--desde", type=int, required=True)
    ap.add_argument("--hasta", type=int, required=True)
    ap.add_argument("--reintento-en", type=int, help="mes intermedio en el que se provoca y se prueba un reintento")
    ap.add_argument("--resumen", type=Path, help="copia del resumen, además de <ejecución>/pruebas/")
    ap.add_argument("--catalogo", choices=sorted(K.CATALOGOS), default=K.ACTIVO, help="sólo con --nueva")
    a = ap.parse_args(argv)
    meses = meses_entre(a.desde, a.hasta)
    if a.reintento_en and a.reintento_en not in meses[:-1]:
        ap.error("--reintento-en debe ser un mes de la secuencia que no sea el último")
    origenes = {m: insumo(m) for m in meses}  # verificación de los insumos, fuera del reloj
    resumen = {"inicio": time.strftime("%Y-%m-%dT%H:%M:%S"), "desde": a.desde, "hasta": a.hasta,
               "reloj": "pared del proceso mensual: desde antes de lanzarlo (incluye arranque e imports y la copia a "
                        "input/) hasta que termina, con la salida publicada y el reporte acumulado regenerado",
               "meses": []}
    if a.nueva:
        env, resumen["preparacion"] = preparar(a.nueva, anterior(a.desde), a.catalogo)
        print(f"Preparación: {resumen['preparacion']['pared_s']} s (fuera del tiempo mensual)", flush=True)
    else:
        env = a.ejecucion.resolve()
    resumen["ejecucion"] = mostrar(env)
    inicial = {int(m) for m in leer_json(env / "entorno.json")["historia"]["meses"]}
    codigo = 0
    despierto(True)
    for i, mes in enumerate(meses):
        if mes == a.reintento_en:
            intentos, resumen["reintento"] = provocar_reintento(env, mes, origenes[mes],
                                                                (meses[i + 1], origenes[meses[i + 1]]))
            ok_intentos = resumen["reintento"]["ok"]
        else:
            intentos = [lanzar(env, mes, origenes[mes])]
            ok_intentos = intentos[0]["codigo"] == 0
        if not ok_intentos:
            resumen["meses"].append({"mes": mes, "ok": False, "intentos": intentos})
            print(f"[{mes}] intentos inesperados {intentos}; se detiene la secuencia", flush=True)
            codigo = 2
            break
        r = comprobar(env, mes, inicial)
        r["intentos"] = intentos
        r["tiempo_total_s"] = round(sum(x["pared_s"] for x in intentos), 1)
        r["arranque_y_cierre_s"] = (round(intentos[0]["pared_s"] - r["total_interno_desde_entrada_s"], 1)
                                    if len(intentos) == 1 and r["total_interno_desde_entrada_s"] else None)
        resumen["meses"].append(r)
        print(f"[{mes}] {'OK' if r['ok'] else 'FALLA'} | {r['tiempo_total_s']} s | clientes {r['clientes']:,} | "
              f"envíos {r['envios']} | jaccard {r['coincidencia']['jaccard']} | "
              f"checks fallidos: {[k for k, v in r['checks'].items() if not v]}", flush=True)
        if not r["ok"]:
            codigo = 2
            break
    despierto(False)
    resumen["retrospectiva"] = {m: (R.cargar(env, m) or {}) for m in completados(env)}
    resumen["fin"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    resumen["ok"] = codigo == 0
    (env / "pruebas").mkdir(exist_ok=True)
    out = env / "pruebas" / f"secuencia_{a.desde}_{a.hasta}.json"
    texto = json.dumps(resumen, indent=2, ensure_ascii=False, default=str)
    out.write_text(texto, encoding="utf-8")
    if a.resumen:
        a.resumen.write_text(texto + "\n", encoding="utf-8", newline="\n")
    print(f"Resumen: {mostrar(out)}")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
