# CLAUDE.md

## Teil 1 — Konventionen (portfolio-weit)

### Vor der Arbeit

Klon-Aktualität prüfen — Standard-Branch ermitteln, nicht `main` annehmen:

```bash
B=$(git ls-remote --symref origin HEAD | sed -n 's|^ref: refs/heads/\([^[:space:]]*\).*|\1|p')
git fetch origin "${B:?Standard-Branch nicht ermittelbar}" &&
  git rev-list --count HEAD..FETCH_HEAD
```

Drei Server im Portfolio heissen ihren Standard-Branch `master`
(`openlex-mcp`, `swiss-courts-mcp`, `swisstopo-mcp`); dort scheitert ein fest
verdrahtetes `origin/main` mit «couldn't find remote ref main». Wer das für ein
Netzproblem hält, arbeitet weiter auf genau dem veralteten Klon, vor dem dieser
Absatz warnt. Den `:?`-Schutz nicht weglassen: Bei leerem `B` fetcht git still
den Remote-HEAD und endet mit 0.

Ein veralteter Klon erzeugt eine rote CI, deren Ursache nicht im Diff steht.
Am 3.8.2026 zweimal passiert — beide Male fehlten genau die Commits, die
das Gate einführten, an dem der Branch scheiterte.

Gates lokal fahren, mit der GEPINNTEN ruff-Version aus der CI. Eine andere
Version meldet Abweichungen, die niemand verursacht hat.

### Tests

Gegenprobe ist Pflicht. Ein Test, der grün bleibt, wenn man die
Implementierung entfernt, prüft nichts. Jede neue Zusicherung einzeln
neutralisieren und zeigen, dass genau die zugehörigen Tests fallen.

Zwei Fallen, die beide grün blieben:

- Eine Fake-Uhr, die nur beim Schlafen vorrückt, kann eine Zusicherung über
  echte Zeit nicht widerlegen.
- `monkeypatch.setattr(modul.asyncio, "sleep", ...)` greift ins Modul
  `asyncio` selbst und entschärft die Mechanik im ganzen Prozess. Patche
  einen Modul-Alias (`_sleep = asyncio.sleep`), nicht das fremde Modul.

Handgeschriebene Fixtures kodieren die Annahme des Autors und können sie
nicht widerlegen. Mindestens eine aufgezeichnete Antwort pro externem
Endpunkt, mit Aufnahmedatum.

### Wenn etwas rot ist

Roter Live-Test: erst die Quelle abfragen, dann einordnen. Nicht aus der
Fehlermeldung schliessen. Am 3.8.2026 hiess "nicht gefunden" nicht, dass der
Datensatz weg war, sondern dass die Quelle die Schreibweise ihrer Kopfzeile
gewechselt hatte — vier von sechs Datensätzen produktiv kaputt, alle
Unit-Tests grün.

**Ein 4xx ist kein Nein.** Am 29.8.2026 antwortete `past-publications` in
`swiss-procurement-mcp` auf jede Publikation mit Losen mit HTTP 400. Daraus war
geschlossen worden, die Quelle verweigere diese Auskunft; der Befund stand
datiert im Fixture-Nachweis, ein Test bestätigte ihn, alles blieb grün. Die
Spec desselben Endpunkts führt einen als *optional* deklarierten Parameter
`lotId` — für Publikationen mit Losen ist er Pflicht. Mit ihm antwortet
dieselbe Publikation mit 200. Ein Projekt trug sieben Vorgängerpublikationen,
die der Server als «Quelle nicht erreichbar» wegwarf.

Drei Handgriffe daraus:

- **Die Parameterliste der Spec durchgehen, bevor ein Statuscode eingeordnet
  wird.** «Optional» heisst dort oft «optional für die Mehrheit».
- **Einer deterministischen Absage keinen Wiederholungsrat geben.** «Nicht
  erreichbar, bitte später erneut» ist bei einem 400 falsch und liest sich für
  das Modell wie eine Störung. Den Status mitführen und den fehlenden
  Parameter benennen — den Status, nicht den Antwortkörper.
