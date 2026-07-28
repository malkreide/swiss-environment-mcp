# Live-Probe — Lärmbelastungskataster Fluglärm (BAZL via geo.admin.ch)

**Datum der Probe:** 2026-07-28
**Prober:** Fluglärm-Erweiterung (Skill `mcp-data-source-probe`, Schritte 1–2)
**Einstieg:** `https://api3.geo.admin.ch/rest/services/ech/MapServer/identify`
**Ziel:** Punktbezogene Fluglärmbelastung an einer LV95-Koordinate.
**Auth-Prüfung:** ✅ **kein Auth, keine Registrierung.** Fair Use ca. 20 Req./Min.
**Koordinatensystem:** LV95 / EPSG:2056 (`sr=2056`).

---

## 1. Layer-Katalog (Vorab-Check statt Trial-and-Error)

`GET /rest/services/ech/MapServer/layersConfig?lang=de` liefert alle Layer mit
ihren Eigenschaften. **Der entscheidende Indikator ist `tooltip`:**

| Layer-Gruppe | `type` | `tooltip` | identify |
|---|---|---|---|
| `ch.bazl.laermbelastungskataster-zivilflugplaetze_*` (8 Sublayer) | `wms` | `true` | ✅ |
| `ch.bafu.laerm-strassenlaerm_tag` / `_nacht` | `wmts` | `false` | ❌ HTTP 400 |
| `ch.bav.laermbelastung-eisenbahn_*` | `wmts` | – | ✅ (s. u.) |

Damit lässt sich die Abfragbarkeit **vor** dem ersten identify-Call bestimmen.

---

## 2. Befund-Tabelle — alle acht BAZL-Sublayer

Punkt Kloten `2685000 / 1258000`, Suchradius 500 m. Die Spalte «CH gesamt»
stammt aus einer `esriGeometryEnvelope`-Abfrage über die Landesausdehnung —
sie trennt *«Layer kann nicht»* von *«hier liegt nichts»*.

| Sublayer | HTTP | Treffer @Kloten | CH gesamt | `exposuretype` | Bemerkung |
|---|---|---|---|---|---|
| `_klein-grossflugzeuge` | 200 | 18 (58–75 dB) | 180 Obj. / 8 Register | `OverallTrafficDay_Lr` | Hauptfall |
| `_erste-nachtstunde` | 200 | 18 (53–70 dB) | 124 / 5 | `FirstNightHour_Lr` | |
| `_zweite-nachtstunde` | 200 | 17 (43–59 dB) | 80 / 3 | `SecondNightHour_Lr` | |
| `_letzte-nachtstunde` | 200 | 0 | 7 / 1 | `LastNightHour_Lr` | nur CDB Genève |
| `_helikopter` | 200 | 0 | 19 / 1 | `Helicopter_Lr` | nur LBK Holziken |
| `_helikopter-maximalpegel` | 200 | 0 | 133 / 12 | `Helicopter_Lmax` | Erstfeld, Interlaken, Leysin … |
| `_kleinluftfahrzeuge` | 200 | 4 (50–53 dB) | 201 / 38 | `LightAircraft_Lr` | flächendeckendster Layer |
| `_militaer-gesamt` | 200 | 0 | 3 / 1 | `OverallTrafficMilitary_Lr` | nur CDR Locarno-Magadino |
| **Basis-ID ohne Suffix** | **400** | – | – | – | Sublayer-Suffix ist zwingend |

**Alle acht Sublayer sind identify-fähig.** Die Nullen bei Kloten sind
geografisch, nicht technisch. Gesamtbestand: **747 Objekte**.

### Gegenprobe Raster-Layer

| Layer | HTTP | Befund |
|---|---|---|
| `ch.bafu.laerm-strassenlaerm_tag` | **400** | reiner Rasterdienst, keine Attributabfrage |
| `ch.bafu.laerm-strassenlaerm_nacht` | **400** | dito |
| `ch.bav.laermbelastung-eisenbahn_effektive_immissionen_tag` | **200** | 5 Treffer mit echten Attributen (`de_es`, `de_pointofdetermination` = «Fassadenpunkt») |

