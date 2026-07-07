"""Swap the config.yaml mcp_servers entry from our microsoft365 server to softeria ms365."""
import sys, re

p = sys.argv[1] if len(sys.argv) > 1 else "/opt/data/config.yaml"
s = open(p, encoding="utf-8").read()
lines = s.splitlines(keepends=True)

# 1) remove the "  microsoft365:" block (2-space key + all deeper-indented lines)
out, i, n = [], 0, len(lines)
while i < n:
    line = lines[i]
    if line.rstrip("\n") == "  microsoft365:":
        i += 1
        while i < n:
            nxt = lines[i]
            if nxt.strip() == "":
                i += 1
                continue
            indent = len(nxt) - len(nxt.lstrip(" "))
            if indent > 2:
                i += 1
            else:
                break
        continue
    out.append(line)
    i += 1
s = "".join(out)

# 2) add the ms365 entry under mcp_servers:
ms365 = (
    "  ms365:\n"
    "    command: /usr/local/bin/ms-365-mcp-server\n"
    "    args:\n"
    '      - "--org-mode"\n'
    "    env:\n"
    "      HOME: /opt/data\n"
    "      MS365_MCP_TOKEN_CACHE_PATH: /opt/data/.ms365/token-cache.json\n"
    "      MS365_MCP_SELECTED_ACCOUNT_PATH: /opt/data/.ms365/account.json\n"
)
if "ms365:" in s and "ms-365-mcp-server" in s:
    print("ms365 already registered — no change")
else:
    if re.search(r"(?m)^mcp_servers:\s*$", s):
        s = re.sub(r"(?m)^(mcp_servers:[ \t]*\n)", r"\1" + ms365, s, count=1)
    else:
        if not s.endswith("\n"):
            s += "\n"
        s += "\nmcp_servers:\n" + ms365

open(p, "w", encoding="utf-8").write(s)
try:
    import yaml
    yaml.safe_load(s)
    print("swapped microsoft365 -> ms365 + YAML valid")
    print("--- mcp_servers block now ---")
    import re as _re
    m = _re.search(r"(?ms)^mcp_servers:.*?(?=^\S|\Z)", s)
    print(m.group(0) if m else "(not found)")
except Exception as e:
    print("WARNING YAML parse:", e)
    raise SystemExit(1)
