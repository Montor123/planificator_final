import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import DB, SK, app


def _r():
    with app.test_client() as c:
        c.post("/api/reset")


def _state():
    return DB.load_json(SK, None)


def _save_state(data):
    DB.save_json(SK, data)


def _generate(client, start_date="2026-03-01", num_days=31, max_time=30):
    return client.post("/api/generar", json={"start_date": start_date, "num_days": num_days, "max_time": max_time})


def _row_employee_id(row_key, row):
    if isinstance(row, dict) and row.get("id_empleado") is not None:
        return int(row["id_empleado"])
    return int(str(row_key).split(":", 1)[0])


def _first_work_assignment(schedule, employee_id=None):
    for sid, grid in schedule["grids"].items():
        for rk, emp in grid["employees"].items():
            eid = _row_employee_id(rk, emp)
            if employee_id is not None and eid != employee_id:
                continue
            for ds, cell in emp["days"].items():
                if not cell.get("es_off") and not cell.get("es_restriccion"):
                    return int(sid), int(eid), ds, cell
    return None


def _find_alt_service_row(schedule, employee_id, exclude_service_id):
    for sid, grid in schedule["grids"].items():
        if int(sid) == exclude_service_id:
            continue
        if any(_row_employee_id(rk, row) == employee_id for rk, row in grid["employees"].items()):
            return int(sid)
    return None


def test_state():
    _r()
    with app.test_client() as c:
        d = c.get("/api/state").get_json()
        for k in ("servicios", "posiciones", "turnos", "empleados", "catalogo", "restricciones_empleado", "asignaciones_servicio", "conciliaciones"):
            assert k in d


def test_generar():
    _r()
    with app.test_client() as c:
        r = _generate(c)
        assert r.status_code == 200
        d = r.get_json()
        assert "grids" in d and len(d["dates"]) == 31
        for h in d["hours"]:
            assert "horas_restriccion" in h


def test_generar_requires_full_month():
    _r()
    with app.test_client() as c:
        r = _generate(c, start_date="2026-03-02", num_days=7)
        assert r.status_code == 400
        assert "mes" in r.get_json()["error"].lower()


def test_generar_respects_global_max_hours_and_no_double_booking():
    _r()
    with app.test_client() as c:
        data = _generate(c).get_json()
        state = c.get("/api/state").get_json()
        max_by_emp = {e["id_empleado"]: e["horas_maximas"] for e in state["empleados"]}
        seen = {}
        for sid, grid in data["grids"].items():
            for rk, emp in grid["employees"].items():
                eid = _row_employee_id(rk, emp)
                for ds, cell in emp["days"].items():
                    if cell.get("es_off") or cell.get("es_restriccion"):
                        continue
                    key = (int(eid), ds)
                    assert key not in seen
                    seen[key] = sid
        for h in data["hours"]:
            max_hours = max_by_emp[h["id"]]
            if max_hours is not None:
                assert h["horas_total"] <= max_hours + 1e-6


def test_generar_por_servicio_separado_y_acumula_grids():
    _r()
    with app.test_client() as c:
        s1 = c.post("/api/generar", json={"start_date": "2026-03-01", "num_days": 31, "max_time": 5, "id_servicio": 1})
        assert s1.status_code == 200
        d1 = s1.get_json()
        assert "1" in d1["grids"]
        assert "2" not in d1["grids"]
        # generar luego servicio 2 y comprobar que ambos quedan en el horario guardado
        s2 = c.post("/api/generar", json={"start_date": "2026-03-01", "num_days": 31, "max_time": 5, "id_servicio": 2})
        assert s2.status_code == 200
        d2 = s2.get_json()
        assert "1" in d2["grids"]
        assert "2" in d2["grids"]


def test_crud_empleado():
    _r()
    with app.test_client() as c:
        r = c.post("/api/empleados", json={"nombre": "Test", "preferencia_turno": "nocturno"}).get_json()
        assert r["ok"]
        eid = max(e["id_empleado"] for e in r["empleados"])
        assert c.put(f"/api/empleados/{eid}", json={"nombre": "Test2"}).get_json()["ok"]
        assert c.delete(f"/api/empleados/{eid}").get_json()["ok"]


def test_crud_turno():
    _r()
    with app.test_client() as c:
        assert c.post("/api/turnos", json={"nombre_turno": "T", "id_posicion": 1, "hora_inicio": "09:00", "hora_fin": "17:00", "dias_recurrencia": [0, 1, 2]}).get_json()["ok"]


def test_crud_servicio():
    _r()
    with app.test_client() as c:
        r = c.post("/api/servicios", json={"nombre": "X", "area": "Y"}).get_json()
        assert r["ok"]


def test_restriction_limit():
    _r()
    with app.test_client() as c:
        r = c.post("/api/restricciones", json={"id_empleado": 1, "id_restriccion": 10, "fecha_ini": "2026-04-01", "fecha_fin": "2026-06-01"})
        assert r.status_code == 400
        assert "límite" in r.get_json()["error"].lower() or "limite" in r.get_json()["error"].lower()


def test_day_off_is_unlimited():
    _r()
    with app.test_client() as c:
        r = c.post("/api/restricciones", json={"id_empleado": 1, "id_restriccion": 11, "fecha_ini": "2026-03-01", "fecha_fin": "2026-03-10"})
        assert r.status_code == 200
        assert r.get_json()["ok"] is True


def test_toggle_asig():
    _r()
    with app.test_client() as c:
        assert c.post("/api/asignaciones_servicio/toggle", json={"id_empleado": 4, "id_servicio": 1}).get_json()["ok"]


