"""
cube.link-Guardrail-Schicht für LINDAS — Schicht 2 von 3.

Kapselt den Zwei-Phasen-Zugriff auf RDF-Data-Cubes und die empirisch
gefundenen Stolperfallen (docs/probe-lindas-hydro.md, Nachtrag N1–N7):

  - Jede Query ist am Vokabular verankert (`?cube a cube:Cube` bzw. eine
    konkrete Cube-URI) — Blind-Scans laufen auf LINDAS in 70–90-s-Timeouts.
  - Observations sind NUR über den Zwischenschritt erreichbar:
    `?cube cube:observationSet ?set . ?set cube:observation ?obs .`
    Der Direktpfad `?cube cube:observation ?obs` liefert 0 Zeilen (N3).
  - Cubes sind versioniert; abgelöste Versionen tragen `schema:expires`.
    `find_cubes` dedupliziert darüber auf die aktuelle Version (N5).
  - Dimensionswerte kommen teils als Code-URIs (N4). `get_observations`
    löst sie intern zu Labels auf — der Aufrufer sieht nie rohe Codes.
    Kantons-/Gemeinde-URIs werden zusätzlich als Nummern-Felder
    (`*_canton_number`, `*_bfs_number`) exponiert (Join-Keys zu
    swiss-statistics-mcp und zurich-opendata-mcp).
  - Lizenz liegt am Datensatz im selben Named Graph, nicht am Cube (N7) —
    `get_cube_license` sucht beide Ebenen und ist ehrlich, wenn nichts
    deklariert ist.

Diese Schicht nimmt KEIN freies SPARQL von Tool-Aufrufern entgegen; alle
Query-Bausteine sind intern. Eingaben, die in Queries interpoliert werden,
laufen durch `sparql_escape` bzw. eine URI-Whitelist.

Wie `client.py` extraktionsfähig gehalten: kein Import aus dem Server-Paket.
"""

import re
from collections.abc import Awaitable, Callable
from typing import Any

# Runner-Signatur: eine gebundene `client.select`-Variante (Endpoint, Retry
# und Egress-Guard bereits konfiguriert). So bleibt cube.py transportfrei.
SelectRunner = Callable[[str], Awaitable[list[dict[str, str]]]]

_PREFIXES = """\
PREFIX cube: <https://cube.link/>
PREFIX schema: <http://schema.org/>
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX dcterms: <http://purl.org/dc/terms/>
"""

# Sprach-Präferenz (LINDAS ist fünfsprachig: de/fr/it/rm/en).
_LANG_FALLBACK: tuple[str, ...] = ("de", "en", "fr", "it", "rm")

# Nur syntaktisch harmlose URIs werden in Queries interpoliert.
_SAFE_URI = re.compile(r"^https?://[^\s<>\"'{}|\\^`]+$")

_CANTON_URI = re.compile(r"https://ld\.admin\.ch/canton/(\d+)$")
_MUNICIPALITY_URI = re.compile(r"https://ld\.admin\.ch/municipality/(\d+)$")

LICENSE_UNDECLARED = (
    "Lizenz: nicht am Cube deklariert — Herkunft BAFU/Bund, vor Weiterverwendung "
    "via opendata.swiss prüfen. «Im offenen Triplestore» ist nicht «frei verwendbar»."
)

# Bekannte Lizenz-URIs → lesbares Label (unbekannte URIs bleiben sichtbar).
_KNOWN_LICENSES: dict[str, str] = {
    "https://ld.admin.ch/vocabulary/TermsOfUse/Open-Use": "Open-Use (OGD-CH)",
}


def sparql_escape(value: str) -> str:
    """Escaped einen String für die Interpolation in ein SPARQL-Literal."""
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _safe_uri(uri: str) -> str:
    """Validiert eine URI vor der Interpolation in `<...>` (Injection-Guard)."""
    if not _SAFE_URI.match(uri):
        raise ValueError(f"Unzulässige URI für SPARQL-Interpolation: {uri!r}")
    return uri


def pick_lang(candidates: dict[str, str], lang: str = "de") -> str:
    """Wählt aus sprach-getaggten Kandidaten den besten Wert.

    Präferenz: gewünschte Sprache → de/en/fr/it/rm → untagged ('') → beliebig.
    (Muster aus i14y-mcp übernommen, nicht neu erfunden.)
    """
    if not candidates:
        return ""
    for key in (lang, *_LANG_FALLBACK, ""):
        if key in candidates and candidates[key]:
            return candidates[key]
    return next(iter(candidates.values()))


