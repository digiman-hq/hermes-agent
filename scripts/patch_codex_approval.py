"""Idempotently set codex approval_policy = "never" (top-level, outside managed block).

On an unattended gateway Hermes fail-closes codex approvals (deny), so MCP tool
calls and shell exec are auto-rejected. thread/start sends no permissions, so
codex honors config.toml — setting approval_policy="never" makes codex not ask
for approval at all, letting tools run. SECURITY: this auto-runs ALL codex
commands without prompting (within the workspace-write sandbox). Only for a
trusted, internal instance. Revert by removing the line for client handover.
"""
import sys

p = sys.argv[1] if len(sys.argv) > 1 else "/opt/data/.codex/config.toml"
s = open(p, encoding="utf-8").read()

if "approval_policy" in s:
    print("approval_policy already present — no change")
    raise SystemExit(0)

# Must be a ROOT key (before any [table]) → prepend at the very top.
s = 'approval_policy = "never"\n' + s
open(p, "w", encoding="utf-8").write(s)

try:
    import tomllib
    tomllib.loads(s)
    print('set approval_policy = "never" (top-level) + TOML valid')
except Exception as e:
    print("WARNING: TOML parse failed after edit:", e)
    raise SystemExit(1)
