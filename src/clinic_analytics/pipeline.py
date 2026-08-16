from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

import pandas as pd

from .ingestion import CsvMetadata, read_csv
from .mapping import REQUIRED_FIELDS, infer_mapping


@dataclass
class AnalysisResult:
    raw: pd.DataFrame
    procedures: pd.DataFrame
    sessions: pd.DataFrame
    appointments: pd.DataFrame
    visits: pd.DataFrame
    quality: pd.DataFrame
    metadata: CsvMetadata
    mapping: dict[str, str]
    confidence: dict[str, float]
    missing_required: set[str]


def _normalize_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKD", str(value).strip().upper())
    return " ".join("".join(ch for ch in text if not unicodedata.combining(ch)).split())


def _identifier(*parts: object) -> str:
    source = "|".join("" if pd.isna(part) else str(part) for part in parts)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def _parse_clock(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, format="%H:%M:%S", errors="coerce")


def _event_datetime(service_date: pd.Series, clock: pd.Series) -> pd.Series:
    parsed = _parse_clock(clock)
    return (
        service_date
        + pd.to_timedelta(parsed.dt.hour, unit="h")
        + pd.to_timedelta(parsed.dt.minute, unit="m")
        + pd.to_timedelta(parsed.dt.second, unit="s")
    )


def _minutes_between(end: pd.Series, start: pd.Series, allow_overnight: bool = True) -> pd.Series:
    difference = (end - start).dt.total_seconds() / 60
    overnight = allow_overnight & difference.lt(0) & difference.ge(-12 * 60)
    return difference.mask(overnight, difference + 24 * 60)


