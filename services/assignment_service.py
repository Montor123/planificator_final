from __future__ import annotations
from datetime import date
from domain.models import AsignacionServicioEmpleado

class AssignmentService:
    def default_service_for_date(self, assignments, employee_id, on_date):
        candidates = [a for a in assignments if a.id_empleado==employee_id and a.es_principal]
        if not candidates: return None
        return candidates[0].id_servicio
