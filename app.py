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
from services.assignment_service import AssignmentService
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
    (1,1,True),
    (2,1,True),
    (3,1,True),
    (4,1,True),
    (5,1,True),
    (6,1,True),
    (7,1,True),
]
_SEED_POSITIONS = [
    (1,1,"Control acceso"),
    (2,1,"Ronda"),
]

def _init_legacy():
    ss = ShiftService()
    return {
        "servicios": [asdict(Servicio(1,"Seguridad Norte","Norte","CC-001"))],
        "posiciones": [asdict(Posicion(pid,sid,name)) for pid,sid,name in _SEED_POSITIONS],
        "turnos": [asdict(ss.enrich_shift(Turno(1,1,"Mañana",time(6,0),time(14,0),8,[0,1,2,3,4,5,6],Temporalidad.CONTINUO))),
                   asdict(ss.enrich_shift(Turno(2,1,"Tarde",time(14,0),time(22,0),8,[0,1,2,3,4,5,6],Temporalidad.CONTINUO))),
                   asdict(ss.enrich_shift(Turno(3,1,"Noche",time(22,0),time(6,0),8,[0,1,2,3,4,5,6],Temporalidad.CONTINUO))),
                   asdict(ss.enrich_shift(Turno(6,2,"Mañana",time(6,0),time(14,0),8,[0,1,2,3,4,5,6],Temporalidad.CONTINUO))),
                   asdict(ss.enrich_shift(Turno(7,2,"Tarde",time(14,0),time(22,0),8,[0,1,2,3,4,5,6],Temporalidad.CONTINUO))),
                   asdict(ss.enrich_shift(Turno(8,2,"Noche",time(22,0),time(6,0),8,[0,1,2,3,4,5,6],Temporalidad.CONTINUO)))],
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

# Override de semilla inicial: un único servicio (Seguridad Norte).
def _init():
    return _init_legacy()

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
    service_ids = {int(s["id_servicio"]) for s in data.get("servicios", [])}
    positions = [
        p for p in data.get("posiciones", [])
        if int(p.get("id_servicio", 0)) in service_ids
    ]
    for p in positions:
        if "es_24h" not in p:
            p["es_24h"] = False
        if "modo_24h" not in p:
            p["modo_24h"] = "8h"
        if "temporalidad" not in p:
            p["temporalidad"] = Temporalidad.CONTINUO.value
        if p.get("temporalidad") != Temporalidad.TEMPORAL.value:
            p["fecha_inicio"] = None
            p["fecha_fin"] = None
        if isinstance(p.get("fecha_inicio"), date):
            p["fecha_inicio"] = str(p["fecha_inicio"])
        if isinstance(p.get("fecha_fin"), date):
            p["fecha_fin"] = str(p["fecha_fin"])
    pos_ids = {int(p["id_posicion"]) for p in positions}
    for pid, sid, name in _SEED_POSITIONS:
        if sid not in service_ids:
            continue
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

    raw_asigs = data.get("asignaciones_servicio")
    if raw_asigs is None:
        raw_asigs = [
            {"id_empleado": eid, "id_servicio": sid, "es_principal": principal}
            for eid, sid, principal in _SEED_ASSIGNMENTS
        ]
    data["asignaciones_servicio"] = _normalize_assignments_rows(
        [a for a in raw_asigs if int(a.get("id_servicio", 0)) in service_ids]
    )
    data["restricciones_empleado"] = _normalize_restriction_rows(data.get("restricciones_empleado", []))

    turnos = []
    for raw in data.get("turnos", []):
        tt = _to_turno(raw)
        if int(tt.id_posicion) not in pos_ids:
            continue
        turnos.append(tt)
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

def _to_pos(x):
    if isinstance(x,Posicion): return x
    d=dict(x)
    if "es_24h" not in d:
        d["es_24h"] = False
    mode = str(d.get("modo_24h") or "8h").lower()
    if mode not in {"8h", "12h", "auto"}:
        mode = "8h"
    d["modo_24h"] = mode
    d["temporalidad"] = _normalize_position_temporality(d.get("temporalidad"))
    if isinstance(d.get("fecha_inicio"), str) and d["fecha_inicio"]:
        d["fecha_inicio"] = parse_date(d["fecha_inicio"])
    if isinstance(d.get("fecha_fin"), str) and d["fecha_fin"]:
        d["fecha_fin"] = parse_date(d["fecha_fin"])
    if d["temporalidad"] == Temporalidad.CONTINUO:
        d["fecha_inicio"] = None
        d["fecha_fin"] = None
    return Posicion(**d)

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

def _normalize_assignments_rows(rows):
    return AssignmentService.normalize_rows(rows)

def _normalize_restriction_rows(rows):
    by_key = {}
    for raw in rows or []:
        try:
            rr = _to_re(raw)
        except Exception:
            continue
        key = (int(rr.id_empleado), int(rr.id_restriccion), rr.fecha)
        prev = by_key.get(key)
        if prev is None:
            by_key[key] = rr
            continue
        if rr.hora_ini is not None:
            prev.hora_ini = rr.hora_ini
        if rr.hora_fin is not None:
            prev.hora_fin = rr.hora_fin
        if rr.observaciones:
            prev.observaciones = rr.observaciones
    ordered = sorted(by_key.values(), key=lambda r: (int(r.id_empleado), r.fecha, int(r.id_restriccion)))
    return [asdict(r) for r in ordered]

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

def _shift_by_id(state, turn_id: int | None):
    if turn_id is None:
        return None
    try:
        tid = int(turn_id)
    except (TypeError, ValueError):
        return None
    for raw in state.get("turnos", []):
        sh = _to_turno(raw)
        if int(sh.id_turno) == tid:
            return sh
    return None

def _shift_by_label_for_position(state, label: str, position_id: int | None = None):
    candidates = []
    for raw in state.get("turnos", []):
        sh = _to_turno(raw)
        if label in {sh.sigla_turno, sh.nombre_turno}:
            candidates.append(sh)
    if not candidates:
        return None
    if position_id is not None:
        for sh in candidates:
            if int(sh.id_posicion) == int(position_id):
                return sh
    return candidates[0]

def _row_employee_id(row_key: str, row_data: dict) -> int | None:
    raw = row_data.get("id_empleado", None)
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    try:
        return int(str(row_key).split(":", 1)[0])
    except (TypeError, ValueError):
        return None

def _row_position_id(row_data: dict) -> int | None:
    raw = row_data.get("id_posicion", None)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None

def _find_schedule_row(schedule, service_id: int, employee_id: int, row_key: str | None = None, position_id: int | None = None):
    sk = str(service_id)
    service_grid = schedule.get("grids", {}).get(sk, {})
    rows = service_grid.get("employees", {})
    if not isinstance(rows, dict):
        return None, None
    if row_key and row_key in rows:
        row = rows[row_key]
        if _row_employee_id(row_key, row) == int(employee_id):
            return row_key, row
    matches = []
    for rk, row in rows.items():
        eid = _row_employee_id(rk, row)
        if eid != int(employee_id):
            continue
        pid = _row_position_id(row)
        if position_id is not None and pid != int(position_id):
            continue
        matches.append((rk, row))
    if not matches:
        return None, None
    if row_key:
        return None, None
    return matches[0]

def _cell_matches_shift(cell: dict, row: dict, shift: Turno) -> bool:
    if not cell or cell.get("es_off") or cell.get("es_restriccion"):
        return False
    cid = cell.get("id_turno")
    if cid is not None:
        try:
            return int(cid) == int(shift.id_turno)
        except (TypeError, ValueError):
            return False
    row_pos = _row_position_id(row)
    if row_pos is not None and int(row_pos) != int(shift.id_posicion):
        return False
    return cell.get("turno") == (shift.sigla_turno or shift.nombre_turno)

_WD = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

def _position_day_totals(state, position_id: int, *, exclude_turn_id: int | None = None, candidate_shift: Turno | None = None):
    totals = {i: 0.0 for i in range(7)}
    for raw in state.get("turnos", []):
        sh = _to_turno(raw)
        if sh.id_posicion != position_id:
            continue
        if exclude_turn_id is not None and sh.id_turno == exclude_turn_id:
            continue
        hours = float(sh.duracion_horas or 0.0)
        for wd in sh.dias_recurrencia or []:
            if 0 <= int(wd) <= 6:
                totals[int(wd)] += hours
    if candidate_shift is not None and candidate_shift.id_posicion == position_id:
        hours = float(candidate_shift.duracion_horas or 0.0)
        for wd in candidate_shift.dias_recurrencia or []:
            if 0 <= int(wd) <= 6:
                totals[int(wd)] += hours
    return totals

def _fmt_day_totals(totals):
    return ", ".join(f"{_WD[i]} {round(float(totals.get(i, 0.0)), 1)}h" for i in range(7))

def _validate_24h_position_totals(
    state,
    position_id: int,
    *,
    exclude_turn_id: int | None = None,
    candidate_shift: Turno | None = None,
    require_exact: bool = False,
) -> str | None:
    pos_map = {int(pp["id_posicion"]): _to_pos(pp) for pp in state.get("posiciones", [])}
    pos = pos_map.get(int(position_id))
    if not pos or not pos.es_24h:
        return None
    totals = _position_day_totals(
        state,
        int(position_id),
        exclude_turn_id=exclude_turn_id,
        candidate_shift=candidate_shift,
    )
    if any(v > 24.0 + 1e-6 for v in totals.values()):
        return f"La posición '{pos.nombre}' marcada 24H no puede superar 24h diarias ({_fmt_day_totals(totals)})"
    if require_exact and any(abs(v - 24.0) > 1e-6 for v in totals.values()):
        return f"La posición '{pos.nombre}' marcada 24H debe sumar exactamente 24h al día ({_fmt_day_totals(totals)})"
    return None

def _validate_24h_positions_before_generate(state, service_id: int | None = None) -> str | None:
    positions = [_to_pos(pp) for pp in state.get("posiciones", [])]
    if service_id is not None:
        positions = [pp for pp in positions if pp.id_servicio == service_id]
    for pos in positions:
        if not pos.activa or not pos.es_24h:
            continue
        err = _validate_24h_position_totals(state, pos.id_posicion, require_exact=True)
        if err:
            return err
    return None

def _normalize_24h_mode(raw: str | None) -> str:
    mode = str(raw or "8h").lower()
    if mode in {"8", "8h", "3x8", "8-8-8"}:
        return "8h"
    if mode in {"12", "12h", "2x12", "12-12"}:
        return "12h"
    if mode in {"auto", "indistinto"}:
        return "auto"
    return "8h"

def _normalize_position_temporality(raw: str | Temporalidad | None) -> Temporalidad:
    if isinstance(raw, Temporalidad):
        return raw
    mode = str(raw or Temporalidad.CONTINUO.value).lower().strip()
    if mode in {Temporalidad.TEMPORAL.value, "temp"}:
        return Temporalidad.TEMPORAL
    return Temporalidad.CONTINUO

def _position_temporal_fields(pos: Posicion):
    tmode = _normalize_position_temporality(pos.temporalidad)
    if tmode == Temporalidad.TEMPORAL:
        return tmode, pos.fecha_inicio, pos.fecha_fin
    return Temporalidad.CONTINUO, None, None

def _validate_position_temporality_payload(payload: dict, current: Posicion | None = None):
    raw_mode = payload.get("temporalidad", current.temporalidad if current else Temporalidad.CONTINUO.value)
    tmode = _normalize_position_temporality(raw_mode)
    fi_raw = payload.get("fecha_inicio", current.fecha_inicio if current else None)
    ff_raw = payload.get("fecha_fin", current.fecha_fin if current else None)
    try:
        fi = parse_date(fi_raw) if isinstance(fi_raw, str) and fi_raw else fi_raw
        ff = parse_date(ff_raw) if isinstance(ff_raw, str) and ff_raw else ff_raw
    except Exception:
        return None, None, None, "Formato de fecha inválido en la posición temporal"
    if tmode == Temporalidad.TEMPORAL:
        if not fi or not ff:
            return None, None, None, "Para posiciones temporales debes indicar fecha de inicio y fecha de fin"
        if fi > ff:
            return None, None, None, "La fecha de inicio no puede ser posterior a la fecha de fin"
        return tmode, fi, ff, None
    return Temporalidad.CONTINUO, None, None, None

def _apply_position_temporality_to_turns(data, position_id: int):
    positions = {int(p["id_posicion"]): _to_pos(p) for p in data.get("posiciones", [])}
    pos = positions.get(int(position_id))
    if not pos:
        return
    tmode, fi, ff = _position_temporal_fields(pos)
    turnos = [_to_turno(x) for x in data.get("turnos", [])]
    changed = False
    for t in turnos:
        if int(t.id_posicion) != int(position_id):
            continue
        if t.temporalidad != tmode or t.fecha_inicio != fi or t.fecha_fin != ff:
            t.temporalidad = tmode
            t.fecha_inicio = fi
            t.fecha_fin = ff
            changed = True
    if changed:
        data["turnos"] = [asdict(t) for t in turnos]

def _template_turn_specs_for_mode(mode: str):
    nm = _normalize_24h_mode(mode)
    if nm == "12h":
        return [
            ("Día 12h", time(6, 0), time(18, 0)),
            ("Noche 12h", time(18, 0), time(6, 0)),
        ]
    return [
        ("Mañana", time(6, 0), time(14, 0)),
        ("Tarde", time(14, 0), time(22, 0)),
        ("Noche", time(22, 0), time(6, 0)),
    ]

def _position_turns_match_mode(turns: list[Turno], mode: str) -> bool:
    expected = _template_turn_specs_for_mode(mode)
    if len(turns) != len(expected):
        return False
    got = sorted((t.hora_inicio, t.hora_fin, round(float(t.duracion_horas or 0.0), 1)) for t in turns)
    exp = []
    ss = ShiftService()
    for _, hi, hf in expected:
        tt = ss.enrich_shift(Turno(0, 0, "tmp", hi, hf, 0, [0, 1, 2, 3, 4, 5, 6], Temporalidad.CONTINUO))
        exp.append((hi, hf, round(float(tt.duracion_horas or 0.0), 1)))
    return got == sorted(exp)

def _replace_position_turns_with_mode(data, position_id: int, mode: str):
    mode = _normalize_24h_mode(mode)
    positions = {int(p["id_posicion"]): _to_pos(p) for p in data.get("posiciones", [])}
    pos = positions.get(int(position_id))
    tmode, fi, ff = _position_temporal_fields(pos) if pos else (Temporalidad.CONTINUO, None, None)
    all_turns = [_to_turno(x) for x in data.get("turnos", [])]
    keep = [t for t in all_turns if int(t.id_posicion) != int(position_id)]
    next_id = max((int(t.id_turno) for t in keep), default=0) + 1
    ss = ShiftService()
    for name, hi, hf in _template_turn_specs_for_mode(mode):
        tt = ss.enrich_shift(Turno(
            next_id,
            int(position_id),
            name,
            hi,
            hf,
            0,
            [0, 1, 2, 3, 4, 5, 6],
            tmode,
            fi,
            ff,
        ))
        keep.append(tt)
        next_id += 1
    data["turnos"] = [asdict(t) for t in keep]

def _service_staff_count(data, service_id: int) -> int:
    employees = [_to_emp(x) for x in data.get("empleados", [])]
    active = [e for e in employees if e.activo]
    by_service = _service_employee_map(data.get("servicios", []), active, data.get("asignaciones_servicio", []))
    return len(by_service.get(int(service_id), set()))

def _sync_24h_turn_templates(data, target_service_id: int | None = None, allow_auto_switch: bool = False) -> bool:
    positions = [_to_pos(x) for x in data.get("posiciones", [])]
    all_turns = [_to_turno(x) for x in data.get("turnos", [])]
    changed = False
    for pos in positions:
        if not pos.activa or not pos.es_24h:
            continue
        if target_service_id is not None and int(pos.id_servicio) != int(target_service_id):
            continue
        desired = _normalize_24h_mode(pos.modo_24h)
        if desired == "auto":
            if not allow_auto_switch:
                desired = "8h"
            else:
                desired = "12h" if _service_staff_count(data, pos.id_servicio) <= 2 else "8h"
        current = [t for t in all_turns if int(t.id_posicion) == int(pos.id_posicion)]
        if _position_turns_match_mode(current, desired):
            continue
        _replace_position_turns_with_mode(data, pos.id_posicion, desired)
        all_turns = [_to_turno(x) for x in data.get("turnos", [])]
        changed = True
    return changed

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
    return AssignmentService.service_employee_map(services, employees, asig_srv or [])

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

def _schedule_matches_month(schedule, start: date, days: int) -> bool:
    return bool(
        schedule
        and schedule.get("dates")
        and schedule["dates"][0] == str(start)
        and len(schedule.get("dates", [])) == days
    )

def _work_hours_from_schedule(schedule, exclude_service_id: int | None = None):
    work_hours = {}
    seen = set()
    for sk, sd in schedule.get("grids", {}).items():
        sid = int(sk)
        if exclude_service_id is not None and sid == exclude_service_id:
            continue
        for ek, ed in sd.get("employees", {}).items():
            eid = _row_employee_id(ek, ed)
            if eid is None:
                continue
            for ds, cell in ed.get("days", {}).items():
                if cell.get("es_off") or cell.get("es_restriccion"):
                    continue
                key = (eid, ds)
                if key in seen:
                    continue
                seen.add(key)
                work_hours[eid] = work_hours.get(eid, 0.0) + float(cell.get("horas", 0.0) or 0.0)
    return work_hours

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
            eid = _row_employee_id(ek, ed)
            if eid is None:
                continue
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

def _recompute_schedule_shortages(schedule, state):
    dates = schedule.get("dates", [])
    if not dates:
        return schedule
    start = parse_date(dates[0])
    days = len(dates)
    shifts = [_to_turno(x) for x in state["turnos"]]
    requirements = DemandService().build_requirements(shifts, start, days)
    pos_srv = {int(pp["id_posicion"]): int(pp["id_servicio"]) for pp in state["posiciones"]}
    shift_by_id = {s.id_turno: s for s in shifts}
    service_shift_ids = {}
    for sh in shifts:
        service_shift_ids.setdefault(pos_srv.get(sh.id_posicion, 1), set()).add(sh.id_turno)

    grids = schedule.get("grids", {})
    total_shortage = 0
    shortage_by_service = {}
    shortage_by_position = {}
    for sid, sh_ids in service_shift_ids.items():
        sk = str(sid)
        sd = grids.get(sk)
        if not sd:
            continue
        srv_dark = {}
        srv_dark_by_pos = {}
        for (d, tid), needed in requirements.items():
            if tid not in sh_ids:
                continue
            sh = shift_by_id.get(tid)
            if not sh:
                continue
            covered = 0
            for _, ed in sd.get("employees", {}).items():
                cell = ed.get("days", {}).get(str(d))
                if _cell_matches_shift(cell, ed, sh):
                    covered += 1
            short = max(0, needed - covered)
            if short > 0:
                total_shortage += short
                shortage_by_service[sk] = shortage_by_service.get(sk, 0) + int(short)
                pkey = str(int(sh.id_posicion))
                shortage_by_position[pkey] = shortage_by_position.get(pkey, 0) + int(short)
                ds = str(d)
                srv_dark[ds] = round(srv_dark.get(ds, 0.0) + short * sh.duracion_horas, 1)
                pos_dark = srv_dark_by_pos.setdefault(pkey, {})
                pos_dark[ds] = round(pos_dark.get(ds, 0.0) + short * sh.duracion_horas, 1)
        if srv_dark:
            sd["dark_post"] = srv_dark
        else:
            sd.pop("dark_post", None)
        if srv_dark_by_pos:
            sd["dark_post_by_position"] = srv_dark_by_pos
        else:
            sd.pop("dark_post_by_position", None)

    schedule.setdefault("summary", {})
    schedule["summary"]["faltantes"] = int(total_shortage)
    schedule["summary"]["faltantes_by_service"] = shortage_by_service
    schedule["summary"]["faltantes_by_position"] = shortage_by_position
    return schedule

def _build_schedule_edit_proposal(
    schedule,
    state,
    service_id: int,
    employee_id: int,
    on_date: str,
    turno: str,
    horas: float,
    *,
    row_key: str | None = None,
    row_position_id: int | None = None,
    turn_id: int | None = None,
):
    sk = str(service_id)
    rk, row = _find_schedule_row(schedule, service_id, employee_id, row_key=row_key, position_id=row_position_id)
    if not row:
        return None, None, "Celda no encontrada"

    sh = None
    if turno != OFF_SHIFT:
        sh = _shift_by_id(state, turn_id)
        if sh is None:
            match_pos = row_position_id if row_position_id is not None else _row_position_id(row)
            sh = _shift_by_label_for_position(state, turno, match_pos)
        if sh is None:
            return None, None, "Turno no encontrado"
        row_pos = _row_position_id(row)
        if row_pos not in (None, 0) and int(sh.id_posicion) != int(row_pos):
            return None, None, "Solo puedes asignar turnos de la posición de esta fila"

    proposed = {
        "turno": OFF_SHIFT if turno == OFF_SHIFT else (sh.sigla_turno or sh.nombre_turno),
        "horas": float(horas),
        "es_off": turno == OFF_SHIFT,
    }
    if not proposed["es_off"] and sh is not None:
        proposed["id_turno"] = int(sh.id_turno)
        proposed["id_posicion"] = int(sh.id_posicion)

    restrictions = [_to_re(x) for x in state["restricciones_empleado"]]
    catalog = {int(k): _to_rest(v) for k, v in state["catalogo"].items()}
    if sh and sh.cruza_medianoche:
        vac_days = _vacation_days(restrictions, catalog)
        edit_date = parse_date(on_date)
        if (employee_id, edit_date + _dt.timedelta(days=1)) in vac_days:
            return None, None, "No se puede asignar un turno que termine después de las 23:59 si al día siguiente empiezan vacaciones"

    worked_same_day = 0
    total_work = 0.0
    for sid, sd in schedule.get("grids", {}).items():
        for rk2, ed in sd.get("employees", {}).items():
            if _row_employee_id(rk2, ed) != int(employee_id):
                continue
            for ds, existing in ed.get("days", {}).items():
                cell = proposed if sid == sk and rk2 == rk and ds == on_date else existing
                if not cell or cell.get("es_off") or cell.get("es_restriccion"):
                    continue
                if ds == on_date:
                    worked_same_day += 1
                total_work += float(cell.get("horas", 0.0) or 0.0)

    if worked_same_day > 1:
        return None, None, "No se puede asignar al mismo empleado en dos servicios el mismo día"

    emp = next((x for x in (_to_emp(e) for e in state["empleados"]) if x.id_empleado == employee_id), None)
    if not emp or emp.horas_maximas is None:
        return rk, proposed, None

    dates_set = {parse_date(ds) for ds in schedule.get("dates", [])}
    restriction_hours = _restriction_hours_by_employee(restrictions, catalog, dates_set).get(employee_id, 0.0)
    if total_work + restriction_hours > emp.horas_maximas + 1e-6:
        return None, None, f"El empleado supera sus horas máximas mensuales ({emp.horas_maximas}h)"
    return rk, proposed, None

def _collect_shift_cell_assignments(schedule: dict, service_id: int, on_date: str, shift: Turno, *, position_id: int | None = None):
    out = []
    sk = str(service_id)
    grid = schedule.get("grids", {}).get(sk, {})
    for rk, row in grid.get("employees", {}).items():
        pid = _row_position_id(row)
        if position_id is not None and pid != int(position_id):
            continue
        cell = row.get("days", {}).get(on_date)
        if _cell_matches_shift(cell, row, shift):
            out.append({
                "id_empleado": _row_employee_id(rk, row),
                "nombre": row.get("nombre", ""),
                "row_key": rk,
                "id_posicion": pid,
            })
    out.sort(key=lambda x: (str(x.get("nombre") or ""), int(x.get("id_empleado") or 0)))
    return out

def _candidate_rows_for_shift(schedule: dict, state: dict, service_id: int, on_date: str, position_id: int, shift: Turno):
    employees = [_to_emp(x) for x in state.get("empleados", [])]
    active_employees = [e for e in employees if e.activo]
    service_map = _service_employee_map(state.get("servicios", []), active_employees, state.get("asignaciones_servicio", []))
    allowed_ids = set(service_map.get(int(service_id), set()))
    if not allowed_ids:
        allowed_ids = {e.id_empleado for e in active_employees}

    by_id = {e.id_empleado: e for e in active_employees}
    shift_label = shift.sigla_turno or shift.nombre_turno
    shift_hours = float(shift.duracion_horas or 0.0)
    current = _collect_shift_cell_assignments(schedule, service_id, on_date, shift, position_id=position_id)
    current_ids = {int(x["id_empleado"]) for x in current if x.get("id_empleado") is not None}

    out = []
    for eid in sorted(allowed_ids):
        emp = by_id.get(eid)
        if not emp:
            continue
        rk, row = _find_schedule_row(schedule, int(service_id), int(eid), position_id=int(position_id))
        if not row:
            out.append({
                "id_empleado": int(eid),
                "nombre": emp.nombre,
                "row_key": "",
                "disponible": False,
                "motivo": "No tiene fila para esta posición en el cuadrante",
                "ya_asignado": int(eid) in current_ids,
            })
            continue
        _, _, error = _build_schedule_edit_proposal(
            schedule,
            state,
            int(service_id),
            int(eid),
            on_date,
            shift_label,
            shift_hours,
            row_key=rk,
            row_position_id=int(position_id),
            turn_id=int(shift.id_turno),
        )
        out.append({
            "id_empleado": int(eid),
            "nombre": emp.nombre,
            "row_key": rk,
            "disponible": error is None,
            "motivo": "" if error is None else error,
            "ya_asignado": int(eid) in current_ids,
        })
    out.sort(key=lambda x: (not bool(x.get("disponible")), str(x.get("nombre") or "")))
    return out, current

def _schedule_candidates_response(schedule: dict, state: dict, payload: dict):
    try:
        service_id = int(payload["id_servicio"])
        on_date = str(payload["fecha"])
    except (TypeError, ValueError, KeyError):
        return None, "Parámetros inválidos"

    try:
        parse_date(on_date)
    except Exception:
        return None, "Fecha inválida"

    position_id = payload.get("id_posicion")
    if position_id in (None, "", 0, "0"):
        position_id = None
    else:
        try:
            position_id = int(position_id)
        except (TypeError, ValueError):
            return None, "Posición inválida"

    turn_id = payload.get("id_turno")
    if turn_id in (None, "", "null"):
        turn_id = None
    else:
        try:
            turn_id = int(turn_id)
        except (TypeError, ValueError):
            return None, "Turno inválido"

    shift = _shift_by_id(state, turn_id)
    if shift is None:
        turno_label = str(payload.get("turno") or "").strip()
        if not turno_label:
            return None, "Turno inválido"
        shift = _shift_by_label_for_position(state, turno_label, position_id)
    if shift is None:
        return None, "Turno no encontrado"

    target_position = int(position_id if position_id is not None else shift.id_posicion)
    if int(shift.id_posicion) != target_position:
        return None, "El turno no pertenece a la posición indicada"

    candidates, current = _candidate_rows_for_shift(
        schedule,
        state,
        int(service_id),
        on_date,
        int(target_position),
        shift,
    )
    return {
        "ok": True,
        "id_servicio": int(service_id),
        "id_posicion": int(target_position),
        "id_turno": int(shift.id_turno),
        "turno": shift.sigla_turno or shift.nombre_turno,
        "horas": float(shift.duracion_horas or 0.0),
        "fecha": on_date,
        "current": current,
        "candidates": candidates,
    }, None

def _generate_schedule_result(
    data,
    start: date,
    days: int,
    max_time: int,
    target_service_id: int | None = None,
    base_schedule: dict | None = None,
):
    employees = [_to_emp(x) for x in data["empleados"]]
    active_employees = [e for e in employees if e.activo]
    shifts = [_to_turno(x) for x in data["turnos"]]
    restrictions = [_to_re(x) for x in data["restricciones_empleado"]]
    catalog = {int(k): _to_rest(v) for k, v in data["catalogo"].items()}
    asig_srv = data.get("asignaciones_servicio", [])
    concs = data.get("conciliaciones", [])
    pos_srv = {pp["id_posicion"]: pp["id_servicio"] for pp in data["posiciones"]}
    requirements = DemandService().build_requirements(shifts, start, days)

    if target_service_id is not None:
        shifts = [sh for sh in shifts if pos_srv.get(sh.id_posicion, 1) == target_service_id]
        allowed_emp_ids = _service_employee_map(data["servicios"], active_employees, asig_srv).get(target_service_id, set())
        # Fallback de robustez para generación por servicio:
        # si no hay plantilla explícita asignada, permitimos activos para no devolver cuadrante vacío.
        if not allowed_emp_ids:
            allowed_emp_ids = {e.id_empleado for e in active_employees}
        active_employees = [e for e in active_employees if e.id_empleado in allowed_emp_ids]
        shift_ids = {s.id_turno for s in shifts}
        requirements = {(d, tid): needed for (d, tid), needed in requirements.items() if tid in shift_ids}

    service_employee_ids = _service_employee_map(data["servicios"], active_employees, asig_srv)
    if target_service_id is not None:
        sid_set = set(service_employee_ids.get(target_service_id, set()))
        if not sid_set:
            sid_set = {e.id_empleado for e in active_employees}
        service_employee_ids = {target_service_id: sid_set}
    allowed_shift_ids = _allowed_shift_ids_by_employee(service_employee_ids, shifts, pos_srv, active_employees)
    dates = daterange(start, days)
    dates_set = set(dates)
    restriction_hours = _restriction_hours_by_employee(restrictions, catalog, dates_set)
    preassigned_hours = dict(restriction_hours)
    if target_service_id is not None and base_schedule and _schedule_matches_month(base_schedule, start, days):
        carried = _work_hours_from_schedule(base_schedule, exclude_service_id=target_service_id)
        for eid, hrs in carried.items():
            preassigned_hours[eid] = preassigned_hours.get(eid, 0.0) + hrs
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
        preassigned_hours=preassigned_hours,
    )

    shift_by_id = {s.id_turno: s for s in shifts}
    shift_by_label_pos = {(s.sigla_turno or s.nombre_turno, int(s.id_posicion)): s for s in shifts}
    srv_names = {s["id_servicio"]: s["nombre"] for s in data["servicios"]}
    pos_names = {int(pp["id_posicion"]): pp["nombre"] for pp in data["posiciones"]}
    service_shift_ids = {}
    service_positions = {}
    for sh in shifts:
        sid = int(pos_srv.get(sh.id_posicion, 1))
        service_shift_ids.setdefault(sid, set()).add(sh.id_turno)
        service_positions.setdefault(sid, set()).add(int(sh.id_posicion))

    emp_map = {e.id_empleado: e for e in active_employees}
    grids = {}

    def ensure_row(service_id: int, employee_id: int, position_id: int):
        sk = str(service_id)
        pid = int(position_id or 0)
        rk = f"{int(employee_id)}:{pid}"
        if sk not in grids:
            grids[sk] = {"nombre": srv_names.get(service_id, "Servicio"), "employees": {}}
        if rk not in grids[sk]["employees"]:
            days_map = {}
            for d in dates:
                ds = str(d)
                base = {"turno": OFF_SHIFT, "horas": 0.0, "es_off": True}
                if employee_id in restr_overlay and ds in restr_overlay[employee_id]:
                    base = dict(restr_overlay[employee_id][ds])
                days_map[ds] = base
            grids[sk]["employees"][rk] = {
                "id_empleado": int(employee_id),
                "id_posicion": pid,
                "nombre": emp_map[employee_id].nombre,
                "posicion": pos_names.get(pid, "") if pid else "",
                "days": days_map,
            }
        return grids[sk]["employees"][rk], rk

    for srv in data["servicios"]:
        sid = int(srv["id_servicio"])
        if sid not in service_shift_ids:
            continue
        grids[str(sid)] = {"nombre": srv_names.get(sid, "Servicio"), "employees": {}}
        service_pos_ids = sorted(service_positions.get(sid, set()))
        for eid in sorted(service_employee_ids.get(sid, set())):
            if eid not in emp_map:
                continue
            if not service_pos_ids:
                ensure_row(sid, eid, 0)
                continue
            for pid in service_pos_ids:
                ensure_row(sid, eid, pid)

    for a in plan:
        if a.es_off or a.id_empleado not in emp_map:
            continue
        sid = int(pos_srv.get(a.id_posicion, a.id_servicio or 1))
        row, _ = ensure_row(sid, a.id_empleado, int(a.id_posicion))
        sh = shift_by_label_pos.get((a.turno_asignado, int(a.id_posicion)))
        if sh is None:
            sh = _shift_by_label_for_position(data, a.turno_asignado, int(a.id_posicion))
        row["days"][str(a.fecha)] = {
            "turno": a.turno_asignado,
            "horas": a.horas,
            "es_off": False,
            "id_posicion": int(a.id_posicion),
            "id_turno": int(sh.id_turno) if sh else None,
        }

    total_shortage = 0
    shortage_by_service = {}
    shortage_by_position = {}
    for sid, sh_ids in service_shift_ids.items():
        sk = str(sid)
        if sk not in grids:
            grids[sk] = {"nombre": srv_names.get(sid, "Servicio"), "employees": {}}
        srv_dark = {}
        srv_dark_by_pos = {}
        for (d, tid), needed in requirements.items():
            if tid not in sh_ids:
                continue
            sh = shift_by_id.get(tid)
            if not sh:
                continue
            covered = 0
            for _, ed in grids[sk]["employees"].items():
                cell = ed["days"].get(str(d))
                if _cell_matches_shift(cell, ed, sh):
                    covered += 1
            short = max(0, needed - covered)
            if short > 0:
                total_shortage += short
                shortage_by_service[sk] = shortage_by_service.get(sk, 0) + int(short)
                pkey = str(int(sh.id_posicion))
                shortage_by_position[pkey] = shortage_by_position.get(pkey, 0) + int(short)
                ds = str(d)
                srv_dark[ds] = round(srv_dark.get(ds, 0.0) + short * sh.duracion_horas, 1)
                pos_dark = srv_dark_by_pos.setdefault(pkey, {})
                pos_dark[ds] = round(pos_dark.get(ds, 0.0) + short * sh.duracion_horas, 1)
        if srv_dark:
            grids[sk]["dark_post"] = srv_dark
        else:
            grids[sk].pop("dark_post", None)
        if srv_dark_by_pos:
            grids[sk]["dark_post_by_position"] = srv_dark_by_pos
        else:
            grids[sk].pop("dark_post_by_position", None)

    return {
        "grids": grids,
        "dates": [str(d) for d in dates],
        "hours": _build_hours_summary(active_employees, work_hours, restriction_hours),
        "summary": {
            "faltantes": int(total_shortage),
            "faltantes_by_service": shortage_by_service,
            "faltantes_by_position": shortage_by_position,
            "total": len(plan),
        },
    }

