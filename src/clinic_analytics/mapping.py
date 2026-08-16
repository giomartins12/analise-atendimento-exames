from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable


ALIASES: dict[str, tuple[str, ...]] = {
    "service_date": ("data", "data exame", "data atendimento"),
    "scheduled_time": ("hora", "hora agendada", "horario agendado"),
    "expected_arrival_time": ("h chegada", "hora chegada"),
    "patient_name": ("paciente", "nome paciente"),
    "clinic": ("empresa", "clinica", "unidade"),
    "modality": ("modalidade",),
    "room": ("sala",),
    "physician": ("medico executante", "médico executante", "executante"),
    "procedure": ("procedimento", "exame"),
    "plan": ("plano",),
    "insurer": ("convenio", "convênio"),
    "session_quantity": ("qte", "quantidade"),
    "interview_time": ("h entrevista", "hora entrevista"),
    "clinic_entry_time": ("h entrada", "hora entrada"),
    "ticket_time": ("h senha", "hora senha"),
    "registration_time": ("h ficha", "hora ficha"),
    "room_entry_time": ("h e sala", "hora entrada sala", "inicio exame"),
    "room_exit_time": ("h s sala", "hora saida sala", "fim exame"),
    "clinic_exit_time": ("h saida", "hora saida"),
    "source_prep_delay": ("t atraso preparo",),
    "source_room_delay": ("t atraso sala",),
    "source_patient_delay": ("t atraso paciente",),
    "source_ticket_wait": ("t e senha",),
    "source_registration_time": ("t e ficha",),
    "source_room_wait": ("t e sala",),
    "source_exam_duration": ("t e exame",),
    "source_total_stay": ("t total",),
    "receptionist": ("recepcao", "recepção", "recepcionista"),
    "has_report": ("laudo", "laudo?"),
    "report_time": ("d laudo", "data laudo"),
    "report_signed_time": ("d assinado", "data assinado"),
    "result_delivered_time": ("d entrega realizado", "data entrega realizado"),
}

REQUIRED_FIELDS = {"service_date", "scheduled_time", "patient_name", "procedure"}


def normalized_label(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value).strip().casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def infer_mapping(columns: Iterable[str]) -> tuple[dict[str, str], dict[str, float]]:
    normalized_columns = {normalized_label(column): column for column in columns}
    mapping: dict[str, str] = {}
    confidence: dict[str, float] = {}
    for concept, aliases in ALIASES.items():
        normalized_aliases = [normalized_label(alias) for alias in aliases]
        exact = next((normalized_columns[a] for a in normalized_aliases if a in normalized_columns), None)
        if exact:
            mapping[concept] = exact
            confidence[concept] = 1.0
            continue
        partial = next(
            (original for label, original in normalized_columns.items() if any(a in label for a in normalized_aliases)),
            None,
        )
        if partial:
            mapping[concept] = partial
            confidence[concept] = 0.7
    return mapping, confidence


def save_mapping(mapping: dict[str, str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")


def load_mapping(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(key): str(value) for key, value in data.items()}

