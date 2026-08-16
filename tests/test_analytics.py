from __future__ import annotations

import pandas as pd

from clinic_analytics.analytics import (
    coverage_table,
    demand_by_weekday_hour,
    find_overlaps,
    management_export,
    resource_summary,
)


def sample_sessions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "session_id": ["A", "B", "C"],
            "service_date": pd.to_datetime(["2026-07-06", "2026-07-06", "2026-07-07"]),
            "scheduled_time": ["09:00:00", "09:15:00", "10:00:00"],
            "room": ["S1", "S1", "S1"],
            "physician": ["M1", "M1", "M2"],
            "patient_name": ["P1", "P2", "P3"],
            "room_entry_time_dt": pd.to_datetime(["2026-07-06 09:00", "2026-07-06 09:15", "2026-07-07 10:00"]),
            "room_exit_time_dt": pd.to_datetime(["2026-07-06 09:30", "2026-07-06 09:45", "2026-07-07 10:20"]),
            "procedure_count": [1, 1, 1],
        }
    )


def test_coverage_table_has_stable_column_names() -> None:
    coverage = coverage_table(pd.DataFrame({"filled": [1, 2], "partial": [1, None]}))
    assert list(coverage.columns) == ["Campo", "Preenchimento (%)"]
    assert coverage.set_index("Campo").loc["filled", "Preenchimento (%)"] == 100
    assert coverage.set_index("Campo").loc["partial", "Preenchimento (%)"] == 50


def test_overlap_detection_is_pairwise_by_resource_and_day() -> None:
    overlaps = find_overlaps(sample_sessions(), "room")
    assert len(overlaps) == 1
    assert overlaps.iloc[0]["overlap_min"] == 15
    assert {overlaps.iloc[0]["session_a"], overlaps.iloc[0]["session_b"]} == {"A", "B"}


def test_resource_summary_exposes_overlap_and_observed_utilization() -> None:
    summary = resource_summary(sample_sessions(), "room").iloc[0]
    assert summary["sessions"] == 3
    assert summary["occupied_min"] == 80
    assert summary["observed_window_min"] == 65
    assert round(summary["utilization_pct"], 2) == round(80 / 65 * 100, 2)
    assert summary["overlap_pairs"] == 1


def test_demand_uses_portuguese_weekday_and_hour() -> None:
    demand = demand_by_weekday_hour(sample_sessions())
    monday_nine = demand[(demand["weekday"] == "Segunda") & (demand["hour"] == 9)]
    assert monday_nine.iloc[0]["sessions"] == 2


def test_privacy_export_omits_patient_name() -> None:
    sessions = sample_sessions()
    procedures = sessions.assign(procedure=["E1", "E2", "E3"])
    exports = management_export(sessions, procedures, privacy_mode=True)
    text = exports["sessoes.csv"].decode("utf-8-sig")
    assert "patient_name" not in text
    assert "P1" not in text