- **Beide Antworten aufzeichnen, mit und ohne den Parameter.** Eine
  Aufzeichnung nur des Fehlschlags kann nicht zeigen, dass er vermeidbar war;
  dass nur der 400er aufgezeichnet war, ist der Grund, warum der falsche
  Befund nicht auffiel.

**Und ein 403 ist gar keine Auskunft.** Am 29.8.2026 sollten für 42 Repos die
Dependabot-Labels nachgemessen werden. Alle 13 Abfragen des ersten Stapels
kamen zurück als:

```
Failed to find label: API rate limit already exceeded for user ID 8864492.
```

Der gefährliche Teil steht vorn: Das Werkzeug verpackt eine Sperre als
Fund-Fehlschlag. Wer die Zeile überfliegt oder nur auf ein leeres Ergebnis
prüft, zählt 39 Repos als «Label fehlt» und hat seine eigene Erschöpfung
gemessen. Das Limit hängt am Konto, nicht am Repo — derselbe Vormittag hatte
es mit 42 eröffneten und 42 gemergten PRs verbraucht.

Das ist der Absatz darüber, andersherum gelesen: dort war ein 400 eine echte,
wiederholbare Antwort und galt als Störung; hier ist eine Störung als Antwort
verpackt. Entscheidend ist nie der Statuscode, sondern ob die Quelle überhaupt
geantwortet hat.

- **Positivkontrolle im selben Repo.** Ein «nicht gefunden» wird erst dadurch
  zur Messung, dass eine gleichzeitige Abfrage etwas findet.
- **Die Messung entlang der Sperre teilen.** `raw.githubusercontent.com` ist
  ein CDN und nicht die REST-API. Um 11:19:27 UTC lieferte es für
  `register-mcp` HTTP 200, während die Label-Abfrage desselben Repos in
  derselben Minute die Sperre meldete. Alle 42 `dependabot.yml` kamen so
  durch, während die Label-Hälfte stand.
- **Hier stand «Am Token vorbei geht es nicht». Das ist falsch, und es war der
  teuerste Satz dieser Datei.** Am 19.9.2026 nachgemessen: Ein schlichtes
  `curl` auf `api.github.com` geht durch den Agent-Proxy und kommt
  **authentifiziert** heraus. `api.github.com/user` liefert `malkreide`,
  `api.github.com/rate_limit` meldet `core: limit=15000` — das ist kein
  anonymes Kontingent.

  Was der Proxy wirklich tut, ist nicht sperren, sondern **auf die
  konfigurierten Repos begrenzen**. Geprüft und mit 200 beantwortet wurden am
  19.9.:

  ```bash
  curl -sS https://api.github.com/repos/<owner>/<repo>/branches/main
  curl -sS https://api.github.com/repos/<owner>/<repo>/rulesets
  curl -sS https://api.github.com/repos/<owner>/<repo>/labels/<name>
  curl -sS https://api.github.com/rate_limit
  curl -sS https://api.github.com/user
  ```

  **Repo-eigen heisst dabei nicht «geht».** Der Proxy entscheidet über die
  *Route*, das Token über die *Berechtigung* — zwei Schichten, und beide
  können nein sagen. `repos/<owner>/<repo>/branches/main/protection` liegt auf
  einer erlaubten Route und fällt trotzdem:

  ```
  403 Resource not accessible by integration
  ```

  Das ist die Token-Schicht, nicht der Proxy. Die beiden Absagen lassen sich am
  Text auseinanderhalten — «not accessible by integration» kommt von GitHub,
  «sessions are bound to their configured repositories» vom Proxy. Wer sie
  verwechselt, hält eine Berechtigungsgrenze für eine Proxy-Sperre und sucht
  einen Umweg, den es nicht braucht, oder umgekehrt. Aufgedeckt von einem
  Codex-Review auf PR #125 (P2), nachdem hier pauschal «repo-eigene Pfade
  antworten mit 200» gestanden hatte — im selben Commit, der den 403 auf
  `protection` schon dokumentierte.

  Ein Pfad ausserhalb (hier `api.github.com/octocat`) fällt dagegen mit 403 und
  genau der Meldung, die oben der HTML-Seite zugeschrieben war:

  ```
  This GitHub API path is not available: sessions are bound to their
  configured repositories. Use repository-scoped endpoints
  (repos/{owner}/{repo}/...).
  ```

  Sie ist also keine Sackgasse, sondern eine **Wegbeschreibung** — und sie
  stand die ganze Zeit da. Gelesen wurde sie als zweite Variante desselben
  Neins.

  Die andere zitierte Meldung («GitHub access is not enabled for this
  session») kam am 19.9. auf keinem der geprüften Pfade. Ob sich die Umgebung
  geändert hat oder ob damals ein nicht repo-eigener Pfad abgefragt wurde, ist
  nicht mehr feststellbar; als Beschreibung des heutigen Verhaltens taugt sie
  nicht.

  **Was das praktisch ändert:** Fehlt eine Auskunft im MCP-Werkzeug, heisst das
  nicht, dass sie unerreichbar ist. Erst den Pfad direkt probieren. Und die
  `X-RateLimit`-Frage von oben hat damit eine Antwort — `rate_limit` nennt
  Topf, Limit und Reset-Zeitpunkt, statt sie aus Beobachtungszeitpunkten zu
  schätzen.
