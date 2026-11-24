"""Pruebas de evaluacion/comparacion.py con datos sintéticos.

python -m unittest discover -s pruebas -t . -v
"""
import unittest

import numpy as np

from evaluacion import comparacion as C

FRACCIONES = np.round(np.arange(0.01, 0.30 + 1e-12, 0.005), 6)


def sintetico(semilla, ruido, n=4000):
    rng = np.random.default_rng(semilla)
    clase = np.where(rng.random(n) < 0.03, 2, np.where(rng.random(n) < 0.03, 1, 0)).astype("int8")
    clientes = np.arange(n)
    base = (clase == 2) * 1.0 + rng.normal(0, 1, n)
    preds = [1 / (1 + np.exp(-(base + rng.normal(0, ruido, n)))) for _ in range(5)]
    return preds, (clase, clientes)


class TestComparacion(unittest.TestCase):
    def setUp(self):
        self.meses = (1, 2)
        self.bueno = {}, {}
        self.malo = {}, {}
        for m in self.meses:
            pb, meta = sintetico(m, 0.1)
            pm, _ = sintetico(m, 3.0)
            self.bueno[0][m], self.bueno[1][m] = pb, meta
            self.malo[0][m] = pm
        self.meta = self.bueno[1]

    def test_estructura_y_ensamble(self):
        r = C.evaluar_brazo(self.bueno[0], self.meta, FRACCIONES)
        self.assertIn(r["corte"]["fraccion"], FRACCIONES)
        self.assertEqual(len(r["corte"]["fraccion_por_semilla"]), 5)
        for m in self.meses:
            c = r["corte"][str(m)]
            self.assertEqual(len(c["por_semilla"]), 5)
            self.assertEqual(c["envios"], int(np.ceil(r["corte"]["fraccion"] * len(self.meta[m][0]))))
        self.assertEqual(len(r["transferencia"]), 2)

    def test_regla_detecta_mejora(self):
        bueno = C.evaluar_brazo(self.bueno[0], self.meta, FRACCIONES)
        malo = C.evaluar_brazo(self.malo[0], self.meta, FRACCIONES)
        d = C.regla_adopcion(bueno, malo, self.meses, 4)
        self.assertTrue(d["1_ensamble_mayor_en_todos_los_meses"])
        self.assertTrue(d["2_semillas_a_favor_en_cada_mes"])
        inv = C.regla_adopcion(malo, bueno, self.meses, 4)
        self.assertFalse(inv["adopta"])

    def test_identico_no_se_adopta(self):
        r = C.evaluar_brazo(self.bueno[0], self.meta, FRACCIONES)
        d = C.regla_adopcion(r, r, self.meses, 4)
        self.assertFalse(d["adopta"])  # empate: no hay ganancia mayor
        self.assertEqual(d["pareadas"]["1"]["positivas"], 0)


if __name__ == "__main__":
    unittest.main()
