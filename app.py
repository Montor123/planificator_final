"""Flask backend v3."""
from __future__ import annotations
import datetime as _dt, inspect, json, os, sys
from calendar import monthrange
from collections import defaultdict as _dd
from dataclasses import asdict
from datetime import date, time
from typing import Any
from flask import Flask, jsonify, request, send_from_directory
from flask.json.provider import DefaultJSONProvider

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from domain.enums import OFF_SHIFT, Severidad, Temporalidad, TipoRestriccion
from domain.models import *
from repositories.sqlite_repository import SQLiteRepository
from services.demand_service import DemandService
from services.restriction_service import RestrictionService
from services.shift_service import ShiftService
from solver.scheduler import Scheduler
from utils.date_utils import daterange
from utils.validation import parse_date, parse_time

app = Flask(__name__, static_folder="static")
class CJ(DefaultJSONProvider):
    def default(self, o):
        if isinstance(o, _dt.time): return o.strftime("%H:%M")
        if isinstance(o, _dt.date): return o.isoformat()
        return super().default(o)
app.json_provider_class = CJ; app.json = CJ(app)
DB = SQLiteRepository(os.path.join(BASE, "data", "planificator.db"))
SK = "app_state"; SCH = "last_schedule"
_SEED_EMPLOYEES = [
    (1,"Ana García","diurno"),
    (2,"Luis Martín","nocturno"),
    (3,"María López","indiferente"),
    (4,"Pedro Ruiz","indiferente"),
    (5,"Sara Díaz","diurno"),
    (6,"Carlos Moreno","indiferente"),
    (7,"Lucía Fernández","diurno"),
]
_SEED_ASSIGNMENTS = [
    (1,1,True),(1,2,False),(2,1,True),(3,1,False),(3,2,True),
    (4,2,True),(5,1,True),(5,2,False),(6,1,True),(6,2,False),
    (7,2,True),(7,1,False),
]
_SEED_POSITIONS = [
    (1,1,"Control acceso"),
    (2,1,"Ronda"),
    (3,2,"Control acceso"),
]

def _init():
    ss = ShiftService()
    return {
        "servicios": [asdict(Servicio(1,"Seguridad Norte","Norte","CC-001")),asdict(Servicio(2,"Seguridad Sur","Sur","CC-002"))],
        "posiciones": [asdict(Posicion(pid,sid,name)) for pid,sid,name in _SEED_POSITIONS],
        "turnos": [asdict(ss.enrich_shift(Turno(1,1,"Mañana",time(6,0),time(14,0),8,[0,1,2,3,4,5,6],Temporalidad.CONTINUO))),
                   asdict(ss.enrich_shift(Turno(2,1,"Tarde",time(14,0),time(22,0),8,[0,1,2,3,4,5,6],Temporalidad.CONTINUO))),
                   asdict(ss.enrich_shift(Turno(3,1,"Noche",time(22,0),time(6,0),8,[0,1,2,3,4,5,6],Temporalidad.CONTINUO))),
                   asdict(ss.enrich_shift(Turno(6,2,"Mañana",time(6,0),time(14,0),8,[0,1,2,3,4,5,6],Temporalidad.CONTINUO))),
                   asdict(ss.enrich_shift(Turno(7,2,"Tarde",time(14,0),time(22,0),8,[0,1,2,3,4,5,6],Temporalidad.CONTINUO))),
                   asdict(ss.enrich_shift(Turno(8,2,"Noche",time(22,0),time(6,0),8,[0,1,2,3,4,5,6],Temporalidad.CONTINUO))),
                   asdict(ss.enrich_shift(Turno(4,3,"Mañana",time(6,0),time(14,0),8,[0,1,2,3,4,5,6],Temporalidad.CONTINUO))),
                   asdict(ss.enrich_shift(Turno(5,3,"Noche",time(22,0),time(6,0),8,[0,1,2,3,4,5,6],Temporalidad.CONTINUO)))],
        "empleados": [asdict(Empleado(i,n,True,date(2025,1,1),horas_minimas=140,horas_maximas=176,horas_objetivo=162,preferencia_turno=p))
                      for i,n,p in _SEED_EMPLOYEES],
        "catalogo": {"10":asdict(Restriccion(10,31,"Vacaciones",5.4,"VAC",TipoRestriccion.VACACIONES,Severidad.HARD,True,True)),
                     "11":asdict(Restriccion(11,None,"Día libre",0,"DL",TipoRestriccion.DIA_LIBRE,Severidad.SOFT_LOW,False,False)),
                     "12":asdict(Restriccion(12,None,"Baja médica",5.4,"BM",TipoRestriccion.BAJA_MEDICA,Severidad.HARD,True,True))},
        "restricciones_empleado": [asdict(RestriccionEmpleado(2,10,date(2026,3,20))),asdict(RestriccionEmpleado(2,10,date(2026,3,21)))],
        "asignaciones_servicio": [{"id_empleado":e,"id_servicio":s,"es_principal":p}
            for e,s,p in _SEED_ASSIGNMENTS],
        "conciliaciones": [],
    }

