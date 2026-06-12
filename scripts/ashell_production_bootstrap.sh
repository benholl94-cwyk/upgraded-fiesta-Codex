#!/bin/sh
# a-Shell production bootstrap for benholl94-cmyk/upgraded-fiesta.
# Safe scope: creates local Developer folders, logs, repo control-plane exports,
# a lg2-backed git wrapper, and deterministic local validation. It does not
# create or store secrets.

set -u

DEV_ROOT="$HOME/Developer"
BIN_DIR="$HOME/Documents/bin"
RUN_DATE=`date -u +%Y-%m-%d 2>/dev/null || date +%Y-%m-%d`
RUN_TS=`date -u +%Y%m%dT%H%M%SZ 2>/dev/null || date +%Y%m%dT%H%M%S`
LOG_DIR="$DEV_ROOT/logs"
RUN_DIR="$DEV_ROOT/runs"
LOG_FILE="$LOG_DIR/upgraded-fiesta-ashell-bootstrap-$RUN_TS.log"
SECRET_SCAN_FILE="$LOG_DIR/upgraded-fiesta-secret-scan-$RUN_TS.txt"

mkdir -p "$DEV_ROOT"
mkdir -p "$DEV_ROOT/repos"
mkdir -p "$DEV_ROOT/inbox"
mkdir -p "$DEV_ROOT/outbox"
mkdir -p "$DEV_ROOT/runs"
mkdir -p "$DEV_ROOT/logs"
mkdir -p "$DEV_ROOT/exports"
mkdir -p "$DEV_ROOT/backups"
mkdir -p "$DEV_ROOT/tmp"
mkdir -p "$DEV_ROOT/policies"
mkdir -p "$DEV_ROOT/datasets"
mkdir -p "$BIN_DIR"

touch "$LOG_FILE"

log() {
  NOW=`date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date`
  echo "$NOW $*"
  echo "$NOW $*" >> "$LOG_FILE"
}

log "START upgraded-fiesta a-Shell bootstrap"
log "DEV_ROOT=$DEV_ROOT"

# Resolve repository root. Expected call: sh scripts/ashell_production_bootstrap.sh
SCRIPT_DIR=`dirname "$0"`
if [ "$SCRIPT_DIR" = "." ]; then
  REPO_ROOT=`pwd`
else
  cd "$SCRIPT_DIR/.." 2>/dev/null
  REPO_ROOT=`pwd`
fi

log "REPO_ROOT=$REPO_ROOT"

if [ ! -f "$REPO_ROOT/README.md" ]; then
  log "ERROR README.md not found. Run this script from the upgraded-fiesta repository."
  exit 1
fi

if [ ! -f "$REPO_ROOT/index.html" ]; then
  log "ERROR index.html not found. Repository static platform is incomplete."
  exit 1
fi

if [ ! -f "$REPO_ROOT/scripts/validate_mobile_iphone_platform.py" ]; then
  log "ERROR validation script missing."
  exit 1
fi

# Ensure lg2-backed git wrapper for a-Shell.
if command -v lg2 >/dev/null 2>&1; then
  cat > "$BIN_DIR/git" <<'WRAPPER'
#!/bin/sh
lg2 "$@"
WRAPPER
  chmod +x "$BIN_DIR/git"
  log "OK installed lg2-backed git wrapper at $BIN_DIR/git"
else
  log "WARN lg2 not found. Git wrapper skipped."
fi

# Idempotent a-Shell profile block.
PROFILE="$HOME/.profile"
touch "$PROFILE"
if grep -q "upgraded-fiesta a-Shell bootstrap" "$PROFILE" 2>/dev/null; then
  log "OK profile block already present"
else
  cat >> "$PROFILE" <<'PROFILE_BLOCK'