# ── Routes ──────────────────────────────────────────────────────────
def _parse_schedule_edit_payload(payload: dict):
    sid = int(payload["id_servicio"])
    eid = int(payload["id_empleado"])
    on_date = payload["fecha"]
    turno = payload["turno"]
    horas = float(payload.get("horas", 0))
    row_key = payload.get("row_key")
    row_position_id = payload.get("id_posicion")
    turn_id = payload.get("id_turno")
    if row_position_id in ("", None):
        row_position_id = None
    else:
        row_position_id = int(row_position_id)
    if turn_id in ("", None):
        turn_id = None
    else:
        turn_id = int(turn_id)
    return sid, eid, on_date, turno, horas, row_key, row_position_id, turn_id

def _apply_schedule_cell_edit(schedule: dict, state: dict, payload: dict):
    sid, eid, on_date, turno, horas, row_key, row_position_id, turn_id = _parse_schedule_edit_payload(payload)
    rk, cell, error = _build_schedule_edit_proposal(
        schedule,
        state,
        sid,
        eid,
        on_date,
        turno,
        horas,
        row_key=row_key,
        row_position_id=row_position_id,
        turn_id=turn_id,
    )
    if error:
        return None, error
    sk = str(sid)
    if sk not in schedule.get("grids", {}) or rk not in schedule["grids"][sk].get("employees", {}):
        return None, "Celda no encontrada"
    schedule["grids"][sk]["employees"][rk]["days"][on_date] = cell
    schedule = _recompute_schedule_shortages(_recompute_schedule_hours(schedule, state), state)
    return schedule, None

