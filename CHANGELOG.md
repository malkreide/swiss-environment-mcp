# Änderungsprotokoll / Changelog

Alle wesentlichen Änderungen werden in dieser Datei dokumentiert.
Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).

## [Unreleased]

### Fixed

- **`env_hydro_stations` beantwortete jede Kantonsabfrage mit fünf hartkodierten
  Beispielstationen.** Den Kantons-Code lieferte allein
  `hydrodaten.admin.ch/lhg/az/json/mobile_stations.json`; dieser Endpoint ist
  stillgelegt und antwortet mit 404 — für zwei Nachbar-Endpoints unter `/lhg/az/`
  war das im Code bereits vermerkt, für diesen nicht. Der Kanton-Pfad ging per
  Konstruktion dorthin, lief ins 404 und landete im Fallback. Für `canton='ZH'`
  kamen drei Stationen mit plausiblen Namen zurück; nichts daran war als
  eingebettete Beispielliste zu erkennen.

  Neu sagt das Tool ab: es nennt die stillgelegte Quelle, hält fest, dass **nicht
  gesucht** wurde, und verweist auf `water_body` und die vollständige Liste. Kein
  Request geht dafür mehr raus. `fetch_hydro_stations` ist entfernt — LINDAS
  trägt die Stationsliste (233 Stationen), führt aber kein Kantons-Attribut.

  Die Absage behauptet bewusst nichts über den übergebenen Wert: `canton` ist
  nicht gegen die 26 Kantone validiert, ein `XX` kommt durch, und ein Satz wie
  «dort gibt es Messstationen» wäre dann schlicht falsch.

  Mitgezogen sind die **Feld-Beschreibung** im Input-Schema und beide READMEs.
  MCP-Clients lesen das Schema, nicht den Docstring des Tools; stünde dort weiter
  «Kantonskürzel zum Filtern», würden Modelle den Parameter wählen und eine
  Absage ernten.

- **Der Ausfall-Fallback von `env_hydro_stations` ignorierte
  `response_format`.** Er baute Markdown und gab es zurück, auch wenn der
  Aufrufer die Envelope angefordert hatte — ein Client, der JSON parst, bekam
  ausgerechnet im Störungsfall Text, an dem `json.loads` scheitert. Der Fallback
  liefert jetzt beide Formate; im JSON steht `provenance: "fallback"` und eine
  `note`, die die Liste als eingebettete Auswahl statt als Suchergebnis
  ausweist. Im Markdown steht dasselbe in der Überschrift der Tabelle.

  5 neue bzw. umgeschriebene Tests, darunter der tragende Fall „Kantonsabfrage
  setzt keinen einzigen Request ab" — nur er unterscheidet die Absage von einem
  Fallback, der bloss anders formuliert ist.

- **Die Zusicherungen der Live-Suite waren wirkungslos (OPS-001).** `check()`
  druckte bei einem Fehlschlag ein ❌ und zählte hoch — mehr nicht. Unter pytest
  scheitert ein Test aber ausschliesslich an einer durchschlagenden Exception,
  und das `sys.exit(1)` steht in `main()`, also im Standalone-Pfad
  (`python tests/test_integration.py`), den die CI nie aufruft. Alle ~100
  Zusicherungen von `test_integration.py` waren damit Dekoration; rot wurde der
  nächtliche Job nur, wenn ein Tool eine Exception warf.

  Nachweis, dass das nicht theoretisch war: zwei Zusicherungen in
  `test_nabel_stations` scheiterten seit der Envelope-Umstellung (SDK-002)
  unbemerkt — sie prüften `total` und `nabel_stationen`, während das Tool längst
  `count`/`results`/`match_type` liefert. Der Job war jede Nacht grün.

  `check()` wirft neu einen `AssertionError`. Bewusst sofort statt gesammelt:
  so meldet pytest einen regulären FAILED-Test statt eines Fehlers im Teardown.
  `main()` fängt ihn ab, damit der Standalone-Lauf weiterhin alle Tests
  durchläuft und am Ende bilanziert. Die zwei veralteten NABEL-Zusicherungen
  sind auf die Envelope-Form nachgezogen.

  Damit ein Netzausfall dadurch nicht doch als Vertragsbruch erscheint, reicht
  `_tool_text` einen `ToolError` durch, hinter dem ein reiner Transportfehler
  steckt — der Hook stuft ihn dann zu SKIPPED herab, statt die Meldung durch die
  Zusicherungen fallen zu lassen. End-to-end geprüft: mit einem Transport, der
  jeden Connect in einen Timeout laufen lässt, endet die Live-Suite mit
  11 skipped / 7 passed (die netzwerkfreien Tools) und **0 failed**.

