"""Prueba de reintentos del pipeline mensual (mensual.py) sobre una carpeta de ejecución NUEVA.

Pasos, con el mismo mes:
  1. falla inyectada a mitad de la publicación (PIPELINE_C02_FALLA=durante_publicacion): código 2; no queda
     publicado nada, el estado es fallido y el reporte acumulado no tiene filas;
  2. el proceso muere después de publicar y antes de marcar el estado (PIPELINE_C02_FALLA=tras_publicacion):
     queda todo publicado, estado en_curso y candado huérfano;
  3. reintento normal: reconcilia, comprueba la integridad, marca completado SIN recalcular (no hay features nuevas)
     y el reporte acumulado tiene exactamente una fila del mes;
  4. otro reintento: rechazado con código 4, sin cambiar ningún archivo publicado ni el reporte.
En cada paso se verifica que salida, historia, diagnóstico, estado y reporte estén alineados.

Uso: python scripts/probar_reintentos.py --mes 202001 --entrada <csv>
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from pipeline_competencia02.config import RUTAS, mostrar  # noqa: E402
from pipeline_competencia02.ejecutar_mes import anterior  # noqa: E402


def sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def foto(env: Path, mes: int) -> dict:
    acum = env / "registro" / "reporte_acumulado.csv"
    filas = list(csv.DictReader(open(acum, encoding="utf-8"))) if acum.exists() else []
    est = env / "registro" / "meses" / f"{mes}.json"
    return {"salida": sha(env / "output" / f"churn_{mes}.csv"),
            "historia": sha(env / "historia" / f"foto_mes={mes}.parquet"),
            "diagnostico": (env / "diagnosticos" / str(mes)).exists(),
            "reporte_mes": sha(env / "diagnosticos" / str(mes) / "reporte.json"),
            "estado": json.loads(est.read_text(encoding="utf-8"))["estado"] if est.exists() else None,
            "candado": (env / "registro" / "meses" / f"{mes}.lock").exists(),
            "filas_acumulado": [f["mes"] for f in filas],
            "acumulado_integridad": [f.get("integridad_ok") for f in filas],
            "acumulado_sha": sha(acum), "tmp_vacio": not any((env / "tmp").iterdir()),
            "fallidos": sorted(p.name for p in (env / "diagnosticos").glob(f"{mes}.fallido-*")),
            "intentos": sum(1 for _ in open(env / "registro" / "ejecuciones.jsonl", encoding="utf-8"))
            if (env / "registro" / "ejecuciones.jsonl").exists() else 0}


def correr(env: Path, mes: int, entrada: Path, falla: str | None) -> tuple[int, float]:
    entorno = {k: v for k, v in os.environ.items() if k != "PIPELINE_C02_FALLA"}
    if falla:
        entorno["PIPELINE_C02_FALLA"] = falla
    t = time.perf_counter()
    rc = subprocess.run([sys.executable, "-m", "pipeline_competencia02.mensual", "--ejecucion", str(env), "--mes",
                         str(mes), "--copiar-desde", str(entrada)], cwd=RAIZ, env=entorno,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
    return rc, round(time.perf_counter() - t, 1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mes", type=int, required=True)
    ap.add_argument("--entrada", type=Path, required=True)
    a = ap.parse_args(argv)
    nombre = f"reintentos_{a.mes}_{time.strftime('%Y%m%dT%H%M%S')}"
    subprocess.run([sys.executable, "-m", "pipeline_competencia02.preparar_ejecucion", "--nombre", nombre,
                    "--hasta", str(anterior(a.mes))], cwd=RAIZ, check=True,
                   stdout=subprocess.DEVNULL)
    env, mes = RUTAS.entornos / nombre, a.mes
    pasos = []

    rc, s = correr(env, mes, a.entrada, "durante_publicacion")
    f = foto(env, mes)
    pasos.append({"paso": "1 falla durante la publicación", "codigo": rc, "segundos": s, "foto": f, "ok": (
        rc == 2 and f["salida"] is None and f["historia"] is None and not f["diagnostico"] and f["estado"] == "fallido"
        and not f["candado"] and f["filas_acumulado"] == [] and len(f["fallidos"]) == 1 and f["tmp_vacio"])})

    rc, s = correr(env, mes, a.entrada, "tras_publicacion")
    f = foto(env, mes)
    pasos.append({"paso": "2 el proceso muere después de publicar", "codigo": rc, "segundos": s, "foto": f, "ok": (
        rc == 3 and f["salida"] and f["historia"] and f["diagnostico"] and f["estado"] == "en_curso" and f["candado"]
        and f["filas_acumulado"] == [])})
    publicado = {k: f[k] for k in ("salida", "historia", "reporte_mes")}

    rc, s = correr(env, mes, a.entrada, None)
    f = foto(env, mes)
    est = json.loads((env / "registro" / "meses" / f"{mes}.json").read_text(encoding="utf-8"))
    pasos.append({"paso": "3 reintento: reconcilia sin recalcular", "codigo": rc, "segundos": s, "foto": f, "ok": (
        rc == 0 and {k: f[k] for k in publicado} == publicado and f["estado"] == "completado" and not f["candado"]
        and f["filas_acumulado"] == [str(mes)] and f["acumulado_integridad"] == ["True"] and est.get("recuperado") is True
        and [i["estado"] for i in est["intentos"]] == ["fallido", "fallido", "completado"])})
    antes = f

    rc, s = correr(env, mes, a.entrada, None)
    f = foto(env, mes)
    pasos.append({"paso": "4 mes completado: rechazado sin cambios", "codigo": rc, "segundos": s, "foto": f, "ok": (
        rc == 4 and {k: v for k, v in f.items() if k != "intentos"} == {k: v for k, v in antes.items() if k != "intentos"}
        and f["intentos"] == antes["intentos"] + 1)})

    res = {"ejecucion": mostrar(env), "mes": mes, "pasos": pasos, "ok": all(p["ok"] for p in pasos)}
    (env / "prueba_reintentos.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    for p in pasos:
        print(f"{p['paso']}: código {p['codigo']}, {p['segundos']} s -> {'OK' if p['ok'] else 'FALLA'}")
    print(f"resultado: {'OK' if res['ok'] else 'FALLA'} ({mostrar(env)}/prueba_reintentos.json)")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