@app.route("/")
def index():
    resp = send_from_directory("static", "index.html")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp
@app.route("/static/<path:p>")
def static_f(p):
    resp = send_from_directory("static", p)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

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
    data = _load()
    services = [Servicio(**x) for x in data["servicios"]]
    if not any(s.id_servicio == sid for s in services):
        return jsonify({"ok":False,"error":"Servicio no encontrado"}),404

    data["servicios"] = [asdict(s) for s in services if s.id_servicio != sid]
    removed_positions = {
        int(p["id_posicion"])
        for p in data.get("posiciones", [])
        if int(p["id_servicio"]) == sid
    }
    data["posiciones"] = [
        p for p in data.get("posiciones", [])
        if int(p["id_servicio"]) != sid
    ]
    data["turnos"] = [
        t for t in data.get("turnos", [])
        if int(t.get("id_posicion", 0)) not in removed_positions
    ]
    data["asignaciones_servicio"] = _normalize_assignments_rows([
        a for a in data.get("asignaciones_servicio", [])
        if int(a.get("id_servicio", 0)) != sid
    ])
    _save(data)

    sch = DB.load_json(SCH, None)
    if isinstance(sch, dict):
        sk = str(sid)
        if isinstance(sch.get("grids"), dict):
            sch["grids"].pop(sk, None)
            for srv in sch["grids"].values():
                if not isinstance(srv, dict):
                    continue
                dpbp = srv.get("dark_post_by_position")
                if isinstance(dpbp, dict):
                    for pid in removed_positions:
                        dpbp.pop(str(pid), None)
                    if not dpbp:
                        srv.pop("dark_post_by_position", None)
        summary = sch.get("summary")
        if isinstance(summary, dict):
            if isinstance(summary.get("faltantes_by_service"), dict):
                summary["faltantes_by_service"].pop(sk, None)
            if isinstance(summary.get("faltantes_by_position"), dict):
                for pid in removed_positions:
                    summary["faltantes_by_position"].pop(str(pid), None)
        sch = _recompute_schedule_shortages(_recompute_schedule_hours(sch, data), data)
        DB.save_json(SCH, sch)

    return jsonify({"ok":True,"servicios":data["servicios"]})

