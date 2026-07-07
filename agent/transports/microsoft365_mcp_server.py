"""Standalone Microsoft 365 MCP server (SharePoint / Outlook / user profile).

A self-contained stdio MCP server that exposes Microsoft 365 operations backed
by app-only Microsoft Graph (client-credentials). Unlike the native
``tools/msgraph_tools.py`` registry tools (which only surface on Hermes' own
runtime), an MCP server works on BOTH the default runtime AND the
``codex_app_server`` runtime — Hermes auto-migrates ``mcp_servers`` into
``~/.codex/config.toml`` so codex can call it too. This is our "Work IQ-like"
M365 tool server.

Auth: reads the same three env vars as the rest of the Graph stack (grant the
matching *application* Graph permissions with admin consent):

    MSGRAPH_TENANT_ID / MSGRAPH_CLIENT_ID / MSGRAPH_CLIENT_SECRET

Run:  python -m agent.transports.microsoft365_mcp_server
Register in config.yaml:

    mcp_servers:
      microsoft365:
        command: /opt/hermes/.venv/bin/python
        args: ["-m", "agent.transports.microsoft365_mcp_server"]
        env:
          PYTHONPATH: /opt/hermes
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Optional

logger = logging.getLogger("microsoft365-mcp")


# ---------------------------------------------------------------------------
# Graph client + result shaping
# ---------------------------------------------------------------------------

def _client():
    """Build an app-only Graph client from MSGRAPH_* env, or raise clearly."""
    from tools.microsoft_graph_client import MicrosoftGraphClient

    return MicrosoftGraphClient.from_env()


def _escape_odata(value: str) -> str:
    return value.replace("'", "''")


def _err(msg: str) -> str:
    return json.dumps({"error": msg}, ensure_ascii=False)


def _addr(recipient: Any) -> Optional[str]:
    if not isinstance(recipient, dict):
        return None
    email = recipient.get("emailAddress") or {}
    name, address = email.get("name"), email.get("address")
    if name and address:
        return f"{name} <{address}>"
    return address or name


def _site(s: dict) -> dict:
    return {
        "id": s.get("id"),
        "name": s.get("name") or s.get("displayName"),
        "webUrl": s.get("webUrl"),
    }


def _file(item: dict) -> dict:
    parent = item.get("parentReference") or {}
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "webUrl": item.get("webUrl"),
        "size": item.get("size"),
        "lastModified": item.get("lastModifiedDateTime"),
        "isFolder": "folder" in item,
        "path": parent.get("path"),
    }


def _msg(m: dict) -> dict:
    return {
        "id": m.get("id"),
        "subject": m.get("subject"),
        "from": _addr(m.get("from")),
        "received": m.get("receivedDateTime"),
        "preview": m.get("bodyPreview"),
        "hasAttachments": m.get("hasAttachments"),
    }


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

def _build_server() -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - install hint
        raise ImportError(
            f"microsoft365 MCP server requires the 'mcp' package: {exc}"
        ) from exc

    mcp = FastMCP(
        "microsoft365",
        instructions=(
            "Microsoft 365 operations via app-only Microsoft Graph: search "
            "SharePoint sites and files, read Outlook mail, and look up user "
            "profiles. Tenant-wide read access using a service principal."
        ),
    )

    @mcp.tool()
    async def m365_search_sites(query: str = "*") -> str:
        """Search Microsoft 365 SharePoint sites by keyword.

        Args:
            query: Keyword to match site name/URL. Use '*' to list all sites.
        Returns JSON with matching sites (id, name, webUrl). Use a site id
        with m365_search_files.
        """
        try:
            client = _client()
            payload = await client.get_json("/sites", params={"search": query or "*"})
            sites = (payload or {}).get("value") or []
            return json.dumps(
                {"count": len(sites), "sites": [_site(s) for s in sites]},
                ensure_ascii=False,
            )
        except Exception as exc:  # noqa: BLE001
            return _err(f"m365_search_sites failed: {exc}")

    @mcp.tool()
    async def m365_search_files(query: str, site_id: str = "root", top: int = 20) -> str:
        """Search files/folders inside a SharePoint site's document library.

        Args:
            query: Keyword to search file/folder names and content.
            site_id: Site id from m365_search_sites (default 'root').
            top: Max results (default 20).
        Returns JSON with file name, URL, size and last-modified time.
        """
        if not query.strip():
            return _err("query is required")
        top = max(1, min(int(top or 20), 100))
        q = _escape_odata(query)
        path = f"/sites/{site_id or 'root'}/drive/root/search(q='{q}')"
        try:
            client = _client()
            payload = await client.get_json(
                path,
                params={
                    "$top": top,
                    "$select": (
                        "id,name,webUrl,size,lastModifiedDateTime,folder,"
                        "parentReference"
                    ),
                },
            )
            items = (payload or {}).get("value") or []
            return json.dumps(
                {
                    "site_id": site_id or "root",
                    "query": query,
                    "count": len(items),
                    "files": [_file(i) for i in items],
                },
                ensure_ascii=False,
            )
        except Exception as exc:  # noqa: BLE001
            return _err(f"m365_search_files failed: {exc}")

    @mcp.tool()
    async def m365_list_mail(user: str, query: str = "", top: int = 10) -> str:
        """List or search a mailbox's messages via Microsoft Graph (app-only).

        Args:
            user: Mailbox owner email (UPN) or object id.
            query: Optional full-text search over the mailbox. Omit to list
                the most recent messages.
            top: Max messages (default 10, max 50).
        Returns JSON with subject, sender, received time and a short preview.
        """
        if not user.strip():
            return _err("user (mailbox UPN or id) is required")
        top = max(1, min(int(top or 10), 50))
        params: dict[str, Any] = {
            "$top": top,
            "$select": "id,subject,from,receivedDateTime,bodyPreview,hasAttachments",
        }
        if query.strip():
            params["$search"] = '"' + query.replace('"', '\\"') + '"'
        else:
            params["$orderby"] = "receivedDateTime desc"
        try:
            client = _client()
            payload = await client.get_json(f"/users/{user}/messages", params=params)
            msgs = (payload or {}).get("value") or []
            return json.dumps(
                {"user": user, "count": len(msgs), "messages": [_msg(m) for m in msgs]},
                ensure_ascii=False,
            )
        except Exception as exc:  # noqa: BLE001
            return _err(f"m365_list_mail failed: {exc}")

    @mcp.tool()
    async def m365_get_mail(user: str, message_id: str) -> str:
        """Read the full content of a single mail message by id.

        Args:
            user: Mailbox owner email (UPN) or object id.
            message_id: Message id from m365_list_mail.
        Returns JSON with subject, sender, recipients and the body text.
        """
        if not user.strip() or not message_id.strip():
            return _err("both user and message_id are required")
        try:
            client = _client()
            payload = await client.get_json(
                f"/users/{user}/messages/{message_id}",
                params={
                    "$select": (
                        "id,subject,from,toRecipients,ccRecipients,"
                        "receivedDateTime,hasAttachments,body"
                    )
                },
            )
            body = (payload or {}).get("body") or {}
            return json.dumps(
                {
                    "id": payload.get("id"),
                    "subject": payload.get("subject"),
                    "from": _addr(payload.get("from")),
                    "to": [_addr(r) for r in (payload.get("toRecipients") or [])],
                    "cc": [_addr(r) for r in (payload.get("ccRecipients") or [])],
                    "received": payload.get("receivedDateTime"),
                    "hasAttachments": payload.get("hasAttachments"),
                    "contentType": body.get("contentType"),
                    "body": body.get("content"),
                },
                ensure_ascii=False,
            )
        except Exception as exc:  # noqa: BLE001
            return _err(f"m365_get_mail failed: {exc}")

    @mcp.tool()
    async def m365_get_user(user: str) -> str:
        """Look up a Microsoft 365 user's profile by email (UPN) or id.

        Args:
            user: User email (UPN) or object id.
        Returns JSON with display name, job title, mail, department and office.
        """
        if not user.strip():
            return _err("user (UPN or id) is required")
        try:
            client = _client()
            payload = await client.get_json(
                f"/users/{user}",
                params={
                    "$select": (
                        "id,displayName,userPrincipalName,mail,jobTitle,"
                        "department,officeLocation,mobilePhone"
                    )
                },
            )
            return json.dumps(payload or {}, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            return _err(f"m365_get_user failed: {exc}")

    logger.info("microsoft365 MCP server built with 5 tools")
    return mcp


def _ensure_env() -> None:
    """Load MSGRAPH_* from HERMES_HOME/.env if not already in the environment.

    Hermes spawns this MCP subprocess with the config's ``env`` block; to keep
    the secret out of config.yaml we let the server pull it from the same
    ``.env`` Hermes itself loads. No-op when the vars are already present.
    """
    if os.getenv("MSGRAPH_TENANT_ID") and os.getenv("MSGRAPH_CLIENT_SECRET"):
        return
    home = os.getenv("HERMES_HOME")
    if not home:
        return
    env_path = os.path.join(home, ".env")
    if not os.path.exists(env_path):
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
    except Exception as exc:  # noqa: BLE001 - best effort
        logger.warning("could not load %s: %s", env_path, exc)


def main(argv: Optional[list] = None) -> int:
    argv = argv or sys.argv[1:]
    verbose = "--verbose" in argv or "-v" in argv
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        stream=sys.stderr,  # stdout is the MCP wire
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    os.environ.setdefault("HERMES_QUIET", "1")
    os.environ.setdefault("HERMES_REDACT_SECRETS", "true")
    _ensure_env()
    try:
        server = _build_server()
    except ImportError as exc:
        sys.stderr.write(f"microsoft365 MCP server cannot start: {exc}\n")
        return 2
    server.run()  # FastMCP stdio transport by default
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
