"""CP-SAT scheduler – Google OR-Tools."""
from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime, timedelta

from domain.enums import OFF_SHIFT, Severidad
from domain.enums import TipoRestriccion
from domain.models import AsignacionTurno, Turno
from services.employee_service import EmployeeService
from utils.date_utils import daterange
from utils.validation import parse_time

try:
    from ortools.sat.python import cp_model as _cp
    _ORTOOLS = True
except ImportError:
    _ORTOOLS = False

_SCALE = 10  # horas float → int (×10 para aritmética entera)
_BLOCK_CHANGE_PENALTY = 3
_ISOLATED_DAY_PENALTY = 40
_RUN_OVER_5_PENALTY = 25
_SIX_DAY_BALANCE_PENALTY = 14


# ── helpers ──────────────────────────────────────────────────────────────────

def _has_12h_rest(prev: Turno, nxt: Turno) -> bool:
    base = datetime(2024, 1, 1)
    s1 = datetime.combine(base.date(), prev.hora_inicio)
    e1 = datetime.combine(base.date(), prev.hora_fin)
    if prev.cruza_medianoche or e1 <= s1:
        e1 += timedelta(days=1)
    s2 = datetime.combine(base.date() + timedelta(days=1), nxt.hora_inicio)
    if nxt.cruza_medianoche and nxt.hora_inicio < prev.hora_fin:
        s2 += timedelta(days=1)
    return (s2 - e1).total_seconds() / 3600.0 >= 12.0


def _shift_franja(sh: Turno) -> str:
    sig = sh.sigla_turno or ""
    if sig.startswith("M") or sig.startswith("T"):
        return "diurno"
    if sig.startswith("N"):
        return "nocturno"
    return "indiferente"


def _conciliation_ok(concs, emp_id: int, d: date, sh: Turno) -> bool:
    dow = d.weekday()
    relevant = [
        c for c in concs
        if c.get("id_empleado") == emp_id
        and c.get("dia_semana") == dow
        and str(c.get("fecha_ini", "")) <= str(d) <= str(c.get("fecha_fin", ""))
    ]
    if not relevant:
        return True
    for c in relevant:
        try:
            ci = parse_time(c["hora_ini"]) if isinstance(c["hora_ini"], str) else c["hora_ini"]
            cf = parse_time(c["hora_fin"]) if isinstance(c["hora_fin"], str) else c["hora_fin"]
        except Exception:
            continue
        if sh.hora_inicio >= ci and sh.hora_fin <= cf:
            return True
        if sh.cruza_medianoche and sh.hora_inicio >= ci:
            return True
    return False


def _build_vacation_days(restrictions, catalog) -> set:
    vacation_days = set()
    for rr in restrictions:
        cat = catalog.get(rr.id_restriccion)
        if cat and cat.tipo_restriccion == TipoRestriccion.VACACIONES:
            vacation_days.add((rr.id_empleado, rr.fecha))
    return vacation_days


# ── Scheduler ────────────────────────────────────────────────────────────────

