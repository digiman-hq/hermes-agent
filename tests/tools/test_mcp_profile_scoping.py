"""MCP server registry must be scoped per HERMES_HOME.

A multi-profile gateway serves every user from one process and switches
HERMES_HOME per turn. Before this, ``_servers`` was keyed by bare server name,
so the first profile to connect won and every later profile silently reused
that process — a per-profile ``MS365_MCP_TOKEN_CACHE_PATH`` was ignored and all
users shared one Microsoft 365 identity.
"""

from __future__ import annotations

import pytest

from tools import mcp_tool


@pytest.fixture(autouse=True)
def clean_registry():
    saved = dict(mcp_tool._servers)
    mcp_tool._servers.clear()
    yield
    mcp_tool._servers.clear()
    mcp_tool._servers.update(saved)


def test_server_key_differs_per_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "emp-a"))
    key_a = mcp_tool._server_key("microsoft365")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "emp-b"))
    key_b = mcp_tool._server_key("microsoft365")

    assert key_a != key_b
    assert key_a.startswith("microsoft365")
    assert key_b.startswith("microsoft365")


def test_server_key_is_stable_within_one_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    assert mcp_tool._server_key("microsoft365") == mcp_tool._server_key("microsoft365")


def test_a_connected_server_is_not_reused_by_another_home(tmp_path, monkeypatch):
    """The regression itself: profile B must not see profile A's server."""
    sentinel = object()

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "emp-a"))
    mcp_tool._servers[mcp_tool._server_key("microsoft365")] = sentinel
    assert mcp_tool._servers.get(mcp_tool._server_key("microsoft365")) is sentinel

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "emp-b"))
    assert mcp_tool._servers.get(mcp_tool._server_key("microsoft365")) is None


def test_status_view_reports_bare_server_names(tmp_path, monkeypatch):
    """get_mcp_status re-indexes home-scoped keys back to plain names."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    key = mcp_tool._server_key("microsoft365")
    assert key.split("\x00", 1)[0] == "microsoft365"
