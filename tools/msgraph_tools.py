"""Microsoft Graph agent tools (app-only).

Thin LLM-callable wrappers around :class:`MicrosoftGraphClient` so a Hermes
conversation can search SharePoint sites/files and read Outlook mail. Uses
app-only (client-credentials) auth — configure the three env vars below and
grant the matching *application* Graph permissions with admin consent:

    MSGRAPH_TENANT_ID       (Directory / tenant id)
    MSGRAPH_CLIENT_ID       (App registration client id)
    MSGRAPH_CLIENT_SECRET   (Client secret value)

Required Graph *application* permissions (admin-consented):
    Sites.Read.All   -> msgraph_list_sites, msgraph_search_files
    Files.Read.All   -> msgraph_search_files (drive items)
    Mail.Read        -> msgraph_list_mail, msgraph_get_mail

The tools stay hidden from the model until the env vars are present (see
``_check_msgraph_available``), matching the Home Assistant / Feishu pattern.
"""

from __future__ import annotations

import json
from typing import Any

from tools.registry import registry, tool_error
from tools.microsoft_graph_auth import GraphCredentials
from tools.microsoft_graph_client import (
    MicrosoftGraphAPIError,
    MicrosoftGraphClient,
    MicrosoftGraphClientError,
)


# ---------------------------------------------------------------------------
# Availability gate
# ---------------------------------------------------------------------------

def _check_msgraph_available() -> bool:
    """True only when the MSGRAPH_* app-only credentials are configured."""
    try:
        return bool(GraphCredentials.from_env(required=False))
    except Exception:
        return False


def _escape_odata_literal(value: str) -> str:
    """Escape a value for use inside an OData single-quoted string literal."""
    return value.replace("'", "''")


def _run(coro: Any) -> Any:
    """Run an async Graph coroutine, surfacing Graph errors as tool errors."""
    try:
        return _await(coro)
    except MicrosoftGraphAPIError as exc:  # HTTP-level Graph failure
        raise MicrosoftGraphClientError(
            f"Graph API {exc.status_code}: {exc}"
        ) from exc


def _await(coro: Any) -> Any:
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Already inside a running loop (async agent dispatch): run the coroutine
    # in a dedicated loop on a worker thread so we don't collide with it.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

MSGRAPH_LIST_SITES_SCHEMA = {
    "name": "msgraph_list_sites",
    "description": (
        "Search Microsoft 365 SharePoint sites by keyword. Returns matching "
        "sites with their id, name and URL. Use the returned site id with "
        "msgraph_search_files to search files inside a site."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Keyword to match site name/URL. Use '*' to list all "
                    "sites the app can see."
                ),
            }
        },
        "required": ["query"],
    },
}

MSGRAPH_SEARCH_FILES_SCHEMA = {
    "name": "msgraph_search_files",
    "description": (
        "Search files/folders inside a SharePoint site's default document "
        "library by keyword. Returns file name, URL, size and last-modified "
        "time. Get a site_id first via msgraph_list_sites (or pass 'root' for "
        "the tenant root site)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Keyword to search file/folder names and content.",
            },
            "site_id": {
                "type": "string",
                "description": (
                    "SharePoint site id from msgraph_list_sites. Defaults to "
                    "'root' (tenant root site) when omitted."
                ),
            },
            "top": {
                "type": "integer",
                "description": "Max results to return (default 20).",
            },
        },
        "required": ["query"],
    },
}

MSGRAPH_LIST_MAIL_SCHEMA = {
    "name": "msgraph_list_mail",
    "description": (
        "List or search a mailbox's messages via Microsoft Graph (app-only). "
        "Returns subject, sender, received time and a short preview for each "
        "message. Use msgraph_get_mail with a returned message id to read the "
        "full body."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "user": {
                "type": "string",
                "description": (
                    "Mailbox to read: the user's email (UPN) or object id, "
                    "e.g. 'admin@contoso.onmicrosoft.com'."
                ),
            },
            "query": {
                "type": "string",
                "description": (
                    "Optional full-text search over the mailbox (subject, "
                    "body, sender). Omit to list the most recent messages."
                ),
            },
            "top": {
                "type": "integer",
                "description": "Max messages to return (default 10, max 50).",
            },
        },
        "required": ["user"],
    },
}

