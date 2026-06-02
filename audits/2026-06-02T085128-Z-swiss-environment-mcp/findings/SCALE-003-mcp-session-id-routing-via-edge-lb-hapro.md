## Finding: SCALE-003 — Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status (Check)** | ⚠️ PARTIAL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SCALE-003` |
| **PDF-Reference** | Sec 5.2 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

Dieser Check ergänzt SCALE-002 (Stateful Load Balancing) mit dem konkreten Routing-Layer. Wenn die Architektur-Entscheidung Sticky Sessions ist, muss der Edge-Load-Balancer den `Mcp-Session-Id`-Header **lesen** und für Routing nutzen.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- Single-Instance-Deployment ohne Edge-LB

### Gaps gegenüber Pass-Criteria

- Kein Mcp-Session-Id-Routing via Edge-LB (HAProxy Stick-Table o.ä.) — relevant erst bei Multi-Instance, aber undokumentiert

### Remediation (aus Katalog-Check SCALE-003)

Für K8s-Ingress (NGINX):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mcp-ingress
  annotations:
    nginx.ingress.kubernetes.io/affinity: "cookie"
    nginx.ingress.kubernetes.io/session-cookie-name: "mcp-route"
    nginx.ingress.kubernetes.io/upstream-hash-by: "$http_mcp_session_id"
spec:
  rules:
  - host: mcp.example.ch
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: mcp-server
            port:
              number: 8080
```

### Effort Estimate

M — 1–3 Tage. LB-Config + Failover-Tests.

### Verification After Fix

- Re-Audit von `SCALE-003` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`
