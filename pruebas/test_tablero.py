"""Tablero de seguimiento: lógica (Node) y dibujo de las vistas (Chrome sin interfaz).

- Lógica (pipeline_competencia02/tablero/logica.js, con Node): filtros combinados, selección vacía, meses sin target,
  agregación sólo de métricas aditivas, valores pendientes que siguen pendientes al filtrar o agregar meses, estado
  en la URL y formato.
- Dibujo (si hay Chrome): cada vista se dibuja desde el estado de la URL, sin conexión.
python -m unittest discover -s pruebas -t . -v
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from pipeline_competencia02 import reporte_html as H
from pruebas.test_reporte import escribir, estrategia

LOGICA = Path(H.TABLERO / "logica.js").resolve()
NODE = shutil.which("node")
CHROME = next((c for c in (shutil.which("chrome"), shutil.which("google-chrome"), shutil.which("chromium"),
                           r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                           r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe") if c and Path(c).exists()), None)
REC, ALT = "recomendacion_provisional", "alternativa"


def ejecucion(raiz: Path):
    """202001 con target completo, 202002 parcial, 202003 pendiente (con ceros registrados sólo en 202003)."""
    escribir(raiz / "entorno.json", {"nombre": "prueba", "catalogo": {"nombre": "ce02_b20m10", "sha256": "c" * 64},
                                     "esquema_crudo": [["numero_de_cliente", "BIGINT"], ["foto_mes", "BIGINT"], ["x", "BIGINT"]]})
    for mes, envios in ((202001, 24), (202002, 25), (202003, 26)):
        fal = {"celdas": 50, "columnas_con_faltantes": 1, "por_columna": {"x": 200}}
        if mes == 202003:
            fal["ceros"] = {"celdas": 400, "celdas_observadas": 800, "por_columna": {"x": 400}}
        rep = {"mes": mes, "estado_calidad": "sin_alertas", "validacion": {"clientes": 1000, "historia_meses": [201901]},
               "features": {"clientes_sin_historia": 10}, "faltantes": fal, "incidentes": [],
               "tiempos": {"validacion_s": 10, "features_s": 20, "inferencia_b_s": 100, "inferencia_m_s": 150},
               "memoria": {"pico_working_set_mb": 3000}, "coincidencia": {"jaccard": 0.7},
               "versiones": {"python": "3.12.0"} if mes == 202003 else None,
               "estrategias": [estrategia(REC, "b", envios), estrategia(ALT, "m", envios + 4)]}
        escribir(raiz / "diagnosticos" / str(mes) / "reporte.json", rep)
        escribir(raiz / "registro" / "meses" / f"{mes}.json", {"mes": mes, "estado": "completado", "intentos": [{}],
                                                                "total_desde_entrada_s": 300.0})
    curva = {"envios": [1, 24, 50], "ganancia": [1_072_500, 3_000_000, -500_000]}
    escribir(raiz / "registro" / "retrospectiva" / "202001.json", {
        "version": 2, "disponibilidad": {"estado": "completa", "falta": []},
        "clases": {"BAJA+2": 9, "BAJA+1": 5, "CONTINUA": 986, "clientes": 1000, "definitivas": True},
        "estrategias": [{"rol": REC, "id": "b", "envios": 24, "baja2_enviados": 3, "ganancia": 2_640_000, "auc_baja2": 0.93,
                         "ganancia_maxima_ex_post": 3_000_000, "envios_ganancia_maxima_ex_post": 24, "curva": curva},
                        {"rol": ALT, "id": "m", "envios": 28, "baja2_enviados": 2, "ganancia": 1_430_000, "auc_baja2": 0.91,
                         "ganancia_maxima_ex_post": 3_000_000, "envios_ganancia_maxima_ex_post": 24, "curva": curva}]})
    escribir(raiz / "registro" / "retrospectiva" / "202002.json", {
        "disponibilidad": {"estado": "parcial", "falta": ["202004"]}, "provisional": {"ausentes_en_t1": 7},
        "estrategias": [{"rol": REC, "id": "b", "envios": 25, "provisional_ausentes_en_t1_enviados": 2}]})
    escribir(raiz / "registro" / "retrospectiva" / "202003.json", {"disponibilidad": {"estado": "pendiente", "falta": ["202004", "202005"]}})


ESCENARIOS_JS = r"""
const fs = require("fs"); const L = require(process.argv[2]);
const D = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const s = h => L.leerEstado(h, D);
const sel = h => L.seleccionar(D, s(h));
const ag = (h, rol) => L.agregarNegocio(sel(h), rol, D.importes);
const out = {
  todos: sel("").map(m => m.mes), vacio: sel("#m=ninguno").map(m => m.mes),
  combinado: { meses: sel("#m=202001,202003&t=pendiente&e=binario").map(m => m.mes), roles: L.rolesDe(s("#e=binario").e) },
  combinadoSinResultado: sel("#m=202001&t=pendiente").map(m => m.mes),
  agTodos: ag("", L.REC), agPendientes: ag("#t=pendiente", L.REC), agVacio: ag("#m=ninguno", L.REC),
  serieGanancia: L.serie(D.meses, L.REC, L.MET_NEGOCIO.ganancia, D.importes),
  serieAuc: L.serie(D.meses, L.REC, L.MET_NEGOCIO.auc, D.importes),
  serieEnvios: L.serie(D.meses, L.REC, L.MET_NEGOCIO.envios, D.importes),
  url: L.escribirEstado(s("#v=modelo&m=202001,202003&e=multiclase&t=parcial&c=202001")),
  urlVacia: L.escribirEstado(s("#m=ninguno")), invalido: s("#v=xx&m=209901&e=zz&t=qq&c=1"),
  fmt: [L.nd(-1234.56, 1), L.n0(1234567), L.mill(644077500), L.nd(null), L.mesTxt(202006)],
  ceros: D.meses.map(m => L.pctCeros(m, "x")), nulos: D.meses.map(m => L.pctNulos(m, "x")),
  op: L.resumenOperacion(D.meses, D.limites)
};
// agregar un mes nuevo (pendiente): los meses completos y pendientes conservan su estado; envíos suma, ganancia no
const D2 = JSON.parse(JSON.stringify(D)); const nuevo = JSON.parse(JSON.stringify(D.meses[2])); nuevo.mes = 202004;
D2.meses.push(nuevo);
out.agregado = L.agregarNegocio(L.seleccionar(D2, L.leerEstado("", D2)), L.REC, D2.importes);
out.agregadoSerie = L.serie(D2.meses, L.REC, L.MET_NEGOCIO.ganancia, D2.importes).map(p => [p.mes, p.valor, p.estado]);
console.log(JSON.stringify(out));
"""


@unittest.skipUnless(NODE, "Node no está instalado")
class TestLogica(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        raiz = Path(cls.tmp.name)
        ejecucion(raiz)
        cls.D = H.datos(raiz)
        f = raiz / "datos.json"
        f.write_text(json.dumps(cls.D), encoding="utf-8")
        js = raiz / "escenarios.js"
        js.write_text(ESCENARIOS_JS, encoding="utf-8")
        r = subprocess.run([NODE, str(js), str(LOGICA), str(f)], capture_output=True, text=True, encoding="utf-8", timeout=60)
        if r.returncode:
            raise RuntimeError(r.stderr)
        cls.o = json.loads(r.stdout)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_seleccion_y_filtros_combinados(self):
        self.assertEqual(self.o["todos"], [202001, 202002, 202003])
        self.assertEqual(self.o["combinado"], {"meses": [202003], "roles": [REC]})
        self.assertEqual(self.o["combinadoSinResultado"], [])

    def test_seleccion_vacia(self):
        self.assertEqual(self.o["vacio"], [])
        a = self.o["agVacio"]
        self.assertEqual((a["envios"], a["ganancia"], a["baja2"], a["costo"]), (None, None, None, None))

    def test_solo_metricas_aditivas_y_solo_meses_con_target(self):
        a = self.o["agTodos"]
        self.assertEqual(a["envios"], 24 + 25 + 26)
        self.assertEqual(a["costo"], (24 + 25 + 26) * 27_500)
        self.assertEqual((a["ganancia"], a["baja2"], a["completos"]), (2_640_000, 3, [202001]))
        self.assertEqual(a["sinTarget"], [{"mes": 202002, "estado": "parcial"}, {"mes": 202003, "estado": "pendiente"}])

    def test_meses_sin_target_siguen_pendientes(self):
        a = self.o["agPendientes"]
        self.assertIsNone(a["ganancia"])  # pendiente, no 0
        self.assertEqual(a["envios"], 26)
        g = self.o["serieGanancia"]
        self.assertEqual([(p["valor"], p["estado"]) for p in g], [(2.64, "ok"), (None, "parcial"), (None, "pendiente")])
        self.assertEqual([p["valor"] for p in self.o["serieEnvios"]], [24, 25, 26])  # no requiere target

    def test_auc_por_mes_sin_promedio(self):
        self.assertEqual([p["valor"] for p in self.o["serieAuc"]], [0.93, None, None])

    def test_agregar_un_mes(self):
        a = self.o["agregado"]
        self.assertEqual((a["envios"], a["ganancia"]), (24 + 25 + 26 + 26, 2_640_000))
        self.assertEqual(self.o["agregadoSerie"][-2:], [[202003, None, "pendiente"], [202004, None, "pendiente"]])

    def test_estado_en_la_url(self):
        self.assertEqual(self.o["url"], "#v=modelo&m=202001,202003&e=multiclase&t=parcial&c=202001")
        self.assertEqual(self.o["urlVacia"], "#v=negocio&m=ninguno&e=ambas&t=todos")
        self.assertEqual(self.o["invalido"], {"v": "negocio", "meses": [], "e": "ambas", "t": "todos", "c": None})

    def test_formato_y_no_disponibles(self):
        self.assertEqual(self.o["fmt"], ["−1.234,6", "1.234.567", "644,1 M", "—", "2020-06"])
        self.assertEqual(self.o["ceros"], [None, None, 50.0])  # ceros no registrados: no disponible
        self.assertEqual(self.o["nulos"], [20.0, 20.0, 20.0])
        self.assertEqual(self.o["op"]["intentos"], 3)


@unittest.skipUnless(CHROME, "Chrome no está instalado")
class TestDibujo(unittest.TestCase):
    """Abre el archivo local (file://, sin red) con cada estado y lee el DOM ya dibujado."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        raiz = Path(cls.tmp.name)
        ejecucion(raiz)
        cls.url = H.generar(raiz).resolve().as_uri()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def dom(self, h: str) -> str:
        with tempfile.TemporaryDirectory() as perfil:
            r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={perfil}",
                                "--virtual-time-budget=3000", "--dump-dom", self.url + h],
                               capture_output=True, text=True, encoding="utf-8", timeout=120)
        texto = r.stdout
        return texto[texto.index('<div id="app">'):texto.index('<script id="datos"')]

    def test_negocio(self):
        d = self.dom("#v=negocio")
        for t in ("Ganancia acumulada", "suma de 1 campaña", "2,6 M", "Confirmación para C02 pendiente", "Sin target completo",
                  'aria-selected="true">Negocio'):
            self.assertIn(t, d)

    def test_meses_sin_target(self):
        d = self.dom("#v=negocio&t=pendiente")
        self.assertIn('<b class="p">pendiente</b>', d)
        self.assertNotIn("suma de 1 campaña", d)

    def test_seleccion_vacia(self):
        self.assertIn("Ningún mes cumple los filtros", self.dom("#v=operacion&m=ninguno"))

    def test_modelo_con_filtro_de_estrategia(self):
        d = self.dom("#v=modelo&e=multiclase")
        self.assertIn("multiclase = P(BAJA+2)", d)
        self.assertNotIn("binario = P(BAJA+1", d)
        self.assertIn("Indicadores de deriva", d)

    def test_operacion(self):
        d = self.dom("#v=operacion")
        for t in ("límite 900 s", "margen 450 s", "Versiones", "3.12.0", "no disponible"):
            self.assertIn(t, d)


if __name__ == "__main__":
    unittest.main()
