#!/usr/bin/env bash
# Sourcebook one-line installer
# Usage: curl -fsSL https://raw.githubusercontent.com/joxtoyod/sourcebook/main/install.sh | bash

set -euo pipefail

REPO="https://github.com/joxtoyod/sourcebook.git"
INSTALL_DIR="${SOURCEBOOK_DIR:-$HOME/.sourcebook}"
MIN_PYTHON="3.11"
MIN_NODE="20"

# ── Helpers ────────────────────────────────────────────────────────────────

green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
red()    { printf '\033[0;31m%s\033[0m\n' "$*"; exit 1; }
info()   { printf '  → %s\n' "$*"; }

version_gte() {
  [ "$(printf '%s\n' "$@" | sort -V | head -n1)" = "$2" ]
}

# Detect the user's shell config file
detect_shell_config() {
  local shell_name
  shell_name="$(basename "${SHELL:-bash}")"
  case "$shell_name" in
    zsh)  echo "$HOME/.zshrc" ;;
    bash) echo "${BASH_ENV:-$HOME/.bashrc}" ;;
    fish) echo "$HOME/.config/fish/config.fish" ;;
    *)    echo "$HOME/.profile" ;;
  esac
}

# Add a directory to PATH in the shell config if it's not already there
ensure_in_path() {
  local bin_dir="$1"
  local config_file
  config_file="$(detect_shell_config)"

  # Already in current session's PATH?
  if echo ":$PATH:" | grep -q ":${bin_dir}:"; then
    return 0
  fi

  # Already written to config?
  if [ -f "$config_file" ] && grep -qF "$bin_dir" "$config_file"; then
    return 0
  fi

  yellow "Adding $bin_dir to PATH in $config_file"
  printf '\n# Added by Sourcebook installer\nexport PATH="%s:$PATH"\n' "$bin_dir" >> "$config_file"
  # Also export in the current session so the user can run sourcebook immediately
  export PATH="$bin_dir:$PATH"
}

# ── Prerequisites ──────────────────────────────────────────────────────────

green "Checking prerequisites..."

# Python
if ! command -v python3 &>/dev/null; then
  red "Python 3 not found. Install Python $MIN_PYTHON or newer: https://python.org"
fi
PY_VER=$(python3 -c 'import sys; print(".".join(map(str,sys.version_info[:2])))')
if ! version_gte "$PY_VER" "$MIN_PYTHON"; then
  red "Python $MIN_PYTHON+ required (found $PY_VER). Upgrade Python and re-run."
fi
info "Python $PY_VER"

# Node.js
if ! command -v node &>/dev/null; then
  red "Node.js not found. Install Node.js $MIN_NODE or newer: https://nodejs.org"
fi
NODE_VER=$(node -e 'process.stdout.write(process.versions.node)')
NODE_MAJOR="${NODE_VER%%.*}"
if [ "$NODE_MAJOR" -lt "$MIN_NODE" ]; then
  red "Node.js $MIN_NODE+ required (found $NODE_VER). Upgrade Node.js and re-run."
fi
info "Node.js $NODE_VER"

# npm
if ! command -v npm &>/dev/null; then
  red "npm not found. It should ship with Node.js — check your Node.js installation."
fi
info "npm $(npm --version)"

# claude CLI (optional)
if ! command -v claude &>/dev/null; then
  yellow "Warning: 'claude' CLI not found."
  yellow "Sourcebook uses Claude Code for AI features."
  yellow "Install it from: https://claude.ai/download"
  yellow "(Continuing install — you can add it later.)"
fi

# ── Clone / update ─────────────────────────────────────────────────────────

green "Installing Sourcebook to $INSTALL_DIR ..."

if [ -d "$INSTALL_DIR/.git" ]; then
  info "Existing installation found — updating..."
  git -C "$INSTALL_DIR" pull --ff-only --quiet
else
  info "Cloning repository..."
  git clone --depth=1 --quiet "$REPO" "$INSTALL_DIR"
fi

# ── Build frontend ─────────────────────────────────────────────────────────

green "Building frontend..."

cd "$INSTALL_DIR/frontend"
info "Installing npm dependencies..."
npm install --silent
info "Building SvelteKit app..."
npm run build --silent
info "Frontend built → backend/sourcebook/static/"

# ── Ensure pipx is available ───────────────────────────────────────────────

green "Installing Python package..."

cd "$INSTALL_DIR"

if ! command -v pipx &>/dev/null; then
  info "pipx not found — installing it now..."
  pip install --user --quiet pipx

  # Make pipx available in this session immediately
  USER_BIN="$(python3 -m site --user-base)/bin"
  export PATH="$USER_BIN:$PATH"

  if ! command -v pipx &>/dev/null; then
    red "pipx install failed. Please install pipx manually: https://pipx.pypa.io"
  fi
fi

info "Using pipx..."
pipx install --force ./backend

# Write the bin dir to the shell config so it survives new terminals
pipx ensurepath --quiet 2>/dev/null || true
ensure_in_path "$HOME/.local/bin"

# ── Verify ────────────────────────────────────────────────────────────────

if command -v sourcebook &>/dev/null; then
  info "sourcebook $(sourcebook --version 2>/dev/null || echo 'installed')"
fi

# ── Done ───────────────────────────────────────────────────────────────────

green ""
green "Sourcebook installed successfully!"
printf '\n'
printf '  Run from any project directory:\n'
printf '\n'
printf '    sourcebook          # start the UI\n'
printf '    sourcebook scan     # scan codebase and generate diagram\n'
printf '\n'
printf '  To update later, re-run this installer.\n'
printf '\n'

SHELL_CFG="$(detect_shell_config)"
if ! command -v sourcebook &>/dev/null 2>&1 || \
   [ "$(command -v sourcebook 2>/dev/null)" = "" ]; then
  yellow "Open a new terminal (or run: source $SHELL_CFG) for 'sourcebook' to be available."
else
  green "  'sourcebook' is ready to use in this shell."
fi
