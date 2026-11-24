"""Estrategias de envío: deciden a qué clientes enviar a partir de las probabilidades.

Una estrategia recibe sólo clientes y probabilidades del mes: nunca el target.
Así no puede elegir la cantidad de envíos mirando las etiquetas.

Estrategias actuales (las dos provisionales, sin optimización comercial):
  A  cupo_fijo:1000   los 1.000 clientes de mayor probabilidad. PRINCIPAL,
                      elegida de antemano: define la salida oficial.
  B  porcentaje:1     el 1 % de los clientes del mes, redondeado hacia arriba.

Las dos usan el MISMO score (el modelo de 05) y el mismo orden: probabilidad
descendente y, a igual probabilidad, numero_de_cliente ascendente. Sólo
difieren en cuántos clientes toman de ese orden, así que el conjunto menor
está siempre contenido en el mayor. No tiene sentido compararlas por AUC:
el AUC es una propiedad del score, que es idéntico para ambas.

Para agregar otra: subclase de Estrategia y alta en REGISTRO.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

ESTRATEGIAS_REQUERIDAS = 2


class Estrategia(ABC):
    nombre: str
    provisional: bool = False
    nota: str = ""

    @abstractmethod
    def seleccionar(self, clientes: np.ndarray, probabilidad: np.ndarray) -> np.ndarray:
        """Devuelve un array bool, alineado con `clientes`, con True = enviar."""

    def describir(self) -> dict:
        return {"nombre": self.nombre, "clase": type(self).__name__, "provisional": self.provisional,
                "nota": self.nota, **self.parametros()}

    def parametros(self) -> dict:
        return {}


def orden_por_score(clientes: np.ndarray, probabilidad: np.ndarray) -> np.ndarray:
    """Índices por probabilidad descendente; a igual probabilidad, numero_de_cliente ascendente."""
    return np.lexsort((clientes, -probabilidad))


class CupoFijo(Estrategia):
    """Envía a los `cupo` clientes de mayor probabilidad."""

    nombre = "cupo_fijo"

    def __init__(self, cupo: int, provisional: bool = True,
                 nota: str = "cupo explícito de prueba técnica; provisional, sin validación comercial"):
        if cupo <= 0:
            raise ValueError("el cupo debe ser positivo")
        self.cupo, self.provisional, self.nota = int(cupo), provisional, nota

    def parametros(self) -> dict:
        return {"cupo": self.cupo}

    def seleccionar(self, clientes: np.ndarray, probabilidad: np.ndarray) -> np.ndarray:
        if self.cupo > len(clientes):
            raise ValueError(f"cupo {self.cupo} mayor que la cantidad de clientes ({len(clientes)})")
        enviar = np.zeros(len(clientes), bool)
        enviar[orden_por_score(clientes, probabilidad)[:self.cupo]] = True
        return enviar


class PorcentajeClientes(Estrategia):
    """Envía al `porcentaje` % de los clientes del mes con mayor probabilidad, redondeado hacia arriba."""

    nombre = "porcentaje"

    def __init__(self, porcentaje: int, provisional: bool = True,
                 nota: str = "porcentaje provisional, sin optimización comercial"):
        if not 0 < porcentaje <= 100:
            raise ValueError("el porcentaje debe estar en (0, 100]")
        self.porcentaje, self.provisional, self.nota = int(porcentaje), provisional, nota

    def parametros(self) -> dict:
        return {"porcentaje": self.porcentaje}

    def cantidad(self, n_clientes: int) -> int:
        return -(-n_clientes * self.porcentaje // 100)  # techo en aritmética entera

    def seleccionar(self, clientes: np.ndarray, probabilidad: np.ndarray) -> np.ndarray:
        enviar = np.zeros(len(clientes), bool)
        enviar[orden_por_score(clientes, probabilidad)[:self.cantidad(len(clientes))]] = True
        return enviar


REGISTRO = {
    "cupo_fijo": lambda arg: CupoFijo(int(arg)),
    "porcentaje": lambda arg: PorcentajeClientes(int(arg)),
}


def construir(especificacion: str) -> Estrategia:
    """'nombre:parametro' -> instancia. Ej.: 'cupo_fijo:1000'."""
    nombre, _, arg = especificacion.partition(":")
    if nombre not in REGISTRO:
        raise ValueError(f"estrategia desconocida {nombre!r}; disponibles: {sorted(REGISTRO)}")
    return REGISTRO[nombre](arg)
