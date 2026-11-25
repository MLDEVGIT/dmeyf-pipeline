"""Reglas de corte de CE01 (experimentos/ce01_estabilidad_corte.py) contra el minimax de evaluacion.ganancia.

python -m unittest discover -s pruebas -t . -v
"""
import unittest

import numpy as np

from evaluacion import ganancia as G
from experimentos import ce01_estabilidad_corte as CE
from experimentos.e01_binario_vs_multiclase import FRACCIONES


def curva_sintetica(n, pico, ancho, ruido, semilla):
    rng = np.random.default_rng(semilla)
    k = np.arange(1, n + 1)
    g = 1e8 * np.exp(-((k - pico) / ancho) ** 2) + rng.normal(0, ruido, n).cumsum() * 0.01
    return G.suavizar(g)


class TestReglas(unittest.TestCase):
    def setUp(self):
        self.n = {1: 130000, 2: 132000}
        self.gs = {1: curva_sintetica(130000, 4000, 2500, 1e5, 1), 2: curva_sintetica(132000, 5200, 2500, 1e5, 2)}

    def test_tau_cero_es_el_minimax(self):
        f_lib, _ = G.corte_minimax(self.gs, self.n, FRACCIONES)
        p = CE.peor(CE.arrep(self.gs, self.n))
        self.assertEqual(CE.elegir(p, 0.0), f_lib)

    def test_mve_es_la_menor_fraccion_dentro_de_la_tolerancia_y_monotona(self):
        p = CE.peor(CE.arrep(self.gs, self.n))
        previa = 1.0
        for t in (0.0, 0.005, 0.01, 0.02, 0.05):
            f = CE.elegir(p, t)
            i = CE.idx(f)
            self.assertLessEqual(p[i], np.nanmin(p) + t + 1e-12)
            self.assertTrue(np.all(p[:i] > np.nanmin(p) + t))  # ninguna fracción menor está dentro
            self.assertLessEqual(f, previa)                     # más tolerancia, nunca más envíos
            previa = f

    def test_tramos(self):
        m = np.zeros(len(FRACCIONES), bool)
        m[3:6] = True
        m[10] = True
        self.assertEqual(CE.tramos(m), [[float(FRACCIONES[3]), float(FRACCIONES[5])],
                                        [float(FRACCIONES[10]), float(FRACCIONES[10])]])
        m[:] = False
        m[-2:] = True
        self.assertEqual(CE.tramos(m), [[float(FRACCIONES[-2]), float(FRACCIONES[-1])]])


if __name__ == "__main__":
    unittest.main()