# CRUD Posiciones
@app.route("/api/posiciones",methods=["POST"])
def add_pos():
    p=request.json or {};data=_load();items=[_to_pos(x) for x in data["posiciones"]]
    nid=max((x.id_posicion for x in items),default=0)+1
    es24 = bool(p.get("es_24h", False))
    mode = _normalize_24h_mode(p.get("modo_24h"))
    tmode, fi, ff, terr = _validate_position_temporality_payload(p, None)
    if terr:
        return jsonify({"ok":False,"error":terr}),400
    items.append(Posicion(
        nid,
        int(p["id_servicio"]),
        p["nombre"],
        True,
        es24,
        mode,
        tmode,
        fi,
        ff,
    ))
    data["posiciones"]=[asdict(x) for x in items]
    if es24:
        _replace_position_turns_with_mode(data, nid, "8h" if mode == "auto" else mode)
    _apply_position_temporality_to_turns(data, nid)
    _save(data);return jsonify({"ok":True,"posiciones":data["posiciones"],"turnos":data.get("turnos",[])})
@app.route("/api/posiciones/<int:pid>",methods=["PUT"])
def edit_pos(pid):
    p=request.json or {};data=_load();items=[_to_pos(x) for x in data["posiciones"]]
    target = None
    for x in items:
        if x.id_posicion==pid:
            target = x
            x.nombre=p.get("nombre",x.nombre);x.activa=p.get("activa",x.activa)
            if "es_24h" in p:
                x.es_24h = bool(p.get("es_24h"))
            if "modo_24h" in p:
                x.modo_24h = _normalize_24h_mode(p.get("modo_24h"))
            tmode, fi, ff, terr = _validate_position_temporality_payload(p, x)
            if terr:
                return jsonify({"ok":False,"error":terr}),400
            x.temporalidad = tmode
            x.fecha_inicio = fi
            x.fecha_fin = ff
    data["posiciones"]=[asdict(x) for x in items]
    if target and target.es_24h:
        _replace_position_turns_with_mode(data, pid, "8h" if target.modo_24h == "auto" else target.modo_24h)
    _apply_position_temporality_to_turns(data, pid)
    err = _validate_24h_position_totals(data, pid, require_exact=False)
    if err:
        return jsonify({"ok":False,"error":err}),400
    _save(data);return jsonify({"ok":True,"posiciones":data["posiciones"],"turnos":data.get("turnos",[])})
