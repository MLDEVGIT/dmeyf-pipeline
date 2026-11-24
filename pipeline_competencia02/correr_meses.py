"""Ejecuta meses consecutivos en un entorno, uno por proceso, y comprueba cada uno.

No calcula desempeño: no lee etiquetas. Para cada mes verifica:
  - estado completado y salida oficial publicada;
  - cobertura: los clientes de output/churn_AAAAMM.csv, de las decisiones y
    de las features son exactamente los del CSV recibido;
  - probabilidades finitas, en [0,1] e iguales en la salida oficial y en las
    decisiones;
  - decisiones: A = cupo fijo, B = techo(1 % de los clientes); ambas son el
    prefijo del mismo orden (probabilidad descendente, desempate por
    numero_de_cliente) y el conjunto menor está contenido en el mayor;
  - aislamiento: sólo leyó el mes recibido, la historia anterior y el modelo.

Se detiene ante el primer mes que no pase.

Uso:
  python -m pipeline_competencia02.correr_meses --entorno <dir> --desde 202001 --hasta 202006 \
      --estrategia cupo_fijo:1000 --estrategia porcentaje:1 --principal cupo_fijo
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import duckdb
import numpy as np

from . import estrategias as E

from .config import RAIZ as ROOT, RUTAS, mostrar

INSUMOS = RUTAS.insumos


def meses_entre(desde: int, hasta: int) -> list[int]:
    out, m = [], desde
    while m <= hasta:
        out.append(m)
        a, mm = divmod(m, 100)
        m = a * 100 + mm + 1 if mm < 12 else (a + 1) * 100 + 1
    return out


def comprobar(con, env: Path, mes: int, estrategias: list[E.Estrategia], principal: str) -> dict:
    diag = env / "diagnosticos" / str(mes)
    rep = json.loads((diag / "reporte.json").read_text(encoding="utf-8"))
    estado = json.loads((env / "registro" / "meses" / f"{mes}.json").read_text(encoding="utf-8"))
    entrada = (env / rep["entrada"]["archivo"]).as_posix()
    oficial = (env / "output" / f"churn_{mes}.csv").as_posix()
    dec = (diag / f"decisiones_{mes}.csv").as_posix()
    feat = (diag / f"features_{mes}.parquet").as_posix()

    cab_oficial = (env / "output" / f"churn_{mes}.csv").read_text(encoding="utf-8").split("\n", 1)[0]
    ins = con.execute(f"SELECT numero_de_cliente FROM read_csv('{entrada}', header=true, all_varchar=true)").fetchall()
    cli_entrada = {int(float(c)) for (c,) in ins}  # algunos ids vienen en notación científica (ver README de 02)
    o = con.execute(f"SELECT numero_de_cliente, probabilidad, enviar FROM read_csv('{oficial}', header=true) "
                    f"ORDER BY numero_de_cliente").fetchnumpy()
    d = con.execute(f"SELECT * FROM read_csv('{dec}', header=true) ORDER BY numero_de_cliente").fetchnumpy()
    cli_feat = {c for (c,) in con.execute(f"SELECT numero_de_cliente FROM read_parquet('{feat}')").fetchall()}
    cli, prob = np.asarray(o["numero_de_cliente"]), np.asarray(o["probabilidad"], np.float64)
    n = len(cli)

    orden = E.orden_por_score(cli, prob)
    sel = {}
    for e in estrategias:
        k = e.cupo if isinstance(e, E.CupoFijo) else e.cantidad(n)
        esperado = np.zeros(n, bool)
        esperado[orden[:k]] = True
        sel[e.nombre] = {"esperados": int(k), "seleccionados": int(np.asarray(d[f"enviar_{e.nombre}"]).sum()),
                         "igual_al_prefijo_del_orden": bool(np.array_equal(np.asarray(d[f"enviar_{e.nombre}"]) == 1,
                                                                           esperado))}
    conjuntos = [np.asarray(d[f"enviar_{e.nombre}"]) == 1 for e in estrategias]
    anidadas = all(((a & b).sum() == min(a.sum(), b.sum())) for a in conjuntos for b in conjuntos)

    lect = rep["lecturas"]
    hist_leida = sorted(int(p.split("foto_mes=")[1][:6]) for p in lect if p.startswith("historia/"))
    hist_previa = sorted(int(p.stem.split("=")[1]) for p in (env / "historia").glob("foto_mes=*.parquet")
                         if int(p.stem.split("=")[1]) < mes)
    permitidas = all(p.startswith((f"entradas/{mes}/", f"tmp/{rep['ejecucion']}/", "historia/", "modelo/"))
                     for p in lect)

    checks = {
        "completado": estado["estado"] == "completado" and rep["estado"] == "completado",
        "cabecera_oficial": cab_oficial == "numero_de_cliente,probabilidad,enviar",
        "cobertura_oficial_igual_entrada": n == len(cli_entrada) and set(cli.tolist()) == cli_entrada
                                           and len(np.unique(cli)) == n,
        "cobertura_features_y_decisiones": cli_feat == cli_entrada
                                           and np.array_equal(np.asarray(d["numero_de_cliente"]), cli),
        "probabilidades_finitas_en_0_1": bool(np.isfinite(prob).all() and ((prob >= 0) & (prob <= 1)).all()),
        "probabilidades_iguales_oficial_y_decisiones": bool(np.array_equal(np.asarray(d["probabilidad"]), prob)),
        "oficial_es_la_principal": bool(np.array_equal(np.asarray(o["enviar"]), np.asarray(d[f"enviar_{principal}"]))),
        "cantidades_correctas": all(v["esperados"] == v["seleccionados"] for v in sel.values()),
        "seleccion_por_orden_y_desempate": all(v["igual_al_prefijo_del_orden"] for v in sel.values()),
        "estrategias_anidadas": anidadas,
        "solo_lee_mes_historia_previa_y_modelo": permitidas and hist_leida == hist_previa
                                                  and all(m < mes for m in hist_leida),
        "historia_actualizada": (env / "historia" / f"foto_mes={mes}.parquet").exists(),
    }
    return {"mes": mes, "ok": all(checks.values()), "checks": checks, "clientes": n, "seleccion": sel,
            "historia_leida": f"{hist_leida[0]}-{hist_leida[-1]} ({len(hist_leida)} meses)",
            "comparacion_estrategias": {k: {c: v[c] for c in ("seleccionados", "proporcion",
                                                              "interseccion_con_principal", "jaccard_con_principal")}
                                        for k, v in rep["comparacion_estrategias"].items()},
            "tiempos": rep["tiempos"], "memoria": rep["memoria"], "alertas": rep["alertas"],
            "distribucion_scores": rep["distribucion_scores"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ejecuta y comprueba meses consecutivos en un entorno.")
    ap.add_argument("--entorno", type=Path, required=True)
    ap.add_argument("--desde", type=int, required=True)
    ap.add_argument("--hasta", type=int, required=True)
    ap.add_argument("--estrategia", action="append", required=True)
    ap.add_argument("--principal", required=True)
    a = ap.parse_args(argv)
    env = a.entorno.resolve()
    estrategias = [E.construir(s) for s in a.estrategia]
    resumen = {"entorno": mostrar(env), "estrategias": a.estrategia, "principal": a.principal,
               "nota": "sin desempeño: no se leen etiquetas", "meses": []}
    con = duckdb.connect()
    con.execute("SET threads = 4")
    con.execute("SET memory_limit = '1GB'")
    codigo = 0
    for mes in meses_entre(a.desde, a.hasta):
        entrada = INSUMOS / f"competencia_02_{mes}_crudo.csv"
        cmd = [sys.executable, "-m", "pipeline_competencia02.ejecutar_mes", "--entorno", str(env),
               "--entrada", str(entrada), "--mes", str(mes), "--principal", a.principal]
        for e in a.estrategia:
            cmd += ["--estrategia", e]
        t = time.perf_counter()
        rc = subprocess.run(cmd, cwd=ROOT, env={k: v for k, v in os.environ.items() if k != "PIPELINE_C02_FALLA"}
                            ).returncode
        pared = round(time.perf_counter() - t, 1)
        if rc != 0:
            resumen["meses"].append({"mes": mes, "ok": False, "codigo": rc})
            print(f"[{mes}] FALLÓ con código {rc}; se detiene la secuencia", flush=True)
            codigo = 2
            break
        r = comprobar(con, env, mes, estrategias, a.principal)
        r["tiempo_proceso_s"] = pared
        resumen["meses"].append(r)
        print(f"[{mes}] {'OK' if r['ok'] else 'FALLA'} | clientes {r['clientes']:,} | "
              f"{ {k: v['seleccionados'] for k, v in r['comparacion_estrategias'].items()} } | "
              f"{r['tiempos']['total_s']}s | pico WS {r['memoria']['pico_working_set_mb']:,.0f} MB | "
              f"checks fallidos: {[k for k, v in r['checks'].items() if not v]}", flush=True)
        if not r["ok"]:
            codigo = 2
            break
    con.close()
    resumen["ok"] = codigo == 0
    (env / "pruebas").mkdir(exist_ok=True)
    out = env / "pruebas" / f"secuencia_{a.desde}_{a.hasta}.json"
    out.write_text(json.dumps(resumen, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"Resumen: {mostrar(out)}")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
