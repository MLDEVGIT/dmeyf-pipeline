"""Reporte HTML de seguimiento, detector cero_anomalo en el circuito mensual y puntos de la curva de ganancia.

python -m unittest discover -s pruebas -t . -v
"""
import json
import re
import tempfile
import unittest
from pathlib import Path

import duckdb
import numpy as np

from pipeline_competencia02 import incidentes as I
from pipeline_competencia02 import reporte_html as H
from pipeline_competencia02 import retrospectiva as R
from pipeline_competencia02.mensual import detectar_cero_anomalo


def escribir(p: Path, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def estrategia(rol, id_, envios):
    return {"id": id_, "rol": rol, "fraccion": 0.0235, "envios": envios, "probabilidad_minima_enviada": 0.07,
            "semillas": [1, 2], "modelos_sha256": ["a" * 64, "b" * 64], "score_corto": "x",
            "distribucion": {"media": 0.01, "mayor_0_5": 3, "exactamente_0": 0, "exactamente_1": 0,
                             "cuantiles": {"0.5": 0.001, "0.9": 0.01, "0.99": 0.2}}}


def ejecucion_falsa(raiz: Path):
    escribir(raiz / "entorno.json", {"nombre": "prueba", "catalogo": {"nombre": "ce02_b20m10", "sha256": "c" * 64},
                                     "esquema_crudo": [["numero_de_cliente", "BIGINT"], ["foto_mes", "BIGINT"], ["x", "BIGINT"]]})
    for mes, calidad in ((202001, "sin_alertas"), (202002, "con_alertas")):
        rep = {"mes": mes, "estado_calidad": calidad, "validacion": {"clientes": 1000, "historia_meses": [201901, 201912]},
               "features": {"clientes_sin_historia": 10, "con_lag1": 990, "con_lag2": 980},
               "verificacion_features": {"lags": {"clientes_con_algun_lag_distinto_del_calendario": 2}},
               "faltantes": {"celdas": 50, "columnas_con_faltantes": 1,
                             "ceros": {"celdas": 300, "celdas_observadas": 1000}},
               "categorias_columnas": {"observados_en_cero": ["x"]} if calidad == "con_alertas" else {},
               "deteccion_cero_anomalo": {"detectadas": [{"columna": "x", "esperados_no_cero": 500.0, "mes_referencia": 202001}]}
               if calidad == "con_alertas" else {"detectadas": []},
               "incidentes": [{"regla": "cero_anomalo", "variables": ["x"]}, {"regla": "observados_en_cero", "variables": ["x"]}]
               if calidad == "con_alertas" else [],
               "tiempos": {"validacion_s": 10, "features_s": 20, "inferencia_b_s": 100, "inferencia_m_s": 150},
               "coincidencia": {"jaccard": 0.7, "interseccion": 20, "solo_recomendacion": 3, "solo_alternativa": 5,
                                "correlacion_de_rangos": 0.97},
               "catalogo": {"sha256": "c" * 64}, "politica_incidentes": {"version": 3},
               "metricas_con_target": {"estado": "pendiente", "requiere_listas_de": "t+1 y t+2"},
               "estrategias": [estrategia("recomendacion_provisional", "b", 24), estrategia("alternativa", "m", 28)]}
        escribir(raiz / "diagnosticos" / str(mes) / "reporte.json", rep)
        escribir(raiz / "registro" / "meses" / f"{mes}.json", {"mes": mes, "estado": "completado", "intentos": [{}],
                                                                "total_desde_entrada_s": 470.0 if mes == 202002 else 300.0})
    curva = {"envios": [1, 24, 50], "ganancia": [1_072_500, 3_000_000, -500_000]}
    escribir(raiz / "registro" / "retrospectiva" / "202001.json", {
        "disponibilidad": {"estado": "completa", "falta": []}, "clases": {"BAJA+2": 9},
        "estrategias": [{"rol": "recomendacion_provisional", "id": "b", "envios": 24, "baja2_enviados": 3,
                         "ganancia": 2_640_000, "auc_baja2": 0.93, "ganancia_maxima_ex_post": 3_000_000,
                         "envios_ganancia_maxima_ex_post": 24, "curva": curva},
                        {"rol": "alternativa", "id": "m", "envios": 28, "baja2_enviados": 3, "ganancia": 2_530_000,
                         "auc_baja2": 0.92, "ganancia_maxima_ex_post": 3_000_000, "envios_ganancia_maxima_ex_post": 24,
                         "curva": curva}]})
    escribir(raiz / "registro" / "retrospectiva" / "202002.json", {"disponibilidad": {"estado": "pendiente",
                                                                                      "falta": ["202003", "202004"]}})


class TestReporteHTML(unittest.TestCase):
    """El generador (datos + HTML); la lógica y el dibujo del tablero se prueban en test_tablero.py."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        raiz = Path(cls.tmp.name)
        ejecucion_falsa(raiz)
        cls.d = H.datos(raiz)
        cls.p = H.generar(raiz)
        cls.html = cls.p.read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_meses_y_ubicacion(self):
        self.assertEqual(self.p.name, "reporte_seguimiento.html")
        self.assertIn('data-meses="202001,202002"', self.html)

    def test_autocontenido_sin_red(self):
        self.assertIsNone(re.search(r'(src|href)\s*=\s*"(https?:)?//', self.html))
        self.assertIsNone(re.search(r"<script[^>]*\ssrc=", self.html))
        self.assertNotIn("<link", self.html)
        self.assertNotIn("@import", self.html)
        self.assertNotIn("fetch(", self.html)

    def test_datos_incrustados_son_los_generados(self):
        js = re.search(r'<script id="datos" type="application/json">(.*?)</script>', self.html, re.S).group(1)
        self.assertEqual(json.loads(js.replace("<\\/", "</"))["meses"], json.loads(json.dumps(self.d["meses"])))

    def test_limites_importes_y_scores(self):
        self.assertEqual((self.d["limites"]["limite_s"], self.d["limites"]["margen_s"]), (900, 450))
        self.assertEqual((self.d["importes"]["premio"], self.d["importes"]["costo"]), (1_100_000, 27_500))
        self.assertIn("pendiente", self.d["importes"]["estado_c02"])
        sc = {e["rol"]: e["score"] for e in self.d["catalogo"]["estrategias"]}
        self.assertEqual(sc, {"recomendacion_provisional": "P(BAJA+1 ∪ BAJA+2)", "alternativa": "P(BAJA+2)"})

    def test_pendiente_no_es_cero(self):
        m1, m2 = self.d["meses"]
        self.assertEqual(m1["target"]["estado"], "completa")
        self.assertEqual(m1["estr"]["recomendacion_provisional"]["retro"]["ganancia"], 2_640_000)
        self.assertEqual(m2["target"], {"estado": "pendiente", "falta": [202003, 202004]})
        self.assertIsNone(m2["estr"]["recomendacion_provisional"]["retro"])

    def test_alertas_y_tiempos(self):
        m2 = self.d["meses"][1]
        self.assertEqual({a["regla"] for a in m2["alertas"]}, {"cero_anomalo", "observados_en_cero"})
        self.assertEqual(m2["deteccion"]["detectadas"][0]["columna"], "x")
        self.assertEqual(m2["total_s"], 470.0)
        self.assertAlmostEqual(sum(v or 0 for v in m2["etapas"].values()), 470.0, places=1)


class TestDetectorEnElCircuito(unittest.TestCase):
    def test_registra_alerta_y_no_cambia_el_dato(self):
        con = duckdb.connect()
        con.execute("CREATE TABLE actual AS SELECT range AS numero_de_cliente, 0 AS x FROM range(100)")
        with tempfile.TemporaryDirectory() as d:
            h = (Path(d) / "foto_mes=202001.parquet").as_posix()
            con.execute(f"COPY (SELECT range AS numero_de_cliente, 5 AS x FROM range(100)) TO '{h}' (FORMAT parquet)")
            pol = I.Politica()
            antes = con.execute("SELECT sum(x), count(x) FROM actual").fetchone()
            r = detectar_cero_anomalo(con, [h], 202002, {"observados_en_cero": ["x"]}, pol)
            self.assertEqual([x["columna"] for x in r["detectadas"]], ["x"])
            self.assertEqual(con.execute("SELECT sum(x), count(x) FROM actual").fetchone(), antes)
            inc = [i for i in pol.incidentes if i["regla"] == "cero_anomalo"]
            self.assertEqual((inc[0]["accion"], inc[0]["tipo"], inc[0]["variables"]), ("advertir", "calidad_datos", ["x"]))
            self.assertEqual(pol.estado_calidad(), "con_alertas")

    def test_sin_candidatas_no_lee_historia(self):
        r = detectar_cero_anomalo(None, ["no/existe/foto_mes=202001.parquet"], 202002, {}, I.Politica())
        self.assertEqual((r["candidatas"], r["detectadas"]), (0, []))

    def test_regla_en_la_politica(self):
        pol = I.Politica()
        self.assertEqual(pol.reglas["cero_anomalo"]["accion"], "advertir")
        self.assertEqual(pol.umbrales["cero_anomalo"]["esperados_min"], 30)


class TestCurva(unittest.TestCase):
    def test_puntos_incluyen_corte_y_maximo(self):
        g = np.cumsum(np.where(np.arange(5000) < 300, 1_072_500, -27_500)).astype(np.int64)
        c = R.puntos_curva(g, [117, 300])
        self.assertIn(117, c["envios"])
        self.assertIn(300, c["envios"])
        self.assertEqual(c["ganancia"][c["envios"].index(300)], int(g[299]))
        self.assertEqual(c["envios"], sorted(c["envios"]))


if __name__ == "__main__":
    unittest.main()