@app.route("/api/posiciones/<int:pid>",methods=["DELETE"])
def del_pos(pid):
    data=_load();items=[_to_pos(x) for x in data["posiciones"]]
    for x in items:
        if x.id_posicion==pid: x.activa=False
    data["posiciones"]=[asdict(x) for x in items];_save(data);return jsonify({"ok":True,"posiciones":data["posiciones"]})

# CRUD Turnos
@app.route("/api/turnos",methods=["POST"])
def add_trn():
    p=request.json or {};data=_load();turnos=[_to_turno(x) for x in data["turnos"]]
    pos_map = {int(pp["id_posicion"]): _to_pos(pp) for pp in data.get("posiciones", [])}
    pos = pos_map.get(int(p["id_posicion"]))
    tmode, fi, ff = _position_temporal_fields(pos) if pos else (Temporalidad.CONTINUO, None, None)
    nid=max((t.id_turno for t in turnos),default=0)+1
    dias=[int(d) for d in p.get("dias_recurrencia",[0,1,2,3,4,5,6])]
    t=Turno(nid,int(p["id_posicion"]),p["nombre_turno"],parse_time(p["hora_inicio"]),parse_time(p["hora_fin"]),0,dias,
            tmode,fi,ff)
    t=ShiftService().enrich_shift(t)
    err = _validate_24h_position_totals(data, t.id_posicion, candidate_shift=t, require_exact=False)
    if err:
        return jsonify({"ok":False,"error":err}),400
    turnos.append(t)
    data["turnos"]=[asdict(x) for x in turnos];_save(data);return jsonify({"ok":True,"turnos":data["turnos"]})
