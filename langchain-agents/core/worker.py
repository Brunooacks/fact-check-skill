"""Base de worker governado.

Cada agente é um WORKER de linha de comando (não um servidor HTTP): recebe uma
tarefa, registra sua identidade na governança, executa (via LangChain
AgentExecutor com Claude, ou plano determinístico no modo stub), reporta cada
passo e encerra. Toda ação passa por checagem de política.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Callable, List, Sequence, Tuple

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool

from governance.callbacks import GovernanceCallbackHandler
from governance.client import GovernanceClient
from governance.identity import AgentIdentity

from .llm import build_llm, is_stub

# Um passo de plano determinístico: (nome_da_tool, kwargs_de_input)
PlanStep = Tuple[str, dict]


class GovernedWorker:
    def __init__(
        self,
        identity_path: str | Path,
        tools: Sequence[BaseTool],
        system_prompt: str,
        demo_plan: Callable[[str], List[PlanStep]],
        default_task: str,
    ) -> None:
        self.identity = AgentIdentity.from_yaml(identity_path)
        self.tools = list(tools)
        self.system_prompt = system_prompt
        self.demo_plan = demo_plan
        self.default_task = default_task

        self.llm = build_llm()
        self.client = GovernanceClient(self.identity)
        self.handler = GovernanceCallbackHandler(self.client)
        self._tools_by_name = {t.name: t for t in self.tools}

    def tools_by_name(self) -> dict:
        """Mapa nome->tool (usado pelo harness de avaliação)."""
        return dict(self._tools_by_name)

    # ── ciclo de vida ────────────────────────────────────────────────
    def bootstrap(self) -> None:
        reg = self.client.register()
        mode = "STUB" if is_stub(self.llm) else os.getenv("LLM_MODEL", "claude")
        print(f"▶ {self.identity.name} [{self.identity.agent_id}] registrado "
              f"(LLM={mode}, governança={self.client.base_url or 'local-only'})")
        self.client.emit("agent.bootstrap", {"registration": reg}, level="info")

    def run(self, task: str) -> str:
        # Guardrail de entrada.
        decision = self.client.check_policy("agent.run", {"task": task[:500]})
        if not decision.allow:
            msg = f"Execução bloqueada pela governança: {decision.reason}"
            print("⛔", msg)
            return msg

        if is_stub(self.llm):
            result = self._run_deterministic(task)
        else:
            result = self._run_agent(task)

        self.client.emit("agent.result", {"task": task[:500], "output": result[:2000]})
        return result

    def shutdown(self) -> None:
        self.client.shutdown()

    # ── caminho real: LangChain + Claude ─────────────────────────────
    def _run_agent(self, task: str) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])
        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            callbacks=[self.handler],
            verbose=False,
            max_iterations=8,
            handle_parsing_errors=True,
        )
        out = executor.invoke({"input": task}, config={"callbacks": [self.handler]})
        return out.get("output", "")

    # ── caminho stub: plano determinístico com governança ────────────
    def _run_deterministic(self, task: str) -> str:
        collected = []
        for tool_name, tool_input in self.demo_plan(task):
            tool = self._tools_by_name.get(tool_name)
            if tool is None:
                continue
            # tool.invoke com callbacks dispara on_tool_start/end → auditoria + policy.
            output = tool.invoke(tool_input, config={"callbacks": [self.handler]})
            collected.append((tool_name, output))
        return self._synthesize(task, collected)

    def _synthesize(self, task: str, collected: List[Tuple[str, str]]) -> str:
        lines = [f"# {self.identity.name} — resultado (modo determinístico)",
                 f"Tarefa: {task}", ""]
        for name, out in collected:
            lines.append(f"## {name}")
            try:
                lines.append("```json\n" + json.dumps(json.loads(out), ensure_ascii=False, indent=2) + "\n```")
            except Exception:  # noqa: BLE001
                lines.append(str(out))
            lines.append("")
        return "\n".join(lines)

    # ── entrypoint CLI ───────────────────────────────────────────────
    def main(self, argv: Sequence[str] | None = None) -> None:
        parser = argparse.ArgumentParser(description=self.identity.description or self.identity.name)
        parser.add_argument("--task", default=os.getenv("TASK", self.default_task),
                            help="Tarefa a executar")
        parser.add_argument("--print", action="store_true", help="Imprime o resultado no stdout")
        args = parser.parse_args(argv)

        self.bootstrap()
        try:
            result = self.run(args.task)
            print("\n" + result if args.print else
                  f"✓ Concluído. Trilha de auditoria: {self.client._audit_path}")
        finally:
            self.shutdown()
