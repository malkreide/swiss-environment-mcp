## Finding: ARCH-012 — protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status (Check)** | ❌ FAIL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `ARCH-012` |
| **PDF-Reference** | Anhang A9 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

Die MCP-Spec hat in 13 Monaten vier Major-Updates erlebt (2024-11, 2025-03, 2025-06, 2025-11). Das ist eine ungewöhnlich hohe Velocity für einen Industriestandard. Konkrete Folgen für Server-Maintainer:

1. **Tool Annotations** kamen erst 2025-03-26
2. **OAuth Resource Server** mit RFC 8707 wurde erst 2025-06-18 verpflichtend
3.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- CHANGELOG.md im Keep-a-Changelog-Format vorhanden

### Gaps gegenüber Pass-Criteria

- Kein protocolVersion-Pinning im Server-Code (Default des SDK)
- Keine README-Sektion 'MCP Protocol Version' / Update-Policy
- Kein Dependabot/Renovate

### Remediation (aus Katalog-Check ARCH-012)

### Schritt 1: protocolVersion pinnen

```diff
+ from importlib.metadata import version

  mcp = FastMCP(
      name="zh-education-mcp",
+     protocol_version="2025-06-18",
  )
```

### Schritt 2: CHANGELOG initialisieren

Wenn nicht vorhanden, mit Template starten und retroaktiv Major-Versionen dokumentieren (mindestens letzte 3).

### Schritt 3: Dependabot konfigurieren

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "monthly"
    open-pull-requests-limit: 5
```

### Schritt 4: Quartalsweise Spec-Review

Im Audit-Tracker (Notion) oder GitHub Issues ein recurring Reminder für quartalsweise Spec-Velocity-Review:

- Was hat sich an der MCP-Spec geändert seit letztem Release?
- Welche Server müssen ihre `protocolVersion` aktualisieren?
- Gibt es Compliance-relevante Spec-Änderungen?

### Effort Estimate

S — < 1 Tag pro Server. Pinning + CHANGELOG-Template + Dependabot-Setup.

### Verification After Fix

- Re-Audit von `ARCH-012` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`
