"""Detección de variables rotas (pipeline_competencia02/calidad.py).

Casos sintéticos y la historia de 2019, desde las proporciones versionadas en resultados/c01_calidad_2019.json
(agregados por mes, sin el dataset).
"""
import json
import unittest
from pathlib import Path

import duckdb

from pipeline_competencia02 import calidad

RAIZ = Path(__file__).resolve().parents[1]
RESULTADO = RAIZ / "resultados" / "c01_calidad_2019.json"
U = calidad.umbrales()
RENTABILIDAD_Y_COMISIONES = {"mrentabilidad", "mrentabilidad_annual", "mcomisiones", "ccomisiones_otras",
                             "mcomisiones_otras", "mactivos_margen", "mpasivos_margen"}


def p(ceros, nulos=0.0):
    return {"ceros": ceros, "nulos": nulos}


class Sinteticos(unittest.TestCase):
    def test_variable_toda_en_cero(self):
        hist = [{"x": p(0.30)}, {"x": p(0.32)}, {"x": p(0.31)}]
        d = calidad.detectar({"x": p(1.0)}, hist, U)
        self.assertTrue(d["x"]["rota"])
        self.assertEqual(d["x"]["motivo"], "ceros_casi_todo")

    def test_siempre_casi_toda_cero_no_se_marca(self):
        hist = [{"x": p(0.995)}, {"x": p(0.997)}, {"x": p(0.996)}]
        self.assertFalse(calidad.detectar({"x": p(1.0)}, hist, U)["x"]["rota"])

    def test_salto_de_faltantes(self):
        hist = [{"x": p(0.1, 0.05)}, {"x": p(0.1, 0.04)}]
        d = calidad.detectar({"x": p(0.1, 0.60)}, hist, U)
        self.assertEqual(d["x"]["motivo"], "nulos_salto")

    def test_variable_nueva_no_se_marca(self):
        # vale NULL hasta un mes (sin proporción de ceros) y desde ahí trae valores: no está rota
        hist = [{"x": p(None, 1.0)}, {"x": p(None, 1.0)}]
        self.assertFalse(calidad.detectar({"x": p(0.45, 0.0)}, hist, U)["x"]["rota"])

    def test_primer_mes_sin_historia(self):
        self.assertEqual(calidad.rotas(calidad.detectar({"x": p(1.0)}, [], U)), [])

    def test_baja_de_ceros_no_se_marca(self):
        hist = [{"x": p(0.9)}, {"x": p(0.9)}]
        self.assertFalse(calidad.detectar({"x": p(0.1)}, hist, U)["x"]["rota"])

    def test_proporciones_con_duckdb(self):
        con = duckdb.connect()
        con.execute("CREATE TABLE t AS SELECT * FROM (VALUES (201901, 1, 0, NULL), (201901, 2, 5, NULL), "
                    "(201901, 3, 0, NULL), (201901, 4, NULL, NULL)) v(foto_mes, numero_de_cliente, a, b)")
        props = calidad.proporciones_por_mes(con, "t", ["foto_mes", "numero_de_cliente", "a", "b"])
        self.assertEqual(set(props[201901]), {"a", "b"})
        self.assertAlmostEqual(props[201901]["a"]["ceros"], 2 / 3)   # sobre los observados
        self.assertAlmostEqual(props[201901]["a"]["nulos"], 1 / 4)   # sobre todas las filas
        self.assertIsNone(props[201901]["b"]["ceros"])


class Historia2019(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        res = json.loads(RESULTADO.read_text(encoding="utf-8"))
        cls.props = {int(m): {v: p(c, n) for v, (c, n) in pm.items()} for m, pm in res["proporciones"].items()}
        cls.rotas = calidad.detectar_historia(cls.props, U)

    def test_solo_2019(self):
        self.assertEqual((min(self.props), max(self.props)), (201901, 201912))

    def test_marca_rentabilidad_y_comisiones_en_201905_y_201910(self):
        self.assertTrue(RENTABILIDAD_Y_COMISIONES <= set(self.rotas[201905]), self.rotas[201905])
        self.assertTrue(RENTABILIDAD_Y_COMISIONES <= set(self.rotas[201910]), self.rotas[201910])

    def test_no_marca_las_que_siempre_fueron_casi_todas_cero(self):
        casi_cero = {v for v in self.props[201901]
                     if all((self.props[m][v]["ceros"] or 0) > 0.99 for m in self.props)}
        self.assertGreater(len(casi_cero), 10)
        marcadas = {v for vs in self.rotas.values() for v in vs}
        self.assertEqual(casi_cero & marcadas, set())

    def test_meses_sanos(self):
        for m in (201902, 201908, 201911, 201912):
            self.assertEqual(self.rotas[m], [], m)


if __name__ == "__main__":
    unittest.main()
