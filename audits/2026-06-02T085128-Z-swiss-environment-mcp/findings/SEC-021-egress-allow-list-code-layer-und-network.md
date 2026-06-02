## Finding: SEC-021 — Egress-Allow-List: Code-Layer und Network-Layer

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status (Check)** | ⚠️ PARTIAL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-021` |
| **PDF-Reference** | Anhang B5 + B12 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

SEC-004 (SSRF-Prevention) blockiert Requests an interne IP-Ranges. SEC-021 ergänzt das auf der **anderen Seite**: welche externen Ziele darf der Server überhaupt erreichen?

Defense-in-Depth verlangt zwei Layer:

**1. Code-Layer Allow-List:** Im Server-Code wird vor jedem ausgehenden HTTP-Request geprüft, ob die Ziel-Domain in einer expliziten Allow-Liste steht. Verhindert versehentliche oder durch Prompt-Injection getriggerte Kontakte zu nicht-autorisierten Domains.

**2.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- Upstream-Hosts als feste Modul-Konstanten — impliziter Code-Layer-Allow-List (api_client.py:18-30)

### Gaps gegenüber Pass-Criteria

- Keine explizite frozenset-Allow-List, kein assert_host_allowed-Pre-Request-Check
- Kein Network-Layer-Egress-Control / docs/network-egress.md
- follow_redirects=True umgeht impliziten Allow-List

### Remediation (aus Katalog-Check SEC-021)

### Schritt 1: Allow-List-Inventar

Pro Server alle ausgehenden HTTP-Hosts identifizieren:

```bash
grep -rE 'https://[a-z0-9.-]+' src/ | \
  sed -E 's/.*https:\/\/([a-z0-9.-]+).*/\1/' | sort -u
```

Resultat: minimale Allow-Liste.

### Schritt 2: Code-Layer einbauen

Wie Pass-Pattern Modus 1.

### Schritt 3: Network-Layer einbauen

Bei Kubernetes: NetworkPolicy wie oben. Bei AWS: Security Group mit egress-Rules. Bei Cloudflare WARP: Zero-Trust-Policy.

### Schritt 4: Tests gegen Regression

```python
async def test_egress_blocked_to_non_allowlisted_host():
    with pytest.raises(PermissionError, match="not in allow-list"):
        await fetch_external_data("https://evil.example.com/", mock_ctx())


async def test_egress_allowed_to_allowlisted_host():
    # Mock-Response, kein echter Network-Call
    with respx.mock:
        respx.get("https://opendata.swiss/api/...").respond(200, json={"ok": True})
        result = await fetch_external_data("https://opendata.swiss/api/...", mock_ctx())
        assert result["ok"]
```

### Effort Estimate

M — 1–3 Tage. Code-Layer-Allow-List + Network-Policy + Doku + Tests.

### Verification After Fix

- Re-Audit von `SEC-021` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`
