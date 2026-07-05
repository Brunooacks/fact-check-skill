# 📘 Guia passo-a-passo — configurar, executar, avaliar e integrar ao Cohort

Este guia leva você do zero até: rodar os agentes em Docker, avaliar desempenho
e propósito, e **integrar à sua plataforma de governança (Cohort)**.

> Os agentes já emitem identidade, telemetria e checagem de política. A
> plataforma de governança **não** faz parte deste repositório — você conecta a
> sua (Cohort) só com variáveis de ambiente. Não é preciso mudar código.

---

## 0. Os três agentes

| Agente | `role` | Responsabilidade |
|---|---|---|
| **banking-benchmark** | `banking_product_benchmarking` | Compara produtos bancários e recomenda o melhor |
| **lead-mapper** | `lead_opportunity_mapping` | Mapeia empresas AI-heavy e gera prospects para a Veltrix |
| **compliance-risk** | `agent_output_compliance_audit` | Audita as trilhas dos outros e classifica risco |

Cada um tem identidade declarativa em `agents/<agente>/identity.yaml`.

---

## 1. Pré-requisitos

- **Docker** + **Docker Compose** (caminho recomendado), ou
- **Python 3.12+** para rodar local sem container.

```bash
cd langchain-agents
cp .env.example .env
```

---

## 2. Configuração (`.env`)

| Variável | Para quê | Default |
|---|---|---|
| `LLM_PROVIDER` | provedor LangChain | `anthropic` |
| `LLM_MODEL` | modelo Claude | `claude-sonnet-5` |
| `ANTHROPIC_API_KEY` | **vazio → modo stub** (testa governança sem gastar token) | vazio |
| `GOVERNANCE_URL` | base da sua plataforma (Cohort). Vazio → só auditoria local | vazio |
| `AGENT_CREDENTIAL` | segredo de auth do agente | vazio |
| `GOVERNANCE_STRICT` | `true` → aborta se registro/policy for recusado | `false` |
| `AUDIT_DIR` | onde a trilha JSONL é gravada | `/data/audit` (Docker) |

> **Dica:** comece **sem** `ANTHROPIC_API_KEY` e **sem** `GOVERNANCE_URL`. Tudo
> roda determinístico e grava a trilha local — ideal para validar o fluxo.

---

## 3. Executar com Docker

```bash
# build (uma vez)
docker compose build

# um agente específico
docker compose run --rm banking-benchmark
docker compose run --rm lead-mapper
docker compose run --rm compliance-risk

# tarefa customizada (tudo após o nome do módulo são args do worker)
docker compose run --rm lead-mapper \
  agents.lead_mapper.worker --print --task "Priorize prospects de healthtech regulada"
```

A trilha de cada execução fica em `./audit/<agent_id>.jsonl` (montada no host).

### Sem Docker

```bash
./scripts/run_local.sh banking
./scripts/run_local.sh leads "Mapeie prospects de fintech"
python -m agents.compliance_risk.worker --print
```

---

## 4. Avaliar desempenho e propósito

O harness roda cenários declarativos (`agents/*/evals.py`) e emite um scorecard.

```bash
docker compose run --rm evaluate           # os três agentes
# ou local:
python -m core.evaluation --agent all
python -m core.evaluation --agent banking --json   # saída JSON p/ CI
```

**Como ler o scorecard:**

```
╭─ Scorecard: banking-benchmark-agent (banking)
│  propósito: 100.0%   capacidade: 100.0%   geral: 100.0%
│  latência média: 2.0ms   máx: 3.5ms   (5/5 cenários ok)
```

- **capacidade** — as ferramentas/decisões estão corretas? (asserts sobre o JSON)
- **propósito** — o agente ponta-a-ponta entrega o resultado esperado?
- **latência** — tempo por cenário; ótimo para detectar regressão de performance.
- **exit code ≠ 0** se qualquer cenário falhar → pluga direto em CI.

**Adicionar seus próprios testes:** edite `agents/<agente>/evals.py` e acrescente
um `Scenario`. Operadores de asserção disponíveis: `equals`, `gte`, `lte`,
`one_of`, `contains`, `regex`.

---

## 5. Entender a trilha de auditoria

Cada execução gera eventos em ordem. Exemplo de uma execução saudável:

```
agent.register → agent.bootstrap → policy.decision(agent.run, allow)
  → policy.decision(tool:X, allow) → tool.start(X) → tool.end(X)
  → agent.result → agent.shutdown
```

Quando a política **nega** uma ferramenta, ela **não executa**:

```
policy.decision(tool:Y, allow=false) → tool.blocked(Y)      ◀── sem tool.start/end
```

Inspecionar rapidamente:

```bash
python -c "import json;[print(json.loads(l)['event']) for l in open('audit/<id>.jsonl')]"
```

O **compliance-risk agent** faz exatamente essa leitura automaticamente e
produz um relatório de risco por agente.

---

## 6. 🔗 Integração com o Cohort (sua plataforma de governança)

O agente conversa com a plataforma por 4 momentos. Configure as rotas/auth por
env var para casar com o contrato real do Cohort — **sem tocar em código**.

### 6.1. Contrato que o agente usa

