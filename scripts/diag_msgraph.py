"""Temporary diagnostic: is the msgraph toolset visible to the running config?"""
import os
os.environ.setdefault("HERMES_HOME", "/opt/data")
from hermes_cli.env_loader import load_hermes_dotenv
load_hermes_dotenv()
print("HERMES_HOME =", os.getenv("HERMES_HOME"))
print("MSGRAPH_TENANT_ID present :", bool(os.getenv("MSGRAPH_TENANT_ID")))
print("MSGRAPH_CLIENT_SECRET present :", bool(os.getenv("MSGRAPH_CLIENT_SECRET")))

import tools.msgraph_tools as M
print("check_msgraph_available() :", M._check_msgraph_available())

from tools.registry import registry
names = ["msgraph_list_sites", "msgraph_search_files", "msgraph_list_mail", "msgraph_get_mail"]
print("registered in registry    :", [n for n in names if n in registry._tools])
try:
    defs = registry.get_definitions(set(names))
    print("visible via get_definitions:", sorted(d["function"]["name"] for d in defs))
except Exception as e:
    print("get_definitions err:", repr(e))

import toolsets as TS
print("in _HERMES_CORE_TOOLS      :", "msgraph_list_sites" in TS._HERMES_CORE_TOOLS)

# Resolve the actual tool set the teams platform would expose.
try:
    import inspect
    print("resolve_toolset sig        :", str(inspect.signature(TS.resolve_toolset)))
except Exception as e:
    print("resolve sig err:", repr(e))

for call in ("teams",):
    for attempt in (
        lambda: TS.resolve_toolset(["hermes-teams"]),
        lambda: TS.resolve_toolset("hermes-teams"),
    ):
        try:
            r = attempt()
            names_in = sorted(r) if not isinstance(r, dict) else sorted(r.keys())
            print("resolved hermes-teams -> msgraph present:",
                  any("msgraph" in x for x in names_in),
                  "| total tools:", len(names_in))
            break
        except Exception as e:
            print("resolve attempt err:", repr(e))
