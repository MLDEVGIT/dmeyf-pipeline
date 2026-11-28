"""Ejecutor de etapas con etapas de mentira: orden, corte en la primera falla, omitidas, oyentes y reintento."""
import unittest

from pipeline_competencia02.ejecutor import COMPLETADA, FALLIDA, OMITIDA, Contexto, Etapa, ejecutar


class Oyente:
    def __init__(self):
        self.eventos = []

    def al_empezar(self, etapa, ctx):
        self.eventos.append(("empieza", etapa))

    def al_terminar(self, r, ctx):
        self.eventos.append(("termina", r.nombre, r.estado))


def anotar(nombre, valor=None):
    def f(ctx):
        ctx.datos.setdefault("orden", []).append(nombre)
        return valor
    return f


def romper(ctx):
    ctx.datos.setdefault("orden", []).append("rota")
    raise ValueError("se rompió a propósito")


class TestEjecutor(unittest.TestCase):
    def test_todas_exitosas_en_orden(self):
        ctx = Contexto(mes=202001)
        oy = Oyente()
        res = ejecutar([Etapa("a", anotar("a", {"filas": 10})), Etapa("b", anotar("b", 7)), Etapa("c", anotar("c"))],
                       ctx, [oy])
        self.assertTrue(res.ok)
        self.assertEqual(ctx.datos["orden"], ["a", "b", "c"])
        self.assertEqual([r.estado for r in res.etapas], [COMPLETADA] * 3)
        self.assertEqual(res.etapas[0].filas, 10)
        self.assertIsNone(res.etapas[1].filas)
        self.assertEqual(ctx.resultados["b"], 7)
        self.assertTrue(all(r.duracion_s is not None and r.inicio <= r.fin for r in res.etapas))
        self.assertEqual(oy.eventos, [("empieza", "a"), ("termina", "a", COMPLETADA), ("empieza", "b"),
                                      ("termina", "b", COMPLETADA), ("empieza", "c"), ("termina", "c", COMPLETADA)])

    def test_una_falla_omite_las_siguientes(self):
        ctx = Contexto()
        oy = Oyente()
        res = ejecutar([Etapa("a", anotar("a")), Etapa("rota", romper), Etapa("c", anotar("c")),
                        Etapa("d", anotar("d"))], ctx, [oy])
        self.assertFalse(res.ok)
        self.assertEqual(ctx.datos["orden"], ["a", "rota"])
        self.assertEqual([r.estado for r in res.etapas], [COMPLETADA, FALLIDA, OMITIDA, OMITIDA])
        f = res.fallida
        self.assertEqual(f.nombre, "rota")
        self.assertIn("se rompió a propósito", f.error)
        self.assertIn("ValueError", f.traza)
        self.assertIsInstance(f.excepcion, ValueError)
        self.assertNotIn("rota", ctx.resultados)
        self.assertNotIn(("empieza", "c"), oy.eventos)
        self.assertIn(("termina", "c", OMITIDA), oy.eventos)

    def test_las_etapas_ven_lo_que_devolvieron_las_anteriores(self):
        res = ejecutar([Etapa("uno", lambda ctx: 2), Etapa("dos", lambda ctx: ctx.resultados["uno"] * 3)], Contexto())
        self.assertEqual(res.etapas[1].estado, COMPLETADA)

    def test_reintento_retoma_sin_correr_las_hechas(self):
        ctx = Contexto()
        res = ejecutar([Etapa("a", anotar("a")), Etapa("b", anotar("b")), Etapa("c", anotar("c"))], ctx,
                       ya_hechas={"a", "b"})
        self.assertEqual(ctx.datos["orden"], ["c"])
        self.assertEqual([r.nombre for r in res.etapas], ["c"])

    def test_nombres_repetidos(self):
        with self.assertRaises(ValueError):
            ejecutar([Etapa("a", anotar("a")), Etapa("a", anotar("a"))], Contexto())

    def test_oyente_que_falla_corta(self):
        class Roto(Oyente):
            def al_empezar(self, etapa, ctx):
                raise RuntimeError("registro caído")
        with self.assertRaises(RuntimeError):
            ejecutar([Etapa("a", anotar("a"))], Contexto(), [Roto()])


if __name__ == "__main__":
    unittest.main()
