"""Catálogo candidato ce02 y respaldo ce02_b20m10 (docs/PLAN_PRUEBAS.md § 15), contra lo registrado por CE02.

Lee sólo archivos versionados (catalogo/, resultados/). python -m unittest discover -s pruebas -t . -v
"""
import json
import unittest

import numpy as np

from pipeline_competencia02 import catalogo as K
from pipeline_competencia02.config import RAIZ
from pipeline_competencia02.estrategias import FraccionClientes


def leer(p):
    return json.loads(p.read_text(encoding="utf-8"))


class TestCatalogoCE02(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ce02 = leer(K.archivo("ce02"))
        cls.b20m10 = leer(K.archivo("ce02_b20m10"))
        cls.tc01 = leer(K.archivo("tc01"))
        cls.comp = leer(RAIZ / "resultados" / "ce02_composicion.json")

    def test_el_activo_sigue_siendo_tc01(self):
        self.assertEqual(K.ACTIVO, "tc01")

    def test_cortes_y_procedimiento(self):
        por_obj = {e["objetivo"]: e for e in self.ce02["estrategias"]}
        b, m = por_obj["binary"], por_obj["multiclass"]
        self.assertEqual((b["rol"], m["rol"]), ("recomendacion_provisional", "alternativa"))
        self.assertEqual(b["corte"]["fraccion"], 0.0235)
        self.assertEqual(b["corte"]["minimax_ensamble_20"], 0.03675)  # el minimax original queda registrado
        self.assertEqual(b["corte"]["minimax_ensamble_5"], 0.04475)
        self.assertIn("mínimo volumen equivalente", b["corte"]["procedimiento"])
        self.assertEqual(m["corte"]["fraccion"], 0.02725)

    def test_semillas_son_el_prefijo_registrado(self):
        semillas = self.comp["semillas"]
        for cat, tam in ((self.ce02, {"binary": 20, "multiclass": 20}), (self.b20m10, {"binary": 20, "multiclass": 10})):
            for e in cat["estrategias"]:
                self.assertEqual([x["semilla"] for x in e["modelos"]], semillas[:tam[e["objetivo"]]])
                self.assertEqual(cat["composicion"]["por_estrategia"][e["id"]]["indices"], list(range(tam[e["objetivo"]])))
                self.assertTrue(all(x["rondas"] == 300 for x in e["modelos"]))
            self.assertEqual(cat["target"]["version"], 2)
            self.assertEqual(cat["features"]["sha256_nombres"], self.tc01["features"]["sha256_nombres"])

    def test_las_5_primeras_son_los_modelos_de_tc01(self):
        for e, et in zip(self.ce02["estrategias"], self.tc01["estrategias"]):
            self.assertEqual(e["objetivo"], et["objetivo"])
            self.assertEqual([x["sha256"] for x in e["modelos"][:5]], [x["sha256"] for x in et["modelos"]])

    def test_respaldo_comparte_el_binario(self):
        b = {e["objetivo"]: e for e in self.b20m10["estrategias"]}
        c = {e["objetivo"]: e for e in self.ce02["estrategias"]}
        sha = lambda e, n=None: [x["sha256"] for x in e["modelos"]][:n]  # noqa: E731
        self.assertEqual(b["binary"]["modelos"], c["binary"]["modelos"])
        self.assertEqual(sha(b["multiclass"]), sha(c["multiclass"], 10))
        self.assertIn("nota_tamano", b["multiclass"]["corte"])


class TestCorteMulticlase10CA02(unittest.TestCase):
    """§ 17: el 2,725 % del multiclase de ce02_b20m10 está respaldado por el ensamble de 10 (semillas 0–9) en 2019."""

    @classmethod
    def setUpClass(cls):
        cls.r = leer(RAIZ / "resultados" / "ca02_corte_multiclase_10.json")
        cls.b20m10 = leer(K.archivo("ce02_b20m10"))

    def test_corte_del_catalogo_es_el_evaluado(self):
        m = next(e for e in self.b20m10["estrategias"] if e["objetivo"] == "multiclass")
        self.assertEqual(m["corte"]["fraccion"], self.r["corte_evaluado"])
        self.assertEqual(self.r["fuente"]["indices"], list(range(10)))

    def test_dentro_del_conjunto_equivalente_de_10(self):
        f = self.r["corte_evaluado"]
        self.assertTrue(self.r["respaldado"])
        self.assertTrue(any(a <= f <= b for a, b in self.r["conjunto_equivalente_10"]["tramos"]))
        self.assertLessEqual(self.r["peor_arrepentimiento"]["corte_evaluado"],
                             self.r["conjunto_equivalente_10"]["umbral_peor_arrepentimiento"])

    def test_reproduce_lo_registrado_por_ce02(self):
        self.assertTrue(all(self.r["consistencia_con_ce02"].values()))


class TestCondicionesMaquina(unittest.TestCase):
    def test_condiciones_registra_lo_necesario(self):
        from pipeline_competencia02.correr_meses import condiciones
        c = condiciones()
        if c.get("disponible") is False:
            self.skipTest("psutil no instalado")
        for k in ("frecuencia_mhz", "carga_cpu_pct", "ram_libre_gb", "enchufada", "plan_energia"):
            self.assertIn(k, c)


class TestSeleccionCA01(unittest.TestCase):
    def test_seleccion_igual_a_la_estrategia_del_pipeline(self):
        from experimentos.ca01_separar_efectos import seleccion
        rng = np.random.default_rng(5)
        cli = rng.permutation(10_000).astype(np.int64)
        score = np.round(rng.random(10_000), 3)  # con empates
        for f in (0.0235, 0.02725, 0.04475):
            np.testing.assert_array_equal(seleccion(score, cli, f), FraccionClientes(f).seleccionar(cli, score))


if __name__ == "__main__":
    unittest.main()
