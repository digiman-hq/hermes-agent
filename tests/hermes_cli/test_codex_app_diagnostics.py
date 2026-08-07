from __future__ import annotations

from hermes_cli import codex_app_diagnostics as diag


def test_extract_apps_accepts_common_response_shapes():
    assert diag._extract_apps({"apps": [{"name": "SharePoint"}, {"title": "Outlook"}]}) == [
        "SharePoint",
        "Outlook",
    ]
    assert diag._extract_apps({"items": [{"displayName": "Microsoft 365"}]}) == [
        "Microsoft 365"
    ]
    assert diag._extract_apps({"data": [{"identifier": "onedrive"}]}) == ["onedrive"]


def test_dump_codex_apps_returns_binary_error_without_spawning(monkeypatch):
    from agent.transports import codex_app_server

    monkeypatch.setattr(
        codex_app_server,
        "check_codex_binary",
        lambda: (False, "codex CLI not found"),
    )

    payload = diag.dump_codex_apps()

    assert payload["codex_binary_ok"] is False
    assert payload["codex_error"] == "codex CLI not found"
    assert payload["plugin_list"] is None
    assert payload["app_list"] is None


def test_dump_codex_apps_queries_plugin_and_app_lists(monkeypatch, tmp_path):
    from agent.transports import codex_app_server

    calls = []

    class FakeClient:
        def __init__(self, codex_home=None):
            self.codex_home = codex_home

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def initialize(self, client_name, timeout):
            calls.append(("initialize", client_name, self.codex_home, timeout))
            return {"userAgent": "codex-test"}

        def request(self, method, params, timeout):
            calls.append((method, params, timeout))
            return {"ok": method}

    monkeypatch.setattr(codex_app_server, "check_codex_binary", lambda: (True, "0.130.0"))
    monkeypatch.setattr(codex_app_server, "CodexAppServerClient", FakeClient)

    payload = diag.dump_codex_apps(codex_home=str(tmp_path), timeout=3.0)

    assert payload["codex_binary_ok"] is True
    assert payload["codex_version"] == "0.130.0"
    assert payload["initialize"] == {"userAgent": "codex-test"}
    assert payload["plugin_list"] == {"ok": "plugin/list"}
    assert payload["app_list"] == {"ok": "app/list"}
    assert ("initialize", "hermes-codex-app-diagnostics", str(tmp_path), 3.0) in calls
    assert ("plugin/list", {}, 3.0) in calls
    assert ("app/list", {}, 3.0) in calls
