# Use Cases & Examples — swiss-environment-mcp

Real-world queries by audience. Indicate per example ob ein API-Key erforderlich ist (für diesen Server: **keine** API-Keys erforderlich).

## 🏫 Bildung & Schule
Lehrpersonen, Schulbehörden, Fachreferent:innen

**Klima und Wasser im Unterricht**
«Wir behandeln im Geografieunterricht den Klimawandel. Kannst du mir die historischen Abflussmengen der Limmat in Zürich für die letzten 14 Tage heraussuchen, damit wir die aktuellen Schwankungen analysieren können?»
→ `env_hydro_history(station_id="2099", parameter="Abfluss", days=14)`
Warum nützlich: Erlaubt es Lehrpersonen, abstrakte hydrologische Konzepte anhand lokaler, tagesaktueller und historischer Realdaten greifbar zu machen.

**Luftqualität als Schulprojekt**
«Meine Klasse führt ein Projekt zur Luftverschmutzung durch. Zeige mir alle NABEL-Messstationen in der Schweiz und gib mir die aktuellen Ozon- und Feinstaubwerte für die Station Dübendorf, inklusive Vergleich mit den WHO-Richtwerten.»
→ `env_nabel_stations(response_format="markdown")`
→ `env_nabel_current(station="DUB")`
→ `env_air_limits_check(pollutant="PM10", value=18.5, averaging_period="annual")`
Warum nützlich: Fördert praxisnahen Naturwissenschaftsunterricht, indem Schüler:innen direkte Messdaten mit offiziellen Grenzwerten abgleichen können.

## 👨👩👧 Eltern & Schulgemeinde
Elternräte, interessierte Erziehungsberechtigte

**Gesundheitsvorsorge auf dem Schulweg**
«Mein asthmakrankes Kind hat heute Sporttag draussen. Wie ist die aktuelle Luftqualität (Feinstaub und Ozon) an der Station Zürich-Kaserne und gibt es Überschreitungen der Schweizer Grenzwerte?»
→ `env_nabel_current(station="ZUE")`
Warum nützlich: Bietet Eltern sofortige, verlässliche Umweltdaten, um gesundheitliche Risiken für vulnerable Kinder im Freien besser einzuschätzen.

**Sicherheit bei Klassenfahrten**
«Die Schulklasse meines Sohnes geht nächste Woche in den Kanton Graubünden ins Lager. Gibt es dort aktuell eine hohe Waldbrandgefahr oder Naturgefahrenwarnungen, die wir beachten müssen?»
→ `env_wildfire_danger(canton="GR", language="de")`
→ `env_hazard_regions(region="Graubünden", hazard_type="", language="de")`
Warum nützlich: Hilft Eltern und Betreuungspersonen, sicherheitsrelevante Umwelteinflüsse vor Schulausflügen schnell und gebündelt zu prüfen.

## 🗳️ Bevölkerung & öffentliches Interesse
Allgemeine Öffentlichkeit, politisch und gesellschaftlich Interessierte

**Transparenz bei Hochwasserereignissen**
«Es hat in den letzten Tagen stark geregnet. Gibt es momentan aktive Hochwasserwarnungen für den Kanton Bern und wie hoch ist der aktuelle Pegelstand der Aare in Bern?»
→ `env_flood_warnings(min_level=2, canton="BE")`
→ `env_hydro_current(station_id="2008")`
Warum nützlich: Schafft rasche Klarheit für Anwohner:innen in flussnahen Gebieten bei drohenden Unwettern anhand offizieller Behördendaten.

**Diskussionsgrundlage für Lokalpolitik**
«Für eine anstehende Gemeindeversammlung zur Verkehrsberuhigung brauche ich offizielle BAFU-Datensätze zum Thema Luftqualität. Welche offenen Daten gibt es dazu auf opendata.swiss?»
→ `env_bafu_datasets(query="Luftqualität", rows=5, offset=0)`
Warum nützlich: Stärkt die demokratische Teilhabe, da Bürger:innen unkompliziert evidenzbasierte Daten des Bundes für politische Argumentationen finden.

## 🤖 KI-Interessierte & Entwickler:innen
MCP-Enthusiast:innen, Forscher:innen, Prompt Engineers, öffentliche Verwaltung

**Automatisierte Naturgefahren-Warnungen**
«Ich möchte ein Dashboard bauen. Ruf das aktuelle nationale Naturgefahren-Bulletin auf Deutsch ab, damit ich die Struktur der Warnungen für Lawinen und Hochwasser analysieren kann.»
→ `env_hazard_overview(language="de")`
Warum nützlich: Zeigt Entwickler:innen, wie sie offizielle Warnmeldungen des Bundes strukturiert in eigene Automatisierungs-Pipelines oder Dashboards integrieren können.

**Portfolio-Synergie: Verkehrsdaten und Luftqualität kombinieren**
«Korreliert das aktuelle Verkehrsaufkommen auf den Zürcher Strassen mit den heutigen Schadstoffwerten? Lade die Verkehrszählungsdaten der Stadt Zürich herunter und vergleiche sie mit den aktuellen Werten der NABEL-Station Zürich-Kaserne.»
→ `zh_verkehr_current()` (aus [zurich-opendata-mcp](https://github.com/malkreide/zurich-opendata-mcp))
→ `env_nabel_current(station="ZUE")`
Warum nützlich: Demonstriert die Leistungsfähigkeit des MCP-Ökosystems, indem lokale städtische Mobilitätsdaten nahtlos mit nationalen Umwelt-Referenzstationen verknüpft werden.

---

## 🔧 Technische Referenz: Tool-Auswahl nach Anwendungsfall

| Ich möchte… | Tool(s) | Auth nötig? |
|-------------|---------|-------------|
| **eine NABEL-Station in meiner Nähe finden** | `env_nabel_stations` | Nein |
| **die aktuelle Luftqualität (Ozon, Feinstaub) prüfen** | `env_nabel_current` | Nein |
| **messen, ob ein Schadstoffwert legal ist** | `env_air_limits_check` | Nein |
| **wissen, wo es aktuell Hochwassergefahr gibt** | `env_flood_warnings` | Nein |
| **den Pegelstand oder Abfluss eines Flusses wissen** | `env_hydro_stations`, `env_hydro_current` | Nein |
| **historische Wasserstände analysieren** | `env_hydro_history` | Nein |
| **Wetter- und Gefahrenwarnungen für eine Region sehen** | `env_hazard_regions`, `env_hazard_overview` | Nein |
| **die Waldbrandgefahr in einem Kanton abfragen** | `env_wildfire_danger` | Nein |
| **offizielle Umweltdatensätze des Bundes suchen** | `env_bafu_datasets`, `env_bafu_dataset_detail` | Nein |
