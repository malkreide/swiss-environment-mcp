"""Eingehende Host/Origin-Prüfung des Streamable-HTTP-Transports (SEC-005).

Auslöser war kein fehlender Schutz, sondern ein zu strenger an der falschen
Adresse. mcp 2.x aktiviert automatisch eine Allow-List auf ``127.0.0.1:*``, wenn
das ``host``-Argument der App loopback-artig aussieht — und
``streamable_http_app()`` defaultet genau darauf. Container setzen laut
Settings-Docstring ``MCP_HOST=0.0.0.0``, also bekam jede Anfrage unter einem
echten Hostnamen HTTP 421.

Der SSE-Zweig war nicht betroffen: dort geht ``host`` an ``mcp.run()``, wo das
SDK den echten Bind sieht. Nur ``build_cors_app()`` liess ihn aus.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from swiss_environment_mcp.server import build_cors_app, build_transport_security, settings

_INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    },
}
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


@pytest.fixture(autouse=True)
def _clean_settings(monkeypatch):
    """`settings` ist modulglobal; Felder pro Test zurücksetzen."""
    monkeypatch.setattr(settings, "mcp_allowed_hosts", "", raising=False)
    monkeypatch.setattr(settings, "mcp_cors_allow_origins", "*", raising=False)
    yield


def test_loopback_bind_is_protected():
    sec = build_transport_security("127.0.0.1", 8000)
    assert sec is not None
    assert sec.enable_dns_rebinding_protection is True
    assert "127.0.0.1:8000" in sec.allowed_hosts


def test_wildcard_bind_without_allowlist_stays_off():
    """Der eigentliche Fix.

    Auf 0.0.0.0 ist der erreichbare Name hier unbekannt, und der
    SDK-Loopback-Default ist genau eine Vermutung — er reproduziert das 421.
    """
    assert build_transport_security("0.0.0.0", 8000) is None


def test_wildcard_bind_with_allowlist_is_protected(monkeypatch):
    monkeypatch.setattr(settings, "mcp_allowed_hosts", "umwelt.example.ch")
    sec = build_transport_security("0.0.0.0", 8000)
    assert sec is not None
    assert "umwelt.example.ch" in sec.allowed_hosts
    # Loopback bleibt drin, sonst brechen Container-Health-Checks.
    assert "127.0.0.1:8000" in sec.allowed_hosts


def test_the_cors_wildcard_default_is_not_copied():
    """Hier besonders wichtig: der CORS-Default dieses Servers ist ``*``.

    Als Origin literal übernommen wäre das ein Eintrag namens ``*``, der nichts
    erlaubt und die Liste unlesbar macht.
    """
    sec = build_transport_security("127.0.0.1", 8000)
    assert "*" not in sec.allowed_origins


def test_explicit_cors_origins_pass_the_transport_check(monkeypatch):
    """Sonst weist der Transport genau die Browser-Clients ab, die CORS erlaubt."""
    monkeypatch.setattr(settings, "mcp_cors_allow_origins", "https://claude.ai")
    sec = build_transport_security("127.0.0.1", 8000)
    assert "https://claude.ai" in sec.allowed_origins


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_all_loopback_forms_count_as_local(host):
    assert build_transport_security(host, 8000) is not None


def _post(app, host_header: str) -> int:
    with TestClient(app) as client:
        return client.post(
            "/mcp", headers={"Host": host_header, **_HEADERS}, json=_INIT
        ).status_code


def test_a_public_bind_is_reachable_again():
    """Die Regression selbst, durch den echten ASGI-Stack.

    Ohne den ``host``-Kwarg ist das ein 421 — der Zustand, den dieser Commit
    behebt.
    """
    assert _post(build_cors_app(None, "0.0.0.0", 8000), "umwelt.example.ch") == 200


def test_configured_host_is_served(monkeypatch):
    monkeypatch.setattr(settings, "mcp_allowed_hosts", "umwelt.example.ch")
    assert _post(build_cors_app(None, "0.0.0.0", 8000), "umwelt.example.ch") == 200


def test_foreign_host_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "mcp_allowed_hosts", "umwelt.example.ch")
    assert _post(build_cors_app(None, "0.0.0.0", 8000), "evil.example.com") == 421


def test_right_host_wrong_port_is_rejected(monkeypatch):
    """Der tragende Fall.

    ``evil.example.com`` allein beweist wenig: ein zurückfallender
    Loopback-Default würde ihn ebenfalls abweisen. Nur „richtiger Hostname,
    falscher Port" unterscheidet eine portgenaue Allow-List von einer, die alles
    durchlässt.
    """
    monkeypatch.setattr(settings, "mcp_allowed_hosts", "umwelt.example.ch:8000")
    assert _post(build_cors_app(None, "0.0.0.0", 8000), "umwelt.example.ch:9999") == 421


def test_allowed_hosts_is_parsed_as_csv(monkeypatch):
    monkeypatch.setattr(settings, "mcp_allowed_hosts", "a.example.ch, b.example.ch")
    assert settings.allowed_hosts() == ["a.example.ch", "b.example.ch"]
