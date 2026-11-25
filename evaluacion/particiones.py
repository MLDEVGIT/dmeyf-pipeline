"""Particiones temporales y disponibilidad del target (docs/PLAN_PRUEBAS.md § Particiones).

clase_ternaria del mes t en el target de 2019 que lee este módulo (experimento_sampling/03, "versión 1"):
  ausente en t+1                 -> BAJA+1   (necesita la lista de clientes de t+1)
  presente en t+1, ausente en t+2 -> BAJA+2   (necesita t+1 y t+2)
  presente en t+1 y en t+2       -> CONTINUA (necesita t+1 y t+2)
Con datos de 201901–201912: 201901–201910 completos; 201911 solo BAJA+1; 201912 sin etiqueta.

La regla vigente es la "versión 2" (evaluacion/target.py), que reproduce las etiquetas oficiales de competencia 01:
presente en t+2 -> CONTINUA aunque falte en t+1. El target de 2019 con esa regla es RUTAS.target_2019_v2
(experimentos/tc01_target_2019.py; sólo 201903–201906 y 201908–201909) y lo usan TC01 y el catálogo activo.
RUTAS.target_2019 (versión 1) se conserva para reproducir E01/E02. Difieren sólo en los clientes que vuelven en t+2
(5 filas de 201903–201906 y 12 de 201908); BAJA+2 es idéntico. leer_target recibe la ruta: el control de meses es
el mismo para las dos versiones. Con la versión 2, 201911 no tendría ninguna clase definitiva.

Las etiquetas se leen sólo para los meses que permite cada experimento: `leer_target`
rechaza cualquier otro mes. Octubre (201910) queda reservado para la evaluación final.
"""
from __future__ import annotations

ENTRENAMIENTO = (201903, 201904, 201905, 201906)
DESARROLLO = (201908, 201909)             # desarrollo y elección de cortes
EVALUACION_FINAL = (201910,)              # una sola vez, con el protocolo congelado
SIN_ETIQUETA_COMPLETA = (201911, 201912)  # pendiente de aclaración (CONSIGNA § Contradicción)

PERMITIDOS_DESARROLLO = frozenset(ENTRENAMIENTO + DESARROLLO)


def leer_target(con, ruta: str, meses, permitidos=PERMITIDOS_DESARROLLO):
    """(numero_de_cliente, foto_mes, clase_ternaria) de `meses`, sólo si todos están permitidos."""
    meses = tuple(int(m) for m in meses)
    fuera = sorted(set(meses) - set(permitidos))
    if fuera:
        raise PermissionError(f"meses de target no permitidos en esta etapa: {fuera}")
    lista = ", ".join(str(m) for m in meses)
    return con.execute(
        f"SELECT numero_de_cliente, foto_mes, clase_ternaria FROM read_parquet('{ruta}') "
        f"WHERE foto_mes IN ({lista})")
