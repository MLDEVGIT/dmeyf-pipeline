"""Tablero de seguimiento: registro/reporte_seguimiento.html, acumulativo, interactivo y autocontenido (sin red).

Se regenera junto con registro/reporte_acumulado.csv (mensual.regenerar_reporte): al completar un mes, al recuperarlo
y con `--solo-reporte`. Es derivado: sólo lee lo publicado de la ejecución, no cambia salidas, historia ni modelos.
  - entorno.json                         catálogo y nombre de la ejecución
  - registro/meses/<mes>.json            estado, intentos y tiempo total
  - registro/ejecuciones.jsonl           intentos rechazados o fallidos
  - diagnosticos/<mes>/reporte.json      tiempos, memoria, clientes, columnas, scores, envíos, alertas, versiones
  - registro/retrospectiva/<mes>.json    etiquetas por presencia, ganancia y curva (retrospectiva.py)

Este módulo arma un JSON con esos datos (`datos`) y lo incrusta en el HTML junto con tablero/tablero.css,
tablero/logica.js (selección, agregación y formato; probado con Node) y tablero/interfaz.js (pestañas, filtros y
gráficos SVG). Sin recursos externos: abre sin conexión. El estado de los filtros va en el fragmento de la URL
(#v=negocio&m=202001,202002&e=ambas&t=todos&c=202004), así una vista se puede compartir o verificar.

Uso: python -m pipeline_competencia02.reporte_html --ejecucion <carpeta> [--abrir]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import webbrowser
from pathlib import Path

from evaluacion.ganancia import COSTO_ENVIO, PREMIO_BRUTO

ARCHIVO = "reporte_seguimiento.html"
TABLERO = Path(__file__).with_name("tablero")
LIMITE_S, MARGEN_S = 900, 450
UMBRAL_DERIVA_PP = 20.0  # el mismo umbral que la regla cambio_tasa_nulos (politica_incidentes.json)
MIN_OBSERVADOS_DERIVA = 1000  # Δ ceros sólo con variables observadas en al menos estos clientes en los dos meses
REC, ALT = "recomendacion_provisional", "alternativa"
ESTRATEGIAS = {
    REC: {"corto": "binario", "nombre": "Recomendación (binario)",
          "objetivo": "BAJA+1 ∪ BAJA+2: el cliente se va en t+1 o en t+2",
          "score": "P(BAJA+1 ∪ BAJA+2)"},
    ALT: {"corto": "multiclase", "nombre": "Alternativa (multiclase)",
          "objetivo": "BAJA+2: el cliente se va en t+2 (columna BAJA+2 del multiclase CONTINUA / BAJA+1 / BAJA+2)",
          "score": "P(BAJA+2)"}}
ETAPAS = [("validacion", "Recepción y validación", ("recepcion_s", "validacion_s", "perfil_s", "deteccion_cero_anomalo_s")),
          ("features", "Features", ("features_s", "verificacion_features_s")),
          ("inf_rec", "Inferencia binario", ()), ("inf_alt", "Inferencia multiclase", ()),
          ("lectura", "Carga de modelos y lectura", ("carga_modelos_s", "lectura_y_conversion_s")),
          ("escritura", "Escritura, publicación y reporte", ("estrategias_s", "escritura_s"))]
NOMBRE_REGLA = {"cero_anomalo": "columna en 0 inesperada", "observados_en_cero": "todos los observados en 0",
                "columna_100_nula": "columna 100 % nula", "constante_no_nula": "constante no nula",
                "cambio_tasa_nulos": "cambio de la tasa de nulos", "scores_saturados": "scores en 0 o 1"}
REGLAS_CALIDAD = tuple(NOMBRE_REGLA)


def leer(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def r6(x):
    return None if x is None else round(float(x), 6)


def etapas_mes(rep: dict, est: dict, ids: dict) -> dict:
    """Segundos por etapa. La última absorbe la publicación y lo que el reloj del mes mide fuera de las etapas."""
    t = rep.get("tiempos", {})
    out = {}
    for clave, _, campos in ETAPAS:
        if clave == "inf_rec":
            v = t.get(f"inferencia_{ids.get(REC)}_s")
        elif clave == "inf_alt":
            v = t.get(f"inferencia_{ids.get(ALT)}_s")
        else:
            vals = [float(t[c]) for c in campos if t.get(c) is not None]
            v = sum(vals) if vals else None
        out[clave] = None if v is None else round(float(v), 2)
    pub = (est.get("tiempos_finales") or {}).get("publicacion_y_reporte_s")
    if pub is not None:
        out["escritura"] = round((out["escritura"] or 0) + float(pub), 2)
    total = est.get("total_desde_entrada_s")
    if total is not None:
        resto = float(total) - sum(v or 0 for v in out.values())
        if resto > 0:
            out["escritura"] = round((out["escritura"] or 0) + resto, 2)
    return out


def estado_target(rep: dict, retro: dict | None) -> dict:
    disp = (retro or {}).get("disponibilidad") or {}
    est = disp.get("estado") or rep.get("metricas_con_target", {}).get("estado") or "no_disponible"
    if (retro or {}).get("error"):
        est = "no_disponible"
    out = {"estado": est, "falta": [int(x) for x in disp.get("falta", [])]}
    cl = (retro or {}).get("clases") or {}
    if cl.get("definitivas"):
        out["clases"] = {k: cl.get(k) for k in ("BAJA+1", "BAJA+2", "CONTINUA", "clientes")}
    if (retro or {}).get("provisional"):
        out["provisional_ausentes_t1"] = retro["provisional"].get("ausentes_en_t1")
    return out


def mes_datos(raiz: Path, est: dict, rechazos: dict) -> dict | None:
    m = int(est["mes"])
    rep = leer(raiz / "diagnosticos" / str(m) / "reporte.json")
    if rep is None:
        return None
    retro = leer(raiz / "registro" / "retrospectiva" / f"{m}.json")
    estr = {e["rol"]: e for e in rep.get("estrategias", [])}
    ids = {r: e["id"] for r, e in estr.items()}
    por_rol_retro = {e["rol"]: e for e in (retro or {}).get("estrategias", [])}
    n = rep.get("validacion", {}).get("clientes")
    f = rep.get("features", {})
    fal = rep.get("faltantes", {})
    ceros = (fal.get("ceros") or {}).get("por_columna")
    alertas = [{"regla": i["regla"], "nombre": NOMBRE_REGLA[i["regla"]], "variables": i.get("variables") or [],
                "detalle": i.get("detalle")} for i in rep.get("incidentes", []) if i["regla"] in REGLAS_CALIDAD]
    det = rep.get("deteccion_cero_anomalo")
    out = {
        "mes": m, "recuperado": bool(est.get("recuperado")),
        "intentos": [i.get("estado") for i in est.get("intentos", [])], "rechazos": rechazos.get(m, 0),
        "calidad": rep.get("estado_calidad"), "alertas": alertas,
        "clientes": n, "nuevos": f.get("clientes_sin_historia"), "con_lag1": f.get("con_lag1"), "con_lag2": f.get("con_lag2"),
        "lag_distinto": (rep.get("verificacion_features", {}).get("lags") or {}).get("clientes_con_algun_lag_distinto_del_calendario"),
        "historia_meses": len(rep.get("validacion", {}).get("historia_meses", [])) or None,
        "etapas": etapas_mes(rep, est, ids), "total_s": est.get("total_desde_entrada_s"),
        "memoria": rep.get("memoria"), "versiones": rep.get("versiones"),
        "politica": (rep.get("politica_incidentes") or {}).get("version"),
        "catalogo_sha12": (rep.get("catalogo") or {}).get("sha256", "")[:12] or None,
        "target": estado_target(rep, retro), "regla_target": (retro or {}).get("version"),
        "coincidencia": rep.get("coincidencia"),
        "nulos": fal.get("por_columna", {}), "ceros": ceros,
        "deteccion": None if det is None else {"candidatas": det.get("candidatas"),
                                               "detectadas": [{"columna": d["columna"], "E": d.get("esperados_no_cero"),
                                                               "ref": d.get("mes_referencia")} for d in det.get("detectadas", [])]},
        "estr": {}}
    for rol, e in estr.items():
        d = e.get("distribucion") or {}
        r = por_rol_retro.get(rol) or {}
        out["estr"][rol] = {
            "id": e["id"], "envios": e.get("envios"), "fraccion": e.get("fraccion"),
            "prob_min": r6(e.get("probabilidad_minima_enviada")),
            "media": r6(d.get("media")), "mayor_0_5": d.get("mayor_0_5"),
            "q": {k: r6(v) for k, v in (d.get("cuantiles") or {}).items()},
            "modelos": [{"semilla": s, "sha12": h[:12]} for s, h in zip(e.get("semillas", []), e.get("modelos_sha256", []))],
            "retro": None if "ganancia" not in r else {
                "baja2": r.get("baja2_enviados"), "baja1": r.get("baja1_enviados"), "ganancia": r.get("ganancia"),
                "auc": r6(r.get("auc_baja2")), "max_ex_post": r.get("ganancia_maxima_ex_post"),
                "k_max": r.get("envios_ganancia_maxima_ex_post"), "curva": r.get("curva")},
            "provisional_ausentes_enviados": r.get("provisional_ausentes_en_t1_enviados")}
    return out


def deriva(meses: list[dict]) -> None:
    """Indicadores contra el mes procesado anterior (no contra 2019: el PSI contra 2019 no está implementado)."""
    prev = None
    for x in meses:
        d = {"contra": prev["mes"] if prev else None}
        if prev and x["clientes"] and prev["clientes"]:
            vars_ = set(x["nulos"]) | set(prev["nulos"])
            dn = {v: 100 * (x["nulos"].get(v, 0) / x["clientes"] - prev["nulos"].get(v, 0) / prev["clientes"]) for v in vars_}
            v_max = max(dn, key=lambda v: abs(dn[v]), default=None)
            d["nulos"] = {"max_pp": round(abs(dn[v_max]), 2) if v_max else 0.0, "variable": v_max,
                          "sobre_umbral": sorted(v for v, c in dn.items() if abs(c) > UMBRAL_DERIVA_PP)}
            if x["ceros"] is not None and prev["ceros"] is not None:
                def pz(m, v):
                    obs = m["clientes"] - m["nulos"].get(v, 0)
                    return 100 * m["ceros"].get(v, 0) / obs if obs >= MIN_OBSERVADOS_DERIVA else None
                dz = {}
                for v in set(x["ceros"]) | set(prev["ceros"]):
                    a, b = pz(x, v), pz(prev, v)
                    if a is not None and b is not None:
                        dz[v] = a - b
                z_max = max(dz, key=lambda v: abs(dz[v]), default=None)
                d["ceros"] = {"max_pp": round(abs(dz[z_max]), 2) if z_max else 0.0, "variable": z_max,
                              "sobre_umbral": sorted(v for v, c in dz.items() if abs(c) > UMBRAL_DERIVA_PP)}
            d["mediana_score"] = {r: (round(x["estr"][r]["q"]["0.5"] / prev["estr"][r]["q"]["0.5"], 4)
                                      if r in x["estr"] and r in prev["estr"] and x["estr"][r]["q"].get("0.5")
                                      and prev["estr"][r]["q"].get("0.5") else None) for r in (REC, ALT)}
        x["deriva"] = d
        prev = x


def datos(raiz: Path) -> dict:
    raiz = Path(raiz)
    cfg = leer(raiz / "entorno.json") or {}
    rechazos: dict[int, int] = {}
    log = raiz / "registro" / "ejecuciones.jsonl"
    if log.exists():
        for linea in log.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if d.get("estado") in ("rechazada", "fallido") and d.get("mes"):
                rechazos[int(d["mes"])] = rechazos.get(int(d["mes"]), 0) + 1
    meses = []
    for p in sorted((raiz / "registro" / "meses").glob("*.json")):
        est = leer(p)
        if est and est.get("estado") == "completado":
            x = mes_datos(raiz, est, rechazos)
            if x:
                meses.append(x)
    meses.sort(key=lambda x: x["mes"])
    deriva(meses)
    variables = [c for c, _ in cfg.get("esquema_crudo", []) if c not in ("numero_de_cliente", "foto_mes")]
    cat = cfg.get("catalogo", {})
    ultimo = meses[-1]["estr"] if meses else {}
    return {
        "generado": time.strftime("%Y-%m-%d %H:%M"), "ejecucion": cfg.get("nombre", raiz.name),
        "catalogo": {"nombre": cat.get("nombre"), "sha12": (cat.get("sha256") or "")[:12] or None,
                     "estrategias": [{"rol": r, **ESTRATEGIAS[r], "id": ultimo.get(r, {}).get("id"),
                                      "fraccion": ultimo.get(r, {}).get("fraccion"),
                                      "modelos": ultimo.get(r, {}).get("modelos", [])} for r in (REC, ALT)]},
        "importes": {"premio": PREMIO_BRUTO, "costo": COSTO_ENVIO, "fuente": "competencia 01",
                     "estado_c02": "pendiente de confirmación (docs/GANANCIA.md)"},
        "limites": {"limite_s": LIMITE_S, "margen_s": MARGEN_S, "umbral_deriva_pp": UMBRAL_DERIVA_PP,
                    "min_observados_deriva": MIN_OBSERVADOS_DERIVA},
        "etapas": [{"clave": k, "nombre": n} for k, n, _ in ETAPAS],
        "variables": variables, "meses": meses}


def html(d: dict) -> str:
    css = (TABLERO / "tablero.css").read_text(encoding="utf-8")
    logica = (TABLERO / "logica.js").read_text(encoding="utf-8")
    interfaz = (TABLERO / "interfaz.js").read_text(encoding="utf-8")
    payload = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    meses_attr = ",".join(str(x["mes"]) for x in d["meses"])
    return f'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tablero de seguimiento</title>
<style>{css}</style></head>
<body data-meses="{meses_attr}">
<div id="app"><noscript>Este tablero necesita JavaScript habilitado en el navegador (no usa conexión a internet).</noscript></div>
<script id="datos" type="application/json">{payload}</script>
<script>{logica}</script>
<script>{interfaz}</script>
</body></html>
'''


def generar(raiz: Path) -> Path:
    raiz = Path(raiz)
    destino = raiz / "registro" / ARCHIVO
    texto = html(datos(raiz))
    tmp = destino.with_name(destino.name + f".tmp-{os.getpid()}")
    tmp.write_text(texto, encoding="utf-8", newline="\n")
    os.replace(tmp, destino)
    return destino


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Genera (y opcionalmente abre) el tablero HTML de seguimiento.")
    ap.add_argument("--ejecucion", type=Path, required=True)
    ap.add_argument("--abrir", action="store_true", help="abre el archivo en el navegador predeterminado")
    a = ap.parse_args(argv)
    t = time.perf_counter()
    p = generar(a.ejecucion.resolve())
    print(f"{p} ({time.perf_counter() - t:.2f} s)")
    if a.abrir:
        webbrowser.open(p.resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
