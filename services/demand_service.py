from __future__ import annotations
from collections import defaultdict
from datetime import date
from typing import Iterable
from domain.models import Turno

class DemandService:
    def build_requirements(self, shifts: Iterable[Turno], start: date, days: int):
        req = defaultdict(int)
        for i in range(days):
            d = start.fromordinal(start.toordinal()+i)
            for sh in shifts:
                if d.weekday() in sh.dias_recurrencia:
                    if sh.temporalidad.value=="temporal" and sh.fecha_inicio and sh.fecha_fin:
                        if d<sh.fecha_inicio or d>sh.fecha_fin: continue
                    req[(d,sh.id_turno)]+=1
        return req
    def total_demand_hours(self, req, shifts):
        by_id={s.id_turno:s for s in shifts}
        return sum(n*by_id[sid].duracion_horas for (_,sid),n in req.items() if sid in by_id)
    def estimate_min_staff(self, total_hours, target):
        if target<=0: return 0
        return int(-(-total_hours//target))
