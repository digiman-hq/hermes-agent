"""Idempotently enable network access for codex's workspace-write sandbox.

Appends a [sandbox_workspace_write] table (outside Hermes' managed block, so
it survives re-migration) so MCP servers spawned by codex app-server (e.g. the
microsoft365 Graph MCP) can reach the network. Without this, codex's default
workspace-write sandbox blocks outbound network and MCP Graph calls fail with
'user cancelled MCP tool call'.
"""
import sys

p = sys.argv[1] if len(sys.argv) > 1 else "/opt/data/.codex/config.toml"
s = open(p, encoding="utf-8").read()

if "[sandbox_workspace_write]" in s:
    if "network_access = true" in s or "network_access=true" in s:
        print("network_access already enabled — no change")
    else:
        print("WARNING: [sandbox_workspace_write] exists without network_access=true "
              "— edit manually to add 'network_access = true'")
    raise SystemExit(0)

block = "\n# --- appended by hermes ops: allow MCP servers to reach the network ---\n" \
        "[sandbox_workspace_write]\nnetwork_access = true\n"
if not s.endswith("\n"):
    s += "\n"
s += block
open(p, "w", encoding="utf-8").write(s)

try:
    import tomllib
    tomllib.loads(s)
    print("enabled sandbox_workspace_write.network_access = true + TOML valid")
except Exception as e:
    print("WARNING: TOML parse failed after edit:", e)
    raise SystemExit(1)
