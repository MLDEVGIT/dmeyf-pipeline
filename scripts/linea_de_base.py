"""Línea de base de una secuencia: sha256 de cada salida (output/churn_<mes>.csv) y de cada archivo de decisiones
(diagnosticos/<mes>/decisiones_<mes>.csv) de una carpeta de ejecución.

Es la red de seguridad del reordenamiento en etapas (diseño, decisión 1): se guarda antes de tocar mensual.py y,
después, la misma secuencia tiene que dar exactamente los mismos sha256.

  python scripts/linea_de_base.py --ejecucion <carpeta> --guardar resultados/l01_linea_de_base_<nombre>.json
  python scripts/linea_de_base.py --ejecucion <carpeta> --comparar resultados/l01_linea_de_base_<nombre>.json

Con --comparar termina con 1 si algún archivo falta o difiere.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def huellas(ejecucion: Path) -> dict[str, str]:
    archivos = sorted(ejecucion.glob("output/churn_*.csv")) + sorted(ejecucion.glob("diagnosticos/*/decisiones_*.csv"))
    return {p.relative_to(ejecucion).as_posix(): sha256(p) for p in archivos}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ejecucion", type=Path, required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--guardar", type=Path)
    g.add_argument("--comparar", type=Path)
    a = ap.parse_args(argv)

    actual = huellas(a.ejecucion)
    if not actual:
        print(f"{a.ejecucion} no tiene salidas", file=sys.stderr)
        return 1
    if a.guardar:
        entorno = json.loads((a.ejecucion / "entorno.json").read_text(encoding="utf-8"))
        a.guardar.write_text(json.dumps({
            "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ejecucion": a.ejecucion.name,
            # los sha256 valen para estos modelos: con otro catálogo (otra máquina que fabrique) cambian
            "catalogo": {"origen": entorno["catalogo"]["origen"], "sha256": entorno["catalogo"]["sha256"]},
            "sha256": actual,
        }, indent=1) + "\n", encoding="utf-8")
        print(f"{len(actual)} archivos -> {a.guardar}")
        return 0

    base = json.loads(a.comparar.read_text(encoding="utf-8"))["sha256"]
    distintos = [k for k in base if actual.get(k) != base[k]]
    for k in base:
        print(("igual   " if k not in distintos else ("FALTA   " if k not in actual else "DISTINTO")), k)
    print(f"{len(base) - len(distintos)}/{len(base)} iguales")
    return 1 if distintos else 0


if __name__ == "__main__":
    raise SystemExit(main())
