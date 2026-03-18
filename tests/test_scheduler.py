from datetime import date, time
from domain.enums import Severidad, Temporalidad, TipoRestriccion
from domain.models import Empleado, Restriccion, RestriccionEmpleado, Turno
from services.demand_service import DemandService
from solver.scheduler import Scheduler

def test_hard_restriction():
    e = [Empleado(1,"Ana",True,date(2025,1,1))]
    s = [Turno(1,1,"M",time(6,0),time(14,0),8,[0,1,2,3,4,5,6],Temporalidad.CONTINUO,sigla_turno="M8")]
    start = date(2026,2,1)
    req = DemandService().build_requirements(s, start, 1)
    cat = {1: Restriccion(1,None,"Vac",5.4,"VAC",TipoRestriccion.VACACIONES,Severidad.HARD,True,True)}
    rr = [RestriccionEmpleado(1,1,start)]
    out,_,hours = Scheduler().solve(e,s,req,rr,cat,start,1)
    assert out[0].es_off is True
    assert hours.get(1,0)==0

def test_basic():
    e = [Empleado(i,f"E{i}",True,date(2025,1,1),horas_minimas=40,horas_maximas=80,horas_objetivo=60) for i in range(1,4)]
    s = [Turno(1,1,"M",time(6,0),time(14,0),8,[0,1,2,3,4,5,6],Temporalidad.CONTINUO,sigla_turno="M8")]
    start = date(2026,3,16)
    req = DemandService().build_requirements(s, start, 7)
    out,summary,_ = Scheduler().solve(e,s,req,[],{},start,7)
    assert sum(1 for a in out if not a.es_off) >= 3
    assert summary["faltantes"] == 0

def test_preassigned_hours_reduce_max_capacity():
    e = [Empleado(1,"Ana",True,date(2025,1,1),horas_minimas=0,horas_maximas=16,horas_objetivo=16)]
    s = [Turno(1,1,"M",time(6,0),time(14,0),8,[0,1,2,3,4,5,6],Temporalidad.CONTINUO,sigla_turno="M8")]
    start = date(2026,3,1)
    req = DemandService().build_requirements(s, start, 3)
    out,summary,hours = Scheduler().solve(e,s,req,[],{},start,3,preassigned_hours={1:8})
    assert sum(1 for a in out if not a.es_off) == 1
    assert hours.get(1,0) == 8
    assert summary["faltantes"] == 2

def test_prefers_grouped_runs_over_scattered_days():
    e = [Empleado(i,f"E{i}",True,date(2025,1,1),horas_minimas=0,horas_maximas=40,horas_objetivo=24) for i in range(1,3)]
    s = [Turno(1,1,"M",time(6,0),time(14,0),8,[0,1,2,3,4,5,6],Temporalidad.CONTINUO,sigla_turno="M8")]
    start = date(2026,3,2)
    req = DemandService().build_requirements(s, start, 6)
    out,summary,_ = Scheduler().solve(e,s,req,[],{},start,6)
    assert summary["faltantes"] == 0
    patterns = {
        emp.id_empleado: "".join("W" if not a.es_off else "-" for a in out if a.id_empleado == emp.id_empleado)
        for emp in e
    }
    for pattern in patterns.values():
        assert pattern in {"WWW---", "---WWW"}

def test_vacation_start_blocks_overnight_shift_on_previous_day():
    e = [Empleado(1,"Ana",True,date(2025,1,1),horas_maximas=80,horas_objetivo=40)]
    s = [Turno(1,1,"N",time(22,0),time(6,0),8,[0,1,2,3,4,5,6],Temporalidad.CONTINUO,sigla_turno="N8",cruza_medianoche=True)]
    start = date(2026,3,19)
    req = DemandService().build_requirements(s, start, 1)
    cat = {1: Restriccion(1,None,"Vac",5.4,"VAC",TipoRestriccion.VACACIONES,Severidad.HARD,True,True)}
    rr = [RestriccionEmpleado(1,1,date(2026,3,20))]
    out,summary,hours = Scheduler().solve(e,s,req,rr,cat,start,1)
    assert out[0].es_off is True
    assert summary["faltantes"] == 1
    assert hours.get(1,0) == 0