def version_sort_key(cube_uri: str, version: str = "") -> tuple[int, str]:
    """Sortier-Schlüssel für Cube-Versionen: `schema:version`, sonst URI-Suffix.

    URI-Suffixe kommen mal mit, mal ohne Trailing-Slash vor
    (`ubd0104/4/` vs. `ubd01041prod/13`) — beides wird erkannt.
    """
    if version.isdigit():
        return (int(version), cube_uri)
    tail = cube_uri.rstrip("/").rsplit("/", 1)[-1]
    return (int(tail) if tail.isdigit() else -1, cube_uri)


def base_cube_uri(cube_uri: str) -> str:
    """Basis-URI eines versionierten Cubes (Versions-Suffix abgetrennt)."""
    stripped = cube_uri.rstrip("/")
    head, _, tail = stripped.rpartition("/")
    return head if tail.isdigit() else stripped


def dedupe_latest_versions(cubes: list[dict[str, str]]) -> list[dict[str, str]]:
    """Reduziert eine Cube-Liste auf die jeweils neueste Version je Basis-URI.

    Erwartet Dicts mit mindestens `cube` (URI), optional `version`.
    Server-seitig filtert `find_cubes` bereits abgelöste Versionen über
    `schema:expires` — diese Funktion ist der Belt-and-Braces-Schritt für
    Stores, die `expires` nicht pflegen.
    """
    latest: dict[str, dict[str, str]] = {}
    for cube in cubes:
        base = base_cube_uri(cube.get("cube", ""))
        current = latest.get(base)
        if current is None or version_sort_key(
            cube.get("cube", ""), cube.get("version", "")
        ) > version_sort_key(current.get("cube", ""), current.get("version", "")):
            latest[base] = cube
    return sorted(latest.values(), key=lambda c: c.get("cube", ""))