@app.route("/api/turnos/<int:tid>",methods=["PUT"])
def edit_trn(tid):
    p=request.json or {};data=_load();turnos=[_to_turno(x) for x in data["turnos"]];ss=ShiftService()
    pos_map = {int(pp["id_posicion"]): _to_pos(pp) for pp in data.get("posiciones", [])}
    target = next((x for x in turnos if x.id_turno == tid), None)
    if not target:
        return jsonify({"ok":False,"error":"Turno no encontrado"}),404
    if "id_posicion" in p:
        target.id_posicion = int(p["id_posicion"])
    target.nombre_turno=p.get("nombre_turno",target.nombre_turno)
    if p.get("hora_inicio"): target.hora_inicio=parse_time(p["hora_inicio"])
    if p.get("hora_fin"): target.hora_fin=parse_time(p["hora_fin"])
    if "dias_recurrencia" in p: target.dias_recurrencia=[int(d) for d in p["dias_recurrencia"]]
    pos = pos_map.get(int(target.id_posicion))
    tmode, fi, ff = _position_temporal_fields(pos) if pos else (Temporalidad.CONTINUO, None, None)
    target.temporalidad = tmode
    target.fecha_inicio = fi
    target.fecha_fin = ff
    ss.enrich_shift(target)
    err = _validate_24h_position_totals(
        data,
        target.id_posicion,
        exclude_turn_id=tid,
        candidate_shift=target,
        require_exact=False,
    )
    if err:
        return jsonify({"ok":False,"error":err}),400
    for t in turnos:
        if t.id_turno == tid:
            t.id_posicion = target.id_posicion
            t.nombre_turno = target.nombre_turno
            t.hora_inicio = target.hora_inicio
            t.hora_fin = target.hora_fin
            t.dias_recurrencia = target.dias_recurrencia
            t.duracion_horas = target.duracion_horas
            t.sigla_turno = target.sigla_turno
            t.cruza_medianoche = target.cruza_medianoche
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
    if fi > ff:
        return jsonify({"ok":False,"error":"La fecha inicio no puede ser mayor que la fecha fin"}),400
    add_rows = rs.expand_range_to_daily(
        eid, rid, fi, ff,
        parse_time(p["hora_ini"]) if p.get("hora_ini") else None,
        parse_time(p["hora_fin"]) if p.get("hora_fin") else None,
        p.get("observaciones"),
    )
    existing_dates={r.fecha for r in rows if r.id_empleado==eid and r.id_restriccion==rid}
    new_dates={r.fecha for r in add_rows}
    if rid in cat and cat[rid].tipo_restriccion!=TipoRestriccion.DIA_LIBRE and cat[rid].dias:
        final_days=len(existing_dates.union(new_dates))
        if final_days>cat[rid].dias:
            return jsonify({"ok":False,"error":f"Límite excedido: {cat[rid].desc_restriccion} permite {cat[rid].dias} días, quedaría en {final_days}"}),400
    by_key={(r.id_empleado,r.id_restriccion,r.fecha):r for r in rows}
    for rr in add_rows:
        by_key[(rr.id_empleado,rr.id_restriccion,rr.fecha)]=rr
    merged=sorted(by_key.values(), key=lambda r: (int(r.id_empleado), r.fecha, int(r.id_restriccion)))
    data["restricciones_empleado"]=[asdict(r) for r in merged];_save(data);return jsonify({"ok":True,"restricciones":data["restricciones_empleado"]})