def _load():
    data = _ensure_seed_state(_normalize_catalog_days(DB.load_json(SK, _init())))
    DB.save_json(SK, data)
    return data
def _save(d):
    data = _ensure_seed_state(_normalize_catalog_days(d))
    DB.save_json(SK, data)
    return data

def _normalize_catalog_days(data):
    cat = data.get("catalogo", {})
    changed = False
    for k, raw in list(cat.items()):
        if raw.get("tipo_restriccion") == TipoRestriccion.DIA_LIBRE.value and raw.get("dias") is not None:
            raw["dias"] = None
            cat[k] = raw
            changed = True
    if changed:
        data["catalogo"] = cat
    return data

def _ensure_seed_state(data):
    positions = data.get("posiciones", [])
    pos_ids = {int(p["id_posicion"]) for p in positions}
    for pid, sid, name in _SEED_POSITIONS:
        if pid in pos_ids:
            continue
        positions.append(asdict(Posicion(pid, sid, name, True)))
    positions.sort(key=lambda p: int(p["id_posicion"]))
    data["posiciones"] = positions

    emps = data.get("empleados", [])
    by_id = {int(e["id_empleado"]): e for e in emps}
    for eid, name, pref in _SEED_EMPLOYEES:
        if eid in by_id:
            continue
        emps.append(asdict(Empleado(
            eid, name, True, date(2025,1,1),
            horas_minimas=140, horas_maximas=176, horas_objetivo=162,
            preferencia_turno=pref
        )))
    emps.sort(key=lambda e: int(e["id_empleado"]))
    data["empleados"] = emps

    asigs = data.get("asignaciones_servicio", [])
    existing = {(int(a["id_empleado"]), int(a["id_servicio"])) for a in asigs}
    for eid, sid, principal in _SEED_ASSIGNMENTS:
        if (eid, sid) in existing:
            continue
        asigs.append({"id_empleado": eid, "id_servicio": sid, "es_principal": principal})
    data["asignaciones_servicio"] = asigs

    turnos = [_to_turno(t) for t in data.get("turnos", [])]
    has_ronda = any(t.id_posicion == 2 for t in turnos)
    if not has_ronda:
        ss = ShiftService()
        nid = max((t.id_turno for t in turnos), default=0) + 1
        for name, hi, hf in [("Mañana", time(6,0), time(14,0)), ("Tarde", time(14,0), time(22,0)), ("Noche", time(22,0), time(6,0))]:
            tt = ss.enrich_shift(Turno(nid, 2, name, hi, hf, 0, [0,1,2,3,4,5,6], Temporalidad.CONTINUO))
            turnos.append(tt)
            nid += 1
        data["turnos"] = [asdict(t) for t in turnos]
    return data

def _to_turno(x):
    if isinstance(x,Turno): return x
    d=dict(x)
    if isinstance(d.get("temporalidad"),str): d["temporalidad"]=Temporalidad(d["temporalidad"])
    if isinstance(d.get("hora_inicio"),str): d["hora_inicio"]=parse_time(d["hora_inicio"])
    if isinstance(d.get("hora_fin"),str): d["hora_fin"]=parse_time(d["hora_fin"])
    for k in ("fecha_inicio","fecha_fin"):
        if isinstance(d.get(k),str) and d[k]: d[k]=parse_date(d[k])
    return Turno(**d)

def _to_emp(x):
    if isinstance(x,Empleado): return x
    d=dict(x)
    if isinstance(d.get("fecha_alta"),str): d["fecha_alta"]=parse_date(d["fecha_alta"])
    if isinstance(d.get("fecha_baja"),str) and d["fecha_baja"]: d["fecha_baja"]=parse_date(d["fecha_baja"])
    valid={p.name for p in inspect.signature(Empleado).parameters.values()}
    return Empleado(**{k:v for k,v in d.items() if k in valid})

def _to_rest(x):
    if isinstance(x,Restriccion): return x
    d=dict(x)
    if isinstance(d.get("tipo_restriccion"),str): d["tipo_restriccion"]=TipoRestriccion(d["tipo_restriccion"])
    if isinstance(d.get("severidad"),str): d["severidad"]=Severidad(d["severidad"])
    return Restriccion(**d)

def _to_re(x):
    r=RestriccionEmpleado(**x) if not isinstance(x,RestriccionEmpleado) else x
    if isinstance(r.fecha,str): r.fecha=parse_date(r.fecha)
    return r

def _month_days(d: date) -> int:
    return monthrange(d.year, d.month)[1]

def _validate_month_request(start: date, days: int) -> str | None:
    if start.day != 1:
        return "La planificación debe comenzar el día 1 del mes"
    expected = _month_days(start)
    if days != expected:
        return f"La planificación debe cubrir el mes completo ({expected} días)"
    return None

def _restriction_hours_by_employee(restrictions, catalog, dates_set):
    out = {}
    for rr in restrictions:
        if rr.fecha not in dates_set:
            continue
        cat = catalog.get(rr.id_restriccion)
        if cat and cat.hora_dia:
            out[rr.id_empleado] = out.get(rr.id_empleado, 0.0) + float(cat.hora_dia)
    return out

