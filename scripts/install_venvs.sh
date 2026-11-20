#!/usr/bin/env bash
# Install all four AgriShield virtual environments, one per directory.
#
#   chmod +x scripts/install_venvs.sh
#   ./scripts/install_venvs.sh
#
# What it does, per directory (apps/backend, apps/frontend, data_pipeline, ml-models):
#   1. python3 -m venv <dir>/venv
#   2. pip install --upgrade pip        (fixes stale-index / old-pip resolution failures)
#   3. pip install --retries 10 --timeout 300 -r <dir>/requirements.txt
#      (retry on network timeouts)
#
# No venv is created in the repo root, and every `venv/` is gitignored — nothing here
# is committed. Re-run anytime to repair or refresh an environment.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DIRS=(
  "apps/backend"
  "apps/frontend"
  "data_pipeline"
  "ml-models"
)

log()  { printf '\n==> %s\n' "$*"; }
err()  { printf '\n!! %s\n' "$*" >&2; }

have_venv() {
  local dir="$1"
  [[ -x "$ROOT_DIR/$dir/venv/bin/python" ]]
}

install_one() {
  local dir="$1"
  local req="$ROOT_DIR/$dir/requirements.txt"
  local venv_bin="$ROOT_DIR/$dir/venv/bin"

  log "Creating venv for $dir ..."
  python3 -m venv "$ROOT_DIR/$dir/venv"

  log "Upgrading pip in $dir ..."
  "$venv_bin/python" -m pip install --upgrade pip

  log "Installing $dir/requirements.txt (retries=10, timeout=300s) ..."
  "$venv_bin/pip" install \
        --retries 10 \
        --timeout 300 \
        -r "$req"
  log "$dir installed OK."
}

main() {
  log "Root: $ROOT_DIR"
  log "Python: $(python3 --version)"

  for dir in "${DIRS[@]}"; do
    if have_venv "$dir"; then
      log "Venv already exists for $dir — removing and recreating ..."
      rm -rf "$ROOT_DIR/$dir/venv"
    fi
    install_one "$dir"
  done

  log "=== All four venvs installed ==="
  for dir in "${DIRS[@]}"; do
    printf '  %-22s %s\n' "$dir" "$($ROOT_DIR/$dir/venv/bin/python -c 'import sys; print(sys.version.split()[0])')"
  done
}

main "$@"
