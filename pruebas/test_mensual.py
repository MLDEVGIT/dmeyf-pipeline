"""Pruebas del pipeline mensual con dos estrategias, sin datos reales.

python -m unittest discover -s pruebas -t . -v
"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import lightgbm as lgb
import numpy as np

from evaluacion.ganancia import envios
from pipeline_competencia02 import incidentes as I
from pipeline_competencia02 import mensual as M
from pipeline_competencia02 import preparar_ejecucion as PE
from pipeline_competencia02.catalogo import copiar_con_nombres
from pipeline_competencia02.ejecutar_mes import Entorno
from pipeline_competencia02.estrategias import FraccionClientes

RAIZ = Path(__file__).resolve().parents[1]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class TestEstrategiaYCoincidencia(unittest.TestCase):
    def test_fraccion_usa_el_redondeo_del_protocolo(self):
        e = FraccionClientes(0.029, nombre="x")
        for n in (142929, 131775, 1000, 7):
            self.assertEqual(e.cantidad(n), envios(0.029, n))
        cli = np.array([5, 3, 9, 1])
        prob = np.array([0.2, 0.9, 0.9, 0.1])
        d = FraccionClientes(0.5, nombre="x").seleccionar(cli, prob)
        np.testing.assert_array_equal(d, [False, True, True, False])  # empate en 0,9: ambos entran

    def test_desempate_por_cliente(self):
        d = FraccionClientes(0.25, nombre="x").seleccionar(np.array([9, 3, 7, 1]), np.array([0.5, 0.5, 0.5, 0.5]))
        np.testing.assert_array_equal(d, [False, False, False, True])  # cliente 1 primero

    def test_coincidencia(self):
        a = np.array([1, 1, 0, 0], bool)
        b = np.array([1, 0, 1, 0], bool)
        c = M.coincidencia(a, b, np.array([4., 3, 2, 1]), np.array([4., 3, 2, 1]))
        self.assertEqual((c["interseccion"], c["solo_recomendacion"], c["solo_alternativa"]), (1, 1, 1))
        self.assertAlmostEqual(c["jaccard"], 1 / 3, places=5)
        self.assertAlmostEqual(c["correlacion_de_rangos"], 1.0)

    def test_meses(self):
        self.assertEqual(M.siguiente(201912), 202001)
        self.assertEqual(PE.meses_entre(201911, 202002), [201911, 201912, 202001, 202002])


class TestCatalogo(unittest.TestCase):
    def test_copia_con_nombres_predice_igual(self):
        rng = np.random.default_rng(0)
        X = rng.normal(size=(300, 4))
        y = (X[:, 0] > 0).astype(int)
        b = lgb.train({"objective": "binary", "verbosity": -1, "num_leaves": 4}, lgb.Dataset(X, y), 5)
        with tempfile.TemporaryDirectory() as d:
            o, c = Path(d) / "o.txt", Path(d) / "c.txt"
            b.save_model(str(o))
            copiar_con_nombres(o, c, ["a", "b", "c", "d"])
            self.assertEqual(lgb.Booster(model_file=str(c)).feature_name(), ["a", "b", "c", "d"])
            # idéntica al original salvo la línea feature_names (los fines de línea se conservan tal cual)
            lo, lc = o.read_bytes().split(b"\n"), c.read_bytes().split(b"\n")
            distintas = [i for i, (x, y) in enumerate(zip(lo, lc)) if x != y]
            self.assertEqual(len(lo), len(lc))
            self.assertEqual(len(distintas), 1)
            self.assertTrue(lc[distintas[0]].startswith(b"feature_names="))


def reporte_falso(mes: int, rec_envios: int = 10) -> dict:
    estr = []
    for rol, ide in ((M.ROL_OFICIAL, "rec"), (M.ROL_ALTERNATIVA, "alt")):
        estr.append({"id": ide, "rol": rol, "score_corto": "s", "fraccion": 0.03, "envios": rec_envios,
                     "probabilidad_minima_enviada": 0.1, "modelos_sha256": ["a" * 64],
                     "distribucion": {"cuantiles": {"0.5": 0.01, "0.99": 0.2}, "media": 0.02, "exactamente_0": 0,
                                      "exactamente_1": 0}})
    return {"ejecucion": f"e{mes}", "estado": "completado", "estado_calidad": "sin_alertas",
            "validacion": {"clientes": 100}, "features": {"clientes_sin_historia": 1},
            "verificacion_features": {"lags": {"clientes_con_algun_lag_distinto_del_calendario": 2}},
            "incidentes": [], "categorias_columnas": {}, "faltantes": {"celdas": 0}, "estrategias": estr,
            "coincidencia": {"interseccion": 8, "solo_recomendacion": 2, "solo_alternativa": 2, "jaccard": 0.67,
                             "correlacion_de_rangos": 0.9},
            "metricas_con_target": {"estado": "pendiente", "requiere_listas_de": "x y z"},
            "catalogo": {"sha256": "b" * 64}, "tiempos": {"total_hasta_publicacion_s": 1.0},
            "memoria": {"pico_working_set_mb": 1.0}}


class TestReintentosYReporte(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        for d in ("output", "historia", "diagnosticos", "registro/meses"):
            (self.raiz / d).mkdir(parents=True)
        (self.raiz / "entorno.json").write_text(json.dumps({"nombre": "t", "esquema_crudo": [], "historia": {"meses": {}}}))
        self.env = Entorno(self.raiz)

    def tearDown(self):
        self.tmp.cleanup()

    def publicar_falso(self, mes: int, rep: dict | None = None):
        r = M.rutas_mes(self.env, mes)
        r["diagnostico"].mkdir()
        (r["diagnostico"] / f"decisiones_{mes}.csv").write_text("d\n")
        r["historia"].write_bytes(b"h")
        r["salida"].write_text("numero_de_cliente,probabilidad,enviar\n")
        rep = rep or reporte_falso(mes)
        rep["integridad"] = {"salida": sha(r["salida"]), "historia": sha(r["historia"]),
                             "decisiones": sha(r["diagnostico"] / f"decisiones_{mes}.csv")}
        (r["diagnostico"] / "reporte.json").write_text(json.dumps(rep))
        return r

    def test_sin_publicacion(self):
        self.assertEqual(M.reconciliar(self.env, 202001, "x", I.Politica()), "nada")

    def test_publicado_integro_se_recupera(self):
        self.publicar_falso(202001)
        pol = I.Politica()
        self.assertEqual(M.reconciliar(self.env, 202001, "x", pol), "recuperado")
        self.assertEqual(pol.incidentes[0]["regla"], "mes_recuperado")

    def test_publicado_alterado_va_a_cuarentena(self):
        r = self.publicar_falso(202001)
        r["salida"].write_text("cambiado\n")
        self.assertEqual(M.reconciliar(self.env, 202001, "x", I.Politica()), "cuarentena")
        self.assertFalse(any(p.exists() for p in r.values()))
        self.assertTrue((self.raiz / "diagnosticos" / "202001.cuarentena-x" / "churn_202001.csv").exists())

    def test_pieza_suelta_va_a_cuarentena(self):
        M.rutas_mes(self.env, 202001)["historia"].write_bytes(b"h")
        self.assertEqual(M.reconciliar(self.env, 202001, "x", I.Politica()), "cuarentena")

    def test_reporte_una_fila_por_mes_completado(self):
        for mes, estado in ((202002, "completado"), (202001, "completado"), (202003, "fallido")):
            if estado == "completado":
                self.publicar_falso(mes)
            (self.raiz / "registro" / "meses" / f"{mes}.json").write_text(json.dumps({"mes": mes, "estado": estado}))
        p = M.regenerar_reporte(self.env)
        primera = p.read_text(encoding="utf-8")
        M.regenerar_reporte(self.env)
        self.assertEqual(primera, p.read_text(encoding="utf-8"))  # regenerar no duplica
        filas = primera.strip().split("\n")[1:]
        self.assertEqual([f.split(",")[0] for f in filas], ["202001", "202002"])
        self.assertIn("pendiente", primera)
        self.assertIn("True", filas[0])  # integridad_ok


class TestNoLeeEtiquetas(unittest.TestCase):
    def test_modulos_nuevos_no_leen_target(self):
        for f in ("pipeline_competencia02/mensual.py", "pipeline_competencia02/preparar_ejecucion.py",
                  "pipeline_competencia02/catalogo.py"):
            texto = (RAIZ / f).read_text(encoding="utf-8")
            for prohibido in ("target_2019", "leer_target", "_target.parquet"):
                self.assertNotIn(prohibido, texto, f"{f} menciona {prohibido}")


if __name__ == "__main__":
    unittest.main()
