from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from clinic_analytics.mapping import ALIASES, load_mapping, save_mapping  # noqa: E402
from clinic_analytics.analytics import (  # noqa: E402
    WEEKDAYS_PT,
    coverage_table,
    daily_exam_patient_relation,
    demand_by_procedure_weekday_hour,
    demand_by_weekday_hour,
    find_overlaps,
    management_export,
    resource_summary,
)
from clinic_analytics.history import load_history, save_snapshot  # noqa: E402
from clinic_analytics.pipeline import analyze_csv  # noqa: E402
from clinic_analytics.reporting import build_snapshot, generate_report  # noqa: E402

MAPPING_PATH = ROOT / ".clinic_analytics" / "mapping.json"
HISTORY_PATH = ROOT / ".clinic_analytics" / "history.sqlite3"

st.set_page_config(page_title="Análise de Atendimentos", page_icon="🏥", layout="wide")
st.title("Análise de Atendimento e Exames")
st.caption("Processamento 100% local. A planilha não é enviada para serviços externos.")

with st.sidebar:
    st.header("Arquivo e filtros")
    upload = st.file_uploader("Selecione o CSV", type=["csv"])
    privacy_mode = st.toggle("Modo privacidade", value=True, help="Oculta nomes nas visualizações detalhadas.")
    st.subheader("Limites operacionais")
    start_delay_limit = st.number_input("Início no prazo até (min)", min_value=0, value=10, step=5)
    wait_limit = st.number_input("Espera excessiva acima de (min)", min_value=0, value=30, step=5)

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
history = load_history(HISTORY_PATH)
history_snapshot = build_snapshot(
    content,
    result.sessions,
    result.procedures,
    result.visits,
    result.appointments,
    result.quality,
    start_delay_limit,
    wait_limit,
)
current_snapshot = build_snapshot(
    content,
    sessions,
    procedures,
    filtered_visits,
    filtered_appointments,
    result.quality,
    start_delay_limit,
    wait_limit,
)

metrics = st.columns(5)
metrics[0].metric("Pacientes únicos", sessions["patient_id"].nunique())
metrics[1].metric("Visitas", filtered_visits["visit_id"].nunique())
metrics[2].metric("Agendamentos", filtered_appointments["appointment_id"].nunique())
metrics[3].metric("Sessões", sessions["session_id"].nunique())
metrics[4].metric("Procedimentos", procedures["procedure_id"].nunique())

time_metrics = st.columns(4)
median_wait = sessions["wait_to_exam_min"].median() if "wait_to_exam_min" in sessions else float("nan")
median_duration = sessions["exam_duration_min"].median() if "exam_duration_min" in sessions else float("nan")
on_time = sessions["start_delay_min"].le(start_delay_limit).mean() * 100 if "start_delay_min" in sessions else float("nan")
excess_wait = sessions["wait_to_exam_min"].gt(wait_limit).mean() * 100 if "wait_to_exam_min" in sessions else float("nan")
time_metrics[0].metric("Espera mediana", f"{median_wait:.1f} min" if pd.notna(median_wait) else "Sem dados")
time_metrics[1].metric("Duração mediana", f"{median_duration:.1f} min" if pd.notna(median_duration) else "Sem dados")
time_metrics[2].metric("Início dentro do limite", f"{on_time:.1f}%" if pd.notna(on_time) else "Sem dados")
time_metrics[3].metric("Espera acima do limite", f"{excess_wait:.1f}%" if pd.notna(excess_wait) else "Sem dados")

tab_overview, tab_times, tab_resources, tab_reports, tab_quality, tab_analysis_report, tab_history, tab_details = st.tabs(
    ["Visão geral", "Tempos", "Salas e médicos", "Laudos", "Qualidade", "Relatório", "Histórico", "Detalhes"]
)

