"""Ganancia de una política de envíos, curvas y elección del corte.

Fórmula (por mes):

    G(k) = PREMIO_BRUTO · TP(k) − COSTO_ENVIO · k

  k      = envíos (los k clientes de mayor score);
  TP(k)  = cuántos de esos k son BAJA+2 (BAJA+1 y CONTINUA no pagan).

Es idéntica a la forma que usa el material de la cátedra,
    +GANANCIA_NETA_ACIERTO por cada BAJA+2 enviado y −COSTO_ENVIO por cada otro envío,
porque GANANCIA_NETA_ACIERTO = PREMIO_BRUTO − COSTO_ENVIO: el acierto también paga su envío.
Umbral de equilibrio sobre una probabilidad calibrada de BAJA+2:
    p* = COSTO_ENVIO / PREMIO_BRUTO = 0,025 (1/40), el que usan los notebooks del curso.

Importes y fuente (ver docs/GANANCIA.md):
  - Material del curso (competencia 01): `ifelse(clase_ternaria == "BAJA+2", 1072500, -27500)`
    en arboles/z0201…z0333, ensembles/z420…z470 y monday/z701 (repo dmecoyfin/dmeyf2026).
  - Desglose 2,2 M de valor anual × 50 % de aceptación = 1,1 M bruto, menos 27.500 del estímulo:
    comentario de `comun/ganancia.py` del repo de sampling, copiado de un repo de la cátedra que no
    está disponible en esta máquina.
  - **Competencia 02: importes sin fuente propia (pendiente en CONSIGNA.md).** Se usan los de C01.
    La elección del corte por fracción solo depende de la razón COSTO_ENVIO / PREMIO_BRUTO: si C02
    cambia la escala pero no la razón, los cortes no cambian.
"""
from __future__ import annotations

import math

import numpy as np

PREMIO_BRUTO: int = 1_100_000
COSTO_ENVIO: int = 27_500
GANANCIA_NETA_ACIERTO: int = PREMIO_BRUTO - COSTO_ENVIO  # 1.072.500
UMBRAL_EQUILIBRIO: float = COSTO_ENVIO / PREMIO_BRUTO    # 0,025
VENTANA_SUAVIZADO: int = 501


def orden(score: np.ndarray, clientes: np.ndarray) -> np.ndarray:
    """Probabilidad descendente; a igual probabilidad, numero_de_cliente ascendente (igual que estrategias.py)."""
    return np.lexsort((np.asarray(clientes), -np.asarray(score, dtype="float64")))


def curva(score: np.ndarray, es_baja2: np.ndarray, clientes: np.ndarray) -> np.ndarray:
    """g[k-1] = G(k) para k = 1..n, en pesos."""
    tp = np.cumsum(np.asarray(es_baja2, dtype="int64")[orden(score, clientes)])
    k = np.arange(1, len(tp) + 1, dtype="int64")
    return PREMIO_BRUTO * tp - COSTO_ENVIO * k


def suavizar(g: np.ndarray, ventana: int = VENTANA_SUAVIZADO) -> np.ndarray:
    """Media móvil centrada; NaN donde la ventana no entra completa."""
    m = ventana // 2
    out = np.full(len(g), np.nan)
    c = np.concatenate([[0.0], np.cumsum(g, dtype="float64")])
    out[m:len(g) - m] = (c[ventana:] - c[:-ventana]) / ventana
    return out


def envios(fraccion: float, n: int) -> int:
    return int(math.ceil(fraccion * n))


def arrepentimiento(curvas_suav: dict, n: dict, fracciones: np.ndarray) -> dict:
    """Pérdida relativa al máximo de cada mes al cortar en cada fracción: 1 − Gs(k(f)) / max Gs."""
    tabla = {}
    for mes, gs in curvas_suav.items():
        mx = np.nanmax(gs)
        tabla[mes] = np.array([1 - gs[envios(f, n[mes]) - 1] / mx for f in fracciones])
    return tabla


def corte_minimax(curvas_suav: dict, n: dict, fracciones: np.ndarray) -> tuple[float, dict]:
    """Fracción con menor arrepentimiento máximo entre meses; empate: la menor fracción."""
    tabla = arrepentimiento(curvas_suav, n, fracciones)
    peor = np.max(np.vstack(list(tabla.values())), axis=0)
    i = int(np.nanargmin(peor))
    return float(fracciones[i]), {"peor_caso": peor, **tabla}
