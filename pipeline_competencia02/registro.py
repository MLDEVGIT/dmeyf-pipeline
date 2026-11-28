"""Registro de corridas en Postgres: conexión, migraciones por esquema y exportación (diseño, decisión 5).

Un entorno (`produccion`, `ensayo`, `pruebas_<usuario>`, `medicion_<n>`) es un esquema de la base. Las tablas salen
de las migraciones de `migraciones/` (archivos SQL numerados, solo hacia adelante), que se aplican igual en Cloud SQL
y en el Postgres local de docker-compose.yml. Cada esquema guarda qué migraciones tiene en `migracion_aplicada`; una
corrida se niega a correr contra un esquema de otra versión (`comprobar_version`). Antes de migrar un esquema que ya
tiene tablas, se exporta (COPY de cada tabla a CSV).

Conexión (un solo driver, pg8000, en los dos casos):
  - DMEYF_PG_URL=postgresql://usuario:clave@host:puerto/base  -> Postgres directo (el local, o el plan B);
  - si no, Cloud SQL con el conector y la identidad de Google de quien corre (o de la cuenta de servicio de la VM),
    sin contraseñas: instancia DMEYF_PG_INSTANCIA (proyecto:región:instancia), base DMEYF_PG_BASE y usuario
    DMEYF_PG_USUARIO (por defecto, la cuenta activa de gcloud).
La conexión reintenta un número acotado de veces (DMEYF_PG_INTENTOS, por defecto 5) y después se rinde.

Uso:
  python -m pipeline_competencia02.registro migrar --entorno pruebas_agustina
  python -m pipeline_competencia02.registro version --entorno pruebas_agustina
  python -m pipeline_competencia02.registro ping
  python -m pipeline_competencia02.registro exportar --entorno ensayo [--destino DIR]
"""
from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

from .config import RUTAS

MIGRACIONES = Path(__file__).resolve().parent / "migraciones"
NOMBRE_ESQUEMA = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
INSTANCIA = os.environ.get("DMEYF_PG_INSTANCIA", "proj-uba-261012163242176:northamerica-northeast2:dmeyf-registro")
BASE = os.environ.get("DMEYF_PG_BASE", "dmeyf")


class BaseInalcanzable(RuntimeError):
    """La base no respondió después de los intentos configurados."""


class VersionDistinta(RuntimeError):
    """El esquema no tiene las mismas migraciones que el código."""


def validar_esquema(nombre: str) -> str:
    if not NOMBRE_ESQUEMA.match(nombre or ""):
        raise ValueError(f"nombre de entorno inválido para un esquema: {nombre!r} (minúsculas, dígitos y _)")
    return nombre


# --------------------------------------------------------------------------
# Conexión
def _conectar_url(url: str):
    import pg8000.dbapi
    u = urlparse(url)
    return pg8000.dbapi.connect(user=unquote(u.username or ""), password=unquote(u.password or "") or None,
                                host=u.hostname or "localhost", port=u.port or 5432,
                                database=(u.path or "/").lstrip("/") or "postgres", timeout=10)


_conector = None


def _usuario_google() -> str:
    usuario = os.environ.get("DMEYF_PG_USUARIO")
    if not usuario:
        usuario = subprocess.run(["gcloud", "config", "get", "account"], capture_output=True, text=True,
                                 check=True).stdout.strip()
    # las cuentas de servicio entran sin el sufijo .gserviceaccount.com
    return usuario.removesuffix(".gserviceaccount.com")


def _conectar_cloud_sql():
    global _conector
    from google.cloud.sql.connector import Connector
    if _conector is None:
        _conector = Connector()
    return _conector.connect(INSTANCIA, "pg8000", user=_usuario_google(), db=BASE, enable_iam_auth=True)


def conectar(intentos: int | None = None, espera_s: float = 1.0):
    """Conexión DB-API (pg8000) en autocommit desactivado. Reintenta y, si no puede, lanza BaseInalcanzable."""
    intentos = intentos or int(os.environ.get("DMEYF_PG_INTENTOS", "5"))
    url = os.environ.get("DMEYF_PG_URL")
    ultimo = None
    for i in range(1, intentos + 1):
        try:
            return _conectar_url(url) if url else _conectar_cloud_sql()
        except Exception as e:  # noqa: BLE001 — cualquier falla de red o de autenticación cuenta como intento
            ultimo = e
            if i < intentos:
                time.sleep(espera_s * i)
    raise BaseInalcanzable(f"la base no respondió en {intentos} intentos: {ultimo!r}") from ultimo


def usar_esquema(con, esquema: str) -> None:
    cur = con.cursor()
    cur.execute(f"SET search_path TO {validar_esquema(esquema)}")
    cur.close()


