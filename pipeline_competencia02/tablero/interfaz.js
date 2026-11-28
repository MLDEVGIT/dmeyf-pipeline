/* Interfaz del tablero: pestañas, filtros compartidos, tarjetas y gráficos SVG. Depende de logica.js (window.L).
   Todo se vuelve a dibujar desde el estado S (en el fragmento de la URL) y U (selecciones locales de cada gráfico). */
(function () {
  "use strict";
  var D = JSON.parse(document.getElementById("datos").textContent);
  var L = window.L, REC = L.REC, ALT = L.ALT;
  var app = document.getElementById("app");
  var EST = {};
  D.catalogo.estrategias.forEach(function (e) { EST[e.rol] = e; });
  var COLOR = {}; COLOR[REC] = "s1"; COLOR[ALT] = "s2";
  var ETQ_T = { completa: "✓ completa", parcial: "◐ parcial", pendiente: "○ pendiente", no_disponible: "— no disponible" };
  var TODOS = D.meses.map(function (m) { return m.mes; });
  var S = L.leerEstado(location.hash, D);
  var U0 = { metNeg: "ganancia", metScore: "0.5", escala: "log", mesDist: null, variable: null, metVar: "ceros",
             metCli: "nuevos", metCoinc: "jaccard", ocultas: {}, metMem: "pico_working_set_mb" };
  var U = JSON.parse(JSON.stringify(U0));

  function esc(s) {
    return String(s === null || s === undefined ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function ayuda(t) { return '<details class="ayuda"><summary aria-label="Ayuda">?</summary><div>' + t + "</div></details>"; }
  function chipT(m) {
    var t = m.target.estado;
    var falta = m.target.falta && m.target.falta.length ? " (falta " + m.target.falta.map(L.mesTxt).join(", ") + ")" : "";
    return '<span class="chip ' + t + '" title="' + esc((ETQ_T[t] || t) + falta) + '">' + L.mesTxt(m.mes) + " " + (ETQ_T[t] || t).split(" ")[0] + "</span>";
  }
  function fmtv(v, dec, unidad) { return v === null || v === undefined ? "—" : L.nd(v, dec) + (unidad || ""); }
  function pendTxt(p) { return p.estado === "parcial" ? "parcial" : p.estado === "pendiente" ? "pendiente" : "no disponible"; }
  function opciones(obj, sel) {
    return Object.keys(obj).map(function (k) {
      return '<option value="' + k + '"' + (k === sel ? " selected" : "") + ">" + esc(obj[k].nombre) + "</option>";
    }).join("");
  }
  function sel(ctl, obj, valor, etiqueta) {
    return '<label class="ctl"><span class="sub">' + etiqueta + '</span><select data-ctl="' + ctl + '">' + opciones(obj, valor) + "</select></label>";
  }
  function tabla(cab, filas) {
    return '<div class="tabla"><table><thead><tr>' + cab.map(function (c) { return "<th>" + c + "</th>"; }).join("") +
      "</tr></thead><tbody>" + filas.map(function (f) { return "<tr>" + f.join("") + "</tr>"; }).join("") + "</tbody></table></div>";
  }
  function td(v, n) { return n ? '<td class="n">' + v + "</td>" : "<td>" + v + "</td>"; }
  function tdp(t) { return '<td class="n p">' + esc(t) + "</td>"; }
  function vacio(t) { return '<div class="vacio">' + t + "</div>"; }

  // ---------------------------------------------------------------- gráficos
  function ticks(lo, hi, n) {
    if (!(hi > lo)) { hi = lo + 1; }
    var paso = Math.pow(10, Math.floor(Math.log10((hi - lo) / n)));
    [1, 2, 2.5, 5, 10].some(function (f) { if ((hi - lo) / (paso * f) <= n) { paso *= f; return true; } return false; });
    var out = [], v = Math.floor(lo / paso) * paso;
    for (var i = 0; i < 50; i++) { out.push(+v.toFixed(10)); if (v >= hi - 1e-12) break; v += paso; }
    return out;
  }
  function escala(v, d0, d1, r0, r1) { return d1 === d0 ? r0 : r0 + (v - d0) * (r1 - r0) / (d1 - d0); }
  function leyenda(items) {
    return '<div class="leyenda">' + items.map(function (i) { return '<span><i class="' + (i.cls || "") + '" style="' + (i.color ? "background:var(--" + i.color + ")" : "") + '"></i>' + esc(i.nombre) + "</span>"; }).join("") + "</div>";
  }
  // series por mes; los puntos sin valor se marcan huecos sobre la base con su estado (pendiente, parcial, no disponible)
  function lineas(c) {
    var W = 600, H = c.alto || 220, ml = 56, mr = 78, mt = 12, mb = 28;
    var vals = [];
    c.series.forEach(function (s) { s.pts.forEach(function (p) { if (p.valor !== null && (!c.log || p.valor > 0)) vals.push(p.valor); }); });
    var hayHuecos = c.series.some(function (s) { return s.pts.some(function (p) { return p.valor === null; }); });
    if (!vals.length) {
      var motivos = {};
      c.series.forEach(function (s) { s.pts.forEach(function (p) { motivos[pendTxt(p)] = 1; }); });
      return vacio("Sin valores para la selección: " + (Object.keys(motivos).join(", ") || "no hay meses") + ".");
    }
    var tr, yt, d0, d1;
    if (c.log) {
      var lo = Math.floor(Math.log10(Math.min.apply(null, vals))), hi = Math.ceil(Math.log10(Math.max.apply(null, vals)));
      if (hi === lo) hi = lo + 1;
      yt = []; for (var k = lo; k <= hi; k++) yt.push(Math.pow(10, k));
      tr = function (v) { return Math.log10(v); }; d0 = lo; d1 = hi;
    } else {
      yt = ticks(Math.min(0, Math.min.apply(null, vals)), Math.max.apply(null, vals) * 1.05, 5);
      tr = function (v) { return v; }; d0 = yt[0]; d1 = yt[yt.length - 1];
    }
    var n = c.x.length;
    var X = function (i) { return ml + (i + 0.5) * (W - ml - mr) / n; };
    var Y = function (v) { return escala(tr(v), d0, d1, H - mb, mt); };
    var o = ['<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="' + esc(c.titulo) + '">'];
    yt.forEach(function (v) {
      o.push('<line class="grid" x1="' + ml + '" x2="' + (W - mr) + '" y1="' + Y(v).toFixed(1) + '" y2="' + Y(v).toFixed(1) + '"/>' +
             '<text x="' + (ml - 6) + '" y="' + (Y(v) + 4).toFixed(1) + '" text-anchor="end">' + esc(c.fmtEje ? c.fmtEje(v) : L.nd(v, c.decEje === undefined ? 0 : c.decEje)) + "</text>");
    });
    c.x.forEach(function (m, i) { o.push('<text x="' + X(i).toFixed(1) + '" y="' + (H - 9) + '" text-anchor="middle">' + L.mesTxt(m) + "</text>"); });
    var base = Y(c.log ? Math.pow(10, d0) : Math.max(d0, 0));
    c.series.forEach(function (s, si) {
      var tramo = [];
      var cerrar = function () { if (tramo.length > 1) o.push('<polyline fill="none" stroke="var(--' + s.color + ')" stroke-width="2" points="' + tramo.join(" ") + '"/>'); tramo = []; };
      s.pts.forEach(function (p, i) {
        if (p.valor === null || (c.log && !(p.valor > 0))) { cerrar(); return; }
        tramo.push(X(i).toFixed(1) + "," + Y(p.valor).toFixed(1));
      });
      cerrar();
      s.pts.forEach(function (p, i) {
        var tip;
        if (p.valor === null || (c.log && !(p.valor > 0))) {
          tip = L.mesTxt(p.mes) + " · " + s.nombre + ": " + pendTxt(p);
          o.push('<g data-tip="' + esc(tip) + '"><circle class="hueco" cx="' + (X(i) + si * 7 - 3).toFixed(1) + '" cy="' + (base - 6).toFixed(1) + '" r="4"/>' +
                 '<circle cx="' + X(i).toFixed(1) + '" cy="' + (base - 6).toFixed(1) + '" r="11" fill="transparent"/></g>');
          return;
        }
        tip = L.mesTxt(p.mes) + " · " + s.nombre + ": " + fmtv(p.valor, c.dec, c.unidad);
        o.push('<g data-tip="' + esc(tip) + '"><circle class="pt" cx="' + X(i).toFixed(1) + '" cy="' + Y(p.valor).toFixed(1) + '" r="4" fill="var(--' + s.color + ')"/>' +
               '<circle cx="' + X(i).toFixed(1) + '" cy="' + Y(p.valor).toFixed(1) + '" r="12" fill="transparent"/></g>');
      });
    });
    if (c.series.length <= 3) {  // rótulos directos cortos, separados
      var etq = [];
      c.series.forEach(function (s) {
        for (var i = s.pts.length - 1; i >= 0; i--) {
          var p = s.pts[i];
          if (p.valor !== null && (!c.log || p.valor > 0)) { if (s.corto) etq.push([Y(p.valor) + 4, X(i) + 9, s.corto]); break; }
        }
      });
      etq.sort(function (a, b) { return a[0] - b[0]; });
      for (var j = 1; j < etq.length; j++) etq[j][0] = Math.max(etq[j][0], etq[j - 1][0] + 13);
      etq.forEach(function (e) { o.push('<text class="etq" x="' + e[1].toFixed(1) + '" y="' + e[0].toFixed(1) + '">' + esc(e[2]) + "</text>"); });
    }
    o.push('<line class="base" x1="' + ml + '" x2="' + (W - mr) + '" y1="' + (H - mb) + '" y2="' + (H - mb) + '"/></svg>');
    var ley = c.series.length > 1 ? c.series.map(function (s) { return { nombre: s.nombre, color: s.color }; }) : [];
    if (hayHuecos) ley.push({ nombre: "sin valor (pendiente / no disponible)", cls: "hueco-ley" });
    return (ley.length ? leyenda(ley) : "") + o.join("");
  }

  function barrasTiempo(meses) {
    var W = 720, H = 270, ml = 52, mr = 132, mt = 12, mb = 28;
    var etapas = D.etapas.filter(function (e) { return !U.ocultas[e.clave]; });
    var colores = {}; D.etapas.forEach(function (e, i) { colores[e.clave] = "s" + (i + 1); });
    var tot = meses.map(function (m) { return etapas.reduce(function (a, e) { return a + (m.etapas[e.clave] || 0); }, 0); });
    var top = Math.max.apply(null, tot.concat([D.limites.limite_s * 1.05]));
    var yt = ticks(0, top, 5); top = yt[yt.length - 1];
    var Y = function (v) { return escala(v, 0, top, H - mb, mt); };
    var n = meses.length, bw = Math.min(54, (W - ml - mr) / n * 0.6);
    var o = ['<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Tiempo por mes y por etapa">'];
    yt.forEach(function (v) { o.push('<line class="grid" x1="' + ml + '" x2="' + (W - mr) + '" y1="' + Y(v).toFixed(1) + '" y2="' + Y(v).toFixed(1) + '"/><text x="' + (ml - 6) + '" y="' + (Y(v) + 4).toFixed(1) + '" text-anchor="end">' + L.n0(v) + "</text>"); });
    meses.forEach(function (m, i) {
      var cx = ml + (i + 0.5) * (W - ml - mr) / n, acc = 0;
      etapas.forEach(function (e) {
        var v = m.etapas[e.clave];
        if (!v) return;
        o.push('<rect class="seg" data-tip="' + esc(L.mesTxt(m.mes) + " · " + e.nombre + ": " + L.nd(v, 1) + " s") + '" x="' + (cx - bw / 2).toFixed(1) + '" y="' + Y(acc + v).toFixed(1) + '" width="' + bw.toFixed(1) + '" height="' + Math.max(0.5, Y(acc) - Y(acc + v)).toFixed(1) + '" fill="var(--' + colores[e.clave] + ')"/>');
        acc += v;
      });
      var lbl = m.total_s === null || m.total_s === undefined ? L.n0(acc) + (m.recuperado ? " ↻" : " *") : L.n0(acc);
      o.push('<text class="valor" x="' + cx.toFixed(1) + '" y="' + (Y(acc) - 5).toFixed(1) + '" text-anchor="middle">' + lbl + "</text>" +
             '<text x="' + cx.toFixed(1) + '" y="' + (H - 9) + '" text-anchor="middle">' + L.mesTxt(m.mes) + "</text>");
    });
    o.push('<line class="lim" x1="' + ml + '" x2="' + (W - mr) + '" y1="' + Y(D.limites.limite_s).toFixed(1) + '" y2="' + Y(D.limites.limite_s).toFixed(1) + '"/>' +
           '<text class="lim-t" x="' + (W - mr + 6) + '" y="' + (Y(D.limites.limite_s) + 4).toFixed(1) + '">límite ' + D.limites.limite_s + " s</text>" +
           '<line class="mar" x1="' + ml + '" x2="' + (W - mr) + '" y1="' + Y(D.limites.margen_s).toFixed(1) + '" y2="' + Y(D.limites.margen_s).toFixed(1) + '"/>' +
           '<text class="mar-t" x="' + (W - mr + 6) + '" y="' + (Y(D.limites.margen_s) + 4).toFixed(1) + '">margen ' + D.limites.margen_s + " s</text>" +
           '<line class="base" x1="' + ml + '" x2="' + (W - mr) + '" y1="' + (H - mb) + '" y2="' + (H - mb) + '"/></svg>');
    return o.join("");
  }

  function curva(m, roles) {
    var W = 720, H = 260, ml = 56, mr = 16, mt = 12, mb = 36;
    var ss = roles.map(function (r) { return { r: r, e: m.estr[r] }; }).filter(function (x) { return x.e && x.e.retro && x.e.retro.curva; });
    if (!ss.length) return vacio("La curva no está disponible para este mes.");
    var xs = [], ys = [];
    ss.forEach(function (x) { xs = xs.concat(x.e.retro.curva.envios); ys = ys.concat(x.e.retro.curva.ganancia.map(function (g) { return g / 1e6; })); });
    var x1 = Math.max.apply(null, xs);
    var xt = ticks(0, x1, 5).filter(function (t) { return t <= x1; });
    var yt = ticks(Math.min(0, Math.min.apply(null, ys)), Math.max.apply(null, ys) * 1.05, 5);
    var X = function (v) { return escala(v, 0, x1, ml, W - mr); };
    var Y = function (v) { return escala(v, yt[0], yt[yt.length - 1], H - mb, mt); };
    var o = ['<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Curva de ganancia ' + L.mesTxt(m.mes) + '">'];
    yt.forEach(function (v) { o.push('<line class="grid" x1="' + ml + '" x2="' + (W - mr) + '" y1="' + Y(v).toFixed(1) + '" y2="' + Y(v).toFixed(1) + '"/><text x="' + (ml - 6) + '" y="' + (Y(v) + 4).toFixed(1) + '" text-anchor="end">' + L.n0(v) + "</text>"); });
    xt.forEach(function (v) { o.push('<text x="' + X(v).toFixed(1) + '" y="' + (H - 20) + '" text-anchor="middle">' + L.n0(v) + "</text>"); });
    o.push('<text x="' + ((ml + W - mr) / 2) + '" y="' + (H - 4) + '" text-anchor="middle">envíos</text>');
    if (yt[0] < 0) o.push('<line class="base" x1="' + ml + '" x2="' + (W - mr) + '" y1="' + Y(0).toFixed(1) + '" y2="' + Y(0).toFixed(1) + '"/>');
    ss.forEach(function (x) {
      var c = COLOR[x.r], cv = x.e.retro.curva, rt = x.e.retro;
      o.push('<polyline fill="none" stroke="var(--' + c + ')" stroke-width="2" points="' + cv.envios.map(function (k, i) { return X(k).toFixed(1) + "," + Y(cv.ganancia[i] / 1e6).toFixed(1); }).join(" ") + '"/>');
      o.push('<g data-tip="' + esc(EST[x.r].corto + ": corte en " + L.n0(x.e.envios) + " envíos, " + L.mill(rt.ganancia)) + '"><circle class="pt" cx="' + X(x.e.envios).toFixed(1) + '" cy="' + Y(rt.ganancia / 1e6).toFixed(1) + '" r="5" fill="var(--' + c + ')"/><circle cx="' + X(x.e.envios).toFixed(1) + '" cy="' + Y(rt.ganancia / 1e6).toFixed(1) + '" r="12" fill="transparent"/></g>');
      o.push('<g data-tip="' + esc(EST[x.r].corto + ": máximo ex post " + L.mill(rt.max_ex_post) + " en " + L.n0(rt.k_max) + " envíos (referencia)") + '"><circle cx="' + X(rt.k_max).toFixed(1) + '" cy="' + Y(rt.max_ex_post / 1e6).toFixed(1) + '" r="5" fill="none" stroke="var(--' + c + ')" stroke-width="2"/><circle cx="' + X(rt.k_max).toFixed(1) + '" cy="' + Y(rt.max_ex_post / 1e6).toFixed(1) + '" r="12" fill="transparent"/></g>');
    });
    o.push('<line class="base" x1="' + ml + '" x2="' + (W - mr) + '" y1="' + (H - mb) + '" y2="' + (H - mb) + '"/></svg>');
    return leyenda(ss.map(function (x) { return { nombre: EST[x.r].corto, color: COLOR[x.r] }; })) + o.join("");
  }

  function perfil(m, roles) {
    var Q = ["0.01", "0.1", "0.25", "0.5", "0.75", "0.9", "0.99", "0.999"];
    var W = 720, H = 220, ml = 62, mr = 84, mt = 12, mb = 28;
    var vals = [];
    roles.forEach(function (r) { var e = m.estr[r]; if (e) Q.forEach(function (q) { if (e.q[q] > 0) vals.push(e.q[q]); }); });
    if (!vals.length) return vacio("Distribución no disponible.");
    var lo = Math.floor(Math.log10(Math.min.apply(null, vals))), hi = Math.ceil(Math.log10(Math.max.apply(null, vals)));
    var X = function (i) { return ml + (i + 0.5) * (W - ml - mr) / Q.length; };
    var Y = function (v) { return escala(Math.log10(v), lo, hi, H - mb, mt); };
    var o = ['<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Cuantiles del score">'];
    for (var k = lo; k <= hi; k++) o.push('<line class="grid" x1="' + ml + '" x2="' + (W - mr) + '" y1="' + Y(Math.pow(10, k)).toFixed(1) + '" y2="' + Y(Math.pow(10, k)).toFixed(1) + '"/><text x="' + (ml - 6) + '" y="' + (Y(Math.pow(10, k)) + 4).toFixed(1) + '" text-anchor="end">' + L.nd(Math.pow(10, k), Math.max(0, -k)) + "</text>");
    Q.forEach(function (q, i) { o.push('<text x="' + X(i).toFixed(1) + '" y="' + (H - 9) + '" text-anchor="middle">p' + L.nd(100 * q, q === "0.999" ? 1 : 0) + "</text>"); });
    roles.forEach(function (r) {
      var e = m.estr[r]; if (!e) return;
      o.push('<polyline fill="none" stroke="var(--' + COLOR[r] + ')" stroke-width="2" points="' + Q.map(function (q, i) { return X(i).toFixed(1) + "," + Y(e.q[q]).toFixed(1); }).join(" ") + '"/>');
      Q.forEach(function (q, i) { o.push('<g data-tip="' + esc(EST[r].corto + " · p" + L.nd(100 * q, q === "0.999" ? 1 : 0) + ": " + L.nd(e.q[q], 4)) + '"><circle class="pt" cx="' + X(i).toFixed(1) + '" cy="' + Y(e.q[q]).toFixed(1) + '" r="4" fill="var(--' + COLOR[r] + ')"/><circle cx="' + X(i).toFixed(1) + '" cy="' + Y(e.q[q]).toFixed(1) + '" r="11" fill="transparent"/></g>'); });
    });
    o.push('<line class="base" x1="' + ml + '" x2="' + (W - mr) + '" y1="' + (H - mb) + '" y2="' + (H - mb) + '"/></svg>');
    return leyenda(roles.filter(function (r) { return m.estr[r]; }).map(function (r) { return { nombre: EST[r].corto + " · " + EST[r].score, color: COLOR[r] }; })) + o.join("");
  }

  // ---------------------------------------------------------------- piezas comunes
  function cabecera() {
    var cat = D.catalogo;
    var filas = cat.estrategias.map(function (e) {
      return [td(esc(e.nombre)), td("<code>" + esc(e.id || "—") + "</code>"), td(esc(e.score)), td(e.fraccion ? L.nd(100 * e.fraccion, 3) + " %" : "—", true), td(String(e.modelos.length), true),
              td('<details class="mas"><summary>sha256</summary>' + e.modelos.map(function (x) { return "<code>" + x.semilla + "·" + x.sha12 + "</code>"; }).join(" ") + "</details>")];
    });
    return '<header class="cab"><div><h1>Seguimiento del pipeline · competencia 02</h1><div class="sub">Ejecución <code>' + esc(D.ejecucion) + "</code> · generado " + esc(D.generado) + "</div></div>" +
      '<span class="chip" title="Catálogo de modelos y cortes de esta ejecución">catálogo <b>' + esc(cat.nombre || "—") + "</b> · " + esc(cat.sha12 || "") + "</span></header>" +
      '<details class="mas"><summary>Estrategias y modelos del catálogo</summary>' + tabla(["Estrategia", "Id", "Score", "Corte", "Modelos", ""], filas) + "</details>" +
      '<div class="banda"><b>⚠ Importes de ganancia:</b> ' + L.n0(D.importes.premio) + " por BAJA+2 enviado y " + L.n0(D.importes.costo) + " por envío (" + esc(D.importes.fuente) + "). Confirmación para C02 pendiente.</div>";
  }
  function pestañas() {
    var t = { negocio: "Negocio", modelo: "Modelo y datos", operacion: "Operación" };
    return '<nav class="tabs" role="tablist">' + L.VISTAS.map(function (v) {
      return '<button role="tab" data-accion="vista" data-valor="' + v + '" aria-selected="' + (S.v === v) + '">' + t[v] + "</button>";
    }).join("") + "</nav>";
  }
  function filtros(meses) {
    var chips = D.meses.map(function (m) {
      var on = S.meses === null || S.meses.indexOf(m.mes) >= 0;
      return '<button class="toggle" data-accion="mes" data-valor="' + m.mes + '" aria-pressed="' + on + '" title="target ' + esc(ETQ_T[m.target.estado] || m.target.estado) + '">' + L.mesTxt(m.mes) + " " + (ETQ_T[m.target.estado] || "").split(" ")[0] + "</button>";
    }).join("");
    var estr = ["ambas", "binario", "multiclase"].map(function (e) { return '<button class="toggle" data-accion="estrategia" data-valor="' + e + '" aria-pressed="' + (S.e === e) + '">' + e + "</button>"; }).join("");
    var tg = ["todos", "completa", "parcial", "pendiente"].map(function (t) { return '<option value="' + t + '"' + (S.t === t ? " selected" : "") + ">" + (t === "todos" ? "todos" : ETQ_T[t]) + "</option>"; }).join("");
    return '<div class="filtros"><div class="grupo"><span class="et">Meses</span>' + chips +
      '<button class="boton" data-accion="todos">todos</button><button class="boton" data-accion="ninguno">ninguno</button></div>' +
      '<div class="grupo"><span class="et">Estrategia</span>' + estr + "</div>" +
      '<div class="grupo"><span class="et">Target</span><select data-ctl="target">' + tg + "</select>" + ayuda("Estado de las etiquetas del mes <i>t</i>: completa con <i>t</i>+1 y <i>t</i>+2 recibidos; parcial con sólo <i>t</i>+1; pendiente sin ninguno. Ganancia y BAJA+2 sólo existen con target completo.") + "</div>" +
      '<button class="boton" data-accion="reset">↺ Restablecer filtros</button><span class="resumen-sel">' + meses.length + " de " + D.meses.length + " meses</span></div>";
  }
  function rolesDeVista() { return L.rolesDe(S.e); }
  function chipsAlertas(meses) {
    var con = meses.filter(function (m) { return m.calidad === "con_alertas"; });
    if (!con.length) return "";
    return '<div class="banda">⚠ <b>Alertas de datos:</b> ' + con.map(function (m) {
      var det = m.deteccion ? m.deteccion.detectadas.length : null;
      var cero = (m.alertas.filter(function (a) { return a.regla === "observados_en_cero"; })[0] || { variables: [] }).variables.length;
      return '<span class="chip">' + L.mesTxt(m.mes) + " · " + cero + " columnas en 0" + (det === null ? "" : " (" + det + " inesperadas)") + "</span>";
    }).join(" ") + ' <span class="sub">Se conserva el dato recibido.</span> ' + (S.v !== "modelo" ? '<button class="boton" data-accion="vista" data-valor="modelo">ver detalle</button>' : "") + "</div>";
  }

  // ---------------------------------------------------------------- Negocio
  function vistaNegocio(meses, roles) {
    var sinT = meses.filter(function (m) { return !L.conTarget(m); });
    var o = [chipsAlertas(meses)];
    if (sinT.length) o.push('<div class="banda">Sin target completo: ' + sinT.map(chipT).join(" ") + ' <span class="sub">ganancia y BAJA+2 pendientes en esos meses; no se cuentan como 0</span></div>');
    var ag = {}; roles.forEach(function (r) { ag[r] = L.agregarNegocio(meses, r, D.importes); });
    function card(titulo, ayudaTxt, fn) {
      return '<div class="card"><div class="t"><span>' + titulo + "</span>" + ayuda(ayudaTxt) + '</div><div class="kpi">' + roles.map(function (r) {
        var x = fn(ag[r]);
        return '<div><b class="' + (x.p ? "p" : "") + '">' + x.v + '</b><small><i style="background:var(--' + COLOR[r] + ')"></i>' + EST[r].corto + (x.s ? " · " + x.s : "") + "</small></div>";
      }).join("") + "</div></div>";
    }
    var nC = function (a) { return a.completos.length; };
    o.push('<div class="tarjetas">' +
      card("Envíos", "Suma de los envíos de los meses seleccionados (métrica aditiva).", function (a) { return { v: L.n0(a.envios), s: meses.length + " meses" }; }) +
      card("BAJA+2 capturadas", "Suma de BAJA+2 enviados en los meses con target completo. Los meses sin target no suman.", function (a) { return a.baja2 === null ? { v: "pendiente", p: 1, s: "sin meses con target" } : { v: L.n0(a.baja2), s: nC(a) + " de " + meses.length + " meses" }; }) +
      card("Ganancia acumulada", "Suma de las ganancias de cada campaña mensual con target completo: 1.100.000 × BAJA+2 − 27.500 × envíos. Importes de C01, pendientes de confirmación para C02.", function (a) { return a.ganancia === null ? { v: "pendiente", p: 1, s: "sin meses con target" } : { v: L.mill(a.ganancia), s: "suma de " + nC(a) + (nC(a) === 1 ? " campaña" : " campañas") }; }) +
      card("Costo de los envíos", "27.500 × envíos de los meses seleccionados (no requiere target).", function (a) { return { v: L.mill(a.costo), s: meses.length + " meses" }; }) + "</div>");
    // evolución
    var def = L.MET_NEGOCIO[U.metNeg];
    var series = roles.map(function (r) { return { nombre: EST[r].nombre, corto: EST[r].corto, color: COLOR[r], pts: L.serie(meses, r, def, D.importes) }; });
    var ayEv = U.metNeg === "auc" ? "AUC de BAJA+2 de cada mes, con la etiqueta reconstruida. No se promedia entre meses." :
      def.target ? "Requiere target completo; los meses sin target se marcan como huecos." : "No requiere target.";
    var filas = meses.map(function (m) {
      var f = [td(L.mesTxt(m.mes))];
      var vs = roles.map(function (r) { var p = L.serie([m], r, def, D.importes)[0]; f.push(p.valor === null ? tdp(pendTxt(p)) : td(fmtv(p.valor, def.dec, def.unidad), true)); return p.valor; });
      if (roles.length === 2) f.push(vs[0] === null || vs[1] === null ? tdp("—") : td(fmtv(vs[0] - vs[1], def.dec, def.unidad), true));
      return f;
    });
    o.push('<div class="grid g2"><div class="panel"><div class="t"><h2>Evolución mensual</h2><div class="ctl">' + sel("metNeg", L.MET_NEGOCIO, U.metNeg, "Métrica") + ayuda(ayEv) + "</div></div>" +
      lineas({ titulo: def.nombre, x: meses.map(function (m) { return m.mes; }), series: series, dec: def.dec, unidad: def.unidad, decEje: def.dec > 2 ? 2 : def.dec === 2 ? 1 : 0 }) +
      '<details class="mas"><summary>Tabla y diferencia binario − multiclase</summary>' + tabla(["Mes"].concat(roles.map(function (r) { return EST[r].corto; })).concat(roles.length === 2 ? ["binario − multiclase"] : []), filas) + "</details></div>");
    // curva
    var comp = meses.filter(L.conTarget);
    var mc = comp.filter(function (m) { return m.mes === S.c; })[0] || comp[comp.length - 1];
    o.push('<div class="panel"><div class="t"><h2>Curva de ganancia</h2><div class="ctl">' +
      (comp.length ? '<label class="ctl"><span class="sub">Mes</span><select data-ctl="curva">' + comp.map(function (m) { return '<option value="' + m.mes + '"' + (m === mc ? " selected" : "") + ">" + L.mesTxt(m.mes) + "</option>"; }).join("") + "</select></label>" : "") +
      ayuda("Ganancia (M) según la cantidad de envíos, ordenando por score. Punto lleno: corte aplicado. Círculo: máximo ex post, que usa la etiqueta conocida: es referencia, no criterio.") + "</div></div>" +
      (mc ? curva(mc, roles) : vacio("No hay meses con target completo en la selección.")) + "</div></div>");
    // etiquetas
    o.push('<div class="panel" style="margin-top:12px"><div class="t"><h2>Disponibilidad de etiquetas</h2>' + ayuda("La etiqueta del mes <i>t</i> se reconstruye con la presencia de cada cliente en <i>t</i>+1 y <i>t</i>+2 (regla versión 2). Monitoreo: no cambia modelos, cortes ni salidas.") + "</div>" +
      (meses.length ? meses.map(chipT).join(" ") + tabla(["Mes", "Estado", "Falta", "BAJA+2 del mes", "Ausentes en t+1 (provisional)"], meses.map(function (m) {
        var t = m.target;
        return [td(L.mesTxt(m.mes)), td('<span class="chip ' + t.estado + '">' + (ETQ_T[t.estado] || t.estado) + "</span>"), td(t.falta.map(L.mesTxt).join(", ") || "—"),
                t.clases ? td(L.n0(t.clases["BAJA+2"]), true) : tdp(t.estado === "completa" ? "no disponible" : "pendiente"),
                t.provisional_ausentes_t1 !== undefined ? td(L.n0(t.provisional_ausentes_t1), true) : tdp("—")];
      })) : vacio("Sin meses seleccionados.")) + "</div>");
    return o.join("");
  }

  // ---------------------------------------------------------------- Modelo y datos
  function vistaModelo(meses, roles) {
    var x = meses.map(function (m) { return m.mes; });
    var o = [];
    var con = meses.filter(function (m) { return m.calidad === "con_alertas"; });
    if (con.length) {
      o.push('<div class="alerta-lista">' + con.map(function (m) {
        return '<details class="alerta"><summary><b>⚠ ' + L.mesTxt(m.mes) + "</b> · " + m.alertas.map(function (a) { return esc(a.nombre) + " (" + (a.variables.length || 1) + ")"; }).join(" · ") + " · se conserva el dato recibido</summary>" +
          m.alertas.map(function (a) { return '<div class="sub"><b>' + esc(a.nombre) + ":</b> " + a.variables.map(function (v) { return "<code>" + esc(v) + "</code>"; }).join(", ") + "</div>"; }).join("") +
          (m.deteccion && m.deteccion.detectadas.length ? '<div class="sub">E (valores distintos de 0 esperados): ' + L.n0(Math.min.apply(null, m.deteccion.detectadas.map(function (d) { return d.E; }))) + "–" + L.n0(Math.max.apply(null, m.deteccion.detectadas.map(function (d) { return d.E; }))) + ", referencia " + L.mesTxt(m.deteccion.detectadas[0].ref) + "</div>" : "") +
          '<div class="sub">Las features, el score y la selección usan el dato recibido (E06: ningún tratamiento cumplió el criterio).</div></details>';
      }).join("") + "</div>");
    }
    // scores
    var dS = L.MET_SCORE[U.metScore];
    var logOk = U.escala === "log" && !dS.entero;
    o.push('<div class="grid g2"><div class="panel"><div class="t"><h2>Scores</h2><div class="ctl">' + sel("metScore", L.MET_SCORE, U.metScore, "Estadístico") +
      '<button class="toggle" data-accion="escala" aria-pressed="' + logOk + '">log</button>' +
      ayuda("Binario: " + esc(EST[REC].objetivo) + ". Multiclase: " + esc(EST[ALT].objetivo) + ". Estiman eventos distintos: comparar la evolución de cada uno, no sus niveles.") + "</div></div>" +
      '<div class="leyenda">' + roles.map(function (r) { return '<span class="chip"><i style="background:var(--' + COLOR[r] + ');width:8px;height:8px;border-radius:2px;display:inline-block"></i>' + EST[r].corto + " = " + esc(EST[r].score) + "</span>"; }).join(" ") + "</div>" +
      lineas({ titulo: dS.nombre, x: x, log: logOk, series: roles.map(function (r) { return { nombre: EST[r].corto, corto: EST[r].corto, color: COLOR[r], pts: L.serieScore(meses, r, U.metScore) }; }), dec: dS.entero ? 0 : 4, decEje: dS.entero ? 0 : 3, fmtEje: logOk ? function (v) { return L.nd(v, Math.max(0, -Math.round(Math.log10(v)))); } : null }) + "</div>");
    var md = meses.filter(function (m) { return m.mes === U.mesDist; })[0] || meses[meses.length - 1];
    o.push('<div class="panel"><div class="t"><h2>Distribución del mes</h2><div class="ctl">' + (meses.length ? '<label class="ctl"><span class="sub">Mes</span><select data-ctl="mesDist">' + meses.map(function (m) { return '<option value="' + m.mes + '"' + (m === md ? " selected" : "") + ">" + L.mesTxt(m.mes) + "</option>"; }).join("") + "</select></label>" : "") + ayuda("Cuantiles del score en escala logarítmica.") + "</div></div>" + (md ? perfil(md, roles) : vacio("Sin meses seleccionados.")) + "</div></div>");
    // variables
    var apv = L.alertasPorVariable(meses);
    var conAl = Object.keys(apv).sort();
    var v = U.variable && D.variables.indexOf(U.variable) >= 0 ? U.variable : (conAl[0] || D.variables[0]);
    var MV = { ceros: { nombre: "% en 0 (entre observados)" }, nulos: { nombre: "% faltantes" } };
    var ptsV = meses.map(function (m) { var val = U.metVar === "ceros" ? L.pctCeros(m, v) : L.pctNulos(m, v); return { mes: m.mes, valor: val, estado: val === null ? "no_disponible" : "ok" }; });
    var ab = { cero_anomalo: "CA", observados_en_cero: "0", columna_100_nula: "N", constante_no_nula: "K", cambio_tasa_nulos: "Δn", scores_saturados: "S" };
    var calor = conAl.length ? '<div style="max-height:320px;overflow:auto">' + tabla(["Variable"].concat(x.map(L.mesTxt)), conAl.map(function (vr) {
      return [td('<button class="boton" data-accion="variable" data-valor="' + esc(vr) + '">' + esc(vr) + "</button>")].concat(x.map(function (mm) {
        var rr = apv[vr][mm];
        return rr ? '<td class="c on" title="' + esc(rr.join(", ")) + '">' + rr.map(function (q) { return ab[q] || q; }).join(" ") + "</td>" : '<td class="c"></td>';
      }));
    })) + '</div><div class="nota">CA = columna en 0 inesperada (E06) · 0 = todos los observados en 0 · N = 100 % nula · K = constante · Δn = cambio de tasa de nulos</div>' : '<div class="nota">Ninguna variable con alertas en la selección.</div>';
    o.push('<div class="grid g2"><div class="panel"><div class="t"><h2>Ceros y faltantes por variable</h2><div class="ctl"><label class="ctl"><span class="sub">Variable</span><select data-ctl="variable">' +
      D.variables.map(function (vv) { return '<option value="' + esc(vv) + '"' + (vv === v ? " selected" : "") + ">" + esc(vv) + (apv[vv] ? " ⚠" : "") + "</option>"; }).join("") + "</select></label>" +
      sel("metVar", MV, U.metVar, "Medida") + ayuda("% en 0: celdas iguales a 0 sobre las observadas (no nulas). Los meses procesados antes de registrar los ceros figuran como no disponibles.") + "</div></div>" +
      lineas({ titulo: MV[U.metVar].nombre + " · " + v, x: x, series: [{ nombre: v, corto: "", color: "s1", pts: ptsV }], dec: 2, unidad: " %", decEje: 0 }) +
      '<h3 style="margin-top:8px">Variables con alertas</h3>' + calor + "</div>");
    // clientes
    var dC = L.MET_CLIENTES[U.metCli];
    o.push('<div class="panel"><div class="t"><h2>Clientes e historia</h2><div class="ctl">' + sel("metCli", L.MET_CLIENTES, U.metCli, "Métrica") + ayuda("Cliente nuevo: sin observación previa (lags y deltas vacíos). Lag por fila ≠ calendario: le falta algún mes intermedio; los lags usan la observación previa, como en el entrenamiento.") + "</div></div>" +
      lineas({ titulo: dC.nombre, x: x, series: [{ nombre: dC.nombre, corto: "", color: "s1", pts: L.serieSimple(meses, dC.f) }], dec: dC.dec, unidad: dC.unidad, decEje: dC.dec ? 1 : 0 }) + "</div></div>");
    // coincidencia y deriva
    var dK = L.MET_COINC[U.metCoinc];
    o.push('<div class="grid g2"><div class="panel"><div class="t"><h2>Coincidencia entre estrategias</h2><div class="ctl">' + sel("metCoinc", L.MET_COINC, U.metCoinc, "Métrica") + ayuda("Compara los clientes enviados por el binario y por el multiclase en cada mes; no depende del filtro de estrategia. Jaccard = enviados por ambas / enviados por alguna.") + "</div></div>" +
      lineas({ titulo: dK.nombre, x: x, series: [{ nombre: dK.nombre, corto: "", color: "s1", pts: L.serieSimple(meses, function (m) { return m.coincidencia ? dK.f(m.coincidencia) : null; }) }], dec: dK.dec, decEje: dK.dec ? 2 : 0 }) + "</div>");
    var um = D.limites.umbral_deriva_pp;
    var defs = "<ul><li><b>Δ nulos</b>: mayor cambio absoluto, en puntos porcentuales, de la tasa de faltantes de una variable contra el mes procesado anterior; &gt; " + um + " pp activa la alerta cambio_tasa_nulos.</li>" +
      "<li><b>Δ ceros</b>: lo mismo con el % de ceros entre observados, sólo para variables con al menos " + L.n0(D.limites.min_observados_deriva) + " observados en los dos meses (desde que se registran los ceros).</li><li><b>Mediana</b>: cociente de la mediana del score contra el mes anterior (1 = sin cambio).</li>" +
      "<li><b>Columnas en 0 inesperadas</b>: regla cero_anomalo (E06).</li><li><b>PSI contra 2019</b>: no implementado, no disponible.</li></ul>";
    o.push('<div class="panel"><div class="t"><h2>Indicadores de deriva</h2>' + ayuda(defs) + "</div>" + tabla(["Mes", "contra", "Δ nulos máx (pp)", "vars Δ nulos &gt; " + um + " pp", "Δ ceros máx (pp)", "vars Δ ceros &gt; " + um + " pp", "mediana binario", "mediana multiclase", "en 0 inesperadas", "PSI 2019"], meses.map(function (m) {
      var d = m.deriva || {};
      return [td(L.mesTxt(m.mes)), d.contra ? td(L.mesTxt(d.contra)) : tdp("—"),
              d.nulos ? td(L.nd(d.nulos.max_pp, 1) + (d.nulos.variable ? ' <span class="sub">' + esc(d.nulos.variable) + "</span>" : ""), true) : tdp("—"),
              d.nulos ? td(String(d.nulos.sobre_umbral.length), true) : tdp("—"),
              d.ceros ? td(L.nd(d.ceros.max_pp, 1) + (d.ceros.variable ? ' <span class="sub">' + esc(d.ceros.variable) + "</span>" : ""), true) : tdp(d.contra ? "no disponible" : "—"),
              d.ceros ? td(String(d.ceros.sobre_umbral.length), true) : tdp(d.contra ? "no disponible" : "—"),
              d.mediana_score && d.mediana_score[REC] ? td(L.nd(d.mediana_score[REC], 2) + "×", true) : tdp("—"),
              d.mediana_score && d.mediana_score[ALT] ? td(L.nd(d.mediana_score[ALT], 2) + "×", true) : tdp("—"),
              m.deteccion ? td(String(m.deteccion.detectadas.length), true) : tdp("no evaluada"), tdp("no disponible")];
    })) + '<details class="mas"><summary>Definiciones</summary>' + defs + "</details></div></div>");
    return o.join("");
  }

  // ---------------------------------------------------------------- Operación
  function vistaOperacion(meses) {
    var lim = D.limites, r = L.resumenOperacion(meses, lim);
    var o = [];
    if (r.sobreLimite.length) o.push('<div class="banda crit">⚠ <b>Sobre el límite de ' + lim.limite_s + " s:</b> " + r.sobreLimite.map(L.mesTxt).join(", ") + "</div>");
    if (r.sobreMargen.length) o.push('<div class="banda">⚠ <b>Sobre el margen interno de ' + lim.margen_s + " s:</b> " + r.sobreMargen.map(L.mesTxt).join(", ") + "</div>");
    if (r.recuperados.length || r.rechazos) o.push('<div class="banda">↻ <b>Reintentos:</b> ' + (r.recuperados.length ? "recuperados " + r.recuperados.map(L.mesTxt).join(", ") + "; " : "") + r.rechazos + " intentos rechazados o fallidos</div>");
    o.push(chipsAlertas(meses));
    var est = r.tmax === null ? "" : r.tmax > lim.limite_s ? "⚠ sobre el límite" : r.tmax > lim.margen_s ? "⚠ sobre el margen" : "✓ dentro del margen";
    o.push('<div class="tarjetas"><div class="card"><div class="t">Meses completados</div><div class="kpi"><div><b>' + r.meses + "</b><small>de " + D.meses.length + " procesados</small></div></div></div>" +
      '<div class="card"><div class="t"><span>Tiempo máximo por mes</span>' + ayuda("Reloj del proceso mensual: desde la copia de la entrada hasta la salida y el reporte. El arranque del intérprete se mide aparte, en el ensayo secuencial.") + '</div><div class="kpi"><div><b>' + (r.tmax === null ? "—" : L.n0(r.tmax) + " s") + "</b><small>" + est + "</small></div></div></div>" +
      '<div class="card"><div class="t">Meses sobre ' + lim.margen_s + " / " + lim.limite_s + ' s</div><div class="kpi"><div><b>' + r.sobreMargen.length + " / " + r.sobreLimite.length + "</b><small>margen interno / límite</small></div></div></div>" +
      '<div class="card"><div class="t">Intentos</div><div class="kpi"><div><b>' + r.intentos + "</b><small>" + r.recuperados.length + " recuperados · " + r.rechazos + " rechazados o fallidos</small></div></div></div></div>");
    var chipsE = D.etapas.map(function (e, i) { return '<button class="toggle" data-accion="etapa" data-valor="' + e.clave + '" aria-pressed="' + !U.ocultas[e.clave] + '"><i style="display:inline-block;width:8px;height:8px;border-radius:2px;background:var(--s' + (i + 1) + ')"></i> ' + esc(e.nombre) + "</button>"; }).join(" ");
    o.push('<div class="panel" style="margin-top:12px"><div class="t"><h2>Tiempo por mes y por etapa</h2>' + ayuda("Barras: etapas seleccionadas. Línea roja: límite de la consigna (900 s). Línea punteada: margen interno (450 s), para absorber una máquina más lenta.") + "</div>" +
      '<div class="ctl">' + chipsE + "</div>" + leyenda([{ nombre: "límite de la consigna " + lim.limite_s + " s", cls: "linea-lim" }, { nombre: "margen interno " + lim.margen_s + " s", cls: "linea-mar" }]) +
      barrasTiempo(meses) + (meses.some(function (m) { return m.total_s === null || m.total_s === undefined; }) ? '<div class="nota">↻ mes recuperado: suma de las etapas del intento que publicó; su tiempo total no se registró.</div>' : "") +
      '<details class="mas"><summary>Tabla de tiempos y estado</summary>' +
      tabla(["Mes", "Estado", "Intentos", "Rechazos", "Calidad"].concat(D.etapas.map(function (e) { return esc(e.nombre); })).concat(["Total (s)", "Respecto de los límites"]), meses.map(function (m) {
        var t = m.total_s;
        return [td(L.mesTxt(m.mes)), td(m.recuperado ? "↻ recuperado" : "completado"), td(esc((m.intentos || []).join(" → ") || "—")), td(String(m.rechazos), true), td(m.calidad === "con_alertas" ? "⚠ con alertas" : "sin alertas")]
          .concat(D.etapas.map(function (e) { var v = m.etapas[e.clave]; return v === null || v === undefined ? tdp("—") : td(L.nd(v, 1), true); }))
          .concat([t === null || t === undefined ? tdp("no disponible") : td(L.nd(t, 1), true), td(t === null || t === undefined ? "—" : t > lim.limite_s ? "⚠ sobre el límite" : t > lim.margen_s ? "⚠ sobre el margen" : "✓ dentro")]);
      })) + "</details></div>");
    var dM = L.MET_MEMORIA[U.metMem];
    o.push('<div class="grid g2"><div class="panel"><div class="t"><h2>Memoria</h2><div class="ctl">' + sel("metMem", L.MET_MEMORIA, U.metMem, "Medida") + ayuda("Del proceso mensual, según el sistema operativo.") + "</div></div>" +
      lineas({ titulo: dM.nombre, x: meses.map(function (m) { return m.mes; }), series: [{ nombre: dM.nombre, corto: "", color: "s1", pts: L.serieSimple(meses, function (m) { return m.memoria ? m.memoria[U.metMem] : null; }) }], dec: 0, unidad: " MB" }) + "</div>");
    var uniq = function (f) { var s = {}; meses.forEach(function (m) { var v = f(m); s[v === null || v === undefined ? "no disponible" : v] = 1; }); return Object.keys(s).join(", ") || "—"; };
    var sw = function (k) { return uniq(function (m) { return m.versiones ? m.versiones[k] : null; }); };
    o.push('<div class="panel"><div class="t"><h2>Versiones</h2>' + ayuda("Valores distintos entre los meses seleccionados. «no disponible»: el mes no registró ese dato.") + "</div>" +
      tabla(["Componente", "Versión"], [[td("Catálogo"), td(esc((D.catalogo.nombre || "—") + " · " + uniq(function (m) { return m.catalogo_sha12; })))],
        [td("Política de incidentes"), td(esc(uniq(function (m) { return m.politica; })))], [td("Regla del target"), td(esc(uniq(function (m) { return m.regla_target; })))],
        [td("Python"), td(esc(sw("python")))], [td("LightGBM"), td(esc(sw("lightgbm")))], [td("DuckDB"), td(esc(sw("duckdb")))], [td("numpy / pandas"), td(esc(sw("numpy") + " / " + sw("pandas")))]]) +
      '<details class="mas"><summary>Modelos (semilla · sha256)</summary>' + D.catalogo.estrategias.map(function (e) { return '<div class="sub"><b>' + esc(e.corto) + ":</b> " + e.modelos.map(function (x) { return "<code>" + x.semilla + "·" + x.sha12 + "</code>"; }).join(" ") + "</div>"; }).join("") + "</details></div></div>");
    return o.join("");
  }

  // ---------------------------------------------------------------- render y eventos
  function render() {
    var meses = L.seleccionar(D, S), roles = rolesDeVista();
    var cuerpo;
    if (!D.meses.length) cuerpo = vacio("Todavía no hay meses completados en esta ejecución.");
    else if (!meses.length) cuerpo = vacio('Ningún mes cumple los filtros. <button class="boton" data-accion="reset">↺ Restablecer filtros</button>');
    else cuerpo = S.v === "negocio" ? vistaNegocio(meses, roles) : S.v === "modelo" ? vistaModelo(meses, roles) : vistaOperacion(meses);
    var y = window.scrollY;
    app.innerHTML = cabecera() + pestañas() + filtros(meses) + '<main role="tabpanel">' + cuerpo + "</main>";
    window.scrollTo(0, y);
    var h = L.escribirEstado(S);
    if (location.hash !== h) { try { history.replaceState(null, "", h); } catch (e) { /* file:// en algunos navegadores */ } }
  }
  app.addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-accion]");
    if (!b) return;
    var a = b.getAttribute("data-accion"), v = b.getAttribute("data-valor");
    if (a === "vista") S.v = v;
    else if (a === "mes") {
      var m = +v, act = S.meses === null ? TODOS.slice() : S.meses.slice(), i = act.indexOf(m);
      if (i >= 0) act.splice(i, 1); else act.push(m);
      act.sort();
      S.meses = act.length === TODOS.length ? null : act;
    } else if (a === "todos") S.meses = null;
    else if (a === "ninguno") S.meses = [];
    else if (a === "estrategia") S.e = v;
    else if (a === "reset") { var vista = S.v; S = L.estadoInicial(D); S.v = vista; U = JSON.parse(JSON.stringify(U0)); }
    else if (a === "escala") U.escala = U.escala === "log" ? "lineal" : "log";
    else if (a === "etapa") U.ocultas[v] = !U.ocultas[v];
    else if (a === "variable") U.variable = v;
    else return;
    render();
  });
  app.addEventListener("change", function (ev) {
    var c = ev.target.getAttribute("data-ctl");
    if (!c) return;
    var v = ev.target.value;
    if (c === "target") S.t = v;
    else if (c === "curva") S.c = +v;
    else if (c === "mesDist") U.mesDist = +v;
    else U[c] = v;
    render();
  });
  window.addEventListener("hashchange", function () { S = L.leerEstado(location.hash, D); render(); });
  // ayuda contextual de los gráficos
  var tip = document.createElement("div");
  tip.id = "tip"; tip.setAttribute("role", "tooltip");
  document.body.appendChild(tip);
  app.addEventListener("mousemove", function (ev) {
    var t = ev.target.closest && ev.target.closest("[data-tip]");
    if (!t) { tip.className = ""; return; }
    tip.textContent = t.getAttribute("data-tip");
    tip.className = "on";
    var x = Math.min(ev.clientX + 12, window.innerWidth - tip.offsetWidth - 8);
    tip.style.left = Math.max(8, x) + "px"; tip.style.top = (ev.clientY + 14) + "px";
  });
  app.addEventListener("mouseleave", function () { tip.className = ""; });
  render();
})();