- **Die Sperre gilt nicht dem Dienst, sondern dem Zugangspfad.** Unmittelbar
  nachdem eine Abfrage der Checks eines PR sauber durchlief, meldete die
  Label-Abfrage weiter die Sperre. Von einem blockierten Werkzeug also nicht
  auf «GitHub ist zu» schliessen — und umgekehrt eine gelungene Abfrage nicht
  als Entwarnung für die gesperrte nehmen.

Wann die Sperre fällt, geben diese Beobachtungen nicht her. Die Meldung nennt
keinen Zeitpunkt, und die `X-RateLimit`-Kopfzeilen sind hinter dem Proxy nicht
zu sehen. Belegt sind drei gesperrte Zeitpunkte — 11:14, 11:16 und 11:19 UTC.
Wer daraus eine Dauer macht, hat sie erfunden.

**Dieselbe Falle bei einer Konfigurationsoption: die Vorgabe lesen, bevor man
einen Schlüssel für wirkungslos hält.** Am 29.8.2026 fielen die
`labels:`-Zeilen aus den `dependabot.yml` des Portfolios, begründet mit
«Dependabot legt Labels nicht an». Eine Messung danach zeigte, dass
`dependencies` in 36 von 42 Repos sehr wohl existiert, 35 davon mit GitHubs
Standardbeschreibung. Das las sich zuerst wie ein Beleg, dass die Aktion
falsch war.

Die Optionsreferenz kehrt es um:

```
Dependabot creates these default labels automatically, as necessary in
your repository.

If you define more than one package manager, an additional label for the
ecosystem or language is added to each pull request.

The labels specified are used instead of the default labels.
```

Ohne `labels:` vergibt Dependabot also `dependencies` — und, sobald mehr als
ein Paketmanager deklariert ist, zusätzlich ein Ökosystem-Label — und legt sie
selbst an; eine eigene Liste **ersetzt** diesen Satz, und «if any of these
labels is not defined in the repository, it is ignored». Die Zeile war nicht
wirkungslos — sie tauschte einen sich selbst pflegenden Vorgabesatz gegen eine
starre Liste.

**Die Bedingung nicht weglassen.** Bei nur einem Paketmanager steht das
Ökosystem-Label gar nicht zu; wer es dort trotzdem erwartet, schreibt genau
den Fehlbefund auf, gegen den dieser Abschnitt geschrieben ist — der Abschnitt
liefe an sich selbst vorbei. Im Portfolio deklariert jede `dependabot.yml`
zwei (`pip` und `github-actions`), die Bedingung ist hier also überall
erfüllt; anderswo nicht unbedingt. Aufgefallen ist die fehlende Bedingung
nicht beim Schreiben, sondern durch einen Codex-Review auf
`swiss-environment-mcp` PR #113 — vierzehn Sekunden vor dem Merge desselben
PR.

