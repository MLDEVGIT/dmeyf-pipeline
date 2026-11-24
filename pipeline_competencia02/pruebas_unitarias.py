"""Pruebas pequeñas de esquema, monitoreo de columnas y política de incidentes.

Uso: python -m unittest pipeline_competencia02.pruebas_unitarias -v
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import duckdb

from . import incidentes as I
from .ejecutar_mes import perfil_mes

ESPERADO = ["numero_de_cliente", "foto_mes", "a", "b", "c", "d"]


class DiagnosticoEsquema(unittest.TestCase):
    def test_identico(self):
        d = I.diagnosticar_esquema(ESPERADO, ESPERADO)
        self.assertTrue(d["identico"] and d["mismo_conjunto"])
        self.assertFalse(d["orden_distinto"] or d["faltantes"] or d["adicionales"])

    def test_faltante_no_es_cambio_de_orden(self):
        # el escenario 'ausente' de la prueba de robustez: antes decía "mismo orden=False"
        d = I.diagnosticar_esquema([c for c in ESPERADO if c != "b"], ESPERADO)
        self.assertEqual(d["faltantes"], ["b"])
        self.assertFalse(d["orden_distinto"])
        self.assertFalse(d["mismo_conjunto"])

    def test_mismo_conjunto_otro_orden(self):
        cab = ["numero_de_cliente", "foto_mes", "b", "a", "c", "d"]
        d = I.diagnosticar_esquema(cab, ESPERADO)
        self.assertTrue(d["mismo_conjunto"])
        self.assertTrue(d["orden_distinto"])
        self.assertFalse(d["identico"] or d["faltantes"] or d["adicionales"])
        self.assertEqual(d["columnas_fuera_de_orden"], ["b", "a"])

    def test_adicional_al_final_no_es_cambio_de_orden(self):
        d = I.diagnosticar_esquema(ESPERADO + ["extra"], ESPERADO)
        self.assertEqual(d["adicionales"], ["extra"])
        self.assertFalse(d["orden_distinto"])

    def test_faltante_y_desorden_a_la_vez(self):
        d = I.diagnosticar_esquema(["numero_de_cliente", "foto_mes", "c", "a", "d"], ESPERADO)
        self.assertEqual(d["faltantes"], ["b"])
        self.assertTrue(d["orden_distinto"])

    def test_repetidas_y_target(self):
        d = I.diagnosticar_esquema(ESPERADO + ["a", "clase_ternaria"], ESPERADO)
        self.assertEqual(d["repetidas"], ["a"])
        self.assertEqual(d["targets"], ["clase_ternaria"])


class Clasificacion(unittest.TestCase):
    def test_categorias(self):
        self.assertEqual(I.clasificar_columna(10, 0, 0, 0), "nula_100")
        self.assertEqual(I.clasificar_columna(10, 4, 4, 1), "observados_en_cero")
        self.assertEqual(I.clasificar_columna(10, 10, 0, 1), "constante_no_nula")
        self.assertEqual(I.clasificar_columna(10, 3, 0, 1), "constante_no_nula")  # con nulos
        self.assertIsNone(I.clasificar_columna(10, 10, 5, 2))  # ceros y otro valor: variable normal
        self.assertIsNone(I.clasificar_columna(10, 10, 0, 7))


class PoliticaIncidentes(unittest.TestCase):
    def test_configuracion_real(self):
        p = I.Politica()
        rechazar = {k for k, r in p.reglas.items() if r["accion"] == "rechazar"}
        advertir = {k for k, r in p.reglas.items() if r["accion"] == "advertir"}
        self.assertTrue({"claves_nulas", "claves_duplicadas", "mes_distinto_del_pedido", "mes_fuera_de_secuencia",
                         "columnas_faltantes"} <= rechazar)
        self.assertTrue({"columna_100_nula", "observados_en_cero", "constante_no_nula"} <= advertir)

    def test_configuracion_invalida(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "mala.json"
            p.write_text(json.dumps({"version": 1, "reglas": {"x": {"tipo": "validacion", "accion": "borrar",
                                                                      "criterio": "?"}}}), encoding="utf-8")
            with self.assertRaises(ValueError):
                I.Politica(p)

    def test_advertir_no_corta_y_rechazar_corta_con_todos(self):
        p = I.Politica()
        p.registrar("observados_en_cero", ["a"])
        p.cortar_si_rechazo()  # no corta
        p.registrar("columnas_faltantes", ["b"])
        p.registrar("orden_de_columnas_distinto", ["c", "d"])
        with self.assertRaises(I.Rechazo) as cm:
            p.cortar_si_rechazo()
        self.assertEqual([i["regla"] for i in cm.exception.incidentes],
                         ["columnas_faltantes", "orden_de_columnas_distinto"])

    def test_estado_calidad(self):
        p = I.Politica()
        self.assertEqual(p.estado_calidad(), "no_evaluada")
        p.calidad_evaluada = True
        p.registrar("estrategia_provisional", ["cupo_fijo"], "provisional")  # informativo: no cuenta
        self.assertEqual(p.estado_calidad(), "sin_alertas")
        p.registrar("constante_no_nula", ["a"])
        self.assertEqual(p.estado_calidad(), "con_alertas")


class PerfilMes(unittest.TestCase):
    def test_perfil_sintetico(self):
        with tempfile.TemporaryDirectory() as d:
            prev = (Path(d) / "prev.parquet").as_posix()
            con = duckdb.connect()
            con.execute("""CREATE TABLE actual AS SELECT i AS numero_de_cliente, 202001 AS foto_mes,
                           NULL::DOUBLE AS nula, CASE WHEN i % 2 = 0 THEN 0 END AS ceros,
                           CASE WHEN i % 3 = 0 THEN 7 END AS cte, i % 5 AS normal, 0.0 AS cero_total
                           FROM range(100) t(i)""")
            con.execute(f"COPY (SELECT i AS numero_de_cliente, 201912 AS foto_mes, 1.0 AS nula, 1 AS ceros, "
                        f"7 AS cte, i AS normal, 1.0 AS cero_total FROM range(100) t(i)) TO '{prev}' (FORMAT parquet)")
            pol = I.Politica()
            cols = ["nula", "ceros", "cte", "normal", "cero_total"]
            faltantes, cats = perfil_mes(con, "actual", cols, prev, 100, pol)
            self.assertEqual(cats, {"nula_100": ["nula"], "observados_en_cero": ["cero_total", "ceros"],
                                    "constante_no_nula": ["cte"]})
            reglas = {i["regla"]: i for i in pol.incidentes}
            self.assertEqual(reglas["constante_no_nula"]["detalle"], {"valores": {"cte": 7.0}})
            self.assertTrue(all(i["accion"] == "advertir" for i in pol.incidentes))
            self.assertEqual(sorted(reglas["cambio_tasa_nulos"]["variables"]), ["ceros", "cte", "nula"])
            self.assertEqual(pol.estado_calidad(), "con_alertas")
            self.assertEqual(faltantes["celdas"], 100 + 50 + 66)


if __name__ == "__main__":
    unittest.main()
