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
- **Am Token vorbei geht es nicht.** Beide Umwege enden am Agent-Proxy, und
  jeder mit einer eigenen irreführenden Begründung. `api.github.com` ohne
  Zugangsdaten:

  ```
  GitHub access is not enabled for this session. An org admin must connect
  the Claude GitHub App for this organization.
  ```

  Das ist keine Aussage über die Organisation, sondern das, was ohne Token
  kommt. Wer ihr folgt, sucht einen Admin für ein Problem, das keiner hat.
  Die HTML-Seite `github.com/<owner>/<repo>/labels` fällt ebenfalls, aber
  anders:

  ```
  This GitHub API path is not available: sessions are bound to their
  configured repositories. Use repository-scoped endpoints
  (repos/{owner}/{repo}/...).
  ```

  Der Proxy behandelt also auch `github.com` als API-Pfad; die zweite Meldung
  klingt nach einem Scope-Problem und ist doch nur dieselbe Sackgasse. Den
  Token aus der Umgebung in einen curl-Header zu setzen, blockiert der
  Klassifikator. Ob es überhaupt hülfe, ist offen: die Sperre nennt ein
  Nutzerkonto, und ob der Token zu diesem gehört, wurde nie geprüft.
- **Die Sperre gilt nicht dem Dienst, sondern dem Zugangspfad.** Unmittelbar
  nachdem eine Abfrage der Checks eines PR sauber durchlief, meldete die
  Label-Abfrage weiter die Sperre. Von einem blockierten Werkzeug also nicht
  auf «GitHub ist zu» schliessen — und umgekehrt eine gelungene Abfrage nicht
  als Entwarnung für die gesperrte nehmen. Das ist dieselbe Asymmetrie wie
  bei der verschwundenen Codex-Meldung weiter unten.

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

