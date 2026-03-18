from __future__ import annotations
import json, os, sqlite3
import datetime as _dt
from typing import Any

class SQLiteRepository:
    def __init__(self, db_path: str = "data/planificator.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._conn() as c:
            c.execute("CREATE TABLE IF NOT EXISTS kv_store(k TEXT PRIMARY KEY, v TEXT NOT NULL)")
            c.execute("""CREATE TABLE IF NOT EXISTS schedule_history(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                fecha_inicio TEXT,
                fecha_fin TEXT,
                created_at TEXT NOT NULL,
                data TEXT NOT NULL
            )""")
            c.commit()

    def _conn(self): return sqlite3.connect(self.db_path)

    def save_json(self, key, payload):
        data = json.dumps(payload, ensure_ascii=False, default=str)
        with self._conn() as c:
            c.execute("INSERT INTO kv_store(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",(key,data))
            c.commit()

    def load_json(self, key, default=None):
        with self._conn() as c:
            cur = c.execute("SELECT v FROM kv_store WHERE k=?",(key,))
            row = cur.fetchone()
        return json.loads(row[0]) if row else default

    # ── Histórico de horarios ────────────────────────────────────────
    def save_schedule_version(self, nombre: str, fecha_inicio: str, fecha_fin: str, data: dict) -> int:
        blob = json.dumps(data, ensure_ascii=False, default=str)
        created_at = _dt.datetime.now().isoformat(timespec="seconds")
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO schedule_history(nombre,fecha_inicio,fecha_fin,created_at,data) VALUES(?,?,?,?,?)",
                (nombre, fecha_inicio, fecha_fin, created_at, blob)
            )
            c.commit()
            return cur.lastrowid

    def list_schedule_versions(self) -> list:
        with self._conn() as c:
            cur = c.execute(
                "SELECT id,nombre,fecha_inicio,fecha_fin,created_at FROM schedule_history ORDER BY id DESC"
            )
            return [{"id":r[0],"nombre":r[1],"fecha_inicio":r[2],"fecha_fin":r[3],"created_at":r[4]} for r in cur.fetchall()]

    def load_schedule_version(self, vid: int):
        with self._conn() as c:
            cur = c.execute("SELECT data FROM schedule_history WHERE id=?", (vid,))
            row = cur.fetchone()
        return json.loads(row[0]) if row else None

    def delete_schedule_version(self, vid: int):
        with self._conn() as c:
            c.execute("DELETE FROM schedule_history WHERE id=?", (vid,))
            c.commit()

    def update_schedule_version(self, vid: int, data: dict):
        blob = json.dumps(data, ensure_ascii=False, default=str)
        with self._conn() as c:
            c.execute("UPDATE schedule_history SET data=? WHERE id=?", (blob, vid))
            c.commit()
