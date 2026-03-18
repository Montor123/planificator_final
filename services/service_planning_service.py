from __future__ import annotations
from domain.enums import Temporalidad
from domain.models import Posicion, Servicio, Turno
from services.shift_service import ShiftService
from utils.validation import validate_date_range

class ServicePlanningService:
    def __init__(self): self.shift_service = ShiftService()
    def add_servicio(self, lst, s):
        if any(x.id_servicio==s.id_servicio for x in lst): raise ValueError("ID duplicado")
        return [*lst, s]
    def add_turno(self, lst, t):
        if t.temporalidad==Temporalidad.TEMPORAL and t.fecha_inicio and t.fecha_fin:
            validate_date_range(t.fecha_inicio,t.fecha_fin)
        t = self.shift_service.enrich_shift(t)
        return [*lst, t]
