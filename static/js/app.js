"use strict";
var S=null,SCH=null,HIST_ID=null;
var DN=["D","L","M","X","J","V","S"],MN=["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];
var DF=["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"];
var TIT={"pg-horario":"Cuadrante - Servicio","pg-horario-empleado":"Cuadrante empleado","pg-config":"Configuración","pg-resumen":"Resúmenes",
  "pg-servicios":"Servicios","pg-posiciones":"Posiciones y turnos","pg-turnos":"Turnos","pg-empleados":"Empleados",
  "pg-catalogo":"Catálogo de restricciones","pg-restricciones":"Restricciones asignadas",
  "pg-asignaciones":"Asignación servicio→empleado","pg-conciliaciones":"Conciliaciones"};

function $(id){return document.getElementById(id)}
function V(id){return $(id).value}
function NV(id){return parseFloat($(id).value)||0}
function H(id,h){var e=$(id);if(e)e.innerHTML=h}

function toast(m,t){var c=$("tts"),e=document.createElement("div");e.className="tt "+(t||"");e.textContent=m;c.appendChild(e);setTimeout(function(){e.remove()},3500)}
function formatLocalDate(d){
  var y=d.getFullYear();
  var m=("0"+(d.getMonth()+1)).slice(-2);
  var day=("0"+d.getDate()).slice(-2);
  return y+"-"+m+"-"+day;
}
function monthDaysForValue(v){
  if(!v)return 31;
  var d=new Date(v+"T00:00:00");
  return new Date(d.getFullYear(),d.getMonth()+1,0).getDate();
}
function syncMonthInputs(){
  var startEl=$("c-start"),daysEl=$("c-days");
  if(!startEl||!daysEl||!startEl.value)return;
  var d=new Date(startEl.value+"T00:00:00");
  d.setDate(1);
  startEl.value=formatLocalDate(d);
  daysEl.value=monthDaysForValue(startEl.value);
}
function scheduleMatchesSelection(schedule){
  var startEl=$("c-start"),daysEl=$("c-days");
  if(!schedule||!schedule.dates||!schedule.dates.length)return false;
  if(!startEl||!daysEl)return true;
  return schedule.dates[0]===startEl.value && schedule.dates.length===(parseInt(daysEl.value)||schedule.dates.length);
}
function syncInputsFromSchedule(schedule){
  var startEl=$("c-start"),daysEl=$("c-days");
  if(!schedule||!schedule.dates||!schedule.dates.length||!startEl||!daysEl)return;
  startEl.value=schedule.dates[0];
  daysEl.value=schedule.dates.length;
  updateNavPeriodo();
}
function showLatestScheduleMonth(){
  if(!SCH||!SCH.dates||!SCH.dates.length)return;
  syncInputsFromSchedule(SCH);
  renderSch();
  if(typeof renderSchEmpleado==="function") renderSchEmpleado();
  toast("Mostrando el último horario generado","ok");
}
function solverSeconds(){
  var raw=parseInt(V("c-time"),10);
  return raw>0?raw:30;
}

function api(path,opts){
  opts=opts||{};
  return fetch(path,{method:opts.method||"GET",headers:{"Content-Type":"application/json"},
    body:opts.body?JSON.stringify(opts.body):undefined})
  .then(function(r){
    if(!r.ok) return r.json().then(function(e){throw new Error(e.error||r.statusText)});
    return r.json();
  });
}

// ═══ NAVIGATION ═══════════════════════════════════════════════════
function go(el){
  var pg=el.getAttribute("data-pg");
  document.querySelectorAll(".pg").forEach(function(p){p.classList.add("hid")});
  $(pg).classList.remove("hid");
  document.querySelectorAll(".nav").forEach(function(n){n.classList.remove("on")});
  el.classList.add("on");
  $("title").textContent=TIT[pg]||"";
  load(pg);
}

function load(pg){
  if(!S){api("/api/state").then(function(d){S=d;load(pg)});return}
  if(pg==="pg-servicios") rSrv();
  if(pg==="pg-posiciones") rPos();
  if(pg==="pg-turnos") rTrn();
  if(pg==="pg-empleados") rEmp();
  if(pg==="pg-catalogo") rCat();
  if(pg==="pg-restricciones") rRes();
  if(pg==="pg-asignaciones"){_loadAsigData().then(function(){rAsig()}).catch(function(e){toast(e.message,"er")});}
  if(pg==="pg-conciliaciones") rConc();
  if(pg==="pg-resumen") rResSel();
  if(pg==="pg-horario"){refreshScheduleServiceFilter();if(SCH)renderSch();loadHistory();updateNavPeriodo();}
  if(pg==="pg-horario-empleado"){if(typeof refreshEmployeeScheduleFilter==="function")refreshEmployeeScheduleFilter();if(SCH&&typeof renderSchEmpleado==="function")renderSchEmpleado();updateNavPeriodo();}
}

// ═══ MODALS ═══════════════════════════════════════════════════════
function oMo(h){$("mo-c").innerHTML=h;$("modal").classList.add("op")}
function cMo(){$("modal").classList.remove("op")}
function cEm(){$("emodal").classList.remove("op")}

// ═══ SERVICIOS ════════════════════════════════════════════════════
function rSrv(){
  var rows=S.servicios.map(function(s){
    var btns=s.activo?'<button class="btn sm" onclick="mEditSrv('+s.id_servicio+')">✎</button> <button class="btn dan sm" onclick="dSrv('+s.id_servicio+')">✕</button>':'';
    return '<tr><td>'+s.id_servicio+'</td><td>'+s.nombre+'</td><td>'+s.area+'</td><td>'+s.centro_coste+'</td><td><span class="tg '+(s.activo?'tg-on':'tg-off')+'">'+(s.activo?'Activo':'Off')+'</span></td><td>'+btns+'</td></tr>'}).join("");
  H("srv-t",'<table class="dt"><thead><tr><th>ID</th><th>Nombre</th><th>Área</th><th>CC</th><th>Estado</th><th></th></tr></thead><tbody>'+rows+'</tbody></table>');
}
function mSrv(){oMo('<h3>Nuevo servicio</h3><div class="fr"><div class="fg gw"><label>Nombre</label><input id="i-sn"></div><div class="fg"><label>Área</label><input id="i-sa"></div><div class="fg"><label>CC</label><input id="i-sc"></div></div><div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cMo()">Cancelar</button><button class="btn suc" onclick="doSrv()">Crear</button></div>')}
function doSrv(){api("/api/servicios",{method:"POST",body:{nombre:V("i-sn"),area:V("i-sa"),centro_coste:V("i-sc")}}).then(function(r){S.servicios=r.servicios;rSrv();cMo();toast("Servicio creado","ok")}).catch(function(e){toast(e.message,"er")})}
function dSrv(id){api("/api/servicios/"+id,{method:"DELETE"}).then(function(r){S.servicios=r.servicios;rSrv();toast("Eliminado","ok")})}
function mEditSrv(id){
  var s=S.servicios.find(function(x){return x.id_servicio===id});if(!s)return;
  oMo('<h3>Editar servicio</h3><div class="fr"><div class="fg gw"><label>Nombre</label><input id="es-n" value="'+s.nombre+'"></div><div class="fg"><label>Área</label><input id="es-a" value="'+(s.area||"")+'"></div><div class="fg"><label>CC</label><input id="es-c" value="'+(s.centro_coste||"")+'"></div></div><div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cMo()">Cancelar</button><button class="btn pri" onclick="doEditSrv('+id+')">Guardar</button></div>');
}
function doEditSrv(id){
  api("/api/servicios/"+id,{method:"PUT",body:{nombre:V("es-n"),area:V("es-a"),centro_coste:V("es-c")}}).then(function(r){S.servicios=r.servicios;rSrv();cMo();toast("Servicio actualizado","ok")}).catch(function(e){toast(e.message,"er")});
}

// ═══ POSICIONES ═══════════════════════════════════════════════════
function rPos(){
  var sm={};S.servicios.forEach(function(s){sm[s.id_servicio]=s.nombre});
  var tm={};(S.turnos||[]).forEach(function(t){
    var pid=parseInt(t.id_posicion,10);
    if(!tm[pid]) tm[pid]=[];
    tm[pid].push(t);
  });
  var rows=S.posiciones.map(function(p){
    var is24=!!p.es_24h;
    var mode=((p.modo_24h||"8h")+"").toLowerCase();
    var modeLbl=mode==="12h"?"2x12":mode==="auto"?"Indistinto":"3x8";
    var cov=is24?'<span class="tg" style="background:rgba(52,211,153,.12);color:var(--gn)">24H · '+modeLbl+'</span>':'<span class="tg" style="background:rgba(107,122,141,.15);color:var(--dm)">Flexible</span>';
    var turns=(tm[p.id_posicion]||[]);
    var turnBadges=turns.length?turns.map(function(t){
      var sig=t.sigla_turno||t.nombre_turno;
      return '<span class="tg" style="margin:1px 4px 1px 0">'+sig+'</span>';
    }).join(""):'<span style="font-size:11px;color:var(--dm)">Sin turnos</span>';
    var btns=p.activa
      ?'<button class="btn sm" onclick="mPosTurns('+p.id_posicion+')">Turnos</button> <button class="btn sm" onclick="mEditPos('+p.id_posicion+')">✎</button> <button class="btn dan sm" onclick="dPos('+p.id_posicion+')">✕</button>'
      :'<button class="btn sm" onclick="mPosTurns('+p.id_posicion+')">Turnos</button>';
    return '<tr><td>'+p.id_posicion+'</td><td>'+p.nombre+'</td><td>'+(sm[p.id_servicio]||p.id_servicio)+'</td><td>'+cov+'</td><td>'+turnBadges+'</td><td><span class="tg '+(p.activa?'tg-on':'tg-off')+'">'+(p.activa?'Activa':'Off')+'</span></td><td>'+btns+'</td></tr>'}).join("");
  H("pos-t",'<table class="dt"><thead><tr><th>ID</th><th>Nombre</th><th>Servicio</th><th>Cobertura</th><th>Turnos</th><th>Estado</th><th></th></tr></thead><tbody>'+rows+'</tbody></table>');
}
function mPos(){
  var opts=S.servicios.filter(function(s){return s.activo}).map(function(s){return '<option value="'+s.id_servicio+'">'+s.nombre+'</option>'}).join("");
  oMo('<h3>Nueva posición</h3><p style="font-size:11px;color:var(--dm);margin:0 0 10px">Después podrás crear sus turnos desde esta misma pantalla.</p><div class="fr"><div class="fg gw"><label>Nombre</label><input id="i-pn"></div><div class="fg"><label>Servicio</label><select id="i-ps">'+opts+'</select></div></div><div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cMo()">Cancelar</button><button class="btn suc" onclick="doPos()">Crear</button></div>')}
function doPos(){api("/api/posiciones",{method:"POST",body:{nombre:V("i-pn"),id_servicio:parseInt(V("i-ps"))}}).then(function(r){
  S.posiciones=r.posiciones;
  rPos();
  cMo();
  var newPosId=S.posiciones.reduce(function(mx,p){
    var pid=parseInt(p.id_posicion,10);
    return isNaN(pid)?mx:Math.max(mx,pid);
  },0);
  if(newPosId){mPosTurns(newPosId);}
  toast("Posición creada","ok")
}).catch(function(e){toast(e.message,"er")})}
function dPos(id){api("/api/posiciones/"+id,{method:"DELETE"}).then(function(r){S.posiciones=r.posiciones;rPos()})}
function mEditPos(id){
  var p=S.posiciones.find(function(x){return x.id_posicion===id});if(!p)return;
  oMo('<h3>Editar posición</h3><div class="fr"><div class="fg gw"><label>Nombre</label><input id="ep-n" value="'+p.nombre+'"></div></div><div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cMo()">Cancelar</button><button class="btn pri" onclick="doEditPos('+id+')">Guardar</button></div>');
}
function doEditPos(id){
  api("/api/posiciones/"+id,{method:"PUT",body:{nombre:V("ep-n")}}).then(function(r){S.posiciones=r.posiciones;rPos();cMo();toast("Posición actualizada","ok")}).catch(function(e){toast(e.message,"er")});
}
function mPosTurns(pid){
  var p=S.posiciones.find(function(x){return x.id_posicion===pid});if(!p)return;
  var sm={};S.servicios.forEach(function(s){sm[s.id_servicio]=s.nombre});
  var turns=(S.turnos||[]).filter(function(t){return parseInt(t.id_posicion,10)===pid;});
  turns.sort(function(a,b){return (a.hora_inicio||"").localeCompare(b.hora_inicio||"");});
  var rows=turns.map(function(t){
    var sig=t.sigla_turno||t.nombre_turno;
    var dias=(t.dias_recurrencia||[]).map(function(d){return (DF[d]||"").substring(0,2)}).join(",");
    return '<tr><td><span class="tg">'+sig+'</span></td><td>'+t.nombre_turno+'</td><td style="font-family:var(--m);font-size:11px">'+(t.hora_inicio||"").substring(0,5)+'–'+(t.hora_fin||"").substring(0,5)+'</td><td>'+t.duracion_horas+'h</td><td>'+dias+'</td><td><button class="btn sm" onclick="mEditTrn('+t.id_turno+')">✎</button> <button class="btn dan sm" onclick="dPosTurn('+t.id_turno+','+pid+')">✕</button></td></tr>';
  }).join("");
  if(!rows) rows='<tr><td colspan="6" style="color:var(--dm);font-size:11px">Sin turnos en esta posición.</td></tr>';
  oMo('<h3>Posición y turnos</h3><p style="font-size:11px;color:var(--dm);margin:0 0 10px"><b>'+(sm[p.id_servicio]||("Servicio "+p.id_servicio))+' · '+p.nombre+'</b></p><div style="display:flex;justify-content:flex-end;margin-bottom:8px"><button class="btn suc sm" onclick="mPosTurn('+pid+')">+ Nuevo turno</button></div><table class="dt"><thead><tr><th>Sigla</th><th>Nombre</th><th>Horario</th><th>Dur.</th><th>Días</th><th></th></tr></thead><tbody>'+rows+'</tbody></table><div style="display:flex;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cMo()">Cerrar</button></div>');
}
function mPosTurn(pid){
  var p=S.posiciones.find(function(x){return x.id_posicion===pid});if(!p)return;
  var sm={};S.servicios.forEach(function(s){sm[s.id_servicio]=s.nombre});
  var dc=DF.map(function(d,i){return '<label style="display:flex;gap:2px;align-items:center;font-size:11px"><input type="checkbox" class="dcp" value="'+i+'" '+(i<5?"checked":"")+'>'+d.substring(0,2)+'</label>'}).join("");
  oMo('<h3>Nuevo turno</h3><p style="font-size:11px;color:var(--dm);margin:0 0 10px">Posición: <b>'+(sm[p.id_servicio]||("Servicio "+p.id_servicio))+' · '+p.nombre+'</b></p><div class="fr"><div class="fg gw"><label>Nombre</label><input id="ip-tn" value="Refuerzo"></div></div><div class="fr"><div class="fg"><label>Hora ini</label><input type="time" id="ip-thi" value="08:00"></div><div class="fg"><label>Hora fin</label><input type="time" id="ip-thf" value="16:00"></div></div><div class="fr"><div class="fg gw"><label>Días</label><div style="display:flex;gap:5px;flex-wrap:wrap">'+dc+'</div></div></div><div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="mPosTurns('+pid+')">Volver</button><button class="btn suc" onclick="doPosTurn('+pid+')">Crear</button></div>');
}
function doPosTurn(pid){
  var dias=[];document.querySelectorAll(".dcp:checked").forEach(function(c){dias.push(parseInt(c.value))});
  api("/api/turnos",{method:"POST",body:{nombre_turno:V("ip-tn"),id_posicion:pid,hora_inicio:V("ip-thi"),hora_fin:V("ip-thf"),dias_recurrencia:dias}})
    .then(function(r){S.turnos=r.turnos;rPos();mPosTurns(pid);toast("Turno creado","ok")})
    .catch(function(e){toast(e.message,"er")});
}
function dPosTurn(id,pid){
  api("/api/turnos/"+id,{method:"DELETE"})
    .then(function(r){S.turnos=r.turnos;rPos();mPosTurns(pid);toast("Turno eliminado","ok")})
    .catch(function(e){toast(e.message,"er")});
}

// ═══ TURNOS ═══════════════════════════════════════════════════════
function rTrn(){
  var pm={};(S.posiciones||[]).forEach(function(p){pm[p.id_posicion]=p});
  var sm={};(S.servicios||[]).forEach(function(s){sm[s.id_servicio]=s.nombre});
  var rows=S.turnos.map(function(t){
    var sig=t.sigla_turno||t.nombre_turno;
    var bg=sig[0]==="M"?"rgba(56,189,248,.15);color:var(--sM)":sig[0]==="T"?"rgba(251,191,36,.12);color:var(--sT)":"rgba(167,139,250,.15);color:var(--sN)";
    var dias=(t.dias_recurrencia||[]).map(function(d){return (DF[d]||"").substring(0,2)}).join(",");
    var pos=pm[t.id_posicion];
    var posName=pos?pos.nombre:("Posición "+t.id_posicion);
    var srvName=pos?(sm[pos.id_servicio]||("Servicio "+pos.id_servicio)):"-";
    return '<tr><td><span class="tg" style="background:'+bg+'">'+sig+'</span></td><td>'+t.nombre_turno+'</td><td>'+srvName+'</td><td>'+posName+'</td><td style="font-family:var(--m);font-size:11px">'+(t.hora_inicio||"").substring(0,5)+'–'+(t.hora_fin||"").substring(0,5)+'</td><td>'+t.duracion_horas+'h</td><td>'+dias+'</td><td><button class="btn sm" onclick="mEditTrn('+t.id_turno+')">✎</button> <button class="btn dan sm" onclick="dTrn('+t.id_turno+')">✕</button></td></tr>'}).join("");
  H("trn-t",'<table class="dt"><thead><tr><th>Sigla</th><th>Nombre</th><th>Servicio</th><th>Posición</th><th>Horario</th><th>Dur.</th><th>Días</th><th></th></tr></thead><tbody>'+rows+'</tbody></table>');
}
function syncTurnoNuevaPos(){
  var isNew=V("i-tp")==="__new__";
  var box=$("i-new-pos-wrap");
  if(box) box.style.display=isNew?"flex":"none";
}
function mTrn(){
  var sm={};(S.servicios||[]).forEach(function(s){sm[s.id_servicio]=s.nombre});
  var po=S.posiciones.filter(function(p){return p.activa}).map(function(p){
    var srv=sm[p.id_servicio]||("Servicio "+p.id_servicio);
    return '<option value="'+p.id_posicion+'">'+srv+' · '+p.nombre+'</option>';
  }).join("")+'<option value="__new__">+ Nueva posición…</option>';
  var so=S.servicios.filter(function(s){return s.activo}).map(function(s){return '<option value="'+s.id_servicio+'">'+s.nombre+'</option>'}).join("");
  var dc=DF.map(function(d,i){return '<label style="display:flex;gap:2px;align-items:center;font-size:11px"><input type="checkbox" class="dc" value="'+i+'" '+(i<5?"checked":"")+'>'+d.substring(0,2)+'</label>'}).join("");
  oMo('<h3>Nuevo turno</h3><div class="fr"><div class="fg gw"><label>Nombre</label><input id="i-tn" value="Refuerzo"></div><div class="fg"><label>Posición</label><select id="i-tp" onchange="syncTurnoNuevaPos()">'+po+'</select></div></div><div class="fr" id="i-new-pos-wrap" style="display:none"><div class="fg gw"><label>Nueva posición</label><input id="i-npn" placeholder="Nombre de la posición"></div><div class="fg"><label>Servicio</label><select id="i-nps">'+so+'</select></div></div><div class="fr"><div class="fg"><label>Hora ini</label><input type="time" id="i-thi" value="08:00"></div><div class="fg"><label>Hora fin</label><input type="time" id="i-thf" value="16:00"></div></div><div class="fr"><div class="fg gw"><label>Días</label><div style="display:flex;gap:5px;flex-wrap:wrap">'+dc+'</div></div></div><div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cMo()">Cancelar</button><button class="btn suc" onclick="doTrn()">Crear</button></div>');
  syncTurnoNuevaPos();
}
function doTrn(){
  var dias=[];document.querySelectorAll(".dc:checked").forEach(function(c){dias.push(parseInt(c.value))});
  var createTurno=function(posId){
    return api("/api/turnos",{method:"POST",body:{nombre_turno:V("i-tn"),id_posicion:posId,hora_inicio:V("i-thi"),hora_fin:V("i-thf"),dias_recurrencia:dias}});
  };
  var posSel=V("i-tp");
  var flow;
  if(posSel==="__new__"){
    var npn=V("i-npn").trim();
    if(!npn){toast("Nombre de posición requerido","er");return}
    var newSrvId=parseInt(V("i-nps"),10);
    if(isNaN(newSrvId)){toast("Selecciona un servicio para la nueva posición","er");return}
    flow=api("/api/posiciones",{method:"POST",body:{nombre:npn,id_servicio:newSrvId}}).then(function(r){
      S.posiciones=r.posiciones;
      var newPosId=S.posiciones.reduce(function(mx,p){
        var pid=parseInt(p.id_posicion,10);
        return isNaN(pid)?mx:Math.max(mx,pid);
      },0);
      if(!newPosId) throw new Error("No se pudo crear la nueva posición");
      return createTurno(newPosId);
    });
  }else{
    var posId=parseInt(posSel,10);
    if(isNaN(posId)){toast("Selecciona una posición válida","er");return}
    flow=createTurno(posId);
  }
  flow.then(function(r){S.turnos=r.turnos;rTrn();rPos();cMo();toast("Turno creado","ok")}).catch(function(e){toast(e.message,"er")});
}
function dTrn(id){api("/api/turnos/"+id,{method:"DELETE"}).then(function(r){S.turnos=r.turnos;rTrn();rPos()})}
function mEditTrn(id){
  var t=S.turnos.find(function(x){return x.id_turno===id});if(!t)return;
  var pm={};(S.posiciones||[]).forEach(function(p){pm[p.id_posicion]=p});
  var sm={};(S.servicios||[]).forEach(function(s){sm[s.id_servicio]=s.nombre});
  var pos=pm[t.id_posicion];
  var posInfo=pos?((sm[pos.id_servicio]||("Servicio "+pos.id_servicio))+" · "+pos.nombre):("Posición "+t.id_posicion);
  var dc=DF.map(function(d,i){return '<label style="display:flex;gap:2px;align-items:center;font-size:11px"><input type="checkbox" class="de" value="'+i+'"'+((t.dias_recurrencia||[]).indexOf(i)>=0?' checked':'')+'>'+d.substring(0,2)+'</label>'}).join("");
  oMo('<h3>Editar turno</h3><p style="font-size:11px;color:var(--dm);margin:0 0 10px">Pertenece a: <b>'+posInfo+'</b></p><div class="fr"><div class="fg gw"><label>Nombre</label><input id="et-n" value="'+t.nombre_turno+'"></div></div><div class="fr"><div class="fg"><label>Hora ini</label><input type="time" id="et-hi" value="'+(t.hora_inicio||"").substring(0,5)+'"></div><div class="fg"><label>Hora fin</label><input type="time" id="et-hf" value="'+(t.hora_fin||"").substring(0,5)+'"></div></div><div class="fr"><div class="fg gw"><label>Días</label><div style="display:flex;gap:5px;flex-wrap:wrap">'+dc+'</div></div></div><div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cMo()">Cancelar</button><button class="btn pri" onclick="doEditTrn('+id+')">Guardar</button></div>');
}
function doEditTrn(id){
  var dias=[];document.querySelectorAll(".de:checked").forEach(function(c){dias.push(parseInt(c.value))});
  api("/api/turnos/"+id,{method:"PUT",body:{nombre_turno:V("et-n"),hora_inicio:V("et-hi"),hora_fin:V("et-hf"),dias_recurrencia:dias}}).then(function(r){S.turnos=r.turnos;rTrn();rPos();cMo();toast("Turno actualizado","ok")}).catch(function(e){toast(e.message,"er")});
}

// ═══ EMPLEADOS ════════════════════════════════════════════════════
function rEmp(){
  var rows=S.empleados.map(function(e){
    var btns='<button class="btn sm" onclick="mEditEmp('+e.id_empleado+')">✎</button>'+(e.activo?' <button class="btn dan sm" onclick="dEmp('+e.id_empleado+')">✕</button>':'');
    return '<tr><td>'+e.id_empleado+'</td><td style="font-weight:600;color:var(--br)">'+e.nombre+'</td><td style="font-family:var(--m);font-size:10px">'+(e.horas_minimas||"-")+"/"+(e.horas_objetivo||"-")+"/"+(e.horas_maximas||"-")+'</td><td>'+(e.preferencia_turno||"indiferente")+'</td><td><span class="tg '+(e.activo?"tg-on":"tg-off")+'">'+(e.activo?"Activo":"Baja")+'</span></td><td>'+btns+'</td></tr>'}).join("");
  H("emp-t",'<table class="dt"><thead><tr><th>ID</th><th>Nombre</th><th>Min/Obj/Max</th><th>Pref.</th><th>Estado</th><th></th></tr></thead><tbody>'+rows+'</tbody></table>');
}
function mEmp(){oMo('<h3>Nuevo empleado</h3><div class="fr"><div class="fg gw"><label>Nombre</label><input id="i-en"></div></div><div class="fr"><div class="fg"><label>Fecha alta</label><input type="date" id="i-ea" value="2025-01-01"></div><div class="fg"><label>H.mín</label><input type="number" id="i-emin" value="140"></div><div class="fg"><label>H.máx</label><input type="number" id="i-emax" value="176"></div><div class="fg"><label>H.obj</label><input type="number" id="i-eobj" value="162"></div></div><div class="fr"><div class="fg"><label>Preferencia</label><select id="i-epref"><option value="indiferente">Indiferente</option><option value="diurno">Diurno</option><option value="nocturno">Nocturno</option></select></div></div><div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cMo()">Cancelar</button><button class="btn suc" onclick="doEmp()">Crear</button></div>')}
function doEmp(){var n=V("i-en");if(!n){toast("Nombre requerido","er");return}api("/api/empleados",{method:"POST",body:{nombre:n,fecha_alta:V("i-ea"),horas_minimas:NV("i-emin"),horas_maximas:NV("i-emax"),horas_objetivo:NV("i-eobj"),preferencia_turno:V("i-epref")}}).then(function(r){S.empleados=r.empleados;rEmp();cMo();toast("Empleado creado","ok")}).catch(function(e){toast(e.message,"er")})}
function dEmp(id){api("/api/empleados/"+id,{method:"DELETE"}).then(function(r){S.empleados=r.empleados;rEmp()})}
function mEditEmp(id){
  var e=S.empleados.find(function(x){return x.id_empleado===id});if(!e)return;
  var psel=function(v){return ['indiferente','diurno','nocturno'].map(function(o){return '<option value="'+o+'"'+(o===v?' selected':'')+'>'+o.charAt(0).toUpperCase()+o.slice(1)+'</option>'}).join("")};
  oMo('<h3>Editar empleado</h3><div class="fr"><div class="fg gw"><label>Nombre</label><input id="ee-n" value="'+e.nombre+'"></div></div><div class="fr"><div class="fg"><label>H.mín</label><input type="number" id="ee-min" value="'+(e.horas_minimas||140)+'"></div><div class="fg"><label>H.obj</label><input type="number" id="ee-obj" value="'+(e.horas_objetivo||162)+'"></div><div class="fg"><label>H.máx</label><input type="number" id="ee-max" value="'+(e.horas_maximas||176)+'"></div></div><div class="fr"><div class="fg"><label>Preferencia</label><select id="ee-pref">'+psel(e.preferencia_turno||"indiferente")+'</select></div><div class="fg"><label>Estado</label><select id="ee-act"><option value="true"'+(e.activo?' selected':'')+'>Activo</option><option value="false"'+(!e.activo?' selected':'')+'>Baja</option></select></div></div><div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cMo()">Cancelar</button><button class="btn pri" onclick="doEditEmp('+id+')">Guardar</button></div>');
}
function doEditEmp(id){
  var n=V("ee-n");if(!n){toast("Nombre requerido","er");return}
  api("/api/empleados/"+id,{method:"PUT",body:{nombre:n,horas_minimas:NV("ee-min"),horas_objetivo:NV("ee-obj"),horas_maximas:NV("ee-max"),preferencia_turno:V("ee-pref"),activo:V("ee-act")==="true"}}).then(function(r){S.empleados=r.empleados;rEmp();cMo();toast("Empleado actualizado","ok")}).catch(function(e){toast(e.message,"er")});
}

// ═══ CATÁLOGO ═════════════════════════════════════════════════════
var _TIPOS=['vacaciones','permiso','baja_medica','dia_libre','asunto_propio','conciliacion','lactancia','jornada_reducida','indisponibilidad','otro'];
var _SEVS=['HARD','SOFT_HIGH','SOFT_MEDIUM','SOFT_LOW'];
function _tipoOpts(sel){return _TIPOS.map(function(t){return '<option value="'+t+'"'+(t===sel?' selected':'')+'>'+t+'</option>'}).join("")}
function _sevOpts(sel){return _SEVS.map(function(s){return '<option value="'+s+'"'+(s===sel?' selected':'')+'>'+s+'</option>'}).join("")}
function rCat(){
  var items=Object.values(S.catalogo||{});
  var rows=items.map(function(c){
    var btns=c.activa?'<button class="btn sm" onclick="mEditCat('+c.id_restriccion+')">✎</button> <button class="btn dan sm" onclick="dCat('+c.id_restriccion+')">✕</button>':'';
    return '<tr><td>'+c.id_restriccion+'</td><td>'+c.desc_restriccion+'</td><td style="font-size:10px;color:var(--dm)">'+c.tipo_restriccion+'</td><td><span class="tg '+(c.severidad==="HARD"?"tg-hard":"tg-soft")+'">'+c.severidad+'</span></td><td style="font-family:var(--m)">'+(c.hora_dia||0)+'h</td><td>'+(c.dias||"∞")+'</td><td><span class="tg '+(c.activa?"tg-on":"tg-off")+'">'+(c.activa?"On":"Off")+'</span></td><td>'+btns+'</td></tr>'}).join("");
  H("cat-t",'<table class="dt"><thead><tr><th>ID</th><th>Descripción</th><th>Tipo</th><th>Sev.</th><th>H/día</th><th>Días máx</th><th>Estado</th><th></th></tr></thead><tbody>'+rows+'</tbody></table>');
}
function mCat(){oMo('<h3>Nueva restricción</h3><div class="fr"><div class="fg gw"><label>Descripción</label><input id="i-cd"></div><div class="fg"><label>Siglas</label><input id="i-csig" placeholder="VC" style="width:60px"></div></div><div class="fr"><div class="fg"><label>Tipo</label><select id="i-ct">'+_tipoOpts("vacaciones")+'</select></div><div class="fg"><label>Severidad</label><select id="i-cs">'+_sevOpts("SOFT_MEDIUM")+'</select></div><div class="fg"><label>H/día</label><input type="number" id="i-ch" value="0" step="0.1"></div><div class="fg"><label>Días máx</label><input type="number" id="i-cdi" value="31"></div></div><div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cMo()">Cancelar</button><button class="btn suc" onclick="doCat()">Crear</button></div>')}
function doCat(){api("/api/catalogo",{method:"POST",body:{desc_restriccion:V("i-cd"),siglas:V("i-csig")||null,tipo_restriccion:V("i-ct"),severidad:V("i-cs"),hora_dia:NV("i-ch"),dias:parseInt(V("i-cdi"))}}).then(function(r){S.catalogo=r.catalogo;rCat();cMo();toast("Creada","ok")}).catch(function(e){toast(e.message,"er")})}
function dCat(id){api("/api/catalogo/"+id,{method:"DELETE"}).then(function(r){S.catalogo=r.catalogo;rCat()})}
function mEditCat(id){
  var c=Object.values(S.catalogo||{}).find(function(x){return x.id_restriccion===id});if(!c)return;
  oMo('<h3>Editar restricción</h3><div class="fr"><div class="fg gw"><label>Descripción</label><input id="ec-d" value="'+c.desc_restriccion+'"></div><div class="fg"><label>Siglas</label><input id="ec-sig" value="'+(c.siglas||"")+'" style="width:60px"></div></div><div class="fr"><div class="fg"><label>Tipo</label><select id="ec-t">'+_tipoOpts(c.tipo_restriccion)+'</select></div><div class="fg"><label>Severidad</label><select id="ec-s">'+_sevOpts(c.severidad)+'</select></div><div class="fg"><label>H/día</label><input type="number" id="ec-h" value="'+(c.hora_dia||0)+'" step="0.1"></div><div class="fg"><label>Días máx</label><input type="number" id="ec-di" value="'+(c.dias||31)+'"></div></div><div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cMo()">Cancelar</button><button class="btn pri" onclick="doEditCat('+id+')">Guardar</button></div>');
}
function doEditCat(id){
  api("/api/catalogo/"+id,{method:"PUT",body:{desc_restriccion:V("ec-d"),siglas:V("ec-sig")||null,tipo_restriccion:V("ec-t"),severidad:V("ec-s"),hora_dia:NV("ec-h"),dias:parseInt(V("ec-di"))}}).then(function(r){S.catalogo=r.catalogo;rCat();cMo();toast("Actualizada","ok")}).catch(function(e){toast(e.message,"er")});
}

// ═══ RESTRICCIONES ════════════════════════════════════════════════
function rRes(){
  var em={};S.empleados.forEach(function(e){em[e.id_empleado]=e.nombre});
  var cm={};Object.values(S.catalogo||{}).forEach(function(c){cm[c.id_restriccion]=c.desc_restriccion});
  var rows=(S.restricciones_empleado||[]).map(function(r){return '<tr><td>'+(em[r.id_empleado]||r.id_empleado)+'</td><td>'+(cm[r.id_restriccion]||r.id_restriccion)+'</td><td style="font-family:var(--m);font-size:10px">'+(r.fecha||"").substring(0,10)+'</td><td style="font-size:10px;color:var(--dm)">'+(r.observaciones||"")+'</td><td><button class="btn dan sm" onclick="dRes('+r.id_empleado+','+r.id_restriccion+',\''+(r.fecha||"").substring(0,10)+'\')">✕</button></td></tr>'}).join("");
  H("res-t",'<table class="dt"><thead><tr><th>Empleado</th><th>Restricción</th><th>Fecha</th><th>Obs.</th><th></th></tr></thead><tbody>'+rows+'</tbody></table>');
}
function mRes(){
  var eo=S.empleados.filter(function(e){return e.activo}).map(function(e){return '<option value="'+e.id_empleado+'">'+e.nombre+'</option>'}).join("");
  var co=Object.values(S.catalogo||{}).filter(function(c){return c.activa}).map(function(c){return '<option value="'+c.id_restriccion+'">'+c.desc_restriccion+'</option>'}).join("");
  oMo('<h3>Asignar restricción</h3><div class="fr"><div class="fg"><label>Empleado</label><select id="i-re">'+eo+'</select></div><div class="fg"><label>Restricción</label><select id="i-rr">'+co+'</select></div></div><div class="fr"><div class="fg"><label>Desde</label><input type="date" id="i-rfi" value="2026-03-16"></div><div class="fg"><label>Hasta</label><input type="date" id="i-rff" value="2026-03-20"></div></div><div class="fr"><div class="fg gw"><label>Observaciones</label><input id="i-ro"></div></div><div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cMo()">Cancelar</button><button class="btn suc" onclick="doRes()">Asignar</button></div>')}
function doRes(){api("/api/restricciones",{method:"POST",body:{id_empleado:parseInt(V("i-re")),id_restriccion:parseInt(V("i-rr")),fecha_ini:V("i-rfi"),fecha_fin:V("i-rff"),observaciones:V("i-ro")}}).then(function(r){S.restricciones_empleado=r.restricciones;rRes();cMo();toast("Asignada","ok")}).catch(function(e){toast(e.message,"er")})}
function dRes(eid,rid,f){api("/api/restricciones/delete",{method:"POST",body:{id_empleado:eid,id_restriccion:rid,fecha:f}}).then(function(r){S.restricciones_empleado=r.restricciones;rRes()})}

// ═══ ASIGNACIONES SERVICIO ════════════════════════════════════════
function rAsig(){
  return _renderAsig();
}
function tAsig(eid,sid){return _toggleAsig(eid,sid)}

// ═══ CONCILIACIONES ═══════════════════════════════════════════════
function rConc(){
  var em={};S.empleados.forEach(function(e){em[e.id_empleado]=e.nombre});
  var gr={};(S.conciliaciones||[]).forEach(function(c){gr[c.id_conciliacion]=gr[c.id_conciliacion]||[];gr[c.id_conciliacion].push(c)});
  var rows="";
  Object.keys(gr).forEach(function(cid){
    var items=gr[cid];var f=items[0];
    var dias=items.map(function(i){return (DF[i.dia_semana]||"").substring(0,3)+": "+(i.hora_ini||"").substring(0,5)+"-"+(i.hora_fin||"").substring(0,5)}).join(", ");
    rows+='<tr><td>'+(em[f.id_empleado]||f.id_empleado)+'</td><td style="font-size:10px">'+dias+'</td><td style="font-family:var(--m);font-size:10px">'+(f.fecha_ini||"").substring(0,10)+" → "+(f.fecha_fin||"").substring(0,10)+'</td><td><button class="btn sm" onclick="mEditConc('+cid+')">✎</button> <button class="btn dan sm" onclick="dConc('+cid+')">✕</button></td></tr>';
  });
  H("conc-t",'<table class="dt"><thead><tr><th>Empleado</th><th>Horarios</th><th>Vigencia</th><th></th></tr></thead><tbody>'+rows+'</tbody></table>');
}
function _concModal(title, eid, fi, ff, items, saveBtn){
  var eo=S.empleados.filter(function(e){return e.activo}).map(function(e){return '<option value="'+e.id_empleado+'"'+(e.id_empleado===eid?' selected':'')+'>'+e.nombre+'</option>'}).join("");
  var dh=DF.map(function(d,i){var it=items.find(function(c){return c.dia_semana===i});return '<div class="fr" style="align-items:center"><label style="width:80px;font-size:11px"><input type="checkbox" class="cc" value="'+i+'"'+(it?' checked':i<5?' checked':'')+"> "+d.substring(0,3)+'</label><div class="fg"><label>Desde</label><input type="time" id="i-chi'+i+'" value="'+(it?it.hora_ini||"06:00":"06:00")+'"></div><div class="fg"><label>Hasta</label><input type="time" id="i-chf'+i+'" value="'+(it?it.hora_fin||"22:00":"22:00")+'"></div></div>'}).join("");
  oMo('<h3>'+title+'</h3><div class="fr"><div class="fg"><label>Empleado</label><select id="i-ce">'+eo+'</select></div><div class="fg"><label>Desde</label><input type="date" id="i-cfi" value="'+fi+'"></div><div class="fg"><label>Hasta</label><input type="date" id="i-cff" value="'+ff+'"></div></div><div style="margin:10px 0;font-size:11px;color:var(--dm)">Horario disponible por día:</div>'+dh+'<div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cMo()">Cancelar</button>'+saveBtn+'</div>');
}
function mConc(){
  var today=formatLocalDate(new Date());
  _concModal("Nueva conciliación",null,today,"2026-12-31",[],'<button class="btn suc" onclick="doConc()">Crear</button>');
}
function doConc(){
  var dias=[];document.querySelectorAll(".cc:checked").forEach(function(c){var i=parseInt(c.value);dias.push({dia_semana:i,hora_ini:V("i-chi"+i),hora_fin:V("i-chf"+i)})});
  if(!dias.length){toast("Selecciona al menos un día","er");return}
  api("/api/conciliaciones",{method:"POST",body:{id_empleado:parseInt(V("i-ce")),dias:dias,fecha_ini:V("i-cfi"),fecha_fin:V("i-cff")}}).then(function(r){S.conciliaciones=r.conciliaciones;rConc();cMo();toast("Conciliación creada","ok")}).catch(function(e){toast(e.message,"er")})}
function dConc(cid){api("/api/conciliaciones/"+cid,{method:"DELETE"}).then(function(r){S.conciliaciones=r.conciliaciones;rConc()})}
function mEditConc(cid){
  var items=(S.conciliaciones||[]).filter(function(c){return c.id_conciliacion==cid});
  if(!items.length)return;
  var f=items[0];
  _concModal("Editar conciliación",f.id_empleado,(f.fecha_ini||"").substring(0,10),(f.fecha_fin||"").substring(0,10),items,'<button class="btn pri" onclick="doEditConc('+cid+')">Guardar</button>');
}
function doEditConc(cid){
  var dias=[];document.querySelectorAll(".cc:checked").forEach(function(c){var i=parseInt(c.value);dias.push({dia_semana:i,hora_ini:V("i-chi"+i),hora_fin:V("i-chf"+i)})});
  if(!dias.length){toast("Selecciona al menos un día","er");return}
  api("/api/conciliaciones/"+cid,{method:"DELETE"}).then(function(){
    return api("/api/conciliaciones",{method:"POST",body:{id_empleado:parseInt(V("i-ce")),dias:dias,fecha_ini:V("i-cfi"),fecha_fin:V("i-cff")}});
  }).then(function(r){S.conciliaciones=r.conciliaciones;rConc();cMo();toast("Conciliación actualizada","ok")}).catch(function(e){toast(e.message,"er")});
}

// ═══ GENERAR ══════════════════════════════════════════════════════
function generar(){
  syncMonthInputs();
  var sid=selectedScheduleServiceId();
  var body={start_date:V("c-start"),num_days:parseInt(V("c-days"),10),max_time:solverSeconds()};
  if(sid!==null) body.id_servicio=sid;
  toast("Generando...");
  api("/api/generar",{method:"POST",body:body})
  .then(function(r){SCH=r;HIST_ID=null;syncInputsFromSchedule(r);renderSch();updateHistBanner();loadHistory();
    var el=document.querySelector('[data-pg="pg-horario"]');if(el)go(el);
    if(sid!==null) toast("Horario generado para el servicio seleccionado","ok");
    else toast("Horario generado","ok")})
  .catch(function(e){toast("Error: "+e.message,"er")});
}

// ═══ NAVEGACIÓN MESES ═════════════════════════════════════════════
function navMonth(dir){
  var startEl=$("c-start"),daysEl=$("c-days");if(!startEl)return;
  var d=new Date(startEl.value+"T00:00:00");
  d.setDate(1);d.setMonth(d.getMonth()+dir);
  startEl.value=formatLocalDate(d);
  daysEl.value=monthDaysForValue(startEl.value);
  updateNavPeriodo();
  renderSch();
  if(typeof renderSchEmpleado==="function") renderSchEmpleado();
}
function updateNavPeriodo(){
  var el=$("nav-periodo"),elEmp=$("emp-nav-periodo");if(!el&&!elEmp)return;
  var MNL=["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];
  var startEl=$("c-start"),daysEl=$("c-days");
  if(startEl&&startEl.value){
    var fi=new Date(startEl.value+"T00:00:00");
    var days=daysEl?parseInt(daysEl.value)||monthDaysForValue(startEl.value):monthDaysForValue(startEl.value);
    var ffD=new Date(fi);ffD.setDate(ffD.getDate()+days-1);
    var s=MNL[fi.getMonth()]+" "+fi.getFullYear();
    if(fi.getMonth()!==ffD.getMonth()||fi.getFullYear()!==ffD.getFullYear())
      s+=" – "+MNL[ffD.getMonth()]+" "+ffD.getFullYear();
    if(el) el.textContent=s;
    if(elEmp) elEmp.textContent=s;
  }else{
    if(el) el.textContent="Sin configurar";
    if(elEmp) elEmp.textContent="Sin configurar";
  }
}

// ═══ RENDER SCHEDULE ══════════════════════════════════════════════
function refreshScheduleServiceFilter(){
  var sel=$("sch-srv-filter");
  if(!sel||!S)return;
  var current=sel.value||"";
  var map={};
  (S.servicios||[]).forEach(function(s){map[String(s.id_servicio)]=s.nombre;});
  if(SCH&&SCH.grids){
    Object.keys(SCH.grids).forEach(function(sk){
      if(!map[sk]) map[sk]=(SCH.grids[sk]&&SCH.grids[sk].nombre)||("Servicio "+sk);
    });
  }
  var keys=Object.keys(map).sort(function(a,b){return parseInt(a,10)-parseInt(b,10)});
  sel.innerHTML='<option value="">Todos los servicios</option>'+keys.map(function(k){return '<option value="'+k+'">'+map[k]+'</option>'}).join("");
  if(current&&map[current]) sel.value=current;
}
function selectedScheduleServiceId(){
  var sel=$("sch-srv-filter");
  if(!sel||!sel.value) return null;
  var sid=parseInt(sel.value,10);
  return isNaN(sid)?null:sid;
}
function onScheduleServiceFilterChange(){renderSch();}

function renderSch(){
  var a=$("sch-area"),sb=$("sts"),hc=$("hrs-card");
  refreshScheduleServiceFilter();
  if(!SCH||!SCH.grids){a.innerHTML='<div class="card"><div class="card-b" style="text-align:center;padding:50px;color:var(--dm)"><div style="font-size:40px;opacity:.3;margin-bottom:10px">📋</div><p>Sin horario generado para este mes</p></div></div>';sb.style.display="none";hc.style.display="none";return}
  if(!scheduleMatchesSelection(SCH)){
    var fi=(SCH.dates&&SCH.dates.length)?SCH.dates[0]:"";
    a.innerHTML='<div class="card"><div class="card-b" style="text-align:center;padding:40px;color:var(--dm)"><div style="font-size:40px;opacity:.3;margin-bottom:10px">📅</div><p style="margin-bottom:10px">No hay horario generado para el mes seleccionado.</p><p style="font-size:11px;margin-bottom:16px">Último horario disponible desde <b>'+fi+'</b>.</p><button class="btn pri" onclick="showLatestScheduleMonth()">Ver último horario</button></div></div>';
    sb.style.display="none";hc.style.display="none";return
  }
  var grids=SCH.grids,dates=SCH.dates,hours=SCH.hours||[];
  var selectedSid=selectedScheduleServiceId();
  var visibleServiceKeys=Object.keys(grids).filter(function(sk){return selectedSid===null||parseInt(sk,10)===selectedSid;});
  if(!visibleServiceKeys.length){
    a.innerHTML='<div class="card"><div class="card-b" style="text-align:center;padding:40px;color:var(--dm)"><div style="font-size:34px;opacity:.35;margin-bottom:8px">🔎</div><p>No hay datos para el servicio seleccionado en este mes.</p></div></div>';
    sb.style.display="none";hc.style.display="none";return;
  }
  sb.style.display="flex";
  var te=0,tc=0,to=0;
  visibleServiceKeys.forEach(function(sk){
    var g=grids[sk];
    Object.values(g.employees).forEach(function(ed){te++;Object.values(ed.days).forEach(function(c){if(c.es_off)to++;else tc++})});
  });
  H("s-emp",te);H("s-cub",tc);H("s-flt",SCH.summary?SCH.summary.faltantes||0:0);H("s-dias",dates.length);

  var html="";
  visibleServiceKeys.forEach(function(sk){
    var sd=grids[sk];
    html+='<div class="card" style="margin-bottom:16px"><div class="srv-hdr">🏢 '+sd.nombre+'</div><div class="sw"><table class="sc"><thead><tr><th class="eh">Empleado</th><th class="ph">Posición</th>';
    dates.forEach(function(ds){var d=new Date(ds+"T00:00:00");var dow=d.getDay();var we=dow===0||dow===6;
      html+='<th'+(we?' class="we"':'')+ '>'+DN[dow]+'<br>'+d.getDate()+'<br><span style="font-size:7px">'+MN[d.getMonth()]+'</span></th>'});
    html+='</tr></thead><tbody>';
    Object.keys(sd.employees).forEach(function(ek){
      var ed=sd.employees[ek];
      html+='<tr><td class="en">'+ed.nombre+'</td><td class="ep">'+ed.posicion+'</td>';
      dates.forEach(function(ds){
        var c=ed.days[ds];var d=new Date(ds+"T00:00:00");var we=d.getDay()===0||d.getDay()===6;
        if(!c){html+='<td class="cl cO'+(we?" we":"")+'">-</td>';return}
        var cls;
        if(c.es_restriccion){var sig=c.turno;cls=sig==="VC"?"cVC":sig==="BM"?"cBM":"cRL";}
        else{cls=c.turno[0]==="M"?"cM":c.turno[0]==="T"?"cT":c.turno[0]==="N"?"cN":"cO";}
        var click=c.es_restriccion?"":'onclick="eCell('+sk+","+ek+",'"+ds+"','"+c.turno+"',"+c.horas+')"';
        html+='<td class="cl '+cls+(we?" we":"")+'" title="'+ed.nombre+": "+c.turno+" ("+c.horas+'h)" '+click+'>'+c.turno+'</td>';
      });
      html+='</tr>';
    });
    // DARK POST row
    if(sd.dark_post){
      html+='<tr style="border-top:2px solid var(--bd)">';
      html+='<td class="en" style="color:var(--rd);opacity:.6;font-style:italic;font-size:10px">—</td><td class="ep" style="color:var(--rd);font-weight:700;font-size:9px;letter-spacing:.5px">DARK POST</td>';
      dates.forEach(function(ds){var h=sd.dark_post[ds]||0;html+='<td class="cl" style="background:rgba(248,113,113,.07);color:var(--rd);font-size:8px;font-weight:700">'+(h>0?h+'h':'')+'</td>';});
      html+='</tr>';
    }
    html+='</tbody></table></div></div>';
  });
  a.innerHTML=html;

  var visibleEmployees={};
  visibleServiceKeys.forEach(function(sk){
    Object.keys((grids[sk]&&grids[sk].employees)||{}).forEach(function(ek){visibleEmployees[ek]=true;});
  });
  var filteredHours=hours.filter(function(h){return visibleEmployees[String(h.id)]});
  if(!filteredHours.length){hc.style.display="none";H("hrs-area","");return}
  hc.style.display="block";
  var hh='<table class="ht"><thead><tr><th>Empleado</th><th>H.Trabajo</th><th>H.Restr.</th><th>Total</th><th>Objetivo</th><th>Diff</th><th style="width:25%">Balance</th></tr></thead><tbody>';
  filteredHours.forEach(function(h){
    var pct=Math.min((h.horas_total/h.objetivo)*100,150);
    var cls=h.diff>5?"ov":h.diff<-10?"un":"ok";
    var ds=h.diff>=0?"+"+h.diff:""+h.diff;
    var col=cls==="ok"?"var(--gn)":cls==="ov"?"var(--rd)":"var(--am)";
    hh+='<tr><td style="font-weight:600;color:var(--br)">'+h.nombre+'</td><td style="font-family:var(--m)">'+h.horas_trabajo+'</td><td style="font-family:var(--m);color:var(--am)">'+h.horas_restriccion+'</td><td style="font-family:var(--m);font-weight:700">'+h.horas_total+'</td><td style="font-family:var(--m);color:var(--dm)">'+h.objetivo+'</td><td style="font-family:var(--m);color:'+col+'">'+ds+'</td><td><div class="hb"><div class="hb-f '+cls+'" style="width:'+Math.min(pct,100)+'%"></div></div></td></tr>';
  });
  hh+='</tbody></table>';H("hrs-area",hh);
}

// ═══ EDIT CELL ════════════════════════════════════════════════════
function eCell(srv,emp,fecha,turno,horas){
  var opts=S.turnos.map(function(s){var sig=s.sigla_turno||s.nombre_turno;return '<option value="'+sig+'" data-h="'+s.duracion_horas+'" '+(sig===turno?"selected":"")+'>'+sig+' ('+s.nombre_turno+' '+s.duracion_horas+'h)</option>'}).join("");
  $("emo-c").innerHTML='<h3>Editar turno – '+fecha+'</h3><div class="fr"><div class="fg gw"><label>Turno</label><select id="ec-t" onchange="$(\'ec-h\').value=this.selectedOptions[0].dataset.h||0">'+opts+'<option value="OFF" '+(turno==="OFF"?"selected":"")+'>OFF (0h)</option></select></div><div class="fg"><label>Horas</label><input type="number" id="ec-h" value="'+horas+'" step="0.5"></div></div><div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cEm()">Cancelar</button><button class="btn pri" onclick="doEC('+srv+','+emp+',\''+fecha+'\')">Guardar</button></div>';
  $("emodal").classList.add("op");
}
function doEC(srv,emp,f){
  var t=V("ec-t"),h=NV("ec-h");
  var url=HIST_ID!==null?"/api/schedule/history/"+HIST_ID+"/edit":"/api/schedule/edit";
  api(url,{method:"POST",body:{id_servicio:srv,id_empleado:emp,fecha:f,turno:t,horas:h}})
  .then(function(){
    var reload=HIST_ID!==null?api("/api/schedule/history/"+HIST_ID):api("/api/schedule");
    return reload.then(function(data){SCH=data;syncInputsFromSchedule(data);renderSch();cEm();toast("Turno actualizado","ok")});
  })
  .catch(function(e){toast(e.message,"er")});
}

// ═══ RESÚMENES ════════════════════════════════════════════════════
function rResSel(){
  var eo='<option value="">Seleccionar...</option>'+S.empleados.filter(function(e){return e.activo}).map(function(e){return '<option value="'+e.id_empleado+'">'+e.nombre+'</option>'}).join("");
  $("r-emp").innerHTML=eo;
  var so='<option value="">Seleccionar...</option>'+S.servicios.filter(function(s){return s.activo}).map(function(s){return '<option value="'+s.id_servicio+'">'+s.nombre+'</option>'}).join("");
  $("r-srv").innerHTML=so;
}
function resEmp(){
  var eid=V("r-emp");if(!eid){H("r-emp-a","");return}
  api("/api/resumen/empleado/"+eid).then(function(d){
    var tc="";Object.keys(d.turnos_count||{}).forEach(function(t){tc+='<tr><td>'+t+'</td><td>'+d.turnos_count[t]+'</td></tr>'});
    H("r-emp-a",'<div class="sts" style="margin-top:10px"><div class="st"><div class="sl">H.Trabajo</div><div class="sv">'+d.horas_trabajo+'</div></div><div class="st"><div class="sl">H.Restr.</div><div class="sv" style="color:var(--am)">'+d.horas_restriccion+'</div></div><div class="st"><div class="sl">Total</div><div class="sv" style="color:var(--gn)">'+d.horas_total+'</div></div><div class="st"><div class="sl">OFF</div><div class="sv">'+d.dias_off+'</div></div><div class="st"><div class="sl">D.Restr.</div><div class="sv">'+d.dias_restriccion+'</div></div></div><table class="dt" style="margin-top:10px"><thead><tr><th>Turno</th><th>Veces</th></tr></thead><tbody>'+tc+'</tbody></table>');
  }).catch(function(e){H("r-emp-a",'<p style="color:var(--rd)">'+e.message+'</p>')});
}
function resSrv(){
  var sid=V("r-srv");if(!sid){H("r-srv-a","");return}
  api("/api/resumen/servicio/"+sid).then(function(d){
    var er="";Object.keys(d.empleados||{}).forEach(function(n){er+='<tr><td>'+n+'</td><td style="font-family:var(--m)">'+d.empleados[n]+'</td></tr>'});
    var tc="";Object.keys(d.turnos_count||{}).forEach(function(t){tc+='<tr><td>'+t+'</td><td>'+d.turnos_count[t]+'</td></tr>'});
    H("r-srv-a",'<div class="sts" style="margin-top:10px"><div class="st"><div class="sl">Total horas</div><div class="sv" style="color:var(--gn)">'+d.total_horas+'</div></div></div><div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:10px"><div style="flex:1"><h4 style="font-size:12px;color:var(--dm);margin-bottom:6px">HORAS/EMPLEADO</h4><table class="dt"><tbody>'+er+'</tbody></table></div><div style="flex:1"><h4 style="font-size:12px;color:var(--dm);margin-bottom:6px">TURNOS</h4><table class="dt"><tbody>'+tc+'</tbody></table></div></div>');
  }).catch(function(e){H("r-srv-a",'<p style="color:var(--rd)">'+e.message+'</p>')});
}

// ═══ RESET ════════════════════════════════════════════════════════
function doReset(){api("/api/reset",{method:"POST"}).then(function(d){S=d;SCH=null;HIST_ID=null;renderSch();updateHistBanner();toast("Reiniciado","ok")})}

// ═══ HISTÓRICO ════════════════════════════════════════════════════
function loadHistory(){
  api("/api/schedule/history").then(function(versions){
    if(!versions.length){H("hist-list",'<p style="color:var(--dm);font-size:11px;padding:4px 0">Sin versiones guardadas. Genera un horario y pulsa 💾 para guardar.</p>');return}
    var rows=versions.map(function(v){
      var act=HIST_ID===v.id;
      return '<tr style="'+(act?"background:rgba(251,191,36,.08)":"")+'"><td style="font-weight:'+(act?"700":"400")+';color:'+(act?"var(--am)":"var(--br)")+'">'+v.nombre+'</td>'
        +'<td style="font-family:var(--m);font-size:10px;color:var(--dm)">'+(v.fecha_inicio||"")+(v.fecha_fin?" → "+v.fecha_fin:"")+'</td>'
        +'<td style="font-family:var(--m);font-size:10px;color:var(--dm)">'+(v.created_at||"").substring(0,16)+'</td>'
        +'<td style="white-space:nowrap"><button class="btn sm '+(act?"pri":"")+ '" onclick="loadVersion('+v.id+')">'+(act?"✓ Activo":"Cargar")+'</button> '
        +'<button class="btn dan sm" onclick="delVersion('+v.id+')">✕</button></td></tr>';
    }).join("");
    H("hist-list",'<table class="dt"><thead><tr><th>Nombre</th><th>Período</th><th>Guardado</th><th></th></tr></thead><tbody>'+rows+'</tbody></table>');
  }).catch(function(){H("hist-list",'<p style="color:var(--dm);font-size:11px;padding:4px 0">Sin versiones guardadas.</p>')});
}

function mSaveVersion(){
  var today=formatLocalDate(new Date());
  // Usar siempre las fechas de config (no SCH, que puede ser una versión histórica)
  var startEl=$("c-start"),daysEl=$("c-days");
  var fi=startEl?startEl.value:today;
  var days=daysEl?parseInt(daysEl.value)||31:31;
  var ffD=new Date(fi+"T00:00:00");ffD.setDate(ffD.getDate()+days-1);
  var ff=formatLocalDate(ffD);
  var MNL=["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];
  var fd=new Date(fi+"T00:00:00");
  var defNombre="Horario "+MNL[fd.getMonth()]+" "+fd.getFullYear();
  oMo('<h3>Guardar versión</h3><div class="fr"><div class="fg gw"><label>Nombre</label><input id="sv-n" value="'+defNombre+'"></div></div>'
    +'<div class="fr"><div class="fg"><label>Período desde</label><input type="date" id="sv-fi" value="'+fi+'"></div><div class="fg"><label>Hasta</label><input type="date" id="sv-ff" value="'+ff+'"></div></div>'
    +'<div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cMo()">Cancelar</button><button class="btn suc" onclick="doSaveVersion()">Guardar</button></div>');
}

function doSaveVersion(){
  var n=V("sv-n");if(!n){toast("Nombre requerido","er");return}
  api("/api/schedule/save",{method:"POST",body:{nombre:n,fecha_inicio:V("sv-fi"),fecha_fin:V("sv-ff")}})
    .then(function(){loadHistory();cMo();toast("Versión guardada","ok")})
    .catch(function(e){toast(e.message,"er")});
}

function loadVersion(vid){
  api("/api/schedule/history/"+vid).then(function(data){
    SCH=data;HIST_ID=vid;syncInputsFromSchedule(data);renderSch();updateHistBanner();loadHistory();toast("Versión cargada","ok");
  }).catch(function(e){toast(e.message,"er")});
}

function delVersion(vid){
  api("/api/schedule/history/"+vid,{method:"DELETE"})
    .then(function(){if(HIST_ID===vid)exitHistView();else loadHistory();toast("Eliminada")})
    .catch(function(e){toast(e.message,"er")});
}

function exitHistView(){
  HIST_ID=null;updateHistBanner();
  api("/api/schedule").then(function(s){if(s&&s.grids){SCH=s;syncInputsFromSchedule(s);}else{SCH=null;}renderSch();}).catch(function(){SCH=null;renderSch();});
  loadHistory();
}

function updateHistBanner(){
  var b=$("hist-banner");
  if(HIST_ID!==null){b.style.display="flex";$("hist-banner-txt").textContent="Viendo versión histórica #"+HIST_ID+" — las ediciones se guardan en esta versión";}
  else{b.style.display="none";}
}

// ═══ INIT ═════════════════════════════════════════════════════════
document.addEventListener("DOMContentLoaded",function(){
  syncMonthInputs();
  updateNavPeriodo();
  api("/api/state").then(function(d){
    S=d;
    refreshScheduleServiceFilter();
    api("/api/schedule").then(function(s){if(s&&s.grids){SCH=s;syncInputsFromSchedule(s);renderSch()}}).catch(function(){});
    loadHistory();
  });
  var startEl=$("c-start"),daysEl=$("c-days");
  if(startEl)startEl.addEventListener("change",function(){syncMonthInputs();updateNavPeriodo();renderSch();if(typeof renderSchEmpleado==="function")renderSchEmpleado();});
  if(daysEl)daysEl.addEventListener("change",function(){syncMonthInputs();updateNavPeriodo();renderSch();if(typeof renderSchEmpleado==="function")renderSchEmpleado();});
  document.addEventListener("keydown",function(e){if(e.key==="Escape"){cMo();cEm()}});
});

function _posDayTotals(pid){
  var totals=[0,0,0,0,0,0,0];
  (S.turnos||[]).forEach(function(t){
    if(parseInt(t.id_posicion,10)!==parseInt(pid,10)) return;
    var h=parseFloat(t.duracion_horas)||0;
    (t.dias_recurrencia||[]).forEach(function(d){
      var wd=parseInt(d,10);
      if(wd>=0&&wd<7) totals[wd]+=h;
    });
  });
  return totals;
}

function mPos(){
  var opts=S.servicios.filter(function(s){return s.activo}).map(function(s){return '<option value="'+s.id_servicio+'">'+s.nombre+'</option>'}).join("");
  oMo('<h3>Nueva posición</h3><p style="font-size:11px;color:var(--dm);margin:0 0 10px">Después podrás crear sus turnos desde esta misma pantalla.</p><div class="fr"><div class="fg gw"><label>Nombre</label><input id="i-pn"></div><div class="fg"><label>Servicio</label><select id="i-ps">'+opts+'</select></div></div><div class="fr"><div class="fg gw"><label style="text-transform:none;letter-spacing:0"><input type="checkbox" id="i-p24" style="margin-right:6px"> Posición 24H (sumatorio de turnos = 24h por día)</label></div></div><div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cMo()">Cancelar</button><button class="btn suc" onclick="doPos()">Crear</button></div>');
}

function doPos(){
  api("/api/posiciones",{method:"POST",body:{nombre:V("i-pn"),id_servicio:parseInt(V("i-ps"),10),es_24h:!!($("i-p24")&&$("i-p24").checked)}}).then(function(r){
    S.posiciones=r.posiciones;
    rPos();
    cMo();
    var newPosId=S.posiciones.reduce(function(mx,p){
      var pid=parseInt(p.id_posicion,10);
      return isNaN(pid)?mx:Math.max(mx,pid);
    },0);
    if(newPosId){mPosTurns(newPosId);}
    toast("Posición creada","ok");
  }).catch(function(e){toast(e.message,"er")});
}

function mEditPos(id){
  var p=S.posiciones.find(function(x){return x.id_posicion===id});if(!p)return;
  var totals=_posDayTotals(id);
  var info=totals.map(function(h,i){return DF[i].substring(0,2)+": "+(Math.round(h*10)/10)+"h"}).join(" · ");
  oMo('<h3>Editar posición</h3><div class="fr"><div class="fg gw"><label>Nombre</label><input id="ep-n" value="'+p.nombre+'"></div></div><div class="fr"><div class="fg gw"><label style="text-transform:none;letter-spacing:0"><input type="checkbox" id="ep-24"'+(p.es_24h?' checked':'')+' style="margin-right:6px"> Posición 24H (sumatorio de turnos = 24h por día)</label><p style="font-size:10px;color:var(--dm);margin-top:6px">Totales actuales por día: '+info+'</p></div></div><div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" onclick="cMo()">Cancelar</button><button class="btn pri" onclick="doEditPos('+id+')">Guardar</button></div>');
}

function doEditPos(id){
  api("/api/posiciones/"+id,{method:"PUT",body:{nombre:V("ep-n"),es_24h:!!($("ep-24")&&$("ep-24").checked)}}).then(function(r){
    S.posiciones=r.posiciones;
    rPos();
    cMo();
    toast("Posición actualizada","ok");
  }).catch(function(e){toast(e.message,"er")});
}

// Refactor módulo de asignaciones: carga fresca + eventos declarativos
function _loadAsigData(){
  return api("/api/asignaciones_servicio").then(function(rows){
    S.asignaciones_servicio = rows || [];
    return S.asignaciones_servicio;
  });
}

function _renderAsig(){
  var box=$("asig-t");if(!box)return;
  var srvs=S.servicios.filter(function(s){return s.activo});
  var emps=S.empleados.filter(function(e){return e.activo});
  var selected={};
  (S.asignaciones_servicio||[]).forEach(function(a){
    selected[a.id_empleado+"-"+a.id_servicio]=true;
  });
  var h='<table class="mx"><thead><tr><th style="text-align:left">Empleado</th>';
  srvs.forEach(function(s){h+='<th>'+s.nombre+'</th>'});
  h+='</tr></thead><tbody>';
  emps.forEach(function(e){
    h+='<tr><td style="text-align:left;font-weight:600">'+e.nombre+'</td>';
    srvs.forEach(function(s){
      var on=!!selected[e.id_empleado+"-"+s.id_servicio];
      h+='<td><button type="button" class="ck asig-btn" data-eid="'+e.id_empleado+'" data-sid="'+s.id_servicio+'" style="background:transparent;border:none;cursor:pointer;font-size:16px;color:'+(on?"var(--gn)":"var(--dm)")+'">'+(on?"●":"○")+'</button></td>';
    });
    h+='</tr>';
  });
  h+='</tbody></table>';
  box.innerHTML=h;
  box.querySelectorAll(".asig-btn").forEach(function(btn){
    btn.addEventListener("click",function(){
      var eid=parseInt(this.getAttribute("data-eid"),10);
      var sid=parseInt(this.getAttribute("data-sid"),10);
      if(isNaN(eid)||isNaN(sid)) return;
      _toggleAsig(eid,sid);
    });
  });
}

function _toggleAsig(eid,sid){
  api("/api/asignaciones_servicio/toggle",{method:"POST",body:{id_empleado:eid,id_servicio:sid}})
    .then(function(r){
      S.asignaciones_servicio=r.asignaciones_servicio||[];
      _renderAsig();
    })
    .catch(function(e){toast(e.message,"er")});
}
