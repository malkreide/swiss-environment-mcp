## Finding: SCALE-006 — Resource-Limits per Container (Memory, CPU, FDs)

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status (Check)** | ⚠️ PARTIAL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SCALE-006` |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

Ohne explizite Resource-Limits kann ein einzelner MCP-Server-Bug das ganze System destabilisieren: ein Memory-Leak frisst die Host-Ressourcen, ein File-Descriptor-Leak öffnet Tausende dangling Connections, ein CPU-bound Query starvt nachbar-Pods. In Multi-Tenant-Cloud-Umgebungen (Railway, Render, K8s) müssen Memory, CPU, FDs explizit gedeckelt werden.

Faustregeln für MCP-Server: 256 MB – 1 GB RAM (je nach Daten-Cache), 0.5–1 CPU, FD-Limit 1024 (Standard reicht meistens). Bei Hybrid-Servern mit lokalem Dump-Cache eher 1–2 GB RAM einplanen.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- render.yaml plan: starter; Resource-Limit-Strategie in docs/scaling.md dokumentiert (#8); httpx-Timeouts gesetzt

### Gaps gegenüber Pass-Criteria

- Keine harten Memory/CPU-Limits in render.yaml/Docker explizit gesetzt — nur dokumentiert

### Remediation (aus Katalog-Check SCALE-006)

Für Railway: in der Web-UI unter Project Settings → Resources die Limits setzen.

Für Docker-Compose-Production:

```yaml
services:
  mcp:
    image: malkreide/mcp-server:v0.1.0
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
    ulimits:
      nofile:
        soft: 4096
        hard: 8192
```

### Effort Estimate

S — < 1 Tag pro Server.

### Verification After Fix

- Re-Audit von `SCALE-006` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`
