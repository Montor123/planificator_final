from __future__ import annotations
from datetime import date
from domain.models import Empleado

class EmployeeService:
    def is_available(self, e: Empleado, d: date) -> bool:
        if not e.activo: return False
        if d < e.fecha_alta: return False
        if e.fecha_baja and d > e.fecha_baja: return False
        return True