# upgraded-fiesta a-Shell bootstrap
export EDITOR=vim
export MOBILE_DEV_ROOT="$HOME/Developer"
export UPGRADED_FIESTA_REPO="$HOME/Developer/repos/upgraded-fiesta"
alias ll='ls -la'
alias py='python3'
alias serve='python3 -m http.server 8000'
alias gs='lg2 status'
alias gv='lg2 version'
PROFILE_BLOCK
  log "OK appended upgraded-fiesta profile block to $PROFILE"
fi

# Export versioned control-plane settings and datasets into the local Developer contract.
mkdir -p "$DEV_ROOT/policies/mobile-iphone-platform"
mkdir -p "$DEV_ROOT/datasets/mobile-iphone-platform"

if [ -d "$REPO_ROOT/settings/mobile-iphone-platform" ]; then
  cp "$REPO_ROOT/settings/mobile-iphone-platform"/*.json "$DEV_ROOT/policies/mobile-iphone-platform/" 2>/dev/null
  log "OK exported settings to $DEV_ROOT/policies/mobile-iphone-platform"
else
  log "WARN settings/mobile-iphone-platform missing"
fi

if [ -d "$REPO_ROOT/datasets/mobile-iphone-platform" ]; then
  cp "$REPO_ROOT/datasets/mobile-iphone-platform"/* "$DEV_ROOT/datasets/mobile-iphone-platform/" 2>/dev/null
  log "OK exported datasets to $DEV_ROOT/datasets/mobile-iphone-platform"
else
  log "WARN datasets/mobile-iphone-platform missing"
fi

# Minimal local secret-pattern scan. No content is printed, only path hits.
: > "$SECRET_SCAN_FILE"
find "$REPO_ROOT" -name ".env" >> "$SECRET_SCAN_FILE" 2>/dev/null
find "$REPO_ROOT" -name "id_ed25519" >> "$SECRET_SCAN_FILE" 2>/dev/null
find "$REPO_ROOT" -name "*.pem" >> "$SECRET_SCAN_FILE" 2>/dev/null
find "$REPO_ROOT" -name "*.p12" >> "$SECRET_SCAN_FILE" 2>/dev/null
find "$REPO_ROOT" -name "secrets.*" >> "$SECRET_SCAN_FILE" 2>/dev/null

if [ -s "$SECRET_SCAN_FILE" ]; then
  log "BLOCKED forbidden secret-like files detected. Review $SECRET_SCAN_FILE before commit or push."
  cat "$SECRET_SCAN_FILE"
  exit 2
else
  log "OK forbidden secret-like file scan clean"
fi

# Deterministic local validation.
if command -v python3 >/dev/null 2>&1; then
  python3 -m py_compile "$REPO_ROOT/scripts/validate_mobile_iphone_platform.py" >> "$LOG_FILE" 2>&1
  if [ $? -ne 0 ]; then
    log "ERROR Python compile check failed"
    exit 3
  fi
  log "OK Python compile check passed"

  cd "$REPO_ROOT"
  python3 scripts/validate_mobile_iphone_platform.py >> "$LOG_FILE" 2>&1
  if [ $? -ne 0 ]; then
    log "ERROR mobile iPhone platform validation failed"
    exit 4
  fi
  log "OK mobile iPhone platform validation passed"
else
  log "WARN python3 not found. Validation skipped."
fi

# Git status through lg2 if available.
if command -v lg2 >/dev/null 2>&1; then
  cd "$REPO_ROOT"
  lg2 status >> "$LOG_FILE" 2>&1
  log "OK lg2 status recorded"
fi

# Daily run marker.
echo "upgraded-fiesta bootstrap ok: $RUN_TS" > "$RUN_DIR/$RUN_DATE-upgraded-fiesta-bootstrap.log"
log "OK wrote daily run marker $RUN_DIR/$RUN_DATE-upgraded-fiesta-bootstrap.log"
log "DONE upgraded-fiesta a-Shell production bootstrap"
log "Log file: $LOG_FILE"

exit 0