The labels specified are used instead of the default labels.
```

Ohne `labels:` vergibt Dependabot also `dependencies` plus ein Ökosystem-Label
und legt beide selbst an; eine eigene Liste **ersetzt** diesen Satz, und «if
any of these labels is not defined in the repository, it is ignored». Die
Zeile war nicht wirkungslos — sie tauschte einen sich selbst pflegenden
Vorgabesatz gegen eine starre Liste.

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

Ein Codex-Review auf einem PR wird beantwortet oder behoben, nie ignoriert.

### Wenn Codex gar nicht erst hinsieht

Die Zeile oben unterstellt, dass es einen Befund geben *kann*. Das ist nicht
immer so, und man sieht es dem PR nicht an.

Am 21.8.2026 war das Code-Review-Kontingent zwischen 08:41 und 09:48
aufgebraucht — davor echte Reviews, danach in 30 Repos nur noch:

```
You have reached your Codex usage limits for code reviews.
```

Wie lange die Sperre dauerte, geben die Beobachtungen nur als Spanne her. Vier
Zeitpunkte sind belegt: letzter gelungener Review am 21.8. um 08:41, erste
Limit-Meldung um 09:48, letzte beobachtete Limit-Meldung am 22.8. um 11:03,
erste *andere* Meldung am 23.8. um 08:22.

Zwischen erster und letzter Limit-Meldung liegen **25 h 15 min**. Das ist der
Abstand zweier Fehlschläge, nicht die Dauer einer Sperre. Wer ihn Untergrenze
nennt, hat die durchgehende Erschöpfung schon vorausgesetzt, die er belegen
soll: Öffnete sich das Fenster zwischendurch und schloss es sich durch neue
Auslöser wieder, waren es zwei kurze Sperren und nie eine von 25 Stunden.
Untergrenze einer *einzelnen* Sperre sind die 25 h 15 min nur unter genau dieser
Annahme — und die ist unbelegt.

Nach oben trägt die Rechnung dagegen. Die längste mit den Beobachtungen
verträgliche Sperre reicht vom letzten Erfolg um 08:41 bis zur abweichenden
Meldung um 08:22, also **47 h 41 min**; länger kann keine einzelne gewesen sein.
Wer stattdessen ab der ersten Limit-Meldung rechnet, unterschlägt die 67
Minuten, in denen das Kontingent schon weg gewesen sein kann, und nennt die
Spanne zwischen zwei Beobachtungen eine Obergrenze.

Beobachtungspunkte sind keine Messreihe — die 21 Stunden vor der abweichenden
Meldung liefen ganz ohne Codex-Auslöser, dort hat niemand gemessen.

In der Zwischenzeit sind 32 PRs mit formal erfülltem Häkchen gemergt worden,
ohne dass jemand hineingesehen hat, und am 22.8. noch einmal 43.

**Vier** Gründe, warum Codex schweigt, und nur einer davon ist harmlos:

- **Kein Befund** — dann schreibt er einen gewöhnlichen Issue-Kommentar:

  ```
  Codex Review: Didn't find any major issues. Swish!
  ```

  Der Schlusssatz wechselt bei jedem Lauf («Delightful!», «Keep it up!»,
  «More of your lovely PRs please.»); stabil ist nur der Satz davor. Der
  Infokasten, den Codex unter jeden Review setzt, behauptet weiterhin eine
  Reaktion («otherwise it will react with 👍») — am 23.8. kam in sechs Repos
  die Meldung und in keinem die Reaktion. Der Kasten ist keine Quelle.
- **Der PR ist ein Draft** — darauf läuft Codex nicht an.
- **Das Kontingent ist weg** — dann schreibt er die Meldung oben.
- **Für das Repo fehlt eine Environment** — dann schreibt er:

  ```
  To use Codex here, create an environment for this repo.
  ```

Der vierte kam erst zum Vorschein, als der dritte wegfiel, und das ist kein
Zufall: Die Prüfungen liegen hintereinander. Dass es diese Reihenfolge ist und
nicht die umgekehrte, lässt sich an einem einzigen Repo ablesen — in
`swiss-public-data-mcp` bekam PR #54 am 22.8. um 10:56:55 die Kontingent-Meldung
und PR #56 am 23.8. um 08:22:20 die Environment-Meldung. Läge die
Environment-Prüfung vorn, hätte #54 sie schon am Vortag gesehen; die Environment
fehlte ja bereits. Zwei Meldungen aus demselben Repo schlagen hier jede
Vermutung über die Reihenfolge.

Praktisch heisst das: **Eine verschwundene Limit-Meldung ist keine Entwarnung.**
Sie kann bedeuten, dass das Kontingent wieder da ist — und dass jetzt etwas
anderes den Review verhindert. Belegt ist eine Prüfung erst durch ein
Review-Objekt **oder** eine Befundlos-Meldung. Wer nur das Objekt gelten lässt,
zählt jeden befundlosen Review als ungeprüft — und baut sich denselben Fehlalarm
ein, den dieser Abschnitt verhindern soll, nur in die andere Richtung.

«Kein Kommentar» heisst also nicht «geprüft und sauber». Unterscheiden lässt es
sich an der Form: Ein Review **mit** Befund ist ein Review-Objekt
(«💡 Codex Review», mit Commit-Angabe); ein Review **ohne** Befund und die
beiden Ausfallmeldungen — Kontingent wie Environment — sind gewöhnliche
Issue-Kommentare und trennen sich nur im Text. Beim Draft gibt es überhaupt
nichts, weil Codex nicht anläuft; ein kommentarloser Draft ist deshalb kein
Beleg, sondern ein nicht durchgeführter Test.

Das sind verschiedene Abfragen — `get_reviews` fürs Objekt, `get_comments` für
alles andere; wer nur eine nimmt, übersieht den Rest. Genau so ist die
Limit-Meldung zuerst durchgerutscht.

Der Kommentarzähler allein reicht ohnehin nicht: `comments: 1` kann die
Befundlos-, die Kontingent- **oder** die Environment-Meldung sein — drei
gegensätzliche Bedeutungen unter derselben Zahl. Den Text lesen, nicht die Zahl.
Und einen unbekannten vierten Text wörtlich zitieren, statt ihn in eine der
bekannten Schubladen zu zwingen: Dieser Abschnitt musste schon einmal von drei
auf vier Gründe wachsen, und die 👍-Reaktion stand hier zwei Fassungen lang als
Tatsache.

Und ein befundloser Lauf ist kein Freispruch. Am 23.8. lief derselbe Text durch
42 Reviews: 36 meldeten denselben P2-Befund, 6 die Befundlos-Meldung — gleiche
Eingabe, gegenteiliges Urteil, alles in denselben neun Minuten. Ein sauberer
Lauf sagt damit etwas über den Lauf, nicht über den Text. Wer sein Häkchen
daran hängt, hängt es an einen Münzwurf.

### Und dann wechselt die Quelle ihr Format

Am 29.8.2026 hat Codex das Meldeformat umgestellt. Statt Einzelmeldungen führt
er jetzt **einen** Kommentar je PR und schreibt ihn fort — eine Zeile je Review,
mit Status und Commit. Wörtlich an `swiss-environment-mcp#104`, Head `5147312`,
um 06:50:52:

```
| 📝 **Code Review** | 🔄 **Running** since 2026-08-29T06:50:41Z | `5147312` | Draft marked ready |
```

und um 06:52:29 derselbe Kommentar, dieselbe `id`, dasselbe `created_at`:

```
| 📝 **Code Review** | ✅ **Completed** 2026-08-29T06:52:26.201705Z | `5147312` | Draft marked ready |
```

Der Infokasten sagt neu: «Codex reacts with 👀 while any review is running,
comments if it has suggestions, and reacts with 👍 once all reviews finish with
no findings.» Damit fällt die Befundlos-Meldung als Text weg — ein sauberer Lauf
hinterlässt nur noch eine Reaktion. Wer weiter auf «Didn't find any major
issues» wartet, wartet auf einen Satz, den niemand mehr schreibt.

Drei Folgen, und die dritte ist die unangenehme:

- **`created_at` ist kein Alter mehr.** Der Kommentar wird bearbeitet, nicht neu
  geschrieben; sein Erstelldatum steht still, während sein Inhalt weiterläuft.
  Ein Frischefilter über `created_at` wirft nach dem nächsten Push genau das
  Signal weg, auf das er wartet.
- **Die Commit-Spalte ist das bessere Signal.** Sie nennt den geprüften Stand
  selbst — genauer als jeder Zeitstempel, und in beide Richtungen.
- **«Running» ist kein Ausfall.** Das Gate hier hat den neuen Kommentar als
  unbekannten Text eingeordnet und rot gesetzt. Für einen *laufenden* Review ist
  das falsch; richtig wäre gelb. Dass es überhaupt auffiel, ist die Regel oben
  in Funktion: Unbekanntes wird zitiert, nicht einsortiert.

Und der Wechsel `Running` → `Completed` ist eine **Bearbeitung**. Ein Workflow
auf `issue_comment: [created]` sieht ihn nie.

Der Zähler taugt damit noch weniger als vorher: `comments: 1` ist heute meist
die Summary — und die kann laufend, fertig oder für einen ganz anderen Commit
sein.

Portfolio-weit nachsehen:

```
search_pull_requests: user:malkreide commenter:chatgpt-codex-connector[bot] updated:>=<Datum>
```

Findet nur, wo er *kommentiert* hat. Repos ohne PR-Aktivität tauchen nicht auf
— das ist kein Beleg, dass dort geprüft wurde.

Zweiter Weg, den Prüfer zu verlieren, ganz ohne Kontingentproblem: zu schnell
mergen. Am 21./22.8. lagen zwischen «ready for review» und Merge mehrfach drei
bis fünf Sekunden. Codex wird beim Umschalten von Draft auf ready ausgelöst und
braucht danach Zeit; wer sofort mergt, hat das Häkchen gesetzt und den Review
nicht abgewartet.

Das Kontingent hängt am Konto, nicht am Repo, und Code-Reviews haben einen
eigenen Topf — nur GitHub-getriggerte Reviews zählen hinein. ChatGPT-Pläne
fahren ein rollendes Fünf-Stunden-Fenster plus Wochenlimits; welches greift,
steht im Codex-Dashboard. Welches hier griff, ist **offen**. Die Lücke oben
schliesst das Fünf-Stunden-Fenster nicht aus: Es kann sich zwischendurch
geöffnet und durch neue Auslöser wieder erschöpft haben. Das auszuschliessen
bräuchte den Nachweis, dass in der ganzen Spanne kein einziger Review durchlief
— den gibt es nicht, weil nur Fehlschläge beobachtet wurden. Eine lange Reihe
von Fehlschlägen belegt eine lange Reihe von Fehlschlägen, nicht ihre Ursache.

