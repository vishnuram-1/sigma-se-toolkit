#!/usr/bin/env bash
# Install this repo's Claude skills, plus the upstream ones they depend on.
#
# Why symlinks rather than copies:
#
#   sigma-api, sigma-data-models and sigma-workbook-conventions are maintained
#   in other people's repos. This toolkit used to ship forked copies, which
#   drifted badly — at the time of writing the upstream ryan-workbook-skill was
#   54 commits ahead of the copy that had been vendored here, with no way for
#   anyone to notice or update. Symlinking a real clone makes `git pull` the
#   update path and stops fixes flowing only one way.
#
#   This repo's OWN skills are symlinked too, into ~/.claude/skills/. That
#   makes them load from any directory rather than only when Claude Code is
#   started from inside the repo, and it means editing the installed skill
#   edits the repo file — so an improvement you make is a commit you can push,
#   not a change stranded on your laptop.
#
# Usage:
#   scripts/install-skills.sh              # install / refresh everything
#   scripts/install-skills.sh --own-only   # skip the upstream clones
#   scripts/install-skills.sh --list       # show what's installed and where
#   scripts/install-skills.sh --uninstall  # remove only the links we created

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="$HOME/.claude/skills"
SOURCES_DIR="$HOME/.claude/skill-sources"

# installed-name : git-url : path-to-skill-within-that-repo
UPSTREAM=(
  "sigma-api:https://github.com/sigmacomputing/sigma-agent-skills.git:skills/sigma-api"
  "sigma-data-models:https://github.com/sigmacomputing/sigma-agent-skills.git:skills/sigma-data-models"
  "sigma-workbook-conventions:https://github.com/RyanLauderback/ryan-workbook-skill.git:.claude/skills/sigma-workbook-conventions"
)

ok()   { printf '  + %s\n' "$*"; }
warn() { printf '  ! %s\n' "$*"; }
bold() { printf '\n\033[1m%s\033[0m\n' "$*"; }

own_skills() {
  find "$REPO/.claude/skills" -maxdepth 1 -mindepth 1 -type d -exec basename {} \; 2>/dev/null | sort
}

# Link $2 -> $1, refusing to clobber anything that isn't a symlink we own.
link() {
  # Separate `local` statements: within a single `local`, later assignments
  # can't see earlier ones, so `dest` would silently read an outer `name`.
  local target="$1"
  local name="$2"
  local dest="$SKILLS_DIR/$name"
  if [ -L "$dest" ]; then
    local current
    current="$(readlink "$dest")"
    if [ "$current" = "$target" ]; then ok "$name (already linked)"; return 0; fi
    rm -f "$dest"
  elif [ -e "$dest" ]; then
    warn "$name — a real directory already exists at $dest, leaving it alone."
    warn "    Move or delete it, then re-run, if you want the linked version."
    return 1
  fi
  ln -s "$target" "$dest"
  ok "$name -> ${target/#$HOME/~}"
}

case "${1:-}" in
  --list)
    bold "Installed skills in ${SKILLS_DIR/#$HOME/~}"
    if [ ! -d "$SKILLS_DIR" ]; then warn "nothing installed"; exit 0; fi
    for d in "$SKILLS_DIR"/*; do
      [ -e "$d" ] || continue
      name="$(basename "$d")"
      if [ -L "$d" ]; then
        printf '  %-32s -> %s\n' "$name" "$(readlink "$d" | sed "s|^$HOME|~|")"
      else
        printf '  %-32s    (real directory, not managed here)\n' "$name"
      fi
    done
    exit 0 ;;
  --uninstall)
    bold "Removing symlinks this script created"
    for name in $(own_skills); do
      dest="$SKILLS_DIR/$name"
      [ -L "$dest" ] && { rm -f "$dest"; ok "removed $name"; }
    done
    for entry in "${UPSTREAM[@]}"; do
      name="${entry%%:*}"; dest="$SKILLS_DIR/$name"
      [ -L "$dest" ] && { rm -f "$dest"; ok "removed $name"; }
    done
    warn "clones under ${SOURCES_DIR/#$HOME/~} were left in place; delete them by hand if you want them gone."
    exit 0 ;;
  --own-only) SKIP_UPSTREAM=1 ;;
  "") SKIP_UPSTREAM=0 ;;
  *) echo "error: unknown argument: $1" >&2; exit 1 ;;
esac

mkdir -p "$SKILLS_DIR" "$SOURCES_DIR"

# --- this repo's own skills -------------------------------------------------
bold "This toolkit's skills"
failed=0
for name in $(own_skills); do
  link "$REPO/.claude/skills/$name" "$name" || failed=1
done

# --- upstream skills -------------------------------------------------------
if [ "${SKIP_UPSTREAM:-0}" = "0" ]; then
  bold "Upstream skills (maintained elsewhere; refreshed with git pull)"
  if ! command -v git >/dev/null 2>&1; then
    warn "git not found — skipping upstream skills"
  else
    for entry in "${UPSTREAM[@]}"; do
      name="${entry%%:*}"
      rest="${entry#*:}"
      url="${rest%:*}"
      subpath="${rest##*:}"
      repo_name="$(basename "$url" .git)"
      clone="$SOURCES_DIR/$repo_name"

      if [ -d "$clone/.git" ]; then
        if out=$(git -C "$clone" pull --ff-only 2>&1); then
          case "$out" in
            *"Already up to date"*) ok "$repo_name (up to date)" ;;
            *) ok "$repo_name (updated)" ;;
          esac
        else
          warn "$repo_name — pull failed, using the existing clone as-is"
        fi
      else
        printf '  cloning %s ... ' "$repo_name"
        if git clone -q --depth 50 "$url" "$clone" 2>/dev/null; then echo "done"
        else echo "FAILED"; warn "could not clone $url — skipping $name"; failed=1; continue; fi
      fi

      if [ ! -d "$clone/$subpath" ]; then
        warn "$name — expected $subpath inside $repo_name and it isn't there."
        warn "    Upstream may have moved it; update UPSTREAM in this script."
        failed=1; continue
      fi
      link "$clone/$subpath" "$name" || failed=1
    done
  fi
fi

bold "Done"
printf '  %s skill(s) linked into %s\n' \
  "$(find "$SKILLS_DIR" -maxdepth 1 -type l | wc -l | tr -d ' ')" "${SKILLS_DIR/#$HOME/~}"
echo "  scripts/install-skills.sh --list      see what points where"
echo "  scripts/install-skills.sh             re-run any time to refresh upstream"
[ "$failed" = "0" ] || { echo; warn "some steps reported problems — see above"; exit 1; }