Was das kostet, ist an `openlex-mcp` gemessen: zwei Ökosysteme deklariert,
also stünden `dependencies` **und** ein Ökosystem-Label zu; vorhanden ist nur
das erste, `github-actions` und `github_actions` fehlen beide (Kontrolle `bug`
vorhanden). `register-mcp` ist die Gegenprobe: dort existieren alle vier
deklarierten Namen mit handgeschriebener Beschreibung, die Liste ist gewollt
und vollständig.

**Dreimal falsch eingeordnet, in drei Richtungen.** Erst die Zeile für bloss
wirkungslos gehalten. Dann die gefundenen Labels für einen Widerspruch. Dann,
auf denselben Fund gestützt, einen richtigen PR geschlossen mit dem Argument,
das Label existiere ja — obwohl es existiert, *weil* die Vorgabe es anlegt.
Der dritte Fehler ist der teuerste, weil er wie eine Messung aussah.

Was die Messung **nicht** hergibt: wer die 36 Labels angelegt hat. Die
Referenz sagt, Dependabot tue es; die Objekt-IDs liegen aber so dicht
beieinander, dass sie eher aus einem Stapellauf stammen. Beides passt zum
Befund, keines ist belegt — die Herkunft blieb ungemessen.

Beim Aufräumen gilt deshalb dieselbe Frage wie bei `lotId`: Was ist die
*Vorgabe*, wenn man das Ding weglässt — nicht bloss, ob der aktuelle Wert
etwas bewirkt.

**`results[0]` ist nur so verlässlich wie die Zusicherung danach.** Pinnt die
Abfrage einen bekannten Datensatz, ist der erste Treffer eine Drift-Wache und
in Ordnung. Hängt die Zusicherung dagegen davon ab, *welche* Variante die
Quelle heute zuoberst hat, prüft der Test den Tag: am 25.8.2026 rot, weil die
neueste Zürcher Publikation zufällig Lose hatte, am 26.8. grün, ohne dass sich
etwas geändert hätte. Den Fall gezielt wählen und beide Zweige fahren.

PR ohne jeden Check ist selten ein Repo ohne CI, meistens ein
Merge-Konflikt: GitHub berechnet dafür keinen Merge-Commit und startet nichts.

**Bei einem blockierten PR nennt der Merge-Versuch den Blocker, jede Ableitung
rät.** `mergeable_state: blocked` bei grüner CI heisst: ein required Kontext
fehlt oder steht nicht auf grün. Welcher, sagt die Einstellung — und die sperrt
der Agent-Proxy mit HTTP 403, ein MCP-Werkzeug dafür gibt es nicht. Der Ausweg
ist nicht Indizienarbeit, sondern ein Merge-Versuch über die API:

```
PUT /repos/<owner>/<repo>/pulls/<n>/merge
405 Required status check "Codex hat diesen Head geprueft" is expected.
```

Der Name steht dort wörtlich so, wie er in der Branch Protection eingetragen
ist. Scheitert der Versuch, kostet er nichts.

Am 24./25.9.2026 über drei Repos vermessen, nachdem ein Gate-Workflow entfernt
worden war und seinen required Kontext ohne Berichterstatter zurückliess:

| Repo | eingetragener Kontext | Art |
|---|---|---|
| `register-mcp` | `Codex hat den PR angesehen` | Check-Run |
| `srgssr-mcp` | `review-abgeschlossen` | Check-Run |
| `fedlex-mcp` | `Codex hat diesen Head geprueft` | Check-Run |

**Warum Ableiten hier systematisch fehlgeht.** GitHub nimmt als Check-Run-Name
den **Job**-Namen, nicht den des Workflows. Zwei der drei Kontexte enthalten die
Zeichenfolge «codex-gate» nicht, obwohl sie aus `codex-gate.yml` stammen; wer in
den Einstellungen danach sucht, findet nichts und hält die Regel für abwesend.
Trug der Job kein `name:`, nimmt GitHub die Job-ID — daher `review-abgeschlossen`.

Zwei Fehlschlüsse sind dabei belegt, beide aus **einer** Beobachtung gezogen:

