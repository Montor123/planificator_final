from __future__ import annotations

from services.assignment_service import AssignmentService


def test_normalize_rows_deduplicates_pairs():
    rows = [
        {"id_empleado": "1", "id_servicio": "2", "es_principal": False},
        {"id_empleado": 1, "id_servicio": 2, "es_principal": True},
        {"id_empleado": "bad", "id_servicio": 2},
    ]
    out = AssignmentService.normalize_rows(rows)
    assert out == [{"id_empleado": 1, "id_servicio": 2, "es_principal": True}]


def test_toggle_add_then_remove():
    rows = []
    rows = AssignmentService.toggle(rows, 3, 1)
    assert rows == [{"id_empleado": 3, "id_servicio": 1, "es_principal": False}]
    rows = AssignmentService.toggle(rows, 3, 1)
    assert rows == []


def test_service_employee_map_is_explicit_per_service():
    services = [{"id_servicio": 1}, {"id_servicio": 2}]
    employees = [
        {"id_empleado": 1, "activo": True},
        {"id_empleado": 2, "activo": True},
        {"id_empleado": 3, "activo": False},
    ]
    rows = [{"id_empleado": 1, "id_servicio": 1, "es_principal": False}]
    out = AssignmentService.service_employee_map(services, employees, rows)
    assert out[1] == {1}
    assert out[2] == set()
