#!/usr/bin/env bash
# Roda os agentes localmente (sem Docker), útil para desenvolvimento rápido.
# Uso: ./scripts/run_local.sh [banking|leads] ["tarefa custom"]
set -euo pipefail
cd "$(dirname "$0")/.."

AGENT="${1:-banking}"
TASK="${2:-}"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  ./.venv/bin/pip install -q -r requirements.txt
fi
source .venv/bin/activate

case "$AGENT" in
  banking) MODULE="agents.banking_benchmark.worker" ;;
  leads)   MODULE="agents.lead_mapper.worker" ;;
  *) echo "agente desconhecido: $AGENT (use 'banking' ou 'leads')"; exit 1 ;;
esac

if [[ -n "$TASK" ]]; then
  python -m "$MODULE" --print --task "$TASK"
else
  python -m "$MODULE" --print
fi
