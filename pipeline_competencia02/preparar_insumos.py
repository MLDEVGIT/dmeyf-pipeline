"""Prepara CSV crudos mensuales desde el original, sin modificar sus valores.

Queda FUERA del tiempo de la ejecución mensual: simula la entrega del archivo
de cada mes.

- Copia byte a byte la cabecera y las líneas con foto_mes en [desde, hasta]:
  no reescribe valores, separadores ni fines de línea.
- El original está ordenado por foto_mes. La lectura se corta en la primera
  línea de un mes > hasta: de esa línea sólo se mira foto_mes y no se guarda.
  Los meses posteriores nunca se recorren. Si aparece un mes menor que el
  anterior, el script aborta, porque el corte dejaría de ser seguro.
- Prueba de orden y completitud: los conteos de 2019 encontrados antes del
  corte deben coincidir con la auditoría de 01 (referencia/01_filas_por_mes.csv).
- Nunca sobrescribe. Si un insumo ya existe, verifica su sha256 contra el .json.

Uso: python -m pipeline_competencia02.preparar_insumos --desde 202001 --hasta 202006
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from .config import RUTAS, mostrar

ORIGEN = RUTAS.crudo
INSUMOS = RUTAS.insumos
AUDITORIA_2019 = RUTAS.auditoria_2019


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def destino(mes: int) -> Path:
    return INSUMOS / f"competencia_02_{mes}_crudo.csv"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Prepara CSV crudos mensuales desde el original.")
    ap.add_argument("--desde", type=int, required=True)
    ap.add_argument("--hasta", type=int, required=True)
    a = ap.parse_args(argv)
    t0 = time.perf_counter()
    INSUMOS.mkdir(parents=True, exist_ok=True)

    existentes = [m for m in range(a.desde, a.hasta + 1) if 1 <= m % 100 <= 12 and destino(m).exists()]
    for m in existentes:
        info = json.loads(destino(m).with_suffix(".json").read_text(encoding="utf-8"))
        if sha256(destino(m)) != info["sha256"]:
            raise RuntimeError(f"{destino(m)} cambió desde que se preparó")
    print(f"ya preparados y verificados: {existentes}")

    tmp, handles, conteo = {}, {}, {}
    corte, previo = None, 0
    with gzip.open(ORIGEN, "rb") as src:
        cab = src.readline()
        idx = cab.decode("utf-8").rstrip("\r\n").split(",").index("foto_mes")
        for linea in src:
            mes = int(linea.split(b",", idx + 1)[idx])
            if mes < previo:
                raise RuntimeError(f"el original no está ordenado por foto_mes ({previo} -> {mes}); el corte no es seguro")
            if mes > a.hasta:
                corte = mes  # sólo se miró foto_mes de esta línea; no se guarda
                break
            previo = mes
            conteo[mes] = conteo.get(mes, 0) + 1
            if mes >= a.desde and mes not in existentes:
                if mes not in handles:
                    tmp[mes] = destino(mes).with_name(destino(mes).name + f".tmp-{os.getpid()}")
                    handles[mes] = open(tmp[mes], "wb")
                    handles[mes].write(cab)
                handles[mes].write(linea)
    for h in handles.values():
        h.close()

    with open(AUDITORIA_2019, encoding="utf-8") as f:
        esperado_2019 = {int(r["foto_mes"]): int(r["filas"]) for r in csv.DictReader(f)}
    obtenido_2019 = {m: n for m, n in conteo.items() if m // 100 == 2019}
    pedidos = [m for m in range(a.desde, a.hasta + 1) if 1 <= m % 100 <= 12]
    checks = {"conteos_2019_igual_auditoria_01": obtenido_2019 == esperado_2019,
              "todos_los_meses_pedidos_presentes": all(conteo.get(m, 0) > 0 for m in pedidos),
              "corte_en_mes_posterior": corte is not None and corte > a.hasta}
    if not all(checks.values()):
        for p in tmp.values():
            p.unlink(missing_ok=True)
        raise RuntimeError(f"preparación inválida: {checks}")

    resumen = {}
    for m, p in sorted(tmp.items()):
        if destino(m).exists():
            raise FileExistsError(f"{destino(m)} apareció durante la preparación; no se sobrescribe")
        os.rename(p, destino(m))
        info = {"origen": mostrar(ORIGEN), "mes": m, "filas": conteo[m],
                "sha256": sha256(destino(m)), "preparado": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "metodo": "cabecera y líneas con foto_mes == mes, copiadas byte a byte (fin de línea del original)",
                "lectura_cortada_en": corte, "checks": checks}
        destino(m).with_suffix(".json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
        resumen[m] = {"filas": conteo[m], "sha256": info["sha256"][:16]}
    print(f"preparados: {resumen}")
    print(f"checks: {checks} | lectura cortada en la primera línea de {corte} | "
          f"{time.perf_counter() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