def _vacation_days(restrictions, catalog):
    out = set()
    for rr in restrictions:
        cat = catalog.get(rr.id_restriccion)
        if cat and cat.tipo_restriccion == TipoRestriccion.VACACIONES:
            out.add((rr.id_empleado, rr.fecha))
    return out

def _shift_by_label(state, label: str):
    for raw in state.get("turnos", []):
        sh = _to_turno(raw)
        if label in {sh.sigla_turno, sh.nombre_turno}:
            return sh
    return None

def _restriction_overlay(restrictions, catalog, dates_set):
    out = {}
    for rr in restrictions:
        if rr.fecha not in dates_set:
            continue
        cat = catalog.get(rr.id_restriccion)
        if not cat or cat.severidad != Severidad.HARD:
            continue
        sigla = cat.siglas or cat.desc_restriccion[:2].upper()
        out.setdefault(rr.id_empleado, {})[str(rr.fecha)] = {
            "turno": sigla,
            "horas": float(cat.hora_dia or 0),
            "es_off": False,
            "es_restriccion": True,
        }
    return out

def _service_employee_map(services, employees, asig_srv):
    active_ids = [e.id_empleado for e in employees if e.activo]
    explicit = {}
    for a in asig_srv:
        explicit.setdefault(int(a["id_servicio"]), set()).add(int(a["id_empleado"]))
    out = {}
    for srv in services:
        sid = int(srv["id_servicio"])
        out[sid] = set(explicit.get(sid, active_ids))
    return out

def _allowed_shift_ids_by_employee(service_employee_ids, shifts, pos_srv, employees):
    active_ids = {e.id_empleado for e in employees if e.activo}
    allowed = {eid: set() for eid in active_ids}
    for sh in shifts:
        sid = pos_srv.get(sh.id_posicion, 1)
        eligible = service_employee_ids.get(sid, active_ids)
        for eid in eligible:
            if eid in active_ids:
                allowed.setdefault(eid, set()).add(sh.id_turno)
    return allowed

def _build_hours_summary(employees, work_hours, restriction_hours):
    summary = []
    for e in employees:
        if not e.activo:
            continue
        hw = round(work_hours.get(e.id_empleado, 0.0), 1)
        hr = round(restriction_hours.get(e.id_empleado, 0.0), 1)
        ht = round(hw + hr, 1)
        obj = e.horas_objetivo or 162
        summary.append({
            "id": e.id_empleado,
            "nombre": e.nombre,
            "horas_trabajo": hw,
            "horas_restriccion": hr,
            "horas_total": ht,
            "objetivo": obj,
            "diff": round(ht - obj, 1),
        })
    return summary

def _recompute_schedule_hours(schedule, state):
    employees = [_to_emp(x) for x in state["empleados"]]
    restrictions = [_to_re(x) for x in state["restricciones_empleado"]]
    catalog = {int(k): _to_rest(v) for k, v in state["catalogo"].items()}
    dates_set = {parse_date(ds) for ds in schedule.get("dates", [])}
    restriction_hours = _restriction_hours_by_employee(restrictions, catalog, dates_set)
    work_hours = {}
    seen = set()
    for _, sd in schedule.get("grids", {}).items():
        for ek, ed in sd.get("employees", {}).items():
            eid = int(ek)
            for ds, cell in ed.get("days", {}).items():
                if cell.get("es_off") or cell.get("es_restriccion"):
                    continue
                key = (eid, ds)
                if key in seen:
                    continue
                seen.add(key)
                work_hours[eid] = work_hours.get(eid, 0.0) + float(cell.get("horas", 0.0) or 0.0)
    schedule["hours"] = _build_hours_summary(employees, work_hours, restriction_hours)
    return schedule

def _validate_schedule_edit(schedule, state, service_id: int, employee_id: int, on_date: str, turno: str, horas: float) -> str | None:
    sk = str(service_id)
    ek = str(employee_id)
    if sk not in schedule.get("grids", {}) or ek not in schedule["grids"][sk].get("employees", {}):
        return "Celda no encontrada"

    proposed = {"turno": turno, "horas": float(horas), "es_off": turno == "OFF"}
    sh = None if turno == "OFF" else _shift_by_label(state, turno)
    restrictions = [_to_re(x) for x in state["restricciones_empleado"]]
    catalog = {int(k): _to_rest(v) for k, v in state["catalogo"].items()}
    if sh and sh.cruza_medianoche:
        vac_days = _vacation_days(restrictions, catalog)
        edit_date = parse_date(on_date)
        if (employee_id, edit_date + _dt.timedelta(days=1)) in vac_days:
            return "No se puede asignar un turno que termine después de las 23:59 si al día siguiente empiezan vacaciones"
    worked_same_day = 0
    total_work = 0.0
    for sid, sd in schedule.get("grids", {}).items():
        ed = sd.get("employees", {}).get(ek)
        if not ed:
            continue
        for ds, existing in ed.get("days", {}).items():
            cell = proposed if sid == sk and ds == on_date else existing
            if not cell or cell.get("es_off") or cell.get("es_restriccion"):
                continue
            if ds == on_date:
                worked_same_day += 1
            total_work += float(cell.get("horas", 0.0) or 0.0)

    if worked_same_day > 1:
        return "No se puede asignar al mismo empleado en dos servicios el mismo día"

    emp = next((x for x in (_to_emp(e) for e in state["empleados"]) if x.id_empleado == employee_id), None)
    if not emp or emp.horas_maximas is None:
        return None

    dates_set = {parse_date(ds) for ds in schedule.get("dates", [])}
    restriction_hours = _restriction_hours_by_employee(restrictions, catalog, dates_set).get(employee_id, 0.0)
    if total_work + restriction_hours > emp.horas_maximas + 1e-6:
        return f"El empleado supera sus horas máximas mensuales ({emp.horas_maximas}h)"
    return None

