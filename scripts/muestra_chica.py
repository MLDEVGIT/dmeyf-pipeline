"""Muestra chica del dataset para correr las pruebas, el ensayo y la fábrica en una notebook con el mismo código.

Toma del crudo del curso (RUTAS.crudo, ordenado por foto_mes) las líneas de 201901–202003 de una fracción fija de
clientes, copiadas byte a byte (sin reescribir valores), y deja una carpeta de datos con la misma forma que la
real:

  <destino>/competencia_02/competencia_02_crudo.csv.gz   201901–202003, solo los clientes de la muestra
  <destino>/referencia_filas_por_mes.csv                 filas por mes de 2019 (como referencia/01_filas_por_mes.csv)
  <destino>/config.toml                                  rutas de la muestra
  <destino>/muestra.json                                 regla, conteos y sha256

Regla de la muestra: el cliente entra si (numero_de_cliente · 2654435761) mod 2³² cae en el primer `1/denominador`
del rango (hash multiplicativo de Knuth): es fija, no depende del orden del archivo y se puede explicar a mano. Un
cliente que entra, entra en todos sus meses, así la historia y los lags son los de verdad.

Uso:
  python scripts/muestra_chica.py --destino ~/datos/dmeyf-muestra [--denominador 20]
  DMEYF_CONFIG=~/datos/dmeyf-muestra/config.toml python entrenamiento/legado/02_convertir_parquet.py   # y el resto
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from pipeline_competencia02.config import RUTAS, mostrar  # noqa: E402

HASTA = 202003
KNUTH = 2654435761


def entra(cliente: int, denominador: int) -> bool:
    return (cliente * KNUTH) % 2**32 < 2**32 // denominador


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Muestra chica del crudo (201901–202003).")
    ap.add_argument("--destino", type=Path, required=True)
    ap.add_argument("--denominador", type=int, default=20, help="1 de cada N clientes (por defecto 20, 5 %%)")
    a = ap.parse_args(argv)
    destino = a.destino.expanduser().resolve()
    crudo = destino / "competencia_02" / "competencia_02_crudo.csv.gz"
    if crudo.exists():
        raise SystemExit(f"{crudo} ya existe; no se sobrescribe")
    crudo.parent.mkdir(parents=True)
    t0 = time.perf_counter()
    filas, clientes, ultimo = Counter(), {}, 0
    tmp = crudo.with_name(crudo.name + ".tmp")
    with gzip.open(RUTAS.crudo, "rb") as fin, gzip.open(tmp, "wb", compresslevel=6) as fout:
        cabecera = fin.readline()
        cols = cabecera.decode().rstrip("\r\n").split(",")
        i_cli, i_mes = cols.index("numero_de_cliente"), cols.index("foto_mes")
        fout.write(cabecera)
        for linea in fin:
            campos = linea.split(b",", max(i_cli, i_mes) + 1)
            mes = int(campos[i_mes])
            if mes < ultimo:
                raise SystemExit(f"el crudo no está ordenado por foto_mes ({mes} después de {ultimo})")
            ultimo = mes
            if mes > HASTA:
                break  # los meses posteriores no se recorren
            cli = int(float(campos[i_cli]))  # hay clientes escritos como 1.1e+08
            if entra(cli, a.denominador):
                fout.write(linea)
                filas[mes] += 1
                clientes.setdefault(mes, set()).add(cli)
    tmp.rename(crudo)
    ref = destino / "referencia_filas_por_mes.csv"
    with open(ref, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["foto_mes", "filas", "clientes_unicos", "esperado"])
        for m in sorted(x for x in filas if x <= 201912):
            w.writerow([m, filas[m], len(clientes[m]), filas[m] == len(clientes[m])])
    (destino / "config.toml").write_text(
        "# Muestra chica (scripts/muestra_chica.py). Usar con DMEYF_CONFIG=<esta ruta>.\n[rutas]\n"
        f'datos = "{destino.as_posix()}"\nauditoria_2019 = "{ref.as_posix()}"\n', encoding="utf-8")
    info = {"origen": mostrar(RUTAS.crudo), "hasta": HASTA, "regla": f"(numero_de_cliente · {KNUTH}) mod 2^32 "
            f"< 2^32 / {a.denominador}", "denominador": a.denominador,
            "filas_por_mes": {str(m): filas[m] for m in sorted(filas)},
            "clientes_por_mes": {str(m): len(clientes[m]) for m in sorted(clientes)},
            "sha256": {"crudo": sha256(crudo), "referencia": sha256(ref)},
            "segundos": round(time.perf_counter() - t0, 1), "creado": time.strftime("%Y-%m-%dT%H:%M:%S")}
    (destino / "muestra.json").write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: info[k] for k in ("filas_por_mes", "segundos")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
