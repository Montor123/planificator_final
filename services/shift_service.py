from __future__ import annotations
from datetime import datetime, timedelta
from domain.enums import FranjaTurno
from domain.models import Turno

class ShiftService:
    def enrich_shift(self, t: Turno) -> Turno:
        base = datetime(2024,1,1)
        s = datetime.combine(base.date(), t.hora_inicio)
        e = datetime.combine(base.date(), t.hora_fin)
        cruza = e <= s
        if cruza: e += timedelta(days=1)
        hours = (e-s).total_seconds()/3600
        t.cruza_medianoche = cruza; t.duracion_horas = hours
        if cruza or t.hora_inicio.hour >= 17: f = FranjaTurno.N
        elif t.hora_inicio.hour >= 12: f = FranjaTurno.T
        else: f = FranjaTurno.M
        suf = int(hours) if float(hours).is_integer() else round(hours,1)
        t.sigla_turno = f"{f.value}{suf}"
        return t
    def overlap_minutes(self, a: Turno, b: Turno) -> int:
        base = datetime(2024,1,1)
        a_s=datetime.combine(base.date(),a.hora_inicio); a_e=datetime.combine(base.date(),a.hora_fin)
        b_s=datetime.combine(base.date(),b.hora_inicio); b_e=datetime.combine(base.date(),b.hora_fin)
        if a_e<=a_s: a_e+=timedelta(days=1)
        if b_e<=b_s: b_e+=timedelta(days=1)
        return int(max(0,(min(a_e,b_e)-max(a_s,b_s)).total_seconds()/60))
