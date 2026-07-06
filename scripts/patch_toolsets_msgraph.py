"""Idempotently add the "msgraph" entry to the TOOLSETS dict in toolsets.py."""
p = "/opt/hermes/toolsets.py"
s = open(p, encoding="utf-8").read()
if '"msgraph": {' in s:
    print("msgraph TOOLSETS entry already present — no change")
    raise SystemExit(0)
marker = "TOOLSETS = {"
i = s.index(marker) + len(marker)
entry = (
    "\n    \"msgraph\": {\n"
    "        \"description\": \"Microsoft 365 SharePoint files and Outlook mail via Graph\",\n"
    "        \"tools\": [\n"
    "            \"msgraph_list_sites\", \"msgraph_search_files\",\n"
    "            \"msgraph_list_mail\", \"msgraph_get_mail\",\n"
    "        ],\n"
    "        \"includes\": [],\n"
    "    },"
)
s = s[:i] + entry + s[i:]
open(p, "w", encoding="utf-8").write(s)
# sanity: file still imports
import py_compile, tempfile
py_compile.compile(p, doraise=True)
print("inserted msgraph TOOLSETS entry + py_compile OK")