- Aus einem Commit-Status auf den required Kontext geschlossen. In `fedlex-mcp`
  stand der Status `codex-gate` auf dem Head auf `success` und blockierte
  nichts, während der fehlende Check-Run den Merge hielt. Am Kontroll-PR waren
  beide rot — dort ist nicht zu unterscheiden, welcher von beiden eingetragen
  ist. Genommen wurde der auffälligere.
- Aus einer Check-Run-Liste auf den required Kontext geschlossen. Die Liste
  zeigt, was **berichtet** wurde; eingetragen sein kann ein Name, der gerade
  gar nicht erscheint. Genau das ist der Fall, um den es geht.

**Ein Vorbehalt, der zur Methode gehört:** Die Absage nennt immer nur den
**ersten** fehlenden Kontext. Ist ein zweiter eingetragen, zeigt ihn erst der
nächste Versuch. Nach jeder Änderung an der Einstellung also erneut versuchen,
bis der Merge durchgeht oder ein neuer Name fällt.

Die Kosten der Ableitung sind gemessen: ein Arbeitstag, an dem der PR-Text den
falschen Namen trug und in den Einstellungen nach einer Zeichenfolge gesucht
wurde, die dort nicht steht.

### Wenn zwei Agenten dasselbe tun

Vor dem Anlegen eines Branches mit vorgegebenem Namen prüfen, ob es ihn schon
gibt:

```bash
git ls-remote --heads origin claude/<name> | wc -l
```

Steht dort `1`, arbeitet jemand anderes daran — mit Schreibrecht auf denselben
Ref.

Ein PR mit leerem Diff wird geschlossen, nicht gemergt. Der Test ist
`get_files` auf dem PR: kommt `[]` zurück, ändert er nichts. Ein grüner Check
sagt dazu nichts — die CI prüft den Head, nicht die Differenz zur Basis.

Am 21.8.2026 liefen zwei Sessions dieselbe Aufgabe über 45 Repos, auf den
Branches `claude/codex-review-audit-templates-9sn6mx` und
`claude/codex-review-audit-7ioh56`. Wo die eine zuerst nach `main` kam, wurde
`main` in den Branch der anderen gemergt und der add/add-Konflikt zugunsten
von `main` aufgelöst. Übrig blieben 14 PRs, die durch sämtliche Gates grün
liefen und nichts enthielten; sie wurden gemergt und hinterliessen leere
Merge-Commits. Mit den zwei Folge-PRs, die aus demselben Grund gegenstandslos
waren, waren 16 der 59 PRs jenes Tages reine Reibung.

Dieselbe Klasse wie der handgeschriebene Stub, der denselben Feldnamen annahm
wie der Code: Nichts ist rot, weil nichts geprüft wird, worauf es ankommt.

## Teil 2 — dieses Repo

**ruff:** genau eine Quelle — der exakte Pin im `[dev]`-Extra von
`pyproject.toml`. Ein Install des Extras reicht also, lokal wie in der CI.
Die Nummer steht hier bewusst **nicht**: Sie stand es, und der Abschnitt, der
«genau eine Quelle» verspricht, war damit selbst die zweite. Am 18.9.2026 nannte
er `0.16.3`, während `pyproject.toml` nach zwei Dependabot-Bumps auf `0.16.5`
stand — ausgerechnet der Absatz, der vor ruff-Versionsdrift warnt, war
abgedriftet. Wer die aktuelle Zahl braucht, liest sie dort:

```bash
grep 'ruff==' pyproject.toml
```

Keine zweite Version in die Workflows schreiben: ein solcher Schritt läuft
nach dem Install und überstimmt den Pin still — er stand hier an zwei Stellen,
in den Jobs `test` und `lint` (`test_dependencies.py` hält beides fest). Eine
`.pre-commit-config.yaml` gibt es nicht.

**Und nicht das `ruff` aus dem `PATH` nehmen.** Ein älteres früher im `PATH`
schlägt den Pin, ohne etwas zu melden. `ruff --version` zu prüfen reicht dafür
nicht — es sagt, welches gewinnt, aber nicht, dass das falsche gewinnt. Den
Interpreter entscheiden lassen; in der CI gibt es nur das eine ruff, lokal
nicht, deshalb steht dort `ruff` und hier `python -m ruff`:

