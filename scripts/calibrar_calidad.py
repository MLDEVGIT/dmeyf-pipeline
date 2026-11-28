"""Calibra la detección de variables rotas (pipeline_competencia02/calidad.py) con la historia de 2019.

Mide la proporción de ceros y de faltantes de cada variable en cada mes de 201901–201912, corre la detección mes a mes
(cada mes contra los anteriores) con los umbrales de la política y con una grilla alrededor, y guarda todo en
resultados/c01_calidad_2019.json. Las proporciones son agregados por mes (sin datos de clientes): quedan versionadas y
la prueba de la detección corre sobre ellas sin el dataset.

Uso: python scripts/calibrar_calidad.py [--salida resultados/c01_calidad_2019.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import duckdb  # noqa: E402

from pipeline_competencia02 import calidad  # noqa: E402
from pipeline_competencia02.config import RUTAS  # noqa: E402

GRILLA = [{"casi_todo": ct, "mediana_max": 0.95, "salto": s} for ct in (0.99, 0.999) for s in (0.2, 0.3, 0.4, 0.5)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--salida", type=Path, default=RAIZ / "resultados" / "c01_calidad_2019.json")
    a = ap.parse_args(argv)

    con = duckdb.connect()
    fuente = f"read_parquet('{RUTAS.historico_2019.as_posix()}')"
    columnas = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {fuente}").fetchall()]
    props = calidad.proporciones_por_mes(con, fuente, columnas)
    assert min(props) >= 201901 and max(props) <= 201912, "la calibración usa solo 2019"

    u = calidad.umbrales()
    vigente = calidad.detectar_historia(props, u)
    grilla = []
    for g in GRILLA:
        det = calidad.detectar_historia(props, g)
        grilla.append({**g, "rotas_por_mes": {m: len(v) for m, v in det.items()}})

    casi_cero = sorted(v for v in props[min(props)]
                       if all((props[m][v]["ceros"] or 0) > u["casi_todo"] - 0.05 for m in props))
    res = {
        "experimento": "c01_calidad_2019",
        "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fuente": "historia de 2019 (RUTAS.historico_2019), todas las filas de cada mes",
        "regla": calidad.__doc__.split("\n\n")[2].strip(),
        "umbrales_vigentes": u,
        "rotas_por_mes": vigente,
        "variables_con_mas_de_99_4_pct_de_ceros_todo_el_anio": casi_cero,
        "grilla": grilla,
        "proporciones": {str(m): {v: [None if p["ceros"] is None else round(p["ceros"], 6), round(p["nulos"], 6)] for v, p in pm.items()}
                         for m, pm in props.items()},
        "formato_proporciones": "mes -> variable -> [proporción de ceros sobre los observados (null sin observados), proporción de faltantes sobre todas las filas]",
    }
    a.salida.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for m, v in vigente.items():
        print(m, len(v), " ".join(v))
    print("grilla (rotas por mes):")
    for g in grilla:
        print(f"  casi_todo={g['casi_todo']} salto={g['salto']}:", list(g["rotas_por_mes"].values()))
    print("guardado en", a.salida.relative_to(RAIZ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