⚠️ **Korrektur einer Vorannahme:** Der BAV-Bahnlärm ist **abfragbar** — anders
als ursprünglich notiert. Er bleibt out of scope, aber als *bewusste
Abgrenzung*, nicht als technische Unmöglichkeit.

---

## 3. Das Kernfundstück: die Kurven sind Linien, keine Flächen

Mit `returnGeometry=true`:

```
geomType = MultiLineString
featureId = 48238
bbox = [2677682.9, 1252181.4, 2686847.0, 1264079.5]
```

`identify` macht damit **keinen Punkt-in-Fläche-Test**, sondern eine
Näherungsabfrage im Pixel-Toleranzradius. Der Radius entscheidet das Ergebnis:

| Radius ab `2685000/1258000` | Treffer | dB-Spanne |
|---|---|---|
| 100 m | 2 | 61–62 |
| 250 m | 6 | 60–65 |
| 500 m | 18 | **58–75** |

Bei 500 m ist der höchste Wert 75 dB — die Pistenkurve **1,5 km entfernt**.
«Die höchste gefundene Kurve zurückgeben» ist bei grossem Radius grob falsch.

**Konsequenz für die Implementation:** Das Tool liefert eine **Klammer**
(min/max der nahen Kurven) mit dem höchsten Wert als ausgewiesener *oberer
Schranke*, nie einen interpolierten Punktwert. Der Suchradius steht in jeder
Antwort.

### Null Treffer ist zweideutig

Piste Kloten `2683600 / 1256800`:

| Radius | Treffer | dB-Werte |
|---|---|---|
| 100 m | **0** | – |
| 250 m | 5 | 71–75 |
| 500 m | 10 | 67–75 |

Am lautesten Punkt der Schweiz liefert r=100 m dasselbe leere Resultat wie
Chur (`2759500 / 1191000`, 0 Treffer bei 100 m **und** 1000 m). Auflösung: bei
null Treffern **einmal mit Fernradius nachfassen** — Treffer dort ⇒
`wide_area_only` (Punkt liegt innerhalb der innersten Kurve oder im flachen
Gradienten), auch dort nichts ⇒ `no_cadastre`.

---

## 4. Attributschema (exakt, nicht geraten)

| Feld | Beispiel | Typ |
|---|---|---|
| `noisepollutionregister_registername` | `LBK Zürich` | String |
| `noisepollutionregister_editor` | `Bundesamt für Zivilluftfahrt BAZL` | String |
| `noisepollutionregister_validity_validfrom` | `03.07.2015` | String `TT.MM.JJJJ` |
| `noisepollutionregister_documentlink` | URL auf amtliches PDF | String |
| `exposuregroup_exposuretype` | `OverallTrafficDay_Lr` | String |
| `exposurecurve_level_db` | `62` | **String, nicht Zahl** |
| `label` | `62` | String (Anzeigetext) |

`exposurecurve_level_db` wird zentral in `geoadmin.clean_level_db()` nach
`float` normalisiert — dieselbe Fehlerklasse wie bei den EFV-Reframe-Werten im
Portfolio (String-Sortierung: `'9' > '62'`).

---

## 5. Stichtagskataster, kein Echtzeitdienst

`validfrom` streut je Register erheblich:

| Register | Gültig ab |
|---|---|
| CDB Genève | **01.03.2009** |
| LBK Basel-Mulhouse | 01.11.2009 |
| LBK Zürich | 03.07.2015 |
| LBK Bern | 28.09.2018 |
| LBK Saanen | 17.02.2020 |
| CDR Lugano-Agno | 09.10.2020 |
| LBK Samedan | 25.05.2020 |
| LBK St. Gallen-Altenrhein | **16.04.2024** |

`source_freshness` darf hier **niemals «live» behaupten** — es trägt das
`validfrom` des gefundenen Registers.

---

## 6. LSV-Grenzwerte — Verifikation

