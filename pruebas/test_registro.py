"""Registro en el Postgres local (docker compose up -d): migraciones, versión, exportación y reintentos.

Si la base local no responde, las pruebas se saltean (en GitHub Actions corre como servicio).
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline_competencia02 import registro as R

URL = os.environ.get("DMEYF_PG_URL_PRUEBAS", "postgresql://dmeyf:dmeyf@localhost:5433/dmeyf")


def base_local():
    try:
        with mock.patch.dict(os.environ, {"DMEYF_PG_URL": URL}):
            return R.conectar(intentos=1)
    except R.BaseInalcanzable:
        return None


def hay_base_local() -> bool:
    con = base_local()
    if con is None:
        return False
    con.close()
    return True


@unittest.skipIf(not hay_base_local(), "sin Postgres local (docker compose up -d)")
class TestMigraciones(unittest.TestCase):
    def setUp(self):
        self.esquema = f"pruebas_t{os.getpid()}"
        self.con = base_local()

    def tearDown(self):
        self.con.rollback()
        cur = self.con.cursor()
        cur.execute(f"DROP SCHEMA IF EXISTS {self.esquema} CASCADE")
        self.con.commit()
        self.con.close()

    def test_aplicar_dos_veces_y_version(self):
        with self.assertRaises(R.VersionDistinta):
            R.comprobar_version(self.con, self.esquema)
        primera = R.migrar(self.con, self.esquema)
        self.assertEqual(primera, [n for n, _ in R.migraciones()])
        self.assertEqual(R.migrar(self.con, self.esquema), [])
        self.assertEqual(R.comprobar_version(self.con, self.esquema), primera)
        self.assertTrue({"corrida", "etapa", "evento", "control_calidad", "envios", "publicacion",
                         "medicion_eventual", "migracion_aplicada"} <= set(R.tablas(self.con, self.esquema)))

    def test_esquema_de_otra_version_se_rechaza(self):
        R.migrar(self.con, self.esquema)
        cur = self.con.cursor()
        cur.execute(f"INSERT INTO {self.esquema}.migracion_aplicada (nombre) VALUES ('9999_del_futuro')")
        self.con.commit()
        with self.assertRaises(R.VersionDistinta):
            R.comprobar_version(self.con, self.esquema)
        with self.assertRaises(R.VersionDistinta):
            R.migrar(self.con, self.esquema)

    def test_horas_con_zona_y_una_sola_corrida_en_curso_por_mes(self):
        R.migrar(self.con, self.esquema)
        R.usar_esquema(self.con, self.esquema)
        cur = self.con.cursor()
        cur.execute("SELECT data_type FROM information_schema.columns WHERE table_schema = %s AND column_name = 'inicio'"
                    " AND table_name = 'corrida'", (self.esquema,))
        self.assertEqual(cur.fetchone()[0], "timestamp with time zone")
        ins = "INSERT INTO corrida (tipo, mes, quien, maquina, pid) VALUES ('mensual', 202001, 'a', 'm', 1)"
        cur.execute(ins)
        self.con.commit()
        with self.assertRaises(Exception):
            cur.execute(ins)
        self.con.rollback()

    def test_exportar_antes_de_migrar(self):
        with tempfile.TemporaryDirectory() as d:
            R.migrar(self.con, self.esquema)
            R.usar_esquema(self.con, self.esquema)
            cur = self.con.cursor()
            cur.execute("INSERT INTO corrida (tipo, mes, quien, maquina, pid) VALUES ('prueba', 202001, 'a', 'm', 1)")
            self.con.commit()
            destino = R.exportar(self.con, self.esquema, Path(d) / "exp")
            texto = (destino / "corrida.csv").read_text()
            self.assertIn("prueba", texto)
            self.assertTrue((destino / "migracion_aplicada.csv").exists())


class TestConexion(unittest.TestCase):
    def test_se_rinde_despues_de_los_intentos(self):
        with mock.patch.dict(os.environ, {"DMEYF_PG_URL": "postgresql://x:y@127.0.0.1:1/z"}), \
                mock.patch.object(R, "_conectar_url", side_effect=OSError("rechazada")) as c, \
                mock.patch.object(R.time, "sleep"):
            with self.assertRaises(R.BaseInalcanzable):
                R.conectar(intentos=3)
            self.assertEqual(c.call_count, 3)

    def test_nombre_de_esquema(self):
        for malo in ("Produccion", "pruebas-agus", "1x", "x; drop table corrida", ""):
            with self.assertRaises(ValueError):
                R.validar_esquema(malo)
        self.assertEqual(R.validar_esquema("pruebas_agustina"), "pruebas_agustina")


if __name__ == "__main__":
    unittest.main()
