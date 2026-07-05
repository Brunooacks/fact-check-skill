"""Harness de avaliação de agentes.

Mede se um agente cumpre seu PROPÓSITO e com que DESEMPENHO. Roda cenários
declarativos (definidos em cada agente) e produz um scorecard com:

  - capability: as ferramentas produzem as decisões corretas? (asserts sobre JSON)
  - purpose:    o agente, ponta-a-ponta, entrega o resultado esperado?
  - desempenho: latência por cenário, nº de chamadas de ferramenta, sucesso.

Uso:
  python -m core.evaluation --agent banking      # um agente
  python -m core.evaluation --agent all --json    # todos, saída JSON
"""
from __future__ import annotations

import argparse
import importlib
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

# Registro de agentes avaliáveis (chave curta -> pacote).
AGENTS: Dict[str, str] = {
    "banking": "agents.banking_benchmark",
    "leads": "agents.lead_mapper",
    "compliance": "agents.compliance_risk",
}

_UNSET = object()


@dataclass
class Scenario:
    """Um caso de teste declarativo.

    category="capability": chama `tool` com `tool_input`, asserta sobre o JSON.
    category="purpose":    roda o agente ponta-a-ponta com `task`, asserta sobre o texto.
    """
    name: str
    category: str  # "capability" | "purpose"
    task: str = ""
    tool: str = ""
    tool_input: dict = field(default_factory=dict)
    asserts: List[dict] = field(default_factory=list)
    weight: float = 1.0


# ── resolução de asserts ─────────────────────────────────────────────
def _resolve(data: Any, path: str) -> Any:
    if not path:
        return data
    cur = data
    for part in path.split("."):
        if isinstance(cur, list) and part.isdigit():
            idx = int(part)
            cur = cur[idx] if idx < len(cur) else _UNSET
        elif isinstance(cur, dict):
            cur = cur.get(part, _UNSET)
        else:
            return _UNSET
        if cur is _UNSET:
            return _UNSET
    return cur


def _check(data: Any, a: dict) -> tuple[bool, str]:
    """Avalia uma asserção. Suporta: equals, gte, lte, contains, one_of, regex."""
    path = a.get("path", "")
    value = _resolve(data, path)
    label = f"{path or '<root>'}={value!r}"

    if "equals" in a:
        ok = value == a["equals"]
        return ok, f"{label} {'==' if ok else '!='} {a['equals']!r}"
    if "gte" in a:
        ok = isinstance(value, (int, float)) and value >= a["gte"]
        return ok, f"{label} >= {a['gte']}"
    if "lte" in a:
        ok = isinstance(value, (int, float)) and value <= a["lte"]
        return ok, f"{label} <= {a['lte']}"
    if "one_of" in a:
        ok = value in a["one_of"]
        return ok, f"{label} in {a['one_of']}"
    if "contains" in a:
        ok = a["contains"].lower() in str(value).lower()
        return ok, f"contains {a['contains']!r} -> {ok}"
    if "regex" in a:
        ok = re.search(a["regex"], str(value), re.I) is not None
        return ok, f"regex {a['regex']!r} -> {ok}"
    return False, f"asserção sem operador reconhecido: {a}"


# ── execução ─────────────────────────────────────────────────────────
def _run_scenario(worker, scen: Scenario) -> dict:
    details, tool_calls = [], 0
    t0 = time.perf_counter()
    try:
        if scen.category == "capability":
            tool = worker.tools_by_name().get(scen.tool)
            if tool is None:
                raise KeyError(f"tool '{scen.tool}' não existe")
            raw = tool.invoke(scen.tool_input)
            tool_calls = 1
            try:
                data = json.loads(raw)
            except Exception:  # noqa: BLE001
                data = raw
        else:  # purpose: ponta-a-ponta
            data = worker.run(scen.task)
            tool_calls = len(scen.asserts)  # aproximação informativa
    except Exception as exc:  # noqa: BLE001
        latency = (time.perf_counter() - t0) * 1000
        return {"name": scen.name, "category": scen.category, "passed": False,
                "latency_ms": round(latency, 1), "error": str(exc), "checks": []}

    latency = (time.perf_counter() - t0) * 1000
    checks = [dict(zip(("passed", "detail"), _check(data, a))) for a in scen.asserts]
    passed = all(c["passed"] for c in checks) if checks else True
    return {
        "name": scen.name, "category": scen.category, "passed": passed,
        "latency_ms": round(latency, 1), "tool_calls": tool_calls, "checks": checks,
    }


def evaluate_agent(key: str) -> dict:
    pkg = AGENTS[key]
    worker = importlib.import_module(f"{pkg}.worker").build()
    scenarios: List[Scenario] = importlib.import_module(f"{pkg}.evals").EVALS
    worker.bootstrap()

    results = [_run_scenario(worker, s) for s in scenarios]
    worker.shutdown()

    def _rate(cat: str) -> float:
        subset = [r for r in results if r["category"] == cat]
        return round(100 * sum(r["passed"] for r in subset) / len(subset), 1) if subset else 0.0

    passed = sum(r["passed"] for r in results)
    latencies = [r["latency_ms"] for r in results]
    return {
        "agent": key,
        "identity": {
            "name": worker.identity.name,
            "agent_id": worker.identity.agent_id,
            "role": worker.identity.role,
            "risk_tier": worker.identity.risk_tier,
        },
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "summary": {
            "scenarios": len(results),
            "passed": passed,
            "score_pct": round(100 * passed / len(results), 1) if results else 0.0,
            "capability_pct": _rate("capability"),
            "purpose_pct": _rate("purpose"),
            "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
            "max_latency_ms": max(latencies) if latencies else 0.0,
        },
        "scenarios": results,
    }


# ── relatório ────────────────────────────────────────────────────────
def _print_scorecard(sc: dict) -> None:
    s = sc["summary"]
    print(f"\n╭─ Scorecard: {sc['identity']['name']} ({sc['agent']})")
    print(f"│  role={sc['identity']['role']}  id={sc['identity']['agent_id']}")
    print(f"│  propósito: {s['purpose_pct']}%   capacidade: {s['capability_pct']}%   "
          f"geral: {s['score_pct']}%")
    print(f"│  latência média: {s['avg_latency_ms']}ms   máx: {s['max_latency_ms']}ms   "
          f"({s['passed']}/{s['scenarios']} cenários ok)")
    print("├─ cenários")
    for r in sc["scenarios"]:
        mark = "✓" if r["passed"] else "✗"
        line = f"│  {mark} [{r['category']:<10}] {r['name']}  ({r['latency_ms']}ms)"
        print(line)
        if r.get("error"):
            print(f"│      erro: {r['error']}")
        for c in r.get("checks", []):
            if not c["passed"]:
                print(f"│      ✗ {c['detail']}")
    print("╰─────────────────────────────────────────────")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Avalia desempenho e propósito dos agentes")
    parser.add_argument("--agent", default="all", choices=[*AGENTS, "all"])
    parser.add_argument("--json", action="store_true", help="Saída em JSON (para pipelines/CI)")
    args = parser.parse_args(argv)

    keys = list(AGENTS) if args.agent == "all" else [args.agent]
    scorecards = [evaluate_agent(k) for k in keys]

    if args.json:
        print(json.dumps(scorecards, ensure_ascii=False, indent=2))
    else:
        for sc in scorecards:
            _print_scorecard(sc)

    # Exit code != 0 se qualquer cenário falhou (útil para CI).
    all_ok = all(sc["summary"]["passed"] == sc["summary"]["scenarios"] for sc in scorecards)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
