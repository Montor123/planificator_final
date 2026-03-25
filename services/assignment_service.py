from __future__ import annotations

from domain.models import AsignacionServicioEmpleado


class AssignmentService:
    def default_service_for_date(self, assignments, employee_id, on_date):
        candidates = [a for a in assignments if a.id_empleado == employee_id and a.es_principal]
        if not candidates:
            return None
        return candidates[0].id_servicio

    @staticmethod
    def normalize_rows(rows):
        out = {}
        for raw in rows or []:
            try:
                eid = int(raw["id_empleado"])
                sid = int(raw["id_servicio"])
            except (TypeError, ValueError, KeyError):
                continue
            key = (eid, sid)
            prev = out.get(key)
            principal = bool(raw.get("es_principal", False)) or bool(prev.get("es_principal", False) if prev else False)
            out[key] = {"id_empleado": eid, "id_servicio": sid, "es_principal": principal}
        return [out[k] for k in sorted(out.keys())]

    @staticmethod
    def toggle(rows, employee_id: int, service_id: int, *, is_primary: bool = False):
        normalized = AssignmentService.normalize_rows(rows)
        employee_id = int(employee_id)
        service_id = int(service_id)
        filtered = [
            a
            for a in normalized
            if not (int(a["id_empleado"]) == employee_id and int(a["id_servicio"]) == service_id)
        ]
        if len(filtered) == len(normalized):
            filtered.append({"id_empleado": employee_id, "id_servicio": service_id, "es_principal": bool(is_primary)})
        return AssignmentService.normalize_rows(filtered)

    @staticmethod
    def service_employee_map(services, employees, rows):
        active_ids = set()
        for e in employees:
            if hasattr(e, "activo"):
                if e.activo:
                    active_ids.add(int(e.id_empleado))
            elif isinstance(e, dict) and bool(e.get("activo", False)):
                active_ids.add(int(e.get("id_empleado")))

        explicit = {}
        for a in AssignmentService.normalize_rows(rows):
            sid = int(a["id_servicio"])
            eid = int(a["id_empleado"])
            if eid not in active_ids:
                continue
            explicit.setdefault(sid, set()).add(eid)

        out = {}
        for srv in services:
            if isinstance(srv, dict):
                sid = int(srv["id_servicio"])
            else:
                sid = int(srv.id_servicio)
            # Modo explícito por servicio:
            # sin filas => servicio sin plantilla asignada.
            out[sid] = set(explicit.get(sid, set()))
        return out
