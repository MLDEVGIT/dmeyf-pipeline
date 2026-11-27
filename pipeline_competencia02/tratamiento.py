"""Detección y tratamiento de columnas anómalas (E06, docs/PLAN_PRUEBAS.md § 19).

Mismo código para la simulación de 2019 (experimentos/e06_columnas_anomalas.py) y para el pipeline mensual.

Regla `cero_anomalo` (sólo el mes recibido y su historia; sin etiquetas). La columna c se detecta en el mes t si:
  1. en t tiene >= 1 observado (no nulo) y todos los observados valen 0;
  2. hay un mes de referencia r: el más reciente de la historia entre t-1 y t-3 con >= 1 observado distinto de 0;
  3. E = observados en t × (fracción distinta de 0 en r) >= esperados_min (30).
Sin referencia o con E chico no se detecta: un 0 en toda la columna puede ser legítimo.

Tratamientos, sólo sobre las columnas detectadas y antes de calcular features (la historia guarda el mes tratado):
  advertir      A: valor recibido (vigente; no cambia nada)
  faltantes     N: la columna pasa a NULL
  ultimo_valor  L: cada valor observado pasa al último valor válido del cliente: el del mes más reciente m con
                t - m <= antiguedad_max (2) meses calendario, cliente observado en m, columna no tratada en m y valor
                no nulo; si no hay, NULL (clientes nuevos, sin observaciones recientes o meses tratados seguidos).
                Los nulos de origen siguen nulos.
"""
from __future__ import annotations

METODOS = ("advertir", "faltantes", "ultimo_valor")
PARAMS = {"esperados_min": 30.0, "meses_referencia": 3, "antiguedad_max": 2}
KEY = "numero_de_cliente"


def q(c: str) -> str:
    return '"' + c.replace('"', '""') + '"'


