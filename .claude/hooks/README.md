# SessionStart-Hook: Klon-Aktualitätsprüfung

`session-start.sh` meldet beim Sessionstart, wie viele Commits der
ausgecheckte Stand hinter `origin/<Default-Branch>` liegt. Liegt er nicht
zurück, gibt der Hook nichts aus.

## Grund

Ein veralteter Klon hat am 3.8.2026 **zweimal** eine rote CI erzeugt, deren
Ursache nicht im Diff stand — die fehlenden Commits waren jeweils genau die,
die das Gate einführten, an dem der Branch scheiterte. Man sucht den Fehler
dann in den geänderten Dateien, und dort ist er nicht.

Die Prüfung kostet eine Sekunde und ersetzt eine Fehlersuche in den falschen
Dateien. Sie automatisiert den ersten Absatz von `CLAUDE.md`
(«Vor der Arbeit»), damit er nicht davon abhängt, dass jemand daran denkt.

## Zusicherungen

Nach Wichtigkeit geordnet — die erste schlägt alle anderen.

1. **Der Hook blockiert die Session nie.** Kein Netz, kein Remote `origin`,
   kein Git-Repo, detached HEAD, fehlende Credentials, flatterndes DNS: jeder
   dieser Fälle endet still mit Exit 0. Ein Hook, der bei Netzproblemen die
   Arbeit anhält, wird nach dem zweiten Mal abgeschaltet und schützt danach
   gar nichts.

   Umgesetzt durch: bewusst **kein** `set -e`/`set -u` (ein einziges
   unerwartet scheiterndes Kommando würde den Hook sonst mit != 0 beenden),
   jeder Ausstieg ein explizites `exit 0`, `GIT_TERMINAL_PROMPT=0` und
   `BatchMode=yes` gegen interaktive Nachfragen.

2. **Kurzes Timeout auf die Netzaufrufe.** 5 Sekunden als **Gesamtbudget**
   über alle Netzaufrufe zusammen (`timeout -k 1` auf die jeweilige Restzeit,
   dazu `ConnectTimeout`), überschreibbar über `CLAUDE_STALE_CLONE_TIMEOUT`.
   Gesamt und nicht pro Aufruf, weil ein Host, der die Verbindung annimmt und
   dann schweigt, sonst zweimal in die Schranke läuft — gemessen 10.0 s
   gegenüber 5.0 s mit Gesamtbudget. Darunter liegt als zweites Netz das
   `"timeout": 15` in `settings.json`, mit dem die Harness einen hängenden
   Hook selbst abbricht. Fehlt `timeout` (macOS ohne coreutils), greifen
   `ConnectTimeout` und die Harness-Schranke.

3. **Ausgabe nur, wenn tatsächlich Commits fehlen.** Bei 0 schweigt er. Ein
   Hook, der bei jedem Start etwas sagt, wird nach einer Woche überlesen.

4. **Der Default-Branch wird ermittelt, nicht angenommen.** Über
   `git ls-remote --symref origin HEAD`, mit der lokalen
   `refs/remotes/origin/HEAD` als Rückfallebene. Drei Server im Portfolio
   nennen ihren Default-Branch `master` (`openlex-mcp`, `swiss-courts-mcp`,
   `swisstopo-mcp`); ein fest verdrahtetes `main` scheitert dort still —
   genau diese Annahme hat schon einmal einen Branch 15 Commits alt werden
   lassen.

## Zwei bewusste Entscheidungen

**Detached HEAD wird gemeldet, nicht übersprungen.** Die Frage lautet, wie
weit der *ausgecheckte Stand* zurückliegt, und die ist auch ohne Branchnamen
beantwortbar. Verlangt ist, dass dieser Fall nicht scheitert — nicht, dass er
schweigt. Die Ausgabe nennt dann den kurzen SHA statt eines Branchnamens.

**Ohne Netz wird nicht gegen die lokale `origin/<default>` gezählt.** Diese
Referenz ist genau so alt wie der Klon; eine Zahl daraus wäre eine Aussage
über den Stand von gestern, ausgegeben als Aussage über heute. Schweigen ist
die ehrlichere Fehlerform.

## Kosten

Im Normalfall — Klon aktuell — genau **ein** Netzaufruf: `ls-remote --symref`
liefert Branchnamen und Ziel-SHA zusammen. Ist der SHA lokal schon vorhanden
(`git cat-file -e`), entfällt der `fetch` ganz. Erst wenn wirklich etwas
fehlt, wird geholt.

## Lokal testen

```bash
CLAUDE_PROJECT_DIR="$PWD" ./.claude/hooks/session-start.sh; echo "exit=$?"
```

`exit=0` bei leerer Ausgabe heisst: Klon aktuell. `exit=0` muss es immer sein.