**SR 814.41**, Lärmschutz-Verordnung, **Anhang 5** «Belastungsgrenzwerte für
den Lärm ziviler Flugplätze» (zu Art. 40 Abs. 1). Konsolidierte Fassung
**in Kraft seit 01.04.2026**, verifiziert am **28.07.2026**.

Bezugsweg: Fedlex-SPARQL (`https://fedlex.data.admin.ch/sparqlendpoint`) →
aktuelle Konsolidierung ermitteln → amtliches HTML abrufen. Die Werte sind
**aus dem amtlichen Text ausgelesen**, nicht aus dem Modellgedächtnis.

**Ziff. 221 — Lr_t, Tag (06–22 Uhr):**

| ES | Planungswert | IGW | Alarmwert |
|---|---|---|---|
| I | 53 | 55 | 60 |
| II | 57 | 60 | 65 |
| III | 60 | 65 | 70 |
| IV | 65 | 70 | 75 |

**Ziff. 222 — Lr_n, Nachtstunden:**

| ES | Planungswert | IGW | Alarmwert |
|---|---|---|---|
| I | 43 | 45 | 55 |
| II | 47 / **50** | 50 / **55** | 60 / **65** |
| III | 50 | 55 | 65 |
| IV | 55 | 60 | 70 |

Fussnote im Original: «Die höheren Werte gelten für die erste Nachtstunde
(22–23 Uhr)» — betrifft **ausschliesslich ES II**. Genau der Fall, den eine
Grenzwertprüfung sonst still falsch rechnet.

**Ziff. 21 — Lr_k, Kleinluftfahrzeuge (≤ 8618 kg):**
I 50/55/65 · II 55/60/70 · III 60/65/70 · IV 65/70/75

**Ziff. 23 — L_max, reine Helikopterflugplätze:**
I 70/75/85 · II 75/80/90 · III 80/85/90 · IV 85/90/95

⚠️ Anhang 5 gilt ausdrücklich für **zivile** Flugplätze. Für Militärflugplätze
ist **Anhang 8** einschlägig — nicht geprobt, daher verweigert
`env_noise_limits_check` die Prüfung für `period='military'`.

---

## 7. Architektur-Entscheid: Live-API (Abweichung vom Dump-first-Standard)

Gemessen, nicht unterstellt:

| Grösse | Wert |
|---|---|
| Objekte gesamt (8 Sublayer) | **747** |
| Nutzlast mit Geometrie (180 Obj.) | 764 KB / 26'406 Stützpunkte |
| Hochrechnung Gesamtkataster | **~3 MB GeoJSON** |

Ein Dump wäre also **problemlos machbar** — die Prämisse «kein sinnvoller
Bulk-Download» trifft nicht zu. Ausschlaggebend sind zwei andere Gründe:

1. **Die Frischezusage würde zur Lüge.** Die Kataster werden je Flugplatz
   einzeln und unangekündigt nachgeführt (2009–2024). Aus einem Dump gelesen
   wäre `source_freshness` das `validfrom` zum Spiegelzeitpunkt — das Tool
   würde Provenienz *behaupten*, die es nicht mehr hat. Für einen Server,
   dessen drittes Tool ausdrücklich «wie alt ist die Grundlage» beantwortet,
   ist das der schlechtestmögliche Fehlermodus.
2. **Die räumliche Abfrage ist der Wert, nicht die Attribute.** Lokal
   ausgewertet hiesse: Punkt-zu-Linie-Distanzen über 26'000+ Stützpunkte je
   Layer. Das erfordert entweder **shapely/GEOS** — die erste kompilierte
   Abhängigkeit in einem bewusst binärfreien `pyproject.toml` — oder eigene
   Distanzmathematik. Letztere wäre in LV95 (metrische Projektion, euklidische
   Distanz exakt) machbar; dann verantwortet aber *dieser Server* die Auslegung
   amtlicher Lärmkurven statt des Bundesamts.

---

## 8. Merksatz

> **Fluglärm hat Linien, Strassenlärm hat nur Pixel** — Bahnlärm hätte Daten,
> ist aber bewusst nicht angebunden.
