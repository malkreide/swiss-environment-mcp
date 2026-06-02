## Finding: SEC-009 — Session-ID Cryptographic Binding (user_id:session_id)

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status (Check)** | ⚠️ PARTIAL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-009` |
| **PDF-Reference** | Sec 4.6 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

In statusbehafteten MCP-Setups mit Streamable HTTP / SSE wird jeder Verbindung eine `Mcp-Session-Id` zugewiesen. Diese ID identifiziert den Sitzungszustand auf Server-Seite und wird bei jedem Folge-Request mitgesendet.

**Angriffsmuster (Session Hijacking):**

1. Server generiert vorhersagbare Session-IDs (z.B. inkrementell oder mit schwachem PRNG)
2. Angreifer rät / erschöpft Session-ID-Raum
3. Angreifer sendet bösartiges Event (Tool-Call) mit der erratenen Session-ID
4. Server führt Operation im Kontext des Opfers aus

**Verschärfung in Cloud-Architekturen:** Bei Shared-State-Setups (z.B.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- Kein eigenes Session-/User-Handling im Code; auth_model=none

### Gaps gegenüber Pass-Criteria

- Kein App-Level-Session-Hardening; verlässt sich auf FastMCP-Defaults
- Bei künftiger Auth: User-zu-Session-Binding fehlt — bei aktuellem No-Auth-Public-Setup jedoch geringe reale Exposition

### Remediation (aus Katalog-Check SEC-009)

Volles Pattern oben. Zusätzlich:

### Session-Rotation bei Privilege-Wechsel

```python
@mcp.tool()
async def elevate_to_admin(ctx: Context, justification: str):
    # Bei Privilege-Wechsel neue Session-ID generieren
    new_token = await session_store.create(ctx.user_id, scopes=["admin"])
    ctx.set_response_header("Mcp-Session-Id", new_token)
    # Alte Session invalidieren
    await session_store.invalidate(ctx.session_token)
```

### Logout-Endpoint mit Server-Side-Invalidation

```python
@app.post("/mcp/logout")
async def logout(request: Request):
    session_token = request.headers.get("Mcp-Session-Id")
    if session_token:
        await session_store.invalidate(session_token)
    return Response(status_code=204)
```

### Effort Estimate

M — 1–3 Tage. Session-Manager-Refactoring + Binding-Logic + Tests.

### Verification After Fix

- Re-Audit von `SEC-009` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`
