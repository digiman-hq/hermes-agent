"""Idempotently register the microsoft365 MCP server in a Hermes config.yaml.

Adds under mcp_servers:
  microsoft365:
    command: /opt/hermes/.venv/bin/python
    args: ["-m", "agent.transports.microsoft365_mcp_server"]
    env: { PYTHONPATH: /opt/hermes, HERMES_HOME: <home> }
"""
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "/opt/data/config.yaml"
home = sys.argv[2] if len(sys.argv) > 2 else "/opt/data"
s = open(path, encoding="utf-8").read()

if "microsoft365:" in s and "microsoft365_mcp_server" in s:
    print("microsoft365 MCP server already registered — no change")
    raise SystemExit(0)

entry = (
    "  microsoft365:\n"
    "    command: /opt/hermes/.venv/bin/python\n"
    "    args:\n"
    "      - \"-m\"\n"
    "      - \"agent.transports.microsoft365_mcp_server\"\n"
    "    env:\n"
    "      PYTHONPATH: /opt/hermes\n"
    f"      HERMES_HOME: {home}\n"
)

lines = s.splitlines(keepends=True)
out = []
inserted = False
for i, line in enumerate(lines):
    out.append(line)
    if not inserted and line.rstrip("\n") == "mcp_servers:":
        out.append(entry)
        inserted = True

if not inserted:
    # no mcp_servers block yet — append a fresh one at EOF
    if out and not out[-1].endswith("\n"):
        out[-1] += "\n"
    out.append("\nmcp_servers:\n")
    out.append(entry)

new = "".join(out)
open(path, "w", encoding="utf-8").write(new)

# sanity: still valid YAML
try:
    import yaml
    yaml.safe_load(new)
    print("registered microsoft365 MCP server + YAML valid")
except Exception as e:
    print("WARNING: YAML parse failed after edit:", e)
    raise SystemExit(1)
