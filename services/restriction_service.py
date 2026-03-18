from __future__ import annotations
from datetime import date, timedelta
from domain.enums import Severidad, TipoRestriccion
from domain.models import Restriccion, RestriccionEmpleado

class RestrictionService:
    def default_severity_for_type(self, tipo):
        if tipo in {TipoRestriccion.VACACIONES,TipoRestriccion.MATRIMONIO,TipoRestriccion.BAJA_MEDICA,TipoRestriccion.INDISPONIBILIDAD}:
            return Severidad.HARD
        if tipo==TipoRestriccion.DIA_LIBRE: return Severidad.SOFT_LOW
        return Severidad.SOFT_MEDIUM
    def expand_range_to_daily(self, eid, rid, fi, ff, hi=None, hf=None, obs=None):
        rows=[]; cur=fi
        while cur<=ff:
            rows.append(RestriccionEmpleado(eid,rid,cur,hi,hf,obs))
            cur+=timedelta(days=1)
        return rows
