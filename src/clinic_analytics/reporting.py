from __future__ import annotations

import hashlib

import pandas as pd

from .analytics import daily_exam_patient_relation, find_overlaps


def _median(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame:
        return None
    value = frame[column].median()
    return round(float(value), 2) if pd.notna(value) else None


def build_snapshot(
    content: bytes,
    sessions: pd.DataFrame,
    procedures: pd.DataFrame,
    visits: pd.DataFrame,
    appointments: pd.DataFrame,
    quality: pd.DataFrame,
    start_delay_limit: float,
    wait_limit: float,
) -> dict[str, object]:
    period_start = procedures["service_date"].min()
    period_end = procedures["service_date"].max()
    same_month = period_start.to_period("M") == period_end.to_period("M")
    period_label = period_start.strftime("%Y-%m") if same_month else f"{period_start:%Y-%m-%d} a {period_end:%Y-%m-%d}"
    patient_count = int(procedures["patient_id"].nunique())
    on_time = sessions["start_delay_min"].le(start_delay_limit).mean() * 100 if "start_delay_min" in sessions else None
    excess_wait = sessions["wait_to_exam_min"].gt(wait_limit).mean() * 100 if "wait_to_exam_min" in sessions else None
    warnings = 0
    if not quality.empty:
        warnings = int(quality.loc[quality["severity"].eq("warning"), "count"].sum())
    return {
        "period_label": period_label,
        "period_start": period_start.date().isoformat(),
        "period_end": period_end.date().isoformat(),
        "file_hash": hashlib.sha256(content).hexdigest(),
        "patients": patient_count,
        "visits": int(visits["visit_id"].nunique()),
        "appointments": int(appointments["appointment_id"].nunique()),
        "sessions": int(sessions["session_id"].nunique()),
        "procedures": int(procedures["procedure_id"].nunique()),
        "procedures_per_patient": round(len(procedures) / patient_count, 3) if patient_count else None,
        "median_wait_min": _median(sessions, "wait_to_exam_min"),
        "median_duration_min": _median(sessions, "exam_duration_min"),
        "median_total_stay_min": _median(sessions, "total_stay_min"),
        "on_time_pct": round(float(on_time), 2) if on_time is not None and pd.notna(on_time) else None,
        "excess_wait_pct": round(float(excess_wait), 2) if excess_wait is not None and pd.notna(excess_wait) else None,
        "start_delay_limit": float(start_delay_limit),
        "wait_limit": float(wait_limit),
        "room_overlap_pairs": len(find_overlaps(sessions, "room")),
        "physician_overlap_pairs": len(find_overlaps(sessions, "physician")),
        "quality_warnings": warnings,
    }


def _fmt(value: object, decimals: int = 1) -> str:
    return "Sem dados" if value is None or pd.isna(value) else f"{float(value):.{decimals}f}"


def _correlation_text(value: float) -> str:
    if pd.isna(value):
        return "não pôde ser calculada com o período disponível"
    strength = "forte" if abs(value) >= 0.7 else "moderada" if abs(value) >= 0.4 else "fraca" if abs(value) >= 0.2 else "muito baixa"
    direction = "positiva" if value >= 0 else "negativa"
    return f"{strength} e {direction} (r = {value:.2f})"


def generate_report(
    snapshot: dict[str, object],
    procedures: pd.DataFrame,
    quality: pd.DataFrame,
    history: pd.DataFrame,
) -> str:
    daily, correlation = daily_exam_patient_relation(procedures)
    top = procedures["procedure"].value_counts().head(5)
    peak = daily.loc[daily["procedures"].idxmax()] if not daily.empty else None
    previous = history[
        (history["period_start"] < pd.Timestamp(snapshot["period_start"]))
        & history["period_label"].ne(snapshot["period_label"])
    ].tail(1)
    comparison = "Ainda não existe mês anterior registrado para comparação."
    if not previous.empty:
        row = previous.iloc[0]
        patient_delta = int(snapshot["patients"]) - int(row["patients"])
        procedure_delta = int(snapshot["procedures"]) - int(row["procedures"])
        comparison = (
            f"Em relação a **{row['period_label']}**, houve variação de **{patient_delta:+d} pacientes** "
            f"e **{procedure_delta:+d} procedimentos**."
        )
    quality_lines = "\n".join(
        f"- {row.description}: **{int(row.count)}** registro(s)." for row in quality.itertuples()
    ) or "- Nenhuma inconsistência coberta pelas regras atuais."
    top_lines = "\n".join(f"- {name}: **{int(count)}**" for name, count in top.items())
    peak_text = "Sem dados."
    if peak is not None:
        peak_text = f"{peak['service_date']:%d/%m/%Y}, com {int(peak['procedures'])} procedimentos e {int(peak['patients'])} pacientes."
    return f"""# Relatório de análise operacional — {snapshot['period_label']}

## Escopo

Período analisado: **{pd.Timestamp(snapshot['period_start']):%d/%m/%Y} a {pd.Timestamp(snapshot['period_end']):%d/%m/%Y}**.

| Indicador | Resultado |
|---|---:|
| Pacientes únicos | {snapshot['patients']} |
| Visitas | {snapshot['visits']} |
| Agendamentos | {snapshot['appointments']} |
| Sessões | {snapshot['sessions']} |
| Procedimentos | {snapshot['procedures']} |
| Procedimentos por paciente | {_fmt(snapshot['procedures_per_patient'], 2)} |

## Relação entre pacientes e procedimentos

A relação diária entre pacientes e procedimentos foi **{_correlation_text(correlation)}**. Correlação indica associação entre os volumes diários, não causalidade. O dia de maior volume foi **{peak_text}**

## Tempos operacionais

- Espera mediana até o exame: **{_fmt(snapshot['median_wait_min'])} min**.
- Duração mediana do exame: **{_fmt(snapshot['median_duration_min'])} min**.
- Permanência total mediana: **{_fmt(snapshot['median_total_stay_min'])} min**.
- Inícios dentro do limite de {snapshot['start_delay_limit']:.0f} min: **{_fmt(snapshot['on_time_pct'])}%**.
- Esperas acima de {snapshot['wait_limit']:.0f} min: **{_fmt(snapshot['excess_wait_pct'])}%**.

## Procedimentos com maior volume

{top_lines}

## Recursos e qualidade

- Pares de sessões sobrepostas por sala: **{snapshot['room_overlap_pairs']}**.
- Pares de sessões sobrepostas por médico: **{snapshot['physician_overlap_pairs']}**.

{quality_lines}

## Comparação histórica

{comparison}

## Metodologia

- Paciente único: nome normalizado, pois o CSV não possui identificador estável.
- Visita: paciente + data.
- Agendamento: paciente + data + horário agendado + modalidade.
- Sessão: agendamento + médico + sala + entrada/saída da sala.
- Procedimento: cada linha operacional válida.
- Cobertura: quantidade de sessões que possuem os horários necessários para calcular cada indicador.
- Sobreposição: intervalos simultâneos para o mesmo recurso; é um alerta de auditoria, não uma conclusão automática de erro.
- O histórico armazena somente indicadores agregados e não contém nomes ou o CSV original.
"""