```bash
python -m ruff --version      # muss die Zahl aus pyproject.toml sein
python -m ruff check src/ tests/ scripts/
```

Am 18.9.2026 lag in dieser Umgebung `ruff 0.15.8` vor dem damals gepinnten
`0.16.4`; `ruff format --check` meldete prompt eine Abweichung, die mit dem
richtigen Binary verschwand. Auch der Installationsausgabe nicht glauben:
`pip install -e ".[dev]"` lud sichtbar `ruff-0.16.5` herunter und schrieb in
dieselbe Zusammenfassung `ruff-0.16.4`. Gemessen wird mit
`python -m ruff --version`, nicht mit dem, was pip behauptet.

**Gates, wörtlich aus der CI** (Job `test`, dazu `lint` mit denselben zwei
ruff-Schritten plus dem Versions-Sync):

```bash
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
python -m py_compile src/swiss_environment_mcp/server.py src/swiss_environment_mcp/api_client.py
python -c "from swiss_environment_mcp.server import mcp; print('Import OK')"
python scripts/tool_snapshot.py check     # PYTHONPATH=src
pytest -m "not live" -v                   # PYTHONPATH=src
python scripts/check_version_sync.py
```

**Weitere Gates hängen an jedem PR, ausserhalb von `ci.yml`:**

- `security.yml` — gitleaks über History *und* Working Tree, Konfig
  `.gitleaks.toml`. Läuft immer.
- `image-size.yml` — baut das Image und bricht über einem Ceiling von
  **350 MB** ab (Audit SCALE-004). Läuft **nur**, wenn `Dockerfile`,
  `pyproject.toml` oder `src/**` im Diff sind.

### Die Required-Liste, direkt gelesen

**Sie ist abfragbar, und zwar die ganze Zeit gewesen.** Nicht über
`branches/main/protection` — das antwortet mit 403 «Resource not accessible by
integration», eine Grenze des App-Tokens — sondern über die **Rulesets**, und
moderne Branch Protection ist hier genau das:

```bash
curl -sS https://api.github.com/repos/<owner>/<repo>/rulesets
curl -sS https://api.github.com/repos/<owner>/<repo>/rulesets/<id>
```

Stand 19.9.2026 laufen hier zwei, beide `enforcement: active`:

| Ruleset | gilt für | Regeln |
|---|---|---|
| `main` | `refs/heads/main` | `deletion`, `non_fast_forward`, required status checks (Liste unten) |
| `codex-gate` | `~ALL` | `deletion`, `non_fast_forward` — **keine** Status-Checks |

Required auf `main` waren am 19.9.2026 sieben Kontexte:

```
codex-gate                  ← zu entfernen, der Workflow ist weg
codex-gate: Status setzen   ← zu entfernen, der Workflow ist weg
gitleaks
lint
test (3.11)
test (3.12)
test (3.13)
```

**Die zwei ersten Kontexte hängen jetzt in der Luft.** Mit dem Workflow ist
weg, was sie berichtet; ein required Kontext ohne Berichterstatter hält jeden
PR auf. Sie gehören aus dem Ruleset `main` gestrichen — eine Einstellung, die
der Agent-Proxy mit HTTP 403 sperrt und die deshalb nur ein Mensch vornehmen
kann.

**Das Ruleset `codex-gate` selbst darf dabei NICHT weg.** Es trägt trotz
seines Namens keinen Status-Check, sondern `non_fast_forward` auf `~ALL` —
den Force-Push-Stopp für sämtliche Branches. Wer beim Aufräumen dem Namen
folgt statt dem Inhalt, entfernt den Schutz und merkt es erst, wenn jemand
Historie überschreibt. Zu streichen sind die zwei **Kontexte** im Ruleset
`main`, nicht das gleichnamige Ruleset.

**Vier Dinge, die daraus folgen:**

- **Ein Kontext im Ruleset und der Name des Jobs, der ihn setzt, sind zwei
  Dinge.** Wer den Jobnamen ändert, ohne das Ruleset mitzuziehen, hinterlässt
  einen Kontext, der nie wieder berichtet — genau der Zustand, in dem die
  zwei Zeilen oben jetzt stehen.
