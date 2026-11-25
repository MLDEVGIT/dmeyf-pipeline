"""Métricas retrospectivas de los meses ya publicados, a medida que llegan los meses que las etiquetan.

Regla de target (versión 2), para un cliente presente en el mes t:
  presente en t+2                   -> CONTINUA  (aunque falte en t+1: el cliente "vuelve")
  presente en t+1 y ausente en t+2  -> BAJA+2
  ausente en t+1 y ausente en t+2   -> BAJA+1
Es la regla que reproduce SIN discrepancias las etiquetas oficiales de competencia 01
(experimento_sampling/03b_validar_target_competencia01.py, "regla_alternativa_compatible_con_oficial": 0 diferencias
en 983.061 filas). La versión 1 de este módulo copiaba experimento_sampling/03 (lead sobre la grilla, igual al código
docente en R), que etiqueta BAJA+1 al cliente ausente en t+1 que vuelve en t+2; el archivo oficial lo etiqueta CONTINUA
(15 de 15 casos en competencia 01). El patrón ausente t+1 / presente t+2 / ausente t+3 no aparece en esa verificación:
se le aplica la misma regla (CONTINUA) sin verificación directa.

La clase depende de t+2 en TODOS los casos (también BAJA+1: un ausente en t+1 puede volver en t+2). Por eso:
  completa  t+1 y t+2 en historia/  -> clases definitivas; ganancia, aciertos y AUC de BAJA+2 por estrategia
  parcial   sólo t+1 en historia/   -> NINGUNA clase definitiva. Se informa, marcado como provisional, cuántos
                                       clientes faltan en t+1 (BAJA+1 provisional: pasan a CONTINUA si vuelven en t+2)
                                       y cuántos de ellos se enviaron. El archivo oficial de competencia 01 sí etiquetó
                                       BAJA+1 en su anteúltimo mes sin esperar t+2; acá no se presenta como definitivo.
  pendiente ni t+1                  -> nada

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

REGLA = {"CONTINUA": "presente en t+2 (aunque falte en t+1)", "BAJA+2": "presente en t+1 y ausente en t+2",
         "BAJA+1": "ausente en t+1 y ausente en t+2",
         "verificacion": "igual a las etiquetas oficiales de competencia 01 (experimento_sampling/03b, 0 diferencias)",
         "fuente": "presencia de numero_de_cliente en historia/foto_mes=<t+1|t+2>.parquet (meses recibidos)"}
VERSION = 2


def siguiente(m: int) -> int:
    a, mm = divmod(m, 100)
    return a * 100 + mm + 1 if mm < 12 else (a + 1) * 100 + 1


def disponibilidad(historia: Path, mes: int) -> dict:
    m1, m2 = siguiente(mes), siguiente(siguiente(mes))
    h1, h2 = (historia / f"foto_mes={m1}.parquet").exists(), (historia / f"foto_mes={m2}.parquet").exists()
    estado = "completa" if h1 and h2 else "parcial" if h1 else "pendiente"
    falta = [str(m) for m, h in ((m1, h1), (m2, h2)) if not h]
    return {"estado": estado, "requiere": [m1, m2], "falta": falta}


def etiquetar(en1: np.ndarray, en2: np.ndarray) -> np.ndarray:
    """Clase con t+1 y t+2 observados (regla versión 2). La presencia en t+2 manda."""
    return np.where(en2, "CONTINUA", np.where(en1, "BAJA+2", "BAJA+1"))


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
    if en2 is not None:
        clase = etiquetar(en1, en2)
        baja1, baja2 = clase == "BAJA+1", clase == "BAJA+2"
        out["clases"] = {"clientes": len(cli), "BAJA+1": int(baja1.sum()), "BAJA+2": int(baja2.sum()),
                         "CONTINUA": int((clase == "CONTINUA").sum()),
                         "ausentes_en_t1_que_vuelven_en_t2": int((~en1 & en2).sum()),
                         "definitivas": True}
    else:
        baja1 = baja2 = None
        out["clases"] = {"clientes": len(cli), "definitivas": False}
        out["provisional"] = {
            "ausentes_en_t1": int((~en1).sum()),
            "nota": "BAJA+1 provisional: pasan a CONTINUA si vuelven en t+2; los presentes en t+1 pueden ser "
                    "BAJA+2 o CONTINUA. Ninguna clase es definitiva hasta recibir t+2."}
    out["estrategias"] = []
    for e in estrategias:
        p = dec[f"probabilidad_{e['id']}"].to_numpy(np.float64)
        env = dec[f"enviar_{e['id']}"].to_numpy() == 1
        k = int(env.sum())
        r = {"id": e["id"], "rol": e["rol"], "score": e["score_corto"], "envios": k}
        if en2 is None:
            r["provisional_ausentes_en_t1_enviados"] = int((env & ~en1).sum())
        else:
            r["baja1_enviados"] = int((env & baja1).sum())
            tp = int((env & baja2).sum())
            g = curva(p, baja2, cli)
            kmax = int(np.argmax(g)) + 1
            r.update({"baja2_enviados": tp, "precision_baja2": round(tp / k, 6) if k else None,
                      "recall_baja2": round(tp / out["clases"]["BAJA+2"], 6) if out["clases"]["BAJA+2"] else None,
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