class Scheduler:
    def __init__(self, max_time_sec: int = 30):
        self.max_time_sec = max_time_sec
        self.es = EmployeeService()

    def solve(self, employees, shifts, requirements, restrictions, catalog,
              start: date, days: int, conciliaciones=None,
              allowed_shift_ids=None, preassigned_hours=None):
        concs = conciliaciones or []
        allowed = allowed_shift_ids or {}
        consumed = preassigned_hours or {}
        if not _ORTOOLS:
            raise RuntimeError("OR-Tools es obligatorio para generar horarios")
        return self._ortools_solve(employees, shifts, requirements,
                                   restrictions, catalog, start, days, concs,
                                   allowed, consumed)

    # ── CP-SAT ───────────────────────────────────────────────────────────────

    def _ortools_solve(self, employees, shifts, requirements, restrictions,
                       catalog, start, days, conciliaciones,
                       allowed_shift_ids, preassigned_hours):
        dates = daterange(start, days)
        date_idx = {d: i for i, d in enumerate(dates)}
        shift_by_id = {s.id_turno: s for s in shifts}
        n_days = len(dates)

        # Hard-blocked (empleado, fecha)
        hard_blocked: set = set()
        vacation_days = _build_vacation_days(restrictions, catalog)
        for rr in restrictions:
            cat = catalog.get(rr.id_restriccion)
            if cat and cat.severidad == Severidad.HARD:
                hard_blocked.add((rr.id_empleado, rr.fecha))

        model = _cp.CpModel()

        # Variables x[(eid, di, tid)] = BoolVar
        x: dict = {}
        for e in employees:
            allowed = allowed_shift_ids.get(e.id_empleado)
            max_remaining = None
            if e.horas_maximas is not None:
                max_remaining = max(0.0, e.horas_maximas - preassigned_hours.get(e.id_empleado, 0.0))
            for di, d in enumerate(dates):
                if not self.es.is_available(e, d):
                    continue
                if (e.id_empleado, d) in hard_blocked:
                    continue
                for sh in shifts:
                    if allowed is not None and sh.id_turno not in allowed:
                        continue
                    if max_remaining is not None and max_remaining <= 0:
                        continue
                    if sh.cruza_medianoche and (e.id_empleado, d + timedelta(days=1)) in vacation_days:
                        continue
                    if not _conciliation_ok(conciliaciones, e.id_empleado, d, sh):
                        continue
                    x[(e.id_empleado, di, sh.id_turno)] = model.NewBoolVar(
                        f'x_{e.id_empleado}_{di}_{sh.id_turno}'
                    )

        # C1 – máximo un turno por empleado/día
        worked: dict = {}
        for e in employees:
            for di in range(n_days):
                day_vars = [x[(e.id_empleado, di, sh.id_turno)]
                            for sh in shifts if (e.id_empleado, di, sh.id_turno) in x]
                if day_vars:
                    w = model.NewBoolVar(f'w_{e.id_empleado}_{di}')
                    if len(day_vars) == 1:
                        model.Add(w == day_vars[0])
                    else:
                        model.Add(_cp.LinearExpr.Sum(day_vars) == w)
                    worked[(e.id_empleado, di)] = w
                if len(day_vars) > 1:
                    model.AddAtMostOne(day_vars)

        # C2 – descanso 12 h entre días consecutivos
        for e in employees:
            for di in range(n_days - 1):
                for sh_p in shifts:
                    kp = (e.id_empleado, di, sh_p.id_turno)
                    if kp not in x:
                        continue
                    for sh_n in shifts:
                        kn = (e.id_empleado, di + 1, sh_n.id_turno)
                        if kn not in x:
                            continue
                        if not _has_12h_rest(sh_p, sh_n):
                            model.AddBoolOr([x[kp].Not(), x[kn].Not()])

        # C3 – horas máximas (hard)
        for e in employees:
            if not e.horas_maximas:
                continue
            max_remaining = max(0.0, e.horas_maximas - preassigned_hours.get(e.id_empleado, 0.0))
            terms = [
                (x[(e.id_empleado, di, sh.id_turno)], int(sh.duracion_horas * _SCALE))
                for di in range(n_days) for sh in shifts
                if (e.id_empleado, di, sh.id_turno) in x
            ]
            if terms:
                model.Add(
                    _cp.LinearExpr.WeightedSum(
                        [v for v, _ in terms], [w for _, w in terms]
                    ) <= int(max_remaining * _SCALE)
                )

        # Variables de déficit de cobertura (soft – objetivo primario)
        shortage_vars: list = []
        fixed_shortage = 0
        for (d, sid), needed in requirements.items():
            di = date_idx.get(d)
            if di is None:
                continue
            if not shift_by_id.get(sid):
                continue
            cover = [x[(e.id_empleado, di, sid)]
                     for e in employees if (e.id_empleado, di, sid) in x]
            if not cover:
                fixed_shortage += needed
                continue
            sv = model.NewIntVar(0, needed, f'sh_{di}_{sid}')
            model.Add(_cp.LinearExpr.Sum(cover) + sv >= needed)
            shortage_vars.append(sv)

        # Desviación de horas objetivo (soft – objetivo secundario)
        dev_vars: list = []
        for e in employees:
            if not e.horas_objetivo:
                continue
            target = int((e.horas_objetivo - preassigned_hours.get(e.id_empleado, 0.0)) * _SCALE)
            terms = [
                (x[(e.id_empleado, di, sh.id_turno)], int(sh.duracion_horas * _SCALE))
                for di in range(n_days) for sh in shifts
                if (e.id_empleado, di, sh.id_turno) in x
            ]
            if not terms:
                continue
            actual = _cp.LinearExpr.WeightedSum(
                [v for v, _ in terms], [w for _, w in terms]
            )
            ov = model.NewIntVar(0, int(800 * _SCALE), f'ov_{e.id_empleado}')
            un = model.NewIntVar(0, int(800 * _SCALE), f'un_{e.id_empleado}')
            model.Add(actual - target == ov - un)
            dev_vars.extend([ov, un])

        # Penalización preferencia de turno (soft – objetivo terciario)
        pref_terms: list = []
        for e in employees:
            pref = getattr(e, 'preferencia_turno', 'indiferente')
            if pref == 'indiferente':
                continue
            for di in range(n_days):
                for sh in shifts:
                    k = (e.id_empleado, di, sh.id_turno)
                    if k not in x:
                        continue
                    sf = _shift_franja(sh)
                    if sf != 'indiferente' and sf != pref:
                        pref_terms.append((x[k], 50))

        # Agrupar trabajo en bloques 2-5 días cuando sea posible.
        block_terms: list = []
        for e in employees:
            for di in range(n_days):
                w = worked.get((e.id_empleado, di))
                if w is None:
                    continue
                prev = worked.get((e.id_empleado, di - 1))
                nxt = worked.get((e.id_empleado, di + 1))
                prev_expr = prev if prev is not None else 0
                next_expr = nxt if nxt is not None else 0
                isolated = model.NewBoolVar(f'iso_{e.id_empleado}_{di}')
                model.Add(isolated <= w)
                if prev is not None:
                    model.Add(isolated + prev <= 1)
                if nxt is not None:
                    model.Add(isolated + nxt <= 1)
                model.Add(isolated >= w - prev_expr - next_expr)
                block_terms.append((isolated, _ISOLATED_DAY_PENALTY))

            for di in range(n_days - 1):
                a = worked.get((e.id_empleado, di))
                b = worked.get((e.id_empleado, di + 1))
                if a is None and b is None:
                    continue
                a_expr = a if a is not None else 0
                b_expr = b if b is not None else 0
                change = model.NewBoolVar(f'chg_{e.id_empleado}_{di}')
                model.Add(change >= a_expr - b_expr)
                model.Add(change >= b_expr - a_expr)
                model.Add(change <= a_expr + b_expr)
                model.Add(change <= 2 - a_expr - b_expr)
                block_terms.append((change, _BLOCK_CHANGE_PENALTY))

            for di in range(n_days - 5):
                window = [worked.get((e.id_empleado, di + off)) for off in range(6)]
                if any(w is None for w in window):
                    continue
                over = model.NewBoolVar(f'ov5_{e.id_empleado}_{di}')
                model.Add(sum(window) - 5 <= over)
                for w in window:
                    model.Add(over <= w)
                block_terms.append((over, _RUN_OVER_5_PENALTY))
                over3 = model.NewIntVar(0, 6, f'ov3_{e.id_empleado}_{di}')
                under3 = model.NewIntVar(0, 6, f'un3_{e.id_empleado}_{di}')
                model.Add(sum(window) - 3 == over3 - under3)
                block_terms.extend([(over3, _SIX_DAY_BALANCE_PENALTY), (under3, _SIX_DAY_BALANCE_PENALTY)])

        # Objetivo global: minimizar déficit (×1000) + desviación + preferencia
        obj_parts = (
            [(sv, 1000) for sv in shortage_vars]
            + [(dv, 1) for dv in dev_vars]
            + pref_terms
            + block_terms
        )
        if obj_parts:
            model.Minimize(
                _cp.LinearExpr.WeightedSum(
                    [v for v, _ in obj_parts], [w for _, w in obj_parts]
                )
            )

        solver = _cp.CpSolver()
        solver.parameters.max_time_in_seconds = float(self.max_time_sec)
        solver.parameters.num_search_workers = 4
        solver.parameters.log_search_progress = False
        status = solver.Solve(model)
        ok = status in (_cp.OPTIMAL, _cp.FEASIBLE)

        out: list[AsignacionTurno] = []
        hours: dict = defaultdict(float)

        for e in employees:
            for di, d in enumerate(dates):
                if not self.es.is_available(e, d):
                    continue
                assigned = None
                if ok:
                    for sh in shifts:
                        k = (e.id_empleado, di, sh.id_turno)
                        if k in x and solver.Value(x[k]) == 1:
                            assigned = sh
                            break
                if assigned:
                    out.append(AsignacionTurno(
                        1, e.id_empleado, 1, assigned.id_posicion, d,
                        assigned.sigla_turno or assigned.nombre_turno,
                        assigned.duracion_horas, False
                    ))
                    hours[e.id_empleado] += assigned.duracion_horas
                else:
                    out.append(AsignacionTurno(1, e.id_empleado, 1, 0, d, OFF_SHIFT, 0.0, True))

        total_shortage = fixed_shortage + (sum(solver.Value(sv) for sv in shortage_vars) if ok else 0)
        return out, {"faltantes": int(total_shortage), "excesos": 0}, dict(hours)
