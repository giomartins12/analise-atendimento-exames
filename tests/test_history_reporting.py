from __future__ import annotations

from pathlib import Path

import pandas as pd

from clinic_analytics.history import load_history, save_snapshot
from clinic_analytics.reporting import build_snapshot, generate_report


def frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    procedures = pd.DataFrame(
        {
            "procedure_id": ["P1", "P2"],
            "patient_id": ["A", "A"],
            "visit_id": ["V1", "V1"],
            "appointment_id": ["A1", "A1"],
            "session_id": ["S1", "S1"],
            "service_date": pd.to_datetime(["2026-07-01", "2026-07-01"]),
            "procedure": ["EXAME A", "EXAME B"],
        }
    )
    sessions = pd.DataFrame(
        {
            "session_id": ["S1"], "patient_id": ["A"], "service_date": pd.to_datetime(["2026-07-01"]),
            "room": ["R1"], "physician": ["M1"],
            "room_entry_time_dt": pd.to_datetime(["2026-07-01 09:00"]),
            "room_exit_time_dt": pd.to_datetime(["2026-07-01 09:20"]),
            "wait_to_exam_min": [20.0], "exam_duration_min": [20.0], "total_stay_min": [50.0],
            "start_delay_min": [5.0],
        }
    )
    visits = pd.DataFrame({"visit_id": ["V1"]})
    appointments = pd.DataFrame({"appointment_id": ["A1"]})
    return sessions, procedures, visits, appointments


def test_monthly_history_is_aggregate_and_upserts(tmp_path: Path) -> None:
    sessions, procedures, visits, appointments = frames()
    snapshot = build_snapshot(b"csv", sessions, procedures, visits, appointments, pd.DataFrame(), 10, 30)
    path = tmp_path / "history.sqlite3"
    assert save_snapshot(path, snapshot) == "created"
    snapshot["procedures"] = 3
    assert save_snapshot(path, snapshot) == "updated"
    history = load_history(path)
    assert len(history) == 1
    assert history.iloc[0]["period_label"] == "2026-07"
    assert history.iloc[0]["procedures"] == 3
    assert "patient_name" not in history.columns


def test_generated_report_documents_metrics_and_methodology(tmp_path: Path) -> None:
    sessions, procedures, visits, appointments = frames()
    snapshot = build_snapshot(b"csv", sessions, procedures, visits, appointments, pd.DataFrame(), 10, 30)
    report = generate_report(snapshot, procedures, pd.DataFrame(), load_history(tmp_path / "history.sqlite3"))
    assert "Relatório de análise operacional" in report
    assert "Procedimentos por paciente" in report
    assert "Cobertura:" in report
    assert "não contém nomes" in report
