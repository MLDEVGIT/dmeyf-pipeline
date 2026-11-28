/* Lógica pura del tablero de seguimiento: selección por filtros, agregación, métricas, estado en la URL y formato.
   Sin DOM: se prueba con Node (pruebas/test_tablero.py). Reglas:
   - Al agregar meses sólo se suman métricas aditivas: envíos, costo, BAJA+2 capturadas y ganancia (campañas mensuales).
   - Ganancia y BAJA+2 sólo existen en meses con target completo; los demás quedan "pendiente"/"parcial", nunca 0.
   - AUC, precisión, cuantiles de score, coincidencia y tiempos se muestran por mes: no se suman ni se promedian. */
(function (raiz) {
  "use strict";
  var REC = "recomendacion_provisional", ALT = "alternativa";
  var ROLES = [REC, ALT];
  var CORTO = {}; CORTO[REC] = "binario"; CORTO[ALT] = "multiclase";
  var VISTAS = ["negocio", "modelo", "operacion"];
  var ESTRATEGIAS = ["ambas", "binario", "multiclase"];
  var TARGETS = ["todos", "completa", "parcial", "pendiente"];

  // ---------------------------------------------------------------- formato (es-AR)
  function agrupar(s) { return s.replace(/\B(?=(\d{3})+(?!\d))/g, "."); }
  function nd(x, d) {
    if (x === null || x === undefined || !isFinite(x)) return "—";
    d = d === undefined ? 1 : d;
    var neg = x < 0, t = Math.abs(x).toFixed(d).split(".");
    return (neg ? "−" : "") + agrupar(t[0]) + (t[1] ? "," + t[1] : "");
  }
  function n0(x) { return nd(x, 0); }
  function mill(x) { return x === null || x === undefined ? "—" : nd(x / 1e6, 1) + " M"; }
  function mesTxt(m) { m = +m; return Math.floor(m / 100) + "-" + String(m % 100).padStart(2, "0"); }

  // ---------------------------------------------------------------- estado (fragmento de la URL)
  function estadoInicial(D) { return { v: "negocio", meses: null, e: "ambas", t: "todos", c: null }; }
  function leerEstado(hash, D) {
    var s = estadoInicial(D);
    var p = {};
    String(hash || "").replace(/^#/, "").split("&").forEach(function (kv) {
      if (!kv) return;
      var i = kv.indexOf("=");
      p[decodeURIComponent(i < 0 ? kv : kv.slice(0, i))] = i < 0 ? "" : decodeURIComponent(kv.slice(i + 1));
    });
    if (VISTAS.indexOf(p.v) >= 0) s.v = p.v;
    if (ESTRATEGIAS.indexOf(p.e) >= 0) s.e = p.e;
    if (TARGETS.indexOf(p.t) >= 0) s.t = p.t;
    var disponibles = D.meses.map(function (m) { return m.mes; });
    if (p.m === "ninguno") s.meses = [];
    else if (p.m && p.m !== "todos") s.meses = p.m.split(",").map(Number).filter(function (m) { return disponibles.indexOf(m) >= 0; });
    if (p.c && disponibles.indexOf(+p.c) >= 0) s.c = +p.c;
    return s;
  }
  function escribirEstado(s) {
    var m = s.meses === null ? "todos" : (s.meses.length ? s.meses.join(",") : "ninguno");
    return "#v=" + s.v + "&m=" + m + "&e=" + s.e + "&t=" + s.t + (s.c ? "&c=" + s.c : "");
  }

  // ---------------------------------------------------------------- selección
  function rolesDe(e) { return e === "binario" ? [REC] : e === "multiclase" ? [ALT] : ROLES.slice(); }
  function seleccionar(D, s) {
    return D.meses.filter(function (m) {
      return (s.meses === null || s.meses.indexOf(m.mes) >= 0) && (s.t === "todos" || m.target.estado === s.t);
    });
  }
  function conTarget(m) { return m.target && m.target.estado === "completa"; }

  // ---------------------------------------------------------------- negocio
  function agregarNegocio(meses, rol, importes) {
    var r = { meses: meses.length, envios: null, costo: null, baja2: null, ganancia: null, enviosConTarget: null,
              completos: [], sinTarget: [] };
    meses.forEach(function (m) {
      var e = m.estr[rol];
      if (!e) return;
      if (e.envios !== null && e.envios !== undefined) {
        r.envios = (r.envios || 0) + e.envios;
        r.costo = (r.costo || 0) + e.envios * importes.costo;
      }
      if (conTarget(m) && e.retro) {
        r.completos.push(m.mes);
        r.baja2 = (r.baja2 || 0) + e.retro.baja2;
        r.ganancia = (r.ganancia || 0) + e.retro.ganancia;
        r.enviosConTarget = (r.enviosConTarget || 0) + e.envios;
      } else {
        r.sinTarget.push({ mes: m.mes, estado: m.target ? m.target.estado : "no_disponible" });
      }
    });
    return r;
  }
  var MET_NEGOCIO = {
    ganancia: { nombre: "Ganancia", unidad: " M", target: true, dec: 1,
                f: function (m, e) { return e.retro ? e.retro.ganancia / 1e6 : null; } },
    baja2: { nombre: "BAJA+2 capturadas", unidad: "", target: true, dec: 0, f: function (m, e) { return e.retro ? e.retro.baja2 : null; } },
    envios: { nombre: "Envíos", unidad: "", target: false, dec: 0, f: function (m, e) { return e.envios; } },
    costo: { nombre: "Costo de los envíos", unidad: " M", target: false, dec: 1, costo: true,
             f: function (m, e, imp) { return e.envios === null || e.envios === undefined ? null : e.envios * imp.costo / 1e6; } },
    precision: { nombre: "Precisión (BAJA+2 / envíos)", unidad: " %", target: true, dec: 2,
                 f: function (m, e) { return e.retro && e.envios ? 100 * e.retro.baja2 / e.envios : null; } },
    auc: { nombre: "AUC de BAJA+2", unidad: "", target: true, dec: 4, f: function (m, e) { return e.retro ? e.retro.auc : null; } },
    max_ex_post: { nombre: "Ganancia máxima ex post", unidad: " M", target: true, dec: 1,
                   f: function (m, e) { return e.retro ? e.retro.max_ex_post / 1e6 : null; } },
    captura: { nombre: "Ganancia / máximo ex post", unidad: " %", target: true, dec: 1,
               f: function (m, e) { return e.retro && e.retro.max_ex_post > 0 ? 100 * e.retro.ganancia / e.retro.max_ex_post : null; } }
  };
  // serie por mes: valor null y estado del target cuando la métrica requiere target y no está completo
  function serie(meses, rol, def, imp) {
    return meses.map(function (m) {
      var e = m.estr[rol];
      if (!e) return { mes: m.mes, valor: null, estado: "no_disponible" };
      if (def.target && !conTarget(m)) return { mes: m.mes, valor: null, estado: m.target ? m.target.estado : "no_disponible" };
      var v = def.f(m, e, imp);
      return { mes: m.mes, valor: v === undefined ? null : v, estado: v === null || v === undefined ? "no_disponible" : "ok" };
    });
  }

  // ---------------------------------------------------------------- modelo y datos
  var MET_SCORE = {
    "0.5": { nombre: "Mediana", f: function (e) { return e.q["0.5"]; } },
    media: { nombre: "Media", f: function (e) { return e.media; } },
    "0.9": { nombre: "Percentil 90", f: function (e) { return e.q["0.9"]; } },
    "0.99": { nombre: "Percentil 99", f: function (e) { return e.q["0.99"]; } },
    "0.999": { nombre: "Percentil 99,9", f: function (e) { return e.q["0.999"]; } },
    prob_min: { nombre: "Probabilidad mínima enviada", f: function (e) { return e.prob_min; } },
    mayor_0_5: { nombre: "Clientes con score > 0,5", entero: true, f: function (e) { return e.mayor_0_5; } }
  };
  function serieScore(meses, rol, clave) {
    var def = MET_SCORE[clave];
    return meses.map(function (m) {
      var e = m.estr[rol], v = e ? def.f(e) : null;
      return { mes: m.mes, valor: v === undefined ? null : v, estado: v === null || v === undefined ? "no_disponible" : "ok" };
    });
  }
  var MET_CLIENTES = {
    nuevos: { nombre: "Clientes nuevos", dec: 0, f: function (m) { return m.nuevos; } },
    pct_nuevos: { nombre: "% clientes nuevos", dec: 2, unidad: " %",
                  f: function (m) { return m.clientes && m.nuevos !== null && m.nuevos !== undefined ? 100 * m.nuevos / m.clientes : null; } },
    clientes: { nombre: "Clientes", dec: 0, f: function (m) { return m.clientes; } },
    con_lag1: { nombre: "Con lag1 (observación previa)", dec: 0, f: function (m) { return m.con_lag1; } },
    con_lag2: { nombre: "Con lag2", dec: 0, f: function (m) { return m.con_lag2; } },
    lag_distinto: { nombre: "Lag por fila ≠ calendario", dec: 0, f: function (m) { return m.lag_distinto; } },
    historia_meses: { nombre: "Meses de historia leídos", dec: 0, f: function (m) { return m.historia_meses; } }
  };
  var MET_COINC = {
    jaccard: { nombre: "Jaccard de enviados", dec: 3, f: function (c) { return c.jaccard; } },
    interseccion: { nombre: "Enviados por ambas", dec: 0, f: function (c) { return c.interseccion; } },
    solo_recomendacion: { nombre: "Sólo binario", dec: 0, f: function (c) { return c.solo_recomendacion; } },
    solo_alternativa: { nombre: "Sólo multiclase", dec: 0, f: function (c) { return c.solo_alternativa; } },
    correlacion_de_rangos: { nombre: "Correlación de rangos", dec: 3, f: function (c) { return c.correlacion_de_rangos; } }
  };
  function serieSimple(meses, f) {
    return meses.map(function (m) {
      var v = f(m);
      return { mes: m.mes, valor: v === undefined ? null : v, estado: v === null || v === undefined ? "no_disponible" : "ok" };
    });
  }
  // % de faltantes y % de ceros entre observados de una variable; ceros no registrados = no disponible
  function pctNulos(m, v) { return m.clientes ? 100 * ((m.nulos || {})[v] || 0) / m.clientes : null; }
  function pctCeros(m, v) {
    if (!m.ceros || !m.clientes) return null;
    var obs = m.clientes - ((m.nulos || {})[v] || 0);
    return obs > 0 ? 100 * (m.ceros[v] || 0) / obs : null;
  }
  function alertasPorVariable(meses) {
    var out = {};
    meses.forEach(function (m) {
      (m.alertas || []).forEach(function (a) {
        a.variables.forEach(function (v) {
          out[v] = out[v] || {};
          (out[v][m.mes] = out[v][m.mes] || []).push(a.regla);
        });
      });
    });
    return out;
  }

  // ---------------------------------------------------------------- operación
  var MET_MEMORIA = {
    pico_working_set_mb: { nombre: "Pico de working set", unidad: " MB" },
    pico_commit_privado_mb: { nombre: "Pico de commit privado", unidad: " MB" },
    rss_mb: { nombre: "Memoria residente al final", unidad: " MB" }
  };
  function resumenOperacion(meses, lim) {
    var r = { meses: meses.length, recuperados: [], intentos: 0, rechazos: 0, tmax: null, sobreMargen: [], sobreLimite: [],
              sinTiempo: [] };
    meses.forEach(function (m) {
      if (m.recuperado) r.recuperados.push(m.mes);
      r.intentos += (m.intentos || []).length;
      r.rechazos += m.rechazos || 0;
      if (m.total_s === null || m.total_s === undefined) { r.sinTiempo.push(m.mes); return; }
      r.tmax = r.tmax === null ? m.total_s : Math.max(r.tmax, m.total_s);
      if (m.total_s > lim.limite_s) r.sobreLimite.push(m.mes);
      else if (m.total_s > lim.margen_s) r.sobreMargen.push(m.mes);
    });
    return r;
  }

  var L = { REC: REC, ALT: ALT, ROLES: ROLES, CORTO: CORTO, VISTAS: VISTAS, nd: nd, n0: n0, mill: mill, mesTxt: mesTxt,
            estadoInicial: estadoInicial, leerEstado: leerEstado, escribirEstado: escribirEstado, rolesDe: rolesDe,
            seleccionar: seleccionar, conTarget: conTarget, agregarNegocio: agregarNegocio, MET_NEGOCIO: MET_NEGOCIO,
            serie: serie, MET_SCORE: MET_SCORE, serieScore: serieScore, MET_CLIENTES: MET_CLIENTES, MET_COINC: MET_COINC,
            serieSimple: serieSimple, pctNulos: pctNulos, pctCeros: pctCeros, alertasPorVariable: alertasPorVariable,
            MET_MEMORIA: MET_MEMORIA, resumenOperacion: resumenOperacion };
  if (typeof module !== "undefined" && module.exports) module.exports = L;
  else raiz.L = L;
})(typeof window !== "undefined" ? window : this);
