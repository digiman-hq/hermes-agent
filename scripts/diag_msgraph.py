"""Diagnostic: does the teams gateway path expose the msgraph tools?"""
import os
os.environ.setdefault("HERMES_HOME", "/opt/data")
from hermes_cli.env_loader import load_hermes_dotenv
load_hermes_dotenv()
print("MSGRAPH_TENANT_ID present :", bool(os.getenv("MSGRAPH_TENANT_ID")))
import tools.msgraph_tools as M
print("check_msgraph_available() :", M._check_msgraph_available())
import toolsets as TS
print("'msgraph' in TOOLSETS dict :", "msgraph" in TS.TOOLSETS)

import yaml
cfg = yaml.safe_load(open("/opt/data/config.yaml", encoding="utf-8")) or {}
from hermes_cli.tools_config import _get_platform_tools
ets = sorted(_get_platform_tools(cfg, "teams"))
print("enabled_toolsets(teams)   :", ets)
import model_tools
defs = model_tools.get_tool_definitions(enabled_toolsets=ets)
tn = sorted(d["function"]["name"] for d in defs)
print("teams total tools         :", len(tn))
print("teams msgraph tools       :", [t for t in tn if "msgraph" in t])
