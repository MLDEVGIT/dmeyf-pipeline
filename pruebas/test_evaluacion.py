"""Pruebas de evaluacion/ganancia.py y evaluacion/particiones.py (sin datos reales).

python -m unittest discover -s pruebas -t . -v
"""
import unittest

import duckdb
import numpy as np

from evaluacion import ganancia as G
from evaluacion import particiones as P


class TestGanancia(unittest.TestCase):
    def test_desglose(self):
        self.assertEqual(G.GANANCIA_NETA_ACIERTO, 1_072_500)
        self.assertAlmostEqual(G.UMBRAL_EQUILIBRIO, 0.025)

    def test_formas_equivalentes(self):
        rng = np.random.default_rng(0)
        y = rng.random(5000) < 0.01
        s = rng.random(5000)
        ids = np.arange(5000)
        g = G.curva(s, y, ids)
        o = G.orden(s, ids)
        catedra = np.cumsum(np.where(y[o], G.GANANCIA_NETA_ACIERTO, -G.COSTO_ENVIO))
        np.testing.assert_array_equal(g, catedra)

    def test_umbral_de_equilibrio(self):
        # enviar a quien tiene p = 0,025 tiene valor esperado cero
        p = G.UMBRAL_EQUILIBRIO
        self.assertAlmostEqual(p * G.GANANCIA_NETA_ACIERTO - (1 - p) * G.COSTO_ENVIO, 0.0, places=6)

    def test_desempate_por_cliente(self):
        s = np.array([0.5, 0.5, 0.9])
        ids = np.array([30, 10, 20])
        np.testing.assert_array_equal(G.orden(s, ids), [2, 1, 0])

    def test_suavizado(self):
        g = np.arange(10, dtype=float)
        gs = G.suavizar(g, 3)
        self.assertTrue(np.isnan(gs[0]) and np.isnan(gs[-1]))
        np.testing.assert_allclose(gs[1:-1], g[1:-1])

    def test_minimax(self):
        n = {1: 1000, 2: 1000}
        k = np.arange(1, 1001)
        curvas = {1: -((k - 100) ** 2).astype(float), 2: -((k - 300) ** 2).astype(float)}
        curvas = {m: c - c.min() + 1 for m, c in curvas.items()}
        f, _ = G.corte_minimax(curvas, n, np.arange(0.05, 0.5, 0.01))
        self.assertTrue(0.1 < f < 0.3)


class TestParticiones(unittest.TestCase):
    def test_octubre_rechazado(self):
        con = duckdb.connect()
        with self.assertRaises(PermissionError):
            P.leer_target(con, "no_importa.parquet", [201908, 201910])
        with self.assertRaises(PermissionError):
            P.leer_target(con, "no_importa.parquet", [201911])

    def test_particiones_disjuntas(self):
        self.assertFalse(set(P.ENTRENAMIENTO) & set(P.DESARROLLO))
        self.assertFalse(set(P.PERMITIDOS_DESARROLLO) & set(P.EVALUACION_FINAL))


if __name__ == "__main__":
    unittest.main()
