from __future__ import annotations

import pandas as pd


WEEKDAYS_PT = {
    0: "Segunda",
    1: "Terça",
    2: "Quarta",
    3: "Quinta",
    4: "Sexta",
    5: "Sábado",
    6: "Domingo",
}


def find_overlaps(sessions: pd.DataFrame, resource: str) -> pd.DataFrame:
    """Retorna pares de sessões simultâneas para a mesma sala ou médico."""
    columns = [resource, "service_date", "session_a", "session_b", "overlap_min"]
    required = {resource, "service_date", "session_id", "room_entry_time_dt", "room_exit_time_dt"}
    if not required.issubset(sessions.columns):
        return pd.DataFrame(columns=columns)

    source = sessions.dropna(subset=[resource, "room_entry_time_dt", "room_exit_time_dt"])
    records: list[dict[str, object]] = []
    for (resource_value, service_date), group in source.groupby([resource, "service_date"], dropna=False):
        ordered = group.sort_values("room_entry_time_dt")
        rows = list(ordered[["session_id", "room_entry_time_dt", "room_exit_time_dt"]].itertuples(index=False))
        for index, current in enumerate(rows):
            for candidate in rows[index + 1 :]:
                if candidate.room_entry_time_dt >= current.room_exit_time_dt:
                    break
                overlap = (
                    min(current.room_exit_time_dt, candidate.room_exit_time_dt)
                    - candidate.room_entry_time_dt
                ).total_seconds() / 60
                if overlap > 0:
                    records.append(
                        {
                            resource: resource_value,
                            "service_date": service_date,
                            "session_a": current.session_id,
                            "session_b": candidate.session_id,
                            "overlap_min": overlap,
                        }
                    )
    return pd.DataFrame(records, columns=columns)


def resource_summary(sessions: pd.DataFrame, resource: str) -> pd.DataFrame:
    """Resume volume e ocupação estimada dentro da janela observada de cada recurso."""
    columns = [
        resource,
        "sessions",
        "occupied_min",
        "observed_window_min",
        "utilization_pct",
        "idle_min",
        "overlap_pairs",
    ]
    required = {resource, "session_id", "room_entry_time_dt", "room_exit_time_dt"}
    if not required.issubset(sessions.columns):
        return pd.DataFrame(columns=columns)

    valid = sessions.dropna(subset=[resource, "room_entry_time_dt", "room_exit_time_dt"]).copy()
    valid["duration_min"] = (
        valid["room_exit_time_dt"] - valid["room_entry_time_dt"]
    ).dt.total_seconds() / 60
    valid = valid[valid["duration_min"].ge(0)]
    overlap_counts = find_overlaps(valid, resource).groupby(resource).size()
    rows: list[dict[str, object]] = []
    for resource_value, group in valid.groupby(resource):
        occupied = float(group["duration_min"].sum())
        observed_window = 0.0
        idle = 0.0
        for _, day in group.groupby(group["room_entry_time_dt"].dt.date):
            ordered = day.sort_values("room_entry_time_dt")
            observed_window += (
                ordered["room_exit_time_dt"].max() - ordered["room_entry_time_dt"].min()
            ).total_seconds() / 60
            previous_end = None
            for item in ordered.itertuples():
                if previous_end is not None:
                    idle += max((item.room_entry_time_dt - previous_end).total_seconds() / 60, 0)
                previous_end = item.room_exit_time_dt if previous_end is None else max(previous_end, item.room_exit_time_dt)
        rows.append(
            {
                resource: resource_value,
                "sessions": int(group["session_id"].nunique()),
                "occupied_min": occupied,
                "observed_window_min": observed_window,
                "utilization_pct": occupied / observed_window * 100 if observed_window else pd.NA,
                "idle_min": idle,
                "overlap_pairs": int(overlap_counts.get(resource_value, 0)),
            }
        )
    return pd.DataFrame(rows, columns=columns).sort_values("sessions", ascending=False)


def demand_by_weekday_hour(sessions: pd.DataFrame) -> pd.DataFrame:
    if "scheduled_time" not in sessions or "service_date" not in sessions:
        return pd.DataFrame(columns=["weekday", "weekday_order", "hour", "sessions"])
    clock = pd.to_datetime(sessions["scheduled_time"], format="%H:%M:%S", errors="coerce")
    data = sessions.assign(
        weekday_order=sessions["service_date"].dt.dayofweek,
        hour=clock.dt.hour,
    ).dropna(subset=["weekday_order", "hour"])
    data["weekday"] = data["weekday_order"].astype(int).map(WEEKDAYS_PT)
    return (
        data.groupby(["weekday_order", "weekday", "hour"], as_index=False)
        .agg(sessions=("session_id", "nunique"))
        .sort_values(["weekday_order", "hour"])
    )


def management_export(
    sessions: pd.DataFrame,
    procedures: pd.DataFrame,
    privacy_mode: bool = True,
) -> dict[str, bytes]:
    session_columns = [
        "service_date", "scheduled_time", "clinic", "modality", "room", "physician", "insurer",
        "procedure_count", "patient_delay_min", "wait_to_exam_min", "start_delay_min",
        "exam_duration_min", "total_stay_min", "result_delivery_min",
    ]
    procedure_columns = [
        "service_date", "scheduled_time", "procedure", "modality", "room", "physician", "insurer",
        "patient_delay_min", "wait_to_exam_min", "exam_duration_min", "total_stay_min",
    ]
    if not privacy_mode:
        session_columns.insert(2, "patient_name")
        procedure_columns.insert(2, "patient_name")
    session_columns = [column for column in session_columns if column in sessions]
    procedure_columns = [column for column in procedure_columns if column in procedures]
    return {
        "sessoes.csv": sessions[session_columns].to_csv(index=False).encode("utf-8-sig"),
        "procedimentos.csv": procedures[procedure_columns].to_csv(index=False).encode("utf-8-sig"),
    }