MSGRAPH_GET_MAIL_SCHEMA = {
    "name": "msgraph_get_mail",
    "description": (
        "Read the full content of a single mail message by id from a mailbox "
        "via Microsoft Graph (app-only). Returns subject, sender, recipients "
        "and the message body text."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "user": {
                "type": "string",
                "description": "Mailbox owner email (UPN) or object id.",
            },
            "message_id": {
                "type": "string",
                "description": "Message id returned by msgraph_list_mail.",
            },
        },
        "required": ["user", "message_id"],
    },
}


# ---------------------------------------------------------------------------
# Result shaping helpers
# ---------------------------------------------------------------------------

def _site_summary(site: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": site.get("id"),
        "name": site.get("name") or site.get("displayName"),
        "displayName": site.get("displayName"),
        "webUrl": site.get("webUrl"),
    }


def _file_summary(item: dict[str, Any]) -> dict[str, Any]:
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


def _addr(recipient: dict[str, Any] | None) -> str | None:
    if not isinstance(recipient, dict):
        return None
    email = recipient.get("emailAddress") or {}
    name = email.get("name")
    address = email.get("address")
    if name and address:
        return f"{name} <{address}>"
    return address or name


def _message_summary(msg: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": msg.get("id"),
        "subject": msg.get("subject"),
        "from": _addr(msg.get("from")),
        "received": msg.get("receivedDateTime"),
        "preview": msg.get("bodyPreview"),
        "hasAttachments": msg.get("hasAttachments"),
    }


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _handle_list_sites(args: dict, **kwargs) -> str:
    query = (args.get("query") or "").strip() or "*"
    try:
        client = MicrosoftGraphClient.from_env()
        payload = _run(client.get_json("/sites", params={"search": query}))
        sites = payload.get("value") if isinstance(payload, dict) else None
        sites = sites or []
        return json.dumps(
            {"count": len(sites), "sites": [_site_summary(s) for s in sites]},
            ensure_ascii=False,
        )
    except MicrosoftGraphClientError as exc:
        return tool_error(str(exc))
    except Exception as exc:  # noqa: BLE001
        return tool_error(f"msgraph_list_sites failed: {exc}")


def _handle_search_files(args: dict, **kwargs) -> str:
    query = (args.get("query") or "").strip()
    if not query:
        return tool_error("query is required")
    site_id = (args.get("site_id") or "root").strip() or "root"
    try:
        top = int(args.get("top") or 20)
    except (TypeError, ValueError):
        top = 20
    top = max(1, min(top, 100))

    q = _escape_odata_literal(query)
    path = f"/sites/{site_id}/drive/root/search(q='{q}')"
    try:
        client = MicrosoftGraphClient.from_env()
        payload = _run(
            client.get_json(
                path,
                params={
                    "$top": top,
                    "$select": (
                        "id,name,webUrl,size,lastModifiedDateTime,folder,"
                        "parentReference"
                    ),
                },
            )
        )
        items = payload.get("value") if isinstance(payload, dict) else None
        items = items or []
        return json.dumps(
            {
                "site_id": site_id,
                "query": query,
                "count": len(items),
                "files": [_file_summary(i) for i in items],
            },
            ensure_ascii=False,
        )
    except MicrosoftGraphClientError as exc:
        return tool_error(str(exc))
    except Exception as exc:  # noqa: BLE001
        return tool_error(f"msgraph_search_files failed: {exc}")


