"""Ejecutor de etapas: corre una lista de etapas en orden sobre un contexto, mide cada una y corta en la primera falla.

Es el único lugar que sabe de estados y tiempos (diseño, decisión 1). Cada etapa es una función que recibe el
contexto y devuelve su resultado; el ejecutor lo guarda en `ctx.resultados[nombre]` para las etapas siguientes.
Si una etapa lanza una excepción, queda `fallida` con su error y las siguientes quedan `omitidas` sin correr.

Quien quiera enterarse (el registro de corridas, un log, una prueba) se suscribe como oyente: el ejecutor le avisa
al empezar y al terminar cada etapa. Un oyente que falla no cambia el resultado de la etapa, pero sí corta la
corrida, porque un registro que no se escribe no se puede ignorar en silencio.

    etapas = [Etapa("recepcion", recepcion), Etapa("validacion", validacion), ...]
    res = ejecutar(etapas, Contexto(mes=202001, carpeta=Path(...)), oyentes=[registro])
    res.ok, res.etapas[-1].estado
"""
from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

COMPLETADA, FALLIDA, OMITIDA = "completada", "fallida", "omitida"


@dataclass
class Etapa:
    nombre: str
    funcion: Callable[["Contexto"], Any]


@dataclass
class Contexto:
    """Lo que comparten las etapas de una corrida: el mes, la carpeta y los resultados de las etapas anteriores."""
    mes: int | None = None
    carpeta: Path | None = None
    datos: dict = field(default_factory=dict)       # lo que pone quien arma la corrida (argumentos, conexión, …)
    resultados: dict = field(default_factory=dict)  # nombre de etapa -> lo que devolvió


@dataclass
class ResultadoEtapa:
    nombre: str
    estado: str
    inicio: datetime | None = None
    fin: datetime | None = None
    duracion_s: float | None = None
    filas: int | None = None
    error: str | None = None
    traza: str | None = None
    excepcion: BaseException | None = field(default=None, repr=False)


@dataclass
class ResultadoCorrida:
    etapas: list[ResultadoEtapa]

    @property
    def ok(self) -> bool:
        return all(e.estado == COMPLETADA for e in self.etapas)

    @property
    def fallida(self) -> ResultadoEtapa | None:
        return next((e for e in self.etapas if e.estado == FALLIDA), None)

    def tiempos(self) -> dict[str, float]:
        return {e.nombre: e.duracion_s for e in self.etapas if e.duracion_s is not None}


class Oyente(Protocol):
    def al_empezar(self, etapa: str, ctx: Contexto) -> None: ...
    def al_terminar(self, resultado: ResultadoEtapa, ctx: Contexto) -> None: ...


def _filas(valor: Any) -> int | None:
    """Filas que informa una etapa: un entero en la clave o el atributo `filas` de lo que devolvió."""
    f = valor.get("filas") if isinstance(valor, dict) else getattr(valor, "filas", None)
    return int(f) if isinstance(f, (int,)) and not isinstance(f, bool) else None


def ejecutar(etapas: Iterable[Etapa], ctx: Contexto, oyentes: Iterable[Oyente] = (),
             ya_hechas: Iterable[str] = ()) -> ResultadoCorrida:
    """Corre las etapas en orden. Las de `ya_hechas` no se corren (un reintento que retoma) y no figuran."""
    etapas, oyentes, hechas = list(etapas), list(oyentes), set(ya_hechas)
    nombres = [e.nombre for e in etapas]
    if len(set(nombres)) != len(nombres):
        raise ValueError(f"etapas con nombre repetido: {nombres}")
    resultados: list[ResultadoEtapa] = []
    cortar = False
    for etapa in etapas:
        if etapa.nombre in hechas:
            continue
        if cortar:
            r = ResultadoEtapa(etapa.nombre, OMITIDA)
            resultados.append(r)
            for o in oyentes:
                o.al_terminar(r, ctx)
            continue
        for o in oyentes:
            o.al_empezar(etapa.nombre, ctx)
        inicio, t0 = datetime.now(timezone.utc), time.perf_counter()
        try:
            valor = etapa.funcion(ctx)
        except Exception as e:  # noqa: BLE001 — la falla de una etapa es un resultado, no un error del ejecutor
            r = ResultadoEtapa(etapa.nombre, FALLIDA, inicio, datetime.now(timezone.utc),
                               round(time.perf_counter() - t0, 3), error=repr(e),
                               traza="".join(traceback.format_exception(e)), excepcion=e)
            cortar = True
        else:
            ctx.resultados[etapa.nombre] = valor
            r = ResultadoEtapa(etapa.nombre, COMPLETADA, inicio, datetime.now(timezone.utc),
                               round(time.perf_counter() - t0, 3), filas=_filas(valor))
        resultados.append(r)
        for o in oyentes:
            o.al_terminar(r, ctx)
    return ResultadoCorrida(resultados)
