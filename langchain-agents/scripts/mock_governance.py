#!/usr/bin/env python3
"""Mock de plataforma de governança — só stdlib, para testar a integração.

Simula o contrato que o GovernanceClient espera. Serve para você verificar, no
seu computador, que os agentes registram identidade, mandam eventos e consultam
política ANTES de apontar para o Cohort de verdade.

Uso:
  python scripts/mock_governance.py               # porta 9000
  # noutro terminal:
  GOVERNANCE_URL=http://localhost:9000 \
  ./scripts/run_local.sh banking

Para simular um bloqueio de política, suba com DENY_TOOL:
  DENY_TOOL=benchmark_products python scripts/mock_governance.py
"""
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

DENY_TOOL = os.getenv("DENY_TOOL", "")
PORT = int(os.getenv("PORT", "9000"))


class Handler(BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        path = self.path

        if path.endswith("/register"):
            print(f"\n📥 REGISTER  {payload.get('name')} ({payload.get('agent_id')})")
            print(f"   role={payload.get('role')}  tools={payload.get('allowed_tools')}")
            self._send({"status": "registered", "session_token": "mock-token-123"})

        elif path.endswith("/evaluate"):
            ctx = payload.get("context", {})
            tool = ctx.get("tool", "")
            allow = not (DENY_TOOL and tool == DENY_TOOL)
            reason = "ok" if allow else f"tool '{tool}' bloqueada pelo mock"
            print(f"🔐 POLICY    action={payload.get('action')} -> allow={allow}")
            self._send({"allow": allow, "reason": reason})

        elif path.endswith("/events"):
            print(f"📝 EVENT     seq={payload.get('seq')} {payload.get('event')} "
                  f"[{payload.get('level')}]")
            self._send({"ok": True})

        else:  # heartbeat / shutdown / etc.
            print(f"➡️  {path}  {payload}")
            self._send({"ok": True})

    def log_message(self, *args):  # silencia o log padrão do http.server
        pass


if __name__ == "__main__":
    print(f"🛡️  Mock de governança em http://localhost:{PORT}"
          + (f"  (negando tool '{DENY_TOOL}')" if DENY_TOOL else ""))
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