with tab_overview:
    daily, daily_correlation = daily_exam_patient_relation(procedures)
    relationship_metrics = st.columns(2)
    ratio = len(procedures) / procedures["patient_id"].nunique() if procedures["patient_id"].nunique() else float("nan")
    relationship_metrics[0].metric("Procedimentos por paciente", f"{ratio:.2f}" if pd.notna(ratio) else "Sem dados")
    relationship_metrics[1].metric("Correlação diária", f"{daily_correlation:.2f}" if pd.notna(daily_correlation) else "Sem dados")
    st.plotly_chart(
        px.line(
            daily,
            x="service_date",
            y=["procedures", "patients"],
            markers=True,
            title="Procedimentos e pacientes por dia",
            labels={"value": "Quantidade", "service_date": "Data", "variable": "Indicador"},
        ),
        use_container_width=True,
    )
    st.caption("Compara o volume diário de procedimentos com pacientes únicos. A diferença entre as linhas mostra quantos pacientes realizaram mais de um procedimento no mesmo dia.")
    st.plotly_chart(
        px.scatter(
            daily,
            x="patients",
            y="procedures",
            hover_data=["service_date", "procedures_per_patient"],
            title="Relação diária entre pacientes e procedimentos",
            labels={"patients": "Pacientes únicos", "procedures": "Procedimentos", "service_date": "Data", "procedures_per_patient": "Procedimentos/paciente"},
        ),
        use_container_width=True,
    )
    st.caption("Cada ponto representa um dia. A correlação mostra quanto o volume de procedimentos acompanha o número de pacientes; ela não demonstra causalidade.")
    volume = procedures.groupby("procedure", as_index=False).size().sort_values("size", ascending=False)
    st.plotly_chart(px.bar(volume.head(15), x="size", y="procedure", orientation="h", title="Procedimentos com maior volume", labels={"size": "Procedimentos", "procedure": "Exame"}), use_container_width=True)
    st.caption("Ranking dos 15 procedimentos mais realizados no período filtrado. Cada linha válida do CSV conta como um procedimento.")
    demand = demand_by_weekday_hour(sessions)
    if not demand.empty:
        weekday_order = [WEEKDAYS_PT[index] for index in range(7) if WEEKDAYS_PT[index] in demand["weekday"].unique()]
        st.plotly_chart(
            px.density_heatmap(
                demand,
                x="hour",
                y="weekday",
                z="sessions",
                histfunc="sum",
                category_orders={"weekday": weekday_order},
                labels={"hour": "Hora agendada", "weekday": "Dia da semana", "sessions": "Sessões"},
                title="Demanda por dia da semana e horário",
            ),
            use_container_width=True,
        )
        st.caption("A intensidade da cor representa o número de sessões agendadas em cada combinação de dia da semana e hora. Tons mais escuros indicam maior demanda.")
    procedure_demand = demand_by_procedure_weekday_hour(procedures)
    if not procedure_demand.empty:
        procedure_choices = sorted(procedure_demand["procedure"].unique().tolist())
        selected_procedure = st.selectbox("Procedimento para analisar por dia e horário", procedure_choices)
        selected_demand = procedure_demand[procedure_demand["procedure"].eq(selected_procedure)]
        weekday_order = [WEEKDAYS_PT[index] for index in range(7) if WEEKDAYS_PT[index] in selected_demand["weekday"].unique()]
        st.plotly_chart(
            px.density_heatmap(
                selected_demand,
                x="hour",
                y="weekday",
                z="procedures",
                histfunc="sum",
                category_orders={"weekday": weekday_order},
                labels={"hour": "Hora agendada", "weekday": "Dia da semana", "procedures": "Procedimentos"},
                title=f"Demanda de {selected_procedure} por dia e horário",
            ),
            use_container_width=True,
        )
        st.caption("Mostra em quais dias e horários o procedimento selecionado é mais realizado. A contagem é de procedimentos, não de sessões ou pacientes.")

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
    st.info("Cobertura é a quantidade de sessões que possuem todos os horários necessários para calcular o indicador. Ela varia porque alguns registros não têm entrada, início, término ou saída preenchidos.")
    st.dataframe(pd.DataFrame(summary_rows).round(1), hide_index=True, use_container_width=True)
    if "exam_duration_min" in sessions:
        st.plotly_chart(px.box(sessions, x="modality" if "modality" in sessions else None, y="exam_duration_min", points="outliers", title="Distribuição da duração por modalidade", labels={"exam_duration_min": "Duração (min)", "modality": "Modalidade"}), use_container_width=True)
        st.caption("A caixa representa a faixa central das durações; a linha interna é a mediana e os pontos isolados são valores extremos que merecem verificação, mas não são necessariamente erros.")

