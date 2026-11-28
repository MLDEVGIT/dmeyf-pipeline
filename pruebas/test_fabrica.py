"""Fábrica con datos sintéticos: plan del catálogo, reanudación por modelo, interrupción y manifiesto."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from entrenamiento import fabrica as F

PARAMS = dict(learning_rate=0.1, num_leaves=7, min_data_in_leaf=5, max_bin=31, data_random_seed=1,
              deterministic=True, force_col_wise=True, verbosity=-1)


def catalogo():
    def modelos(pref, semillas):
        return [{"semilla": s, "archivo": f"{pref}/semilla_{s}.txt", "sha256": "x" * 64} for s in semillas]
    return {"target": {"sha256": "t"}, "target_version": 2, "estrategias": [
        {"id": "bin", "objetivo": "binary", "num_class": None, "params": PARAMS, "rondas": 5,
         "modelos": modelos("bin", [1, 2, 3])},
        {"id": "multi", "objetivo": "multiclass", "num_class": 3, "params": PARAMS, "rondas": 5,
         "modelos": modelos("multi", [1, 2])},
        {"id": "bin_corto", "objetivo": "binary", "num_class": None, "params": PARAMS, "rondas": 5,
         "modelos": modelos("bin", [1, 2])}]}  # comparte modelos con "bin", como ce02_b20m10 con ce02


def datos():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(400, 4))
    clase = np.where(X[:, 0] > 1, 2, np.where(X[:, 1] > 1.2, 1, 0)).astype("int8")
    return X, clase, ["a", "b", "c", "d"]


class TestFabrica(unittest.TestCase):
    def test_plan_sin_repetidos(self):
        p = F.plan(catalogo())
        self.assertEqual([r["archivo"] for r in p], ["bin/semilla_1.txt", "bin/semilla_2.txt", "bin/semilla_3.txt",
                                                     "multi/semilla_1.txt", "multi/semilla_2.txt"])

    def test_reanuda_sin_reentrenar_y_es_determinista(self):
        X, clase, nombres = datos()
        with tempfile.TemporaryDirectory() as d:
            destino = Path(d)
            p = F.plan(catalogo())
            primero = F.entrenar(p, X, clase, nombres, destino, hilos=1)
            self.assertTrue(all(h["origen"] == "fabrica" for h in primero))
            mtimes = {h["archivo"]: (destino / h["archivo"]).stat().st_mtime_ns for h in primero}
            (destino / "multi/semilla_2.txt").unlink()
            segundo = F.entrenar(p, X, clase, nombres, destino, hilos=1)
            origen = {h["archivo"]: h["origen"] for h in segundo}
            self.assertEqual(origen.pop("multi/semilla_2.txt"), "fabrica")
            self.assertEqual(set(origen.values()), {"reanudado"})
            for a in origen:
                self.assertEqual((destino / a).stat().st_mtime_ns, mtimes[a])
            # determinista: el modelo reentrenado es idéntico byte a byte
            self.assertEqual({h["archivo"]: h["sha256"] for h in primero}, {h["archivo"]: h["sha256"] for h in segundo})
            self.assertIn("feature_names=a b c d", (destino / "bin/semilla_1.txt").read_text())

    def test_interrumpida_y_relanzada(self):
        X, clase, nombres = datos()
        with tempfile.TemporaryDirectory() as d:
            destino = Path(d)
            p = F.plan(catalogo())

            def cortar(info):
                if info["archivo"] == "bin/semilla_2.txt":
                    raise KeyboardInterrupt
            with self.assertRaises(KeyboardInterrupt):
                F.entrenar(p, X, clase, nombres, destino, hilos=1, al_terminar=cortar)
            self.assertEqual(sorted(x.name for x in destino.rglob("*") if x.is_file()), ["semilla_1.txt", "semilla_2.txt"])
            hechos = F.entrenar(p, X, clase, nombres, destino, hilos=1)
            self.assertEqual([h["origen"] for h in hechos], ["reanudado", "reanudado", "fabrica", "fabrica", "fabrica"])
            self.assertFalse(list(destino.rglob("*.tmp-*")))

    def test_manifiesto(self):
        X, clase, nombres = datos()
        with tempfile.TemporaryDirectory() as d:
            cat = catalogo()
            hechos = F.entrenar(F.plan(cat), X, clase, nombres, Path(d), hilos=1)
            man = F.manifiesto(cat, hechos, "tc01")
            sha = {h["archivo"]: h["sha256"] for h in hechos}
            for e in man["estrategias"]:
                for m in e["modelos"]:
                    self.assertEqual(m["sha256"], sha[m["archivo"]])
                    self.assertEqual(m["sha256_equipo"], "x" * 64)
            self.assertFalse(man["fabrica"]["todos_iguales_al_equipo"])
            self.assertEqual(cat["estrategias"][0]["modelos"][0]["sha256"], "x" * 64)  # no toca el original
            json.dumps(man)


if __name__ == "__main__":
    unittest.main()


class TestCandadoDeMeses(unittest.TestCase):
    def test_mes_de_2020_en_la_configuracion_corta_antes_de_entrenar(self):
        from unittest import mock
        with mock.patch.object(F, "cargar_entrenamiento") as cargar, mock.patch.object(F, "entrenar") as entrenar, \
                tempfile.TemporaryDirectory() as d:
            with self.assertRaises(F.MesNoPermitido):
                F.main(["--catalogo", "tc01", "--modelos", d, "--meses", "201905", "202001"])
            cargar.assert_not_called()
            entrenar.assert_not_called()
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_carga_tambien_rechaza(self):
        with self.assertRaises(F.MesNoPermitido):
            F.cargar_entrenamiento(["a"], (201912, 202003))

    def test_meses_de_2019_pasan(self):
        self.assertEqual(F.comprobar_meses([201903, 201912]), (201903, 201912))

    def test_clase_de_201910_solo_en_la_evaluacion_final(self):
        import duckdb
        from evaluacion import particiones as P
        con = duckdb.connect()
        with self.assertRaises(PermissionError):
            P.leer_target(con, "no_importa.parquet", [201910])
        with self.assertRaises(PermissionError):
            F.cargar_entrenamiento(["a"], (201906, 201910))
