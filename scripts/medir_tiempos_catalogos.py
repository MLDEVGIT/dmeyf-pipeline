"""Mide el tiempo mensual completo de varios catálogos en las MISMAS condiciones de máquina (PLAN_PRUEBAS.md § 15).

Para cada repetición y catálogo, en orden alternado (A B C … C B A, para compensar la deriva de la máquina:
temperatura, frecuencia, otras aplicaciones):
  1. prepara una carpeta nueva con historia 201901 a (mes − 1) y ese catálogo (no se mide);
  2. lanza `python -m pipeline_competencia02.mensual --mes M --copiar-desde <insumo>` y mide la pared del proceso,
     desde antes de lanzarlo (arranque, imports y copia a input/) hasta que termina (salida y reporte publicados);
  3. guarda los tiempos internos (inferencia por estrategia), la memoria pico y la frecuencia y carga de la CPU.
Pensado también para la máquina del vivo (T12): misma orden, sin parámetros de esta máquina.

Uso: python scripts/medir_tiempos_catalogos.py --mes 202001 --catalogos tc01 ce02 ce02_b20m10 --repeticiones 2
     [--salida resultados/<archivo>.json]
"""
from __future__ import annotations

import argparse
import ctypes
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import psutil

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from pipeline_competencia02.config import RUTAS, mostrar  # noqa: E402
from pipeline_competencia02.correr_meses import insumo  # noqa: E402
from pipeline_competencia02.ejecutar_mes import anterior  # noqa: E402


def despierto(activar: bool):
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | (0x00000001 if activar else 0))


def cpu() -> dict:
    f = psutil.cpu_freq()
    return {"frecuencia_mhz": round(f.current) if f else None, "carga_pct": psutil.cpu_percent(interval=2)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mes", type=int, default=202001)
    ap.add_argument("--catalogos", nargs="+", default=["tc01", "ce02", "ce02_b20m10"])
    ap.add_argument("--repeticiones", type=int, default=2)
    ap.add_argument("--salida", type=Path)
    a = ap.parse_args(argv)
    origen = insumo(a.mes)
    orden = []
    for r in range(a.repeticiones):
        orden += [(r, c) for c in (a.catalogos if r % 2 == 0 else a.catalogos[::-1])]
    marca = time.strftime("%Y%m%dT%H%M%S")
    res = {"mes": a.mes, "marca": marca, "orden": [c for _, c in orden],
           "reloj": "pared del proceso mensual, con arranque, imports, copia de la entrada, salida y reporte",
           "maquina": {"cpu": platform.processor(), "cpu_logicos": psutil.cpu_count(),
                       "cpu_fisicos": psutil.cpu_count(logical=False),
                       "ram_gb": round(psutil.virtual_memory().total / 2**30, 1), "plataforma": platform.platform()},
           "corridas": []}
    despierto(True)
    try:
        for r, cat in orden:
            nombre = f"tiempos_{cat}_{a.mes}_{marca}_r{r}"
            subprocess.run([sys.executable, "-m", "pipeline_competencia02.preparar_ejecucion", "--nombre", nombre,
                            "--hasta", str(anterior(a.mes)), "--catalogo", cat], cwd=RAIZ, check=True,
                           stdout=subprocess.DEVNULL)
            env = RUTAS.entornos / nombre
            antes = cpu()
            t = time.perf_counter()
            rc = subprocess.run([sys.executable, "-m", "pipeline_competencia02.mensual", "--ejecucion", str(env),
                                 "--mes", str(a.mes), "--copiar-desde", str(origen)], cwd=RAIZ,
                                stdout=subprocess.DEVNULL).returncode
            pared = round(time.perf_counter() - t, 1)
            rep = json.loads((env / "diagnosticos" / str(a.mes) / "reporte.json").read_text(encoding="utf-8"))
            fila = {"repeticion": r, "catalogo": cat, "codigo": rc, "pared_s": pared, "cpu_antes": antes,
                    "cpu_despues": cpu(), "tiempos_internos": rep["tiempos"], "memoria": rep["memoria"],
                    "modelos": {e["id"]: len(e["semillas"]) for e in rep["estrategias"]},
                    "ejecucion": mostrar(env)}
            res["corridas"].append(fila)
            print(f"[r{r}] {cat}: código {rc}, {pared} s, inferencia "
                  f"{ {k: v for k, v in rep['tiempos'].items() if k.startswith('inferencia')} }, "
                  f"cpu {antes} -> {fila['cpu_despues']}", flush=True)
    finally:
        despierto(False)
    res["resumen"] = {c: {"pared_s": [x["pared_s"] for x in res["corridas"] if x["catalogo"] == c]}
                      for c in a.catalogos}
    res["ok"] = all(x["codigo"] == 0 for x in res["corridas"])
    texto = json.dumps(res, indent=2, ensure_ascii=False) + "\n"
    (RUTAS.entornos / f"tiempos_catalogos_{a.mes}_{marca}.json").write_text(texto, encoding="utf-8")
    if a.salida:
        a.salida.write_text(texto, encoding="utf-8", newline="\n")
    print(json.dumps(res["resumen"]))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
