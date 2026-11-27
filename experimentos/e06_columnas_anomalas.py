"""E06 — detección y tratamiento de columnas anómalas, simulados en 2019 (docs/PLAN_PRUEBAS.md § 19).

Catálogo de trabajo fijo: ce02_b20m10 (binario 20 semillas en 2,35 %, multiclase 10 en 2,725 %). Sin reentrenar.
Datos: crudo de 2019 (RUTAS.historico_2019) sólo 201901–201909; target versión 2 sólo de 201908 y 201909 (desarrollo,
evaluacion.particiones.leer_target); octubre bloqueado y no se lee. 2020 sólo para la detección descriptiva.

Por celda (conjunto de columnas, meses inyectados, tratamiento, mes evaluado):
  1. procesa los meses en orden, como el pipeline: inyecta (todos los observados -> 0) si corresponde, detecta con
     tratamiento.detectar sobre la historia ya tratada, trata con tratamiento.sql_tratado y guarda el mes tratado como
     historia;
  2. calcula las features del mes evaluado con features.sql_mes sobre esa historia;
  3. aplica los 30 modelos, promedia en el orden del catálogo y corta en la fracción fija;
  4. mide envíos, BAJA+2, ganancia, AUC y cambio de selección contra O (sin corrupción).
Controles: features de O idénticas a features_2019/; ensamble de O idéntico al promedio de las predicciones de CE02.

Reanudable: cada celda se guarda en ejecuciones/e06/<marca>/celdas/. Uso:
  python -m experimentos.e06_columnas_anomalas [--trabajo ejecuciones/e06/<marca>] [--salida resultados/e06_simulacion_2019.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import duckdb
import lightgbm as lgb
import numpy as np
import psutil
from sklearn.metrics import roc_auc_score

from evaluacion import particiones as P
from evaluacion.ganancia import COSTO_ENVIO, PREMIO_BRUTO, envios, orden
from pipeline_competencia02 import tratamiento as T
from pipeline_competencia02.config import RAIZ, RUTAS, mostrar
from pipeline_competencia02.correr_meses import despierto
from pipeline_competencia02.features import KEYS, crear_prev, nombres, q, sql_mes

CATALOGO = RAIZ / "catalogo" / "estrategias_ce02_b20m10.json"
PREDICTORES = RAIZ / "catalogo" / "predictores.json"
CE02 = RAIZ / "resultados" / "ce02_ensambles_20.json"
MESES_CRUDO = (201901, 201902, 201903, 201904, 201905, 201906, 201907, 201908, 201909)
EVALUADOS = P.DESARROLLO  # (201908, 201909)
TOLERANCIA = 2_200_000  # 2 BAJA+2
CONJUNTOS_FUENTE = {"C47": ("resultados/i02_columnas_en_cero_202006.json", None),
                    "C7": (None, 201905), "C6": (None, 202002)}
ESCENARIOS = {"S1": ((201909,), (201909,)), "S2": ((201908,), (201908, 201909)),
              "S3": ((201907,), (201908, 201909)), "S4": ((201908, 201909), (201908, 201909)),
              "S5": ((201907, 201908, 201909), (201909,))}
PLAN = {"C47": ("S1", "S2", "S3", "S4", "S5"), "C7": ("S1", "S2"), "C6": ("S1",)}
BLOQUE = 30_000


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ------------------------------------------------------------------ datos base
class Base:
    def __init__(self, trabajo: Path):
        self.dir = trabajo / "base"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect()
        self.con.execute("SET threads = 4")
        self.con.execute("SET memory_limit = '4GB'")
        self.con.execute(f"SET temp_directory = '{(trabajo / 'duckdb').as_posix()}'")
        h = RUTAS.historico_2019.as_posix()
        for m in MESES_CRUDO:  # nunca 201910 o posteriores
            p = self.path(m)
            if not p.exists():
                self.con.execute(f"COPY (SELECT * FROM read_parquet('{h}') WHERE foto_mes = {m}) TO '{p.as_posix()}' "
                                 f"(FORMAT parquet, COMPRESSION zstd)")
        self.tipos = [(c, t) for c, t, *_ in self.con.execute(f"DESCRIBE SELECT * FROM read_parquet('{self.path(201901).as_posix()}')").fetchall()]
        self.cols = [c for c, _ in self.tipos if c not in KEYS]
        self._perfiles: dict[str, dict] = {}

    def path(self, m: int) -> Path:
        return self.dir / f"foto_mes={m}.parquet"

    def perfil(self, p: Path) -> dict:
        k = p.as_posix()
        if k not in self._perfiles:
            self._perfiles[k] = T.perfil(self.con, f"read_parquet('{k}')", self.cols)
        return self._perfiles[k]


def columnas_conjunto(base: Base, nombre: str) -> list[str]:
    archivo, mes = CONJUNTOS_FUENTE[nombre]
    if archivo:
        return sorted(json.loads((RAIZ / archivo).read_text(encoding="utf-8"))["columnas"])
    perfil_json = json.loads((RAIZ / "resultados" / "e06_deteccion.json").read_text(encoding="utf-8"))
    fuente = perfil_json["meses"] if str(mes) in perfil_json["meses"] else perfil_json["2020"]
    return sorted(d["columna"] for d in fuente[str(mes)]["detectadas"])


# ------------------------------------------------------------------ simulación de la secuencia de meses
def procesar(base: Base, trabajo: Path, cols_inj: list[str], inyectados: tuple, metodo: str, hasta: int, clave: str):
    """Recorre los meses desde el primero inyectado hasta `hasta`. Devuelve historia (mes -> parquet) y registro."""
    hist = {m: base.path(m) for m in MESES_CRUDO}
    tratadas: dict[int, set] = {}
    registro = {}
    d = trabajo / "meses" / clave
    d.mkdir(parents=True, exist_ok=True)
    for t in [m for m in MESES_CRUDO if min(inyectados) <= m <= hasta] if inyectados else []:
        t0 = time.perf_counter()
        crudo = hist[t]
        if t in inyectados:
            crudo = d / f"crudo_{t}.parquet"
            sel = ", ".join(f"CASE WHEN {q(c)} IS NULL THEN NULL ELSE 0 END::{ty} AS {q(c)}" if c in cols_inj else q(c)
                            for c, ty in base.tipos)
            base.con.execute(f"COPY (SELECT {sel} FROM read_parquet('{base.path(t).as_posix()}')) TO '{crudo.as_posix()}' "
                             f"(FORMAT parquet, COMPRESSION zstd)")
        t1 = time.perf_counter()
        perf_t = T.perfil(base.con, f"read_parquet('{crudo.as_posix()}')", base.cols)
        ph = {m: base.perfil(hist[m]) for m in (T.mes_menos(t, k) for k in range(1, T.PARAMS["meses_referencia"] + 1))
              if m in hist}
        det = T.detectar(perf_t, ph, t)
        cols_det = [x["columna"] for x in det["detectadas"]]
        rel_h = {m: f"read_parquet('{p.as_posix()}')" for m, p in hist.items() if m < t}
        actual = f"read_parquet('{crudo.as_posix()}')"
        s = T.sql_tratado(actual, base.tipos, cols_det, metodo, t, rel_h, tratadas)
        cont = T.conteos(base.con, actual, cols_det, metodo, t, rel_h, tratadas)
        tratado = crudo
        if s:
            tratado = d / f"tratado_{t}.parquet"
            base.con.execute(f"COPY ({s}) TO '{tratado.as_posix()}' (FORMAT parquet, COMPRESSION zstd)")
            tratadas[t] = set(cols_det)
        seg = round(time.perf_counter() - t1, 2)
        hist[t] = tratado
        inj = set(cols_inj) if t in inyectados else set()
        registro[str(t)] = {
            "inyectado": t in inyectados, "detectadas": det["detectadas"], "no_detectadas": det["no_detectadas"],
            "inyectadas_detectadas": len(inj & set(cols_det)), "inyectadas_no_detectadas": sorted(inj - set(cols_det)),
            "detectadas_no_inyectadas": sorted(set(cols_det) - inj), "conteos": cont,
            "deteccion_y_tratamiento_s": seg, "rss_mb": round(psutil.Process().memory_info().rss / 2**20),
            "con_inyeccion_s": round(time.perf_counter() - t0, 2)}
    return hist, registro


def features(base: Base, hist: dict, mes: int, destino: Path) -> Path:
    paths = [hist[m].as_posix() for m in MESES_CRUDO if m <= mes]
    base.con.execute(f"CREATE OR REPLACE VIEW src AS SELECT * FROM read_parquet({paths})")
    crear_prev(base.con, "src")
    base.con.execute(f"COPY ({sql_mes('src', base.cols, mes)}) TO '{destino.as_posix()}' (FORMAT parquet, COMPRESSION zstd)")
    return destino


# ------------------------------------------------------------------ modelos e inferencia
class Modelos:
    def __init__(self):
        cat = json.loads(CATALOGO.read_text(encoding="utf-8"))
        self.pred = [c for c, _ in json.loads(PREDICTORES.read_text(encoding="utf-8"))["predictores"]]
        self.estr = []
        for e in cat["estrategias"]:
            bs = []
            for m in e["modelos"]:
                p = RUTAS.modelos / m["archivo"]
                if sha(p) != m["sha256"]:
                    raise RuntimeError(f"{p}: sha256 distinto del catálogo")
                bs.append(lgb.Booster(model_file=str(p)))
            self.estr.append({"id": e["id"], "rol": e["rol"], "col": e["columna_score"],
                              "fraccion": e["corte"]["fraccion"], "boosters": bs})
        self.catalogo = {"archivo": mostrar(CATALOGO), "sha256": sha(CATALOGO), "nombre": cat["nombre"]}

    def predecir(self, con, feat: Path) -> tuple[np.ndarray, dict]:
        tipos = {c: t for c, t, *_ in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{feat.as_posix()}')").fetchall()}
        if [c for c in tipos if c not in KEYS] != self.pred:
            raise RuntimeError("features distintas de predictores.json")
        expr = ", ".join(f"CAST({q(c)} AS DOUBLE) AS {q(c)}" for c in self.pred)
        rel = con.execute(f"SELECT numero_de_cliente, {expr} FROM read_parquet('{feat.as_posix()}') ORDER BY numero_de_cliente")
        cli, partes = [], {e["id"]: [] for e in self.estr}
        while True:
            df = rel.fetch_df_chunk(BLOQUE // 2048 + 1)
            if df is None or len(df) == 0:
                break
            cli.append(df["numero_de_cliente"].to_numpy(np.int64))
            X = df[self.pred].to_numpy(np.float64, na_value=np.nan)
            for e in self.estr:
                ps = [b.predict(X, num_threads=4) for b in e["boosters"]]
                ps = [p if e["col"] is None else p[:, e["col"]] for p in ps]
                partes[e["id"]].append(np.mean(ps, axis=0))
            del X, df
        return np.concatenate(cli), {k: np.concatenate(v) for k, v in partes.items()}


def seleccion(score: np.ndarray, cli: np.ndarray, f: float) -> np.ndarray:
    s = np.zeros(len(cli), bool)
    s[orden(score, cli)[:envios(f, len(cli))]] = True
    return s


def etiquetas(con, mes: int, cli: np.ndarray) -> np.ndarray:
    t = P.leer_target(con, RUTAS.target_2019_v2.as_posix(), [mes]).df()
    t = t.set_index("numero_de_cliente").reindex(cli)
    if t["clase_ternaria"].isna().any():
        raise RuntimeError(f"{mes}: clientes sin target")
    return (t["clase_ternaria"] == "BAJA+2").to_numpy()


# ------------------------------------------------------------------ detección sobre meses reales
def deteccion_real(base: Base, salida: Path) -> dict:
    """201902–201909 reales (falsas alarmas y positivos reales), columnas de poca actividad y 2020 descriptivo."""
    out = {"criterio": T.PARAMS, "meses": {}, "poca_actividad": {}, "2020": {}}
    for t in MESES_CRUDO[1:]:
        ph = {m: base.perfil(base.path(m)) for m in (T.mes_menos(t, k) for k in (1, 2, 3)) if m in MESES_CRUDO}
        out["meses"][str(t)] = T.detectar(base.perfil(base.path(t)), ph, t)
    # columnas activas con E < 30 pasadas a 0 en los meses de desarrollo: no deben detectarse
    for t in EVALUADOS:
        pt, pr = base.perfil(base.path(t)), base.perfil(base.path(T.mes_menos(t, 1)))
        bajas = [c for c in base.cols if pt[c][0] and pr[c][1] and pt[c][0] * pr[c][1] / pr[c][0] < T.PARAMS["esperados_min"]]
        sim = {c: ((pt[c][0], 0) if c in bajas else v) for c, v in pt.items()}
        ph = {m: base.perfil(base.path(m)) for m in (T.mes_menos(t, k) for k in (1, 2, 3))}
        det = T.detectar(sim, ph, t)
        out["poca_actividad"][str(t)] = {"columnas": bajas, "detectadas": det["detectadas"],
                                         "no_detectadas": det["no_detectadas"]}
    # 2020: historia de la corrida de CA02 (sólo describe; 201910 y 201911 no se leen)
    sec = RUTAS.entornos / (RAIZ / "ejecuciones" / "ultima_secuencia_ce02_b20m10.txt").read_text().strip() / "historia"
    if sec.exists():
        perf = {m: base.perfil(sec / f"foto_mes={m}.parquet") for m in (201912, 202001, 202002, 202003, 202004, 202005, 202006)}
        for t in range(202001, 202007):
            out["2020"][str(t)] = T.detectar(perf[t], {m: v for m, v in perf.items() if m < t}, t)
        out["2020_fuente"] = mostrar(sec)
    salida.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return out


# ------------------------------------------------------------------ medición dedicada de detección y tratamiento
def medir_tratamiento(base: Base, trabajo: Path, conjuntos: dict, repeticiones: int = 2) -> dict:
    """Detección y tratamiento solos (sin features ni inferencia), para todos los escenarios y métodos, con la
    máquina despierta. Los tiempos dentro de las celdas quedaron afectados por una suspensión y por carga externa."""
    out = {"repeticiones": repeticiones, "metodos": {}, "nota": "segundos por mes procesado: perfil, detección, "
           "tratamiento y escritura del mes tratado; sin la inyección", "carga_cpu_inicial_pct": psutil.cpu_percent(interval=2)}
    for met in T.METODOS:
        vals = []
        for r in range(repeticiones):
            for nombre, escs in PLAN.items():
                for esc in escs:
                    iny, ev = ESCENARIOS[esc]
                    _, reg = procesar(base, trabajo, conjuntos[nombre], iny, met, max(ev), f"medicion_r{r}_{nombre}_{esc}_{met}")
                    vals += [v["deteccion_y_tratamiento_s"] for v in reg.values()]
        out["metodos"][met] = {"n": len(vals), "max_s": max(vals), "mediana_s": float(np.median(vals))}
    out["pico_working_set_mb"] = round(getattr(psutil.Process().memory_info(), "peak_wset", 0) / 2**20)
    return out


# ------------------------------------------------------------------ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trabajo", type=Path)
    ap.add_argument("--salida", type=Path, default=RAIZ / "resultados" / "e06_simulacion_2019.json")
    ap.add_argument("--solo-deteccion", action="store_true")
    a = ap.parse_args(argv)
    trabajo = (a.trabajo or RAIZ / "ejecuciones" / "e06" / time.strftime("%Y%m%dT%H%M%S")).resolve()
    (trabajo / "celdas").mkdir(parents=True, exist_ok=True)
    (trabajo / "features").mkdir(exist_ok=True)
    t_ini = time.perf_counter()
    despierto(True)  # la simulación dura horas: evita la suspensión
    base = Base(trabajo)
    det = deteccion_real(base, RAIZ / "resultados" / "e06_deteccion.json")
    print("detección real:", {m: [x["columna"] for x in v["detectadas"]] for m, v in det["meses"].items() if v["detectadas"]},
          "| 2020:", {m: len(v["detectadas"]) for m, v in det["2020"].items()}, flush=True)
    if a.solo_deteccion:
        return 0
    conjuntos = {n: columnas_conjunto(base, n) for n in PLAN}
    print({n: len(v) for n, v in conjuntos.items()}, flush=True)
    med_arch = trabajo / "medicion_tratamiento.json"
    if not med_arch.exists():
        med_arch.write_text(json.dumps(medir_tratamiento(base, trabajo, conjuntos), ensure_ascii=False), encoding="utf-8")
    medicion = json.loads(med_arch.read_text(encoding="utf-8"))
    print("medición de detección y tratamiento:", medicion["metodos"], flush=True)
    mod = Modelos()
    con_t = duckdb.connect()
    b2 = {}
    celdas = []
    for nombre, escs in [("O", ("O",))] + list(PLAN.items()):
        for esc in escs:
            inyectados, evaluados = ((), EVALUADOS) if nombre == "O" else ESCENARIOS[esc]
            for metodo in (("advertir",) if nombre == "O" else T.METODOS):
                for e in evaluados:
                    inj_e = tuple(m for m in inyectados if m <= e)
                    clave = f"{nombre}_{'-'.join(map(str, inj_e)) or 'sin'}_{metodo}_{e}"
                    celdas.append({"conjunto": nombre, "escenario": esc, "metodo": metodo, "mes": e, "clave": clave})
                    arch = trabajo / "celdas" / f"{clave}.json"
                    if arch.exists():
                        continue
                    t0 = time.perf_counter()
                    hist, registro = procesar(base, trabajo, conjuntos.get(nombre, []), inj_e, metodo, e, clave)
                    t1 = time.perf_counter()
                    feat = features(base, hist, e, trabajo / "features" / f"{clave}.parquet")
                    t2 = time.perf_counter()
                    cli, score = mod.predecir(base.con, feat)
                    t3 = time.perf_counter()
                    np.savez(trabajo / "celdas" / f"{clave}.npz", clientes=cli, **score)
                    arch.write_text(json.dumps({"registro_meses": registro, "segundos": {
                        "meses": round(t1 - t0, 1), "features": round(t2 - t1, 1), "inferencia": round(t3 - t2, 1)},
                        "pico_working_set_mb": round(getattr(psutil.Process().memory_info(), "peak_wset", 0) / 2**20)},
                        ensure_ascii=False), encoding="utf-8")
                    if nombre != "O":
                        feat.unlink()  # sólo se conservan las features de O (control)
                    print(f"{clave}: meses {t1 - t0:.0f} s, features {t2 - t1:.0f} s, inferencia {t3 - t2:.0f} s", flush=True)

    # ------------------------------------------------ métricas
    ref = {}
    for e in EVALUADOS:
        z = np.load(trabajo / "celdas" / f"O_sin_advertir_{e}.npz")
        ref[e] = {"cli": z["clientes"], "score": {x["id"]: z[x["id"]] for x in mod.estr}}
        b2[e] = etiquetas(con_t, e, ref[e]["cli"])
    res_celdas = []
    for c in celdas:
        z = np.load(trabajo / "celdas" / f"{c['clave']}.npz")
        info = json.loads((trabajo / "celdas" / f"{c['clave']}.json").read_text(encoding="utf-8"))
        e = c["mes"]
        cli = z["clientes"]
        if not np.array_equal(cli, ref[e]["cli"]):
            raise RuntimeError(f"{c['clave']}: clientes distintos de O")
        fila = {**{k: c[k] for k in ("conjunto", "escenario", "metodo", "mes")}, "estrategias": {}, **info}
        for x in mod.estr:
            s, so = z[x["id"]], ref[e]["score"][x["id"]]
            sel, sel_o = seleccion(s, cli, x["fraccion"]), seleccion(so, cli, x["fraccion"])
            tp = int((sel & b2[e]).sum())
            fila["estrategias"][x["rol"]] = {
                "envios": int(sel.sum()), "baja2_enviados": tp, "ganancia": int(PREMIO_BRUTO * tp - COSTO_ENVIO * int(sel.sum())),
                "auc_baja2": round(float(roc_auc_score(b2[e], s)), 6),
                "jaccard_con_O": round(float((sel & sel_o).sum() / (sel | sel_o).sum()), 4),
                "entran": int((sel & ~sel_o).sum()), "salen": int((sel_o & ~sel).sum()),
                "score_identico_a_O": bool(np.array_equal(s, so))}
        res_celdas.append(fila)

    # controles de O
    controles = {}
    pred_ce02 = RAIZ / json.loads(CE02.read_text(encoding="utf-8"))["modelos"]
    for e in EVALUADOS:
        f_o = trabajo / "features" / f"O_sin_advertir_{e}.parquet"
        f_s = RUTAS.features_2019 / f"features_{e}.parquet"
        cols = ", ".join(q(c) for c in ["numero_de_cliente"] + mod.pred)
        dif = con_t.execute(f"SELECT count(*) FROM (SELECT {cols} FROM read_parquet('{f_o.as_posix()}') EXCEPT ALL "
                            f"SELECT {cols} FROM read_parquet('{f_s.as_posix()}'))").fetchone()[0]
        n_o, n_s = (con_t.execute(f"SELECT count(*) FROM read_parquet('{p.as_posix()}')").fetchone()[0] for p in (f_o, f_s))
        meta = np.load(pred_ce02 / f"meta_{e}.npz")
        idx = np.argsort(meta["clientes"])
        ok_pred = {}
        for x, archivo, n in ((mod.estr[0], "pred_binario.npz", 20), (mod.estr[1], "pred_multiclase_p1.npz", 10)):
            P_ = np.load(pred_ce02 / archivo)[str(e)]
            prom = P_[:n].mean(axis=0)[idx]
            ok_pred[x["id"]] = {"mismos_clientes": bool(np.array_equal(meta["clientes"][idx], ref[e]["cli"])),
                                "identico": bool(np.array_equal(prom, ref[e]["score"][x["id"]])),
                                "max_dif_abs": float(np.max(np.abs(prom - ref[e]["score"][x["id"]])))}
        controles[str(e)] = {"features_iguales_a_features_2019": dif == 0 and n_o == n_s, "filas": n_o,
                             "ensamble_igual_al_promedio_de_ce02": ok_pred}

    # criterio del § 19
    G = {(r["conjunto"], r["escenario"], r["metodo"], r["mes"]): r["estrategias"] for r in res_celdas}
    crit = {}
    claves_cm = [(n, s, e) for n in ("C47", "C7") for s in PLAN[n] for e in ESCENARIOS[s][1]]
    claves_c6 = [("C6", s, e) for s in PLAN["C6"] for e in ESCENARIOS[s][1]]
    reales = {m: [x["columna"] for x in v["detectadas"]] for m, v in det["meses"].items()}
    falsas = {m: v for m, v in reales.items() if v and m not in ("201904", "201905")}
    # § 19: se exige detectar las inyectadas con E >= esperados_min; las que no tienen mes de referencia (sin
    # actividad en los 3 meses previos) o tienen E chico quedan fuera por definición y se informan aparte
    def motivo(v, c):
        return next((x.get("motivo") for x in v["no_detectadas"] if x["columna"] == c), "no evaluada")
    inj_no_det, fuera_de_regla = set(), set()
    for r in res_celdas:
        for m, v in r["registro_meses"].items():
            for c in v["inyectadas_no_detectadas"]:
                mot = motivo(v, c)
                (fuera_de_regla if mot.startswith(("sin actividad", "E <")) else inj_no_det).add((r["conjunto"], m, c, mot))
    inj_no_det, fuera_de_regla = sorted(inj_no_det), sorted(fuera_de_regla)
    det_en_O = sorted({(r["conjunto"], m) for r in res_celdas for m, v in r["registro_meses"].items()
                       if v["detectadas_no_inyectadas"]})
    detector = {"falsas_alarmas_2019": falsas, "poca_actividad_detectadas": {m: v["detectadas"] for m, v in det["poca_actividad"].items() if v["detectadas"]},
                "inyectadas_no_detectadas": [list(x) for x in inj_no_det],
                "inyectadas_fuera_de_la_regla": [list(x) for x in fuera_de_regla],
                "detectadas_sin_inyeccion": [list(x) for x in det_en_O]}
    detector["ok"] = not (falsas or detector["poca_actividad_detectadas"] or inj_no_det or det_en_O)
    for met in ("faltantes", "ultimo_valor"):
        dif = lambda rol, ks: {f"{n}_{s}_{e}": G[(n, s, met, e)][rol]["ganancia"] - G[(n, s, "advertir", e)][rol]["ganancia"] for n, s, e in ks}  # noqa: E731
        d_bin, d_mc, d_c6 = dif("recomendacion_provisional", claves_cm), dif("alternativa", claves_cm), dif("recomendacion_provisional", claves_c6)
        tiempos_celdas = [v["deteccion_y_tratamiento_s"] for r in res_celdas if r["metodo"] == met
                          for v in r["registro_meses"].values()]
        tiempos = medicion["metodos"][met]["max_s"] if medicion else max(tiempos_celdas)
        c = {"1_detector": detector["ok"],
             "2_binario_cada_celda": all(v >= -TOLERANCIA for v in d_bin.values()), "2_binario_suma_positiva": sum(d_bin.values()) > 0,
             "3_multiclase_suma_no_negativa": sum(d_mc.values()) >= 0,
             "4_c6_binario_cada_celda": all(v >= -TOLERANCIA for v in d_c6.values()),
             "5_costo_deteccion_y_tratamiento_max_30s": tiempos <= 30}
        crit[met] = {"condiciones": c, "cumple": all(c.values()), "diferencias_binario": d_bin, "diferencias_multiclase": d_mc,
                     "diferencias_c6_binario": d_c6, "suma_binario": sum(d_bin.values()), "suma_multiclase": sum(d_mc.values()),
                     "deteccion_y_tratamiento_s_max": tiempos,
                     "deteccion_y_tratamiento_s_en_celdas": {"max": max(tiempos_celdas),
                                                              "mediana": float(np.median(tiempos_celdas))}}
    cumplen = [m for m in crit if crit[m]["cumple"]]
    if len(cumplen) == 2:
        dif_suma = crit["ultimo_valor"]["suma_binario"] - crit["faltantes"]["suma_binario"]
        elegido = "ultimo_valor" if dif_suma > TOLERANCIA else "faltantes"
    else:
        elegido = cumplen[0] if cumplen else "advertir"
    res = {"experimento": "E06 detección y tratamiento de columnas anómalas (simulación en 2019)",
           "protocolo": "docs/PLAN_PRUEBAS.md § 19", "catalogo": mod.catalogo, "trabajo": mostrar(trabajo),
           "datos": "crudo 201901–201909; target versión 2 de 201908 y 201909; octubre bloqueado",
           "origen_del_problema": "identificado en el ensayo exploratorio de 2020 (202002 y 202006)",
           "parametros": T.PARAMS, "conjuntos": conjuntos, "escenarios": {k: {"inyectados": v[0], "evaluados": v[1]} for k, v in ESCENARIOS.items()},
           "plan": PLAN, "medicion_tratamiento": medicion, "controles": controles, "detector": detector, "celdas": res_celdas, "criterio": crit,
           "eleccion": elegido, "segundos": round(time.perf_counter() - t_ini, 1)}
    a.salida.write_text(json.dumps(res, indent=2, ensure_ascii=False, default=lambda o: sorted(o) if isinstance(o, set) else str(o)) + "\n",
                        encoding="utf-8", newline="\n")
    print("controles", controles, "\ndetector ok", detector["ok"], "\ncriterio", {m: v["condiciones"] for m, v in crit.items()},
          "\nelección", elegido, "->", mostrar(a.salida), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