def mes_menos(mes: int, k: int) -> int:
    a, m = divmod(mes, 100)
    i = a * 12 + (m - 1) - k
    return (i // 12) * 100 + i % 12 + 1


def perfil(con, rel: str, cols: list[str]) -> dict[str, tuple[int, int]]:
    """(observados, distintos de 0) por columna, en una sola pasada."""
    exprs = ", ".join(f"count({q(c)}), count(*) FILTER (WHERE {q(c)} <> 0)" for c in cols)
    r = con.execute(f"SELECT {exprs} FROM {rel}").fetchone()
    return {c: (int(r[2 * i]), int(r[2 * i + 1])) for i, c in enumerate(cols)}


def detectar(perfil_t: dict, perfiles_hist: dict[int, dict], mes: int, params: dict = PARAMS) -> dict:
    """Columnas con todos los observados en 0, separadas en detectadas y no detectadas (con el motivo)."""
    detectadas, no_detectadas = [], []
    for c, (obs, nz) in perfil_t.items():
        if obs == 0 or nz:
            continue
        ref = next((mes_menos(mes, k) for k in range(1, params["meses_referencia"] + 1)
                    if mes_menos(mes, k) in perfiles_hist and perfiles_hist[mes_menos(mes, k)][c][1] > 0), None)
        fila = {"columna": c, "observados": obs, "mes_referencia": ref}
        if ref is None:
            no_detectadas.append({**fila, "motivo": f"sin actividad en los últimos {params['meses_referencia']} meses"})
            continue
        o_r, nz_r = perfiles_hist[ref][c]
        e = obs * nz_r / o_r
        fila.update(fraccion_no_cero_referencia=round(nz_r / o_r, 6), esperados_no_cero=round(e, 1))
        (detectadas if e >= params["esperados_min"] else no_detectadas).append(
            fila if e >= params["esperados_min"] else {**fila, "motivo": f"E < {params['esperados_min']:g}"})
    return {"detectadas": detectadas, "no_detectadas": no_detectadas}


def fuentes_ultimo_valor(mes: int, hist: dict[int, str], tratadas_hist: dict[int, set], params: dict = PARAMS):
    """Meses candidatos para L, del más reciente al más antiguo, con su relación y las columnas tratadas en cada uno."""
    out = []
    for k in range(1, params["antiguedad_max"] + 1):
        m = mes_menos(mes, k)
        if m in hist:
            out.append((k, m, hist[m], set(tratadas_hist.get(m, set()))))
    return out


def sql_tratado(actual: str, tipos: list[tuple[str, str]], detectadas: list[str], metodo: str, mes: int,
                hist: dict[int, str] | None = None, tratadas_hist: dict[int, set] | None = None,
                params: dict = PARAMS) -> str | None:
    """SELECT del mes tratado, con las mismas columnas, orden y tipos que `actual`. None si no hay nada que cambiar."""
    if metodo not in METODOS:
        raise ValueError(f"método {metodo!r} fuera de {METODOS}")
    det = set(detectadas)
    if metodo == "advertir" or not det:
        return None
    if metodo == "faltantes":
        sel = [f"CAST(NULL AS {t}) AS {q(c)}" if c in det else f"a.{q(c)}" for c, t in tipos]
        return f"SELECT {', '.join(sel)} FROM {actual} a"
    fuentes = fuentes_ultimo_valor(mes, hist or {}, tratadas_hist or {}, params)
    joins = " ".join(f"LEFT JOIN {rel} h{k} ON h{k}.{q(KEY)} = a.{q(KEY)}" for k, _, rel, _ in fuentes)
    sel = []
    for c, t in tipos:
        if c not in det:
            sel.append(f"a.{q(c)}")
            continue
        cands = [f"h{k}.{q(c)}" for k, _, _, trat in fuentes if c not in trat]
        valor = f"COALESCE({', '.join(cands)})" if len(cands) > 1 else (cands[0] if cands else "NULL")
        sel.append(f"CAST(CASE WHEN a.{q(c)} IS NULL THEN NULL ELSE {valor} END AS {t}) AS {q(c)}")
    # el JOIN puede reordenar: se conserva el orden de llegada para que la historia tratada sea reproducible
    return (f"SELECT {', '.join(sel)} FROM (SELECT *, row_number() OVER () AS _fila FROM {actual}) a {joins} "
            f"ORDER BY a._fila")


def conteos(con, actual: str, detectadas: list[str], metodo: str, mes: int, hist: dict[int, str] | None = None,
            tratadas_hist: dict[int, set] | None = None, params: dict = PARAMS) -> dict:
    """Celdas tratadas: observadas, imputadas por antigüedad (L), puestas en NULL; clientes sin observaciones recientes."""
    if metodo == "advertir" or not detectadas:
        return {"celdas_observadas": 0}
    obs = " + ".join(f"count({q(c)})" for c in detectadas)
    if metodo == "faltantes":
        n = con.execute(f"SELECT {obs} FROM {actual}").fetchone()[0]
        return {"celdas_observadas": int(n), "a_null": int(n)}
    fuentes = fuentes_ultimo_valor(mes, hist or {}, tratadas_hist or {}, params)
    joins = " ".join(f"LEFT JOIN {rel} h{k} ON h{k}.{q(KEY)} = a.{q(KEY)}" for k, _, rel, _ in fuentes)
    exprs, claves = [], []
    for c in detectadas:
        previas = []
        for k, m, _, trat in fuentes:
            if c in trat:
                continue
            cond = " AND ".join([f"a.{q(c)} IS NOT NULL"] + [f"{p} IS NULL" for p in previas] + [f"h{k}.{q(c)} IS NOT NULL"])
            exprs.append(f"count(*) FILTER (WHERE {cond})")
            claves.append(f"antiguedad_{k}")
            previas.append(f"h{k}.{q(c)}")
        exprs.append(f"count({q('a')}.{q(c)})")
        claves.append("observadas")
    nuevos = (f"count(*) FILTER (WHERE {' AND '.join(f'h{k}.{q(KEY)} IS NULL' for k, *_ in fuentes)})"
              if fuentes else "count(*)")
    r = con.execute(f"SELECT {', '.join(exprs)}, {nuevos} FROM {actual} a {joins}").fetchone()
    out = {"celdas_observadas": 0, **{f"imputadas_antiguedad_{k}": 0 for k, *_ in fuentes}}
    for clave, v in zip(claves, r[:-1]):
        out["celdas_observadas" if clave == "observadas" else f"imputadas_{clave}"] += int(v)
    out["a_null_sin_valor_valido"] = out["celdas_observadas"] - sum(v for k, v in out.items() if k.startswith("imputadas"))
    out["clientes_sin_observaciones_recientes"] = int(r[-1])
    out["fuentes"] = [{"antiguedad": k, "mes": m, "columnas_tratadas_en_ese_mes": sorted(set(detectadas) & trat)}
                      for k, m, _, trat in fuentes]
    return out