def test_toggle_asig_rejects_invalid_entities():
    _r()
    with app.test_client() as c:
        r1 = c.post("/api/asignaciones_servicio/toggle", json={"id_empleado": 9999, "id_servicio": 1})
        assert r1.status_code == 400
        r2 = c.post("/api/asignaciones_servicio/toggle", json={"id_empleado": 1, "id_servicio": 9999})
        assert r2.status_code == 400


def test_assignments_are_strict_per_service():
    _r()
    with app.test_client() as c:
        asigs = c.get("/api/asignaciones_servicio").get_json() or []
        for a in list(asigs):
            if int(a["id_servicio"]) == 2:
                c.post(
                    "/api/asignaciones_servicio/toggle",
                    json={"id_empleado": int(a["id_empleado"]), "id_servicio": 2},
                )
        r = _generate(c, id_servicio=2).get_json()
        assert r["grids"]["2"]["employees"] == {}
        assert int(r["summary"]["faltantes_by_service"].get("2", 0)) > 0


def test_conciliaciones():
    _r()
    with app.test_client() as c:
        assert c.post("/api/conciliaciones", json={"id_empleado": 1, "dias": [{"dia_semana": 0, "hora_ini": "08:00", "hora_fin": "16:00"}], "fecha_ini": "2026-03-01", "fecha_fin": "2026-12-31"}).get_json()["ok"]


def test_manual_edit():
    _r()
    with app.test_client() as c:
        schedule = _generate(c).get_json()
        sid, eid, ds, _ = _first_work_assignment(schedule)
        assert c.post("/api/schedule/edit", json={"id_servicio": sid, "id_empleado": eid, "fecha": ds, "turno": "N8", "horas": 8}).get_json()["ok"]


def test_manual_edit_rejects_double_booking():
    _r()
    with app.test_client() as c:
        schedule = _generate(c).get_json()
        sid, eid, ds, cell = _first_work_assignment(schedule, employee_id=1)
        other_sid = _find_alt_service_row(schedule, eid, sid)
        assert other_sid is not None
        r = c.post("/api/schedule/edit", json={"id_servicio": other_sid, "id_empleado": eid, "fecha": ds, "turno": cell["turno"], "horas": cell["horas"]})
        assert r.status_code == 400
        assert "mismo" in r.get_json()["error"].lower()


def test_manual_edit_rejects_max_hours_excess():
    _r()
    state = _state()
    for emp in state["empleados"]:
        if emp["id_empleado"] == 1:
            emp["horas_maximas"] = 8
            emp["horas_objetivo"] = 8
    _save_state(state)
    with app.test_client() as c:
        schedule = _generate(c).get_json()
        target_service = next(
            sid
            for sid, grid in schedule["grids"].items()
            if any(_row_employee_id(rk, row) == 1 for rk, row in grid["employees"].items())
        )
        target_row = next(
            row
            for rk, row in schedule["grids"][target_service]["employees"].items()
            if _row_employee_id(rk, row) == 1
        )
        target_day = next(ds for ds, cell in target_row["days"].items() if cell.get("es_off"))
        r = c.post("/api/schedule/edit", json={"id_servicio": int(target_service), "id_empleado": 1, "fecha": target_day, "turno": "M8", "horas": 8})
        assert r.status_code == 400
        assert "horas" in r.get_json()["error"].lower()


def test_manual_edit_rejects_overnight_shift_before_vacation():
    _r()
    state = _state()
    state["restricciones_empleado"] = [r for r in state["restricciones_empleado"] if r["id_empleado"] != 1]
    state["restricciones_empleado"].append({"id_empleado": 1, "id_restriccion": 10, "fecha": "2026-03-20", "hora_ini": None, "hora_fin": None, "observaciones": None})
    _save_state(state)
    with app.test_client() as c:
        schedule = _generate(c).get_json()
        service_id = next(
            int(sid)
            for sid, grid in schedule["grids"].items()
            if any(_row_employee_id(rk, row) == 1 for rk, row in grid["employees"].items())
        )
        r = c.post("/api/schedule/edit", json={"id_servicio": service_id, "id_empleado": 1, "fecha": "2026-03-19", "turno": "N8", "horas": 8})
        assert r.status_code == 400
        assert "vacaciones" in r.get_json()["error"].lower()


def test_restriction_hours_reduce_available_capacity():
    _r()
    state = _state()
    for emp in state["empleados"]:
        if emp["id_empleado"] == 1:
            emp["horas_maximas"] = 16
            emp["horas_objetivo"] = 16
    state["restricciones_empleado"] = [r for r in state["restricciones_empleado"] if r["id_empleado"] != 1]
    state["restricciones_empleado"].append({"id_empleado": 1, "id_restriccion": 10, "fecha": "2026-03-01", "hora_ini": None, "hora_fin": None, "observaciones": None})
    _save_state(state)
    with app.test_client() as c:
        data = _generate(c).get_json()
        summary = next(h for h in data["hours"] if h["id"] == 1)
        assert summary["horas_restriccion"] == 5.4
        assert summary["horas_total"] <= 16


def test_shortage_reported_instead_of_exceeding_max():
    _r()
    state = _state()
    for emp in state["empleados"]:
        emp["horas_maximas"] = 8
        emp["horas_objetivo"] = 8
    _save_state(state)
    with app.test_client() as c:
        data = _generate(c).get_json()
        assert data["summary"]["faltantes"] > 0
        for h in data["hours"]:
            assert h["horas_total"] <= 8 + 1e-6


def test_resumen():
    _r()
    with app.test_client() as c:
        _generate(c)
        assert "horas_total" in c.get("/api/resumen/empleado/1").get_json()
        assert "total_horas" in c.get("/api/resumen/servicio/1").get_json()