def _as_boolean(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().str.casefold().map(
        {"true": True, "false": False, "sim": True, "não": False, "nao": False, "1": True, "0": False}
    ).astype("boolean")


def analyze_csv(content: bytes, mapping_override: dict[str, str] | None = None) -> AnalysisResult:
    raw, metadata = read_csv(content)
    inferred, confidence = infer_mapping(raw.columns)
    mapping = inferred | {k: v for k, v in (mapping_override or {}).items() if v in raw.columns}
    missing_required = REQUIRED_FIELDS - mapping.keys()
    if missing_required:
        return AnalysisResult(raw, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), metadata, mapping, confidence, missing_required)

    procedures = pd.DataFrame(index=raw.index)
    for concept, original in mapping.items():
        procedures[concept] = raw[original]

    procedures["source_row"] = procedures.index + 2
    procedures["service_date"] = pd.to_datetime(procedures["service_date"], dayfirst=True, errors="coerce")
    valid = procedures["service_date"].notna() & procedures["patient_name"].notna() & procedures["procedure"].notna()
    procedures = procedures.loc[valid].copy()

    for field in ("patient_name", "clinic", "modality", "room", "physician", "procedure", "insurer", "plan"):
        if field in procedures:
            procedures[f"{field}_normalized"] = procedures[field].map(_normalize_text)

    date = procedures["service_date"]
    for field in (
        "scheduled_time", "expected_arrival_time", "interview_time", "clinic_entry_time", "ticket_time",
        "registration_time", "room_entry_time", "room_exit_time", "clinic_exit_time",
    ):
        if field in procedures:
            procedures[f"{field}_dt"] = _event_datetime(date, procedures[field])

    for field in ("report_time", "report_signed_time", "result_delivered_time"):
        if field in procedures:
            procedures[f"{field}_dt"] = pd.to_datetime(procedures[field], dayfirst=True, errors="coerce")
    if "has_report" in procedures:
        procedures["has_report_bool"] = _as_boolean(procedures["has_report"])
    if "session_quantity" in procedures:
        procedures["session_quantity_num"] = pd.to_numeric(procedures["session_quantity"], errors="coerce").astype("Int64")

    patient_key = procedures["patient_name_normalized"]
    date_key = procedures["service_date"].dt.strftime("%Y-%m-%d")
    modality_key = procedures.get("modality_normalized", pd.Series("", index=procedures.index))
    physician_key = procedures.get("physician_normalized", pd.Series("", index=procedures.index))
    room_key = procedures.get("room_normalized", pd.Series("", index=procedures.index))
    scheduled_key = procedures["scheduled_time"].fillna("")
    room_in_key = procedures.get("room_entry_time", pd.Series("", index=procedures.index)).fillna("")
    room_out_key = procedures.get("room_exit_time", pd.Series("", index=procedures.index)).fillna("")

    procedures["patient_id"] = patient_key.map(_identifier)
    procedures["visit_id"] = [_identifier(p, d) for p, d in zip(patient_key, date_key)]
    procedures["appointment_id"] = [
        _identifier(p, d, t, m) for p, d, t, m in zip(patient_key, date_key, scheduled_key, modality_key)
    ]
    procedures["session_id"] = [
        _identifier(p, d, t, m, doctor, room, entry, exit_)
        for p, d, t, m, doctor, room, entry, exit_ in zip(
            patient_key, date_key, scheduled_key, modality_key, physician_key, room_key, room_in_key, room_out_key
        )
    ]
    procedures["procedure_id"] = [
        _identifier(session, row) for session, row in zip(procedures["session_id"], procedures["source_row"])
    ]

    def calculate(
        name: str,
        end: str,
        start: str,
        clip_zero: bool = False,
        allow_overnight: bool = True,
    ) -> None:
        if end in procedures and start in procedures:
            values = _minutes_between(procedures[end], procedures[start], allow_overnight=allow_overnight)
            procedures[name] = values.clip(lower=0) if clip_zero else values.where(values.ge(0))

    # Chegadas antecipadas são legítimas e representam atraso zero. Não são virada de dia.
    calculate(
        "patient_delay_min",
        "clinic_entry_time_dt",
        "scheduled_time_dt",
        clip_zero=True,
        allow_overnight=False,
    )
    calculate("wait_to_exam_min", "room_entry_time_dt", "clinic_entry_time_dt")
    calculate(
        "start_delay_min",
        "room_entry_time_dt",
        "scheduled_time_dt",
        clip_zero=True,
        allow_overnight=False,
    )
    calculate("exam_duration_min", "room_exit_time_dt", "room_entry_time_dt")
    calculate("after_exam_min", "clinic_exit_time_dt", "room_exit_time_dt")
    calculate("total_stay_min", "clinic_exit_time_dt", "clinic_entry_time_dt")
    if "result_delivered_time_dt" in procedures and "room_exit_time_dt" in procedures:
        procedures["result_delivery_min"] = (
            procedures["result_delivered_time_dt"] - procedures["room_exit_time_dt"]
        ).dt.total_seconds() / 60

    session_agg: dict[str, tuple[str, str]] = {
        "patient_id": ("patient_id", "first"), "visit_id": ("visit_id", "first"),
        "appointment_id": ("appointment_id", "first"), "service_date": ("service_date", "first"),
        "scheduled_time": ("scheduled_time", "first"), "patient_name": ("patient_name", "first"),
        "procedure_count": ("procedure_id", "size"),
    }
    for field in ("clinic", "modality", "room", "physician", "insurer", "clinic_entry_time_dt", "room_entry_time_dt", "room_exit_time_dt", "clinic_exit_time_dt", "patient_delay_min", "wait_to_exam_min", "start_delay_min", "exam_duration_min", "after_exam_min", "total_stay_min", "result_delivery_min", "session_quantity_num"):
        if field in procedures:
            session_agg[field] = (field, "first")
    sessions = procedures.groupby("session_id", as_index=False).agg(**session_agg)
    if "session_quantity_num" in sessions:
        sessions["quantity_matches"] = sessions["session_quantity_num"].eq(sessions["procedure_count"])

    appointments = sessions.groupby("appointment_id", as_index=False).agg(
        patient_id=("patient_id", "first"), visit_id=("visit_id", "first"),
        service_date=("service_date", "first"), scheduled_time=("scheduled_time", "first"),
        session_count=("session_id", "size"), procedure_count=("procedure_count", "sum"),
    )
    visits = sessions.groupby("visit_id", as_index=False).agg(
        patient_id=("patient_id", "first"), service_date=("service_date", "first"),
        first_entry=("clinic_entry_time_dt", "min") if "clinic_entry_time_dt" in sessions else ("service_date", "first"),
        last_exit=("clinic_exit_time_dt", "max") if "clinic_exit_time_dt" in sessions else ("service_date", "first"),
        session_count=("session_id", "size"), procedure_count=("procedure_count", "sum"),
    )

    issues: list[dict[str, object]] = []
    footer_count = int((~valid).sum())
    if footer_count:
        issues.append({"severity": "info", "rule": "non_operational_rows", "count": footer_count, "description": "Linhas de rodapé ou sem campos operacionais foram ignoradas."})
    if "quantity_matches" in sessions:
        mismatches = int((~sessions["quantity_matches"].fillna(False)).sum())
        if mismatches:
            issues.append({"severity": "warning", "rule": "session_quantity_mismatch", "count": mismatches, "description": "Sessões em que Qte difere do número de procedimentos agrupados."})
    for metric in ("wait_to_exam_min", "exam_duration_min", "total_stay_min"):
        if metric in procedures:
            impossible = int(procedures[metric].isna().sum() - procedures[metric.replace("_min", "")].isna().sum()) if metric.replace("_min", "") in procedures else 0
            if impossible > 0:
                issues.append({"severity": "warning", "rule": f"negative_{metric}", "count": impossible, "description": "Intervalo negativo não foi usado no indicador."})
    if "result_delivery_min" in procedures:
        negative_delivery = int(procedures["result_delivery_min"].lt(0).sum())
        if negative_delivery:
            issues.append({"severity": "warning", "rule": "delivery_before_exam_end", "count": negative_delivery, "description": "Entrega registrada antes do término do exame; requer auditoria da origem."})
    quality = pd.DataFrame(issues, columns=["severity", "rule", "count", "description"])

    return AnalysisResult(raw, procedures, sessions, appointments, visits, quality, metadata, mapping, confidence, set())
