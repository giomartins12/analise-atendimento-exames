# Análise de Atendimento e Exames

Aplicação Streamlit executada localmente para analisar o fluxo operacional de uma clínica a partir de CSV. Os dados não são enviados a APIs ou serviços externos.

## O que já está incluído no Marco 1

- detecção de delimitador e codificação;
- mapeamento automático e corrigível de colunas;
- descarte de rodapés não operacionais;
- normalização sem alteração dos valores originais;
- distinção entre pacientes, visitas, agendamentos, sessões e procedimentos;
- recálculo dos tempos a partir dos horários de origem;
- indicadores, filtros, gráficos e auditoria de qualidade;
- modo privacidade ativado por padrão;
- configuração do mapeamento salva somente no computador local;
- testes unitários das regras homologadas.

## Executar no Windows 11

Requer Python 3.12.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
streamlit run app.py
```

Ou execute `run.ps1`, que cria o ambiente e instala as dependências automaticamente.

## Regras homologadas

- paciente único: nome normalizado, pois o arquivo não possui identificador estável;
- visita: paciente + data;
- agendamento: paciente + data + hora agendada + modalidade;
- sessão: agendamento + médico + sala + entrada/saída da sala;
- procedimento: cada linha operacional válida;
- `Qte`: total de procedimentos na mesma sessão; nunca deve ser somado por linha;
- `Hora`: horário agendado;
- `H. Entrada`: chegada real à clínica;
- `H. E. Sala`: início do exame;
- `D. Entrega Realizado`: entrega efetiva do resultado;
- `Empresa`: clínica;
- atraso do paciente: `máx(H. Entrada - Hora, 0)`;
- `H. Entrevista` e `T. E. Senha`: não usados em KPIs quando vazios ou zerados.

## Privacidade

Não faça commit de planilhas reais. O `.gitignore` bloqueia formatos comuns de planilha. Nomes aparecem somente em uma tabela detalhada quando o modo privacidade é desligado pelo usuário.