- **`image-size` ist nicht required.** Ein Doku-PR wird davon nicht gehalten,
  und das ist jetzt abgelesen statt erschlossen.
- **Es gibt keine `pull_request`-Regel**, also keine Genehmigungspflicht.
- **Der Force-Push-Stopp ist `non_fast_forward` im Ruleset `~ALL`.** Daher
  melden sämtliche Branches `protected: true`. Verwirrend ist nur der Name:
  Das Ruleset heisst `codex-gate` und enthält gerade **keinen** Status-Check;
  die Gate-Kontexte liegen im Ruleset `main`.

**Und die Lehre ist die unangenehme.** Dieser Abschnitt hat drei PRs lang
behauptet, die Liste sei nicht abzulesen — geschlossen daraus, dass das
MCP-Werkzeug den Endpunkt nicht anbietet. Das ist derselbe Fehler wie «ein 403
ist gar keine Auskunft» in Teil 1, nur in der Variante «ein fehlendes Werkzeug
ist keine Aussage über die Quelle». Der indirekte Weg oben hat am Ende das
richtige Ergebnis gebracht, zweimal falsch abgebogen und mehrere Stunden und
drei Review-Runden gekostet. Zuerst fragen, ob die Quelle direkt antwortet.

**Und dabei ist noch etwas anderes passiert.** Seit derselben Änderung melden
*sämtliche* Branches `protected: true`, nicht nur `main`; am Vormittag standen
die `claude/*`-Branches noch auf `false`. Das Ruleset greift also breiter als
`main`.

**Was es dort erzwingt, stand hier als ungemessen — und ist es seit dem
19.9.2026 nicht mehr.** Der Fall kam von selbst: #124 wurde gemergt, während
ein Korrektur-Commit noch entstand, der damit eine neue Basis brauchte. Der
übliche Rebase endete an der Sperre:

```
remote: - Cannot force-push to this branch
```

Ein *normaler* Push auf denselben Branch lief unmittelbar davor und danach
durch. Verboten ist also nicht das Schreiben, sondern das Umschreiben.

**Die Regel dahinter steht inzwischen namentlich fest** (siehe «Die
Required-Liste, direkt gelesen»): Es ist `non_fast_forward` im Ruleset mit dem
Ziel `~ALL`. Daher auch das `protected: true` auf jedem Branch — dort steckt
kein einziger Status-Check, nur `deletion` und `non_fast_forward`. Zwei
Handgriffe daraus:

- **Auf einem Arbeitsbranch dieses Repos ist der Rebase keine Option mehr.**
  Basis nachziehen heisst hier `git merge origin/main`, auch auf dem eigenen
  Branch — der Merge-Commit hält den Branch vorwärts-kompatibel und kommt ohne
  Force-Push aus.
- **Wer die Sperre für ein Netzproblem hält, verliert den Commit.** Die
  Meldung nennt eine Regelverletzung (`GH013`), keinen Übertragungsfehler; ein
  Wiederholungsversuch mit Backoff scheitert beliebig oft gleich.

Der Pfadfilter ist die Falle: Auf einem reinen Doku-PR fehlt dieser Check in
der Liste, und das ist der Normalfall, nicht das Symptom aus Teil 1. Erst
wenn *gar kein* Check läuft, gilt dort der Merge-Konflikt-Verdacht. Beide
brauchen Docker bzw. gitleaks und sind damit die zwei Gates, die sich nicht
so nebenbei lokal nachfahren lassen.

Vor dem Merge-Konflikt-Verdacht steht aber noch eine billigere Erklärung: Alle
drei PR-Gates filtern auf `branches: [main]` (`ci.yml`, `security.yml`,
`image-size.yml`). Ein PR gegen eine andere Basis läuft völlig ungeprüft — er
ist nicht grün, weil nichts zu beanstanden war, sondern weil nichts gefragt
wurde. Also erst die Basis prüfen, dann den Merge-Konflikt vermuten.

`draft-release.yml` ist kein Gate — nur `workflow_dispatch`.