def _generate_schedule_result(data, start: date, days: int, max_time: int):
    employees = [_to_emp(x) for x in data["empleados"]]
    active_employees = [e for e in employees if e.activo]
    shifts = [_to_turno(x) for x in data["turnos"]]
    restrictions = [_to_re(x) for x in data["restricciones_empleado"]]
    catalog = {int(k): _to_rest(v) for k, v in data["catalogo"].items()}
    requirements = DemandService().build_requirements(shifts, start, days)
    asig_srv = data.get("asignaciones_servicio", [])
    concs = data.get("conciliaciones", [])
    pos_srv = {pp["id_posicion"]: pp["id_servicio"] for pp in data["posiciones"]}
    service_employee_ids = _service_employee_map(data["servicios"], active_employees, asig_srv)
    allowed_shift_ids = _allowed_shift_ids_by_employee(service_employee_ids, shifts, pos_srv, active_employees)
    dates = daterange(start, days)
    dates_set = set(dates)
    restriction_hours = _restriction_hours_by_employee(restrictions, catalog, dates_set)
    restr_overlay = _restriction_overlay(restrictions, catalog, dates_set)
    scheduler = Scheduler(max(1, int(max_time or 30)))
    plan, sched_summary, work_hours = scheduler.solve(
        active_employees,
        shifts,
        requirements,
        restrictions,
        catalog,
        start,
        days,
        concs,
        allowed_shift_ids=allowed_shift_ids,
        preassigned_hours=restriction_hours,
    )

    shift_by_id = {s.id_turno: s for s in shifts}
    srv_names = {s["id_servicio"]: s["nombre"] for s in data["servicios"]}
    pos_names = {pp["id_posicion"]: pp["nombre"] for pp in data["posiciones"]}
    service_shift_ids = {}
    for sh in shifts:
        service_shift_ids.setdefault(pos_srv.get(sh.id_posicion, 1), set()).add(sh.id_turno)

    emp_map = {e.id_empleado: e for e in active_employees}
    grids = {}

    def ensure_row(service_id: int, employee_id: int):
        sk = str(service_id)
        ek = str(employee_id)
        if sk not in grids:
            grids[sk] = {"nombre": srv_names.get(service_id, "Servicio"), "employees": {}}
        if ek not in grids[sk]["employees"]:
            days_map = {}
            for d in dates:
                ds = str(d)
                base = {"turno": OFF_SHIFT, "horas": 0.0, "es_off": True}
                if employee_id in restr_overlay and ds in restr_overlay[employee_id]:
                    base = dict(restr_overlay[employee_id][ds])
                days_map[ds] = base
            grids[sk]["employees"][ek] = {"nombre": emp_map[employee_id].nombre, "posicion": "", "days": days_map}
        return grids[sk]["employees"][ek]

    for srv in data["servicios"]:
        sid = srv["id_servicio"]
        if sid not in service_shift_ids:
            continue
        grids[str(sid)] = {"nombre": srv_names.get(sid, "Servicio"), "employees": {}}
        for eid in sorted(service_employee_ids.get(sid, set())):
            if eid in emp_map:
                ensure_row(sid, eid)

    for a in plan:
        if a.es_off or a.id_empleado not in emp_map:
            continue
        sid = pos_srv.get(a.id_posicion, a.id_servicio or 1)
        row = ensure_row(sid, a.id_empleado)
        row["days"][str(a.fecha)] = {"turno": a.turno_asignado, "horas": a.horas, "es_off": False}
        if not row["posicion"]:
            row["posicion"] = pos_names.get(a.id_posicion, "")

    for sid, sh_ids in service_shift_ids.items():
        sk = str(sid)
        if sk not in grids:
            grids[sk] = {"nombre": srv_names.get(sid, "Servicio"), "employees": {}}
        srv_dark = {}
        for (d, tid), needed in requirements.items():
            if tid not in sh_ids:
                continue
            sh = shift_by_id.get(tid)
            if not sh:
                continue
            sig = sh.sigla_turno or sh.nombre_turno
            covered = 0
            for _, ed in grids[sk]["employees"].items():
                cell = ed["days"].get(str(d))
                if cell and not cell.get("es_off") and not cell.get("es_restriccion") and cell.get("turno") == sig:
                    covered += 1
            short = max(0, needed - covered)
            if short > 0:
                ds = str(d)
                srv_dark[ds] = round(srv_dark.get(ds, 0.0) + short * sh.duracion_horas, 1)
        if srv_dark:
            grids[sk]["dark_post"] = srv_dark

    return {
        "grids": grids,
        "dates": [str(d) for d in dates],
        "hours": _build_hours_summary(active_employees, work_hours, restriction_hours),
        "summary": {"faltantes": int((sched_summary or {}).get("faltantes", 0)), "total": len(plan)},
    }