# --------------------------------------------------------------------------
# Migraciones
def migraciones() -> list[tuple[str, str]]:
    """(nombre, sql) de cada archivo NNNN_*.sql, en orden."""
    archivos = sorted(MIGRACIONES.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    nums = [int(p.name[:4]) for p in archivos]
    if nums != list(range(1, len(nums) + 1)):
        raise RuntimeError(f"migraciones con números salteados o repetidos: {[p.name for p in archivos]}")
    return [(p.stem, p.read_text(encoding="utf-8")) for p in archivos]


def aplicadas(con, esquema: str) -> list[str]:
    cur = con.cursor()
    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema = %s AND table_name = 'migracion_aplicada'",
                (esquema,))
    if not cur.fetchone():
        cur.close()
        return []
    cur.execute(f"SELECT nombre FROM {esquema}.migracion_aplicada ORDER BY nombre")
    out = [r[0] for r in cur.fetchall()]
    cur.close()
    return out


def comprobar_version(con, esquema: str) -> list[str]:
    """La corrida se niega a correr si el esquema no tiene exactamente las migraciones del código."""
    esperadas = [n for n, _ in migraciones()]
    tiene = aplicadas(con, validar_esquema(esquema))
    if tiene != esperadas:
        raise VersionDistinta(f"el esquema {esquema} tiene las migraciones {tiene}; el código espera {esperadas}. "
                              f"Aplicarlas con: python -m pipeline_competencia02.registro migrar --entorno {esquema}")
    return tiene


def tablas(con, esquema: str) -> list[str]:
    cur = con.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = %s AND table_type = 'BASE TABLE' "
                "ORDER BY table_name", (esquema,))
    out = [r[0] for r in cur.fetchall()]
    cur.close()
    return out


def exportar(con, esquema: str, destino: Path) -> Path:
    """COPY de cada tabla del esquema a <destino>/<tabla>.csv, por la misma conexión (decisión 5)."""
    validar_esquema(esquema)
    destino.mkdir(parents=True, exist_ok=True)
    cur = con.cursor()
    for t in tablas(con, esquema):
        buf = io.BytesIO()
        cur.execute(f"COPY {esquema}.{t} TO STDOUT WITH (FORMAT csv, HEADER true)", stream=buf)
        (destino / f"{t}.csv").write_bytes(buf.getvalue())
    cur.close()
    con.commit()
    return destino


def migrar(con, esquema: str, exportar_en: Path | None = None) -> list[str]:
    """Crea el esquema si falta y aplica, en una transacción, las migraciones que le faltan. Devuelve las aplicadas."""
    validar_esquema(esquema)
    todas = migraciones()
    tiene = aplicadas(con, esquema)
    if tiene != [n for n, _ in todas][:len(tiene)]:
        raise VersionDistinta(f"el esquema {esquema} tiene migraciones que el código no conoce: {tiene}")
    faltan = todas[len(tiene):]
    if not faltan:
        con.commit()
        return []
    if tablas(con, esquema):
        exportar(con, esquema, exportar_en or RUTAS.datos / "exportaciones" / esquema /
                 f"antes_de_{faltan[0][0]}_{time.strftime('%Y%m%dT%H%M%S')}")
    cur = con.cursor()
    try:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {esquema}")
        cur.execute(f"SET LOCAL search_path TO {esquema}")
        cur.execute("CREATE TABLE IF NOT EXISTS migracion_aplicada (nombre text PRIMARY KEY, "
                    "aplicada timestamptz NOT NULL DEFAULT now())")
        for nombre, sql in faltan:
            cur.execute(sql)
            cur.execute("INSERT INTO migracion_aplicada (nombre) VALUES (%s)", (nombre,))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        cur.close()
    return [n for n, _ in faltan]


# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Registro de corridas: migraciones, versión, ping y exportación.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("migrar", "version", "exportar"):
        p = sub.add_parser(c)
        p.add_argument("--entorno", required=True)
        if c == "exportar":
            p.add_argument("--destino", type=Path)
    sub.add_parser("ping")
    a = ap.parse_args(argv)
    con = conectar()
    try:
        if a.cmd == "ping":
            cur = con.cursor()
            cur.execute("SELECT current_user, version(), now()")
            usuario, version, ahora = cur.fetchone()
            print(f"ok: {usuario} | {version.split(',')[0]} | {ahora:%Y-%m-%d %H:%M:%S %Z}")
        elif a.cmd == "migrar":
            hechas = migrar(con, a.entorno)
            print(f"{a.entorno}: " + (f"aplicadas {hechas}" if hechas else "al día"))
        elif a.cmd == "version":
            print(f"{a.entorno}: {comprobar_version(con, a.entorno)}")
        elif a.cmd == "exportar":
            d = a.destino or RUTAS.datos / "exportaciones" / a.entorno / time.strftime("%Y%m%dT%H%M%S")
            print(exportar(con, a.entorno, d))
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
