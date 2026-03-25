"use strict";

(function () {
  function posMode(mode) {
    var m = ((mode || "8h") + "").toLowerCase();
    if (m === "12h") return "12h";
    if (m === "auto") return "auto";
    return "8h";
  }

  function posModeLabel(mode) {
    var m = posMode(mode);
    if (m === "12h") return "2x12";
    if (m === "auto") return "Indistinto";
    return "3x8";
  }

  window.rPos = function rPos() {
    var sm = {};
    S.servicios.forEach(function (s) {
      sm[s.id_servicio] = s.nombre;
    });
    var tm = {};
    (S.turnos || []).forEach(function (t) {
      var pid = parseInt(t.id_posicion, 10);
      if (!tm[pid]) tm[pid] = [];
      tm[pid].push(t);
    });
    var rows = S.posiciones.map(function (p) {
      var is24 = !!p.es_24h;
      var cov = is24
        ? '<span class="tg" style="background:rgba(52,211,153,.12);color:var(--gn)">24H · ' + posModeLabel(p.modo_24h) + "</span>"
        : '<span class="tg" style="background:rgba(107,122,141,.15);color:var(--dm)">Flexible</span>';
      var turns = tm[p.id_posicion] || [];
      var turnBadges = turns.length
        ? turns
            .map(function (t) {
              var sig = t.sigla_turno || t.nombre_turno;
              return '<span class="tg" style="margin:1px 4px 1px 0">' + sig + "</span>";
            })
            .join("")
        : '<span style="font-size:11px;color:var(--dm)">Sin turnos</span>';
      var btns = p.activa
        ? '<button class="btn sm" onclick="mPosTurns(' + p.id_posicion + ')">Turnos</button> <button class="btn sm" onclick="mEditPos(' + p.id_posicion + ')">✎</button> <button class="btn dan sm" onclick="dPos(' + p.id_posicion + ')">✕</button>'
        : '<button class="btn sm" onclick="mPosTurns(' + p.id_posicion + ')">Turnos</button>';
      return (
        "<tr><td>" +
        p.id_posicion +
        "</td><td>" +
        p.nombre +
        "</td><td>" +
        (sm[p.id_servicio] || p.id_servicio) +
        "</td><td>" +
        cov +
        "</td><td>" +
        turnBadges +
        '</td><td><span class="tg ' +
        (p.activa ? "tg-on" : "tg-off") +
        '">' +
        (p.activa ? "Activa" : "Off") +
        "</span></td><td>" +
        btns +
        "</td></tr>"
      );
    }).join("");
    H(
      "pos-t",
      '<table class="dt"><thead><tr><th>ID</th><th>Nombre</th><th>Servicio</th><th>Cobertura</th><th>Turnos</th><th>Estado</th><th></th></tr></thead><tbody>' +
        rows +
        "</tbody></table>"
    );
  };

  window.syncPos24Mode = function syncPos24Mode(prefix) {
    var cb = $(prefix + "-24");
    var wrap = $(prefix + "-24mode-wrap");
    if (wrap) wrap.style.display = cb && cb.checked ? "block" : "none";
  };

  window.syncPosTemporalMode = function syncPosTemporalMode(prefix) {
    var sel = $(prefix + "-tp");
    var wrap = $(prefix + "-tp-wrap");
    if (wrap) wrap.style.display = sel && sel.value === "temporal" ? "flex" : "none";
  };

  window.mPos = function mPos() {
    var opts = S.servicios
      .filter(function (s) {
        return s.activo;
      })
      .map(function (s) {
        return '<option value="' + s.id_servicio + '">' + s.nombre + "</option>";
      })
      .join("");
    oMo(
      '<h3>Nueva posicion</h3><p style="font-size:11px;color:var(--dm);margin:0 0 10px">Define si la posicion es continua o temporal. Si es 24H se crean turnos por defecto.</p>' +
        '<div class="fr"><div class="fg gw"><label>Nombre</label><input id="i-pn"></div><div class="fg"><label>Servicio</label><select id="i-ps">' +
        opts +
        '</select></div></div>' +
        '<div class="fr"><div class="fg"><label>Temporalidad</label><select id="i-tp" onchange="syncPosTemporalMode(\'i\')"><option value="continua">Continua</option><option value="temporal">Temporal</option></select></div></div>' +
        '<div class="fr" id="i-tp-wrap" style="display:none"><div class="fg"><label>Fecha inicio</label><input type="date" id="i-fi"></div><div class="fg"><label>Fecha fin</label><input type="date" id="i-ff"></div></div>' +
        '<div class="fr"><div class="fg gw"><label style="text-transform:none;letter-spacing:0"><input type="checkbox" id="i-24" style="margin-right:6px" onchange="syncPos24Mode(\'i\')"> Posicion 24H (sumatorio diario = 24h)</label></div></div>' +
        '<div class="fr" id="i-24mode-wrap" style="display:none"><div class="fg"><label>Modo 24H</label><select id="i-24mode"><option value="8h">3 turnos (8-8-8)</option><option value="12h">2 turnos (12-12)</option><option value="auto">Indistinto (auto 12/8)</option></select></div></div>' +
        '<div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cMo()">Cancelar</button><button class="btn suc" onclick="doPos()">Crear</button></div>'
    );
    syncPos24Mode("i");
    syncPosTemporalMode("i");
  };

  window.doPos = function doPos() {
    var is24 = !!($("i-24") && $("i-24").checked);
    var mode = is24 ? V("i-24mode") || "8h" : "8h";
    var tp = V("i-tp") || "continua";
    var fi = V("i-fi");
    var ff = V("i-ff");
    api("/api/posiciones", {
      method: "POST",
      body: {
        nombre: V("i-pn"),
        id_servicio: parseInt(V("i-ps"), 10),
        es_24h: is24,
        modo_24h: mode,
        temporalidad: tp,
        fecha_inicio: tp === "temporal" ? fi : null,
        fecha_fin: tp === "temporal" ? ff : null,
      },
    })
      .then(function (r) {
        S.posiciones = r.posiciones;
        if (r.turnos) S.turnos = r.turnos;
        rPos();
        cMo();
        var newPosId = S.posiciones.reduce(function (mx, p) {
          var pid = parseInt(p.id_posicion, 10);
          return isNaN(pid) ? mx : Math.max(mx, pid);
        }, 0);
        if (newPosId) mPosTurns(newPosId);
        toast("Posicion creada", "ok");
      })
      .catch(function (e) {
        toast(e.message, "er");
      });
  };

  window.mEditPos = function mEditPos(id) {
    var p = S.posiciones.find(function (x) {
      return x.id_posicion === id;
    });
    if (!p) return;
    var totals = _posDayTotals(id);
    var info = totals
      .map(function (h, i) {
        return DF[i].substring(0, 2) + ": " + Math.round(h * 10) / 10 + "h";
      })
      .join(" · ");
    var mode = posMode(p.modo_24h);
    oMo(
      '<h3>Editar posicion</h3><div class="fr"><div class="fg gw"><label>Nombre</label><input id="ep-n" value="' +
        p.nombre +
        '"></div></div>' +
        '<div class="fr"><div class="fg gw"><label style="text-transform:none;letter-spacing:0"><input type="checkbox" id="ep-24"' +
        (p.es_24h ? " checked" : "") +
        ' style="margin-right:6px" onchange="syncPos24Mode(\'ep\')"> Posicion 24H (sumatorio diario = 24h)</label><p style="font-size:10px;color:var(--dm);margin-top:6px">Totales por dia: ' +
        info +
        "</p></div></div>" +
        '<div class="fr" id="ep-24mode-wrap" style="display:' +
        (p.es_24h ? "block" : "none") +
        '"><div class="fg"><label>Modo 24H</label><select id="ep-24mode"><option value="8h"' +
        (mode === "8h" ? " selected" : "") +
        '>3 turnos (8-8-8)</option><option value="12h"' +
        (mode === "12h" ? " selected" : "") +
        '>2 turnos (12-12)</option><option value="auto"' +
        (mode === "auto" ? " selected" : "") +
        '>Indistinto (auto 12/8)</option></select></div></div>' +
        '<div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cMo()">Cancelar</button><button class="btn pri" onclick="doEditPos(' +
        id +
        ')">Guardar</button></div>'
    );
    syncPos24Mode("ep");
  };

  window.doEditPos = function doEditPos(id) {
    var is24 = !!($("ep-24") && $("ep-24").checked);
    var mode = is24 ? V("ep-24mode") || "8h" : "8h";
    api("/api/posiciones/" + id, {
      method: "PUT",
      body: { nombre: V("ep-n"), es_24h: is24, modo_24h: mode },
    })
      .then(function (r) {
        S.posiciones = r.posiciones;
        if (r.turnos) S.turnos = r.turnos;
        rPos();
        cMo();
        toast("Posicion actualizada", "ok");
      })
      .catch(function (e) {
        toast(e.message, "er");
      });
  };

  // Override edit posicion with temporal controls.
  window.mEditPos = function mEditPos(id) {
    var p = S.posiciones.find(function (x) {
      return x.id_posicion === id;
    });
    if (!p) return;
    var totals = _posDayTotals(id);
    var info = totals
      .map(function (h, i) {
        return DF[i].substring(0, 2) + ": " + Math.round(h * 10) / 10 + "h";
      })
      .join(" · ");
    var mode = posMode(p.modo_24h);
    var tp = ((p.temporalidad || "continua") + "").toLowerCase() === "temporal" ? "temporal" : "continua";
    var fi = p.fecha_inicio || "";
    var ff = p.fecha_fin || "";
    oMo(
      '<h3>Editar posicion</h3><div class="fr"><div class="fg gw"><label>Nombre</label><input id="ep-n" value="' +
        p.nombre +
        '"></div></div>' +
        '<div class="fr"><div class="fg"><label>Temporalidad</label><select id="ep-tp" onchange="syncPosTemporalMode(\'ep\')"><option value="continua"' +
        (tp === "continua" ? " selected" : "") +
        '>Continua</option><option value="temporal"' +
        (tp === "temporal" ? " selected" : "") +
        '>Temporal</option></select></div></div>' +
        '<div class="fr" id="ep-tp-wrap" style="display:' +
        (tp === "temporal" ? "flex" : "none") +
        '"><div class="fg"><label>Fecha inicio</label><input type="date" id="ep-fi" value="' +
        fi +
        '"></div><div class="fg"><label>Fecha fin</label><input type="date" id="ep-ff" value="' +
        ff +
        '"></div></div>' +
        '<div class="fr"><div class="fg gw"><label style="text-transform:none;letter-spacing:0"><input type="checkbox" id="ep-24"' +
        (p.es_24h ? " checked" : "") +
        ' style="margin-right:6px" onchange="syncPos24Mode(\'ep\')"> Posicion 24H (sumatorio diario = 24h)</label><p style="font-size:10px;color:var(--dm);margin-top:6px">Totales por dia: ' +
        info +
        "</p></div></div>" +
        '<div class="fr" id="ep-24mode-wrap" style="display:' +
        (p.es_24h ? "block" : "none") +
        '"><div class="fg"><label>Modo 24H</label><select id="ep-24mode"><option value="8h"' +
        (mode === "8h" ? " selected" : "") +
        '>3 turnos (8-8-8)</option><option value="12h"' +
        (mode === "12h" ? " selected" : "") +
        '>2 turnos (12-12)</option><option value="auto"' +
        (mode === "auto" ? " selected" : "") +
        '>Indistinto (auto 12/8)</option></select></div></div>' +
        '<div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cMo()">Cancelar</button><button class="btn pri" onclick="doEditPos(' +
        id +
        ')">Guardar</button></div>'
    );
    syncPos24Mode("ep");
    syncPosTemporalMode("ep");
  };

  window.doEditPos = function doEditPos(id) {
    var is24 = !!($("ep-24") && $("ep-24").checked);
    var mode = is24 ? V("ep-24mode") || "8h" : "8h";
    var tp = V("ep-tp") || "continua";
    var fi = V("ep-fi");
    var ff = V("ep-ff");
    api("/api/posiciones/" + id, {
      method: "PUT",
      body: {
        nombre: V("ep-n"),
        es_24h: is24,
        modo_24h: mode,
        temporalidad: tp,
        fecha_inicio: tp === "temporal" ? fi : null,
        fecha_fin: tp === "temporal" ? ff : null,
      },
    })
      .then(function (r) {
        S.posiciones = r.posiciones;
        if (r.turnos) S.turnos = r.turnos;
        rPos();
        cMo();
        toast("Posicion actualizada", "ok");
      })
      .catch(function (e) {
        toast(e.message, "er");
      });
  };

  window.mPosTurn = function mPosTurn(pid) {
    var p = S.posiciones.find(function (x) {
      return x.id_posicion === pid;
    });
    if (!p) return;
    var sm = {};
    S.servicios.forEach(function (s) {
      sm[s.id_servicio] = s.nombre;
    });
    var dc = DF.map(function (d, i) {
      return '<label style="display:flex;gap:2px;align-items:center;font-size:11px"><input type="checkbox" class="dcp" value="' + i + '" ' + (i < 5 ? "checked" : "") + ">" + d.substring(0, 2) + "</label>";
    }).join("");
    oMo(
      '<h3>Nuevo turno</h3><p style="font-size:11px;color:var(--dm);margin:0 0 10px">Posicion: <b>' +
        (sm[p.id_servicio] || "Servicio " + p.id_servicio) +
        " · " +
        p.nombre +
        '</b></p><div class="fr"><div class="fg gw"><label>Nombre</label><input id="ip-tn" value="Refuerzo"></div></div><div class="fr"><div class="fg"><label>Hora ini</label><input type="time" id="ip-thi" value="08:00"></div><div class="fg"><label>Hora fin</label><input type="time" id="ip-thf" value="16:00"></div></div><div class="fr"><div class="fg gw"><label>Dias</label><div style="display:flex;gap:5px;flex-wrap:wrap">' +
        dc +
        '</div></div></div><div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="mPosTurns(' +
        pid +
        ')">Volver</button><button class="btn suc" onclick="doPosTurn(' +
        pid +
        ')">Crear</button></div>'
    );
  };

  window.doPosTurn = function doPosTurn(pid) {
    var dias = [];
    document.querySelectorAll(".dcp:checked").forEach(function (c) {
      dias.push(parseInt(c.value, 10));
    });
    api("/api/turnos", {
      method: "POST",
      body: {
        nombre_turno: V("ip-tn"),
        id_posicion: pid,
        hora_inicio: V("ip-thi"),
        hora_fin: V("ip-thf"),
        dias_recurrencia: dias,
      },
    })
      .then(function (r) {
        S.turnos = r.turnos;
        rPos();
        mPosTurns(pid);
        toast("Turno creado", "ok");
      })
      .catch(function (e) {
        toast(e.message, "er");
      });
  };

  window.rTrn = function rTrn() {
    var pm = {};
    (S.posiciones || []).forEach(function (p) {
      pm[p.id_posicion] = p;
    });
    var sm = {};
    (S.servicios || []).forEach(function (s) {
      sm[s.id_servicio] = s.nombre;
    });
    var rows = S.turnos
      .map(function (t) {
        var sig = t.sigla_turno || t.nombre_turno;
        var bg = sig[0] === "M" ? "rgba(56,189,248,.15);color:var(--sM)" : sig[0] === "T" ? "rgba(251,191,36,.12);color:var(--sT)" : "rgba(167,139,250,.15);color:var(--sN)";
        var dias = (t.dias_recurrencia || [])
          .map(function (d) {
            return (DF[d] || "").substring(0, 2);
          })
          .join(",");
        var pos = pm[t.id_posicion];
        var posName = pos ? pos.nombre : "Posicion " + t.id_posicion;
        var srvName = pos ? sm[pos.id_servicio] || "Servicio " + pos.id_servicio : "-";
        return '<tr><td><span class="tg" style="background:' + bg + '">' + sig + "</span></td><td>" + t.nombre_turno + "</td><td>" + srvName + "</td><td>" + posName + '</td><td style="font-family:var(--m);font-size:11px">' + (t.hora_inicio || "").substring(0, 5) + "–" + (t.hora_fin || "").substring(0, 5) + "</td><td>" + t.duracion_horas + "h</td><td>" + dias + '</td><td><button class="btn sm" onclick="mEditTrn(' + t.id_turno + ')">✎</button> <button class="btn dan sm" onclick="dTrn(' + t.id_turno + ')">✕</button></td></tr>';
      })
      .join("");
    H("trn-t", '<table class="dt"><thead><tr><th>Sigla</th><th>Nombre</th><th>Servicio</th><th>Posicion</th><th>Horario</th><th>Dur.</th><th>Dias</th><th></th></tr></thead><tbody>' + rows + "</tbody></table>");
  };

  window.mTrn = function mTrn() {
    var sm = {};
    (S.servicios || []).forEach(function (s) {
      sm[s.id_servicio] = s.nombre;
    });
    var po = S.posiciones
      .filter(function (p) {
        return p.activa;
      })
      .map(function (p) {
        var srv = sm[p.id_servicio] || "Servicio " + p.id_servicio;
        return '<option value="' + p.id_posicion + '">' + srv + " · " + p.nombre + "</option>";
      })
      .join("") + '<option value="__new__">+ Nueva posicion…</option>';
    var so = S.servicios
      .filter(function (s) {
        return s.activo;
      })
      .map(function (s) {
        return '<option value="' + s.id_servicio + '">' + s.nombre + "</option>";
      })
      .join("");
    var dc = DF.map(function (d, i) {
      return '<label style="display:flex;gap:2px;align-items:center;font-size:11px"><input type="checkbox" class="dc" value="' + i + '" ' + (i < 5 ? "checked" : "") + ">" + d.substring(0, 2) + "</label>";
    }).join("");
    oMo(
      '<h3>Nuevo turno</h3><div class="fr"><div class="fg gw"><label>Nombre</label><input id="i-tn" value="Refuerzo"></div><div class="fg"><label>Posicion</label><select id="i-tp" onchange="syncTurnoNuevaPos()">' +
        po +
        '</select></div></div><div class="fr" id="i-new-pos-wrap" style="display:none"><div class="fg gw"><label>Nueva posicion</label><input id="i-npn" placeholder="Nombre de la posicion"></div><div class="fg"><label>Servicio</label><select id="i-nps">' +
        so +
        '</select></div><div class="fg"><label style="text-transform:none;letter-spacing:0"><input type="checkbox" id="i-np24" style="margin-right:6px" onchange="syncTurnoNewPos24()">24H</label><select id="i-np24m" style="display:none"><option value="8h">3x8</option><option value="12h">2x12</option><option value="auto">Indistinto</option></select></div><div class="fg"><label>Temporalidad</label><select id="i-nptp" onchange="syncTurnoNewPosTemporal()"><option value="continua">Continua</option><option value="temporal">Temporal</option></select></div></div><div class="fr" id="i-nptp-wrap" style="display:none"><div class="fg"><label>Fecha inicio</label><input type="date" id="i-npfi"></div><div class="fg"><label>Fecha fin</label><input type="date" id="i-npff"></div></div><div class="fr"><div class="fg"><label>Hora ini</label><input type="time" id="i-thi" value="08:00"></div><div class="fg"><label>Hora fin</label><input type="time" id="i-thf" value="16:00"></div></div><div class="fr"><div class="fg gw"><label>Dias</label><div style="display:flex;gap:5px;flex-wrap:wrap">' +
        dc +
        '</div></div></div><div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cMo()">Cancelar</button><button class="btn suc" onclick="doTrn()">Crear</button></div>'
    );
    syncTurnoNuevaPos();
    syncTurnoNewPos24();
    syncTurnoNewPosTemporal();
  };

  window.syncTurnoNewPos24 = function syncTurnoNewPos24() {
    var cb = $("i-np24"), sel = $("i-np24m");
    if (sel) sel.style.display = cb && cb.checked ? "block" : "none";
  };

  window.syncTurnoNewPosTemporal = function syncTurnoNewPosTemporal() {
    var sel = $("i-nptp"), wrap = $("i-nptp-wrap");
    if (wrap) wrap.style.display = sel && sel.value === "temporal" ? "flex" : "none";
  };

  window.doTrn = function doTrn() {
    var dias = [];
    document.querySelectorAll(".dc:checked").forEach(function (c) {
      dias.push(parseInt(c.value, 10));
    });
    var createTurno = function (posId) {
      return api("/api/turnos", {
        method: "POST",
        body: {
          nombre_turno: V("i-tn"),
          id_posicion: posId,
          hora_inicio: V("i-thi"),
          hora_fin: V("i-thf"),
          dias_recurrencia: dias,
        },
      });
    };
    var posSel = V("i-tp");
    var flow;
    if (posSel === "__new__") {
      var npn = V("i-npn").trim();
      if (!npn) {
        toast("Nombre de posicion requerido", "er");
        return;
      }
      var newSrvId = parseInt(V("i-nps"), 10);
      if (isNaN(newSrvId)) {
        toast("Selecciona un servicio para la nueva posicion", "er");
        return;
      }
      var newIs24 = !!($("i-np24") && $("i-np24").checked);
      var newMode = newIs24 ? V("i-np24m") || "8h" : "8h";
      var newTp = V("i-nptp") || "continua";
      var newFi = V("i-npfi");
      var newFf = V("i-npff");
      flow = api("/api/posiciones", {
        method: "POST",
        body: {
          nombre: npn,
          id_servicio: newSrvId,
          es_24h: newIs24,
          modo_24h: newMode,
          temporalidad: newTp,
          fecha_inicio: newTp === "temporal" ? newFi : null,
          fecha_fin: newTp === "temporal" ? newFf : null,
        },
      }).then(function (r) {
        S.posiciones = r.posiciones;
        if (r.turnos) S.turnos = r.turnos;
        var newPosId = S.posiciones.reduce(function (mx, p) {
          var pid = parseInt(p.id_posicion, 10);
          return isNaN(pid) ? mx : Math.max(mx, pid);
        }, 0);
        if (!newPosId) throw new Error("No se pudo crear la nueva posicion");
        return createTurno(newPosId);
      });
    } else {
      var posId = parseInt(posSel, 10);
      if (isNaN(posId)) {
        toast("Selecciona una posicion valida", "er");
        return;
      }
      flow = createTurno(posId);
    }
    flow
      .then(function (r) {
        S.turnos = r.turnos;
        rTrn();
        rPos();
        cMo();
        toast("Turno creado", "ok");
      })
      .catch(function (e) {
        toast(e.message, "er");
      });
  };

  window.mEditTrn = function mEditTrn(id) {
    var t = S.turnos.find(function (x) {
      return x.id_turno === id;
    });
    if (!t) return;
    var pm = {};
    (S.posiciones || []).forEach(function (p) {
      pm[p.id_posicion] = p;
    });
    var sm = {};
    (S.servicios || []).forEach(function (s) {
      sm[s.id_servicio] = s.nombre;
    });
    var pos = pm[t.id_posicion];
    var posInfo = pos ? (sm[pos.id_servicio] || "Servicio " + pos.id_servicio) + " · " + pos.nombre : "Posicion " + t.id_posicion;
    var dc = DF.map(function (d, i) {
      return '<label style="display:flex;gap:2px;align-items:center;font-size:11px"><input type="checkbox" class="de" value="' + i + '"' + ((t.dias_recurrencia || []).indexOf(i) >= 0 ? " checked" : "") + ">" + d.substring(0, 2) + "</label>";
    }).join("");
    oMo(
      '<h3>Editar turno</h3><p style="font-size:11px;color:var(--dm);margin:0 0 10px">Pertenece a: <b>' +
        posInfo +
        '</b></p><div class="fr"><div class="fg gw"><label>Nombre</label><input id="et-n" value="' +
        t.nombre_turno +
        '"></div></div><div class="fr"><div class="fg"><label>Hora ini</label><input type="time" id="et-hi" value="' +
        (t.hora_inicio || "").substring(0, 5) +
        '"></div><div class="fg"><label>Hora fin</label><input type="time" id="et-hf" value="' +
        (t.hora_fin || "").substring(0, 5) +
        '"></div></div><div class="fr"><div class="fg gw"><label>Dias</label><div style="display:flex;gap:5px;flex-wrap:wrap">' +
        dc +
        '</div></div></div><div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cMo()">Cancelar</button><button class="btn pri" onclick="doEditTrn(' +
        id +
        ')">Guardar</button></div>'
    );
  };

  window.doEditTrn = function doEditTrn(id) {
    var dias = [];
    document.querySelectorAll(".de:checked").forEach(function (c) {
      dias.push(parseInt(c.value, 10));
    });
    api("/api/turnos/" + id, {
      method: "PUT",
      body: {
        nombre_turno: V("et-n"),
        hora_inicio: V("et-hi"),
        hora_fin: V("et-hf"),
        dias_recurrencia: dias,
      },
    })
      .then(function (r) {
        S.turnos = r.turnos;
        rTrn();
        rPos();
        cMo();
        toast("Turno actualizado", "ok");
      })
      .catch(function (e) {
        toast(e.message, "er");
      });
  };

  window.generar = function generar() {
    syncMonthInputs();
    var sid = selectedScheduleServiceId();
    var body = { start_date: V("c-start"), num_days: parseInt(V("c-days"), 10), max_time: solverSeconds() };
    if (sid !== null) body.id_servicio = sid;
    toast("Generando...");
    api("/api/generar", { method: "POST", body: body })
      .then(function (r) {
        SCH = r;
        HIST_ID = null;
        return api("/api/state")
          .then(function (st) {
            S = st;
          })
          .catch(function () {})
          .then(function () {
            syncInputsFromSchedule(r);
            renderSch();
            updateHistBanner();
            loadHistory();
            var el = document.querySelector('[data-pg="pg-horario"]');
            if (el) go(el);
            if (sid !== null) toast("Horario generado para el servicio seleccionado", "ok");
            else toast("Horario generado", "ok");
          });
      })
      .catch(function (e) {
        toast("Error: " + e.message, "er");
      });
  };

  window.refreshScheduleServiceFilter = function refreshScheduleServiceFilter() {
    var sel = $("sch-srv-filter");
    if (!sel || !S) return;
    var current = sel.value || "";
    var map = {};
    (S.servicios || []).forEach(function (s) {
      map[String(s.id_servicio)] = s.nombre;
    });
    if (SCH && SCH.grids) {
      Object.keys(SCH.grids).forEach(function (sk) {
        if (!map[sk]) map[sk] = (SCH.grids[sk] && SCH.grids[sk].nombre) || ("Servicio " + sk);
      });
    }
    var keys = Object.keys(map).sort(function (a, b) {
      return parseInt(a, 10) - parseInt(b, 10);
    });
    sel.innerHTML =
      '<option value="">Todos los servicios</option>' +
      keys
        .map(function (k) {
          return '<option value="' + k + '">' + map[k] + "</option>";
        })
        .join("");
    if (current && map[current]) sel.value = current;
    else if (!current && keys.length === 1) sel.value = keys[0];
    else sel.value = "";
    if (typeof refreshSchedulePositionFilter === "function") refreshSchedulePositionFilter();
  };

  window.refreshSchedulePositionFilter = function refreshSchedulePositionFilter() {
    var sel = $("sch-pos-filter");
    if (!sel || !S) return;
    var current = sel.value || "";
    var selectedSid = selectedScheduleServiceId();
    var srvMap = {};
    (S.servicios || []).forEach(function (s) {
      srvMap[String(s.id_servicio)] = s.nombre;
    });
    var map = {};
    (S.posiciones || []).forEach(function (p) {
      if (p && p.activa === false) return;
      var sid = parseInt(p.id_servicio, 10);
      var pid = parseInt(p.id_posicion, 10);
      if (isNaN(sid) || isNaN(pid) || pid <= 0) return;
      if (selectedSid !== null && sid !== selectedSid) return;
      var label = selectedSid !== null ? p.nombre : (srvMap[String(sid)] || ("Servicio " + sid)) + " · " + p.nombre;
      map[String(pid)] = label;
    });
    if (SCH && SCH.grids) {
      Object.keys(SCH.grids).forEach(function (sk) {
        if (selectedSid !== null && parseInt(sk, 10) !== selectedSid) return;
        var sd = SCH.grids[sk] || {};
        Object.keys(sd.employees || {}).forEach(function (rk) {
          var ed = sd.employees[rk] || {};
          var pid = parseInt(ed.id_posicion, 10);
          if (isNaN(pid) || pid <= 0) return;
          if (map[String(pid)]) return;
          map[String(pid)] =
            selectedSid !== null
              ? ed.posicion || ("Posición " + pid)
              : (sd.nombre || ("Servicio " + sk)) + " · " + (ed.posicion || ("Posición " + pid));
        });
      });
    }
    var keys = Object.keys(map).sort(function (a, b) {
      return parseInt(a, 10) - parseInt(b, 10);
    });
    sel.innerHTML =
      '<option value="">Todas las posiciones</option>' +
      keys
        .map(function (k) {
          return '<option value="' + k + '">' + map[k] + "</option>";
        })
        .join("");
    if (current && map[current]) sel.value = current;
    else sel.value = "";
  };

  window.selectedSchedulePositionId = function selectedSchedulePositionId() {
    var sel = $("sch-pos-filter");
    if (!sel || !sel.value) return null;
    var pid = parseInt(sel.value, 10);
    return isNaN(pid) ? null : pid;
  };

  window.onScheduleServiceFilterChange = function onScheduleServiceFilterChange() {
    refreshSchedulePositionFilter();
    renderSch();
  };

  window.onSchedulePositionFilterChange = function onSchedulePositionFilterChange() {
    renderSch();
  };

  /* window.toggleAllScheduleCrew = function toggleAllScheduleCrew(checked) {
    document.querySelectorAll(".sch-crew-cb").forEach(function (el) {
      el.checked = !!checked;
    });
  };

  window.renderScheduleCrewCrud = function renderScheduleCrewCrud() {
    var box = $("sch-crew-crud");
    if (!box) return;
    if (!S) {
      box.innerHTML = '<p style="font-size:11px;color:var(--dm)">Cargando datos…</p>';
      return;
    }
    var sid = selectedScheduleServiceId();
    if (sid === null) {
      box.innerHTML = '<p style="font-size:11px;color:var(--dm)">Selecciona un servicio para gestionar vigilantes.</p>';
      return;
    }

    var srv = (S.servicios || []).find(function (s) {
      return parseInt(s.id_servicio, 10) === sid;
    });
    if (!srv) {
      box.innerHTML = '<p style="font-size:11px;color:var(--rd)">Servicio no encontrado.</p>';
      return;
    }

    var assigned = {};
    (S.asignaciones_servicio || []).forEach(function (a) {
      if (parseInt(a.id_servicio, 10) !== sid) return;
      assigned[String(parseInt(a.id_empleado, 10))] = true;
    });

    var emps = (S.empleados || [])
      .filter(function (e) {
        return !!e.activo;
      })
      .sort(function (a, b) {
        return (a.nombre || "").localeCompare(b.nombre || "");
      });
    if (!emps.length) {
      box.innerHTML = '<p style="font-size:11px;color:var(--dm)">No hay empleados activos para asignar.</p>';
      return;
    }

    var rows = emps
      .map(function (e) {
        var eid = parseInt(e.id_empleado, 10);
        var checked = assigned[String(eid)] ? " checked" : "";
        return (
          '<tr><td style="width:32px;text-align:center"><input class="sch-crew-cb" type="checkbox" value="' +
          eid +
          '"' +
          checked +
          "></td><td>" +
          (e.nombre || ("Empleado " + eid)) +
          "</td><td style=\"font-family:var(--m);font-size:11px\">" +
          (e.horas_maximas || 0) +
          "h</td></tr>"
        );
      })
      .join("");

    box.innerHTML =
      '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:10px"><span class="tg">Servicio: ' +
      (srv.nombre || ("Servicio " + sid)) +
      '</span><button class="btn sm" onclick="toggleAllScheduleCrew(true)">Marcar todos</button><button class="btn sm" onclick="toggleAllScheduleCrew(false)">Limpiar</button><button class="btn dan sm" onclick="deleteSelectedScheduleService()">Eliminar servicio</button><div style="flex:1"></div><button class="btn pri sm" onclick="saveScheduleCrewCrud()">Guardar vigilantes</button></div>' +
      '<div class="sw"><table class="dt"><thead><tr><th></th><th>Vigilante</th><th>H. max</th></tr></thead><tbody>' +
      rows +
      "</tbody></table></div>";
  };

  window.saveScheduleCrewCrud = function saveScheduleCrewCrud() {
    var sid = selectedScheduleServiceId();
    if (sid === null) {
      toast("Selecciona un servicio", "er");
      return;
    }
    var selected = [];
    document.querySelectorAll(".sch-crew-cb:checked").forEach(function (el) {
      var eid = parseInt(el.value, 10);
      if (!isNaN(eid)) selected.push(eid);
    });
    api("/api/asignaciones_servicio/set", {
      method: "POST",
      body: {
        id_servicio: sid,
        empleados: selected,
      },
    })
      .then(function (r) {
        S.asignaciones_servicio = r.asignaciones_servicio || [];
        renderScheduleCrewCrud();
        renderSch();
        toast("Vigilantes guardados", "ok");
      })
      .catch(function (e) {
        toast(e.message, "er");
      });
  };

  window.deleteSelectedScheduleService = function deleteSelectedScheduleService() {
    var sid = selectedScheduleServiceId();
    if (sid === null) {
      toast("Selecciona un servicio", "er");
      return;
    }
    var srv = (S.servicios || []).find(function (s) {
      return parseInt(s.id_servicio, 10) === sid;
    });
    var name = srv ? srv.nombre : "este servicio";
    if (!confirm("¿Eliminar " + name + " y todo su contenido asociado?")) return;

    api("/api/servicios/" + sid, { method: "DELETE" })
      .then(function (r) {
        S.servicios = r.servicios || S.servicios;
        if (r.posiciones) S.posiciones = r.posiciones;
        if (r.turnos) S.turnos = r.turnos;
        if (r.asignaciones_servicio) S.asignaciones_servicio = r.asignaciones_servicio;
        if (SCH && SCH.grids) {
          delete SCH.grids[String(sid)];
        }
        refreshScheduleServiceFilter();
        refreshSchedulePositionFilter();
        renderScheduleCrewCrud();
        renderSch();
        toast("Servicio eliminado", "ok");
      })
      .catch(function (e) {
        toast(e.message, "er");
      });
  };

  */
  function _employeeScheduleRows() {
    var dates = (SCH && SCH.dates) || [];
    var byEmp = {};
    Object.keys((SCH && SCH.grids) || {}).forEach(function (sk) {
      var sd = SCH.grids[sk] || {};
      Object.keys(sd.employees || {}).forEach(function (rk) {
        var ed = sd.employees[rk] || {};
        var eid = parseInt(ed.id_empleado, 10);
        if (isNaN(eid)) eid = parseInt(String(rk).split(":", 1)[0], 10);
        if (isNaN(eid)) return;
        if (!byEmp[eid]) byEmp[eid] = { id: eid, nombre: ed.nombre || ("Empleado " + eid), days: {} };
        dates.forEach(function (ds) {
          var c = (ed.days || {})[ds];
          if (!c) c = { turno: "OFF", horas: 0, es_off: true };
          var score = c.es_off ? 0 : c.es_restriccion ? 1 : 2;
          var prev = byEmp[eid].days[ds];
          if (!prev || score > prev.score) {
            byEmp[eid].days[ds] = {
              score: score,
              cell: c,
              servicio: sd.nombre || ("Servicio " + sk),
              posicion: ed.posicion || "",
            };
          }
        });
      });
    });
    return Object.keys(byEmp)
      .map(function (k) {
        return byEmp[k];
      })
      .sort(function (a, b) {
        return (a.nombre || "").localeCompare(b.nombre || "");
      });
  }

  window.refreshEmployeeScheduleFilter = function refreshEmployeeScheduleFilter() {
    var sel = $("emp-sch-filter");
    if (!sel || !S) return;
    var current = sel.value || "";
    var rows = _employeeScheduleRows();
    var opts =
      '<option value="">Todos los empleados</option>' +
      rows
        .map(function (r) {
          return '<option value="' + r.id + '">' + r.nombre + "</option>";
        })
        .join("");
    sel.innerHTML = opts;
    if (current && rows.some(function (r) { return String(r.id) === current; })) sel.value = current;
    else sel.value = "";
  };

  function _selectedEmployeeScheduleId() {
    var sel = $("emp-sch-filter");
    if (!sel || !sel.value) return null;
    var eid = parseInt(sel.value, 10);
    return isNaN(eid) ? null : eid;
  }

  window.onEmployeeScheduleFilterChange = function onEmployeeScheduleFilterChange() {
    if (typeof renderSchEmpleado === "function") renderSchEmpleado();
  };

  window.renderSchEmpleado = function renderSchEmpleado() {
    var a = $("emp-sch-area");
    if (!a) return;
    refreshEmployeeScheduleFilter();
    if (!SCH || !SCH.grids) {
      a.innerHTML =
        '<div class="card"><div class="card-b" style="text-align:center;padding:50px;color:var(--dm)"><div style="font-size:40px;opacity:.3;margin-bottom:10px">👤</div><p>Sin horario generado para este mes</p></div></div>';
      return;
    }
    if (!scheduleMatchesSelection(SCH)) {
      var fi = SCH.dates && SCH.dates.length ? SCH.dates[0] : "";
      a.innerHTML =
        '<div class="card"><div class="card-b" style="text-align:center;padding:40px;color:var(--dm)"><div style="font-size:40px;opacity:.3;margin-bottom:10px">📅</div><p style="margin-bottom:10px">No hay horario generado para el mes seleccionado.</p><p style="font-size:11px;margin-bottom:16px">Último horario disponible desde <b>' +
        fi +
        '</b>.</p><button class="btn pri" onclick="showLatestScheduleMonth()">Ver último horario</button></div></div>';
      return;
    }
    var selectedEid = _selectedEmployeeScheduleId();
    var dates = SCH.dates || [];
    var rows = _employeeScheduleRows().filter(function (r) {
      return selectedEid === null || r.id === selectedEid;
    });
    if (!rows.length) {
      a.innerHTML =
        '<div class="card"><div class="card-b" style="text-align:center;padding:40px;color:var(--dm)"><div style="font-size:34px;opacity:.35;margin-bottom:8px">🔎</div><p>No hay filas para el empleado seleccionado.</p></div></div>';
      return;
    }
    var html = '<div class="card"><div class="card-h"><h3>Organización de empleados</h3></div><div class="sw"><table class="sc"><thead><tr><th class="eh">Empleado</th>';
    dates.forEach(function (ds) {
      var d = new Date(ds + "T00:00:00");
      var dow = d.getDay();
      var we = dow === 0 || dow === 6;
      html += "<th" + (we ? ' class="we"' : "") + ">" + DN[dow] + "<br>" + d.getDate() + '<br><span style="font-size:7px">' + MN[d.getMonth()] + "</span></th>";
    });
    html += "</tr></thead><tbody>";
    rows.forEach(function (row) {
      html += '<tr><td class="en">' + row.nombre + "</td>";
      dates.forEach(function (ds) {
        var info = row.days[ds];
        var c = info ? info.cell : { turno: "OFF", horas: 0, es_off: true };
        var d = new Date(ds + "T00:00:00");
        var we = d.getDay() === 0 || d.getDay() === 6;
        var cls;
        if (c.es_restriccion) {
          var sig = c.turno || "RL";
          cls = sig === "VC" ? "cVC" : sig === "BM" ? "cBM" : "cRL";
        } else {
          var t = c.turno || "OFF";
          cls = t[0] === "M" ? "cM" : t[0] === "T" ? "cT" : t[0] === "N" ? "cN" : "cO";
        }
        var tip = row.nombre + ": " + (c.turno || "OFF") + " (" + (c.horas || 0) + "h)";
        if (info && !c.es_off && !c.es_restriccion) tip += " · " + (info.servicio || "") + (info.posicion ? " · " + info.posicion : "");
        html += '<td class="cl ' + cls + (we ? " we" : "") + '" title="' + tip + '">' + (c.turno || "OFF") + "</td>";
      });
      html += "</tr>";
    });
    html += "</tbody></table></div></div>";
    a.innerHTML = html;
  };

  window.renderSchServicePivot = function renderSchServicePivot() {
    var a = $("sch-area"),
      sb = $("sts"),
      hc = $("hrs-card");
    refreshScheduleServiceFilter();
    if (!SCH || !SCH.grids) {
      a.innerHTML =
        '<div class="card"><div class="card-b" style="text-align:center;padding:50px;color:var(--dm)"><div style="font-size:40px;opacity:.3;margin-bottom:10px">ðŸ“‹</div><p>Sin horario generado para este mes</p></div></div>';
      sb.style.display = "none";
      hc.style.display = "none";
      return;
    }
    if (!scheduleMatchesSelection(SCH)) {
      var fi = SCH.dates && SCH.dates.length ? SCH.dates[0] : "";
      a.innerHTML =
        '<div class="card"><div class="card-b" style="text-align:center;padding:40px;color:var(--dm)"><div style="font-size:40px;opacity:.3;margin-bottom:10px">ðŸ“…</div><p style="margin-bottom:10px">No hay horario generado para el mes seleccionado.</p><p style="font-size:11px;margin-bottom:16px">Ãšltimo horario disponible desde <b>' +
        fi +
        '</b>.</p><button class="btn pri" onclick="showLatestScheduleMonth()">Ver Ãºltimo horario</button></div></div>';
      sb.style.display = "none";
      hc.style.display = "none";
      return;
    }

    var grids = SCH.grids,
      dates = SCH.dates || [],
      hours = SCH.hours || [];
    var selectedSid = selectedScheduleServiceId();
    var selectedPid = selectedSchedulePositionId();
    var visibleServiceKeys = Object.keys(grids).filter(function (sk) {
      return selectedSid === null || parseInt(sk, 10) === selectedSid;
    });
    if (!visibleServiceKeys.length) {
      a.innerHTML =
        '<div class="card"><div class="card-b" style="text-align:center;padding:40px;color:var(--dm)"><div style="font-size:34px;opacity:.35;margin-bottom:8px">ðŸ”Ž</div><p>No hay datos para el servicio seleccionado en este mes.</p></div></div>';
      sb.style.display = "none";
      hc.style.display = "none";
      return;
    }

    var visibleEmployees = {};
    var tc = 0;
    visibleServiceKeys.forEach(function (sk) {
      var g = grids[sk] || {};
      Object.keys(g.employees || {}).forEach(function (rk) {
        var ed = g.employees[rk] || {};
        var pid = parseInt(ed.id_posicion, 10);
        if (selectedPid !== null && pid !== selectedPid) return;
        var eid = parseInt(ed.id_empleado, 10);
        if (isNaN(eid)) eid = parseInt(String(rk).split(":", 1)[0], 10);
        if (!isNaN(eid)) visibleEmployees[String(eid)] = true;
        Object.values(ed.days || {}).forEach(function (c) {
          if (c && !c.es_off && !c.es_restriccion) tc++;
        });
      });
    });
    var te = Object.keys(visibleEmployees).length;
    var summary = SCH.summary || {};
    var filteredFaltantes = summary.faltantes || 0;
    if (selectedPid !== null && summary.faltantes_by_position) {
      filteredFaltantes = summary.faltantes_by_position[String(selectedPid)] || 0;
    } else if (selectedSid !== null && summary.faltantes_by_service) {
      filteredFaltantes = summary.faltantes_by_service[String(selectedSid)] || 0;
    }
    sb.style.display = "flex";
    H("s-emp", te);
    H("s-cub", tc);
    H("s-flt", filteredFaltantes);
    H("s-dias", dates.length);

    var posMap = {};
    (S.posiciones || []).forEach(function (p) {
      posMap[p.id_posicion] = p;
    });
    var turnByPosition = {};
    (S.turnos || []).forEach(function (t) {
      var pid = parseInt(t.id_posicion, 10);
      if (!turnByPosition[pid]) turnByPosition[pid] = [];
      turnByPosition[pid].push(t);
    });
    function turnOrder(sigla) {
      var s = (sigla || "").toUpperCase();
      if (s.charAt(0) === "M") return "1|" + s;
      if (s.charAt(0) === "T") return "2|" + s;
      if (s.charAt(0) === "N") return "3|" + s;
      return "9|" + s;
    }
    function ensureRow(rowMap, pid, posName, turnSigla, turnId) {
      var k = String(pid || 0) + "|" + String(turnSigla || "");
      if (!rowMap[k]) {
        rowMap[k] = {
          id_posicion: pid || 0,
          posicion: posName || "",
          turno: turnSigla || "",
          id_turno: turnId === undefined || turnId === null ? null : parseInt(turnId, 10),
          days: {},
        };
      } else if (turnId !== undefined && turnId !== null) {
        rowMap[k].id_turno = parseInt(turnId, 10);
      }
      return rowMap[k];
    }

    var html = "";
    var renderedServices = 0;
    visibleServiceKeys.forEach(function (sk) {
      var sid = parseInt(sk, 10);
      var sd = grids[sk] || {};
      var rowMap = {};

      Object.keys(turnByPosition).forEach(function (pidKey) {
        var pid = parseInt(pidKey, 10);
        var pos = posMap[pid];
        if (!pos) return;
        if (parseInt(pos.id_servicio, 10) !== sid) return;
        if (selectedPid !== null && pid !== selectedPid) return;
        (turnByPosition[pid] || []).forEach(function (t) {
          var sig = t.sigla_turno || t.nombre_turno || "";
          if (!sig) return;
          ensureRow(rowMap, pid, pos.nombre || ("Posicion " + pid), sig, t.id_turno);
        });
      });

      Object.keys(sd.employees || {}).forEach(function (rk) {
        var ed = sd.employees[rk] || {};
        var pid = parseInt(ed.id_posicion, 10);
        if (selectedPid !== null && pid !== selectedPid) return;
        var posName = ed.posicion || (posMap[pid] && posMap[pid].nombre) || (pid ? "Posicion " + pid : "");
        Object.keys(ed.days || {}).forEach(function (ds) {
          var c = (ed.days || {})[ds];
          if (!c || c.es_off || c.es_restriccion) return;
          var sig = c.turno || "";
          if (!sig || sig === "OFF") return;
          var row = ensureRow(rowMap, pid, posName, sig, c.id_turno);
          if (!row.days[ds]) row.days[ds] = [];
          if (row.days[ds].indexOf(ed.nombre || "") < 0) row.days[ds].push(ed.nombre || "");
        });
      });

      var rows = Object.keys(rowMap).map(function (k) {
        return rowMap[k];
      });
      rows.sort(function (a, b) {
        var byPos = (a.posicion || "").localeCompare(b.posicion || "");
        if (byPos !== 0) return byPos;
        return turnOrder(a.turno).localeCompare(turnOrder(b.turno));
      });

      var visibleDark = sd.dark_post || null;
      if (selectedPid !== null && sd.dark_post_by_position) {
        visibleDark = sd.dark_post_by_position[String(selectedPid)] || {};
      }
      var hasDark = !!(visibleDark && Object.keys(visibleDark).length);
      if (!rows.length && !hasDark) return;

      renderedServices++;
      html +=
        '<div class="card" style="margin-bottom:16px"><div class="srv-hdr">ðŸ¢ ' +
        sd.nombre +
        '</div><div class="sw"><table class="sc"><thead><tr><th class="ph">Posicion</th><th class="ph">Turno</th>';
      dates.forEach(function (ds) {
        var d = new Date(ds + "T00:00:00");
        var we = d.getDay() === 0 || d.getDay() === 6;
        html += "<th" + (we ? ' class="we"' : "") + ">" + d.getDate() + "</th>";
      });
      html += "</tr></thead><tbody>";

      rows.forEach(function (row) {
        var t = row.turno || "";
        var cls = t.charAt(0) === "M" ? "cM" : t.charAt(0) === "T" ? "cT" : t.charAt(0) === "N" ? "cN" : "cO";
        html += '<tr><td class="ep">' + (row.posicion || "") + "</td><td class='en'>" + t + "</td>";
        dates.forEach(function (ds) {
          var d = new Date(ds + "T00:00:00");
          var we = d.getDay() === 0 || d.getDay() === 6;
          var names = row.days[ds] || [];
          var label = names.join(", ");
          var click =
            ' onclick="ePivotCell(' +
            sid +
            "," +
            (row.id_posicion || 0) +
            "," +
            (row.id_turno === null || row.id_turno === undefined || isNaN(parseInt(row.id_turno, 10)) ? "null" : parseInt(row.id_turno, 10)) +
            ",'" +
            encodeURIComponent(row.turno || "") +
            "','" +
            ds +
            '\')"';
          html +=
            '<td class="cl ' +
            cls +
            (we ? " we" : "") +
            '" title="' +
            (label || "-") +
            '"' +
            click +
            ">" +
            (label || "") +
            "</td>";
        });
        html += "</tr>";
      });

      if (hasDark) {
        html += '<tr style="border-top:2px solid var(--bd)">';
        html +=
          '<td class="ep" style="color:var(--rd);opacity:.6;font-style:italic;font-size:10px">-</td><td class="ep" style="color:var(--rd);font-weight:700;font-size:9px;letter-spacing:.5px">DARK POST</td>';
        dates.forEach(function (ds) {
          var h = visibleDark[ds] || 0;
          html +=
            '<td class="cl" style="background:rgba(248,113,113,.07);color:var(--rd);font-size:8px;font-weight:700">' +
            (h > 0 ? h + "h" : "") +
            "</td>";
        });
        html += "</tr>";
      }
      html += "</tbody></table></div></div>";
    });

    if (!renderedServices) {
      a.innerHTML =
        '<div class="card"><div class="card-b" style="text-align:center;padding:40px;color:var(--dm)"><div style="font-size:34px;opacity:.35;margin-bottom:8px">ðŸ”Ž</div><p>No hay filas para el filtro de posicion seleccionado.</p></div></div>';
      sb.style.display = "none";
      hc.style.display = "none";
      return;
    }
    a.innerHTML = html;

    var filteredHours = hours.filter(function (h) {
      return visibleEmployees[String(h.id)];
    });
    if (!filteredHours.length) {
      hc.style.display = "none";
      H("hrs-area", "");
      return;
    }
    hc.style.display = "block";
    var hh =
      '<table class="ht"><thead><tr><th>Empleado</th><th>H.Trabajo</th><th>H.Restr.</th><th>Total</th><th>Objetivo</th><th>Diff</th><th style="width:25%">Balance</th></tr></thead><tbody>';
    filteredHours.forEach(function (h) {
      var pct = Math.min((h.horas_total / h.objetivo) * 100, 150);
      var cls = h.diff > 5 ? "ov" : h.diff < -10 ? "un" : "ok";
      var ds = h.diff >= 0 ? "+" + h.diff : "" + h.diff;
      var col = cls === "ok" ? "var(--gn)" : cls === "ov" ? "var(--rd)" : "var(--am)";
      hh +=
        '<tr><td style="font-weight:600;color:var(--br)">' +
        h.nombre +
        '</td><td style="font-family:var(--m)">' +
        h.horas_trabajo +
        '</td><td style="font-family:var(--m);color:var(--am)">' +
        h.horas_restriccion +
        '</td><td style="font-family:var(--m);font-weight:700">' +
        h.horas_total +
        '</td><td style="font-family:var(--m);color:var(--dm)">' +
        h.objetivo +
        '</td><td style="font-family:var(--m);color:' +
        col +
        '">' +
        ds +
        '</td><td><div class="hb"><div class="hb-f ' +
        cls +
        '" style="width:' +
        Math.min(pct, 100) +
        '%"></div></div></td></tr>';
    });
    hh += "</tbody></table>";
    H("hrs-area", hh);
  };

  window.renderSch = function renderSch() {
    return window.renderSchServicePivot();
    var a = $("sch-area"),
      sb = $("sts"),
      hc = $("hrs-card");
    refreshScheduleServiceFilter();
    if (!SCH || !SCH.grids) {
      a.innerHTML =
        '<div class="card"><div class="card-b" style="text-align:center;padding:50px;color:var(--dm)"><div style="font-size:40px;opacity:.3;margin-bottom:10px">📋</div><p>Sin horario generado para este mes</p></div></div>';
      sb.style.display = "none";
      hc.style.display = "none";
      return;
    }
    if (!scheduleMatchesSelection(SCH)) {
      var fi = SCH.dates && SCH.dates.length ? SCH.dates[0] : "";
      a.innerHTML =
        '<div class="card"><div class="card-b" style="text-align:center;padding:40px;color:var(--dm)"><div style="font-size:40px;opacity:.3;margin-bottom:10px">📅</div><p style="margin-bottom:10px">No hay horario generado para el mes seleccionado.</p><p style="font-size:11px;margin-bottom:16px">Último horario disponible desde <b>' +
        fi +
        '</b>.</p><button class="btn pri" onclick="showLatestScheduleMonth()">Ver último horario</button></div></div>';
      sb.style.display = "none";
      hc.style.display = "none";
      return;
    }
    var grids = SCH.grids,
      dates = SCH.dates,
      hours = SCH.hours || [];
    var selectedSid = selectedScheduleServiceId();
    var selectedPid = selectedSchedulePositionId();
    var visibleServiceKeys = Object.keys(grids).filter(function (sk) {
      return selectedSid === null || parseInt(sk, 10) === selectedSid;
    });
    if (!visibleServiceKeys.length) {
      a.innerHTML =
        '<div class="card"><div class="card-b" style="text-align:center;padding:40px;color:var(--dm)"><div style="font-size:34px;opacity:.35;margin-bottom:8px">🔎</div><p>No hay datos para el servicio seleccionado en este mes.</p></div></div>';
      sb.style.display = "none";
      hc.style.display = "none";
      return;
    }

    var visibleEmployees = {};
    var tc = 0;
    visibleServiceKeys.forEach(function (sk) {
      var g = grids[sk] || {};
      Object.keys(g.employees || {}).forEach(function (rk) {
        var ed = g.employees[rk] || {};
        var pid = parseInt(ed.id_posicion, 10);
        if (selectedPid !== null && pid !== selectedPid) return;
        var eid = parseInt(ed.id_empleado, 10);
        if (isNaN(eid)) eid = parseInt(String(rk).split(":", 1)[0], 10);
        if (!isNaN(eid)) visibleEmployees[String(eid)] = true;
        Object.values(ed.days || {}).forEach(function (c) {
          if (c && !c.es_off && !c.es_restriccion) tc++;
        });
      });
    });
    var te = Object.keys(visibleEmployees).length;
    var summary = SCH.summary || {};
    var filteredFaltantes = summary.faltantes || 0;
    if (selectedPid !== null && summary.faltantes_by_position) {
      filteredFaltantes = summary.faltantes_by_position[String(selectedPid)] || 0;
    } else if (selectedSid !== null && summary.faltantes_by_service) {
      filteredFaltantes = summary.faltantes_by_service[String(selectedSid)] || 0;
    }
    sb.style.display = "flex";
    H("s-emp", te);
    H("s-cub", tc);
    H("s-flt", filteredFaltantes);
    H("s-dias", dates.length);

    var html = "";
    var renderedServices = 0;
    visibleServiceKeys.forEach(function (sk) {
      var sd = grids[sk] || {};
      var entries = Object.keys(sd.employees || {})
        .map(function (rk) {
          return { key: rk, row: sd.employees[rk] };
        })
        .filter(function (entry) {
          var pid = parseInt(entry.row.id_posicion, 10);
          return selectedPid === null || pid === selectedPid;
        });
      if (!entries.length) return;
      entries.sort(function (a, b) {
        var byName = (a.row.nombre || "").localeCompare(b.row.nombre || "");
        if (byName !== 0) return byName;
        return (parseInt(a.row.id_posicion, 10) || 0) - (parseInt(b.row.id_posicion, 10) || 0);
      });
      renderedServices++;
      html +=
        '<div class="card" style="margin-bottom:16px"><div class="srv-hdr">🏢 ' +
        sd.nombre +
        '</div><div class="sw"><table class="sc"><thead><tr><th class="eh">Empleado</th><th class="ph">Posición</th>';
      dates.forEach(function (ds) {
        var d = new Date(ds + "T00:00:00");
        var dow = d.getDay();
        var we = dow === 0 || dow === 6;
        html +=
          "<th" +
          (we ? ' class="we"' : "") +
          ">" +
          DN[dow] +
          "<br>" +
          d.getDate() +
          '<br><span style="font-size:7px">' +
          MN[d.getMonth()] +
          "</span></th>";
      });
      html += "</tr></thead><tbody>";
      entries.forEach(function (entry) {
        var rk = entry.key;
        var ed = entry.row || {};
        var rowEmp = parseInt(ed.id_empleado, 10);
        if (isNaN(rowEmp)) rowEmp = parseInt(String(rk).split(":", 1)[0], 10);
        if (isNaN(rowEmp)) rowEmp = 0;
        var rowPos = parseInt(ed.id_posicion, 10);
        if (isNaN(rowPos)) rowPos = 0;
        html += '<tr><td class="en">' + ed.nombre + '</td><td class="ep">' + (ed.posicion || "") + "</td>";
        dates.forEach(function (ds) {
          var c = (ed.days || {})[ds];
          var d = new Date(ds + "T00:00:00");
          var we = d.getDay() === 0 || d.getDay() === 6;
          if (!c) {
            html += '<td class="cl cO' + (we ? " we" : "") + '">-</td>';
            return;
          }
          var turnoCell = c.turno || "OFF";
          var cls;
          if (c.es_restriccion) {
            var sig = turnoCell;
            cls = sig === "VC" ? "cVC" : sig === "BM" ? "cBM" : "cRL";
          } else {
            cls = turnoCell[0] === "M" ? "cM" : turnoCell[0] === "T" ? "cT" : turnoCell[0] === "N" ? "cN" : "cO";
          }
          var rkEnc = encodeURIComponent(rk);
          var turnoEnc = encodeURIComponent(turnoCell);
          var tid = c.id_turno === undefined || c.id_turno === null ? "null" : String(parseInt(c.id_turno, 10));
          var click = c.es_restriccion
            ? ""
            : 'onclick="eCell(' +
              sk +
              ",'" +
              rkEnc +
              "'," +
              rowEmp +
              "," +
              rowPos +
              ",'" +
              ds +
              "','" +
              turnoEnc +
              "'," +
              c.horas +
              "," +
              tid +
              ')"';
          html +=
            '<td class="cl ' +
            cls +
            (we ? " we" : "") +
            '" title="' +
            ed.nombre +
            ": " +
            turnoCell +
            " (" +
            c.horas +
            'h)" ' +
            click +
            ">" +
            turnoCell +
            "</td>";
        });
        html += "</tr>";
      });
      var visibleDark = sd.dark_post || null;
      if (selectedPid !== null && sd.dark_post_by_position) {
        visibleDark = sd.dark_post_by_position[String(selectedPid)] || {};
      }
      if (visibleDark && Object.keys(visibleDark).length) {
        html += '<tr style="border-top:2px solid var(--bd)">';
        html +=
          '<td class="en" style="color:var(--rd);opacity:.6;font-style:italic;font-size:10px">—</td><td class="ep" style="color:var(--rd);font-weight:700;font-size:9px;letter-spacing:.5px">DARK POST</td>';
        dates.forEach(function (ds) {
          var h = visibleDark[ds] || 0;
          html +=
            '<td class="cl" style="background:rgba(248,113,113,.07);color:var(--rd);font-size:8px;font-weight:700">' +
            (h > 0 ? h + "h" : "") +
            "</td>";
        });
        html += "</tr>";
      }
      html += "</tbody></table></div></div>";
    });
    if (!renderedServices) {
      a.innerHTML =
        '<div class="card"><div class="card-b" style="text-align:center;padding:40px;color:var(--dm)"><div style="font-size:34px;opacity:.35;margin-bottom:8px">🔎</div><p>No hay filas para el filtro de posición seleccionado.</p></div></div>';
      sb.style.display = "none";
      hc.style.display = "none";
      return;
    }
    a.innerHTML = html;

    var filteredHours = hours.filter(function (h) {
      return visibleEmployees[String(h.id)];
    });
    if (!filteredHours.length) {
      hc.style.display = "none";
      H("hrs-area", "");
      return;
    }
    hc.style.display = "block";
    var hh =
      '<table class="ht"><thead><tr><th>Empleado</th><th>H.Trabajo</th><th>H.Restr.</th><th>Total</th><th>Objetivo</th><th>Diff</th><th style="width:25%">Balance</th></tr></thead><tbody>';
    filteredHours.forEach(function (h) {
      var pct = Math.min((h.horas_total / h.objetivo) * 100, 150);
      var cls = h.diff > 5 ? "ov" : h.diff < -10 ? "un" : "ok";
      var ds = h.diff >= 0 ? "+" + h.diff : "" + h.diff;
      var col = cls === "ok" ? "var(--gn)" : cls === "ov" ? "var(--rd)" : "var(--am)";
      hh +=
        '<tr><td style="font-weight:600;color:var(--br)">' +
        h.nombre +
        '</td><td style="font-family:var(--m)">' +
        h.horas_trabajo +
        '</td><td style="font-family:var(--m);color:var(--am)">' +
        h.horas_restriccion +
        '</td><td style="font-family:var(--m);font-weight:700">' +
        h.horas_total +
        '</td><td style="font-family:var(--m);color:var(--dm)">' +
        h.objetivo +
        '</td><td style="font-family:var(--m);color:' +
        col +
        '">' +
        ds +
        '</td><td><div class="hb"><div class="hb-f ' +
        cls +
        '" style="width:' +
        Math.min(pct, 100) +
        '%"></div></div></td></tr>';
    });
    hh += "</tbody></table>";
    H("hrs-area", hh);
  };

  function _currentPivotNames(srv, pos, fecha, shiftSigla, turnId) {
    var names = [];
    if (!SCH || !SCH.grids || !SCH.grids[String(srv)]) return names;
    var sd = SCH.grids[String(srv)] || {};
    Object.keys(sd.employees || {}).forEach(function (rk) {
      var ed = sd.employees[rk] || {};
      var pid = parseInt(ed.id_posicion, 10);
      if (!isNaN(parseInt(pos, 10)) && pid !== parseInt(pos, 10)) return;
      var c = (ed.days || {})[fecha];
      if (!c || c.es_off || c.es_restriccion) return;
      if (turnId !== null && turnId !== undefined && !isNaN(parseInt(turnId, 10))) {
        if (parseInt(c.id_turno, 10) !== parseInt(turnId, 10)) return;
      } else {
        if ((c.turno || "") !== (shiftSigla || "")) return;
      }
      if ((ed.nombre || "") && names.indexOf(ed.nombre) < 0) names.push(ed.nombre);
    });
    names.sort(function (a, b) {
      return String(a || "").localeCompare(String(b || ""));
    });
    return names;
  }

  window.ePivotCell = function ePivotCell(srv, pos, turnId, turnoEnc, fecha) {
    var sid = parseInt(srv, 10);
    var pid = parseInt(pos, 10);
    var tid = turnId === null || turnId === undefined || isNaN(parseInt(turnId, 10)) ? null : parseInt(turnId, 10);
    var turno = decodeURIComponent(turnoEnc || "");
    if (isNaN(sid) || isNaN(pid) || !fecha || !turno) {
      toast("No se pudo abrir la edición del hueco", "er");
      return;
    }
    var url = HIST_ID !== null ? "/api/schedule/history/" + HIST_ID + "/candidates" : "/api/schedule/candidates";
    api(url, {
      method: "POST",
      body: {
        id_servicio: sid,
        id_posicion: pid,
        id_turno: tid,
        turno: turno,
        fecha: fecha,
      },
    })
      .then(function (r) {
        var current = r.current || [];
        var currentNames = current
          .map(function (x) {
            return x.nombre || "";
          })
          .filter(function (x) {
            return !!x;
          });
        if (!currentNames.length) currentNames = _currentPivotNames(sid, pid, fecha, r.turno || turno, r.id_turno);

        var candidates = r.candidates || [];
        var available = candidates.filter(function (c) {
          return !!c.disponible;
        });
        var blocked = candidates.filter(function (c) {
          return !c.disponible;
        });

        var opts = available
          .map(function (c) {
            return (
              '<option value="' +
              c.id_empleado +
              '" data-rk="' +
              encodeURIComponent(c.row_key || "") +
              '">' +
              c.nombre +
              (c.ya_asignado ? " (ya asignado)" : "") +
              "</option>"
            );
          })
          .join("");

        var blockedHtml = "";
        if (blocked.length) {
          var rows = blocked
            .slice(0, 10)
            .map(function (c) {
              return (
                "<tr><td>" +
                c.nombre +
                "</td><td style=\"font-size:10px;color:var(--dm)\">" +
                (c.motivo || "No disponible") +
                "</td></tr>"
              );
            })
            .join("");
          blockedHtml =
            '<div style="margin-top:10px"><div style="font-size:10px;color:var(--dm);margin-bottom:6px">No disponibles por tiempo/reglas</div><table class="dt"><tbody>' +
            rows +
            "</tbody></table></div>";
        }

        var currentInfo = currentNames.length
          ? currentNames.join(", ")
          : "Sin asignaciones en esta celda";

        $("emo-c").innerHTML =
          '<h3>Asignar en hueco - ' +
          fecha +
          '</h3><div class="fr"><div class="fg gw"><label>Turno</label><input value="' +
          (r.turno || turno) +
          '" disabled></div><div class="fg"><label>Horas</label><input value="' +
          (r.horas || 0) +
          'h" disabled></div></div><div class="fr"><div class="fg gw"><label>Ya asignados</label><div style="font-size:12px;color:var(--br);padding:6px 8px;border:1px solid var(--bd);border-radius:6px;background:var(--bg)">' +
          currentInfo +
          '</div></div></div><div class="fr"><div class="fg gw"><label>Disponibles</label><select id="ec-cand">' +
          (opts || '<option value="">Sin disponibles</option>') +
          '</select></div></div>' +
          blockedHtml +
          '<div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cEm()">Cancelar</button><button class="btn pri" ' +
          (available.length ? "" : "disabled ") +
          'onclick="doPivotAssign(' +
          sid +
          "," +
          pid +
          "," +
          (r.id_turno || tid || "null") +
          ",'" +
          encodeURIComponent(r.turno || turno) +
          "','" +
          fecha +
          "'," +
          (r.horas || 0) +
          ')">Asignar</button></div>';
        $("emodal").classList.add("op");
      })
      .catch(function (e) {
        toast(e.message, "er");
      });
  };

  window.doPivotAssign = function doPivotAssign(srv, pos, turnId, turnoEnc, fecha, horas) {
    var sel = $("ec-cand");
    if (!sel || !sel.value) {
      toast("No hay empleado disponible para asignar", "er");
      return;
    }
    var eid = parseInt(sel.value, 10);
    var opt = sel.selectedOptions && sel.selectedOptions.length ? sel.selectedOptions[0] : null;
    var rowKey = opt && opt.dataset ? decodeURIComponent(opt.dataset.rk || "") : "";
    var turno = decodeURIComponent(turnoEnc || "");
    var tid = turnId === null || turnId === undefined || isNaN(parseInt(turnId, 10)) ? null : parseInt(turnId, 10);
    if (isNaN(eid) || !rowKey) {
      toast("Empleado o fila inválidos para asignar", "er");
      return;
    }
    var url = HIST_ID !== null ? "/api/schedule/history/" + HIST_ID + "/edit" : "/api/schedule/edit";
    api(url, {
      method: "POST",
      body: {
        id_servicio: parseInt(srv, 10),
        id_empleado: eid,
        row_key: rowKey,
        id_posicion: parseInt(pos, 10),
        id_turno: tid,
        fecha: fecha,
        turno: turno,
        horas: parseFloat(horas) || 0,
      },
    })
      .then(function () {
        var reload = HIST_ID !== null ? api("/api/schedule/history/" + HIST_ID) : api("/api/schedule");
        return reload.then(function (data) {
          SCH = data;
          syncInputsFromSchedule(data);
          renderSch();
          cEm();
          toast("Asignación guardada", "ok");
        });
      })
      .catch(function (e) {
        toast(e.message, "er");
      });
  };

  window.eCell = function eCell(srv, rowKeyEnc, emp, pos, fecha, turnoEnc, horas, turnId) {
    var turno = decodeURIComponent(turnoEnc || "OFF");
    var pm = {};
    (S.posiciones || []).forEach(function (p) {
      pm[p.id_posicion] = p;
    });
    var shifts = (S.turnos || []).filter(function (s) {
      var pid = parseInt(s.id_posicion, 10);
      if (parseInt(pos, 10) > 0) return pid === parseInt(pos, 10);
      var p = pm[pid];
      return p ? parseInt(p.id_servicio, 10) === parseInt(srv, 10) : true;
    });
    shifts.sort(function (a, b) {
      var ah = (a.hora_inicio || "00:00") + "-" + (a.sigla_turno || a.nombre_turno || "");
      var bh = (b.hora_inicio || "00:00") + "-" + (b.sigla_turno || b.nombre_turno || "");
      return ah.localeCompare(bh);
    });
    var hasTurnId = turnId !== null && turnId !== undefined && !isNaN(parseInt(turnId, 10));
    var opts = shifts
      .map(function (s) {
        var sig = s.sigla_turno || s.nombre_turno;
        var selected = hasTurnId ? parseInt(turnId, 10) === parseInt(s.id_turno, 10) : sig === turno;
        return (
          '<option value="' +
          sig +
          '" data-tid="' +
          s.id_turno +
          '" data-pid="' +
          s.id_posicion +
          '" data-h="' +
          s.duracion_horas +
          '" ' +
          (selected ? "selected" : "") +
          ">" +
          sig +
          " (" +
          s.nombre_turno +
          " " +
          s.duracion_horas +
          "h)</option>"
        );
      })
      .join("");
    var posInfo = "";
    if (parseInt(pos, 10) > 0 && pm[parseInt(pos, 10)]) posInfo = ' <span style="color:var(--dm);font-size:11px">· ' + pm[parseInt(pos, 10)].nombre + "</span>";
    $("emo-c").innerHTML =
      '<h3>Editar turno – ' +
      fecha +
      posInfo +
      '</h3><div class="fr"><div class="fg gw"><label>Turno</label><select id="ec-t" onchange="$(\'ec-h\').value=this.selectedOptions[0].dataset.h||0">' +
      opts +
      '<option value="OFF" data-h="0" data-tid="" data-pid="' +
      (pos || 0) +
      '" ' +
      (turno === "OFF" ? "selected" : "") +
      '>OFF (0h)</option></select></div><div class="fg"><label>Horas</label><input type="number" id="ec-h" value="' +
      horas +
      '" step="0.5"></div></div><div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cEm()">Cancelar</button><button class="btn pri" onclick="doEC(' +
      srv +
      ",'" +
      rowKeyEnc +
      "'," +
      emp +
      "," +
      pos +
      ",'" +
      fecha +
      "')\">Guardar</button></div>";
    $("emodal").classList.add("op");
  };

  window.doEC = function doEC(srv, rowKeyEnc, emp, pos, f) {
    var t = V("ec-t"),
      h = NV("ec-h");
    var sel = $("ec-t").selectedOptions[0];
    var tid = sel && sel.dataset && sel.dataset.tid ? parseInt(sel.dataset.tid, 10) : null;
    var pid = sel && sel.dataset && sel.dataset.pid ? parseInt(sel.dataset.pid, 10) : parseInt(pos, 10);
    if (isNaN(pid)) pid = null;
    var url = HIST_ID !== null ? "/api/schedule/history/" + HIST_ID + "/edit" : "/api/schedule/edit";
    api(url, {
      method: "POST",
      body: {
        id_servicio: srv,
        id_empleado: emp,
        row_key: decodeURIComponent(rowKeyEnc || ""),
        id_posicion: pid,
        id_turno: tid,
        fecha: f,
        turno: t,
        horas: h,
      },
    })
      .then(function () {
        var reload = HIST_ID !== null ? api("/api/schedule/history/" + HIST_ID) : api("/api/schedule");
        return reload.then(function (data) {
          SCH = data;
          syncInputsFromSchedule(data);
          renderSch();
          cEm();
          toast("Turno actualizado", "ok");
        });
      })
      .catch(function (e) {
        toast(e.message, "er");
      });
  };
})();
