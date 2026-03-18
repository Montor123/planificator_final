from datetime import date
from domain.enums import TipoRestriccion
from services.restriction_service import RestrictionService

def test_expand_range():
    rows = RestrictionService().expand_range_to_daily(1, 10, date(2026,2,1), date(2026,2,3))
    assert len(rows) == 3

def test_severity_vacaciones():
    assert RestrictionService().default_severity_for_type(TipoRestriccion.VACACIONES).value == "HARD"