with tab_resources:
    room_summary = resource_summary(sessions, "room") if "room" in sessions else pd.DataFrame()
    physician_summary = resource_summary(sessions, "physician") if "physician" in sessions else pd.DataFrame()
    room_overlaps = find_overlaps(sessions, "room") if "room" in sessions else pd.DataFrame()
    physician_overlaps = find_overlaps(sessions, "physician") if "physician" in sessions else pd.DataFrame()
    overlap_metrics = st.columns(2)
    overlap_metrics[0].metric("Sobreposições de sala", len(room_overlaps))
    overlap_metrics[1].metric("Sobreposições de médico", len(physician_overlaps))
    st.caption("Sobreposição indica intervalos simultâneos e deve ser auditada; não significa automaticamente erro operacional.")
    left, right = st.columns(2)
    if "room" in sessions:
        left.plotly_chart(px.bar(room_summary, x="room", y="sessions", title="Sessões por sala", labels={"room": "Sala", "sessions": "Sessões"}), use_container_width=True)
        left.caption("Compara o número de sessões realizadas em cada sala. Volume não equivale à ocupação, pois as durações variam.")
        left.dataframe(room_summary.round(1), hide_index=True, use_container_width=True)
    if "physician" in sessions:
        right.plotly_chart(px.bar(physician_summary, x="physician", y="sessions", title="Sessões por médico", labels={"physician": "Médico", "sessions": "Sessões"}), use_container_width=True)
        right.caption("Compara a quantidade de sessões por médico executante. Não mede complexidade, carga contratual ou qualidade clínica.")
        right.dataframe(physician_summary.round(1), hide_index=True, use_container_width=True)

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
    coverage = coverage_table(procedures)
    st.info("Preenchimento (%) indica a proporção de procedimentos com valor disponível em cada campo. Ausência não é convertida em zero.")
    st.dataframe(coverage.round(1), hide_index=True, use_container_width=True)

with tab_analysis_report:
    report_markdown = generate_report(current_snapshot, procedures, result.quality, history)
    st.markdown(report_markdown)
    st.download_button(
        "Baixar relatório em Markdown",
        data=report_markdown.encode("utf-8"),
        file_name=f"relatorio-{current_snapshot['period_label']}.md",
        mime="text/markdown",
    )
    st.caption("O relatório é gerado localmente com os filtros atuais e documenta resultados, metodologia, relações e alertas de qualidade.")

with tab_history:
    st.info("O histórico guarda somente indicadores mensais agregados no computador. Nomes, linhas individuais e o CSV original não são armazenados.")
    if st.button(f"Registrar ou atualizar {history_snapshot['period_label']} no histórico", type="primary"):
        action = save_snapshot(HISTORY_PATH, history_snapshot)
        history = load_history(HISTORY_PATH)
        if action == "created":
            st.success("Mês registrado no histórico.")
        else:
            st.success("Mês atualizado no histórico com a versão mais recente da planilha.")
    if history.empty:
        st.warning("Nenhum mês foi registrado ainda. Use o botão acima após conferir a análise.")
    else:
        history_chart = history.rename(columns={"period_label": "Mês", "patients": "Pacientes", "procedures": "Procedimentos"})
        st.plotly_chart(
            px.line(
                history_chart,
                x="Mês",
                y=["Pacientes", "Procedimentos"],
                markers=True,
                title="Evolução mensal de pacientes e procedimentos",
                labels={"value": "Quantidade", "variable": "Indicador"},
            ),
            use_container_width=True,
        )
        st.caption("Compara os totais consolidados dos meses registrados. O mês é substituído, e não duplicado, quando uma planilha corrigida do mesmo período é registrada novamente.")
        st.plotly_chart(
            px.line(
                history,
                x="period_label",
                y="procedures_per_patient",
                markers=True,
                title="Procedimentos por paciente ao longo dos meses",
                labels={"period_label": "Mês", "procedures_per_patient": "Procedimentos por paciente"},
            ),
            use_container_width=True,
        )
        st.caption("Mostra a intensidade média do atendimento: valores maiores indicam mais procedimentos realizados por paciente no mês.")
        history_display = history.drop(columns=["file_hash"], errors="ignore").rename(
            columns={
                "period_label": "Mês", "patients": "Pacientes", "visits": "Visitas",
                "appointments": "Agendamentos", "sessions": "Sessões", "procedures": "Procedimentos",
                "procedures_per_patient": "Procedimentos/paciente", "saved_at": "Registrado em",
            }
        )
        st.dataframe(history_display, hide_index=True, use_container_width=True)

with tab_details:
    visible = ["service_date", "scheduled_time", "procedure", "modality", "room", "physician", "insurer", "patient_delay_min", "wait_to_exam_min", "exam_duration_min", "total_stay_min"]
    if not privacy_mode:
        visible.insert(2, "patient_name")
    visible = [column for column in visible if column in procedures]
    st.dataframe(procedures[visible], hide_index=True, use_container_width=True)
    st.subheader("Exportações")
    exports = management_export(sessions, procedures, privacy_mode=privacy_mode)
    export_columns = st.columns(len(exports))
    for column, (filename, data) in zip(export_columns, exports.items()):
        column.download_button(
            f"Baixar {filename}",
            data=data,
            file_name=filename,
            mime="text/csv",
            use_container_width=True,
        )
    if privacy_mode:
        st.caption("As exportações estão sem nomes de pacientes porque o modo privacidade está ativo.")
