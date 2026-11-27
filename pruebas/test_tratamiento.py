"""E06 (docs/PLAN_PRUEBAS.md § 19): detector `cero_anomalo`, tratamientos y resultado versionado de la simulación.

python -m unittest discover -s pruebas -t . -v
"""
import json
import unittest

import duckdb

from pipeline_competencia02 import tratamiento as T
from pipeline_competencia02.config import RAIZ

TIPOS = [("numero_de_cliente", "INTEGER"), ("foto_mes", "INTEGER"), ("x", "INTEGER"), ("y", "DOUBLE")]


class TestDetector(unittest.TestCase):
    def test_mes_menos(self):
        self.assertEqual([T.mes_menos(202001, k) for k in (0, 1, 2, 13)], [202001, 201912, 201911, 201812])

    def test_detecta_con_E_suficiente(self):
        r = T.detectar({"x": (1000, 0)}, {201908: {"x": (1000, 500)}}, 201909)
        self.assertEqual([d["columna"] for d in r["detectadas"]], ["x"])
        self.assertEqual(r["detectadas"][0]["esperados_no_cero"], 500.0)

    def test_no_detecta_poca_actividad(self):
        r = T.detectar({"x": (1000, 0)}, {201908: {"x": (1000, 20)}}, 201909)  # E = 20 < 30
        self.assertEqual(r["detectadas"], [])
        self.assertTrue(r["no_detectadas"][0]["motivo"].startswith("E <"))

    def test_consecutiva_usa_mes_anterior_con_actividad(self):
        hist = {201908: {"x": (1000, 0)}, 201907: {"x": (1000, 900)}}
        r = T.detectar({"x": (1000, 0)}, hist, 201909)
        self.assertEqual(r["detectadas"][0]["mes_referencia"], 201907)

    def test_sin_referencia_en_3_meses_no_detecta(self):
        hist = {201908: {"x": (0, 0)}, 201907: {"x": (0, 0)}, 201906: {"x": (0, 0)}, 201905: {"x": (10, 9)}}
        r = T.detectar({"x": (1000, 0)}, hist, 201909)
        self.assertEqual(r["detectadas"], [])
        self.assertTrue(r["no_detectadas"][0]["motivo"].startswith("sin actividad"))

    def test_columna_con_actividad_o_vacia_no_se_evalua(self):
        r = T.detectar({"x": (1000, 1), "y": (0, 0)}, {201908: {"x": (1000, 500), "y": (1000, 500)}}, 201909)
        self.assertEqual(r, {"detectadas": [], "no_detectadas": []})


class TestTratamientos(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect()
        self.con.execute("CREATE TABLE h2 AS SELECT * FROM (VALUES (1, 201907, 10, 1.0), (2, 201907, 20, 2.0)) "
                         "t(numero_de_cliente, foto_mes, x, y)")
        self.con.execute("CREATE TABLE h1 AS SELECT * FROM (VALUES (3, 201908, 0, 3.0), (1, 201908, 11, 1.0)) "
                         "t(numero_de_cliente, foto_mes, x, y)")
        self.con.execute("CREATE TABLE a AS SELECT * FROM (VALUES (5, 201909, NULL, 5.0), (1, 201909, 0, 1.5), "
                         "(3, 201909, 0, 3.5), (2, 201909, 0, 2.5), (4, 201909, 0, 4.5)) t(numero_de_cliente, foto_mes, x, y)")
        self.hist = {201908: "h1", 201907: "h2"}

    def correr(self, metodo, tratadas=None):
        s = T.sql_tratado("a", TIPOS, ["x"], metodo, 201909, self.hist, tratadas or {})
        return None if s is None else self.con.execute(s).fetchall()

    def test_advertir_no_cambia(self):
        self.assertIsNone(self.correr("advertir"))
        self.assertIsNone(T.sql_tratado("a", TIPOS, [], "ultimo_valor", 201909, self.hist, {}))

    def test_faltantes(self):
        filas = self.correr("faltantes")
        self.assertTrue(all(f[2] is None for f in filas))
        self.assertEqual([f[3] for f in filas], [5.0, 1.5, 3.5, 2.5, 4.5])  # otras columnas intactas

    def test_ultimo_valor(self):
        filas = self.correr("ultimo_valor")
        self.assertEqual([f[0] for f in filas], [5, 1, 3, 2, 4])  # orden de llegada
        self.assertEqual({f[0]: f[2] for f in filas}, {5: None,  # nulo de origen
                                                       1: 11,    # t-1
                                                       3: 0,     # 0 legítimo de t-1
                                                       2: 20,    # t-2
                                                       4: None})  # cliente nuevo
        c = T.conteos(self.con, "a", ["x"], "ultimo_valor", 201909, self.hist, {})
        self.assertEqual((c["celdas_observadas"], c["imputadas_antiguedad_1"], c["imputadas_antiguedad_2"],
                          c["a_null_sin_valor_valido"], c["clientes_sin_observaciones_recientes"]), (4, 2, 1, 1, 2))

    def test_ultimo_valor_saltea_meses_tratados(self):
        filas = self.correr("ultimo_valor", {201908: {"x"}})
        self.assertEqual({f[0]: f[2] for f in filas}[1], 10)  # 201908 tratado: usa 201907
        filas = self.correr("ultimo_valor", {201908: {"x"}, 201907: {"x"}})
        self.assertTrue(all(f[2] is None for f in filas))  # tres meses tratados seguidos: NULL

    def test_metodo_invalido(self):
        with self.assertRaises(ValueError):
            T.sql_tratado("a", TIPOS, ["x"], "otro", 201909)


class TestResultadoE06(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = json.loads((RAIZ / "resultados" / "e06_simulacion_2019.json").read_text(encoding="utf-8"))
        cls.d = json.loads((RAIZ / "resultados" / "e06_deteccion.json").read_text(encoding="utf-8"))

    def test_controles_de_la_simulacion(self):
        for c in self.r["controles"].values():
            self.assertTrue(c["features_iguales_a_features_2019"])
            self.assertTrue(all(v["identico"] for v in c["ensamble_igual_al_promedio_de_ce02"].values()))

    def test_catalogo_y_meses(self):
        self.assertEqual(self.r["catalogo"]["nombre"], "ce02_b20m10")
        self.assertEqual(sorted({c["mes"] for c in self.r["celdas"]}), [201908, 201909])

    def test_detector_en_2019(self):
        reales = {m: [x["columna"] for x in v["detectadas"]] for m, v in self.d["meses"].items() if v["detectadas"]}
        self.assertEqual(sorted(reales), ["201904", "201905"])
        self.assertNotIn("201910", self.d["meses"])
        self.assertTrue(self.r["detector"]["ok"])

    def test_regla_de_adopcion(self):
        c = self.r["criterio"]
        for met in ("faltantes", "ultimo_valor"):
            self.assertEqual(c[met]["cumple"], all(c[met]["condiciones"].values()))
        self.assertFalse(c["faltantes"]["cumple"])
        self.assertFalse(c["ultimo_valor"]["condiciones"]["2_binario_cada_celda"])
        self.assertEqual(self.r["eleccion"], "advertir")


if __name__ == "__main__":
    unittest.main()
