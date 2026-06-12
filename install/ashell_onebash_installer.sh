#!/bin/sh
# Minimal a-Shell installer for upgraded-fiesta.

set -u

REPO_URL="https://github.com/benholl94-cmyk/upgraded-fiesta.git"
DEV_ROOT="$HOME/Documents/Developer"
REPO_DIR="$DEV_ROOT/upgraded-fiesta.git"
LOG_DIR="$DEV_ROOT/logs"
RUN_TS=`date +%Y%m%dT%H%M%S`
LOG_FILE="$LOG_DIR/onebash-ashell-installer-$RUN_TS.log"

mkdir -p "$DEV_ROOT"
mkdir -p "$LOG_DIR"
touch "$LOG_FILE"

log() {
  NOW=`date +%Y-%m-%dT%H:%M:%S`
  echo "$NOW $*"
  echo "$NOW $*" >> "$LOG_FILE"
}

fail() {
  log "ERROR $*"
  exit 1
}

log "START installer"

command -v lg2 >/dev/null 2>&1
if [ $? -ne 0 ]; then
  fail "lg2 not available"
fi

command -v python3 >/dev/null 2>&1
if [ $? -ne 0 ]; then
  fail "python3 not available"
fi

cd "$DEV_ROOT" || fail "cannot enter Developer folder"

if [ -d "$REPO_DIR" ]; then
  log "repository exists; pulling"
  cd "$REPO_DIR" || fail "cannot enter repository"
  lg2 pull >> "$LOG_FILE" 2>&1
  if [ $? -ne 0 ]; then
    fail "pull failed"
  fi
else
  log "repository missing; cloning"
  lg2 clone "$REPO_URL" >> "$LOG_FILE" 2>&1
  if [ $? -ne 0 ]; then
    fail "clone failed"
  fi
fi

cd "$REPO_DIR" || fail "cannot enter repository"

python3 -m py_compile scripts/mobile_operator.py >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
  fail "mobile operator compile failed"
fi

python3 -m py_compile scripts/ashell_static_server.py >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
  fail "static server compile failed"
fi

python3 scripts/mobile_operator.py validate >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
  fail "platform validation failed"
fi

python3 scripts/mobile_operator.py doctor >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
  fail "doctor check failed"
fi

log "DONE installer"
echo "Installed upgraded-fiesta mobile control plane."
echo "Next: cd ~/Documents/Developer/upgraded-fiesta.git"
echo "Next: python3 scripts/mobile_operator.py audit"
echo "Next: python3 scripts/mobile_operator.py serve"
echo "Log: $LOG_FILE"
exit 0
