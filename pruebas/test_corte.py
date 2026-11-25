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


class TestCE02(unittest.TestCase):
    def test_reduccion_rho_cero_es_la_curva_original_y_formula_exacta(self):
        from experimentos.ce02_analisis import curva_rho
        rng = np.random.default_rng(3)
        score, cli = rng.random(2000), np.arange(2000)
        b2 = rng.random(2000) < 0.05
        g = G.curva(score, b2, cli)
        np.testing.assert_array_equal(curva_rho(g, 0.0), g)
        tp = np.cumsum(b2[G.orden(score, cli)])
        k = np.arange(1, 2001)
        # tolerancia absoluta de un centavo: cerca de cero la relativa falla por redondeo de (1 − 0,33)
        np.testing.assert_allclose(curva_rho(g, 0.33), G.PREMIO_BRUTO * 0.67 * tp - G.COSTO_ENVIO * k, rtol=0, atol=0.01)

    def test_reduccion_coincide_con_el_promedio_de_simulaciones(self):
        """La fórmula exacta es la esperanza de borrar cada BAJA+2 con probabilidad ρ (scores fijos)."""
        from experimentos.ce02_analisis import curva_rho
        rng = np.random.default_rng(4)
        score, cli = rng.random(500), np.arange(500)
        b2 = rng.random(500) < 0.2
        sims = [G.curva(score, b2 & (rng.random(500) >= 0.5), cli) for _ in range(4000)]
        np.testing.assert_allclose(np.mean(sims, axis=0), curva_rho(G.curva(score, b2, cli), 0.5),
                                   atol=0.04 * G.PREMIO_BRUTO * b2.sum())

    def test_composiciones_registradas(self):
        from experimentos import ce02_composicion as C
        comp = C.composiciones()
        self.assertEqual(C.SEMILLAS[:5], [20261124 + i for i in range(5)])
        self.assertEqual(sorted(sum(comp["disjuntos"]["5"], [])), list(range(20)))
        for N in ("5", "10"):
            subs = comp["aleatorios"][N]
            self.assertEqual(len({tuple(s) for s in subs}), 200)
            self.assertTrue(all(len(s) == int(N) and len(set(s)) == int(N) for s in subs))
        self.assertEqual(comp, C.composiciones())  # determinista


if __name__ == "__main__":
    unittest.main()
