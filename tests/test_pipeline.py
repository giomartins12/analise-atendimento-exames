from __future__ import annotations

from clinic_analytics.ingestion import detect_delimiter, detect_encoding
from clinic_analytics.pipeline import analyze_csv


HEADER = (
    "Data;Hora;H. Chegada;Paciente;Empresa;Modalidade;Sala;Médico Executante;Procedimento;"
    "Plano;Convênio;Qte;H. Entrevista;H. Entrada;H. Senha;H. Ficha;H. E. Sala;H. S. Sala;"
    "H. Saída;T. Atraso Preparo;T. Atraso Sala;T. Atraso Paciente;T. E. Senha;T. E. Ficha;"
    "T. E. Sala;T. E. Exame;T. Total;Recepção;Laudo?;D. Laudo;D. Assinado;D. Entrega Realizado"
)


def csv_bytes(rows: list[str]) -> bytes:
    return (HEADER + "\n" + "\n".join(rows)).encode("cp1252")


def test_detects_cp1252_and_semicolon() -> None:
    content = "Paciente;Convênio\nJosé;Saúde".encode("cp1252")
    assert detect_encoding(content) == "cp1252"
    assert detect_delimiter(content.decode("cp1252")) == ";"


def test_homologated_entities_and_patient_delay() -> None:
    base = "01/07/2026;09:00:00;09:00:00;PACIENTE A;CLÍNICA;US;SALA 1;MÉDICO A;{};PARTICULAR;PARTICULAR;2;;09:15:00;09:15:10;09:20:00;09:30:00;09:40:00;09:45:00;00:30;00:30;00:00;00:00;00:05;00:10;00:10;00:30;ATENDENTE;True;01/07/2026 09:45;01/07/2026 10:00;01/07/2026 10:10"
    result = analyze_csv(csv_bytes([base.format("EXAME A"), base.format("EXAME B")]))
    assert len(result.procedures) == 2
    assert len(result.sessions) == 1
    assert len(result.appointments) == 1
    assert len(result.visits) == 1
    assert result.sessions.iloc[0]["procedure_count"] == 2
    assert result.sessions.iloc[0]["quantity_matches"]
    assert result.sessions.iloc[0]["patient_delay_min"] == 15
    assert result.sessions.iloc[0]["exam_duration_min"] == 10


def test_footer_is_ignored() -> None:
    row = "01/07/2026;09:00:00;09:00:00;A;CLÍNICA;US;S1;M1;E1;P;P;1;;09:00:00;;;09:10:00;09:20:00;09:30:00;;;;;;;;A;False;;;"
    footer = ";;;;;;;;;;;;;;;;;;;;;;;;;;01:25;;;;;"
    result = analyze_csv(csv_bytes([row, footer]))
    assert len(result.procedures) == 1
    assert result.quality.loc[result.quality["rule"].eq("non_operational_rows"), "count"].item() == 1


def test_patient_name_normalization_prevents_inflated_count() -> None:
    first = "01/07/2026;09:00:00;09:00:00;José da Silva;C;US;S1;M1;E1;P;P;1;;09:00:00;;;09:10:00;09:20:00;09:30:00;;;;;;;;A;False;;;"
    second = "02/07/2026;09:00:00;09:00:00; JOSE  DA SILVA ;C;US;S1;M1;E1;P;P;1;;09:00:00;;;09:10:00;09:20:00;09:30:00;;;;;;;;A;False;;;"
    result = analyze_csv(csv_bytes([first, second]))
    assert result.procedures["patient_id"].nunique() == 1
    assert len(result.visits) == 2


def test_early_arrival_is_not_treated_as_next_day() -> None:
    row = "01/07/2026;09:00:00;09:00:00;A;C;US;S1;M1;E1;P;P;1;;08:40:00;;;09:10:00;09:20:00;09:30:00;;;;;;;;A;False;;;"
    result = analyze_csv(csv_bytes([row]))
    assert result.sessions.iloc[0]["patient_delay_min"] == 0
    assert result.sessions.iloc[0]["start_delay_min"] == 10