@app.route("/api/restricciones/delete",methods=["POST"])
def del_rest():
    p=request.json or {};data=_load();target=parse_date(p["fecha"]);eid=int(p["id_empleado"]);rid=int(p["id_restriccion"])
    rows=[_to_re(x) for x in data["restricciones_empleado"]]
    rows=[r for r in rows if not(r.id_empleado==eid and r.id_restriccion==rid and r.fecha==target)]
    data["restricciones_empleado"]=_normalize_restriction_rows(rows);_save(data);return jsonify({"ok":True,"restricciones":data["restricciones_empleado"]})

# Asignaciones servicio-empleado
@app.route("/api/asignaciones_servicio")
def get_asig(): return jsonify(_normalize_assignments_rows(_load().get("asignaciones_servicio",[])))
@app.route("/api/asignaciones_servicio/toggle",methods=["POST"])
def toggle_asig():
    p = request.json or {}
    try:
        eid = int(p["id_empleado"])
        sid = int(p["id_servicio"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"ok": False, "error": "Parámetros de asignación inválidos"}), 400
    data = _load()
    valid_employees = {int(e["id_empleado"]) for e in data.get("empleados", []) if bool(e.get("activo", False))}
    valid_services = {int(s["id_servicio"]) for s in data.get("servicios", []) if bool(s.get("activo", False))}
    if eid not in valid_employees:
        return jsonify({"ok": False, "error": "Empleado no válido o inactivo"}), 400
    if sid not in valid_services:
        return jsonify({"ok": False, "error": "Servicio no válido o inactivo"}), 400
    data["asignaciones_servicio"] = AssignmentService.toggle(
        data.get("asignaciones_servicio", []),
        eid,
        sid,
        is_primary=bool(p.get("es_principal", False)),
    )
    _save(data)
    return jsonify({"ok": True, "asignaciones_servicio": data["asignaciones_servicio"]})

