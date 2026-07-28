"""
Fluglärmbelastungskataster (BAZL) via `api3.geo.admin.ch` — identify-Endpoint.

Datenquelle: Bundesamt für Zivilluftfahrt BAZL, publiziert über die
Bundes-Geodaten-Infrastruktur (api3.geo.admin.ch, `ech`-MapServer). Keine
Authentifizierung, Fair Use ca. 20 Requests/Minute.

Aufbau analog `lindas/client.py`: **abhängigkeitsarm und extraktionsfähig** —
das Modul kennt weder den geteilten HTTP-Client noch den Egress-Guard, beide
werden vom Aufrufer übergeben. Die Bindung an den Server liegt in
`api_client.py`, die Tool-Schicht in `server.py`.

Live-Probe 2026-07-28 (siehe `docs/probe-fluglaerm.md`) — die Befunde, die
diesen Code prägen:

  1. Die Kurven sind **MultiLineString-Isolinien, keine Flächen.** `identify`
     macht damit *keinen* Punkt-in-Fläche-Test, sondern eine Näherungsabfrage
     im Toleranzradius. Dieses Modul liefert deshalb eine **Klammer**
     (min/max der nahen Kurven), keinen interpolierten Punktwert — siehe
     `noise_at_point`.
  2. Der Toleranzradius entscheidet das Ergebnis: am selben Punkt liefern
     100 m → 61–62 dB, aber 500 m → 58–75 dB (die 75-dB-Kurve liegt 1,5 km
     entfernt auf der Piste). «Höchste gefundene Kurve» ist nur bei kleinem
     Radius eine sinnvolle obere Schranke.
  3. Null Treffer ist **zweideutig**: ausserhalb jedes Katasters (Chur) —
     oder mitten auf der Piste, innerhalb der innersten Kurve. Beides liefert
     bei r=100 m null Treffer. Auflösung über eine zweite Abfrage mit
     Fernradius (`FAR_RADIUS_M`).
  4. `exposurecurve_level_db` kommt als **String**, nicht als Zahl → zentral
     in `clean_level_db()` normalisiert.
  5. Die Layer-ID braucht zwingend den Sublayer-Suffix; die Basis-ID allein
     quittiert mit HTTP 400.
  6. Stichtagskataster, kein Echtzeitdienst: `validfrom` streut je Register
     von 01.03.2009 (Genève) bis 16.04.2024 (St. Gallen-Altenrhein). Die
     Frischeangabe muss aus dem *gefundenen* Register stammen, nie «live».
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from . import sparql_client

# --- Endpoint & Layer ---------------------------------------------------------

GEOADMIN_HOST = "api3.geo.admin.ch"
IDENTIFY_URL = f"https://{GEOADMIN_HOST}/rest/services/ech/MapServer/identify"

# Basis-ID der BAZL-Kataster. Ohne Sublayer-Suffix → HTTP 400 (Fundstück 5).
LAYER_PREFIX = "ch.bazl.laermbelastungskataster-zivilflugplaetze"

# Retry: Portfolio-Standard 2 s/4 s/8 s (wie `lindas/client.py`), nicht der
# 0.5-s-Default von `sparql_client`. Tests monkeypatchen RETRY_BASE_DELAY auf 0.
RETRY_MAX_ATTEMPTS = 4
RETRY_BASE_DELAY = 2.0

# --- LV95-Plausibilitätsvalidator ---------------------------------------------
# Portiert aus `swisstopo-mcp/src/swisstopo_mcp/coords.py` (Ausdehnung der
# Schweiz in EPSG:2056). WGS84-Eingaben sind der häufigste LLM-Fehler bei
# Schweizer Geodaten: 8.54/47.37 ist eine gültige Koordinate — nur eben in
# Grad. Ohne diesen Guard würde sie als Meterwert weit ausserhalb der Schweiz
# interpretiert und stillschweigend «kein Kataster» liefern.

LV95_E_MIN, LV95_E_MAX = 2_480_000, 2_840_000
LV95_N_MIN, LV95_N_MAX = 1_070_000, 1_300_000


class CoordinateError(ValueError):
    """Eingabekoordinate ist kein plausibler LV95-Punkt in der Schweiz."""


def validate_lv95(east: float, north: float) -> tuple[int, int]:
    """Prüft ein Koordinatenpaar auf LV95-Plausibilität (EPSG:2056, Meter).

    Raises:
        CoordinateError: mit Umrechnungshinweis, wenn die Werte nach WGS84-Grad
            aussehen oder ausserhalb der Landesausdehnung liegen.
    """
    # Gradwerte zuerst abfangen — das ist der informativere Fehler.
    if abs(east) <= 180 and abs(north) <= 180:
        raise CoordinateError(
            f"Die Werte east={east}, north={north} sehen nach WGS84-Grad aus, "
            "erwartet werden LV95-Meter (EPSG:2056). Umrechnung z.B. über den "
            "swisstopo-REFRAME-Dienst oder das Tool `convert_coordinates` in "
            "swisstopo-mcp. "
            "Beispiel Zürich HB: WGS84 8.540/47.378 → LV95 E 2683146 / N 1247993."
        )
    if not (LV95_E_MIN <= east <= LV95_E_MAX) or not (LV95_N_MIN <= north <= LV95_N_MAX):
        raise CoordinateError(
            f"LV95-Koordinaten ausserhalb der Schweiz: east muss zwischen "
            f"{LV95_E_MIN} und {LV95_E_MAX} liegen, north zwischen {LV95_N_MIN} "
            f"und {LV95_N_MAX} (Meter, EPSG:2056). Erhalten: east={east}, north={north}. "
            "Bei vertauschten Achsen: east ist der grössere Wert (~2.6 Mio)."
        )
    return int(east), int(north)


# --- Perioden / Sublayer ------------------------------------------------------


@dataclass(frozen=True)
class PeriodSpec:
    """Ein abfragbarer Sublayer des Katasters."""

    suffix: str
    exposure_type: str
    label_de: str
    label_en: str
    #: Zugehörige LSV-Grenzwerttabelle (Anhang 5) — None, wenn Anhang 5 nicht gilt.
    limits_table: str | None

    @property
    def layer(self) -> str:
        return f"{LAYER_PREFIX}{self.suffix}"


# Alle acht Sublayer sind identify-fähig (Probe 2026-07-28). Die vier Werte
# `light_aircraft`/`helicopter`/`helicopter_max`/`military` waren im ersten
# Entwurf nicht vorgesehen — ohne sie bleiben 18 der 38 Register des Katasters
# unerreichbar (Regionalflugplätze wie Grenchen, Birrfeld, Schänis erscheinen
# ausschliesslich im Kleinluftfahrzeug-Layer).
PERIODS: dict[str, PeriodSpec] = {
    "day": PeriodSpec(
        "_klein-grossflugzeuge",
        "OverallTrafficDay_Lr",
        "Gesamtverkehr Tag (06–22 Uhr), Lr",
        "Overall traffic, day (06:00–22:00), Lr",
        "Z221",
    ),
    "night_first": PeriodSpec(
        "_erste-nachtstunde",
        "FirstNightHour_Lr",
        "Erste Nachtstunde (22–23 Uhr), Lr",
        "First night hour (22:00–23:00), Lr",
        "Z222_first",
    ),
    "night_second": PeriodSpec(
        "_zweite-nachtstunde",
        "SecondNightHour_Lr",
        "Zweite Nachtstunde (23–24 Uhr), Lr",
        "Second night hour (23:00–24:00), Lr",
        "Z222",
    ),
    "night_last": PeriodSpec(
        "_letzte-nachtstunde",
        "LastNightHour_Lr",
        "Letzte Nachtstunde (05–06 Uhr), Lr",
        "Last night hour (05:00–06:00), Lr",
        "Z222",
    ),
    "light_aircraft": PeriodSpec(
        "_kleinluftfahrzeuge",
        "LightAircraft_Lr",
        "Kleinluftfahrzeuge (≤ 8618 kg), Lr",
        "Light aircraft (≤ 8618 kg), Lr",
        "Z21",
    ),
    "helicopter": PeriodSpec(
        "_helikopter",
        "Helicopter_Lr",
        "Helikopter, Lr",
        "Helicopters, Lr",
        # Helikopter ≤ 8618 kg sind Kleinluftfahrzeuge nach Anhang 5 Ziff. 1 Abs. 3;
        # Ziff. 23 stellt die Lmax-Werte ausdrücklich «zusätzlich zu den
        # Belastungsgrenzwerten in Lrk» → für Lr gilt Ziff. 21.
        "Z21",
    ),
    "helicopter_max": PeriodSpec(
        "_helikopter-maximalpegel",
        "Helicopter_Lmax",
        "Helikopter, Maximalpegel Lmax",
        "Helicopters, maximum level Lmax",
        "Z23",
    ),
    "military": PeriodSpec(
        "_militaer-gesamt",
        "OverallTrafficMilitary_Lr",
        "Militärflugplatz, Gesamtverkehr Lr",
        "Military airfield, overall traffic Lr",
        # Anhang 5 gilt ausdrücklich für *zivile* Flugplätze. Für Militär-
        # flugplätze ist Anhang 8 LSV einschlägig — nicht geprobt, daher hier
        # bewusst None statt einer plausibel aussehenden, falschen Tabelle.
        None,
    ),
}

PERIOD_NAMES = tuple(PERIODS.keys())

# --- Suchradius ---------------------------------------------------------------
# `tolerance` ist in Pixeln relativ zu imageDisplay/mapExtent. Mit einem
# Kartenausschnitt von ±EXTENT_HALF_M über 1000 px ergibt sich ein fester
# Massstab von 2 m/px — der Radius ist damit direkt in Metern steuerbar.
EXTENT_HALF_M = 1000
_METRES_PER_PIXEL = (2 * EXTENT_HALF_M) / 1000

DEFAULT_RADIUS_M = 100
FAR_RADIUS_M = 1000
MIN_RADIUS_M = 10
MAX_RADIUS_M = EXTENT_HALF_M  # grösser als der Ausschnitt wäre sinnlos

# Landesausdehnung als Envelope — für die Registerübersicht.
CH_ENVELOPE = f"{LV95_E_MIN},{LV95_N_MIN},{LV95_E_MAX},{LV95_N_MAX}"

LEGAL_NOTICE = (
    "Der Lärmbelastungskataster ist eine Orientierungsgrundlage. "
    "Rechtsverbindliche Auskünfte zu Bauvorhaben erteilen die zuständige "
    "kantonale Fachstelle bzw. das BAZL. Dieses Tool ersetzt keine "
    "Baubewilligungsabklärung."
)

LEGAL_NOTICE_EN = (
    "The aircraft noise cadastre is an orientation aid. Legally binding "
    "information on construction projects is issued by the competent cantonal "
    "office or by the FOCA (BAZL). This tool does not replace a building "
    "permit clarification."
)

SOURCE = "BAZL Lärmbelastungskataster Zivilflugplätze (api3.geo.admin.ch)"
PROVENANCE = "live_api"


# --- Normalisierung -----------------------------------------------------------


def clean_level_db(raw: Any) -> float | None:
    """Normalisiert `exposurecurve_level_db` zu float.

    Der Dienst liefert den dB-Wert als String ('62'), gelegentlich mit
    Einheit oder Dezimalkomma. Ohne zentrale Normalisierung entstehen genau
    die Vergleichsfehler, die im Portfolio schon bei den EFV-Reframe-Werten
    aufgetreten sind (String-Sortierung: '9' > '62').
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    text = str(raw).strip().replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:  # pragma: no cover — Regex garantiert Parsebarkeit
        return None


