#!/usr/bin/env bash
#
# SessionStart-Hook — Klon-Aktualitätsprüfung
#
# Meldet beim Sessionstart, wie viele Commits der ausgecheckte Stand hinter
# origin/<Default-Branch> liegt. Bei 0 schweigt er.
#
# WARUM (siehe auch .claude/hooks/README.md und CLAUDE.md, «Vor der Arbeit»):
# Ein veralteter Klon hat am 3.8.2026 zweimal eine rote CI erzeugt, deren
# Ursache nicht im Diff stand — die fehlenden Commits waren jeweils genau die,
# die das Gate einführten, an dem der Branch scheiterte. Die Prüfung kostet
# eine Sekunde und ersetzt eine Fehlersuche in den falschen Dateien.
#
# REGEL 1 — der Hook blockiert die Session NIE.
# Kein Netz, kein Remote, kein Git-Repo, detached HEAD, flatterndes DNS,
# fehlende Credentials: jeder dieser Fälle endet still mit Exit 0. Ein Hook,
# der bei Netzproblemen die Arbeit anhält, wird nach dem zweiten Mal
# abgeschaltet und schützt danach gar nichts.
# Deshalb bewusst KEIN `set -e` / `set -u`: ein einziges unerwartet
# scheiterndes Kommando würde den Hook sonst mit != 0 beenden. Stattdessen ist
# jeder Ausstieg ein explizites `exit 0`.
#
# REGEL 2 — der Default-Branch wird ermittelt, nicht angenommen.
# Im Portfolio heissen drei Server ihren Default-Branch `master`
# (openlex-mcp, swiss-courts-mcp, swisstopo-mcp). Ein fest verdrahtetes `main`
# scheitert dort still — und genau diese Annahme hat schon einmal einen Branch
# 15 Commits alt werden lassen.

# GESAMTBUDGET für alle Netzaufrufe zusammen, in Sekunden. Bewusst klein und
# bewusst *gesamt*, nicht pro Aufruf: bei einem Host, der die Verbindung
# annimmt und dann schweigt, würde ein Budget pro Aufruf sonst zweimal
# ablaufen und den Sessionstart doppelt so lange aufhalten.
NET_BUDGET="${CLAUDE_STALE_CLONE_TIMEOUT:-5}"
_net_deadline=$(( $(date +%s) + NET_BUDGET ))

# Nichts darf interaktiv nachfragen — eine Passwort- oder Host-Key-Abfrage
# wäre genau das Hängen, das Regel 1 ausschliesst.
export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS=/bin/true
export SSH_ASKPASS=/bin/true
export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh} -o BatchMode=yes -o ConnectTimeout=${NET_BUDGET}"

# Kappt das Kommando auf die noch verbleibende Restzeit des Budgets. Ist es
# aufgebraucht, wird gar nicht mehr angefragt.
# `timeout` ist coreutils und fehlt z. B. auf macOS ohne GNU-Tools. Fehlt es,
# läuft das Kommando ohne harte Schranke — ConnectTimeout oben und das
# `timeout` in settings.json bleiben als Netz darunter.
run_capped() {
  local left=$(( _net_deadline - $(date +%s) ))
  [ "$left" -gt 0 ] || return 1
  if command -v timeout >/dev/null 2>&1; then
    timeout -k 1 "$left" "$@"
  else
    "$@"
  fi
}

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0

# Kein Git-Repo, kein Remote `origin` → nichts zu prüfen.
git rev-parse --git-dir >/dev/null 2>&1 || exit 0
git remote get-url origin >/dev/null 2>&1 || exit 0

# Default-Branch beim Remote erfragen. `--symref` liefert in einem Aufruf den
# Namen UND den SHA von HEAD — der SHA spart unten oft den zweiten Netzaufruf.
default_branch=""
remote_head=""
ls_remote="$(run_capped git ls-remote --symref origin HEAD 2>/dev/null)"
if [ -n "$ls_remote" ]; then
  default_branch="$(printf '%s\n' "$ls_remote" |
    sed -n 's|^ref: refs/heads/\([^[:space:]]*\)[[:space:]]*HEAD$|\1|p' | head -1)"
  remote_head="$(printf '%s\n' "$ls_remote" |
    sed -n 's|^\([0-9a-f]\{7,\}\)[[:space:]]*HEAD$|\1|p' | head -1)"
fi

# Ohne Netz: letzte lokal bekannte Zuordnung. Auch die kann fehlen.
if [ -z "$default_branch" ]; then
  default_branch="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null)"
  default_branch="${default_branch#origin/}"
fi
[ -n "$default_branch" ] || exit 0

# Zielcommit bestimmen. Haben wir den Remote-HEAD schon lokal, ist gar kein
# fetch nötig — das ist der Normalfall beim aktuellen Klon.
target=""
if [ -n "$remote_head" ] && git cat-file -e "${remote_head}^{commit}" 2>/dev/null; then
  target="$remote_head"
elif run_capped git fetch --quiet --no-tags origin "$default_branch" >/dev/null 2>&1; then
  # FETCH_HEAD nur lesen, wenn der fetch gerade erfolgreich war — sonst wäre
  # es der Stand eines früheren Laufs.
  target="$(git rev-parse --verify --quiet FETCH_HEAD 2>/dev/null)"
fi
[ -n "$target" ] || exit 0

behind="$(git rev-list --count "HEAD..${target}" 2>/dev/null)"
case "$behind" in
  '' | *[!0-9]*) exit 0 ;;
esac
[ "$behind" -gt 0 ] || exit 0

# Ab hier: es fehlen tatsächlich Commits. Nur jetzt wird etwas ausgegeben.
current="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
if [ -z "$current" ] || [ "$current" = "HEAD" ]; then
  current="detached HEAD $(git rev-parse --short HEAD 2>/dev/null)"
fi

if [ "$behind" -eq 1 ]; then
  commits="1 Commit"
else
  commits="${behind} Commits"
fi

cat <<EOF
⚠️  Klon veraltet: '${current}' liegt ${commits} hinter origin/${default_branch}.

Vor der Arbeit einholen. Ein veralteter Klon erzeugt eine rote CI, deren
Ursache nicht im Diff steht — die fehlenden Commits sind erfahrungsgemäss
genau die, die das Gate einführen, an dem der Branch dann scheitert.

    git fetch origin ${default_branch} && git merge FETCH_HEAD
EOF

exit 0