def resolve_codes(
    rows: list[dict[str, Any]], labels: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Ersetzt Code-URIs in Observation-Zeilen durch Labels (rein, testbar).

    Je aufgelöster Dimension `d` entstehen:
      - `d`: das Label (der Aufrufer sieht nie den rohen Code),
      - `d_code`: der Kurz-Identifier (schema:identifier bzw. URI-Endstück),
      - `d_canton_number` / `d_bfs_number`: Nummern-Join-Keys, falls die
        Code-URI bzw. ihr `containedInPlace` auf Kanton/Gemeinde zeigt.
    """
    resolved: list[dict[str, Any]] = []
    for row in rows:
        out: dict[str, Any] = {}
        for key, value in row.items():
            info = labels.get(value) if isinstance(value, str) else None
            if info is None:
                out[key] = value
                continue
            out[key] = info.get("label") or value.rstrip("/").rsplit("/", 1)[-1]
            out[f"{key}_code"] = info.get("identifier") or value.rstrip("/").rsplit("/", 1)[-1]
            for uri in (value, info.get("contained_in", "")):
                canton = _CANTON_URI.search(uri or "")
                if canton:
                    out[f"{key}_canton_number"] = int(canton.group(1))
                bfs = _MUNICIPALITY_URI.search(uri or "")
                if bfs:
                    out[f"{key}_bfs_number"] = int(bfs.group(1))
        resolved.append(out)
    return resolved


# --- Phase 0: Cubes finden ------------------------------------------------------


async def find_cubes(
    run: SelectRunner, name_contains: str, *, lang: str = "de", limit: int = 50
) -> list[dict[str, str]]:
    """Sucht aktuelle Cube-Versionen per Namens-Teilstring (verankert).

    Abgelöste Versionen (mit `schema:expires`) werden serverseitig gefiltert,
    danach `dedupe_latest_versions` als zweite Sicherung.
    """
    term = sparql_escape(name_contains.lower())
    query = f"""{_PREFIXES}
SELECT ?cube ?name ?version ?status WHERE {{
  ?cube a cube:Cube ; schema:name ?name .
  FILTER(LANG(?name) = '{sparql_escape(lang)}')
  FILTER(CONTAINS(LCASE(STR(?name)), "{term}"))
  FILTER NOT EXISTS {{ ?cube schema:expires ?expires }}
  OPTIONAL {{ ?cube schema:version ?version }}
  OPTIONAL {{ ?cube schema:creativeWorkStatus ?status }}
}} LIMIT {int(limit)}
"""
    return dedupe_latest_versions(await run(query))


# --- Phase 1: Struktur lesen ----------------------------------------------------


async def get_cube_structure(
    run: SelectRunner, cube_uri: str, *, lang: str = "de"
) -> list[dict[str, str]]:
    """Liest Dimensionen und Measures eines Cubes (Phase-1-Zugriff).

    Liefert je Dimension: `dimension` (URI), `name` (pick_lang), `kind`
    ('key' | 'measure' | 'other').
    """
    uri = _safe_uri(cube_uri)
    query = f"""{_PREFIXES}
SELECT ?dim ?dimName ?dimLang ?kind WHERE {{
  <{uri}> cube:observationConstraint ?shape .
  ?shape sh:property ?p . ?p sh:path ?dim .
  OPTIONAL {{ ?p schema:name ?dimName . BIND(LANG(?dimName) AS ?dimLang) }}
  OPTIONAL {{ ?p a ?kind FILTER(?kind IN (cube:KeyDimension, cube:MeasureDimension)) }}
}}
"""
    names: dict[str, dict[str, str]] = {}
    kinds: dict[str, str] = {}
    for row in await run(query):
        dim = row.get("dim", "")
        names.setdefault(dim, {})
        if row.get("dimName"):
            names[dim][row.get("dimLang", "")] = row["dimName"]
        kind = row.get("kind", "")
        if kind.endswith("KeyDimension"):
            kinds[dim] = "key"
        elif kind.endswith("MeasureDimension"):
            kinds[dim] = "measure"
    return [
        {"dimension": dim, "name": pick_lang(names[dim], lang), "kind": kinds.get(dim, "other")}
        for dim in names
    ]


async def find_dimension_values(
    run: SelectRunner,
    cube_uri: str,
    dimension: str,
    *,
    name_contains: str = "",
    lang: str = "de",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Sucht Werte einer Code-Dimension per Namens-Teilstring (verankert am Cube).

    Übersetzt User-Eingaben (z.B. einen Ortsnamen) in Code-URIs, die dann als
    `filters` an `get_observations` gehen. Liefert je Wert: `value` (URI),
    `name` (pick_lang), `identifier`, `canton_number`/`bfs_number` (falls
    `containedInPlace` auf Kanton/Gemeinde zeigt).
    """
    term = sparql_escape(name_contains.lower())
    name_filter = f'  FILTER(CONTAINS(LCASE(STR(?name)), "{term}"))' if name_contains else ""
    query = f"""{_PREFIXES}
SELECT DISTINCT ?value ?name ?nameLang ?identifier ?place WHERE {{
  <{_safe_uri(cube_uri)}> cube:observationSet ?set .
  ?set cube:observation ?obs .
  ?obs <{_safe_uri(dimension)}> ?value .
  ?value schema:name ?name .
  BIND(LANG(?name) AS ?nameLang)
{name_filter}
  OPTIONAL {{ ?value schema:identifier ?identifier }}
  OPTIONAL {{ ?value schema:containedInPlace ?place }}
}} LIMIT {int(limit) * 5}
"""
    names: dict[str, dict[str, str]] = {}
    meta: dict[str, dict[str, Any]] = {}
    for row in await run(query):
        value = row.get("value", "")
        names.setdefault(value, {})[row.get("nameLang", "")] = row.get("name", "")
        entry = meta.setdefault(value, {"value": value})
        if row.get("identifier"):
            entry["identifier"] = row["identifier"]
        place = row.get("place", "")
        canton = _CANTON_URI.search(place)
        if canton:
            entry["canton_number"] = int(canton.group(1))
        bfs = _MUNICIPALITY_URI.search(place)
        if bfs:
            entry["bfs_number"] = int(bfs.group(1))
    results = []
    for value, entry in meta.items():
        entry["name"] = pick_lang(names.get(value, {}), lang)
        results.append(entry)
    results.sort(key=lambda e: str(e.get("name", "")))
    return results[:limit]


# --- Phase 2: Observations lesen ------------------------------------------------


async def _resolve_labels(
    run: SelectRunner, uris: list[str], *, lang: str
) -> dict[str, dict[str, Any]]:
    """Löst Code-URIs zu Label/Identifier/containedInPlace auf (gebatcht)."""
    labels: dict[str, dict[str, Any]] = {}
    for start in range(0, len(uris), 50):
        values = " ".join(f"<{_safe_uri(u)}>" for u in uris[start : start + 50])
        query = f"""{_PREFIXES}
SELECT ?code ?label ?labelLang ?identifier ?place WHERE {{
  VALUES ?code {{ {values} }}
  ?code schema:name ?label .
  BIND(LANG(?label) AS ?labelLang)
  OPTIONAL {{ ?code schema:identifier ?identifier }}
  OPTIONAL {{ ?code schema:containedInPlace ?place }}
}}
"""
        names: dict[str, dict[str, str]] = {}
        for row in await run(query):
            code = row.get("code", "")
            entry = labels.setdefault(code, {})
            names.setdefault(code, {})[row.get("labelLang", "")] = row.get("label", "")
            if row.get("identifier"):
                entry["identifier"] = row["identifier"]
            if row.get("place"):
                entry["contained_in"] = row["place"]
        for code, cands in names.items():
            labels[code]["label"] = pick_lang(cands, lang)
    return labels


async def get_observations(
    run: SelectRunner,
    cube_uri: str,
    *,
    filters: dict[str, str] | None = None,
    order_desc_by: str | None = None,
    limit: int = 100,
    lang: str = "de",
) -> list[dict[str, Any]]:
    """Liest Observations eines Cubes — MIT aufgelösten Labels (Phase 2).

    Zugriff zwingend über den observationSet-Zwischenschritt (N3). `filters`
    bildet Dimension-URI → Wert ab (URI oder Literal, exakter Match);
    `order_desc_by` sortiert absteigend nach einer Dimensions-URI (z.B. der
    Zeitdimension → «neueste zuerst»). Code-URIs in den Resultaten werden
    intern zu Labels aufgelöst; der Aufrufer sieht nie rohe Codes.
    """
    uri = _safe_uri(cube_uri)
    filter_lines = []
    for dim, value in (filters or {}).items():
        if _SAFE_URI.match(value):
            filter_lines.append(f"    ?obs <{_safe_uri(dim)}> <{_safe_uri(value)}> .")
        else:
            filter_lines.append(f'    ?obs <{_safe_uri(dim)}> "{sparql_escape(value)}" .')
    order_clause = ""
    if order_desc_by:
        filter_lines.append(f"    ?obs <{_safe_uri(order_desc_by)}> ?sortkey .")
        order_clause = " ORDER BY DESC(?sortkey)"
    inner_filters = "\n".join(filter_lines)
    query = f"""{_PREFIXES}
SELECT ?obs ?p ?o WHERE {{
  {{
    SELECT ?obs WHERE {{
      <{uri}> cube:observationSet ?set .
      ?set cube:observation ?obs .
{inner_filters}
    }}{order_clause} LIMIT {int(limit)}
  }}
  ?obs ?p ?o .
}}
"""
    triples = await run(query)

    # Pivot: Triples → eine Zeile je Observation, Dimension-URIs als Kurz-Keys.
    rows_by_obs: dict[str, dict[str, Any]] = {}
    obs_order: list[str] = []
    uri_values: set[str] = set()
    for t in triples:
        obs, pred, obj = t.get("obs", ""), t.get("p", ""), t.get("o", "")
        if pred.endswith("#type") or pred == "https://cube.link/observedBy":
            continue
        if obs not in rows_by_obs:
            rows_by_obs[obs] = {}
            obs_order.append(obs)
        key = pred.rstrip("/").rsplit("/", 1)[-1]
        rows_by_obs[obs][key] = obj
        if obj.startswith("https://ld.admin.ch/") or obj.startswith("http://ld.admin.ch/"):
            uri_values.add(obj)

    labels = await _resolve_labels(run, sorted(uri_values), lang=lang) if uri_values else {}
    return resolve_codes([rows_by_obs[o] for o in obs_order], labels)


# --- Lizenz (N7) ----------------------------------------------------------------


async def get_cube_license(run: SelectRunner, cube_uri: str) -> str:
    """Ermittelt die Lizenz eines Cubes — Cube-Ebene, dann Graph-/Datensatz-Ebene.

    Liefert die Lizenz-URI oder den ehrlichen `LICENSE_UNDECLARED`-Text —
    nie eine stillschweigende «Open-Use»-Annahme.
    """
    uri = _safe_uri(cube_uri)
    query = f"""{_PREFIXES}
SELECT DISTINCT ?license WHERE {{
  {{ <{uri}> dcterms:license|schema:license ?license }}
  UNION
  {{
    GRAPH ?g {{ <{uri}> a cube:Cube }}
    GRAPH ?g {{ ?ds a schema:Dataset ; dcterms:license ?license }}
  }}
}} LIMIT 1
"""
    rows = await run(query)
    if not rows or not rows[0].get("license"):
        return LICENSE_UNDECLARED
    uri = rows[0]["license"]
    return f"Lizenz: {_KNOWN_LICENSES.get(uri, uri)}"
