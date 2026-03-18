from __future__ import annotations
from datetime import date, datetime, time

def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()

def parse_time(value: str) -> time:
    value = value.strip()
    if len(value) > 5 and value.count(":") == 2:
        return datetime.strptime(value, "%H:%M:%S").time()
    return datetime.strptime(value, "%H:%M").time()

def validate_date_range(start: date, end: date) -> None:
    if end < start: raise ValueError("Fecha fin anterior a inicio")
