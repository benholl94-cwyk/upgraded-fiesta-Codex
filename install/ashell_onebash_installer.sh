#!/bin/sh
# a-Shell installer for upgraded-fiesta.

set -u

REPO_URL="https://github.com/benholl94-cmyk/upgraded-fiesta.git"
DEV_ROOT="$HOME/Documents/Developer"
PRIMARY_REPO_DIR="$DEV_ROOT/upgraded-fiesta.git"
ALT_REPO_DIR="$DEV_ROOT/upgraded-fiesta"
REPO_DIR="$PRIMARY_REPO_DIR"
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
  echo "Installer log: $LOG_FILE"
  echo "Last log lines:"
  tail -n 40 "$LOG_FILE" 2>/dev/null || true
  exit 1
}

have() {
  command -v "$1" >/dev/null 2>&1
}

log "START installer"

if ! have lg2; then
  fail "lg2 not available"
fi

if ! have python3; then
  fail "python3 not available"
fi

cd "$DEV_ROOT" || fail "cannot enter Developer folder"

if [ -d "$PRIMARY_REPO_DIR" ]; then
  REPO_DIR="$PRIMARY_REPO_DIR"
  log "repository exists; pulling: $REPO_DIR"
  cd "$REPO_DIR" || fail "cannot enter repository: $REPO_DIR"
  lg2 pull >> "$LOG_FILE" 2>&1
  if [ $? -ne 0 ]; then
    fail "pull failed"
  fi
elif [ -d "$ALT_REPO_DIR" ]; then
  REPO_DIR="$ALT_REPO_DIR"
  log "repository exists; pulling: $REPO_DIR"
  cd "$REPO_DIR" || fail "cannot enter repository: $REPO_DIR"
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
  if [ -d "$ALT_REPO_DIR" ]; then
    REPO_DIR="$ALT_REPO_DIR"
  elif [ -d "$PRIMARY_REPO_DIR" ]; then
    REPO_DIR="$PRIMARY_REPO_DIR"
  else
    fail "clone finished but repository directory was not found"
  fi
fi

cd "$REPO_DIR" || fail "cannot enter repository: $REPO_DIR"

for path in scripts/mobile_operator.py scripts/ashell_static_server.py scripts/validate_mobile_iphone_platform.py scripts/repository_audit_report.py scripts/repository_audit_report.sh scripts/validate_repository.sh
do
  if [ ! -f "$path" ]; then
    fail "required file missing after clone or pull: $path"
  fi
done

python3 -m py_compile scripts/mobile_operator.py scripts/ashell_static_server.py scripts/validate_mobile_iphone_platform.py scripts/repository_audit_report.py >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
  fail "python compile failed"
fi

python3 scripts/mobile_operator.py validate >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
  fail "platform validation failed"
fi

python3 scripts/mobile_operator.py doctor >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
  fail "doctor check failed"
fi

python3 scripts/mobile_operator.py self-test >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
  fail "mobile operator self-test failed"
fi

python3 scripts/ashell_static_server.py --self-test >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
  fail "static server self-test failed"
fi

sh scripts/validate_repository.sh >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
  fail "repository validation failed"
fi

log "DONE installer"
echo "Installed upgraded-fiesta mobile control plane."
echo "Repository: $REPO_DIR"
echo "Next: cd \"$REPO_DIR\""
echo "Next: python3 scripts/mobile_operator.py audit"
echo "Next: python3 scripts/mobile_operator.py serve"
echo "Log: $LOG_FILE"
exit 0