# ── Routes ──────────────────────────────────────────────────────────
@app.route("/")
def index(): return send_from_directory("static","index.html")
@app.route("/static/<path:p>")
def static_f(p): return send_from_directory("static",p)

@app.route("/api/state")
def get_state(): return jsonify(_load())
@app.route("/api/reset",methods=["POST"])
def reset_state(): _save(_init()); DB.save_json(SCH,None); return jsonify(_load())

# CRUD Servicios
@app.route("/api/servicios",methods=["POST"])
def add_srv():
    p=request.json or {};data=_load();items=[Servicio(**x) for x in data["servicios"]]
    nid=max((s.id_servicio for s in items),default=0)+1
    items.append(Servicio(nid,p["nombre"],p.get("area",""),p.get("centro_coste",""),True))
    data["servicios"]=[asdict(s) for s in items];_save(data);return jsonify({"ok":True,"servicios":data["servicios"]})
@app.route("/api/servicios/<int:sid>",methods=["PUT"])
def edit_srv(sid):
    p=request.json or {};data=_load();items=[Servicio(**x) for x in data["servicios"]]
    for s in items:
        if s.id_servicio==sid: s.nombre=p.get("nombre",s.nombre);s.area=p.get("area",s.area);s.centro_coste=p.get("centro_coste",s.centro_coste);s.activo=p.get("activo",s.activo)
    data["servicios"]=[asdict(s) for s in items];_save(data);return jsonify({"ok":True,"servicios":data["servicios"]})
@app.route("/api/servicios/<int:sid>",methods=["DELETE"])
def del_srv(sid):
    data=_load();items=[Servicio(**x) for x in data["servicios"]]
    for s in items:
        if s.id_servicio==sid: s.activo=False
    data["servicios"]=[asdict(s) for s in items];_save(data);return jsonify({"ok":True,"servicios":data["servicios"]})

# CRUD Posiciones
@app.route("/api/posiciones",methods=["POST"])
def add_pos():
    p=request.json or {};data=_load();items=[Posicion(**x) for x in data["posiciones"]]
    nid=max((x.id_posicion for x in items),default=0)+1
    items.append(Posicion(nid,int(p["id_servicio"]),p["nombre"],True))
    data["posiciones"]=[asdict(x) for x in items];_save(data);return jsonify({"ok":True,"posiciones":data["posiciones"]})
@app.route("/api/posiciones/<int:pid>",methods=["PUT"])
def edit_pos(pid):
    p=request.json or {};data=_load();items=[Posicion(**x) for x in data["posiciones"]]
    for x in items:
        if x.id_posicion==pid: x.nombre=p.get("nombre",x.nombre);x.activa=p.get("activa",x.activa)
    data["posiciones"]=[asdict(x) for x in items];_save(data);return jsonify({"ok":True,"posiciones":data["posiciones"]})
@app.route("/api/posiciones/<int:pid>",methods=["DELETE"])
def del_pos(pid):
    data=_load();items=[Posicion(**x) for x in data["posiciones"]]
    for x in items:
        if x.id_posicion==pid: x.activa=False
    data["posiciones"]=[asdict(x) for x in items];_save(data);return jsonify({"ok":True,"posiciones":data["posiciones"]})

# CRUD Turnos
@app.route("/api/turnos",methods=["POST"])
def add_trn():
    p=request.json or {};data=_load();turnos=[_to_turno(x) for x in data["turnos"]]
    nid=max((t.id_turno for t in turnos),default=0)+1
    dias=[int(d) for d in p.get("dias_recurrencia",[0,1,2,3,4,5,6])]
    t=Turno(nid,int(p["id_posicion"]),p["nombre_turno"],parse_time(p["hora_inicio"]),parse_time(p["hora_fin"]),0,dias,
            Temporalidad(p.get("temporalidad","continuo")),parse_date(p["fecha_inicio"]) if p.get("fecha_inicio") else None,parse_date(p["fecha_fin"]) if p.get("fecha_fin") else None)
    t=ShiftService().enrich_shift(t)
    t.grupo_rotacion=p.get("grupo_rotacion") or None;t.es_indistinto=bool(p.get("es_indistinto",False))
    turnos.append(t)
    data["turnos"]=[asdict(x) for x in turnos];_save(data);return jsonify({"ok":True,"turnos":data["turnos"]})
