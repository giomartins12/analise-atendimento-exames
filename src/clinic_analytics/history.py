from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


HISTORY_COLUMNS = [
    "period_label", "period_start", "period_end", "file_hash", "saved_at",
    "patients", "visits", "appointments", "sessions", "procedures",
    "procedures_per_patient", "median_wait_min", "median_duration_min", "median_total_stay_min",
    "on_time_pct", "excess_wait_pct", "start_delay_limit", "wait_limit",
    "room_overlap_pairs", "physician_overlap_pairs", "quality_warnings",
]


def _initialize(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_history (
                period_label TEXT PRIMARY KEY,
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                saved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                patients INTEGER NOT NULL,
                visits INTEGER NOT NULL,
                appointments INTEGER NOT NULL,
                sessions INTEGER NOT NULL,
                procedures INTEGER NOT NULL,
                procedures_per_patient REAL,
                median_wait_min REAL,
                median_duration_min REAL,
                median_total_stay_min REAL,
                on_time_pct REAL,
                excess_wait_pct REAL,
                start_delay_limit REAL,
                wait_limit REAL,
                room_overlap_pairs INTEGER NOT NULL,
                physician_overlap_pairs INTEGER NOT NULL,
                quality_warnings INTEGER NOT NULL
            )
            """
        )


def save_snapshot(path: Path, snapshot: dict[str, object]) -> str:
    """Inclui o mês ou substitui sua versão anterior, sem armazenar dados pessoais."""
    _initialize(path)
    with sqlite3.connect(path) as connection:
        existing = connection.execute(
            "SELECT 1 FROM analysis_history WHERE period_label = ?",
            (snapshot["period_label"],),
        ).fetchone()
        values = [snapshot.get(column) for column in HISTORY_COLUMNS if column != "saved_at"]
        columns = [column for column in HISTORY_COLUMNS if column != "saved_at"]
        placeholders = ", ".join("?" for _ in columns)
        updates = ", ".join(
            f"{column}=excluded.{column}" for column in columns if column != "period_label"
        )
        connection.execute(
            f"""
            INSERT INTO analysis_history ({', '.join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(period_label) DO UPDATE SET
                {updates}, saved_at=CURRENT_TIMESTAMP
            """,
            values,
        )
    return "updated" if existing else "created"


def load_history(path: Path) -> pd.DataFrame:
    _initialize(path)
    with sqlite3.connect(path) as connection:
        frame = pd.read_sql_query(
            "SELECT * FROM analysis_history ORDER BY period_start",
            connection,
        )
    for column in ("period_start", "period_end", "saved_at"):
        frame[column] = pd.to_datetime(frame[column], errors="coerce")
    return frame