# endpoint deshabilitado
def set_asig_service():
    p = request.json or {}
    try:
        sid = int(p["id_servicio"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"ok": False, "error": "Servicio no válido"}), 400

    incoming = p.get("empleados", [])
    if not isinstance(incoming, list):
        return jsonify({"ok": False, "error": "La lista de empleados no es válida"}), 400
    try:
        employee_ids = sorted({int(x) for x in incoming})
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "La lista de empleados contiene valores no válidos"}), 400

    data = _load()
    if not any(int(s["id_servicio"]) == sid for s in data.get("servicios", [])):
        return jsonify({"ok": False, "error": "Servicio no encontrado"}), 404

    valid_active_employees = {int(e["id_empleado"]) for e in data.get("empleados", []) if bool(e.get("activo", False))}
    invalid = [eid for eid in employee_ids if eid not in valid_active_employees]
    if invalid:
        return jsonify({"ok": False, "error": "Hay empleados inválidos o inactivos en la selección"}), 400

    principal_raw = p.get("id_principal")
    principal_id = None
    if principal_raw not in (None, ""):
        try:
            principal_id = int(principal_raw)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Empleado principal no válido"}), 400
        if principal_id not in employee_ids:
            return jsonify({"ok": False, "error": "El empleado principal debe estar seleccionado"}), 400
    elif employee_ids:
        principal_id = employee_ids[0]

    base_rows = [a for a in _normalize_assignments_rows(data.get("asignaciones_servicio", [])) if int(a["id_servicio"]) != sid]
    for eid in employee_ids:
        base_rows.append({
            "id_empleado": eid,
            "id_servicio": sid,
            "es_principal": bool(principal_id is not None and eid == principal_id),
        })
    data["asignaciones_servicio"] = _normalize_assignments_rows(base_rows)
    _save(data)
    return jsonify({"ok": True, "asignaciones_servicio": data["asignaciones_servicio"]})

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
    sid_raw = p.get("id_servicio")
    sid = None
    if sid_raw not in (None, ""):
        try:
            sid = int(sid_raw)
        except (TypeError, ValueError):
            return jsonify({"ok":False,"error":"Servicio no válido"}),400
        if not any(int(s["id_servicio"]) == sid for s in data.get("servicios", [])):
            return jsonify({"ok":False,"error":"Servicio no encontrado"}),400
    if _sync_24h_turn_templates(data, sid, allow_auto_switch=True):
        _save(data)
    error=_validate_month_request(start, days)
    if error: return jsonify({"ok":False,"error":error}),400
    cov_err = _validate_24h_positions_before_generate(data, sid)
    if cov_err:
        return jsonify({"ok":False,"error":cov_err}),400
    existing = DB.load_json(SCH, None)
    try:
        partial=_generate_schedule_result(
            data,start,days,max(1, int(p.get("max_time") or 30)),
            target_service_id=sid,
            base_schedule=existing,
        )
    except RuntimeError as exc:
        return jsonify({"ok":False,"error":str(exc)}),500
    if sid is not None and _schedule_matches_month(existing, start, days):
        result = json.loads(json.dumps(existing))
        result.setdefault("grids", {})
        sk = str(sid)
        if sk in partial.get("grids", {}):
            result["grids"][sk] = partial["grids"][sk]
        else:
            result["grids"].pop(sk, None)
        result["dates"] = partial.get("dates", result.get("dates", []))
        result = _recompute_schedule_hours(result, data)
        result = _recompute_schedule_shortages(result, data)
    elif sid is not None:
        result = _recompute_schedule_shortages(_recompute_schedule_hours(partial, data), data)
    else:
        result = partial
    DB.save_json(SCH,result);return jsonify(result)

# Manual edit
@app.route("/api/schedule/edit",methods=["POST"])
def edit_cell():
    p=request.json or {};sch=DB.load_json(SCH,None);state=_load()
    if not sch: return jsonify({"ok":False,"error":"No hay horario"}),400
    updated, error = _apply_schedule_cell_edit(sch, state, p)
    if error: return jsonify({"ok":False,"error":error}),400
    DB.save_json(SCH,updated);return jsonify({"ok":True})

@app.route("/api/schedule/candidates", methods=["POST"])
def schedule_candidates():
    p = request.json or {}
    sch = DB.load_json(SCH, None)
    state = _load()
    if not sch:
        return jsonify({"ok": False, "error": "No hay horario"}), 400
    result, error = _schedule_candidates_response(sch, state, p)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify(result)

@app.route("/api/schedule")
def get_sch():
    s=DB.load_json(SCH,None)
    if not s: return jsonify({"ok":False}),404
    if "cuadrante" in s or "cuadrante_empleado" in s:
        s.pop("cuadrante", None)
        s.pop("cuadrante_empleado", None)
        DB.save_json(SCH, s)
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
    updated, error = _apply_schedule_cell_edit(data, state, p)
    if error: return jsonify({"ok":False,"error":error}),400
    DB.update_schedule_version(vid,updated);return jsonify({"ok":True})

@app.route("/api/schedule/history/<int:vid>/candidates", methods=["POST"])
def schedule_history_candidates(vid):
    p = request.json or {}
    data = DB.load_schedule_version(vid)
    state = _load()
    if not data:
        return jsonify({"ok": False, "error": "Versión no encontrada"}), 404
    result, error = _schedule_candidates_response(data, state, p)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify(result)

# Resúmenes
@app.route("/api/resumen/empleado/<int:eid>")
def res_emp(eid):
    sch=DB.load_json(SCH,None)
    if not sch: return jsonify({"error":"Sin horario"}),404
    data=_load();catalog={int(k):_to_rest(v) for k,v in data["catalogo"].items()};restrictions=[_to_re(x) for x in data["restricciones_empleado"]]
    tc={};th=0;off=0
    day_best={}
    def _score(c):
        if c.get("es_off"):
            return 0
        if c.get("es_restriccion"):
            return 1
        return 2
    for _,sd in sch["grids"].items():
        for rk,ed in sd["employees"].items():
            if _row_employee_id(rk, ed) != int(eid):
                continue
            for ds,c in ed["days"].items():
                cur=day_best.get(ds)
                if cur is None or _score(c) > _score(cur):
                    day_best[ds]=c
    for _,c in day_best.items():
        if c.get("es_off"):
            off+=1
        else:
            th+=float(c.get("horas",0.0) or 0.0)
        turno=c.get("turno",OFF_SHIFT)
        tc[turno]=tc.get(turno,0)+1
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
    seen_emp_day=set()
    for rk,ed in sd["employees"].items():
        eid = _row_employee_id(rk, ed)
        key = eid if eid is not None else ed.get("nombre", rk)
        name = ed.get("nombre", str(key))
        eh.setdefault(key, {"nombre": name, "horas": 0.0})
        for ds,c in ed["days"].items():
            if c.get("es_off") or c.get("es_restriccion"):
                continue
            pair=(key, ds)
            if pair in seen_emp_day:
                continue
            seen_emp_day.add(pair)
            eh[key]["horas"] += float(c.get("horas",0.0) or 0.0)
            turno=c.get("turno",OFF_SHIFT)
            tc[turno]=tc.get(turno,0)+1
    eh_out={v["nombre"]: round(v["horas"],1) for _,v in eh.items()}
    return jsonify({"servicio":sd["nombre"],"empleados":eh_out,"turnos_count":tc,"total_horas":round(sum(eh_out.values()),1)})

if __name__=="__main__": app.run(host="0.0.0.0",port=5000,debug=True)
