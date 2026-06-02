## Finding: SEC-016 — 0.0.0.0-Binding-Prevention (NeighborJack)

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status (Check)** | ⚠️ PARTIAL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-016` |
| **PDF-Reference** | Sec 4 (Empirie 2025) |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

Die empirische Untersuchung von 2025 ergab: ein erheblicher Teil der OSS-MCP-Server bindet ihren HTTP-Listener an `0.0.0.0` (alle Interfaces) und vertraut implizit darauf, dass Firewall-Regeln den Zugang beschränken. Auf einem Entwickler-Laptop in einem öffentlichen WLAN, einem Co-Working-Space oder einer Konferenz wird der lokale MCP-Server damit für **alle** Geräte im selben Subnetz erreichbar.

**Angriff (NeighborJack):**

1. Entwickler startet lokalen MCP-Server für Tests, gebunden an `0.0.0.0:8080`
2.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- Kein 0.0.0.0 im Code hardcoded (grep ohne Treffer) — sicherer FastMCP-Default 127.0.0.1

### Gaps gegenüber Pass-Criteria

- Kein MCP_HOST-Env-Mechanismus; Dockerfile setzt kein MCP_HOST=0.0.0.0 — Cloud-Deploy (Render) bindet ggf. nur 127.0.0.1 und ist nicht erreichbar (latenter Deploy-Bug)
- Keine README-Erklärung lokal vs. Container

### Remediation (aus Katalog-Check SEC-016)

### Schritt 1: Code-Default auf 127.0.0.1 ändern

```diff
  if __name__ == "__main__":
      transport = os.environ.get("MCP_TRANSPORT", "stdio")
      if transport == "sse":
-         mcp.run(transport="sse", host="0.0.0.0", port=8000)
+         host = os.environ.get("MCP_HOST", "127.0.0.1")
+         port = int(os.environ.get("MCP_PORT", "8000"))
+         mcp.settings.host = host
+         mcp.settings.port = port
+         mcp.run(transport="sse")
```

### Schritt 2: Container-Override im Dockerfile

```dockerfile
ENV MCP_HOST=0.0.0.0
```

### Schritt 3: Docker-Compose Bind-Adresse

```yaml
# docker-compose.yml
services:
  mcp:
    image: malkreide/zurich-opendata-mcp
    ports:
-     - "8000:8000"           # bindet an alle Interfaces
+     - "127.0.0.1:8000:8000" # nur lokal erreichbar
```

### Schritt 4: Warnung bei riskantem Binding

```python
import logging
import socket

def warn_on_dangerous_binding(host: str):
    if host in ("0.0.0.0", "::"):
        # Container-Detection (heuristisch)
        in_container = (
            os.path.exists("/.dockerenv")
            or os.environ.get("KUBERNETES_SERVICE_HOST")
            or os.environ.get("RAILWAY_PROJECT_ID")
        )
        if not in_container:
            logging.warning(
                "Binding to %s outside container context. "
                "This exposes the MCP server to the local network. "
                "Use MCP_HOST=127.0.0.1 for local development.",
                host,
            )
```

### Schritt 5: README-Dokumentation

```markdown

### Effort Estimate

S — < 1 Tag. Default-Änderung + Dockerfile-ENV + README-Update + Test.

### Verification After Fix

- Re-Audit von `SEC-016` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`
