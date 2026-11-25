"""Definición única del target (clase_ternaria) por presencia de clientes: entrenamiento, evaluación y retrospectiva.

Regla (versión 2), para un cliente presente en el mes t:
  presente en t+2                   -> CONTINUA  (aunque falte en t+1: el cliente "vuelve")
  presente en t+1 y ausente en t+2  -> BAJA+2
  ausente en t+1 y ausente en t+2   -> BAJA+1
La etiqueta definitiva necesita las listas de clientes de t+1 y de t+2: sin t+2 no hay clase (tampoco BAJA+1).

Fuente: reproduce sin diferencias las etiquetas oficiales de competencia 01 (983.061 filas;
experimento_sampling/03b_validar_target_competencia01.py, "regla_alternativa_compatible_con_oficial").
La versión 1 (experimento_sampling/03, igual al código docente en R) etiquetaba BAJA+1 al cliente que vuelve en t+2;
el archivo oficial lo etiqueta CONTINUA (15 de 15). El patrón ausente t+1 / presente t+2 / ausente t+3 no aparece en
esa verificación: la regla lo resuelve igual (CONTINUA).

Dos implementaciones independientes que se contrastan entre sí:
  - etiquetar(): numpy, sobre la presencia en t+1 y t+2 (la usa pipeline_competencia02/retrospectiva.py);
  - sql_etiquetas(): DuckDB, con autojoin por período (la usa experimentos/tc01_target_2019.py).
"""
from __future__ import annotations

import numpy as np

VERSION = 2
REGLA = {"CONTINUA": "presente en t+2 (aunque falte en t+1)", "BAJA+2": "presente en t+1 y ausente en t+2",
         "BAJA+1": "ausente en t+1 y ausente en t+2", "horizonte": "la clase definitiva necesita t+1 y t+2",
         "verificacion": "igual a las etiquetas oficiales de competencia 01 (experimento_sampling/03b, 0 diferencias)"}
CLASES = ("CONTINUA", "BAJA+1", "BAJA+2")


def periodo(mes: int) -> int:
    return mes // 100 * 12 + mes % 100


def etiquetar(en1: np.ndarray, en2: np.ndarray) -> np.ndarray:
    """Clase con t+1 y t+2 observados. La presencia en t+2 manda."""
    return np.where(en2, "CONTINUA", np.where(en1, "BAJA+2", "BAJA+1"))


def sql_etiquetas(fuente: str, meses: list[int]) -> str:
    """SELECT numero_de_cliente, foto_mes, clase_ternaria de `meses`, desde una tabla/vista de presencia `fuente`
    con columnas numero_de_cliente y foto_mes. Quien llama comprueba que t+1 y t+2 estén en la fuente."""
    lista = ", ".join(str(int(m)) for m in meses)
    return f"""
        WITH p AS (SELECT DISTINCT numero_de_cliente, foto_mes, (foto_mes // 100) * 12 + foto_mes % 100 AS per
                   FROM {fuente})
        SELECT a.numero_de_cliente, a.foto_mes,
               CASE WHEN b2.numero_de_cliente IS NOT NULL THEN 'CONTINUA'
                    WHEN b1.numero_de_cliente IS NOT NULL THEN 'BAJA+2'
                    ELSE 'BAJA+1' END AS clase_ternaria
        FROM p a
        LEFT JOIN p b1 ON b1.numero_de_cliente = a.numero_de_cliente AND b1.per = a.per + 1
        LEFT JOIN p b2 ON b2.numero_de_cliente = a.numero_de_cliente AND b2.per = a.per + 2
        WHERE a.foto_mes IN ({lista})
        ORDER BY a.foto_mes, a.numero_de_cliente"""
