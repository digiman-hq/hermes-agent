"""Diagnostic: build the microsoft365 MCP server and list its tools."""
import asyncio, inspect, os
os.environ.setdefault("MSGRAPH_TENANT_ID", "t")
os.environ.setdefault("MSGRAPH_CLIENT_ID", "c")
os.environ.setdefault("MSGRAPH_CLIENT_SECRET", "s")
from agent.transports.microsoft365_mcp_server import _build_server
srv = _build_server()
res = srv.list_tools()
if inspect.iscoroutine(res):
    res = asyncio.run(res)
print("microsoft365 MCP tools:", sorted(getattr(t, "name", str(t)) for t in res))
