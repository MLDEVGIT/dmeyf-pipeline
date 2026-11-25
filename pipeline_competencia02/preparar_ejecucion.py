"""Prepara una carpeta de ejecución nueva para el pipeline mensual con dos estrategias (mensual.py).

Estructura:
  input/<yyyymm>.csv                 entrada del mes (la deja el operador o --copiar-desde de mensual.py)
  output/churn_<yyyymm>.csv          SALIDA OFICIAL: recomendación provisional (binario)
  historia/foto_mes=<yyyymm>.parquet historia tipada: inicial + meses completados
  modelos/                           copia verificada del catálogo elegido (--catalogo; por defecto catalogo.ACTIVO)
                                     como modelos/estrategias.json, y sus modelos
  diagnosticos/<yyyymm>/             features, predicciones por semilla, decisiones de las dos estrategias, reporte.json
  registro/                          meses/<yyyymm>.json (estado), ejecuciones.jsonl (intentos), reporte_acumulado.csv
  tmp/                               intentos en curso
  entorno.json                       esquema crudo, cobertura de la historia, catálogo y hashes

Historia inicial, de 201901 a --hasta, sin huecos:
  - meses <= 201912: del Parquet tipado de 2019 (RUTAS.historico_2019), con las filas por mes contrastadas con
    referencia/01_filas_por_mes.csv;
  - meses >= 202001: de los insumos CSV (RUTAS.insumos/competencia_02_<mes>_crudo.csv), tipados y validados con
    ejecutar_mes.validar_entrada (las mismas reglas que un mes en producción) y contrastados con el .json del insumo.
Cobertura validada: meses consecutivos desde 201901, ninguno >= al primer mes a procesar, nombre de archivo = contenido,
un solo foto_mes por archivo, clientes únicos y el mismo esquema en todos.

No lee etiquetas: ningún archivo de clase ni de 2019 ni de otro período.

Uso: python -m pipeline_competencia02.preparar_ejecucion --nombre N --hasta 201912 [--catalogo tc01|e01]
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import time
from pathlib import Path

import duckdb

from . import catalogo as K
from . import incidentes as I
from .config import RAIZ, RUTAS, mostrar
from .ejecutar_mes import Entorno, sha256, validar_entrada

DESDE = 201901


def siguiente(m: int) -> int:
    a, mm = divmod(m, 100)
    return a * 100 + mm + 1 if mm < 12 else (a + 1) * 100 + 1


def meses_entre(desde: int, hasta: int) -> list[int]:
    out, m = [], desde
    while m <= hasta:
        out.append(m)
        m = siguiente(m)
    return out


def copiar_catalogo(env: Path, nombre: str | None = None) -> dict:
    origen_cat = K.archivo(nombre)
    cat = K.cargar(origen_cat)
    for e in cat["estrategias"]:
        for m in e["modelos"]:
            origen = RUTAS.modelos / m["archivo"]
            destino = env / "modelos" / m["archivo"]
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origen, destino)
            if sha256(destino) != m["sha256"]:
                raise RuntimeError(f"{m['archivo']}: sha256 distinto del catálogo")
    shutil.copy2(origen_cat, env / "modelos" / "estrategias.json")
    shutil.copy2(K.PREDICTORES, env / "modelos" / "predictores.json")
    return cat


def historia_2019(con, env: Path, meses: list[int]) -> dict:
    esperado = {}
    with open(RUTAS.auditoria_2019, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            esperado[int(r["foto_mes"])] = int(r["filas"])
    origen = RUTAS.historico_2019.as_posix()
    out = {}
    for m in meses:
        dst = env / "historia" / f"foto_mes={m}.parquet"
        con.execute(f"COPY (SELECT * FROM read_parquet('{origen}') WHERE foto_mes = {m}) TO '{dst.as_posix()}' "
                    f"(FORMAT parquet, COMPRESSION zstd)")
        n, n_cli, mn, mx = con.execute(f"SELECT count(*), count(DISTINCT numero_de_cliente), min(foto_mes), max(foto_mes) "
                                       f"FROM read_parquet('{dst.as_posix()}')").fetchone()
        if not (n == esperado.get(m) and n_cli == n and mn == mx == m):
            raise RuntimeError(f"historia {m}: {n} filas, {n_cli} clientes, meses {mn}-{mx}; auditoría {esperado.get(m)}")
        out[str(m)] = {"filas": int(n), "fuente": mostrar(RUTAS.historico_2019), "sha256": sha256(dst),
                       "control": "filas = referencia/01_filas_por_mes.csv"}
    return out


def historia_insumos(env_dir: Path, meses: list[int]) -> dict:
    """Agrega meses desde los CSV de insumos, en orden, con la validación de producción."""
    out = {}
    for m in meses:
        insumo = RUTAS.insumos / f"competencia_02_{m}_crudo.csv"
        meta = json.loads(insumo.with_suffix(".json").read_text(encoding="utf-8"))
        if sha256(insumo) != meta["sha256"]:
            raise RuntimeError(f"{insumo.name} cambió desde que se preparó")
        trabajo = env_dir / "tmp" / f"historia_{m}"
        trabajo.mkdir(parents=True)
        copia = trabajo / f"{m}.csv"
        shutil.copy2(insumo, copia)
        env = Entorno(env_dir)
        pol, rep = I.Politica(), {}
        con = duckdb.connect()
        try:
            _, _, pq = validar_entrada(con, env, copia, m, trabajo, rep, pol)
        finally:
            con.close()
        if rep["validacion"]["filas"] != meta["filas"]:
            raise RuntimeError(f"{m}: {rep['validacion']['filas']} filas tipadas, el insumo declara {meta['filas']}")
        dst = env_dir / "historia" / f"foto_mes={m}.parquet"
        pq.rename(dst)
        shutil.rmtree(trabajo)
        out[str(m)] = {"filas": rep["validacion"]["filas"], "fuente": mostrar(insumo), "sha256_insumo": meta["sha256"],
                       "sha256": sha256(dst), "control": "validar_entrada (reglas de producción) + filas del .json"}
    return out


def validar_cobertura(con, env: Path, hasta: int, esquema: list) -> dict:
    archivos = sorted((env / "historia").glob("foto_mes=*.parquet"))
    nombres = [int(p.stem.split("=")[1]) for p in archivos]
    contenido = con.execute(f"SELECT list(DISTINCT foto_mes ORDER BY foto_mes) FROM read_parquet("
                            f"{[p.as_posix() for p in archivos]})").fetchone()[0]
    por_archivo = [con.execute(f"SELECT count(DISTINCT foto_mes) FROM read_parquet('{p.as_posix()}')").fetchone()[0]
                   for p in archivos]
    esquemas = {tuple((c, t) for c, t, *_ in con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{p.as_posix()}')").fetchall()) for p in archivos}
    esperados = meses_entre(DESDE, hasta)
    checks = {"empieza_en_201901": bool(nombres) and nombres[0] == DESDE,
              "termina_en_hasta": bool(nombres) and nombres[-1] == hasta,
              "meses_consecutivos_sin_huecos": nombres == esperados,
              "nombre_igual_contenido": nombres == contenido,
              "un_foto_mes_por_archivo": all(n == 1 for n in por_archivo),
              "mismo_esquema_en_todos": len(esquemas) == 1 and [list(x) for x in next(iter(esquemas))] == esquema}
    if not all(checks.values()):
        raise RuntimeError(f"cobertura de la historia inválida: {checks}")
    return {"desde": DESDE, "hasta": hasta, "meses": len(nombres), "proximo_mes": siguiente(hasta),
            "checks": checks}


def crear(nombre: str, hasta: int, catalogo: str | None = None) -> Path:
    env = RUTAS.entornos / nombre
    if env.exists():
        raise FileExistsError(f"{env} ya existe; cada ensayo usa una carpeta nueva")
    if hasta < 201902:
        raise ValueError("la historia necesita al menos dos meses (lag2)")
    for d in ("input", "output", "historia", "modelos", "diagnosticos", "registro/meses", "tmp"):
        (env / d).mkdir(parents=True)
    t0 = time.perf_counter()
    catalogo = catalogo or K.ACTIVO
    cat = copiar_catalogo(env, catalogo)
    con = duckdb.connect()
    con.execute("SET threads = 4")
    con.execute("SET memory_limit = '2GB'")
    esquema = [[c, t] for c, t, *_ in con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{RUTAS.historico_2019.as_posix()}')").fetchall()]
    cfg = {"nombre": nombre, "tipo": "mensual_dos_estrategias", "creado": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "esquema_crudo": esquema, "catalogo": {"nombre": catalogo, "origen": K.archivo(catalogo).relative_to(RAIZ).as_posix(),
                                                  "target_version": cat.get("target_version", 1),
                                                  "archivo": "modelos/estrategias.json",
                                                  "sha256": sha256(env / "modelos" / "estrategias.json"),
                                                  "estrategias": [e["id"] for e in cat["estrategias"]]},
           "nota": "entorno aislado: la ejecución mensual sólo lee dentro de este directorio; no lee etiquetas"}
    (env / "entorno.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    meses = meses_entre(DESDE, hasta)
    historia = historia_2019(con, env, [m for m in meses if m <= 201912])
    con.close()
    historia.update(historia_insumos(env, [m for m in meses if m > 201912]))
    con = duckdb.connect()
    cfg["historia"] = {"meses": historia, "cobertura": validar_cobertura(con, env, hasta, esquema)}
    con.close()
    cfg["preparacion_s"] = round(time.perf_counter() - t0, 1)
    (env / "entorno.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return env


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Crea una carpeta de ejecución para el pipeline mensual.")
    ap.add_argument("--nombre", required=True)
    ap.add_argument("--hasta", type=int, required=True, help="último foto_mes de historia (el anterior al primero a procesar)")
    ap.add_argument("--catalogo", choices=sorted(K.CATALOGOS), default=K.ACTIVO)
    a = ap.parse_args(argv)
    env = crear(a.nombre, a.hasta, a.catalogo)
    cfg = json.loads((env / "entorno.json").read_text(encoding="utf-8"))
    print(f"Ejecución creada: {mostrar(env)} | historia {cfg['historia']['cobertura']} | {cfg['preparacion_s']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