@app.route("/api/turnos/<int:tid>",methods=["PUT"])
def edit_trn(tid):
    p=request.json or {};data=_load();turnos=[_to_turno(x) for x in data["turnos"]];ss=ShiftService()
    for t in turnos:
        if t.id_turno==tid:
            t.nombre_turno=p.get("nombre_turno",t.nombre_turno)
            if p.get("hora_inicio"): t.hora_inicio=parse_time(p["hora_inicio"])
            if p.get("hora_fin"): t.hora_fin=parse_time(p["hora_fin"])
            if "dias_recurrencia" in p: t.dias_recurrencia=[int(d) for d in p["dias_recurrencia"]]
            if "grupo_rotacion" in p: t.grupo_rotacion=p["grupo_rotacion"] or None
            if "es_indistinto" in p: t.es_indistinto=bool(p["es_indistinto"])
            ss.enrich_shift(t)
    data["turnos"]=[asdict(x) for x in turnos];_save(data);return jsonify({"ok":True,"turnos":data["turnos"]})
@app.route("/api/turnos/<int:tid>",methods=["DELETE"])
def del_trn(tid):
    data=_load();data["turnos"]=[x for x in data["turnos"] if x["id_turno"]!=tid];_save(data);return jsonify({"ok":True,"turnos":data["turnos"]})

# CRUD Empleados
@app.route("/api/empleados",methods=["POST"])
def add_emp():
    p=request.json or {};data=_load();emps=[_to_emp(x) for x in data["empleados"]]
    nid=max((e.id_empleado for e in emps),default=0)+1
    emps.append(Empleado(nid,p["nombre"],True,parse_date(p.get("fecha_alta","2025-01-01")),
        horas_minimas=float(p.get("horas_minimas",140)),horas_maximas=float(p.get("horas_maximas",176)),
        horas_objetivo=float(p.get("horas_objetivo",162)),preferencia_turno=p.get("preferencia_turno","indiferente")))
    data["empleados"]=[asdict(e) for e in emps];_save(data);return jsonify({"ok":True,"empleados":data["empleados"]})
@app.route("/api/empleados/<int:eid>",methods=["PUT"])
def edit_emp(eid):
    p=request.json or {};data=_load();emps=[_to_emp(x) for x in data["empleados"]]
    for e in emps:
        if e.id_empleado==eid:
            for k in ("nombre","activo","horas_minimas","horas_maximas","horas_objetivo","preferencia_turno"):
                if k in p: setattr(e,k,float(p[k]) if k.startswith("horas") else p[k])
    data["empleados"]=[asdict(e) for e in emps];_save(data);return jsonify({"ok":True,"empleados":data["empleados"]})
@app.route("/api/empleados/<int:eid>",methods=["DELETE"])
def del_emp(eid):
    data=_load();emps=[_to_emp(x) for x in data["empleados"]]
    for e in emps:
        if e.id_empleado==eid: e.activo=False
    data["empleados"]=[asdict(e) for e in emps];_save(data);return jsonify({"ok":True,"empleados":data["empleados"]})

# CRUD Catálogo
@app.route("/api/catalogo",methods=["POST"])
def add_cat():
    p=request.json or {};data=_load();cat={int(k):_to_rest(v) for k,v in data["catalogo"].items()}
    nid=max(cat.keys(),default=0)+1;tipo=TipoRestriccion(p["tipo_restriccion"])
    sev=Severidad(p["severidad"]) if p.get("severidad") else RestrictionService().default_severity_for_type(tipo)
    dias=None if tipo==TipoRestriccion.DIA_LIBRE else (int(p["dias"]) if p.get("dias") else 1)
    cat[nid]=Restriccion(nid,dias,p["desc_restriccion"],float(p.get("hora_dia",0)),p.get("siglas"),tipo,sev,True,True,True)
    data["catalogo"]={str(k):asdict(v) for k,v in cat.items()};_save(data);return jsonify({"ok":True,"catalogo":data["catalogo"]})
@app.route("/api/catalogo/<int:rid>",methods=["PUT"])
def edit_cat(rid):
    p=request.json or {};data=_load();cat={int(k):_to_rest(v) for k,v in data["catalogo"].items()}
    if rid in cat:
        c=cat[rid];c.desc_restriccion=p.get("desc_restriccion",c.desc_restriccion)
        if p.get("tipo_restriccion"): c.tipo_restriccion=TipoRestriccion(p["tipo_restriccion"])
        if p.get("severidad"): c.severidad=Severidad(p["severidad"])
        if "hora_dia" in p: c.hora_dia=float(p["hora_dia"])
        if c.tipo_restriccion==TipoRestriccion.DIA_LIBRE:
            c.dias=None
        elif "dias" in p:
            c.dias=int(p["dias"]) if p["dias"] else None
        if p.get("siglas"): c.siglas=p["siglas"]
        c.activa=p.get("activa",c.activa)
    data["catalogo"]={str(k):asdict(v) for k,v in cat.items()};_save(data);return jsonify({"ok":True,"catalogo":data["catalogo"]})
