"""Definición única del target (evaluacion/target.py), sin datos reales.

python -m unittest discover -s pruebas -t . -v
"""
import itertools
import unittest

import duckdb
import numpy as np

from evaluacion import target as T
from pipeline_competencia02 import catalogo as K
from pipeline_competencia02 import retrospectiva as R


class TestRegla(unittest.TestCase):
    def test_un_solo_lugar(self):
        self.assertIs(R.etiquetar, T.etiquetar)
        self.assertEqual(R.VERSION, T.VERSION)
        self.assertEqual({k: R.REGLA[k] for k in T.REGLA}, T.REGLA)

    def test_casos(self):
        en1 = np.array([True, True, False, False])
        en2 = np.array([True, False, True, False])
        np.testing.assert_array_equal(T.etiquetar(en1, en2), ["CONTINUA", "BAJA+2", "CONTINUA", "BAJA+1"])

    def test_sql_igual_numpy_en_todos_los_patrones(self):
        """Un cliente por patrón de presencia en t+1, t+2, t+3 (t+3 no debe influir), etiquetado en t=201903."""
        filas, patrones = [], {}
        for i, (p1, p2, p3) in enumerate(itertools.product([0, 1], repeat=3), start=1):
            patrones[i] = (p1, p2)
            filas.append((i, 201903))
            for mes, presente in ((201904, p1), (201905, p2), (201906, p3)):
                if presente:
                    filas.append((i, mes))
        filas.append((99, 201904))  # otro cliente para que existan todos los meses en la fuente
        filas += [(99, 201905), (99, 201906)]
        con = duckdb.connect()
        con.execute("CREATE TABLE pres(numero_de_cliente BIGINT, foto_mes INTEGER)")
        con.executemany("INSERT INTO pres VALUES (?, ?)", filas)
        r = con.execute(T.sql_etiquetas("pres", [201903])).fetchall()
        con.close()
        sql = {c: k for c, _, k in r}
        esperado = {c: T.etiquetar(np.array([bool(p1)]), np.array([bool(p2)]))[0] for c, (p1, p2) in patrones.items()}
        self.assertEqual(sql, esperado)
        # el cliente que vuelve (ausente t+1, presente t+2) es CONTINUA con cualquier t+3
        self.assertEqual({sql[c] for c, p in patrones.items() if p == (0, 1)}, {"CONTINUA"})

    def test_periodo(self):
        self.assertEqual(T.periodo(201912) + 1, T.periodo(202001))


class TestCatalogos(unittest.TestCase):
    def test_registro(self):
        self.assertEqual(set(K.CATALOGOS), {"e01", "tc01", "ce02", "ce02_b20m10"})
        self.assertIn(K.ACTIVO, K.CATALOGOS)
        self.assertEqual(K.archivo("e01"), K.CATALOGO)
        self.assertEqual({K.CATALOGOS[k]["target_version"] for k in K.CATALOGOS}, {1, 2})


if __name__ == "__main__":
    unittest.main()
