# Aufgezeichnete Fehlerantworten

Aufgezeichnet am **2026-11-14** über den geteilten Client von
`api_client.get_client()` — gleicher User-Agent, gleiches Timeout, gleiche
DNS-Pinning-Schicht wie im Betrieb. Ungekürzt und nicht nachbearbeitet.

Getrennt von `tests/fixtures/`, weil jener Ordner dem Recorder gehört:
`scripts/record_fixtures.py` zeichnet nur gelungene Werkzeugaufrufe auf und
räumt am Ende alles weg, was sein Plan nicht erzeugt hat.

## Was die Aufzeichnungen belegen

`opendata.swiss` liefert für einen Fehler der CKAN-API kein JSON und keinen
Fehlerstatus, sondern eine HTML-Seite mit **HTTP 200**. Der Status der API
steht nur im Seitentitel. Das Wort davor wechselt mit der Sprache der Seite,
die Zahl nicht.

Dieselbe Anfrage mit einer vorhandenen ID antwortet mit HTTP 200 und
`application/json` — am selben Tag geprüft mit
`id=nationales-beobachtungsnetz-fur-luftfremdstoffe-nabel-stationen`, nicht
aufgezeichnet (16 991 Bytes).

Nicht aufgezeichnet ist eine Seite mit einem **5xx**: Sie lässt sich nicht auf
Zuruf auslösen. Dass sie dieselbe Form hat wie die 4xx-Seiten, ist eine Annahme;
die Tests dazu sind handgeschrieben und sagen das.

## `ckan_package_show_404_de.html`

- **Anfrage:** `GET https://opendata.swiss/api/3/action/package_show?id=gibts-nicht-xyzabc`
- **Zusätzlicher Header:** –
- **Antwort:** HTTP 200, `text/html; charset=utf-8`, `X-Powered-By: Express`
- **Seitentitel:** `Fehler 404 |`
- **Grösse:** 10579 Bytes
- **SHA-256:** `638a659e697a0e793bc1bf4bd1faa6ccea3e341cfc073f88051adb0fff8db618`

## `ckan_package_show_404_fr.html`

- **Anfrage:** `GET https://opendata.swiss/api/3/action/package_show?id=gibts-nicht-xyzabc`
- **Zusätzlicher Header:** `Accept-Language: fr`
- **Antwort:** HTTP 200, `text/html; charset=utf-8`, `X-Powered-By: Express`
- **Seitentitel:** `Erreur 404 |`
- **Grösse:** 10636 Bytes
- **SHA-256:** `1bac9e0caed303d98bc8fa7152e5c77c32ca0048232387b2c544b2b02b198a1f`

## `ckan_package_show_409_de.html`

- **Anfrage:** `GET https://opendata.swiss/api/3/action/package_show`
- **Zusätzlicher Header:** –
- **Antwort:** HTTP 200, `text/html; charset=utf-8`, `X-Powered-By: Express`
- **Seitentitel:** `Fehler 409 |`
- **Grösse:** 10791 Bytes
- **SHA-256:** `bb505d86811081661cce8c765c740ba1f10f74d0a25f01d09555383b22e539d4`
