## Finding: SEC-005 — DNS-Rebinding-Prevention: DNS-Pinning gegen TOCTOU

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-005` (Check-Status: partial) |
| **PDF-Reference** | Sec 4.4 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

DNS-Pinning ist korrekt implementiert (Check und Connect atomar im Transport, SNI/Host erhalten) und greift auch für LINDAS über den geteilten Client. Partial, weil die Einmal-Resolution nur in der Substanz, nicht im Wortlaut erfüllt ist und der geforderte 1-DNS-Call-Test fehlt.

Lücken im Detail:
- Pass-Kriterium 'DNS-Resolution erfolgt einmalig' formal verfehlt: assert_host_allowed (api_client.py:154) und _PinnedTransport (Zeile 169) lösen je Request beide auf — zwei getaddrinfo-Calls; die Connect-IP stammt aber aus dem geprüften zweiten Lookup, daher kein ausnutzbares TOCTOU-Fenster
- Kein Test, der 'nur 1 DNS-Call pro Request' verifiziert (Pass-Kriterium); in den gemockten Suiten ist dns_pin_enabled sogar deaktiviert (tests/test_lindas.py:38-39, tests/test_unit.py:56-60), der Pinning-Pfad wird nicht end-to-end getestet

### Expected Behavior

Siehe Pass Criteria in `checks/SEC-005.md` (DNS-Rebinding-Prevention: DNS-Pinning gegen TOCTOU).

### Evidence

- src/swiss_environment_mcp/api_client.py:157-175 — _PinnedTransport löst auf, prüft die IP und setzt request.url.copy_with(host=ip): die geprüfte IP wird für den TCP-Connect verwendet
- src/swiss_environment_mcp/api_client.py:171-174 — sni_hostname-Extension trägt den Original-Hostnamen (TLS-SNI/Zertifikatsprüfung gegen Hostname, nicht IP); Host-Header bleibt der Original-Hostname (beim Request-Bau gesetzt, URL-Rewrite ändert ihn nicht)
- src/swiss_environment_mcp/api_client.py:183-193 — geteilter Client wird mit _PinnedTransport erzeugt; run_sparql (Zeile 271-278) nutzt get_client(), damit gilt das Pinning auch für den neuen LINDAS-Pfad (GET und POST in lindas/client.py laufen über diesen Client)
- tests/test_unit.py:193-215 — test_dns_pin_blocks_internal_ip (169.254.169.254 → SecurityError), test_dns_pin_returns_public_ip, test_client_uses_pinned_transport

### Risk Description

Severity high gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Offen — Behebung gemäss Remediation.

### Remediation

Doppelte DNS-Resolution (assert_host_allowed + _PinnedTransport) auf eine Resolution pro Request zusammenführen (Pin-Ergebnis durchreichen) und einen Unit-Test ergänzen, der genau einen getaddrinfo-Call pro Request verifiziert (Pinning-Pfad aktuell in beiden Suiten deaktiviert).

### Effort Estimate

S