- **`env_snow_stations` und `env_avalanche_bulletin` bestanden ihre Live-Tests
  auch bei totem SLF.** Beide Tests liefen über `_tool_text`, das den
  `ToolError` abfängt, und prüften dann nur, ob „SLF" bzw. „Bulletin" im Text
  steht — was die Fehlermeldungen („SLF-Stationsliste nicht abrufbar",
  „Lawinenbulletin nicht abrufbar") ebenfalls erfüllen. Die Tests konnten
  nichts widerlegen.

  Neu prüfen sie den Nutzinhalt: `env_snow_stations` gegen die JSON-Hülle
  (nicht-leere GR-Trefferliste, `count` konsistent, Kantonsfilter greift, alle
  fünf Felder vorhanden, aus denen die Tabelle gebaut wird) und gegen die
  gerenderte Markdown-Tabelle; `env_avalanche_bulletin` gegen die beiden
  gültigen Saison-Zweige, die unterscheidbar bleiben müssen (Zweig-Logik selbst
  ist gemockt abgedeckt). Beide rufen das Tool direkt auf, damit ein `ToolError`
  durchschlägt.

  Mutationsgeprüft gegen einen Upstream, der **antwortet**, aber nicht mehr das
  Erwartete: bei umbenanntem Feld (`elevation` → `hoehe`, leeres Kantonsfeld)
  und bei HTTP 500 bestanden beide Tests vorher — jetzt scheitern sie. Bei
  unerreichbarem SLF bestanden sie vorher ebenfalls; jetzt werden sie
  übersprungen, mit genanntem Zielhost.

- **Der nächtliche Live-Lauf wurde rot, wenn ein Upstream kurz nicht ans
  Telefon ging (OPS-001).** Am 03.08.2026 riss `test_slf_snow` den Job mit
  `httpx.ConnectTimeout` gegen `measurement-api.slf.ch` — dreimal in Folge, denn
  der Client wiederholt transiente Fehler bereits selbst (3 Versuche in ~16 s).
  Dieselbe API antwortete davor und danach; von 15 Läufen scheiterten drei, je
  an einem anderen Host.

  Diese Tests prüfen den **Vertrag** echter Fremd-APIs: liefert die Quelle noch,
  was dieser Server aus ihr liest? Kam die Verbindung gar nicht erst zustande,
  beantwortet der Lauf diese Frage nicht — er scheiterte an der Leitung. Ein
  roter Job behauptet dann einen Befund, den es nicht gibt, und genau das
  stumpft den nächtlichen Alarm ab.

  Ein Hook in `tests/conftest.py` stuft deshalb einen `live`-Test, der an einem
  reinen Transportfehler scheitert, zu SKIPPED herab. Die Exception-**Kette**
  wird dabei mitgelaufen, weil die Tools den httpx-Fehler einpacken
  (`ToolError` mit `__context__`, LINDAS `QueryTimeoutError` mit `__cause__`) —
  ohne Kettenlauf würde nur der direkte API-Aufruf erkannt.

  Bewusst weiterhin **rot**: alles, was eine Antwort voraussetzt — HTTP 4xx/5xx,
  geändertes Schema, verletzte Assertions, ein `SecurityError` des
  Egress-Guards. Ebenso rot bleibt ein Transportfehler in der gemockten
  Standard-Suite: dort gibt es kein Netz, das ausfallen könnte.

  Übersprungen heisst nicht unsichtbar: `pytest_terminal_summary` schreibt einen
  eigenen Block mit Zielhost und Fehlerklasse. Trifft es denselben Host mehrere
  Nächte hintereinander, ist der Dienst tatsächlich weg — dann untersuchen.

  9 neue Tests, darunter der tragende Fall „HTTP 500 ist kein Transportfehler"
  — nur er unterscheidet die Herabstufung von einem generellen
  Live-Fehler-Schlucker. End-to-end mutationsgeprüft: mit einem Transport, der
  für `*.slf.ch` einen `ConnectTimeout` wirft, meldet `test_slf_snow` ohne den
  Hook exakt den CI-Fehler (`FAILED … - httpx.ConnectTimeout`) und mit ihm
  SKIPPED samt genanntem Zielhost.

  Geprüft mit den wörtlichen CI-Kommandos: 152 passed / 1 skipped / 23
  deselected, `pytest -m live` 23 passed, `ruff check` und
  `ruff format --check` über `src/ tests/ scripts/` clean.

- **Streamable-HTTP wies unter jedem echten Hostnamen mit 421 ab (SEC-005).**
  `build_cors_app()` rief `mcp.streamable_http_app()` ohne `host` auf. Unter
  mcp 2.x ist das kein neutraler Default: das SDK leitet daraus seine
  Host-Allow-List ab und aktiviert bei loopback-artigem Wert automatisch
  `127.0.0.1:*`. Da das Argument selbst auf `127.0.0.1` defaultet, traf das jeden
  Container mit `MCP_HOST=0.0.0.0` (Dockerfile/render.yaml). Vor der Migration
  ging `host` an den `FastMCP`-Konstruktor, wo dieselbe Logik den echten Bind sah
  und den Schutz korrekt ausliess.

  Der **SSE-Zweig war nicht betroffen**: dort geht `host` an `mcp.run()`, wo das
  SDK den echten Bind sieht. Nur der Streamable-HTTP-Pfad liess ihn aus.

  Der Bind reist jetzt in die App, und eine echte Allow-List wird aus dem neuen
  `MCP_ALLOWED_HOSTS` gebaut. Ohne diese Variable bleibt der Schutz auf einem
  Nicht-Loopback-Bind bewusst aus und der Aufrufer warnt — eine geratene Liste
  wäre genau der 421-Fall.

  Der CORS-Default dieses Servers ist `*`; als Transport-Origin wird er bewusst
  nicht übernommen, weil Origins literal verglichen werden und ein Eintrag `*`
  nichts erlauben würde. Ein Test hält das fest.

  13 neue Tests, darunter der tragende Fall „richtiger Hostname, falscher Port"
  — nur er unterscheidet eine portgenaue Allow-List von einer, die alles
  durchlässt. Mutationsgetestet: nimmt man den `host`-Kwarg wieder weg,
  reproduziert der Test das 421.

  Geprüft mit den wörtlichen CI-Kommandos: 143 passed / 1 skipped / 23
  deselected, `ruff check src/` clean, `ruff format --check src/` (10 files
  already formatted).


## [0.5.3] - 2026-08-02

### Behoben

- **`structlog` hatte keine Obergrenze, und der Index fuehrt bereits einen Major
  oberhalb der Untergrenze.** Deklariert war `structlog>=24.1.0`; auf PyPI liegt
  `26.1.0`. Das Artefakt aendert sich nicht — die Antwort des Resolvers auf
  die naechste frische Installation schon, und genau so wurde
  `swiss-energy-mcp` 0.3.3 uninstallierbar, als `mcp` 2.0.0 das Modul entfernt
  hat, das es importierte.

  Neu `structlog>=24.1.0,<27`. Die Grenze ist gemessen, nicht geraten: dieses Paket installiert
  und importiert heute gegen `structlog 26.1.0`, die Obergrenze laesst also zu,
  was nachweislich funktioniert, und stoppt nur den naechsten, unbekannten
  Major.

Ein Abhaengigkeitsbereich erreicht die Nutzenden nur ueber ein neues
Release, daher der Versions-Bump. Am Code aendert sich nichts.

## [0.5.2] – 2026-07-29

Wartungs-Release. Beseitigt den letzten von Hand gepflegten Versionsstring in
`src/`: der User-Agent kommt neu aus den Paket-Metadaten. Für Nutzende ändert
sich nichts — die 21 Tools sind unverändert, der ausgehende User-Agent ist bei
installiertem Paket bitgleich zu v0.5.1. Er entsteht nur nicht mehr manuell.

### Geändert / Changed

- **User-Agent kommt aus den Paket-Metadaten.** `__version__` wird neu über
  `importlib.metadata.version()` aus der installierten Distribution gelesen,
  der User-Agent daraus zusammengesetzt (`USER_AGENT` in `__init__.py`). Damit
  entfällt der letzte von Hand gepflegte Versionsstring in `src/` — die
  Fehlerklasse, die den Server von v0.2.0 bis v0.5.0 mit einer falschen
  Version gegenüber jedem Upstream auftreten liess und in v0.5.1 erneut
  manuell nachgezogen werden musste. Ohne Installation (reiner
  Quell-Checkout) meldet der Server `0+unknown` statt einer erfundenen
  Nummer.

### Behoben / Fixed

- **`__version__` stand auf `0.1.0`.** Das Dunder in `__init__.py` war seit
  dem Initial-Release nie mitgezogen worden und damit noch weiter abgedriftet
  als der User-Agent. Es wurde bislang nirgends ausgewertet, wäre aber die
  naheliegende Quelle für jede Integration gewesen, die die Serverversion
  wissen will. Entfällt jetzt als eigenständiger Wert.

### Tests / CI

- **`check_version_sync.py` verbietet hartkodierte Versionen in `src/`.** Der
  Check vergleicht weiterhin `pyproject.toml` mit `server.json` und meldet
  zusätzlich jedes Versionsliteral unter `src/` (User-Agent-Form und
  `__version__`-Zuweisung). Läuft weiterhin ohne Projekt-Installation im
  `lint`-Job.
- **Die Versions-Badges beider READMEs sind neu im selben Check.** Sie waren
  die dritte Stelle mit einer Versionsnummer und die einzige, die nichts
  erzwang — beim Bump auf 0.5.2 aufgefallen. Rein kosmetisch, aber dieselbe
  Drift-Klasse wie `server.json`: nur sichtbar, wenn jemand hinschaut.
- **Zwei Unit-Tests** (`tests/test_unit.py`): der UA-Header muss aus
  `__version__` gebaut sein, und die installierten Metadaten müssen zu
  `pyproject.toml` passen. Der zweite Test hat beim Schreiben sofort einen
  veralteten editable Install aufgedeckt und wird ohne Installation
  übersprungen statt zu scheitern.

## [0.5.1] – 2026-07-28

Wartungs-Release der **Release-Infrastruktur**. Funktional ändert sich nichts:
die 21 Tools sind unverändert, die einzige Anpassung in `src/` ist der
Versionsstring im User-Agent. Wer das Paket nutzt, bekommt nichts Neues — der
Release existiert, damit die neuen CI-/Release-Bausteine einen getaggten Stand
haben.

### Neu / Added

- **Workflow «Draft Release»** (`.github/workflows/draft-release.yml`, manuell
  via `workflow_dispatch`): legt aus dem passenden `CHANGELOG.md`-Abschnitt ein
  **Draft**-Release an, ohne dass lokal ein Tag gepusht werden muss — GitHub
  erzeugt den Tag erst beim Veröffentlichen. Mit Guards gegen
  Versionsabweichung zu `pyproject.toml`, bereits existierende Tags/Releases und
  fehlende CHANGELOG-Abschnitte. Veröffentlicht **bewusst nicht** selbst: das
  löst über `publish.yml` PyPI und die MCP Registry aus und ist unumkehrbar,
  daher bleibt der letzte Schritt ein bewusster Klick. Release-Verfahren in
  `CONTRIBUTING.md` / `CONTRIBUTING.de.md` dokumentiert.
- **CI-Check «Versions-Sync»** (`scripts/check_version_sync.py`, im `lint`-Job):
  vergleicht `pyproject.toml` mit `server.json → version` **und** jedem
  `packages[*].version` und bricht bei Abweichung ab. Schliesst die Lücke, durch
  die das Registry-Manifest von v0.2.3 bis v0.5.0 unbemerkt veraltet war —
  `publish.yml` überschreibt die Version beim Veröffentlichen aus dem Tag,
  weshalb die committete Datei nie auffällig wurde. Nur Standardbibliothek
  (`tomllib`), lokal ausführbar.

### Geändert / Changed

- **User-Agent auf 0.5.1 mitgezogen.** Der Versionsstring in `api_client.py`
  wird bei jedem Release von Hand gepflegt — bleibt er stehen, entsteht genau
  die Drift, die in v0.5.0 nach drei Releases aufgefallen ist. Bis er aus den
  Paket-Metadaten gelesen wird, gehört er in jeden Versionsbump.

### Behoben / Fixed

- **`server.json` auf 0.5.0 nachgezogen.** Das MCP-Registry-Manifest stand seit
  v0.2.3 auf einer veralteten Version und war damit über mehrere Releases hinweg
  nicht mit `pyproject.toml` synchron. Rein kosmetisch: `publish.yml`
  synchronisiert die Version beim Veröffentlichen ohnehin aus dem Tag-Namen,
  weshalb in der Registry korrekt 0.5.0 publiziert wurde. Die committete Datei
  spiegelt jetzt den tatsächlichen Stand, statt beim Lesen in die Irre zu führen.
- **Draft Release: führende und nachfolgende Leerzeilen im Release-Body.** Die
  Extraktion begann bei der Leerzeile unter der CHANGELOG-Überschrift und endete
  bei den Leerzeilen vor der nächsten — im ersten Lauf (v0.5.0-Entwurf) als
  Abstand am Anfang sichtbar. Der Abschnitt wird jetzt getrimmt; die
  Leer-Prüfung greift neu **nach** dem Trimmen, damit ein Abschnitt aus reinen
  Leerzeilen genauso abbricht wie ein fehlender.

## [0.5.0] – 2026-07-28

Additive Erweiterung um den **Lärmbelastungskataster Fluglärm** des BAZL
(via `api3.geo.admin.ch`). Drei neue Tools, keine Änderung an den 18
bestehenden. Damit ist das Tool-Budget des Servers bei **21 Tools**
ausgeschöpft — weitere Datenquellen gehören in einen eigenen `*-mcp`-Server.

### Neu / Added

- **`env_noise_aircraft_at`** — Fluglärmbelastung an einer LV95-Koordinate.
  Löst die überlappenden Lärmkurven auf und liefert eine **dB-Klammer** mit dem
  höchsten Wert als ausgewiesener oberer Schranke, dazu alle gefundenen Kurven,
  Kataster-Provenienz und den amtlichen PDF-Link. Kein Treffer ergibt ein
  sprechendes «kein Kataster an diesem Standort», nie ein stilles `[]`.
- **`env_noise_aircraft_registers`** — Provenienz-Tool: welche Flugplätze haben
  einen publizierten Kataster, mit welchem Gültigkeitsdatum, welchem
  dB-Bereich und welchem amtlichen Plan. Beantwortet «wie alt ist die
  Grundlage».
- **`env_noise_limits_check`** — Vergleich eines Beurteilungspegels gegen die
  LSV-Belastungsgrenzwerte (Planungswert / Immissionsgrenzwert / Alarmwert)
  nach Empfindlichkeitsstufe ES I–IV. Rein lokale Berechnung, kein Netzwerk.
- **Neues Modul `geoadmin.py`** — extraktionsfähig aufgebaut wie `lindas/`:
  kennt weder den geteilten HTTP-Client noch den Egress-Guard, beide werden
  vom Aufrufer übergeben. Enthält LV95-Validator, identify-Transport,
  Kurvenauflösung und die verifizierten LSV-Tabellen.
- **LV95-Plausibilitätsvalidator (fail-fast).** Eingaben müssen LV95 sein
  (E 2'480'000–2'840'000 / N 1'070'000–1'300'000). WGS84-Grad wie `8.54/47.37`
  scheitern **vor** der Typkoerzierung mit einem Umrechnungshinweis statt mit
  «keine gültige Ganzzahl» — der häufigste LLM-Fehler bei Schweizer Geodaten.
  Portiert aus `swisstopo-mcp/coords.py`.
- **Erweiterter Response-Envelope `NoiseEnvelope`** mit `retrieved_at`,
  `source_freshness` und `legal_notice`. Bewusst ein eigenes Modell statt einer
  Änderung am bestehenden `ResponseEnvelope` — die 18 Bestands-Tools bleiben
  unangetastet.
- **Rechtlicher Hinweis in jeder Antwort** der drei Tools (auch im
  degraded-Fall), nicht nur im README: der Kataster ist eine
  Orientierungsgrundlage, rechtsverbindlich sind kantonale Fachstelle bzw. BAZL.

### Geändert / Changed

- **Egress-Allow-List** um `api3.geo.admin.ch` ergänzt (Code-Layer +
  `deploy/network-policy.example.yaml`, Audit SEC-021).
- **User-Agent korrigiert:** hing seit v0.2.0 fest auf `swiss-environment-mcp/0.2.0`
  und meldete damit gegenüber jedem Upstream eine falsche Version. Jetzt 0.5.0.
- **`period`-Enum gegenüber dem ursprünglichen Entwurf erweitert.** Mit den vier
  ursprünglich geplanten Werten (`day`, `night_first`, `night_second`,
  `night_last`) wären die Hälfte der Sublayer und **18 der 38 Register**
  unerreichbar geblieben — Regionalflugplätze wie Grenchen, Birrfeld oder
  Schänis erscheinen ausschliesslich im Kleinluftfahrzeug-Layer. Ergänzt um
  `light_aircraft`, `helicopter`, `helicopter_max`, `military`. Kein zusätzliches
  Tool, dieselbe Signatur.

### Architektur-Entscheid

- **Live-API statt Dump** — Abweichung vom Dump-first-Standard des Portfolios.
  **Nicht** aus Grössengründen: der gesamte Kataster umfasst gemessene 747
  Objekte (~3 MB GeoJSON) und wäre problemlos spiegelbar. Ausschlaggebend ist,
  dass die Kataster je Flugplatz einzeln und unangekündigt nachgeführt werden
  (Gültigkeitsdaten 2009–2024): ein Spiegel würde die `validfrom`-Angabe in
  `source_freshness` entwerten. Zweitens läge die räumliche Auswertung
  (Punkt-zu-Linie über 26'000+ Stützpunkte) dann bei diesem Server statt beim
  Bundesamt — und erforderte mit shapely/GEOS die erste kompilierte
  Abhängigkeit in einem bewusst binärfreien `pyproject.toml`.

### Bekannte Einschränkungen / Known findings

Alle Befunde stammen aus der Live-Probe vom 2026-07-28, protokolliert in
[`docs/probe-fluglaerm.md`](docs/probe-fluglaerm.md).

1. **Strassenlärm ist nicht abfragbar.** `ch.bafu.laerm-strassenlaerm_tag` und
   `_nacht` quittieren dieselbe identify-Anfrage mit **HTTP 400** — reine
   Rasterdienste (`type: wmts`, `tooltip: false`) ohne Attributabfrage.
   Strassenlärm ist damit **out of scope**, und zwar dauerhaft, nicht als TODO.
   ⚠️ **Korrektur einer Vorannahme:** Der BAV-Bahnlärm
   (`ch.bav.laermbelastung-eisenbahn_effektive_immissionen_tag`) antwortet
   dagegen mit **HTTP 200** und echten Attributen (`de_es`,
   `de_pointofdetermination` = «Fassadenpunkt»). Bahnlärm ist *abfragbar* und
   bleibt trotzdem out of scope — als bewusste Abgrenzung, nicht als technische
   Unmöglichkeit.
2. **Die Layer-ID braucht zwingend den Sublayer-Suffix.** Die Basis-ID
   `ch.bazl.laermbelastungskataster-zivilflugplaetze` allein → HTTP 400. Acht
   gültige Sublayer, **alle acht identify-fähig** (die Nullen an einem
   bestimmten Punkt sind geografisch, nicht technisch).
3. **Attributnamen** sind exakt dokumentiert (`noisepollutionregister_*`,
   `exposuregroup_exposuretype`, `exposurecurve_level_db`, `label`) — siehe
   Probe-Protokoll, Abschnitt 4.
4. **Die Lärmkurven sind `MultiLineString`-Isolinien, keine Flächen.**
   `identify` macht deshalb *keinen* Punkt-in-Fläche-Test, sondern eine
   Näherungsabfrage im Toleranzradius. Der Radius entscheidet das Ergebnis: am
   selben Punkt liefern 100 m → 61–62 dB, aber 500 m → 58–75 dB (die 75-dB-Kurve
   liegt 1,5 km entfernt auf der Piste). Das Tool liefert daher eine Klammer mit
   dem höchsten Wert als oberer Schranke, nie einen interpolierten Punktwert.
5. **`exposurecurve_level_db` kommt als String**, nicht als Zahl — zentral in
   `geoadmin.clean_level_db()` nach `float` normalisiert. Ohne Normalisierung
   dieselbe Fehlerklasse wie bei den EFV-Reframe-Werten im Portfolio
   (String-Sortierung: `'9' > '62'`).
6. **Stichtagskataster, kein Echtzeitdienst.** `validfrom` streut von
   **01.03.2009** (CDB Genève) bis **16.04.2024** (LBK St. Gallen-Altenrhein).
   `source_freshness` behauptet deshalb nie «live», sondern trägt das
   `validfrom` des *gefundenen* Registers.
7. **Null Treffer ist zweideutig** — und wäre fast ein stiller Fehler geworden.
   Auf der Piste Kloten liefert ein Suchradius von 100 m dasselbe leere Resultat
   wie in Chur, obwohl dort 75 dB anliegen (der Punkt liegt *innerhalb* der
   innersten Kurve, es ist also keine Kurve in der Nähe). Das Tool fasst bei
   null Treffern einmal mit Fernradius nach und unterscheidet `no_cadastre` von
   `wide_area_only`.
8. **Anhang 5 LSV gilt nur für zivile Flugplätze.** Für Militärflugplätze ist
   Anhang 8 einschlägig — nicht verifiziert, daher verweigert
   `env_noise_limits_check` für `period='military'` die Prüfung und verweist auf
   die richtige Grundlage, statt eine plausibel aussehende falsche Tabelle
   anzuwenden.
9. **Der `layersConfig`-Endpoint trägt einen maschinenlesbaren
   Abfragbarkeits-Indikator:** abfragbare Layer haben `"tooltip": true`, reine
   Rasterdienste `"tooltip": false`. Das ist der saubere Vorab-Check statt
   Trial-and-Error gegen identify.

> **Merksatz:** *Fluglärm hat Linien, Strassenlärm hat nur Pixel* — Bahnlärm
> hätte Daten, ist aber bewusst nicht angebunden.

### Rechtsgrundlage

- **Lärmschutz-Verordnung (LSV), SR 814.41, Anhang 5** «Belastungsgrenzwerte
  für den Lärm ziviler Flugplätze» (zu Art. 40 Abs. 1), konsolidierte Fassung
  **in Kraft seit 01.04.2026**, verifiziert am **28.07.2026** gegen den
  amtlichen Text auf Fedlex. Die Werte wurden über den Fedlex-SPARQL-Endpoint
  ermittelt und aus dem amtlichen HTML ausgelesen — **nicht** aus dem
  Modellgedächtnis hardcodiert. SR-Nummer, Anhang, Ziffer, Fassung und
  Abrufdatum stehen als Kommentar im Code (`geoadmin.py`) und in jeder Antwort
  des Tools.
- Berücksichtigt ist auch die Fussnote zu Ziff. 222 («Die höheren Werte gelten
  für die erste Nachtstunde»), die **ausschliesslich ES II** betrifft — der
  Fall, den eine Grenzwertprüfung sonst still falsch rechnet.

### Tests

- Neue Suite `tests/test_noise.py` (50 gemockte Tests + 4 Live-Tests):
  Happy Path, Retry bei 503, Timeout, **HTTP 400 bei ungültiger Layer-ID ohne
  Retry**, **WGS84-Eingabe scheitert fail-fast**, vertauschte Achsen,
  dB-String-Normalisierung, Segment-Deduplizierung, die Auflösung von
  `no_cadastre` gegen `wide_area_only`, degraded-Envelope mit letztem
  erfolgreichem Abruf, sowie tabellenweise Verifikation der LSV-Werte inkl. der
  ES-II-Sonderregel für die erste Nachtstunde und der Verweigerung bei
  `military`.
- Live-Tests unter Marker `live`, aus der CI ausgeschlossen (`pytest -m "not live"`).

## [0.4.1] – 2026-07-26

Wartungs-Release: Behebt die Upstream-Endpoint-Drift bei den Naturgefahren-/
Waldbrand-Tools (nicht breaking — Tool-Namen/-Parameter unverändert).
`env_wildfire_danger` liefert wieder echte Live-Gefahrenstufen; die
`naturgefahren.ch`-Tools sind zu deterministischen Routing-Tools umgebaut, weil
kein stabiler öffentlicher Warn-Feed mehr existiert (MeteoSchweiz-Probe
dokumentiert).

### Geändert / Changed

- **`env_hazard_overview` / `env_hazard_regions` → netzwerkfreie Routing-Tools
  (MeteoSchweiz-Follow-up):** Probe 2026-07-26
  ([`docs/probe-naturgefahren-hazards.md`](docs/probe-naturgefahren-hazards.md))
  bestätigt: Für die aggregierten Naturgefahren-/Wetterwarnungen existiert **kein
  stabiler, dokumentierter öffentlicher JSON-Feed** (MeteoSchweiz-OGD/STAC,
  opendata.swiss, App-API — alle geprüft). Statt eines fragilen Scrapings
  verweisen beide Tools jetzt **deterministisch** auf die dedizierten Live-Tools
  (Hochwasser→`env_flood_warnings`, Lawine→`env_avalanche_bulletin`,
  Waldbrand→`env_wildfire_danger`, Schnee→`env_snow_current`) und offizielle
  Portale; aggregierte Wetterwarnungen sind sauber an MeteoSchweiz/`meteoswiss-mcp`
  abgegrenzt. Kein toter Endpoint mehr.
- **Egress-Allow-List verkleinert (SEC-021):** `www.naturgefahren.ch` entfernt
  (kein HTTP-Call mehr) — aus `ALLOWED_HOSTS` und
  `deploy/network-policy.example.yaml`. Tote Fetcher `fetch_hazard_overview` /
  `fetch_regional_hazards` entfernt.

### Behoben / Fixed

- **`env_wildfire_danger` repariert (Upstream-Drift):** `waldbrandgefahr.ch`
  hat seinen REST-Endpoint `/api/danger` stillgelegt (404) und ist neu eine
  Rails/React-App. Der Client nutzt jetzt einen **zweistufigen Zugriff**
  (Startseite → `data-react-props`/`warnMapJsonPath` → signierte
  ActiveStorage-Blob-JSON) mit Schema-Guard; das Tool liefert wieder echte
  Gefahrenstufen je Region (Kanton-Mapping aus den react-props, höchste Stufen
  zuerst, ohne Filter auf 40 Regionen begrenzt).

### Bekannte Einschränkungen / Known findings

- **`naturgefahren.ch`-API stillgelegt:** Die Endpoints
  `/api/v1/warnings/overview/ch` und `/api/v1/warnings/regions` liefern
  301→404, ohne Drop-in-Ersatz. Konsequenz (in diesem Release umgesetzt):
  `env_hazard_overview` / `env_hazard_regions` sind zu netzwerkfreien
  Routing-Tools umgebaut (kein toter Endpoint, kein Scraping mehr) — siehe
  «Geändert». Aggregierte Wetterwarnungen bleiben bewusst an MeteoSchweiz/
  `meteoswiss-mcp` abgegrenzt.
- Funde in [`docs/probe-naturgefahren-waldbrand.md`](docs/probe-naturgefahren-waldbrand.md)
  und [`docs/probe-naturgefahren-hazards.md`](docs/probe-naturgefahren-hazards.md)
  dokumentiert; READMEs unter «Known Limitations» ergänzt.

### Tests

- Wildfire-Mocks auf den Zwei-Schritt-Vertrag umgestellt (Happy Path,
  Schema-Guard-Degradation, Fehlerpfad→`ToolError`). Mocked Suite 79 → 80.
- `tool-snapshot.json` regeneriert: die Tool-Descriptions von
  `env_hazard_overview` / `env_hazard_regions` / `env_wildfire_danger` wurden um
  die neuen Zugriffs-/Abkündigungs-Hinweise ergänzt (Description-Änderung,
  Namen/Parameter unverändert → nicht breaking für Clients).

## [0.4.0] – 2026-07-25

Erster getaggter Release seit v0.2.3 — bündelt die Hydro-Phase-2 (neues Tool
`env_bathing_water`, extraktionsfähiges `lindas/`-Modul; zuvor unter `[0.3.0]`
dokumentiert, aber nie getaggt) **und** die vollständige Audit-Remediation der
17 Findings des Re-Audits 2026-07-25.

**Auditbestätigt** (Re-Audit-Run `2026-07-25T145413-Z`, mcp-audit v1.0.0,
catalog `091f446b`): 44 anwendbare Checks → **38 pass / 6 partial / 0 fail**,
`production_ready: true`, keine blockierenden Fails. Die 6 verbleibenden partials
sind dokumentierte Risiko-Akzeptanzen bzw. ein begründeter Trade-off
(SEC-009/014/015, SCALE-002/003/004) mit Re-Evaluations-Triggern.

> **⚠️ Breaking (OBS-001):** Terminale Ausführungsfehler werden neu als
> `ToolError` geworfen → FastMCP setzt `isError:true`, statt den Fehlertext als
> erfolgreiches Resultat zurückzugeben. Recovery-Hinweise bleiben im
> Fehler-Content. Clients, die bisher Fehlertexte als normalen Output parsten,
> müssen `isError` auswerten. Details im Batch-1-Eintrag unten.

Die folgenden Batch-Einträge dokumentieren die Remediation im Detail; die
Hydro-Phase-2-Änderungen stehen unverändert im `[0.3.0]`-Block darunter.

### Audit-Remediation (Re-Audit 2026-07-25) — Batch 5: Deployment/Scale + Risiko-Akzeptanz

- **SCALE-004 — Image-Size-Gate:** neuer Workflow `.github/workflows/image-size.yml`
  baut das Runtime-Image und prüft die Grösse gegen ein Regressions-Ceiling
  (350 MB; das ≤200-MB-Ideal wird durch python-slim + otel-Extra knapp
  überschritten — das Gate fängt echte Regressionen). Läuft nur bei
  Image-relevanten Änderungen.
- **SCALE-006 — Resource-Limits im produktiven Pfad:** `render.yaml` dokumentiert
  die Plan-`starter`-Deckel (512 MB / 0.5 vCPU, Auto-Restart bei OOM);
  `docs/scaling.md` ergänzt eine Limits-Tabelle je Deployment-Pfad (Compose/
  Render/K8s) und ein reproduzierbares OOM-/Restart-Verfahren.
- **Risiko-Akzeptanz formalisiert (SEC-014, SEC-015, + Re-Evaluations-Trigger):**
  `docs/security.md` trennt Tool-Allow-Listing (SEC-014) und
  Tool-Poisoning-Detection (SEC-015), benennt die vier Detektions-Muster­klassen
  des Katalogs und die verbindlichen Trigger, ab wann die Kontrollen
  nachzurüsten sind (Auth-Einführung, write-Tools, Gateway-/Multi-Tenant-Betrieb).
  SCALE-002/003 (Sticky-LB/Shared-State) und SEC-009 (Session-Binding) bleiben
  dokumentierte Single-Instance-/No-Auth-Akzeptanzen in `docs/scaling.md` bzw.
  `docs/security.md`.

### Audit-Remediation (Re-Audit 2026-07-25) — Batch 4: Architektur-Politur

- **ARCH-007 — Parallelisierung unabhängiger interner Calls:**
  `env_bathing_water` holt Lizenz- und Standort-Query, `env_snow_current` die
  beiden SLF-Endpoints (Tageswerte + Stationen) neu via `asyncio.gather` statt
  sequenziell.
- **ARCH-012 — Protokollversion im Startup-Log:** die Lifespan loggt beim Start
  `server_start` mit `transport` und der vom SDK unterstützten
  `mcp_protocol_version` — ein SDK-Bump, der die Spec-Version verschiebt, wird
  damit im Audit-Trail sichtbar.
- **ARCH-006 — Tool-Budget-Begründung im README:** beide READMEs erklären, warum
  18 Tools über 6 Domänen (statt ≤12) use-case-getrieben sind und welche
  Konsolidierung (Stations-/Current-Paare) bewusst verworfen wurde.

### Audit-Remediation (Re-Audit 2026-07-25) — Batch 3: Security-Härtung

- **SEC-005 — eine DNS-Resolution pro Request:** `assert_host_allowed()` prüft
  nur noch Schema + Allow-List; die DNS-Auflösung samt IP-Blocklist erfolgt
  **einmalig** im `_PinnedTransport` unmittelbar vor dem Connect (zuvor lösten
  Guard *und* Transport je einmal auf → zwei `getaddrinfo`-Calls). Zwei neue
  Tests verifizieren: der Guard löst gar nicht mehr auf, der Transport genau
  einmal (Connect-Ziel = gepinnte IP).
- **SEC-021 — deploybares Network-Layer-Egress-Artefakt:**
  `deploy/network-policy.example.yaml` (vanilla `NetworkPolicy` + Cilium-FQDN-
  Egress auf exakt die Allow-List-Hosts). `docs/security.md` und CONTRIBUTING
  dokumentieren das verbindliche Verfahren für Allow-List-Erweiterungen
  (PR-Begründung, Manifest-Sync, CHANGELOG-Pflicht, Zweit-Review).
- **SEC-022 — Tool-Definitions-Governance dokumentiert:** CONTRIBUTING hält
  Snapshot-Regenerierung + expliziten Client-Re-Approval-Hinweis bei
  breaking Tool-Änderungen fest; das stabile `env_`-Präfix ist als bewusste
  Namespace-Entscheidung in beiden READMEs erklärt.

### Audit-Remediation (Re-Audit 2026-07-25) — Batch 2: Test-Coverage (OPS-001)

- **Gemockte Unit-Tests für die drei bisher ungetesteten Tools** (Happy Path +
  Fehlerpfad → `ToolError`): `env_hazard_overview`, `env_hazard_regions`,
  `env_wildfire_danger`. Damit hat jedes datenliefernde Tool CI-abgedeckte
  Erfolgs- und Fehlerpfade (6 neue Tests, Suite 71 → 77).
- **Eigenständige Live-Tests** für `env_snow_stations` und
  `env_avalanche_bulletin` (bisher nur indirekt über `test_slf_snow`).
- **`tests/test_20_scenarios.py`** ist nicht mehr ein pytest-unsichtbares
  Skript: neu als `live`-markierter `test_all_scenarios` sammelbar (aus der
  CI via `-m "not live"` ausgeschlossen), Docstring auf 18 Tools korrigiert,
  die Fehler-ID-Erwartung an die neue `isError`-Semantik (OBS-001) angepasst.

### Audit-Remediation (Re-Audit 2026-07-25) — Batch 1: Observability

- **OBS-006 — Tracing im Deployment aktivierbar:** Das Docker-Image installiert
  neu das `[otel]`-Extra (`Dockerfile`); `render.yaml` setzt `OTEL_SERVICE_NAME`
  und exponiert `OTEL_EXPORTER_OTLP_ENDPOINT` (sync:false), `docker-compose.yml`
  dokumentiert beide. Tracing bleibt opt-in (No-op ohne Endpoint), ist jetzt aber
  ohne Rebuild einschaltbar.
- **OBS-003 — Logging über den Fehlerpfad hinaus:** `trace_tool` bindet je
  Tool-Call eine Correlation-ID (`request_id`) + `tool` in den Log-Kontext und
  emittiert `tool_invoked`/`tool_succeeded` (info) bzw. `tool_failed` (error).
  Ausgehende Upstream-Requests werden auf `debug` geloggt; `LOG_LEVEL` (Env)
  schaltet die Stufe um. Damit sind vier Severity-Stufen aktiv genutzt.

> **Breaking (OBS-001, JSON-/Protokoll-Konsument:innen):** Terminale
> Ausführungsfehler (Upstream nicht erreichbar, Egress blockiert) werden neu als
> `ToolError` geworfen — FastMCP setzt daraufhin `isError:true` im
> CallToolResult, statt den Fehlertext als *erfolgreiches* Resultat
> (`isError:false`) zurückzugeben. Die maskierte Meldung und die
> Direktzugang-Hinweise bleiben im Fehler-Content erhalten; Clients, die bisher
> den Fehlertext als normalen Output geparst haben, müssen neu `isError`
> auswerten. Graceful-Degradation-Pfade mit echten Ersatzdaten (z.B.
> Beispiel-Stationslisten in `env_hydro_stations`) und leere gültige Resultate
> (`match_type: none`, „keine aktive Warnung") bleiben unveränderte
> Erfolgs-Resultate.

## [0.3.0] – 2026-07-25

### Neu
- **`env_bathing_water` (18. Tool, Cluster Wasser):** Badegewässerqualität
  (E.coli/Enterokokken) aus dem LINDAS-Data-Cube `foen/ubd01041prod` — der
  einzige Hydro-Cube mit echter Mehrjahres-Zeitreihe (Saisondaten seit 2020).
  Standorte werden zu Labels aufgelöst (nie rohe Code-URIs), die Kantonsnummer
  aus der `containedInPlace`-URI wird als Join-Key mitgeliefert, jede Antwort
  trägt ein Lizenzfeld (ehrlicher Hinweis, wenn am Cube keine Lizenz deklariert
  ist — «im offenen Triplestore» ist nicht «frei verwendbar»).

### Architektur
- **Extraktionsfähiges `lindas/`-Modul (Drei-Schichten-Trennung):**
  `lindas/client.py` kennt nur SPARQL+HTTP (GET/POST je Query-Länge,
  45-s-Client-Timeout vor dem 60–90-s-Server-Abbruch, HTTP 400 als
  `QueryError` mit der MALFORMED-Meldung, Retry 2 s/4 s/8 s);
  `lindas/cube.py` kennt das cube.link-Vokabular (observationSet-Zwischenschritt,
  Versions-Deduplizierung über `schema:expires`, Code→Label-Auflösung,
  `pick_lang`, Lizenz-Suche auf Cube- und Graph-Ebene). Die Tools kennen nur
  `cube.py`. Das Modul wird nach `lindas-mcp` gehoben, sobald ein zweiter
  Server LINDAS nutzt.
- Der bestehende Hydro-LINDAS-Pfad (`run_sparql` und Fetcher) läuft neu über
  `lindas/client.py` (flache Result-Dicts statt roher Bindings).

### Known findings (aus der Live-Probe, docs/probe-lindas-hydro.md N1–N7)
- Direktzugriff `?cube cube:observation` liefert **0 Zeilen** ohne Fehler —
  der observationSet-Zwischenschritt ist zwingend.
- Abgelöste Cube-Versionen tragen `schema:expires`; das URI-Suffix kommt mal
  mit, mal ohne Trailing-Slash (`ubd0104/4/` vs. `ubd01041prod/13`).
- Lizenz liegt am Datensatz im Named Graph, nicht am Cube.

> **Breaking (nur interne API):** `api_client.run_sparql` liefert neu flache
> Dicts (Variable → Wert) statt roher SPARQL-Bindings; `api_client._binding_val`
> entfällt. Tool-Antworten sind nicht betroffen.

### Refactor
- **`sparql_client.py` als Portfolio-Baustein vereinheitlicht (Vendoring):** die
  Datei ist jetzt **byte-identisch** zur Kopie in `fedlex-mcp` (dortiger
  `_execute_sparql` bindet neu dünn daran). Ergänzt um einen optionalen
  `on_retry`-Callback (generisches Retry-Logging), rückwärtskompatibel. Der echte
  Single-Source-Schritt (`swiss-mcp-commons`-Paket) bleibt offen — siehe
  `docs/scaling.md`.
- **Wiederverwendbarer SPARQL-/JSON-Client extrahiert** (`sparql_client.py`):
  der aus `fedlex-mcp` stammende Retry-/Escape-/Binding-Aufbau ist jetzt ein
  abhängigkeitsarmes Modul (nur `httpx`/`asyncio`, Egress-Guard als Callback,
  HTTP-Client vom Aufrufer). `api_client.run_sparql` und `_get_json_retry` sind
  dünne Bindungen darauf; öffentliche Namen unverändert. So ist der Baustein 1:1
  in ein gemeinsames Portfolio-Paket hebbar (Cross-Repo-Paketierung als
  Folgeschritt, siehe `docs/scaling.md`).

### Behoben / Fixed
- **BUG-01 (historische Hydrodaten):** Die stillgelegten REST-Endpoints unter
  `hydrodaten.admin.ch/lhg/az/*` (Stunden-CSV, `warnings.json`, Stations-JSON,
  alle 404) werden nicht mehr aufgerufen. `env_flood_warnings` liest neu LINDAS
  `dangerLevel` (`fetch_hydro_warnings_lindas`); `env_hydro_history` liefert den
  aktuellsten LINDAS-Wert + den Bezugsweg für echte historische Reihen
  (BAFU-Abfragezentrale). Tote Fetcher `fetch_hydro_warnings` /
  `fetch_hydro_station_history` entfernt. (Tool-Definitionen geändert →
  `tool-snapshot.json` neu erzeugt.)

### Dokumentation
- **Jagdstatistik-Lizenz recherchiert (2026-07-19):** Daten BAFU-eigen (aus
  kantonalen Stellen; Technik Wildtier Schweiz), **nicht** als lizenzierter
  opendata.swiss-Datensatz publiziert, **keine explizite Lizenz** auf der Quelle.
  Attribution in jeder Antwort («Quellenangabe erforderlich»); formelle
  BAFU-Bestätigung bleibt offen. READMEs + `docs/probe-jagdstatistik.md` präzisiert.

### Neu / Added
- **Jagdstatistik-Tools** (Phase 3, Inkrement 3), Cluster «Jagd»:
  - `env_hunting_species` — 36 Tierarten mit sp-Codes (statisch eingebettet, lokal).
  - `env_hunting_stats` — Abschuss-/Fallwild-/Bestand-/Aussetzungszahlen je
    Tierart, Kanton und Jahr (2015–2024) aus dem `jagdstatistik.ch`-Backend.
  - **Architektur-Entscheid** (Abweichung von Dump-first): Live-Wrapper mit
    **eingebetteten statischen Lookups** (Tierart/Kanton/Datentyp) + **Schema-Guard**
    (Graceful Degradation), da der Container ephemer ist und kein persistenter Dump
    sinnvoll ist. Host `www.jagdstatistik.ch` in der Egress-Allow-List, AJAX-Header
    für den content-negotiierten JSON-Zugang. Tool-Anzahl 15 → 17.

### Known findings
- Jagdstatistik-Backend (`/de/statistics`) undokumentiert, Highcharts-zentriert:
  Datentyp-Param ist `th` (nicht `dt`), erst mit `th` greift der Kanton-Filter `ar`;
  Werte kommen als `[[v], …]` (verschachtelt). Lizenz auf der Quelle nicht
  ausgewiesen (BAFU-Terms anzunehmen, vor Release bestätigen).

- **SLF-Schnee- & Lawinen-Tools** (Phase 3, Inkrement 2), Cluster «Schnee/SLF»:
  - `env_snow_stations` — automatische IMIS-Schneemessstationen (Filter Kanton).
  - `env_snow_current` — aktuelle Schneehöhe (HS) & Neuschnee 24 h (HN_1D) in cm,
    je Station, mit Kanton-/Stations-Filter.
  - `env_avalanche_bulletin` — Lawinenwarnstufen (EAWS 1–5) je Warnregion aus dem
    CAAML-GeoJSON; ausserhalb der Saison sprechender «kein aktives Bulletin»-Pfad.
  - Datenquelle SLF-Datenservice (`measurement-api.slf.ch`, `aws.slf.ch`),
    **CC BY 4.0**, no-auth. Hosts in der Egress-Allow-List. Retry via
    `_get_json_retry`. Tool-Anzahl 12 → 15, `tool-snapshot.json` aktualisiert.
  - **Abgrenzung meteoswiss:** der SLF-IMIS-Niederschlagssensor (`RR_10MIN_SUM`)
    wird bewusst **nicht** als Tool angebunden (Zuständigkeitsmatrix).
- **LINDAS-SPARQL-Anbindung für Hydrodaten** (Phase 3). `env_hydro_current` und
  `env_hydro_stations` fragen primär den BAFU-LINDAS-Endpoint
  (`lindas.admin.ch/query`, Graph `foen/hydro`, `cube.link`-Data-Cube) ab und
  liefern typisierte Live-Werte (Pegel, Abfluss, Wassertemperatur,
  Gefahrenstufe) statt des fragilen `hydrodaten.admin.ch`-JSON-Scrapings. Der
  REST-Pfad bleibt als Fallback erhalten.
- SPARQL-Client (`run_sparql`, `sparql_escape`, `fetch_hydro_*_lindas`) mit
  Egress-Guard, Retry bei transienten Fehlern (429/502/503/504) und
  exponentiellem Backoff — Client-Aufbau bewusst aus `fedlex-mcp`
  wiederverwendet. `lindas.admin.ch` in die Egress-Allow-List aufgenommen.

### Known findings
- LINDAS `foen/hydro` enthält **nur aktuelle Werte** (eine Observation pro
  Station), keine historische Zeitreihe. `schema:identifier` ist `xsd:integer`
  → Stationsvergleich datentyp-robust über `STR(?id)`. Historische Längsschnitte
  weiterhin via `env_hydro_history` / opendata.swiss.

### Geändert / Changed
- Dokumentation an die einheitliche Portfolio-Struktur angeglichen: Root-Level
  `SECURITY.md` (Englisch) mit verlinkter `SECURITY.de.md` (Deutsch) ergänzt;
  README verweist nun auf die Security-Policy. LICENSE-Copyright auf
  «Hayal Oezkan» korrigiert.

## [0.2.0] – 2026-06-02

Erstveröffentlichung nach vollständiger Audit-Remediation (mcp-audit-skill):
31 Findings → 0, `production_ready: true`.

### Neu
- **CORS-Middleware** für den HTTP-Transport (SDK-004): `Mcp-Session-Id` via
  `expose_headers` für Browser-/SSE-Clients exponiert und in `allow_headers`
  zugelassen. Origins via `MCP_CORS_ALLOW_ORIGINS` konfigurierbar (Default `*`
  für Dev, in Produktion explizite Liste; Wildcard wird geloggt).
- **OpenTelemetry-Tracing** (OBS-006, opt-in via `pip install '.[otel]'` +
  `OTEL_EXPORTER_OTLP_ENDPOINT`): pro Tool-Call ein Span `mcp.tool.<name>` mit
  `mcp.tool.name`/`mcp.tool.result.is_error`, httpx-Auto-Instrumentation, keine
  sensitiven Daten in Span-Attributen.
- **Strukturiertes Logging** (OBS-003) via `structlog` nach **stderr** (JSON).
- **Typisierter JSON-Response-Envelope** (SDK-002) für alle Such-/Listen-Tools
  (`env_nabel_stations`, `env_hydro_stations`, `env_bafu_datasets`,
  `env_flood_warnings`): `source`, `provenance`, `count`, `match_type`,
  `results`, `note`. Markdown bleibt Default-Format.
- Leere Such-/Listen-Resultate liefern `match_type: none` + actionable Hinweis
  statt blanker Tabelle (ARCH-003).
- `<use_case>`/`<important_notes>`-Tags in allen 12 Tool-Beschreibungen (ARCH-002).
- `/health`-Endpoint für Cloud-Load-Balancer (SCALE-004/SEC-016).
- Gemockte Unit-Tests (respx) getrennt von Live-Tests (`live`-Marker); CI läuft
  `pytest -m "not live"`, nightly Live-Workflow (OPS-001).
- Tool-Definition-Snapshot + CI-Gate gegen «Rug Pull» (SEC-022).
- Docs: `docs/security.md` (Trifecta-Bewertung SEC-019, Secret-Mgmt SEC-013,
  Session-Modell SEC-009, Egress SEC-021), `docs/scaling.md` (SCALE-002/003/006),
  `docs/roadmap.md` (Phasenarchitektur OPS-003).
- `.env.example`, `.github/dependabot.yml` (ARCH-012),
  `.github/workflows/security.yml` (gitleaks, ARCH-005), `docker-compose.yml`
  mit expliziten Resource-Limits (SCALE-006).

### Geändert
- **Tool-Definitionen geändert** (SEC-022, Tool-Snapshot aktualisiert).
- Korrekter Cloud-Transport `streamable-http` (vorher ungültiges
  `streamable_http`) + behobenes Host-Binding (`MCP_HOST`, SEC-016) — macht das
  Cloud-Deployment erstmals lauffähig.
- Geteilter `httpx.AsyncClient` via FastMCP-Lifespan statt pro Tool-Call (SDK-001).
- Pydantic-Settings + transport-agnostische Server-Logik (ARCH-004).
- `ctx: Context` an allen Tools für Logging/Fehler über den MCP-Context (SDK-003).
- MCP-SDK auf Major-Version gepinnt (`mcp[cli]>=1.27,<2`, ARCH-012).
- Multi-Stage-Dockerfile, non-root User, HEALTHCHECK (SEC-007/SCALE-004).

### Sicherheit
- **SSRF-Härtung** (SEC-004): Egress-Allow-List (frozenset) + `assert_host_allowed`,
  HTTPS-Zwang, IP-Blocklist, `follow_redirects=False`.
- **DNS-Pinning** (SEC-005): Host einmalig auflösen, IP gegen Blocklist prüfen,
  Connect auf gepinnte IP (SNI/Cert gegen Hostnamen) — kein TOCTOU-Fenster.
- **Input-Whitelisting** (SEC-018): Regex-Pattern + `strict` auf Identifier-Inputs.
- **Fehler-Maskierung** (OBS-002): keine internen Details ans LLM; Detail nur im
  Server-Log.

> **Breaking (JSON-Konsument:innen):** Der JSON-Output von `env_nabel_stations` /
> `env_hydro_stations` nutzt neu die Envelope-Keys (`results`/`count`/… statt
> `nabel_stationen`/`total`). Markdown-Konsument:innen sind nicht betroffen.

## [0.1.0] – 2026-03-12

### Neu
- **12 Tools** in 4 thematischen Clustern
- **Luft (3):** `env_nabel_stations`, `env_nabel_current`, `env_air_limits_check`
- **Wasser (4):** `env_hydro_stations`, `env_hydro_current`, `env_hydro_history`, `env_flood_warnings`
- **Naturgefahren (3):** `env_hazard_overview`, `env_hazard_regions`, `env_wildfire_danger`
- **Umweltdaten (2):** `env_bafu_datasets`, `env_bafu_dataset_detail`
- **3 MCP-Resources:** Grenzwerte Luft, NABEL-Stationen, Hochwasser-Gefahrenstufen
- Schweizer LRV-Grenzwerte und WHO 2021-Richtwerte eingebaut
- Fallback-Antworten mit Direktlinks bei API-Ausfällen
- Duale Transport-Unterstützung: stdio (lokal) und Streamable HTTP (Cloud)
- GitHub Actions CI für Python 3.11–3.13
- Bilinguales README (DE/EN)

### Quellen
- hydrodaten.admin.ch (BAFU Hydrologie)
- naturgefahren.ch (SLF/BAFU)
- waldbrandgefahr.ch (BAFU)
- opendata.swiss CKAN-API (BAFU-Datenkatalog)
