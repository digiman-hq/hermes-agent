"""Replace [mcp_servers.microsoft365] with [mcp_servers.ms365] in codex config.toml (in place)."""
import sys

p = sys.argv[1] if len(sys.argv) > 1 else "/opt/data/.codex/config.toml"
s = open(p, encoding="utf-8").read()
if "[mcp_servers.ms365]" in s:
    print("ms365 already in config.toml — no change")
    raise SystemExit(0)

ms365_block = (
    "[mcp_servers.ms365]\n"
    'command = "/usr/local/bin/ms-365-mcp-server"\n'
    'args = ["--org-mode"]\n'
    'env = { HOME = "/opt/data", MS365_MCP_TOKEN_CACHE_PATH = "/opt/data/.ms365/token-cache.json", '
    'MS365_MCP_SELECTED_ACCOUNT_PATH = "/opt/data/.ms365/account.json" }\n'
)

lines = s.splitlines(keepends=True)
out, i, n, replaced = [], 0, len(lines), False
while i < n:
    line = lines[i]
    if line.strip() == "[mcp_servers.microsoft365]":
        out.append(ms365_block)
        replaced = True
        i += 1
        while i < n and not lines[i].lstrip().startswith("["):
            i += 1
        continue
    out.append(line)
    i += 1
s = "".join(out)
open(p, "w", encoding="utf-8").write(s)

try:
    import tomllib
    tomllib.loads(s)
    print("replaced microsoft365 -> ms365 + TOML valid" if replaced
          else "microsoft365 block not found (nothing replaced)")
except Exception as e:
    print("TOML parse err:", e)
    raise SystemExit(1)