def _handle_list_mail(args: dict, **kwargs) -> str:
    user = (args.get("user") or "").strip()
    if not user:
        return tool_error("user (mailbox UPN or id) is required")
    query = (args.get("query") or "").strip()
    try:
        top = int(args.get("top") or 10)
    except (TypeError, ValueError):
        top = 10
    top = max(1, min(top, 50))

    params: dict[str, Any] = {
        "$top": top,
        "$select": (
            "id,subject,from,receivedDateTime,bodyPreview,hasAttachments"
        ),
    }
    headers = None
    if query:
        # $search cannot combine with $orderby; escape embedded quotes.
        params["$search"] = '"' + query.replace('"', '\\"') + '"'
    else:
        params["$orderby"] = "receivedDateTime desc"

    try:
        client = MicrosoftGraphClient.from_env()
        payload = _run(
            client.get_json(f"/users/{user}/messages", params=params, headers=headers)
        )
        msgs = payload.get("value") if isinstance(payload, dict) else None
        msgs = msgs or []
        return json.dumps(
            {
                "user": user,
                "count": len(msgs),
                "messages": [_message_summary(m) for m in msgs],
            },
            ensure_ascii=False,
        )
    except MicrosoftGraphClientError as exc:
        return tool_error(str(exc))
    except Exception as exc:  # noqa: BLE001
        return tool_error(f"msgraph_list_mail failed: {exc}")


def _handle_get_mail(args: dict, **kwargs) -> str:
    user = (args.get("user") or "").strip()
    message_id = (args.get("message_id") or "").strip()
    if not user or not message_id:
        return tool_error("both user and message_id are required")
    try:
        client = MicrosoftGraphClient.from_env()
        payload = _run(
            client.get_json(
                f"/users/{user}/messages/{message_id}",
                params={
                    "$select": (
                        "id,subject,from,toRecipients,ccRecipients,"
                        "receivedDateTime,hasAttachments,body"
                    )
                },
            )
        )
        body = payload.get("body") or {}
        result = {
            "id": payload.get("id"),
            "subject": payload.get("subject"),
            "from": _addr(payload.get("from")),
            "to": [_addr(r) for r in (payload.get("toRecipients") or [])],
            "cc": [_addr(r) for r in (payload.get("ccRecipients") or [])],
            "received": payload.get("receivedDateTime"),
            "hasAttachments": payload.get("hasAttachments"),
            "contentType": body.get("contentType"),
            "body": body.get("content"),
        }
        return json.dumps(result, ensure_ascii=False)
    except MicrosoftGraphClientError as exc:
        return tool_error(str(exc))
    except Exception as exc:  # noqa: BLE001
        return tool_error(f"msgraph_get_mail failed: {exc}")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_MSGRAPH_ENV = ["MSGRAPH_TENANT_ID", "MSGRAPH_CLIENT_ID", "MSGRAPH_CLIENT_SECRET"]

registry.register(
    name="msgraph_list_sites",
    toolset="msgraph",
    schema=MSGRAPH_LIST_SITES_SCHEMA,
    handler=_handle_list_sites,
    check_fn=_check_msgraph_available,
    requires_env=_MSGRAPH_ENV,
    emoji="📁",
)

registry.register(
    name="msgraph_search_files",
    toolset="msgraph",
    schema=MSGRAPH_SEARCH_FILES_SCHEMA,
    handler=_handle_search_files,
    check_fn=_check_msgraph_available,
    requires_env=_MSGRAPH_ENV,
    emoji="📁",
)

registry.register(
    name="msgraph_list_mail",
    toolset="msgraph",
    schema=MSGRAPH_LIST_MAIL_SCHEMA,
    handler=_handle_list_mail,
    check_fn=_check_msgraph_available,
    requires_env=_MSGRAPH_ENV,
    emoji="📧",
)

registry.register(
    name="msgraph_get_mail",
    toolset="msgraph",
    schema=MSGRAPH_GET_MAIL_SCHEMA,
    handler=_handle_get_mail,
    check_fn=_check_msgraph_available,
    requires_env=_MSGRAPH_ENV,
    emoji="📧",
)
