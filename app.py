from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from clinic_analytics.mapping import ALIASES, load_mapping, save_mapping  # noqa: E402
from clinic_analytics.pipeline import analyze_csv  # noqa: E402

MAPPING_PATH = ROOT / ".clinic_analytics" / "mapping.json"

st.set_page_config(page_title="Análise de Atendimentos", page_icon="🏥", layout="wide")
st.title("Análise de Atendimento e Exames")
st.caption("Processamento 100% local. A planilha não é enviada para serviços externos.")

with st.sidebar:
    st.header("Arquivo e filtros")
    upload = st.file_uploader("Selecione o CSV", type=["csv"])
    privacy_mode = st.toggle("Modo privacidade", value=True, help="Oculta nomes nas visualizações detalhadas.")

if upload is None:
    st.info("Selecione um arquivo CSV para iniciar a análise.")
    st.stop()

content = upload.getvalue()
initial = analyze_csv(content, load_mapping(MAPPING_PATH))

with st.expander("Mapeamento das colunas", expanded=bool(initial.missing_required)):
    options = [""] + list(initial.raw.columns)
    edited_mapping: dict[str, str] = {}
    columns = st.columns(2)
    for index, concept in enumerate(ALIASES):
        current = initial.mapping.get(concept, "")
        selected = columns[index % 2].selectbox(
            concept,
            options,
            index=options.index(current) if current in options else 0,
            key=f"map_{concept}",
        )
        if selected:
            edited_mapping[concept] = selected
    if st.button("Salvar mapeamento neste computador"):
        save_mapping(edited_mapping, MAPPING_PATH)
        st.success("Mapeamento salvo localmente.")

result = analyze_csv(content, edited_mapping)
if result.missing_required:
    st.error("Campos obrigatórios sem mapeamento: " + ", ".join(sorted(result.missing_required)))
    st.stop()

sessions = result.sessions
procedures = result.procedures
with st.sidebar:
    dates = sorted(sessions["service_date"].dt.date.unique())
    selected_dates = st.date_input("Período", value=(dates[0], dates[-1]), min_value=dates[0], max_value=dates[-1])
    if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
        start, end = selected_dates
        sessions = sessions[sessions["service_date"].dt.date.between(start, end)]
        procedures = procedures[procedures["service_date"].dt.date.between(start, end)]
    for label, field in (("Modalidade", "modality"), ("Sala", "room"), ("Convênio", "insurer"), ("Médico", "physician")):
        if field in sessions:
            choices = sorted(sessions[field].dropna().unique().tolist())
            selected = st.multiselect(label, choices)
            if selected:
                allowed_sessions = sessions.loc[sessions[field].isin(selected), "session_id"]
                sessions = sessions[sessions["session_id"].isin(allowed_sessions)]
                procedures = procedures[procedures["session_id"].isin(allowed_sessions)]

filtered_visits = result.visits[result.visits["visit_id"].isin(sessions["visit_id"])]
filtered_appointments = result.appointments[result.appointments["appointment_id"].isin(sessions["appointment_id"])]

metrics = st.columns(5)
metrics[0].metric("Pacientes únicos", sessions["patient_id"].nunique())
metrics[1].metric("Visitas", filtered_visits["visit_id"].nunique())
metrics[2].metric("Agendamentos", filtered_appointments["appointment_id"].nunique())
metrics[3].metric("Sessões", sessions["session_id"].nunique())
metrics[4].metric("Procedimentos", procedures["procedure_id"].nunique())

tab_overview, tab_times, tab_resources, tab_reports, tab_quality, tab_details = st.tabs(
    ["Visão geral", "Tempos", "Salas e médicos", "Laudos", "Qualidade", "Detalhes"]
)

with tab_overview:
    daily = sessions.groupby("service_date", as_index=False).agg(sessoes=("session_id", "nunique"), pacientes=("patient_id", "nunique"))
    st.plotly_chart(px.line(daily, x="service_date", y=["sessoes", "pacientes"], markers=True, labels={"value": "Quantidade", "service_date": "Data", "variable": "Indicador"}), use_container_width=True)
    volume = procedures.groupby("procedure", as_index=False).size().sort_values("size", ascending=False)
    st.plotly_chart(px.bar(volume.head(15), x="size", y="procedure", orientation="h", labels={"size": "Procedimentos", "procedure": "Exame"}), use_container_width=True)

with tab_times:
    labels = {
        "patient_delay_min": "Atraso do paciente", "wait_to_exam_min": "Espera até o exame",
        "start_delay_min": "Atraso para início", "exam_duration_min": "Duração do exame",
        "after_exam_min": "Tempo após exame", "total_stay_min": "Permanência total",
    }
    summary_rows = []
    for field, label in labels.items():
        if field in sessions:
            values = sessions[field].dropna()
            summary_rows.append({"Indicador": label, "Cobertura": len(values), "Média (min)": values.mean(), "Mediana (min)": values.median(), "P95 (min)": values.quantile(.95), "Máximo (min)": values.max()})
    st.dataframe(pd.DataFrame(summary_rows).round(1), hide_index=True, use_container_width=True)
    if "exam_duration_min" in sessions:
        st.plotly_chart(px.box(sessions, x="modality" if "modality" in sessions else None, y="exam_duration_min", points="outliers", labels={"exam_duration_min": "Duração (min)", "modality": "Modalidade"}), use_container_width=True)

with tab_resources:
    left, right = st.columns(2)
    if "room" in sessions:
        by_room = sessions.groupby("room", as_index=False).agg(sessoes=("session_id", "size"), minutos_ocupados=("exam_duration_min", "sum"))
        left.plotly_chart(px.bar(by_room, x="room", y="sessoes", labels={"room": "Sala", "sessoes": "Sessões"}), use_container_width=True)
    if "physician" in sessions:
        by_physician = sessions.groupby("physician", as_index=False).agg(sessoes=("session_id", "size"), procedimentos=("procedure_count", "sum"))
        right.plotly_chart(px.bar(by_physician, x="physician", y="sessoes", labels={"physician": "Médico", "sessoes": "Sessões"}), use_container_width=True)

with tab_reports:
    if "has_report_bool" in procedures:
        report_counts = procedures["has_report_bool"].value_counts(dropna=False).rename_axis("Possui laudo").reset_index(name="Procedimentos")
        st.dataframe(report_counts, hide_index=True, use_container_width=True)
    if "result_delivery_min" in sessions:
        values = sessions["result_delivery_min"].dropna()
        st.metric("Mediana até entrega efetiva", f"{values.median():.0f} min" if len(values) else "Sem dados")
        st.caption("Valores negativos permanecem na auditoria e não devem ser interpretados como prazo válido.")

with tab_quality:
    st.write(f"Codificação: `{result.metadata.encoding}` · delimitador: `{result.metadata.delimiter}` · {result.metadata.rows_read} linhas lidas")
    if result.quality.empty:
        st.success("Nenhuma inconsistência coberta pelas regras atuais foi encontrada.")
    else:
        st.dataframe(result.quality, hide_index=True, use_container_width=True)
    coverage = procedures.notna().mean().mul(100).rename("Preenchimento (%)").reset_index(names="Campo")
    st.dataframe(coverage.round(1), hide_index=True, use_container_width=True)

with tab_details:
    visible = ["service_date", "scheduled_time", "procedure", "modality", "room", "physician", "insurer", "patient_delay_min", "wait_to_exam_min", "exam_duration_min", "total_stay_min"]
    if not privacy_mode:
        visible.insert(2, "patient_name")
    visible = [column for column in visible if column in procedures]
    st.dataframe(procedures[visible], hide_index=True, use_container_width=True)

