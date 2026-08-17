#!/usr/bin/env bash
# Make every skill this toolkit uses available inside this repo.
#
# The five skills in .claude/skills/ are maintained here and need no install —
# Claude Code loads project skills automatically when you run it from the repo
# root, which is also where prospects/ lives, so it's where you'd be working
# anyway. Clone the repo and they work.
#
# The only thing that needs installing is the three skills maintained in OTHER
# repos. They are deliberately not vendored here: the copies that used to be
# drifted 54 commits behind upstream, with 4 files where upstream had 37, and
# nothing to signal it. So this script clones them into vendor/ (gitignored)
# and symlinks them into .claude/skills/ with repo-relative links, which keeps
# everything self-contained and machine-independent.
#
# Nothing outside this repo is touched unless you pass --user.
#
# Usage:
#   scripts/install-skills.sh            # clone/refresh upstream, link into the repo
#   scripts/install-skills.sh --user     # ALSO link all skills into ~/.claude/skills/
#                                        #   for working outside the repo directory
#   scripts/install-skills.sh --list     # show what's installed and where
#   scripts/install-skills.sh --uninstall

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS="$REPO/.claude/skills"
VENDOR="$REPO/vendor"

# installed-name : git-url : path-to-skill-within-that-repo
UPSTREAM=(
  "sigma-api:https://github.com/sigmacomputing/sigma-agent-skills.git:skills/sigma-api"
  "sigma-data-models:https://github.com/sigmacomputing/sigma-agent-skills.git:skills/sigma-data-models"
  "sigma-workbook-conventions:https://github.com/RyanLauderback/ryan-workbook-skill.git:skills/sigma-workbook-conventions"
)

ok()   { printf '  + %s\n' "$*"; }
warn() { printf '  ! %s\n' "$*"; }
bold() { printf '\n\033[1m%s\033[0m\n' "$*"; }

upstream_names() { for e in "${UPSTREAM[@]}"; do echo "${e%%:*}"; done; }

owned_names() {
  # A skill is "owned" if it's a real directory (not one of our symlinks).
  find "$SKILLS" -maxdepth 1 -mindepth 1 -type d -exec basename {} \; 2>/dev/null | sort
}

