"""Diagnostics for Codex app-server account plugins and apps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def dump_codex_apps(*, codex_home: str | None = None, timeout: float = 15.0) -> dict[str, Any]:
    """Return raw plugin/list and app/list results from `codex app-server`.

    The payload is intentionally raw: connector availability varies by Codex
    CLI version, ChatGPT account, workspace policy, and installed plugins. The
    operator needs the live server response to decide whether Microsoft 365 can
    use Codex-native connectors or must fall back to a Graph/MCP path.
    """
    from agent.transports.codex_app_server import CodexAppServerClient, check_codex_binary

    ok, version_or_error = check_codex_binary()
    result: dict[str, Any] = {
        "codex_binary_ok": ok,
        "codex_version": version_or_error if ok else None,
        "codex_error": None if ok else version_or_error,
        "codex_home": str(Path(codex_home).expanduser()) if codex_home else None,
        "plugin_list": None,
        "plugin_list_error": None,
        "app_list": None,
        "app_list_error": None,
    }
    if not ok:
        return result

    try:
        with CodexAppServerClient(
            codex_home=str(Path(codex_home).expanduser()) if codex_home else None
        ) as client:
            init = client.initialize(
                client_name="hermes-codex-app-diagnostics",
                timeout=timeout,
            )
            result["initialize"] = init
            for method, key in (("plugin/list", "plugin_list"), ("app/list", "app_list")):
                try:
                    result[key] = client.request(method, {}, timeout=timeout)
                except Exception as exc:  # noqa: BLE001 - diagnostic path
                    result[f"{key}_error"] = str(exc)
    except Exception as exc:  # noqa: BLE001 - diagnostic path
        result["codex_error"] = str(exc)
    return result


def print_codex_apps_summary(payload: dict[str, Any]) -> None:
    """Print a compact human-readable summary for terminal use."""
    if not payload.get("codex_binary_ok"):
        print(f"codex CLI: unavailable ({payload.get('codex_error')})")
        return

    print(f"codex CLI: {payload.get('codex_version')}")
    if payload.get("codex_error"):
        print(f"codex app-server: {payload['codex_error']}")
        return

    plugin_list = payload.get("plugin_list")
    if payload.get("plugin_list_error"):
        print(f"plugin/list: error: {payload['plugin_list_error']}")
    else:
        installed: list[str] = []
        for marketplace in (plugin_list or {}).get("marketplaces") or []:
            market_name = marketplace.get("name") or "openai-curated"
            for plugin in marketplace.get("plugins") or []:
                if plugin.get("installed"):
                    installed.append(f"{plugin.get('name')}@{market_name}")
        print(f"plugin/list: {len(installed)} installed plugin(s)")
        for name in installed:
            print(f"  - {name}")

    app_list = payload.get("app_list")
    if payload.get("app_list_error"):
        print(f"app/list: error: {payload['app_list_error']}")
    else:
        apps = _extract_apps(app_list)
        print(f"app/list: {len(apps)} app entry/entries")
        for app in apps:
            print(f"  - {app}")


def print_codex_apps_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _extract_apps(value: Any) -> list[str]:
    """Best-effort app names from several app/list response shapes."""
    if not isinstance(value, dict):
        return []
    candidates = value.get("apps")
    if candidates is None:
        candidates = value.get("items")
    if candidates is None:
        candidates = value.get("data")
    if not isinstance(candidates, list):
        return []
    names: list[str] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        name = (
            item.get("name")
            or item.get("title")
            or item.get("displayName")
            or item.get("id")
            or item.get("identifier")
        )
        if name:
            names.append(str(name))
    return names
