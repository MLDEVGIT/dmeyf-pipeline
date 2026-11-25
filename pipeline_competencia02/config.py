"""Rutas de datos del pipeline, leídas de configuración (nunca fijas en el código).

Orden de precedencia para cada ruta:
  1. variable de entorno (DMEYF_DATOS, DMEYF_ENTORNOS, ...);
  2. archivo de configuración: DMEYF_CONFIG o, si no está, `config.toml` en la raíz del repo;
  3. valor por defecto relativo a `datos`.

`config.toml` es local y no se versiona; copiar `config.ejemplo.toml` y ajustar.
Las rutas relativas del archivo se resuelven respecto de la raíz del repo.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

# clave -> (variable de entorno, valor por defecto relativo a `datos`, o None si es relativo a la raíz)
_CLAVES = {
    "datos": ("DMEYF_DATOS", None),
    "historico_2019": ("DMEYF_HISTORICO_2019", "competencia_02/competencia_02_2019.parquet"),
    "crudo": ("DMEYF_CRUDO", "competencia_02/competencia_02_crudo.csv.gz"),
    "insumos": ("DMEYF_INSUMOS", "pipeline_competencia02/insumos"),
    "entornos": ("DMEYF_ENTORNOS", "pipeline_competencia02/entornos"),
    "auditoria_2019": ("DMEYF_AUDITORIA_2019", None),
    "features_2019": ("DMEYF_FEATURES_2019", "competencia_02/competencia_02_2019_features"),
    "target_2019": ("DMEYF_TARGET_2019", "competencia_02/competencia_02_2019_target.parquet"),
    # regla versión 2 (evaluacion/target.py), generado por experimentos/tc01_target_2019.py; el anterior se conserva
    "target_2019_v2": ("DMEYF_TARGET_2019_V2", "pipeline_competencia02/target_2019_v2.parquet"),
    "modelos": ("DMEYF_MODELOS", "pipeline_competencia02/modelos"),
}


@dataclass(frozen=True)
class Rutas:
    datos: Path
    historico_2019: Path
    crudo: Path
    insumos: Path
    entornos: Path
    auditoria_2019: Path
    features_2019: Path
    target_2019: Path
    target_2019_v2: Path
    modelos: Path
    archivo: Path | None


def _abs(valor: str | os.PathLike) -> Path:
    p = Path(valor).expanduser()
    return (p if p.is_absolute() else RAIZ / p).resolve()


def cargar() -> Rutas:
    archivo = Path(os.environ["DMEYF_CONFIG"]) if os.environ.get("DMEYF_CONFIG") else RAIZ / "config.toml"
    tabla: dict = {}
    if archivo.exists():
        tabla = tomllib.loads(archivo.read_text(encoding="utf-8")).get("rutas", {})
    else:
        archivo = None

    def valor(clave: str) -> str | None:
        var, _ = _CLAVES[clave]
        return os.environ.get(var) or tabla.get(clave)

    datos = _abs(valor("datos") or "datos")
    out = {"datos": datos, "archivo": archivo}
    for clave, (_, defecto) in _CLAVES.items():
        if clave == "datos":
            continue
        v = valor(clave)
        if v:
            out[clave] = _abs(v)
        elif clave == "auditoria_2019":
            out[clave] = RAIZ / "referencia" / "01_filas_por_mes.csv"
        else:
            out[clave] = (datos / defecto).resolve()
    return Rutas(**out)


RUTAS = cargar()


def mostrar(p: Path) -> str:
    """Ruta legible para reportes: relativa a la raíz del repo o a `datos` si se puede; si no, absoluta."""
    p = Path(p).resolve()
    for base in (RAIZ, RUTAS.datos):
        try:
            return p.relative_to(base).as_posix()
        except ValueError:
            pass
    return p.as_posix()


if __name__ == "__main__":
    for k, v in RUTAS.__dict__.items():
        estado = "" if k == "archivo" else ("ok" if v and Path(v).exists() else "NO EXISTE")
        print(f"{k:15s} {v}  {estado}")
