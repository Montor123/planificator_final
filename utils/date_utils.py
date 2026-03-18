from __future__ import annotations
from datetime import date, timedelta

def daterange(start: date, days: int) -> list[date]:
    return [start + timedelta(days=i) for i in range(days)]