@app.route("/api/catalogo/<int:rid>",methods=["DELETE"])
def del_cat(rid):
    data=_load();cat={int(k):_to_rest(v) for k,v in data["catalogo"].items()}
    if rid in cat: cat[rid].activa=False
    data["catalogo"]={str(k):asdict(v) for k,v in cat.items()};_save(data);return jsonify({"ok":True,"catalogo":data["catalogo"]})

# CRUD Restricciones empleado
@app.route("/api/restricciones",methods=["POST"])
def assign_rest():
    p=request.json or {};data=_load();rs=RestrictionService();rows=[_to_re(x) for x in data["restricciones_empleado"]]
    cat={int(k):_to_rest(v) for k,v in data["catalogo"].items()}
    rid=int(p["id_restriccion"]);eid=int(p["id_empleado"]);fi=parse_date(p["fecha_ini"]);ff=parse_date(p["fecha_fin"])
    nd=(ff-fi).days+1
    if rid in cat and cat[rid].tipo_restriccion!=TipoRestriccion.DIA_LIBRE and cat[rid].dias:
        existing=sum(1 for r in rows if r.id_empleado==eid and r.id_restriccion==rid)
        if existing+nd>cat[rid].dias:
            return jsonify({"ok":False,"error":f"Límite excedido: {cat[rid].desc_restriccion} permite {cat[rid].dias} días, ya tiene {existing}, intenta añadir {nd}"}),400
    rows.extend(rs.expand_range_to_daily(eid,rid,fi,ff,parse_time(p["hora_ini"]) if p.get("hora_ini") else None,parse_time(p["hora_fin"]) if p.get("hora_fin") else None,p.get("observaciones")))
    data["restricciones_empleado"]=[asdict(r) for r in rows];_save(data);return jsonify({"ok":True,"restricciones":data["restricciones_empleado"]})
@app.route("/api/restricciones/delete",methods=["POST"])
def del_rest():
    p=request.json or {};data=_load();target=parse_date(p["fecha"]);eid=int(p["id_empleado"]);rid=int(p["id_restriccion"])
    rows=[_to_re(x) for x in data["restricciones_empleado"]]
    rows=[r for r in rows if not(r.id_empleado==eid and r.id_restriccion==rid and r.fecha==target)]
    data["restricciones_empleado"]=[asdict(r) for r in rows];_save(data);return jsonify({"ok":True,"restricciones":data["restricciones_empleado"]})

# Asignaciones servicio-empleado
@app.route("/api/asignaciones_servicio")
def get_asig(): return jsonify(_load().get("asignaciones_servicio",[]))
@app.route("/api/asignaciones_servicio/toggle",methods=["POST"])
def toggle_asig():
    p=request.json or {};eid=int(p["id_empleado"]);sid=int(p["id_servicio"]);data=_load()
    asigs=data.get("asignaciones_servicio",[]);found=False;new_a=[]
    for a in asigs:
        if a["id_empleado"]==eid and a["id_servicio"]==sid: found=True
        else: new_a.append(a)
    if not found: new_a.append({"id_empleado":eid,"id_servicio":sid,"es_principal":p.get("es_principal",False)})
    data["asignaciones_servicio"]=new_a;_save(data);return jsonify({"ok":True,"asignaciones_servicio":data["asignaciones_servicio"]})

# Conciliaciones
@app.route("/api/conciliaciones")
def get_conc(): return jsonify(_load().get("conciliaciones",[]))
@app.route("/api/conciliaciones",methods=["POST"])
def add_conc():
    p=request.json or {};data=_load();concs=data.get("conciliaciones",[])
    nid=max((c.get("id_conciliacion",0) for c in concs),default=0)+1
    for d in p.get("dias",[]):
        concs.append({"id_conciliacion":nid,"id_empleado":int(p["id_empleado"]),"dia_semana":int(d["dia_semana"]),
                      "hora_ini":d["hora_ini"],"hora_fin":d["hora_fin"],"fecha_ini":p["fecha_ini"],"fecha_fin":p["fecha_fin"]})
    data["conciliaciones"]=concs;_save(data);return jsonify({"ok":True,"conciliaciones":data["conciliaciones"]})
@app.route("/api/conciliaciones/<int:cid>",methods=["DELETE"])
def del_conc(cid):
    data=_load();data["conciliaciones"]=[c for c in data.get("conciliaciones",[]) if c.get("id_conciliacion")!=cid]
    _save(data);return jsonify({"ok":True,"conciliaciones":data["conciliaciones"]})

# Generar horario
@app.route("/api/generar",methods=["POST"])
def api_gen():
    p=request.json or {};data=_load();start=parse_date(p["start_date"]);days=int(p["num_days"])
    error=_validate_month_request(start, days)
    if error: return jsonify({"ok":False,"error":error}),400
    try:
        result=_generate_schedule_result(data,start,days,max(1, int(p.get("max_time") or 30)))
    except RuntimeError as exc:
        return jsonify({"ok":False,"error":str(exc)}),500
    DB.save_json(SCH,result);return jsonify(result)

