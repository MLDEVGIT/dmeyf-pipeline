"""Crea un entorno aislado para el pipeline mensual.

Un entorno es un directorio nuevo bajo la ruta `entornos` de la configuración
con su propia copia de la historia y del modelo. La ejecución mensual sólo lee
dentro de él, así que nunca toca el histórico original, los resultados de 05
ni meses posteriores a los copiados. Nunca se reutiliza: para repetir una
prueba se crea un entorno nuevo.

Estructura:
  entorno.json            configuración, esquema crudo, procedencia y hashes
  historia/foto_mes=AAAAMM.parquet   un archivo por mes disponible
  modelo/                 modelo.txt, predictores.json, configuracion.json
  entradas/AAAAMM/<ejecucion>/   CSV crudo recibido (copia por intento)
  output/churn_AAAAMM.csv        salida OFICIAL (estrategia principal)
  diagnosticos/AAAAMM/           features, scores, decisiones de todas las estrategias y reporte
  diagnosticos/AAAAMM.fallido-<ejecucion>/   diagnóstico de un intento fallido
  registro/               logs, ejecuciones.jsonl, reporte_acumulado.csv, meses/
  tmp/<ejecucion>/        preparación de un intento; se publica sólo al completar

Uso:
  python -m pipeline_competencia02.entorno --nombre N --hasta 201907 --modelo-desde <corrida de 05>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

import duckdb

from .config import RUTAS, mostrar

HISTORICO = RUTAS.historico_2019
ENTORNOS = RUTAS.entornos
ARTEFACTOS_MODELO = ["modelo.txt", "predictores.json", "configuracion.json"]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def crear(nombre: str, hasta: int, modelo_desde: Path) -> Path:
    env = ENTORNOS / nombre
    if env.exists():
        raise FileExistsError(f"{env} ya existe; para repetir una prueba usá un entorno nuevo")
    modelo_desde = Path(modelo_desde).resolve()
    faltan = [a for a in ARTEFACTOS_MODELO if not (modelo_desde / a).exists()]
    if faltan:
        raise FileNotFoundError(f"faltan artefactos del modelo en {modelo_desde}: {faltan}")
    env.mkdir(parents=True)
    for d in ["historia", "modelo", "entradas", "output", "diagnosticos", "registro/meses", "tmp"]:
        (env / d).mkdir(parents=True)

    con = duckdb.connect()
    con.execute("SET threads = 4")
    con.execute("SET memory_limit = '1GB'")
    origen = HISTORICO.as_posix()
    esquema = [[c, t] for c, t, *_ in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{origen}')").fetchall()]
    meses = [m for (m,) in con.execute(f"SELECT DISTINCT foto_mes FROM read_parquet('{origen}') "
                                       f"WHERE foto_mes <= {int(hasta)} ORDER BY 1").fetchall()]
    historia = {}
    for m in meses:
        dst = env / "historia" / f"foto_mes={m}.parquet"
        con.execute(f"COPY (SELECT * FROM read_parquet('{origen}') WHERE foto_mes = {m}) TO '{dst.as_posix()}' "
                    f"(FORMAT parquet, COMPRESSION zstd)")
        n_dst, mn, mx = con.execute(f"SELECT count(*), min(foto_mes), max(foto_mes) "
                                    f"FROM read_parquet('{dst.as_posix()}')").fetchone()
        n_src = con.execute(f"SELECT count(*) FROM read_parquet('{origen}') WHERE foto_mes = {m}").fetchone()[0]
        if not (n_dst == n_src and mn == mx == m):
            raise RuntimeError(f"copia de historia {m} inconsistente")
        historia[str(m)] = {"filas": int(n_dst), "sha256": sha256(dst)}
    con.close()

    modelo = {}
    for a in ARTEFACTOS_MODELO:
        shutil.copy2(modelo_desde / a, env / "modelo" / a)
        modelo[a] = {"sha256": sha256(env / "modelo" / a), "sha256_origen": sha256(modelo_desde / a)}
        if modelo[a]["sha256"] != modelo[a]["sha256_origen"]:
            raise RuntimeError(f"copia de {a} inconsistente")

    cfg = {
        "nombre": nombre, "creado": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "historia": {"origen": mostrar(HISTORICO), "hasta": int(hasta), "meses": historia},
        "modelo": {"origen": mostrar(modelo_desde), "artefactos": modelo},
        "esquema_crudo": esquema,
        "nota": "entorno aislado: la ejecución mensual sólo lee dentro de este directorio",
    }
    (env / "entorno.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return env


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Crea un entorno aislado para el pipeline mensual.")
    ap.add_argument("--nombre", required=True)
    ap.add_argument("--hasta", type=int, required=True, help="último foto_mes de historia disponible")
    ap.add_argument("--modelo-desde", type=Path, required=True, help="carpeta de una corrida de 05")
    a = ap.parse_args(argv)
    env = crear(a.nombre, a.hasta, a.modelo_desde)
    print(f"Entorno creado: {mostrar(env)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