def _curve(feature: dict[str, Any]) -> dict[str, Any]:
    """Extrahiert die fachlichen Felder eines identify-Treffers."""
    p = feature.get("properties") or {}
    return {
        "feature_id": feature.get("featureId"),
        "level_db": clean_level_db(p.get("exposurecurve_level_db")),
        "exposure_type": p.get("exposuregroup_exposuretype"),
        "register_name": p.get("noisepollutionregister_registername"),
        "editor": p.get("noisepollutionregister_editor"),
        "valid_from": p.get("noisepollutionregister_validity_validfrom"),
        "document_link": p.get("noisepollutionregister_documentlink"),
    }


def _dedupe(curves: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fasst Mehrfachsegmente derselben dB-Kurve zusammen.

    Eine Isolinie kann in mehreren Segmenten geliefert werden (bei r=1000 m
    kamen 21 Treffer auf 14 verschiedene dB-Werte). Für die Auswertung zählt
    die Kurve, nicht das Segment.
    """
    seen: dict[tuple[Any, Any], dict[str, Any]] = {}
    for c in curves:
        key = (c["level_db"], c["register_name"])
        if key not in seen:
            seen[key] = c
    return sorted(
        seen.values(),
        key=lambda c: (c["level_db"] is None, c["level_db"] or 0.0),
    )


def utc_now() -> str:
    """Abrufzeitpunkt als ISO-8601-UTC (für `retrieved_at`)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- Transport ----------------------------------------------------------------


async def _identify(
    client: httpx.AsyncClient,
    *,
    layer: str,
    geometry: str,
    geometry_type: str,
    map_extent: str,
    tolerance: float,
    limit: int | None = None,
    egress_check: Callable[[str], None] | None = None,
    base_delay: float | None = None,
    max_attempts: int | None = None,
) -> list[dict[str, Any]]:
    """Ruft den identify-Endpoint auf und liefert die Rohtreffer.

    Retry ausschliesslich bei transienten Fehlern (429/5xx, Timeout, Netzwerk)
    mit 2 s/4 s/8 s Backoff; 4xx ausser 429 wird sofort durchgereicht — HTTP 400
    bei ungültiger Layer-ID ist deterministisch und darf nicht wiederholt werden.
    """
    params: dict[str, Any] = {
        "geometry": geometry,
        "geometryType": geometry_type,
        "geometryFormat": "geojson",
        "imageDisplay": "1000,1000,96",
        "mapExtent": map_extent,
        "tolerance": f"{tolerance:g}",
        "layers": f"all:{layer}",
        "sr": "2056",
        "lang": "de",
        "returnGeometry": "false",
    }
    if limit is not None:
        params["limit"] = str(limit)

    data = await sparql_client.get_json(
        client,
        IDENTIFY_URL,
        params=params,
        base_delay=RETRY_BASE_DELAY if base_delay is None else base_delay,
        max_attempts=RETRY_MAX_ATTEMPTS if max_attempts is None else max_attempts,
        egress_check=egress_check,
    )
    results = (data or {}).get("results")
    return results if isinstance(results, list) else []


async def _identify_point(
    client: httpx.AsyncClient,
    layer: str,
    east: int,
    north: int,
    radius_m: float,
    **kw: Any,
) -> list[dict[str, Any]]:
    """Punktabfrage mit einem in Metern angegebenen Suchradius."""
    d = EXTENT_HALF_M
    return await _identify(
        client,
        layer=layer,
        geometry=f"{east},{north}",
        geometry_type="esriGeometryPoint",
        map_extent=f"{east - d},{north - d},{east + d},{north + d}",
        tolerance=radius_m / _METRES_PER_PIXEL,
        **kw,
    )


# --- Fachlogik: Punktabfrage --------------------------------------------------


async def noise_at_point(
    client: httpx.AsyncClient,
    *,
    period: str,
    east: int,
    north: int,
    radius_m: int = DEFAULT_RADIUS_M,
    **kw: Any,
) -> dict[str, Any]:
    """Ermittelt die Fluglärmbelastung an einem LV95-Punkt.

    Die Kurven sind Isolinien, keine Flächen — `identify` liefert also die
    Kurven *in der Nähe* des Punktes, nicht die Kurve, in der er liegt. Das
    Ergebnis ist deshalb eine Klammer: der Punkt liegt zwischen der niedrigsten
    und der höchsten gefundenen Kurve. `level_db` ist der höchste Wert und
    damit eine **obere Schranke** (Vorsorgeprinzip), kein Messwert.

    Findet die enge Abfrage nichts, wird einmal mit `FAR_RADIUS_M` nachgefasst:
    das unterscheidet «ausserhalb jedes Katasters» von «innerhalb der innersten
    Kurve» — auf der Piste Kloten liefert r=100 m dasselbe leere Resultat wie
    Chur, obwohl dort 75 dB anliegen.
    """
    spec = PERIODS[period]
    features = await _identify_point(client, spec.layer, east, north, radius_m, **kw)
    curves = _dedupe([_curve(f) for f in features])
    resolution = "bracketed"
    effective_radius = radius_m

    if not curves:
        # Zweideutigkeit auflösen (Fundstück 3 der Probe).
        features = await _identify_point(client, spec.layer, east, north, FAR_RADIUS_M, **kw)
        curves = _dedupe([_curve(f) for f in features])
        effective_radius = FAR_RADIUS_M
        resolution = "wide_area_only" if curves else "no_cadastre"

    levels = [c["level_db"] for c in curves if c["level_db"] is not None]
    top = curves[-1] if curves else None

    result: dict[str, Any] = {
        "found": bool(curves),
        "resolution": resolution,
        "period": period,
        "period_label": spec.label_de,
        "layer": spec.layer,
        "east": east,
        "north": north,
        "search_radius_m": effective_radius,
        "curves_found": len(curves),
        "level_db": max(levels) if levels else None,
        "level_db_lower": min(levels) if levels else None,
        "exposure_type": top["exposure_type"] if top else spec.exposure_type,
        "register_name": top["register_name"] if top else None,
        "editor": top["editor"] if top else None,
        "valid_from": top["valid_from"] if top else None,
        "document_link": top["document_link"] if top else None,
        "curves": curves,
    }
    result["note"] = _interpretation(result)
    return result


def _interpretation(r: dict[str, Any]) -> str:
    """Formuliert aus, was der Befund fachlich bedeutet — und was nicht."""
    radius = r["search_radius_m"]
    if r["resolution"] == "no_cadastre":
        return (
            f"An diesem Standort ist kein Fluglärmbelastungskataster publiziert — "
            f"weder im Umkreis von {DEFAULT_RADIUS_M} m noch von {FAR_RADIUS_M} m wurde "
            f"eine Lärmkurve gefunden. Der Kataster deckt nur die Umgebung von "
            f"Flugplätzen ab, nicht die Fläche der Schweiz. Das ist ein gültiges "
            f"Ergebnis, kein Abruffehler."
        )
    lo, hi = r["level_db_lower"], r["level_db"]
    if r["resolution"] == "wide_area_only":
        return (
            f"Im Umkreis von {DEFAULT_RADIUS_M} m liegt keine Lärmkurve, im Umkreis von "
            f"{radius} m dagegen Kurven von {lo:g} bis {hi:g} dB. Der Punkt liegt "
            f"damit entweder innerhalb der innersten Kurve (dann mindestens {hi:g} dB) "
            f"oder in einem Bereich mit flachem Lärmgradienten. Für eine belastbare "
            f"Aussage bitte den amtlichen Katasterplan konsultieren (siehe document_link)."
        )
    if lo == hi:
        return (
            f"Der Punkt liegt auf oder unmittelbar an der {hi:g}-dB-Kurve (Suchradius {radius} m)."
        )
    return (
        f"Der Punkt liegt zwischen der {lo:g}-dB- und der {hi:g}-dB-Kurve "
        f"(Suchradius {radius} m). Ausgewiesen wird {hi:g} dB als obere Schranke "
        f"(Vorsorgeprinzip) — die Kurven sind Isolinien, der Dienst liefert keinen "
        f"interpolierten Punktwert."
    )


# --- Fachlogik: Registerübersicht ---------------------------------------------


async def registers(
    client: httpx.AsyncClient,
    *,
    period: str | None = None,
    limit: int = 1000,
    **kw: Any,
) -> list[dict[str, Any]]:
    """Listet die publizierten Lärmbelastungskataster je Sublayer.

    Ein Envelope über die Landesausdehnung liefert alle Kurvenobjekte; daraus
    wird je Register (Flugplatz) ein Eintrag mit Gültigkeitsdatum, Herausgeber
    und amtlichem PDF-Link verdichtet. Das ist das Provenienz-Tool: es
    beantwortet «wie alt ist die Grundlage».
    """
    wanted = [period] if period else list(PERIODS)
    found: dict[tuple[str, str], dict[str, Any]] = {}

    for name in wanted:
        spec = PERIODS[name]
        features = await _identify(
            client,
            layer=spec.layer,
            geometry=CH_ENVELOPE,
            geometry_type="esriGeometryEnvelope",
            map_extent=CH_ENVELOPE,
            tolerance=0,
            limit=limit,
            **kw,
        )
        for f in features:
            c = _curve(f)
            reg = c["register_name"]
            if not reg:
                continue
            key = (name, reg)
            entry = found.get(key)
            if entry is None:
                found[key] = {
                    "register_name": reg,
                    "period": name,
                    "period_label": spec.label_de,
                    "editor": c["editor"],
                    "valid_from": c["valid_from"],
                    "document_link": c["document_link"],
                    "curve_count": 1,
                    "level_min_db": c["level_db"],
                    "level_max_db": c["level_db"],
                }
            else:
                entry["curve_count"] += 1
                lvl = c["level_db"]
                if lvl is not None:
                    lo, hi = entry["level_min_db"], entry["level_max_db"]
                    entry["level_min_db"] = lvl if lo is None else min(lo, lvl)
                    entry["level_max_db"] = lvl if hi is None else max(hi, lvl)

    return sorted(found.values(), key=lambda e: (e["register_name"], e["period"]))


def parse_valid_from(value: str | None) -> datetime | None:
    """Parst das Schweizer Datumsformat `TT.MM.JJJJ` des Katasters."""
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%d.%m.%Y")
    except ValueError:
        return None


def oldest_valid_from(entries: list[dict[str, Any]]) -> str | None:
    """Ältestes Gültigkeitsdatum einer Registerliste (für `source_freshness`)."""
    dated = [(parse_valid_from(e.get("valid_from")), e.get("valid_from")) for e in entries]
    dated = [(d, raw) for d, raw in dated if d is not None]
    return min(dated)[1] if dated else None


# --- LSV-Grenzwerte (Anhang 5) ------------------------------------------------
#
# Rechtsgrundlage: Lärmschutz-Verordnung (LSV), SR 814.41, **Anhang 5**
# «Belastungsgrenzwerte für den Lärm ziviler Flugplätze» (zu Art. 40 Abs. 1).
# Konsolidierte Fassung in Kraft seit **01.04.2026**.
# Verifiziert am **28.07.2026** gegen den amtlichen Text auf Fedlex:
#   https://www.fedlex.admin.ch/eli/cc/1987/338_338_338/de
# Bezugsquelle der geprüften Fassung (via Fedlex-SPARQL ermittelt):
#   https://fedlex.data.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/1987/
#   338_338_338/20260401/de/html/fedlex-data-admin-ch-eli-cc-1987-338_338_338-
#   20260401-de-html-1.html
#
# Werte NICHT aus dem Gedächtnis übernommen, sondern aus den vier Tabellen des
# Anhangs ausgelesen. Reihenfolge je Empfindlichkeitsstufe:
#   (Planungswert, Immissionsgrenzwert, Alarmwert) in dB(A).

LSV_SR = "SR 814.41"
LSV_ANNEX = "Anhang 5 (zu Art. 40 Abs. 1)"
LSV_VERSION = "konsolidierte Fassung in Kraft seit 01.04.2026"
LSV_VERIFIED_ON = "2026-07-28"
LSV_URL = "https://www.fedlex.admin.ch/eli/cc/1987/338_338_338/de"

SENSITIVITY_LEVELS = ("I", "II", "III", "IV")

LSV_TABLES: dict[str, dict[str, Any]] = {
    # Ziffer 21 — Lrk, Lärm des Verkehrs von Kleinluftfahrzeugen (≤ 8618 kg).
    "Z21": {
        "citation": "Anhang 5 Ziff. 21 LSV",
        "quantity": "Lrk",
        "description": "Lärm des Verkehrs von Kleinluftfahrzeugen (≤ 8618 kg)",
        "values": {
            "I": (50, 55, 65),
            "II": (55, 60, 70),
            "III": (60, 65, 70),
            "IV": (65, 70, 75),
        },
    },
    # Ziffer 221 — Lrt, Gesamtverkehr Tag (06–22 Uhr) auf Flugplätzen mit
    # Grossflugzeugverkehr.
    "Z221": {
        "citation": "Anhang 5 Ziff. 221 LSV",
        "quantity": "Lrt",
        "description": "Gesamtverkehr Klein- und Grossflugzeuge, Tag (06–22 Uhr)",
        "values": {
            "I": (53, 55, 60),
            "II": (57, 60, 65),
            "III": (60, 65, 70),
            "IV": (65, 70, 75),
        },
    },
    # Ziffer 222 — Lrn, zweite (23–24 Uhr) und letzte Nachtstunde (05–06 Uhr).
    "Z222": {
        "citation": "Anhang 5 Ziff. 222 LSV",
        "quantity": "Lrn",
        "description": "Gesamtverkehr, zweite (23–24 Uhr) bzw. letzte Nachtstunde (05–06 Uhr)",
        "values": {
            "I": (43, 45, 55),
            "II": (47, 50, 60),
            "III": (50, 55, 65),
            "IV": (55, 60, 70),
        },
    },
    # Ziffer 222 — Lrn, erste Nachtstunde (22–23 Uhr). Die Fussnote der Tabelle
    # («Die höheren Werte gelten für die erste Nachtstunde») betrifft
    # ausschliesslich ES II; I, III und IV sind in beiden Fällen identisch.
    "Z222_first": {
        "citation": "Anhang 5 Ziff. 222 LSV (erste Nachtstunde, Fussnote 1)",
        "quantity": "Lrn",
        "description": "Gesamtverkehr, erste Nachtstunde (22–23 Uhr)",
        "values": {
            "I": (43, 45, 55),
            "II": (50, 55, 65),
            "III": (50, 55, 65),
            "IV": (55, 60, 70),
        },
    },
    # Ziffer 23 — Lmax, Flugplätze mit ausschliesslichem Helikopterverkehr.
    "Z23": {
        "citation": "Anhang 5 Ziff. 23 LSV",
        "quantity": "Lmax",
        "description": "Maximalpegel, Helikopterflugplätze",
        "values": {
            "I": (70, 75, 85),
            "II": (75, 80, 90),
            "III": (80, 85, 90),
            "IV": (85, 90, 95),
        },
    },
}

THRESHOLD_LABELS = (
    ("planning_value", "Planungswert", "Art. 23 USG"),
    ("immission_limit", "Immissionsgrenzwert", "Art. 15 USG"),
    ("alarm_value", "Alarmwert", "Art. 19 USG"),
)


class LimitsUnavailableError(LookupError):
    """Für diese Periode existiert in Anhang 5 LSV keine Grenzwerttabelle."""


def normalise_sensitivity(value: str) -> str:
    """Normalisiert die Empfindlichkeitsstufe auf 'I'…'IV'.

    Akzeptiert 'II', 'es ii', 'ES-II' und die arabischen Ziffern 1–4.
    """
    v = str(value).strip().upper().replace("ES", "").replace("-", " ").strip()
    arabic = {"1": "I", "2": "II", "3": "III", "4": "IV"}
    v = arabic.get(v, v)
    if v not in SENSITIVITY_LEVELS:
        raise ValueError(
            f"Empfindlichkeitsstufe '{value}' nicht erkannt. Zulässig: "
            f"{', '.join(SENSITIVITY_LEVELS)} (ES I–IV nach Art. 43 LSV)."
        )
    return v


def check_limits(level_db: float, sensitivity_level: str, period: str) -> dict[str, Any]:
    """Vergleicht einen Beurteilungspegel gegen die LSV-Grenzwerte.

    Raises:
        LimitsUnavailable: für `military` — Anhang 5 gilt ausdrücklich nur für
            *zivile* Flugplätze; für Militärflugplätze ist Anhang 8 einschlägig.
            Lieber keine Auskunft als die falsche Tabelle.
    """
    spec = PERIODS[period]
    es = normalise_sensitivity(sensitivity_level)

    if spec.limits_table is None:
        raise LimitsUnavailableError(
            f"Für '{period}' ({spec.label_de}) enthält Anhang 5 LSV keine "
            "Belastungsgrenzwerte: Anhang 5 gilt ausdrücklich für *zivile* "
            "Flugplätze (Landesflughäfen, konzessionierte Flugplätze, Flugfelder). "
            "Für Militärflugplätze ist Anhang 8 LSV einschlägig; dieser wurde für "
            "dieses Tool nicht verifiziert und wird deshalb nicht angewendet. "
            "Bitte direkt beim VBS/BAZL abklären."
        )

    table = LSV_TABLES[spec.limits_table]
    planning, immission, alarm = table["values"][es]

    thresholds = []
    for (key, label, basis), value in zip(THRESHOLD_LABELS, (planning, immission, alarm)):
        thresholds.append(
            {
                "key": key,
                "label": label,
                "legal_basis": basis,
                "limit_db": float(value),
                "exceeded": level_db > value,
                "margin_db": round(level_db - value, 1),
            }
        )

    exceeded = [t for t in thresholds if t["exceeded"]]
    if not exceeded:
        severity, verdict = "ok", f"Alle Belastungsgrenzwerte für ES {es} eingehalten."
    else:
        highest = exceeded[-1]
        severity = highest["key"]
        verdict = (
            f"{highest['label']} überschritten "
            f"({level_db:g} dB gegenüber {highest['limit_db']:g} dB, "
            f"+{highest['margin_db']:g} dB)."
        )

    return {
        "level_db": level_db,
        "sensitivity_level": es,
        "period": period,
        "period_label": spec.label_de,
        "quantity": table["quantity"],
        "description": table["description"],
        "thresholds": thresholds,
        "severity": severity,
        "verdict": verdict,
        "legal_reference": {
            "sr_number": LSV_SR,
            "title": "Lärmschutz-Verordnung (LSV)",
            "annex": LSV_ANNEX,
            "citation": table["citation"],
            "version": LSV_VERSION,
            "verified_on": LSV_VERIFIED_ON,
            "url": LSV_URL,
        },
    }
