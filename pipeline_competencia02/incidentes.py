"""Política central de incidentes y diagnósticos puros que la alimentan.

La acción de cada regla sale de politica_incidentes.json, no del código:
  rechazar  corta la ejecución sin publicar nada (estado operativo fallido);
  advertir  registra el incidente y sigue, sin cambiar score, features ni selección.

Además del estado operativo (completado/fallido), cada ejecución tiene un
estado de calidad separado: con_alertas si se activó alguna regla de tipo
calidad_datos o calidad_scores, sin_alertas si no, y no_evaluada si la
ejecución terminó antes de evaluar la calidad. "completado" sólo significa
que la ejecución terminó y publicó; no garantiza calidad predictiva.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

CONFIG = Path(__file__).with_name("politica_incidentes.json")
ACCIONES = {"rechazar", "advertir"}
TIPOS = {"validacion", "calidad_datos", "calidad_scores", "informativo"}
TIPOS_DE_CALIDAD = {"calidad_datos", "calidad_scores"}
TARGETS = {"clase_ternaria", "clase_binaria", "horizonte_completo"}
AVISO = ("estado operativo 'completado' = la ejecución terminó y publicó; no garantiza calidad predictiva. "
         "La calidad se informa aparte (estado_calidad e incidentes).")


class Rechazo(Exception):
    def __init__(self, incidentes: list[dict]):
        self.incidentes = incidentes
        super().__init__("; ".join(f"{i['regla']}: {i['variables'] or i['detalle']}" for i in incidentes))


class Politica:
    def __init__(self, path: Path = CONFIG):
        texto = Path(path).read_text(encoding="utf-8")
        cfg = json.loads(texto)
        for nombre, r in cfg["reglas"].items():
            if r.get("accion") not in ACCIONES or r.get("tipo") not in TIPOS or not r.get("criterio"):
                raise ValueError(f"regla {nombre!r} mal configurada: {r}")
        self.cfg, self.reglas, self.umbrales = cfg, cfg["reglas"], cfg.get("umbrales", {})
        self.sha256 = hashlib.sha256(texto.encode("utf-8")).hexdigest()
        self.incidentes: list[dict] = []
        self.calidad_evaluada = False
        self._pendientes: list[dict] = []

    def registrar(self, regla: str, variables=(), detalle=None) -> dict:
        r = self.reglas[regla]  # una regla desconocida es un error de programación
        inc = {"regla": regla, "tipo": r["tipo"], "accion": r["accion"], "variables": list(variables),
               "detalle": detalle, "criterio": r["criterio"]}
        self.incidentes.append(inc)
        if r["accion"] == "rechazar":
            self._pendientes.append(inc)
        return inc

    def cortar_si_rechazo(self):
        """Después de registrar los incidentes de una etapa: si alguno pide rechazar, corta con todos juntos."""
        if self._pendientes:
            pend, self._pendientes = self._pendientes, []
            raise Rechazo(pend)

    def estado_calidad(self) -> str:
        if any(i["tipo"] in TIPOS_DE_CALIDAD for i in self.incidentes):
            return "con_alertas"
        return "sin_alertas" if self.calidad_evaluada else "no_evaluada"

    def textos(self) -> list[str]:
        return [f"[{i['accion']}] {i['regla']}: " + (f"{len(i['variables'])} variable(s) {i['variables']}"
                                                     if i["variables"] else str(i["detalle"]))
                for i in self.incidentes]

    def resumen(self) -> dict:
        return {"configuracion": CONFIG.name, "version": self.cfg["version"], "sha256": self.sha256}


def diagnosticar_esquema(cabecera: list[str], esperado: list[str]) -> dict:
    """Separa faltantes, adicionales, repetidas, targets y orden distinto.

    El orden se compara sólo entre las columnas presentes en ambos lados, así
    que una columna faltante o adicional no se informa también como cambio de
    orden. Igualdad de conjuntos e igualdad de orden son cosas distintas.
    """
    cab_set, esp_set = set(cabecera), set(esperado)
    repetidas = sorted({c for c in cabecera if cabecera.count(c) > 1})
    comunes_cab = [c for c in dict.fromkeys(cabecera) if c in esp_set]
    comunes_esp = [c for c in esperado if c in cab_set]
    return {
        "faltantes": [c for c in esperado if c not in cab_set],
        "adicionales": [c for c in dict.fromkeys(cabecera) if c not in esp_set],
        "repetidas": repetidas,
        "targets": sorted(c for c in cab_set if c in TARGETS or "clase" in c.lower()),
        "mismo_conjunto": cab_set == esp_set,
        "orden_distinto": comunes_cab != comunes_esp,
        "columnas_fuera_de_orden": [c for c, e in zip(comunes_cab, comunes_esp) if c != e],
        "identico": cabecera == esperado,
    }


def clasificar_columna(filas: int, no_nulos: int, ceros: int, distintos: int) -> str | None:
    """Categoría disjunta de una columna en un mes: nula_100, observados_en_cero, constante_no_nula o None."""
    if filas == 0:
        return None
    if no_nulos == 0:
        return "nula_100"
    if ceros == no_nulos:
        return "observados_en_cero"
    if distintos == 1:
        return "constante_no_nula"
    return None


REGLA_POR_CATEGORIA = {"nula_100": "columna_100_nula", "observados_en_cero": "observados_en_cero",
                       "constante_no_nula": "constante_no_nula"}
