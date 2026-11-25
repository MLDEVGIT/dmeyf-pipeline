"""CE02 — semillas y composición de los ensambles, fijadas ANTES de entrenar (docs/PLAN_PRUEBAS.md § 13).

20 semillas por objetivo: 20261124 + i, i = 0..19. Las 5 primeras (20261124–20261128) son las de TC01 y se reutilizan;
las 10 primeras coinciden con experimentos.e01_binario_vs_multiclase.SEMILLAS. Se entrenan 15 nuevas (20261129–20261143).

Composiciones (índices sobre la lista de 20, en orden):
  anidados   5 = 0..4 (TC01), 10 = 0..9, 20 = 0..19
  disjuntos  de 5: {0..4}, {5..9}, {10..14}, {15..19};  de 10: {0..9}, {10..19}
  aleatorios 200 subconjuntos de 5 y 200 de 10, sin repetición, generador numpy default_rng(20261125)

Uso: python -m experimentos.ce02_composicion   (escribe resultados/ce02_composicion.json; no lo sobrescribe si cambió)
"""
from __future__ import annotations

import json
import sys

import numpy as np

from pipeline_competencia02.config import RAIZ

SEMILLAS = [20261124 + i for i in range(20)]
SEMILLAS_TC01 = SEMILLAS[:5]
SEMILLAS_NUEVAS = SEMILLAS[5:]
GENERADOR = 20261125
N_ALEATORIOS = 200
REGISTRO = RAIZ / "resultados" / "ce02_composicion.json"


def aleatorios(tamano: int, n: int = N_ALEATORIOS, semilla: int = GENERADOR) -> list[list[int]]:
    rng = np.random.default_rng(semilla + tamano)
    vistos, out = set(), []
    while len(out) < n:
        s = tuple(sorted(int(i) for i in rng.choice(20, size=tamano, replace=False)))
        if s not in vistos:
            vistos.add(s)
            out.append(list(s))
    return out


def composiciones() -> dict:
    return {
        "anidados": {"5": list(range(5)), "10": list(range(10)), "20": list(range(20))},
        "disjuntos": {"5": [list(range(i, i + 5)) for i in (0, 5, 10, 15)], "10": [list(range(10)), list(range(10, 20))]},
        "aleatorios": {"5": aleatorios(5), "10": aleatorios(10)},
    }


def registro() -> dict:
    return {"semillas": SEMILLAS, "semillas_tc01_reutilizadas": SEMILLAS_TC01, "semillas_nuevas": SEMILLAS_NUEVAS,
            "generador_aleatorios": f"numpy default_rng({GENERADOR} + tamaño), sin repetición",
            "indices_sobre": "la lista 'semillas' (0 = 20261124)", "composiciones": composiciones()}


def main() -> int:
    r = registro()
    texto = json.dumps(r, indent=1, ensure_ascii=False) + "\n"
    if REGISTRO.exists() and REGISTRO.read_text(encoding="utf-8") != texto:
        raise SystemExit(f"{REGISTRO} ya existe con otro contenido; no se sobrescribe")
    REGISTRO.write_text(texto, encoding="utf-8", newline="\n")
    print(f"semillas {SEMILLAS[0]}..{SEMILLAS[-1]}; aleatorios 5: {len(r['composiciones']['aleatorios']['5'])}, "
          f"10: {len(r['composiciones']['aleatorios']['10'])} -> {REGISTRO.relative_to(RAIZ).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
