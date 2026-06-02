## Finding: SCALE-004 — Containerization mit Multi-Stage-Builds

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status (Check)** | ❌ FAIL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SCALE-004` |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

Container-Images für MCP-Server sind oft 800 MB – 1.5 GB gross, weil Build-Toolchains (gcc, Rust, npm-build-deps) im finalen Image bleiben. Multi-Stage-Builds trennen Build und Runtime: das finale Image enthält nur den fertigen Server plus minimale Runtime-Dependencies (typischerweise 80–150 MB).

Vorteile über Image-Grösse hinaus: kleinere Angriffsfläche (kein gcc, kein curl, keine Test-Tools im Production-Image), schnellere Pull-Zeiten (relevant bei Auto-Scaling), weniger CVE-Treffer im Container-Scan.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- Dockerfile auf python:3.12-slim Base

### Gaps gegenüber Pass-Criteria

- Single-Stage-Build (1x FROM), kein Multi-Stage
- Keine HEALTHCHECK-Direktive (render.yaml erwartet healthCheckPath /health — Endpoint existiert aber nicht!)
- Kein non-root USER

### Remediation (aus Katalog-Check SCALE-004)

```diff
- FROM python:3.11
- WORKDIR /app
- COPY . .
- RUN pip install -e .
- CMD ["python", "-m", "server"]
+ FROM python:3.11-slim AS builder
+ WORKDIR /build
+ COPY pyproject.toml .
+ COPY src/ ./src/
+ RUN pip install --no-cache-dir --user -e .
+
+ FROM python:3.11-slim AS runtime
+ COPY --from=builder /root/.local /root/.local
+ COPY src/ /app/src/
+ WORKDIR /app
+ ENV PATH=/root/.local/bin:$PATH PYTHONUNBUFFERED=1
+ USER nobody
+ HEALTHCHECK CMD curl -f http://localhost:8000/healthz || exit 1
+ CMD ["python", "-m", "server"]
```

### Effort Estimate

S — < 1 Tag.

### Verification After Fix

- Re-Audit von `SCALE-004` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`