**Ein Workflow, der nicht parst, wird nicht rot — er faellt aus.** GitHub
startet ihn gar nicht, es entsteht kein Check-Run, und in der Liste des PR
fehlt er einfach; nach Teil 1 sucht man dann zuerst den Merge-Konflikt. Am
18.9.2026 ist genau das um Haaresbreite passiert: `name: codex-gate: Status
setzen` ist ungueltiges YAML (unquotierter Skalar mit «: »), und geprueft hat
es im Repo nichts — `test_dependencies.py` liest die Workflows als *Text*.
Seither hält `tests/test_workflows.py` beide Halften fest: dass jede Datei
parst, und dass sie `on:` und `jobs` trägt. Das zweite ist nicht Zierde — eine
geleerte Datei parst (`yaml.safe_load("")` ist `None`) und käme sonst durch.

Dafür steht `pyyaml` im `[dev]`-Extra, als Spanne und nicht exakt gepinnt: Es
entscheidet, ob gültiges YAML parst, und daran ändert ein Minor-Update nichts.

**Den `on:`-Block nicht über `safe_load` suchen — in keiner der beiden
Richtungen.** PyYAML ist YAML **1.1**, dort wird das blanke `on:` zum Boolean
`True`; die Schlüssel von `ci.yml` sind `['name', True, 'jobs']`. Wer auf
`"on"` prüft, baut sich also einen Fehlalarm auf jeden Workflow. Die
naheliegende Gegenrichtung ist aber die gefährliche: `on:`, `true:` und `yes:`
landen alle auf demselben Schlüssel `True`, `1:` landet auf `1`, und
`1 == True` ist in Python wahr. Ein Workflow mit `true:` statt `on:` hat für
GitHub **gar keinen Auslöser** und läuft nie — eine Prüfung auf `True` bliebe
grün, also blind für genau das lautlose Verschwinden, um das es hier geht.
Aufgedeckt von einem Codex-Review auf PR #118 (P2), nachdem die
Fehlalarm-Richtung schon dokumentiert war.

Gelesen wird deshalb die **geschriebene Form** statt des aufgelösten Werts:
`yaml.compose` hält beim Knotenbaum an, wo ein Schlüssel-Skalar seinen Text
noch trägt (`'on'`, `'true'`, `'1'`). `oberste_schluessel()` in
`tests/test_workflows.py` macht genau das.

Die Matrix setzt kein `fail-fast: false`: Eine rote 3.11 bricht 3.12 und 3.13
ab, bevor sie etwas sagen.

Es gibt kein Coverage-Gate. Kein `include` unter `[tool.ruff]` setzen — der
Umfang sind die drei Pfade im Gate-Befehl selbst. Wer ihn prüfen will, zählt
nach statt hier abzulesen: `ruff check src/ tests/ scripts/ --show-files | wc -l`.
`ruff format` meldet dabei eine Datei mehr als `ruff check`, weil 0.16 auch
Markdown formatiert und damit `tests/fixtures/PROVENANCE.md` mitnimmt — zwei
Zahlen, kein Fehler.

**Fixtures: vorhanden, 20 Stück plus `tests/fixtures/PROVENANCE.md`** mit
Aufnahmedatum und dem Grund für den Schnitt — eine Antwort je *Abfrage*, nicht
je Endpunkt, weil fast alles über denselben SPARQL-Endpunkt läuft. Neu
aufzeichnen mit `PYTHONPATH=src python scripts/record_fixtures.py`.

**Live-Tests:** `.github/workflows/live-tests.yml`, nächtlich per Cron
(`0 4 * * *`) plus `workflow_dispatch`. Sie sind hier also nicht bloss per
`-m "not live"` ausgeschlossen. Der Lauf wird nicht am Exit-Code gemessen,
sondern von `scripts/classify_live_run.py` in `clear` / `finding` / `unknown`
eingeordnet — ein Lauf, in dem alles übersprungen wurde, gilt nicht als
Erfolg, und nur ein `finding` öffnet ein Issue. `unknown` schliesst keines.
`schedule` greift nur auf dem Default-Branch: Eine Änderung an Kadenz oder
Workflow ist auf einem Branch wirkungslos und wird erst nach dem Merge scharf.
Vorher von Hand per `workflow_dispatch` prüfen.
