"""TC01 (paso 1) — target de 2019 con la regla versión 2 (evaluacion/target.py), a partir de la presencia de clientes.

Meses: sólo los de entrenamiento y desarrollo (evaluacion.particiones.PERMITIDOS_DESARROLLO: 201903–201906, 201908,
201909). 201910 no se etiqueta ni se informa (evaluación final reservada). La presencia sale de las claves
(numero_de_cliente, foto_mes) del Parquet de 2019; las etiquetas de 201909 usan la presencia en 201910 y 201911.

Comprobaciones (todas deben dar verdadero; si no, no se publica nada):
  1. las dos implementaciones de la regla coinciden fila a fila: SQL (sql_etiquetas) y numpy (etiquetar);
  2. cobertura: mismas claves que las features de cada mes (competencia_02_2019_features), sin clase nula;
  3. contra el target anterior (regla versión 1, experimento_sampling/03, leído con particiones.leer_target):
     BAJA+2 idéntico fila a fila; el único cambio posible es BAJA+1 -> CONTINUA; y los que cambian son exactamente los
     clientes ausentes en t+1 y presentes en t+2, contados aparte.
Salida (no se sobrescribe): RUTAS.target_2019_v2 (+ .json de procedencia al lado) y el resumen versionado
resultados/tc01_target_2019_v2.json (sólo conteos por mes y clase). El target anterior queda intacto.

Uso: python -m experimentos.tc01_target_2019
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import duckdb
import numpy as np

from evaluacion import particiones as P
from evaluacion import target as T
from pipeline_competencia02.config import RAIZ, RUTAS, mostrar

MESES = sorted(P.PERMITIDOS_DESARROLLO)
RESUMEN = RAIZ / "resultados" / "tc01_target_2019_v2.json"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main() -> int:
    if set(MESES) & set(P.EVALUACION_FINAL):
        raise SystemExit("octubre no se etiqueta")
    destino = RUTAS.target_2019_v2
    if destino.exists():
        raise SystemExit(f"{destino} ya existe; no se sobrescribe")
    t0 = time.perf_counter()
    src = RUTAS.historico_2019.as_posix()
    con = duckdb.connect()
    con.execute("SET threads = 8")
    con.execute(f"CREATE TEMP TABLE pres AS SELECT DISTINCT numero_de_cliente, foto_mes FROM read_parquet('{src}')")
    meses_fuente = [m for (m,) in con.execute("SELECT DISTINCT foto_mes FROM pres ORDER BY 1").fetchall()]
    per = {T.periodo(m): m for m in meses_fuente}
    for m in MESES:
        if T.periodo(m) + 1 not in per or T.periodo(m) + 2 not in per:
            raise SystemExit(f"{m}: falta t+1 o t+2 en la fuente; la etiqueta no sería definitiva")

    # 1. dos implementaciones
    nuevo = con.execute(T.sql_etiquetas("pres", MESES)).fetchnumpy()
    cli, mes, clase = (np.asarray(nuevo[k]) for k in ("numero_de_cliente", "foto_mes", "clase_ternaria"))
    clase = clase.astype(str)
    presentes = {m: np.sort(con.execute(f"SELECT numero_de_cliente FROM pres WHERE foto_mes = {m}").fetchnumpy()[
        "numero_de_cliente"]) for m in meses_fuente}
    alt = np.empty(len(cli), dtype=object)
    retorno = np.zeros(len(cli), bool)
    for m in MESES:
        i = mes == m
        en1 = np.isin(cli[i], presentes[per[T.periodo(m) + 1]])
        en2 = np.isin(cli[i], presentes[per[T.periodo(m) + 2]])
        alt[i] = T.etiquetar(en1, en2)
        retorno[i] = ~en1 & en2
    checks = {"sql_igual_numpy": bool(np.array_equal(clase, alt.astype(str)))}

    # 2. cobertura contra las features
    con.execute("CREATE TEMP TABLE nuevo AS SELECT * FROM (" + T.sql_etiquetas("pres", MESES) + ")")
    feats = ", ".join(f"'{(RUTAS.features_2019 / f'features_{m}.parquet').as_posix()}'" for m in MESES)
    sin_par = con.execute(f"""
        SELECT (SELECT count(*) FROM read_parquet([{feats}]) f ANTI JOIN nuevo USING (numero_de_cliente, foto_mes)),
               (SELECT count(*) FROM nuevo n ANTI JOIN read_parquet([{feats}]) f USING (numero_de_cliente, foto_mes)),
               (SELECT count(*) FROM nuevo WHERE clase_ternaria IS NULL)""").fetchone()
    checks["mismas_claves_que_features_y_sin_nulos"] = sin_par == (0, 0, 0)

    # 3. contra la versión 1 (lectura controlada por particiones)
    v1 = P.leer_target(con, RUTAS.target_2019.as_posix(), MESES).df()
    con.register("v1", v1)
    filas = con.execute("""
        SELECT n.foto_mes, v1.clase_ternaria AS antes, n.clase_ternaria AS ahora, count(*)
        FROM nuevo n JOIN v1 USING (numero_de_cliente, foto_mes) GROUP BY ALL ORDER BY ALL""").fetchall()
    n_join = sum(r[3] for r in filas)
    transiciones = {}
    for m, a, b, k in filas:
        transiciones.setdefault(str(m), {})[f"{a} -> {b}"] = int(k)
    cambios = [(m, a, b, k) for m, a, b, k in filas if a != b]
    por_mes_retorno = {str(m): int(retorno[mes == m].sum()) for m in MESES}
    checks["mismas_filas_que_v1"] = n_join == len(cli) == len(v1)
    checks["baja2_identico"] = all(not (a == "BAJA+2") ^ (b == "BAJA+2") for _, a, b, _ in filas)
    checks["unico_cambio_baja1_a_continua"] = all(a == "BAJA+1" and b == "CONTINUA" for _, a, b, _ in cambios)
    checks["cambios_igual_clientes_que_vuelven"] = (
        {str(m): k for m, _, _, k in cambios} == {m: k for m, k in por_mes_retorno.items() if k})
    con.unregister("v1")

    def conteo(etiquetas, meses_arr) -> dict:
        return {str(m): {c: int(((meses_arr == m) & (etiquetas == c)).sum()) for c in T.CLASES} for m in MESES}

    v1_conteo = {str(m): {c: int(((v1["foto_mes"] == m) & (v1["clase_ternaria"] == c)).sum()) for c in T.CLASES}
                 for m in MESES}
    rep = {"experimento": "TC01 paso 1: target 2019 regla versión 2", "inicio": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "regla": T.REGLA, "version": T.VERSION, "meses": MESES, "octubre": "no se etiqueta ni se informa",
           "fuente_presencia": {"archivo": mostrar(RUTAS.historico_2019), "sha256": sha256(RUTAS.historico_2019),
                                "meses": meses_fuente},
           "anterior": {"archivo": mostrar(RUTAS.target_2019), "sha256": sha256(RUTAS.target_2019),
                        "regla": "versión 1 (experimento_sampling/03): ausente en t+1 -> BAJA+1"},
           "codigo": {"evaluacion/target.py": sha256(RAIZ / "evaluacion" / "target.py"),
                      "experimentos/tc01_target_2019.py": sha256(Path(__file__))},
           "conteo_v1": v1_conteo, "conteo_v2": conteo(clase, mes), "transiciones_v1_a_v2": transiciones,
           "cambios": {str(m): {f"{a} -> {b}": int(k)} for m, a, b, k in cambios},
           "clientes_que_vuelven_por_mes": por_mes_retorno, "checks": checks}
    if not all(checks.values()):
        print(json.dumps(rep, indent=1, ensure_ascii=False))
        raise SystemExit(f"comprobaciones fallidas: {[k for k, v in checks.items() if not v]}")

    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(destino.name + f".tmp-{os.getpid()}")
    con.execute(f"COPY (SELECT numero_de_cliente, foto_mes, clase_ternaria FROM nuevo ORDER BY foto_mes, numero_de_cliente) "
                f"TO '{tmp.as_posix()}' (FORMAT parquet, COMPRESSION zstd)")
    con.close()
    os.rename(tmp, destino)
    rep["salida"] = {"archivo": mostrar(destino), "sha256": sha256(destino), "filas": int(len(cli))}
    rep["segundos"] = round(time.perf_counter() - t0, 1)
    texto = json.dumps(rep, indent=2, ensure_ascii=False) + "\n"
    destino.with_suffix(".json").write_text(texto, encoding="utf-8", newline="\n")
    RESUMEN.write_text(texto, encoding="utf-8", newline="\n")
    print(json.dumps({k: rep[k] for k in ("cambios", "clientes_que_vuelven_por_mes", "checks", "salida", "segundos")},
                     indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
