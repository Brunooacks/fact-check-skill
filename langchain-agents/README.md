# 🤖 LangChain Agents — para testar governança de agentes (Veltrix)

Dois agentes **LangChain** com funções e responsabilidades distintas, cada um
rodando como **worker/CLI** dentro de **Docker**, com uma camada de **identidade
+ telemetria genérica** pronta para você plugar na **sua** plataforma de
governança. Inclui um **harness de avaliação** que mede desempenho e propósito.

> A plataforma de governança **não** está incluída — o projeto expõe apenas o
> ponto de integração (identidade + trilha de auditoria + policy hook via REST).
> Você conecta a sua plataforma trocando uma env var (`GOVERNANCE_URL`).

---

## Os agentes

| Agente | Papel | O que faz |
|---|---|---|
| **banking-benchmark-agent** | `banking_product_benchmarking` | Compara produtos bancários entre instituições, calcula competitividade e recomenda a melhor opção. |
| **lead-mapper-agent** | `lead_opportunity_mapping` | Mapeia empresas que usam muito APIs de IA, enriquece, pontua o fit e gera oportunidades quentes para a Veltrix. |

Cada agente tem uma **identidade declarativa** (`identity.yaml`): `agent_id`
estável, papel, capacidades, `allowed_tools`, escopos de dados, nível de risco e
tags. É esse manifesto que se apresenta à plataforma de governança no registro.

---

## Rodando com Docker (recomendado)

```bash
cd langchain-agents
cp .env.example .env          # opcional: preencha ANTHROPIC_API_KEY e GOVERNANCE_URL

# Um agente específico
docker compose run --rm banking-benchmark
docker compose run --rm lead-mapper

# Tarefa customizada
docker compose run --rm lead-mapper agents.lead_mapper.worker --print \
  --task "Priorize prospects de healthtech regulada para a Veltrix"

# Avaliar desempenho e propósito dos dois (scorecard)
docker compose run --rm evaluate
```

A trilha de auditoria de cada execução é gravada em `./audit/<agent_id>.jsonl`
(montado do container), para você inspecionar tudo o que o agente fez.

## Rodando localmente (sem Docker)

```bash
./scripts/run_local.sh banking
./scripts/run_local.sh leads "Mapeie prospects de fintech"
# avaliação
python -m core.evaluation --agent all
```

---

## Modo de LLM

- **Com `ANTHROPIC_API_KEY`** → LangChain + **Claude** (tool-calling real via
  `create_tool_calling_agent` / `AgentExecutor`). Modelo em `LLM_MODEL`
  (default `claude-sonnet-5`).
- **Sem chave** → **modo stub determinístico**: o agente executa um plano fixo de
  ferramentas. Serve para testar identidade, ferramentas e governança **sem
  gastar tokens** nem depender de rede. Ideal para validar sua plataforma.

---

## Integração com sua plataforma de governança

Defina no `.env`:

```bash
GOVERNANCE_URL=https://sua-plataforma.example
AGENT_CREDENTIAL=<token do agente>   # vai como Bearer
GOVERNANCE_STRICT=true               # aborta se registro/policy for recusado
```

O cliente (`governance/client.py`) chama, se a URL estiver definida:

| Momento | Chamada |
|---|---|
| Boot | `POST /agents/register` (envia o manifesto de identidade) |
| Antes de cada ferramenta / da execução | `POST /policy/evaluate` → `{allow, reason}` |
| Cada passo (LLM, tool, ação, resultado) | `POST /agents/{id}/events` |
| Heartbeat / encerramento | `POST /agents/{id}/heartbeat`, `/shutdown` |

Se a URL **não** estiver definida, tudo funciona local (auditoria em JSONL +
política do `governance/policies.yaml`). Governança nunca derruba o agente,
exceto em `GOVERNANCE_STRICT=true`.

---

## Avaliação — desempenho e propósito

`python -m core.evaluation` roda cenários declarativos por agente
(`agents/*/evals.py`) e produz um **scorecard**:

- **capability** — as ferramentas/decisões estão corretas? (asserts sobre JSON)
- **purpose** — o agente ponta-a-ponta entrega o resultado esperado?
- **desempenho** — latência por cenário, nº de chamadas de ferramenta, sucesso.

Exit code ≠ 0 se algum cenário falhar (plugável em CI).

```
╭─ Scorecard: banking-benchmark-agent (banking)
│  propósito: 100.0%   capacidade: 100.0%   geral: 100.0%
│  latência média: 1.0ms   máx: 3.2ms   (5/5 cenários ok)
```

---

## Estrutura

```
langchain-agents/
├── Dockerfile                 # imagem única; o agente é escolhido no command
├── docker-compose.yml         # banking-benchmark | lead-mapper | evaluate
├── requirements.txt
├── .env.example
├── governance/                # ponto de integração (NÃO é a plataforma)
│   ├── identity.py            # AgentIdentity + manifesto
│   ├── client.py              # registro, policy, telemetria (REST + JSONL local)
│   ├── callbacks.py           # LangChain callbacks → eventos de auditoria
│   └── policies.yaml          # política local (fallback offline)
├── core/
│   ├── llm.py                 # factory Claude + fallback stub
│   ├── worker.py              # base do worker governado (CLI)
│   └── evaluation.py          # harness de avaliação (scorecard)
├── agents/
│   ├── banking_benchmark/     # identity.yaml · tools.py · worker.py · evals.py
│   └── lead_mapper/           # identity.yaml · tools.py · worker.py · evals.py
└── scripts/run_local.sh
```

## Adaptando para dados reais

As ferramentas usam datasets **simulados e determinísticos**. Para produção,
troque o corpo de cada `@tool` em `agents/*/tools.py` por chamadas às suas fontes
reais (APIs de bancos, enriquecimento firmográfico, CRM) — a assinatura das
ferramentas, a identidade e a governança permanecem idênticas.
