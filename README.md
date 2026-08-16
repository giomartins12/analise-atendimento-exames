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
- detecção de sobreposições de sala e médico;
- ocupação observada, tempo ocioso e horários de pico;
- limites configuráveis para atraso e espera;
- exportações gerenciais com privacidade.

## Executar no Windows 11

Requer Python 3.12 ou superior. O script detecta automaticamente o Python Launcher (`py`), `python` ou `python3`.

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

O `run.ps1` cria o ambiente virtual, instala as dependências e abre a aplicação. Python 3.13 e 3.14 também são aceitos quando as dependências disponibilizam versões compatíveis.

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
