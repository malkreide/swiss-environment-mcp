## Finding: SEC-004 — SSRF-Prevention: HTTPS-Enforcement + IP-Blocklisting

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status (Check)** | ⚠️ PARTIAL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-004` |
| **PDF-Reference** | Sec 4.4 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

Server-Side Request Forgery (SSRF) entsteht, wenn ein MCP-Server URLs aus User-Input (oder LLM-generierten Args) direkt an HTTP-Clients weitergibt.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- Alle Upstream-Hosts sind feste HTTPS-Konstanten (api_client.py:18-30), User kontrolliert nur Query/Pfad-Segmente
- Kein dynamischer Host aus User-Input

### Gaps gegenüber Pass-Criteria

- follow_redirects=True ohne Re-Validierung des Redirect-Ziels (api_client.py:45) — Redirect zu 169.254.169.254/intern möglich
- Keine IP-Blocklist (private/link-local/loopback), kein Metadata-IP-Block

### Remediation (aus Katalog-Check SEC-004)

Volles Pattern oben. Zusätzlich für Defense-in-Depth:

### Container-Level Egress-Filtering

```yaml
# Kubernetes NetworkPolicy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: mcp-server-egress
spec:
  podSelector:
    matchLabels:
      app: mcp-server
  policyTypes:
    - Egress
  egress:
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
            except:
              - 10.0.0.0/8
              - 172.16.0.0/12
              - 192.168.0.0/16
              - 169.254.0.0/16
              - 127.0.0.0/8
      ports:
        - protocol: TCP
          port: 443
```

### IMDSv2 statt IMDSv1 (AWS-spezifisch)

Falls auf AWS deployed: IMDSv2 mit Hop-Limit 1 erzwingen (verhindert SSRF auch bei Code-Bug).

```bash
aws ec2 modify-instance-metadata-options \
  --instance-id i-xxx \
  --http-tokens required \
  --http-put-response-hop-limit 1
```

### Effort Estimate

M — 1–3 Tage. Egress-Proxy-Setup + URL-Validation-Layer + Tests.

### Verification After Fix

- Re-Audit von `SEC-004` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`
