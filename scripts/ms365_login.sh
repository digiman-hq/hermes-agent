#!/bin/sh
# One-time softeria MS365 device-code login (run as uid 501). Caches the token
# to the /opt/data volume so the MCP server (spawned by hermes/codex) reuses it.
export HOME=/opt/data
export MS365_MCP_TOKEN_CACHE_PATH=/opt/data/.ms365/token-cache.json
export MS365_MCP_SELECTED_ACCOUNT_PATH=/opt/data/.ms365/account.json
mkdir -p /opt/data/.ms365
echo "== device-code login: open the URL below, enter the code, sign in with the Microsoft 365 account =="
exec ms-365-mcp-server --org-mode --login