case "${1:-}" in
  --list)
    bold "Skills in .claude/skills/ (project scope — loaded when you run Claude here)"
    for d in "$SKILLS"/*; do
      [ -e "$d" ] || continue
      if [ -L "$d" ]; then
        printf '  %-30s -> %s  (upstream)\n' "$(basename "$d")" "$(readlink "$d")"
      else
        printf '  %-30s     (maintained here)\n' "$(basename "$d")"
      fi
    done
    if [ -d "$VENDOR" ]; then
      bold "Upstream clones in vendor/"
      for c in "$VENDOR"/*; do
        [ -d "$c/.git" ] || continue
        printf '  %-30s %s\n' "$(basename "$c")" \
          "$(git -C "$c" log -1 --date=short --pretty='%ad %h' 2>/dev/null)"
      done
    fi
    if [ -d "$HOME/.claude/skills" ]; then
      links=$(find "$HOME/.claude/skills" -maxdepth 1 -type l -lname "$REPO/*" 2>/dev/null | wc -l | tr -d ' ')
      [ "$links" = "0" ] || { bold "Also linked into ~/.claude/skills/ (user scope)"; printf '  %s link(s) pointing at this repo\n' "$links"; }
    fi
    exit 0 ;;
  --uninstall)
    bold "Removing upstream symlinks and vendor/"
    for name in $(upstream_names); do
      [ -L "$SKILLS/$name" ] && { rm -f "$SKILLS/$name"; ok "unlinked $name"; }
    done
    for d in "$HOME/.claude/skills"/*; do
      [ -L "$d" ] || continue
      case "$(readlink "$d")" in "$REPO"/*) rm -f "$d"; ok "unlinked ~/.claude/skills/$(basename "$d")" ;; esac
    done
    [ -d "$VENDOR" ] && { rm -rf "$VENDOR"; ok "removed vendor/"; }
    exit 0 ;;
  --user) LINK_USER=1 ;;
  "")     LINK_USER=0 ;;
  *) echo "error: unknown argument: $1" >&2; exit 1 ;;
esac

failed=0
mkdir -p "$VENDOR"

bold "Maintained in this repo (no install needed)"
for name in $(owned_names); do ok "$name"; done

bold "Upstream skills — cloning into vendor/, linking into .claude/skills/"
if ! command -v git >/dev/null 2>&1; then
  warn "git not found; cannot fetch upstream skills"
  exit 1
fi

for entry in "${UPSTREAM[@]}"; do
  name="${entry%%:*}"
  rest="${entry#*:}"
  url="${rest%:*}"
  subpath="${rest##*:}"
  repo_name="$(basename "$url" .git)"
  clone="$VENDOR/$repo_name"

  if [ -d "$clone/.git" ]; then
    if out=$(git -C "$clone" pull --ff-only 2>&1); then
      case "$out" in
        *"Already up to date"*) ok "$repo_name (up to date)" ;;
        *)                      ok "$repo_name (updated)" ;;
      esac
    else
      warn "$repo_name — pull failed; using the existing clone"
    fi
  else
    printf '  cloning %s ... ' "$repo_name"
    if git clone -q --depth 50 "$url" "$clone" 2>/dev/null; then echo "done"
    else echo "FAILED"; warn "could not clone $url"; failed=1; continue; fi
  fi

  if [ ! -d "$clone/$subpath" ]; then
    warn "$name — expected $subpath in $repo_name; upstream may have moved it."
    warn "    Update the UPSTREAM array in this script."
    failed=1; continue
  fi

  dest="$SKILLS/$name"
  if [ -e "$dest" ] && [ ! -L "$dest" ]; then
    warn "$name — a real directory exists at .claude/skills/$name."
    warn "    That's the vendored copy this script replaces. Delete it and re-run."
    failed=1; continue
  fi
  rm -f "$dest"
  # Repo-relative so the link works on any machine and in any clone location.
  ln -s "../../vendor/$repo_name/$subpath" "$dest"

  # A SKILL.md alone isn't proof: upstream left a one-file stub behind at the
  # old .claude/skills/ path when it moved the real skill to skills/, and an
  # existence check happily linked the stub. Count what resolves instead.
  n_files=$(find -L "$dest" -type f 2>/dev/null | wc -l | tr -d ' ')
  if [ ! -f "$dest/SKILL.md" ]; then
    warn "$name — link created but SKILL.md doesn't resolve through it"
    failed=1
  elif [ "$n_files" -lt 2 ]; then
    warn "$name — resolves to a $n_files-file stub, not a full skill."
    warn "    Upstream has probably moved it; check the layout of $repo_name"
    warn "    and update the UPSTREAM array."
    failed=1
  else
    ok "$name -> vendor/$repo_name/$subpath ($n_files files)"
  fi
done

# --- optional: user scope --------------------------------------------------
if [ "${LINK_USER:-0}" = "1" ]; then
  bold "Also linking into ~/.claude/skills/ (loads from any directory)"
  mkdir -p "$HOME/.claude/skills"
  for name in $(owned_names) $(upstream_names); do
    src="$SKILLS/$name"
    dest="$HOME/.claude/skills/$name"
    [ -e "$src" ] || continue
    if [ -e "$dest" ] && [ ! -L "$dest" ]; then
      warn "$name — real directory at ~/.claude/skills/$name, left alone"
      continue
    fi
    rm -f "$dest"
    ln -s "$src" "$dest"
    ok "${HOME/#$HOME/~}/.claude/skills/$name"
  done
fi

bold "Done"
echo "  Run Claude Code from $(basename "$REPO")/ and all skills load automatically."
echo "  scripts/install-skills.sh --list       see what points where"
echo "  scripts/install-skills.sh              re-run to refresh upstream"
[ "$failed" = "0" ] || { echo; warn "some steps reported problems"; exit 1; }
