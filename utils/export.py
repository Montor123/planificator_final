from __future__ import annotations
import os, tempfile
from typing import Sequence
import pandas as pd
from domain.models import AsignacionTurno

def export_csv(assignments: Sequence[AsignacionTurno], filename: str = "planificacion.csv") -> str:
    df = pd.DataFrame([a.__dict__ for a in assignments])
    out_dir = tempfile.mkdtemp(prefix="planificator_")
    out_path = os.path.join(out_dir, filename)
    df.to_csv(out_path, index=False)
    return out_path
