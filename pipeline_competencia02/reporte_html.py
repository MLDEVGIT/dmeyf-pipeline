"""Reporte HTML de seguimiento: registro/reporte_seguimiento.html, acumulativo y autocontenido (sin red).

Se regenera junto con registro/reporte_acumulado.csv (mensual.regenerar_reporte): al completar un mes, al recuperarlo
y con `--solo-reporte`. Es derivado: sólo lee lo publicado de la ejecución, no cambia salidas, historia ni modelos.
  - entorno.json                         catálogo y nombre de la ejecución
  - registro/meses/<mes>.json            estado, intentos y tiempo total
  - diagnosticos/<mes>/reporte.json      tiempos por etapa, clientes, columnas, scores, envíos, alertas
  - registro/retrospectiva/<mes>.json    etiquetas por presencia, ganancia y curva (retrospectiva.py)
Sin JavaScript ni recursos externos: CSS y gráficos SVG en línea; cada gráfico tiene su tabla.

Uso: python -m pipeline_competencia02.reporte_html --ejecucion <carpeta> [--abrir]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import webbrowser
from html import escape
from pathlib import Path

from evaluacion.ganancia import COSTO_ENVIO, PREMIO_BRUTO

ARCHIVO = "reporte_seguimiento.html"
LIMITE_S, MARGEN_S = 900, 450
REC, ALT = "recomendacion_provisional", "alternativa"
SERIE = {REC: "s1", ALT: "s2"}
NOMBRE_ROL = {REC: "Recomendación (binario)", ALT: "Alternativa (multiclase)"}
SIGNIFICADO = {REC: "probabilidad de BAJA+1 ∪ BAJA+2 (objetivo binario: el cliente se va en t+1 o en t+2)",
               ALT: "probabilidad de BAJA+2 (columna BAJA+2 del multiclase CONTINUA / BAJA+1 / BAJA+2)"}
REGLAS_CALIDAD = ("cero_anomalo", "observados_en_cero", "columna_100_nula", "constante_no_nula", "cambio_tasa_nulos",
                  "scores_saturados")
NOMBRE_REGLA = {"cero_anomalo": "columna en 0 inesperada (E06)", "observados_en_cero": "todos los observados en 0",
                "columna_100_nula": "columna 100 % nula", "constante_no_nula": "constante no nula",
                "cambio_tasa_nulos": "cambio de la tasa de nulos", "scores_saturados": "scores en 0 o 1"}


# ------------------------------------------------------------------ formato (es-AR)
def n0(x) -> str:
    return "—" if x is None else f"{x:,.0f}".replace(",", ".")


def nd(x, d=1) -> str:
    if x is None:
        return "—"
    return f"{x:,.{d}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def mill(x) -> str:
    return "—" if x is None else nd(x / 1e6, 1) + " M"


def pct(x, d=1) -> str:
    return "—" if x is None else nd(100 * x, d) + " %"


def mes_txt(m) -> str:
    m = int(m)
    return f"{m // 100}-{m % 100:02d}"


def pend(texto="pendiente") -> str:
    return f'<span class="pend">{escape(texto)}</span>'


# ------------------------------------------------------------------ datos
def leer(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def cargar(raiz: Path) -> dict:
    cfg = leer(raiz / "entorno.json") or {}
    meses = []
    for p in sorted((raiz / "registro" / "meses").glob("*.json")):
        est = leer(p)
        if not est or est.get("estado") != "completado":
            continue
        m = int(est["mes"])
        rep = leer(raiz / "diagnosticos" / str(m) / "reporte.json")
        if rep is None:
            continue
        meses.append({"mes": m, "est": est, "rep": rep, "retro": leer(raiz / "registro" / "retrospectiva" / f"{m}.json"),
                      "estr": {e["rol"]: e for e in rep.get("estrategias", [])}})
    return {"cfg": cfg, "meses": sorted(meses, key=lambda x: x["mes"]), "raiz": raiz}


def etapas(x: dict) -> list[tuple[str, float]]:
    t = x["rep"].get("tiempos", {})
    ids = {r: e["id"] for r, e in x["estr"].items()}
    inf = {r: float(t.get(f"inferencia_{i}_s", 0) or 0) for r, i in ids.items()}
    val = sum(float(t.get(k, 0) or 0) for k in ("recepcion_s", "validacion_s", "perfil_s", "deteccion_cero_anomalo_s"))
    feat = sum(float(t.get(k, 0) or 0) for k in ("features_s", "verificacion_features_s"))
    total = total_mes(x)
    resto = max(0.0, (total or 0) - val - feat - inf.get(REC, 0) - inf.get(ALT, 0))
    return [("Recepción, validación y perfil", val), ("Features", feat), ("Inferencia del binario", inf.get(REC, 0)),
            ("Inferencia del multiclase", inf.get(ALT, 0)), ("Modelos, escritura, publicación y reporte", resto)]


def total_mes(x: dict):
    v = x["est"].get("total_desde_entrada_s")
    if v is None:
        v = x["rep"].get("tiempos", {}).get("total_hasta_publicacion_s")
    return v


# ------------------------------------------------------------------ SVG
def escala(v, d0, d1, r0, r1):
    return r0 if d1 == d0 else r0 + (v - d0) * (r1 - r0) / (d1 - d0)


def ticks(hi: float, n: int = 5, lo: float = 0.0) -> list[float]:
    """Marcas redondas desde <= lo hasta >= hi (la última siempre cubre el máximo)."""
    import math
    rango = hi - lo
    if rango <= 0:
        return [lo, lo + 1]
    paso = 10 ** math.floor(math.log10(rango / n))
    for f in (1, 2, 2.5, 5, 10):
        if rango / (paso * f) <= n:
            paso *= f
            break
    v = math.floor(lo / paso) * paso
    out = []
    while True:
        out.append(round(v, 10))
        if v >= hi - 1e-12:
            return out
        v += paso


def leyenda(items: list[tuple[str, str]]) -> str:
    return '<div class="leyenda">' + "".join(
        f'<span><i style="background:var(--{c})"></i>{escape(t)}</span>' for t, c in items) + "</div>"


def svg_barras_apiladas(meses: list[int], segs: list[tuple[str, str, list[float]]], refs, titulo: str) -> str:
    W, H, ml, mr, mt, mb = 720, 300, 52, 150, 12, 30
    totales = [sum(s[2][i] for s in segs) for i in range(len(meses))]
    top = max([*totales, *(r[0] for r in refs)]) * 1.08
    yt = ticks(top)
    top = max(top, yt[-1])
    y = lambda v: escala(v, 0, top, H - mb, mt)  # noqa: E731
    bw = min(56, (W - ml - mr) / max(1, len(meses)) * 0.6)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{escape(titulo)}">']
    for v in yt:
        out.append(f'<line class="grid" x1="{ml}" x2="{W - mr}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                   f'<text class="eje" x="{ml - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{n0(v)}</text>')
    for i, m in enumerate(meses):
        cx = ml + (i + 0.5) * (W - ml - mr) / len(meses)
        base = 0.0
        for nombre, color, vals in segs:
            v = vals[i]
            if v <= 0:
                continue
            y0, y1 = y(base), y(base + v)
            out.append(f'<rect x="{cx - bw / 2:.1f}" y="{y1:.1f}" width="{bw:.1f}" height="{max(0.5, y0 - y1):.1f}" '
                       f'fill="var(--{color})" class="seg"><title>{mes_txt(m)} · {escape(nombre)}: {nd(v)} s</title></rect>')
            base += v
        out.append(f'<text class="valor" x="{cx:.1f}" y="{y(base) - 5:.1f}" text-anchor="middle">{n0(base)}</text>'
                   f'<text class="eje" x="{cx:.1f}" y="{H - 10}" text-anchor="middle">{mes_txt(m)}</text>')
    for v, txt in refs:
        out.append(f'<line class="ref" x1="{ml}" x2="{W - mr}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                   f'<text class="ref-t" x="{W - mr + 6}" y="{y(v) + 4:.1f}">{escape(txt)}</text>')
    out.append(f'<line class="base" x1="{ml}" x2="{W - mr}" y1="{y(0):.1f}" y2="{y(0):.1f}"/></svg>')
    return (f'<figure><figcaption>{escape(titulo)}</figcaption>' + leyenda([(s[0], s[1]) for s in segs])
            + "".join(out) + "</figure>")


def svg_lineas(meses: list[int], series: list[tuple[str, str, list]], titulo: str, fmt=nd, log=False,
               ymin=None, unidad="", cortos: list[str] | None = None) -> str:
    """Series por mes. Título visible; leyenda con 2+ series; rótulos directos cortos (`cortos`) al final de cada
    serie, separados para no superponerse. Los meses sin dato (None) cortan la línea."""
    W, H, ml, mr, mt, mb = 720, 240, 64, 96, 14, 30
    vals = [v for _, _, s in series for v in s if v is not None]
    if not vals:
        return f'<figure><figcaption>{escape(titulo)}</figcaption><p class="nota">{pend("sin datos para graficar")}</p></figure>'
    import math
    if log:
        lo, hi = math.floor(math.log10(min(vals))), math.ceil(math.log10(max(vals)))
        tr = lambda v: math.log10(v)  # noqa: E731
        yt = [10.0 ** k for k in range(lo, hi + 1)]
        d0, d1 = lo, hi
    else:
        yt = ticks(max(vals) * 1.05, lo=min(0.0 if ymin is None else ymin, min(vals)))
        d0, d1 = yt[0], yt[-1]
        tr = lambda v: v  # noqa: E731
    y = lambda v: escala(tr(v), d0, d1, H - mb, mt)  # noqa: E731
    x = lambda i: ml + (i + 0.5) * (W - ml - mr) / len(meses)  # noqa: E731
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{escape(titulo)}">']
    for v in yt:
        out.append(f'<line class="grid" x1="{ml}" x2="{W - mr}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                   f'<text class="eje" x="{ml - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{escape(fmt(v))}</text>')
    for i, m in enumerate(meses):
        out.append(f'<text class="eje" x="{x(i):.1f}" y="{H - 10}" text-anchor="middle">{mes_txt(m)}</text>')
    for nombre, color, s in series:
        tramo = []
        for i, v in enumerate(s):
            if v is None:
                if len(tramo) > 1:
                    out.append(f'<polyline fill="none" stroke="var(--{color})" stroke-width="2" points="{" ".join(tramo)}"/>')
                tramo = []
                continue
            tramo.append(f"{x(i):.1f},{y(v):.1f}")
        if len(tramo) > 1:
            out.append(f'<polyline fill="none" stroke="var(--{color})" stroke-width="2" points="{" ".join(tramo)}"/>')
        for i, v in enumerate(s):
            if v is None:
                continue
            out.append(f'<g><circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="4" fill="var(--{color})" class="punto"/>'
                       f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="11" fill="transparent"/>'
                       f'<title>{mes_txt(meses[i])} · {escape(nombre)}: {escape(fmt(v))}{unidad}</title></g>')
    if cortos and len(series) <= 4:
        etq = []
        for (nombre, color, s), corto in zip(series, cortos):
            ult = next(((i, v) for i, v in reversed(list(enumerate(s))) if v is not None), None)
            if ult:
                etq.append([y(ult[1]) + 4, x(ult[0]) + 9, corto])
        etq.sort()
        for j in range(1, len(etq)):  # separa rótulos a >= 13 px
            etq[j][0] = max(etq[j][0], etq[j - 1][0] + 13)
        out += [f'<text class="etq" x="{xx:.1f}" y="{yy:.1f}">{escape(t)}</text>' for yy, xx, t in etq]
    out.append(f'<line class="base" x1="{ml}" x2="{W - mr}" y1="{H - mb}" y2="{H - mb}"/></svg>')
    return (f'<figure><figcaption>{escape(titulo)}</figcaption>'
            + (leyenda([(n, c) for n, c, _ in series]) if len(series) > 1 else "") + "".join(out) + "</figure>")


def svg_curvas(x: dict) -> str:
    W, H, ml, mr, mt, mb = 340, 220, 52, 12, 12, 34
    est = [e for e in (x["retro"] or {}).get("estrategias", []) if "curva" in e]
    if not est:
        return ""
    xs = [k for e in est for k in e["curva"]["envios"]]
    ys = [g / 1e6 for e in est for g in e["curva"]["ganancia"]]
    x1 = max(xs)
    xt, yt = [t for t in ticks(x1, 4) if t <= x1], ticks(max(ys) * 1.05, 5, lo=min(0.0, min(ys)))
    X = lambda v: escala(v, 0, x1, ml, W - mr)  # noqa: E731
    Y = lambda v: escala(v, yt[0], yt[-1], H - mb, mt)  # noqa: E731
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Curva de ganancia {mes_txt(x["mes"])}">']
    for v in yt:
        out.append(f'<line class="grid" x1="{ml}" x2="{W - mr}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>'
                   f'<text class="eje" x="{ml - 5}" y="{Y(v) + 4:.1f}" text-anchor="end">{n0(v)}</text>')
    for v in xt:
        out.append(f'<text class="eje" x="{X(v):.1f}" y="{H - 18}" text-anchor="middle">{n0(v)}</text>')
    out.append(f'<text class="eje" x="{(ml + W - mr) / 2:.0f}" y="{H - 3}" text-anchor="middle">envíos</text>')
    if yt[0] < 0:
        out.append(f'<line class="base" x1="{ml}" x2="{W - mr}" y1="{Y(0):.1f}" y2="{Y(0):.1f}"/>')
    for e in est:
        c = SERIE.get(e["rol"], "s3")
        pts = " ".join(f"{X(k):.1f},{Y(g / 1e6):.1f}" for k, g in zip(e["curva"]["envios"], e["curva"]["ganancia"]))
        out.append(f'<polyline fill="none" stroke="var(--{c})" stroke-width="2" points="{pts}"/>')
        k, g = e["envios"], e["ganancia"] / 1e6
        out.append(f'<g><circle cx="{X(k):.1f}" cy="{Y(g):.1f}" r="5" fill="var(--{c})" class="punto"/>'
                   f'<circle cx="{X(k):.1f}" cy="{Y(g):.1f}" r="11" fill="transparent"/>'
                   f'<title>{NOMBRE_ROL.get(e["rol"], e["id"])}: corte en {n0(k)} envíos, {mill(e["ganancia"])}; '
                   f'máximo ex post {mill(e["ganancia_maxima_ex_post"])} en {n0(e["envios_ganancia_maxima_ex_post"])}</title></g>')
    out.append(f'<line class="base" x1="{ml}" x2="{W - mr}" y1="{H - mb}" y2="{H - mb}"/></svg>')
    return f'<figure><figcaption>{mes_txt(x["mes"])} · ganancia (M) según envíos; punto = corte aplicado</figcaption>{"".join(out)}</figure>'


# ------------------------------------------------------------------ secciones
def tabla(cab: list[str], filas: list[list[str]], clase="") -> str:
    th = "".join(f"<th>{c}</th>" for c in cab)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in f) + "</tr>" for f in filas)
    return f'<div class="tabla {clase}"><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


def datos(titulo: str, contenido: str) -> str:
    return f"<details><summary>{escape(titulo)}</summary>{contenido}</details>"


def estado_etiquetas(x: dict) -> tuple[str, str]:
    r = x["retro"]
    if r and r.get("error"):
        return "error", pend("error al calcular")
    disp = (r or {}).get("disponibilidad") or {}
    est = disp.get("estado") or x["rep"].get("metricas_con_target", {}).get("estado", "pendiente")
    falta = disp.get("falta") or []
    if est == "completa":
        return est, "completa"
    if est == "parcial":
        return est, pend(f"parcial: falta {', '.join(mes_txt(f) for f in falta)}")
    req = x["rep"].get("metricas_con_target", {}).get("requiere_listas_de", "")
    return est, pend(f"pendiente: faltan {', '.join(mes_txt(f) for f in falta)}" if falta else f"pendiente ({req})")


def detectadas(x: dict):
    d = x["rep"].get("deteccion_cero_anomalo")
    return None if d is None else d.get("detectadas", [])


def reglas_calidad(x: dict) -> dict:
    out = {}
    for i in x["rep"].get("incidentes", []):
        if i["regla"] in REGLAS_CALIDAD:
            out[i["regla"]] = len(i.get("variables") or []) or 1
    return out


def seccion_alertas(meses: list[dict]) -> str:
    con = [x for x in meses if x["rep"].get("estado_calidad") == "con_alertas"]
    if not con:
        return '<p>Ningún mes procesado tiene alertas de calidad de datos.</p>'
    bloques = []
    for x in con:
        r = reglas_calidad(x)
        det = detectadas(x)
        cat = x["rep"].get("categorias_columnas", {})
        cols = cat.get("observados_en_cero", [])
        n = x["rep"]["validacion"]["clientes"]
        if det is None:
            alcance_det = "la regla <code>cero_anomalo</code> no se evaluó: el mes se procesó antes de integrarla"
        elif det:
            es = [d["esperados_no_cero"] for d in det]
            refs = sorted({d["mes_referencia"] for d in det})
            alcance_det = (f"<code>cero_anomalo</code> marca {len(det)} columna(s): según el mes de referencia "
                           f"({', '.join(mes_txt(m) for m in refs)}) se esperaban entre {n0(min(es))} y {n0(max(es))} "
                           f"valores distintos de 0 por columna")
        else:
            alcance_det = "<code>cero_anomalo</code> no marca ninguna columna (actividad esperada baja o sin referencia)"
        lista = ", ".join(f"<code>{escape(c)}</code>" for c in cols) or "—"
        bloques.append(
            f'<div class="alerta"><h3><span aria-hidden="true">⚠</span> {mes_txt(x["mes"])}: datos con alertas</h3>'
            f'<ul><li><b>Reglas:</b> {"; ".join(f"{escape(NOMBRE_REGLA.get(k, k))} ({v})" for k, v in r.items())}.</li>'
            f'<li><b>Alcance:</b> {len(cols)} columna(s) llegaron con todos sus valores observados en 0, sobre '
            f'{n0(n)} clientes; {alcance_det}.</li>'
            f'<li><b>Decisión:</b> se conservan los datos recibidos. El pipeline no reemplaza valores (política '
            f'<i>advertir</i>); las features, el score y la selección del mes se calcularon con esas columnas tal como '
            f'llegaron, y la historia guarda el dato recibido. E06 (docs/PLAN_PRUEBAS.md § 19–20) evaluó con 2019 '
            f'reemplazarlas por faltantes o por el último valor del cliente y ninguna alternativa cumplió el criterio '
            f'de adopción.</li></ul>{datos("Columnas", "<p>" + lista + "</p>")}</div>')
    return "".join(bloques)


def generar_html(d: dict) -> str:
    meses, cfg = d["meses"], d["cfg"]
    ms = [x["mes"] for x in meses]
    cat = cfg.get("catalogo", {})
    gen = time.strftime("%Y-%m-%d %H:%M")
    S = []

    # resumen
    tot = [total_mes(x) for x in meses]
    alertas = [mes_txt(x["mes"]) for x in meses if x["rep"].get("estado_calidad") == "con_alertas"]
    completas = [x for x in meses if estado_etiquetas(x)[0] == "completa"]
    S.append(f'''<section class="tiles">
<div class="tile"><span>Meses procesados</span><b>{len(meses)}</b><small>{mes_txt(ms[0]) + " a " + mes_txt(ms[-1]) if ms else "ninguno"}</small></div>
<div class="tile"><span>Tiempo máximo por mes</span><b>{n0(max([t for t in tot if t] or [0]))} s</b><small>límite {LIMITE_S} s · margen interno {MARGEN_S} s</small></div>
<div class="tile"><span>Meses con alertas de datos</span><b>{len(alertas)}</b><small>{", ".join(alertas) or "ninguno"}</small></div>
<div class="tile"><span>Meses con etiquetas completas</span><b>{len(completas)}</b><small>{", ".join(mes_txt(x["mes"]) for x in completas) or "ninguno"}</small></div>
</section>''')

    # 1. catálogo y modelos
    filas = []
    if meses:
        for rol in (REC, ALT):
            e = meses[-1]["estr"].get(rol)
            if not e:
                continue
            shas = e.get("modelos_sha256", [])
            filas.append([NOMBRE_ROL[rol], f"<code>{escape(e['id'])}</code>", escape(SIGNIFICADO[rol]),
                          f"{nd(100 * e['fraccion'], 3)} % de los clientes", str(len(shas)),
                          datos(f"{len(shas)} modelos", "<p>" + ", ".join(
                              f"<code>{escape(str(s))}·{escape(h[:12])}</code>" for s, h in zip(e.get("semillas", []), shas)) + "</p>")])
    cambios = sorted({x["rep"].get("catalogo", {}).get("sha256", "")[:12] for x in meses})
    S.append(f'''<section><h2>1. Catálogo y modelos</h2>
<p>Ejecución <code>{escape(cfg.get("nombre", d["raiz"].name))}</code> · catálogo <b>{escape(cat.get("nombre", "—"))}</b>
(<code>{escape(cat.get("sha256", "")[:12])}</code>) · política de incidentes versión {", ".join(sorted({str(x["rep"].get("politica_incidentes", {}).get("version", "—")) for x in meses}))}.
{"El catálogo es el mismo en todos los meses." if len(cambios) <= 1 else "<b>El catálogo cambió entre meses:</b> " + ", ".join(cambios)}</p>
{tabla(["Estrategia", "Id", "Score", "Corte", "Semillas", "Modelos (semilla · sha256)"], filas)}
<p class="nota">Las dos estrategias puntúan a todos los clientes; la salida oficial (<code>output/churn_&lt;mes&gt;.csv</code>) lleva la recomendación. Cada estrategia promedia las probabilidades de sus semillas y envía la fracción fija de clientes con mayor probabilidad.</p></section>''')

    # 2. meses procesados
    filas = []
    for x in meses:
        est, txt = estado_etiquetas(x)
        intentos = len(x["est"].get("intentos", []))
        filas.append([mes_txt(x["mes"]), "completado" + (" (recuperado)" if x["est"].get("recuperado") else ""),
                      str(intentos), ("⚠ con alertas" if x["rep"].get("estado_calidad") == "con_alertas" else "sin alertas"),
                      n0(x["rep"]["validacion"]["clientes"]), txt])
    S.append(f'<section><h2>2. Meses procesados</h2>{tabla(["Mes", "Estado", "Intentos", "Calidad de datos", "Clientes", "Etiquetas"], filas)}</section>')

    # 3. tiempos
    segs_nombres = [n for n, _ in etapas(meses[0])] if meses else []
    colores = ["s1", "s2", "s3", "s4", "s5"]
    segs = [(n, colores[i], [etapas(x)[i][1] for x in meses]) for i, n in enumerate(segs_nombres)]
    filas = []
    for x in meses:
        t = total_mes(x)
        marca = ("—" if t is None else "dentro del margen" if t <= MARGEN_S else
                 "⚠ sobre el margen interno" if t <= LIMITE_S else "⚠ sobre el límite")
        if x["est"].get("recuperado"):
            marca += " (recuperado: tiempo del intento que publicó, hasta la publicación)"
        tf = x["est"].get("tiempos_finales", {})
        filas.append([mes_txt(x["mes"]), *[nd(v) for _, v in etapas(x)], f"<b>{nd(t)}</b>", marca,
                      nd(tf.get("reporte_html_s"), 2) if tf.get("reporte_html_s") is not None else "—"])
    S.append(f'''<section><h2>3. Tiempo por mes y por etapa</h2>
<p>Segundos desde la copia del archivo de entrada hasta la salida publicada y el reporte regenerado (reloj del proceso mensual). El arranque del intérprete se mide aparte, desde afuera, en el ensayo secuencial.</p>
{svg_barras_apiladas(ms, segs, [(MARGEN_S, f"margen interno {MARGEN_S} s"), (LIMITE_S, f"límite {LIMITE_S} s")], "Tiempo por etapa")}
{datos("Tabla de tiempos (s)", tabla(["Mes", *segs_nombres, "Total", "Respecto de los límites", "Reporte HTML"], filas, "num"))}</section>''')

    # 4. clientes e historia
    filas = []
    for x in meses:
        f, v = x["rep"].get("features", {}), x["rep"].get("verificacion_features", {}).get("lags", {})
        n = x["rep"]["validacion"]["clientes"]
        filas.append([mes_txt(x["mes"]), n0(n), n0(f.get("clientes_sin_historia")), pct(f.get("clientes_sin_historia", 0) / n, 2),
                      n0(f.get("con_lag1")), n0(f.get("con_lag2")), n0(v.get("clientes_con_algun_lag_distinto_del_calendario")),
                      f'{len(x["rep"]["validacion"].get("historia_meses", []))} meses ({mes_txt(x["rep"]["validacion"]["historia_meses"][0])} a {mes_txt(x["rep"]["validacion"]["historia_meses"][-1])})'
                      if x["rep"]["validacion"].get("historia_meses") else "—"])
    S.append(f'''<section><h2>4. Clientes e historia disponible</h2>
{svg_lineas(ms, [("Clientes nuevos", "s1", [x["rep"].get("features", {}).get("clientes_sin_historia") for x in meses])], "Clientes nuevos por mes (sin observación previa)", fmt=n0)}
{tabla(["Mes", "Clientes", "Nuevos", "% nuevos", "Con lag1", "Con lag2", "Lag por fila ≠ calendario", "Historia leída"], filas, "num")}
<p class="nota">Un cliente nuevo no tiene observaciones previas: sus lags y deltas quedan vacíos. «Lag por fila ≠ calendario»: clientes a los que les falta algún mes intermedio; los lags usan la observación previa, como en el entrenamiento.</p></section>''')

    # 5. calidad de datos
    filas = []
    for x in meses:
        cat_c = x["rep"].get("categorias_columnas", {})
        det = detectadas(x)
        fal = x["rep"].get("faltantes", {})
        ce = fal.get("ceros")
        r = reglas_calidad(x)
        filas.append([mes_txt(x["mes"]), n0(len(cat_c.get("observados_en_cero", []))),
                      pend("no evaluada") if det is None else n0(len(det)), n0(len(cat_c.get("nula_100", []))),
                      n0(len(cat_c.get("constante_no_nula", []))), n0(r.get("cambio_tasa_nulos", 0)),
                      n0(fal.get("celdas")), n0(fal.get("columnas_con_faltantes")),
                      pct(ce["celdas"] / ce["celdas_observadas"], 1) if ce else pend("no registrado")])
    obs = [x["rep"].get("faltantes", {}).get("ceros") for x in meses]
    serie_ceros = [(c["celdas"] / c["celdas_observadas"] * 100 if c else None) for c in obs]
    serie_falt = [x["rep"].get("faltantes", {}).get("celdas", 0) / (x["rep"]["validacion"]["clientes"] * max(1, len(cfg.get("esquema_crudo", [])) - 2)) * 100
                  for x in meses]
    S.append(f'''<section><h2>5. Calidad de datos: columnas anómalas, ceros y faltantes</h2>
{seccion_alertas(meses)}
{svg_lineas(ms, [("% de celdas en 0, entre las observadas", "s1", serie_ceros), ("% de celdas faltantes", "s2", serie_falt)], "Evolución de ceros y faltantes (% de las celdas de las 152 columnas)", fmt=lambda v: nd(v, 1), unidad=" %", cortos=["en 0", "faltantes"])}
{tabla(["Mes", "Columnas con todos los observados en 0", "Marcadas por cero_anomalo", "100 % nulas", "Constantes no nulas", "Cambio de tasa de nulos", "Celdas faltantes", "Columnas con faltantes", "% de celdas en 0"], filas, "num")}
<p class="nota">Las alertas no cambian el dato: el pipeline advierte y sigue. «no evaluada» / «no registrado»: el mes se procesó antes de que el pipeline registrara ese dato.</p></section>''')

    # 6. scores
    def q(x, rol, k):
        e = x["estr"].get(rol)
        return None if not e else e.get("distribucion", {}).get("cuantiles", {}).get(k)
    series_p50 = [(NOMBRE_ROL[r] + " · mediana", SERIE[r], [q(x, r, "0.5") for x in meses]) for r in (REC, ALT)]
    series_p99 = [(NOMBRE_ROL[r] + " · percentil 99", SERIE[r], [q(x, r, "0.99") for x in meses]) for r in (REC, ALT)]
    filas = []
    for i, x in enumerate(meses):
        for r in (REC, ALT):
            e = x["estr"].get(r)
            if not e:
                continue
            dd = e.get("distribucion", {})
            cq = dd.get("cuantiles", {})
            prev = (meses[i - 1]["estr"].get(r) or {}).get("distribucion", {}).get("cuantiles", {}) if i else {}
            cambio = (nd(cq["0.5"] / prev["0.5"], 2) + "×") if cq.get("0.5") and prev.get("0.5") else "—"
            filas.append([mes_txt(x["mes"]), NOMBRE_ROL[r], nd(dd.get("media"), 4), nd(cq.get("0.5"), 5), cambio,
                          nd(cq.get("0.9"), 4), nd(cq.get("0.99"), 3), n0(dd.get("mayor_0_5")),
                          n0(dd.get("exactamente_0", 0) + dd.get("exactamente_1", 0))])
    fmt_s = lambda v: nd(v, 4) if v < 0.01 else nd(v, 3)  # noqa: E731
    S.append(f'''<section><h2>6. Distribución de scores</h2>
<p><b>Qué estima cada score.</b> Recomendación: {escape(SIGNIFICADO[REC])}. Alternativa: {escape(SIGNIFICADO[ALT])}. No son comparables entre sí en nivel: estiman eventos distintos.</p>
<div class="dos">{svg_lineas(ms, series_p50, "Mediana del score", fmt=fmt_s, log=True, cortos=["binario", "multiclase"])}{svg_lineas(ms, series_p99, "Percentil 99 del score", fmt=fmt_s, log=True, cortos=["binario", "multiclase"])}</div>
<p class="nota">Escala logarítmica. «Cambio de la mediana»: cociente contra el mes anterior.</p>
{datos("Tabla de distribución", tabla(["Mes", "Estrategia", "Media", "Mediana", "Cambio de la mediana", "Percentil 90", "Percentil 99", "Mayores a 0,5", "Exactamente 0 o 1"], filas, "num"))}</section>''')

    # 7. envíos y coincidencia
    filas = []
    for x in meses:
        c = x["rep"].get("coincidencia", {})
        er, ea = x["estr"].get(REC, {}), x["estr"].get(ALT, {})
        filas.append([mes_txt(x["mes"]), n0(er.get("envios")), nd(er.get("probabilidad_minima_enviada"), 3), n0(ea.get("envios")),
                      nd(ea.get("probabilidad_minima_enviada"), 3), n0(c.get("interseccion")), n0(c.get("solo_recomendacion")),
                      n0(c.get("solo_alternativa")), nd(c.get("jaccard"), 3), nd(c.get("correlacion_de_rangos"), 3)])
    S.append(f'''<section><h2>7. Envíos y coincidencia entre estrategias</h2>
{svg_lineas(ms, [("Jaccard", "s1", [x["rep"].get("coincidencia", {}).get("jaccard") for x in meses])], "Coincidencia de clientes enviados entre estrategias (Jaccard)", fmt=lambda v: nd(v, 2), ymin=0)}
{tabla(["Mes", "Envíos recomendación", "Prob. mínima enviada", "Envíos alternativa", "Prob. mínima enviada", "En ambas", "Sólo recomendación", "Sólo alternativa", "Jaccard", "Correlación de rangos"], filas, "num")}
<p class="nota">La cantidad de envíos es una fracción fija de los clientes de cada mes. Jaccard = enviados por ambas / enviados por alguna.</p></section>''')

    # 8. ganancia y etiquetas
    filas = []
    for x in meses:
        est, txt = estado_etiquetas(x)
        r = x["retro"] or {}
        por = {e["rol"]: e for e in r.get("estrategias", [])}
        cl = r.get("clases", {})
        for rol in (REC, ALT):
            e = por.get(rol, {})
            if est == "completa":
                filas.append([mes_txt(x["mes"]), NOMBRE_ROL[rol], txt, n0(cl.get("BAJA+2")), n0(e.get("envios")),
                              n0(e.get("baja2_enviados")), f"<b>{mill(e.get('ganancia'))}</b>", nd(e.get("auc_baja2"), 4),
                              f"{mill(e.get('ganancia_maxima_ex_post'))} ({n0(e.get('envios_ganancia_maxima_ex_post'))} envíos)"])
            elif est == "parcial":
                filas.append([mes_txt(x["mes"]), NOMBRE_ROL[rol], txt,
                              pend(f"provisional: {n0(r.get('provisional', {}).get('ausentes_en_t1'))} ausentes en t+1"),
                              n0(x["estr"].get(rol, {}).get("envios")),
                              pend(f"{n0(e.get('provisional_ausentes_en_t1_enviados'))} enviados ausentes en t+1"),
                              pend(), pend(), pend()])
            else:
                filas.append([mes_txt(x["mes"]), NOMBRE_ROL[rol], txt, pend(), n0(x["estr"].get(rol, {}).get("envios")),
                              pend(), pend(), pend(), pend()])
    serie_g = [(NOMBRE_ROL[rol], SERIE[rol],
                [next((e["ganancia"] / 1e6 for e in (x["retro"] or {}).get("estrategias", []) if e["rol"] == rol and "ganancia" in e), None)
                 for x in meses]) for rol in (REC, ALT)]
    curvas = "".join(svg_curvas(x) for x in completas)
    S.append(f'''<section><h2>8. Etiquetas y ganancia</h2>
<p>La etiqueta del mes <i>t</i> se reconstruye con la presencia de cada cliente en <i>t</i>+1 y <i>t</i>+2 (regla versión 2). Hasta recibir esos dos meses las métricas quedan <span class="pend">pendientes</span>: no son cero. Con sólo <i>t</i>+1, la información es provisional y no se calcula ganancia. Estas métricas son de monitoreo: no cambian modelos, cortes ni salidas.</p>
{svg_lineas(ms, serie_g, "Ganancia por mes (millones de pesos)", fmt=lambda v: nd(v, 1), unidad=" M", cortos=["binario", "multiclase"])}
<p class="nota">Los meses sin punto tienen la ganancia pendiente de etiquetas.</p>
{tabla(["Mes", "Estrategia", "Etiquetas", "BAJA+2 del mes", "Envíos", "BAJA+2 enviados", "Ganancia", "AUC BAJA+2", "Máximo ex post (referencia)"], filas, "num")}
<h3>Curvas de ganancia (meses con etiquetas completas)</h3>
{leyenda([(NOMBRE_ROL[REC], SERIE[REC]), (NOMBRE_ROL[ALT], SERIE[ALT])]) if curvas else ""}
<div class="curvas">{curvas or pend("todavía no hay meses con etiquetas completas")}</div>
<p class="nota">El máximo ex post usa la etiqueta ya conocida: sirve de referencia, no para decidir el corte.</p></section>''')

    # 9. importes y definiciones
    S.append(f'''<section><h2>9. Importes y definiciones</h2>
<ul>
<li><b>Ganancia</b> = {n0(PREMIO_BRUTO)} × BAJA+2 enviados − {n0(COSTO_ENVIO)} × envíos (pesos). Cada BAJA+2 enviado aporta {n0(PREMIO_BRUTO - COSTO_ENVIO)} netos y cada otro envío cuesta {n0(COSTO_ENVIO)}.</li>
<li><b>Importes:</b> son los de la competencia 01. <span class="pend">Su confirmación para la competencia 02 está pendiente</span> (docs/GANANCIA.md); si cambian, cambian las ganancias informadas, no los scores.</li>
<li><b>Recomendación (salida oficial):</b> {escape(SIGNIFICADO[REC])}.</li>
<li><b>Alternativa:</b> {escape(SIGNIFICADO[ALT])}.</li>
<li><b>Límite de la consigna:</b> {LIMITE_S} s por mes. <b>Margen interno:</b> {MARGEN_S} s por mes, para absorber una máquina más lenta.</li>
</ul>
<p class="nota">Fuentes: <code>entorno.json</code>, <code>registro/meses/</code>, <code>diagnosticos/&lt;mes&gt;/reporte.json</code> y <code>registro/retrospectiva/</code> de la ejecución. Este archivo se regenera completo con cada mes publicado o recuperado.</p></section>''')

    meses_attr = ",".join(str(m) for m in ms)
    return f'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Seguimiento del pipeline</title>
<style>{CSS}</style></head>
<body data-meses="{meses_attr}"><main>
<header><h1>Seguimiento del pipeline mensual · competencia 02</h1>
<p class="sub">Ejecución <code>{escape(cfg.get("nombre", d["raiz"].name))}</code> · catálogo {escape(cat.get("nombre", "—"))} · generado {gen}</p></header>
{"".join(S)}
</main></body></html>
'''


CSS = """
:root{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;
--axis:#c3c2b7;--ring:rgba(11,11,11,.10);--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--s5:#e87ba4;
--warn-bg:#fff6e0;--warn-ring:#fab219}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;
--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);--s1:#3987e5;
--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--warn-bg:#2a2311;--warn-ring:#fab219}}
:root[data-theme="dark"]{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;
--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;
--warn-bg:#2a2311;--warn-ring:#fab219}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1120px;margin:0 auto;padding:24px 16px 48px;overflow-x:hidden}
@media (max-width:600px){section{padding:12px}h1{font-size:1.25rem}}
h1{font-size:1.5rem;margin:0 0 4px}h2{font-size:1.15rem;margin:0 0 10px}h3{font-size:1rem;margin:14px 0 6px}
.sub,.nota{color:var(--ink2)}.nota{font-size:.88rem}
section{min-width:0;overflow-wrap:anywhere;background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:18px;margin:16px 0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;background:none;border:0;padding:0}
.tile{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:14px}
.tile span{display:block;color:var(--ink2);font-size:.85rem}.tile b{display:block;font-size:1.7rem;font-variant-numeric:tabular-nums}
.tile small{color:var(--ink2)}
.tabla{overflow-x:auto;margin:8px 0}
table{border-collapse:collapse;width:100%;min-width:640px;font-size:.88rem;overflow-wrap:normal}
th,td{padding:6px 8px;border-bottom:1px solid var(--grid);text-align:left;vertical-align:top}
th{color:var(--ink2);font-weight:600}
td:first-child{white-space:nowrap}.num td{font-variant-numeric:tabular-nums}.num td:not(:first-child){text-align:right}
.num td:nth-child(2):not(:only-child){text-align:left}
code{font-size:.85em;color:var(--ink2);overflow-wrap:anywhere}
.pend{color:var(--muted);font-style:italic}
svg{width:100%;height:auto;display:block;margin:6px 0}
svg text{fill:var(--ink2);font:11px system-ui,-apple-system,"Segoe UI",sans-serif}
svg .valor{fill:var(--ink);font-weight:600}svg .etq{fill:var(--ink)}
svg .grid{stroke:var(--grid);stroke-width:1}svg .base{stroke:var(--axis);stroke-width:1}
svg .ref{stroke:var(--ink2);stroke-width:1.5;stroke-dasharray:6 4}svg .ref-t{fill:var(--ink);font-weight:600}
svg .seg{stroke:var(--surface);stroke-width:2}svg .punto{stroke:var(--surface);stroke-width:2}
.leyenda{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:.85rem;color:var(--ink2);margin-top:6px}
.leyenda i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.dos{display:grid;grid-template-columns:1fr;gap:12px}
.curvas{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
figure{margin:0}figcaption{font-size:.85rem;color:var(--ink2)}
.alerta{background:var(--warn-bg);border:1px solid var(--warn-ring);border-radius:8px;padding:10px 14px;margin:10px 0}
.alerta h3{margin:2px 0 6px}.alerta ul{margin:0;padding-left:20px}
table code{overflow-wrap:normal;white-space:nowrap}
details{margin:8px 0}summary{cursor:pointer;color:var(--ink2)}
"""


def generar(raiz: Path) -> Path:
    raiz = Path(raiz)
    destino = raiz / "registro" / ARCHIVO
    texto = generar_html(cargar(raiz))
    tmp = destino.with_name(destino.name + f".tmp-{os.getpid()}")
    tmp.write_text(texto, encoding="utf-8", newline="\n")
    os.replace(tmp, destino)
    return destino


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Genera (y opcionalmente abre) el reporte HTML de seguimiento.")
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