Zeigt das Dashboard freies Kontingent, während Reviews weiter scheitern, ist
das ein bekannter Fehler bei mehreren verbundenen Konten — dann den
GitHub-Connector in den Codex-Einstellungen trennen und neu verbinden.

Die Environment legt man unter `chatgpt.com/codex/cloud/settings/environments`
an, und zwar **je Repo**. Die Meldung sagt es selbst («for this repo»), und am
23.8. war es genau so: In `swiss-public-data-mcp` fehlte sie, dort kam kein
Review; in den übrigen Repos lief Codex am selben Morgen durch. Eine
Environment fürs Konto genügt also nicht — wer eine anlegt und den Rest für
erledigt hält, mergt weiter Ungeprüftes.

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

**ruff:** genau eine Quelle — `ruff==0.16.3` im `[dev]`-Extra von
`pyproject.toml`. Ein Install des Extras reicht also, lokal wie in der CI.
Keine zweite Version in die Workflows schreiben: ein solcher Schritt läuft
nach dem Install und überstimmt den Pin still — er stand hier an zwei Stellen,
in den Jobs `test` und `lint` (`test_dependencies.py` hält beides fest). Eine
`.pre-commit-config.yaml` gibt es nicht. Vor dem Lauf `ruff --version` prüfen:
ein älteres ruff früher im `PATH` schlägt den Pin, ohne etwas zu melden.

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

**Ein drittes PR-Gate, und es prüft keinen Code:** `codex-gate.yml`. Es setzt
einen Commit-Status `codex-gate` auf den PR-Head und wird nur grün, wenn Codex
diesen Head nachweislich geprüft hat — Review-Objekt ODER Befundlos-Meldung.
Kontingent- und Environment-Meldung lassen es **rot**: Beide heissen
ausdrücklich «nicht geprüft», und ohne Handlung ändert sich daran nichts. Seit
dem Formatwechsel vom 29.8. zählt zusätzlich die Summary-Tabelle: `Completed`
für den Head ist ein Nachweis, `Running` hält auf **gelb**, ein drittes
Statuswort wird zitiert statt geraten. Ihre Frische hängt an der Commit-Spalte,
nicht an `created_at` — Gründe oben. Mehrere Zeilen zählen einzeln: Solange eine
läuft, ist der Head nicht fertig geprüft. Zusammengeführt wird nach Schwere: Was
ausdrücklich «nicht geprüft» sagt, schlägt jede Fertigmeldung. Ein Draft steht
auf **gelb** — er ist ohnehin nicht mergebar, und ein Repo, in dem jeder Draft
ein rotes Kreuz trägt, bringt seinen Leuten bei, rote Kreuze zu übersehen. Das
Gate hat sich diese Lektion selbst erteilt: Seine ersten beiden Läufe färbten
zwei frische Draft-PRs rot.

Bewusst kein Timer. Ein Gate, das nach N Minuten von selbst grün wird,
behauptet eine Prüfung, die es nicht gesehen hat — am 21./22.8. war das
Kontingent über eine Spanne von mindestens 25 h weg, ein Timer wäre die ganze
Zeit durchgelaufen. Die Wartezeit ist die Folge, nicht die Einstellung: Solange
kein Signal da ist, bleibt der Status rot.

Die Einordnung steht in `scripts/classify_codex_review.py` neben ihrem Test,
nicht im YAML — aus demselben Grund wie bei `classify_live_run.py`.

**Das Gate wirkt nur mit Branch Protection.** Der Kontext `codex-gate` muss auf
`main` als *required status check* stehen, samt «Do not allow bypassing the
above settings». Ohne das bleibt der Merge-Button klickbar. Am 28.8.2026 war
`main` hier `protected: false` — es gab überhaupt keinen Required Check, die
sechs grünen Häkchen waren informativ. Wer die Protection wegnimmt, nimmt
das Gate weg, ohne dass eine Datei sich ändert.

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