# Manual edit
@app.route("/api/schedule/edit",methods=["POST"])
def edit_cell():
    p=request.json or {};sch=DB.load_json(SCH,None);state=_load()
    if not sch: return jsonify({"ok":False,"error":"No hay horario"}),400
    sk=str(p["id_servicio"]);ek=str(p["id_empleado"]);f=p["fecha"];t=p["turno"];h=float(p.get("horas",0))
    error=_validate_schedule_edit(sch,state,int(sk),int(ek),f,t,h)
    if error: return jsonify({"ok":False,"error":error}),400
    if sk in sch["grids"] and ek in sch["grids"][sk]["employees"]:
        sch["grids"][sk]["employees"][ek]["days"][f]={"turno":t,"horas":h,"es_off":t=="OFF"}
        DB.save_json(SCH,_recompute_schedule_hours(sch,state));return jsonify({"ok":True})
    return jsonify({"ok":False,"error":"Celda no encontrada"}),404

@app.route("/api/schedule")
def get_sch():
    s=DB.load_json(SCH,None)
    if not s: return jsonify({"ok":False}),404
    return jsonify(s)

# Histórico de horarios
@app.route("/api/schedule/history")
def list_history():
    return jsonify(DB.list_schedule_versions())

@app.route("/api/schedule/save",methods=["POST"])
def save_history():
    p=request.json or {};sch=DB.load_json(SCH,None)
    if not sch: return jsonify({"ok":False,"error":"No hay horario activo"}),400
    nombre=p.get("nombre") or f"Horario {_dt.date.today().isoformat()}"
    vid=DB.save_schedule_version(nombre,p.get("fecha_inicio",""),p.get("fecha_fin",""),sch)
    return jsonify({"ok":True,"id":vid})

@app.route("/api/schedule/history/<int:vid>")
def get_history_version(vid):
    data=DB.load_schedule_version(vid)
    if data is None: return jsonify({"ok":False,"error":"No encontrado"}),404
    return jsonify(data)

@app.route("/api/schedule/history/<int:vid>",methods=["DELETE"])
def del_history_version(vid):
    DB.delete_schedule_version(vid);return jsonify({"ok":True})

@app.route("/api/schedule/history/<int:vid>/edit",methods=["POST"])
def edit_history_cell(vid):
    p=request.json or {};data=DB.load_schedule_version(vid);state=_load()
    if not data: return jsonify({"ok":False,"error":"Versión no encontrada"}),404
    sk=str(p["id_servicio"]);ek=str(p["id_empleado"]);f=p["fecha"];t=p["turno"];h=float(p.get("horas",0))
    error=_validate_schedule_edit(data,state,int(sk),int(ek),f,t,h)
    if error: return jsonify({"ok":False,"error":error}),400
    if sk in data["grids"] and ek in data["grids"][sk]["employees"]:
        data["grids"][sk]["employees"][ek]["days"][f]={"turno":t,"horas":h,"es_off":t=="OFF"}
        DB.update_schedule_version(vid,_recompute_schedule_hours(data,state));return jsonify({"ok":True})
    return jsonify({"ok":False,"error":"Celda no encontrada"}),404

# Resúmenes
@app.route("/api/resumen/empleado/<int:eid>")
def res_emp(eid):
    sch=DB.load_json(SCH,None)
    if not sch: return jsonify({"error":"Sin horario"}),404
    data=_load();catalog={int(k):_to_rest(v) for k,v in data["catalogo"].items()};restrictions=[_to_re(x) for x in data["restricciones_empleado"]]
    tc={};th=0;off=0
    for _,sd in sch["grids"].items():
        ed=sd["employees"].get(str(eid))
        if not ed: continue
        for _,c in ed["days"].items():
            if c["es_off"]: off+=1
            else: th+=c["horas"]
            tc[c["turno"]]=tc.get(c["turno"],0)+1
    rh=sum(catalog[r.id_restriccion].hora_dia for r in restrictions if r.id_empleado==eid and r.id_restriccion in catalog and catalog[r.id_restriccion].hora_dia)
    rd=sum(1 for r in restrictions if r.id_empleado==eid)
    emp=next((e for e in data["empleados"] if e["id_empleado"]==eid),None)
    return jsonify({"empleado":emp,"horas_trabajo":round(th,1),"horas_restriccion":round(rh,1),"horas_total":round(th+rh,1),"dias_off":off,"dias_restriccion":rd,"turnos_count":tc})

@app.route("/api/resumen/servicio/<int:sid>")
def res_srv(sid):
    sch=DB.load_json(SCH,None)
    if not sch: return jsonify({"error":"Sin horario"}),404
    sd=sch["grids"].get(str(sid))
    if not sd: return jsonify({"error":"No encontrado"}),404
    eh={};tc={}
    for _,ed in sd["employees"].items():
        h=0
        for _,c in ed["days"].items():
            if not c["es_off"]: h+=c["horas"];tc[c["turno"]]=tc.get(c["turno"],0)+1
        eh[ed["nombre"]]=round(h,1)
    return jsonify({"servicio":sd["nombre"],"empleados":eh,"turnos_count":tc,"total_horas":round(sum(eh.values()),1)})

if __name__=="__main__": app.run(host="0.0.0.0",port=5000,debug=True)