| Momento | Método + rota (default) | Corpo enviado | Resposta esperada |
|---|---|---|---|
| Registro (boot) | `POST /agents/register` | manifesto de identidade | `{ "session_token": "..." }` |
| Política (antes de agir) | `POST /policy/evaluate` | `{agent_id, action, context, risk_tier}` | `{ "allow": true/false, "reason": "..." }` |
| Evento (cada passo) | `POST /agents/{agent_id}/events` | registro de auditoria | `{}` (200) |
| Heartbeat / fim | `POST /agents/{agent_id}/heartbeat` · `/shutdown` | `{status}` | `{}` (200) |

**Exemplo — manifesto no registro:**
```json
{
  "agent_id": "dfbc50a4-…", "name": "banking-benchmark-agent",
  "role": "banking_product_benchmarking", "risk_tier": "medium",
  "allowed_tools": ["list_banking_products", "get_product_metrics", "benchmark_products"],
  "data_scopes": ["public_market_rates"], "run_id": "run-…", "sdk": "governed-langchain/0.1"
}
```

**Exemplo — requisição de política:**
```json
{ "agent_id": "dfbc50a4-…", "action": "tool:benchmark_products",
  "context": {"tool": "benchmark_products", "input": "{…}"}, "risk_tier": "medium" }
```
O Cohort responde `{"allow": false, "reason": "…"}` → **o agente não roda a tool.**

### 6.2. Mapear para as rotas/auth do Cohort

Se o Cohort usar caminhos ou nomes de campo diferentes, ajuste no `.env`:

```bash
GOVERNANCE_URL=https://api.cohort.example
AGENT_CREDENTIAL=<token do agente no Cohort>

# Estilo de autenticação: bearer | header | query | none
GOV_AUTH_STYLE=bearer
GOV_AUTH_HEADER=Authorization          # nome do header (se style=header/query)

# Rotas (use {agent_id} e {run_id} onde precisar)
GOV_REGISTER_PATH=/v1/agents/register
GOV_EVENTS_PATH=/v1/agents/{agent_id}/telemetry
GOV_POLICY_PATH=/v1/policy/evaluate
GOV_HEARTBEAT_PATH=/v1/agents/{agent_id}/heartbeat
GOV_SHUTDOWN_PATH=/v1/agents/{agent_id}/shutdown

# Nomes de campo na resposta (se o Cohort diferir do default)
GOV_TOKEN_FIELD=session_token          # campo do token no /register
GOV_POLICY_ALLOW_FIELD=allow           # campo booleano da decisão
```

Se o formato do **corpo** for muito diferente (não só nomes de campo), o único
ponto a tocar é `governance/client.py` (métodos `register`, `check_policy`,
`emit`) — o resto dos agentes permanece intacto.

### 6.3. Teste o "fio" antes de apontar pro Cohort

Um mock local (só stdlib) simula o contrato e imprime o que recebe:

```bash
# terminal 1 — sobe o mock (opcional: negar uma tool p/ ver o guardrail)
python scripts/mock_governance.py
# DENY_TOOL=benchmark_products python scripts/mock_governance.py

# terminal 2 — aponta o agente pro mock
GOVERNANCE_URL=http://localhost:9000 AGENT_CREDENTIAL=test \
  ./scripts/run_local.sh banking
```

Você verá no terminal 1: `REGISTER`, cada `EVENT`, e as decisões `POLICY`. Quando
o mock nega uma tool, a trilha do agente mostra `tool.blocked` e a tool não roda.

### 6.4. Modo estrito (produção)

```bash
GOVERNANCE_STRICT=true
```
Com isso, se o Cohort recusar o registro ou uma política (ou estiver
inacessível), o agente **aborta** em vez de seguir em modo degradado. Sem strict,
governança nunca derruba o agente — falhas de transporte viram
`governance.transport_error` na trilha local.

### 6.5. Checklist de integração

- [ ] `GOVERNANCE_URL` aponta para o Cohort
- [ ] `AGENT_CREDENTIAL` + `GOV_AUTH_STYLE`/`GOV_AUTH_HEADER` batem com o Cohort
- [ ] Rotas `GOV_*_PATH` batem com o contrato do Cohort
- [ ] `/register` retorna o token no campo `GOV_TOKEN_FIELD`
- [ ] `/policy/evaluate` retorna `GOV_POLICY_ALLOW_FIELD` booleano
- [ ] Testado contra o mock e depois contra o Cohort
- [ ] `GOVERNANCE_STRICT=true` no ambiente final

---

## 7. Adaptar para dados reais

As ferramentas usam datasets **simulados e determinísticos**. Troque o corpo de
cada `@tool` em `agents/*/tools.py` por chamadas às suas fontes reais (APIs de
bancos, enriquecimento firmográfico, CRM). A identidade, o guardrail de política
e a trilha de auditoria continuam iguais.

---

## 8. Troubleshooting

| Sintoma | Causa provável | Ação |
|---|---|---|
| `LLM=STUB` no log | sem `ANTHROPIC_API_KEY` | normal p/ testar governança; defina a chave p/ Claude real |
| Nada chega ao Cohort | `GOVERNANCE_URL` vazio ou rota errada | confira `GOV_*_PATH`; teste com o mock |
| Agente aborta no boot | `GOVERNANCE_STRICT=true` + Cohort inacessível | valide a URL/token, ou desligue o strict p/ diagnosticar |
| Tool sempre negada | `allowed_tools` do `identity.yaml` não inclui a tool | ajuste o allowlist da identidade |
| `403/407` via proxy | rede corporativa | ver `GOVERNANCE_URL` e credenciais de proxy |
