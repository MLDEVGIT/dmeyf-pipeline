"""Métricas retrospectivas de los meses ya publicados, a medida que llegan los meses que las etiquetan.

Regla de target (la misma de evaluacion/particiones.py y experimento_sampling/03), para un cliente del mes t:
  ausente en t+1                    -> BAJA+1    (alcanza con la lista de clientes de t+1)
  presente en t+1 y ausente en t+2  -> BAJA+2    (necesita t+1 y t+2)
  presente en t+1 y en t+2          -> CONTINUA  (necesita t+1 y t+2)

Disponibilidad de la etiqueta de un mes completado t, según la historia de la ejecución:
  completa  t+1 y t+2 en historia/      -> ganancia, aciertos, AUC de BAJA+2 por estrategia
  parcial   sólo t+1 en historia/       -> sólo BAJA+1 (cantidad y cuántos se enviaron); ganancia pendiente
  pendiente ni t+1                      -> nada

Fuentes, todas dentro de la carpeta de ejecución:
  - clientes y decisiones de t: diagnosticos/<t>/decisiones_<t>.csv (publicado e íntegro);
  - presencia en t+1 y t+2: sólo la columna numero_de_cliente de historia/foto_mes=<t+k>.parquet, que existe
    únicamente si ese mes se recibió y se completó (o es parte de la historia inicial).
No lee ningún archivo de clase ni etiqueta provista: la etiqueta se reconstruye con la presencia.

Uso: monitoreo. Estas métricas NO cambian modelos, features, cortes ni la salida de ningún mes (CONSIGNA R1:
modelos y cortes se eligen sólo con 201901–201912). Se guardan en registro/retrospectiva/<t>.json, aparte de lo
publicado, y el reporte acumulado las incorpora. Se recalculan sólo cuando cambia la disponibilidad.

Ganancia: evaluacion.ganancia (G = 1.100.000 · BAJA+2 enviados − 27.500 · envíos). Importes de C01: los de C02
siguen sin fuente propia (docs/GANANCIA.md).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from evaluacion.ganancia import COSTO_ENVIO, PREMIO_BRUTO, curva

REGLA = {"BAJA+1": "ausente en t+1", "BAJA+2": "presente en t+1 y ausente en t+2",
         "CONTINUA": "presente en t+1 y en t+2",
         "fuente": "presencia de numero_de_cliente en historia/foto_mes=<t+1|t+2>.parquet (meses recibidos)"}
VERSION = 1


def siguiente(m: int) -> int:
    a, mm = divmod(m, 100)
    return a * 100 + mm + 1 if mm < 12 else (a + 1) * 100 + 1


def disponibilidad(historia: Path, mes: int) -> dict:
    m1, m2 = siguiente(mes), siguiente(siguiente(mes))
    h1, h2 = (historia / f"foto_mes={m1}.parquet").exists(), (historia / f"foto_mes={m2}.parquet").exists()
    estado = "completa" if h1 and h2 else "parcial" if h1 else "pendiente"
    falta = [str(m) for m, h in ((m1, h1), (m2, h2)) if not h]
    return {"estado": estado, "requiere": [m1, m2], "falta": falta}


def auc(score: np.ndarray, positivo: np.ndarray) -> float | None:
    """AUC por rangos (Mann-Whitney), con empates promediados."""
    n1 = int(positivo.sum())
    n0 = len(positivo) - n1
    if n1 == 0 or n0 == 0:
        return None
    r = pd.Series(score).rank(method="average").to_numpy()
    return float((r[positivo].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def presentes(con, archivo: Path) -> np.ndarray:
    return con.execute(f"SELECT numero_de_cliente FROM read_parquet('{archivo.as_posix()}')").fetchnumpy()[
        "numero_de_cliente"].astype(np.int64)


def calcular(raiz: Path, mes: int, estrategias: list[dict]) -> dict:
    """estrategias: [{'id', 'rol', 'score_corto'}] del reporte del mes, la recomendación primero."""
    disp = disponibilidad(raiz / "historia", mes)
    out = {"version": VERSION, "mes": mes, "regla": REGLA, "disponibilidad": disp,
           "uso": "monitoreo retrospectivo; no modifica modelos, cortes ni salidas (R1)"}
    if disp["estado"] == "pendiente":
        return out
    dec = pd.read_csv(raiz / "diagnosticos" / str(mes) / f"decisiones_{mes}.csv", float_precision="round_trip")
    cli = dec["numero_de_cliente"].to_numpy(np.int64)
    con = duckdb.connect()
    try:
        m1, m2 = disp["requiere"]
        en1 = np.isin(cli, presentes(con, raiz / "historia" / f"foto_mes={m1}.parquet"))
        en2 = (np.isin(cli, presentes(con, raiz / "historia" / f"foto_mes={m2}.parquet"))
               if disp["estado"] == "completa" else None)
    finally:
        con.close()
    baja1 = ~en1
    clases = {"clientes": len(cli), "BAJA+1": int(baja1.sum())}
    if en2 is not None:
        baja2 = en1 & ~en2
        clases.update({"BAJA+2": int(baja2.sum()), "CONTINUA": int((en1 & en2).sum()),
                       "ausentes_en_t1_que_vuelven_en_t2": int((~en1 & en2).sum())})
    out["clases"] = clases
    out["estrategias"] = []
    for e in estrategias:
        p = dec[f"probabilidad_{e['id']}"].to_numpy(np.float64)
        env = dec[f"enviar_{e['id']}"].to_numpy() == 1
        k = int(env.sum())
        r = {"id": e["id"], "rol": e["rol"], "score": e["score_corto"], "envios": k,
             "baja1_enviados": int((env & baja1).sum())}
        if en2 is not None:
            tp = int((env & baja2).sum())
            g = curva(p, baja2, cli)
            kmax = int(np.argmax(g)) + 1
            r.update({"baja2_enviados": tp, "precision_baja2": round(tp / k, 6) if k else None,
                      "recall_baja2": round(tp / clases["BAJA+2"], 6) if clases["BAJA+2"] else None,
                      "ganancia": int(PREMIO_BRUTO * tp - COSTO_ENVIO * k),
                      "auc_baja2": round(auc(p, baja2), 6) if auc(p, baja2) is not None else None,
                      "ganancia_maxima_ex_post": int(g[kmax - 1]), "envios_ganancia_maxima_ex_post": kmax,
                      "nota_ex_post": "máximo de la curva con la etiqueta ya conocida: referencia, no usable para decidir"})
        out["estrategias"].append(r)
    if en2 is not None and len(out["estrategias"]) == 2:
        a, b = out["estrategias"]
        out["diferencia_ganancia_recomendacion_menos_alternativa"] = a["ganancia"] - b["ganancia"]
    return out


def actualizar(raiz: Path, meses_completados: list[int]) -> dict:
    """Recalcula la retrospectiva de los meses cuya disponibilidad cambió. Devuelve {mes: estado}."""
    destino = raiz / "registro" / "retrospectiva"
    destino.mkdir(exist_ok=True)
    estados = {}
    for mes in sorted(meses_completados):
        archivo = destino / f"{mes}.json"
        disp = disponibilidad(raiz / "historia", mes)
        if archivo.exists():
            previo = json.loads(archivo.read_text(encoding="utf-8"))
            if previo.get("version") == VERSION and previo["disponibilidad"] == disp:
                estados[mes] = disp["estado"]
                continue
        rep = json.loads((raiz / "diagnosticos" / str(mes) / "reporte.json").read_text(encoding="utf-8"))
        estr = sorted(({k: x[k] for k in ("id", "rol", "score_corto")} for x in rep["estrategias"]),
                      key=lambda x: x["rol"] != "recomendacion_provisional")
        res = calcular(raiz, mes, estr)
        tmp = archivo.with_name(archivo.name + f".tmp-{os.getpid()}")
        tmp.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
        os.replace(tmp, archivo)
        estados[mes] = disp["estado"]
    return estados


def cargar(raiz: Path, mes: int) -> dict | None:
    p = raiz / "registro" / "retrospectiva" / f"{mes}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
