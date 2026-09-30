#!/usr/bin/env bash
# Canonical self-contained launcher for the portable FindCare Search demo.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$SCRIPT_DIR"

PORT="${PORT:-8035}"
HOST="127.0.0.1"
APP_URL="http://${HOST}:${PORT}/"
READY_URL="http://${HOST}:${PORT}/ready"
VENDOR_DIR="$SCRIPT_DIR/vendor"
PYTHON_BIN="$VENDOR_DIR/python/install/bin/python3"
VENV_DIR="$SCRIPT_DIR/.venv"
VENV_PY="$VENV_DIR/bin/python"
VENV_RUNTIME_STAMP="$VENV_DIR/.portable-python-version"
REQ_FILE="$SCRIPT_DIR/requirements.txt"
REQ_STAMP="$VENV_DIR/.requirements.sha256"
RUNTIME_DIR="$SCRIPT_DIR/.runtime"
APP_PID_FILE="$RUNTIME_DIR/app-${PORT}.pid"
APP_PID=""

case "$PORT" in
  ''|*[!0-9]*) echo "ERROR: PORT must be a number." >&2; exit 1 ;;
esac
if [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
  echo "ERROR: PORT must be between 1 and 65535." >&2
  exit 1
fi

process_cwd() {
  local pid="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1
  elif [ -e "/proc/$pid/cwd" ] && command -v readlink >/dev/null 2>&1; then
    readlink -f "/proc/$pid/cwd" 2>/dev/null || true
  fi
}

process_is_this_demo() {
  local pid="$1" command cwd
  command="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  cwd="$(process_cwd "$pid")"
  [ "$cwd" = "$SCRIPT_DIR" ] && [[ "$command" == *"uvicorn app.main:app"* ]]
}

is_descendant_of() {
  local pid="$1" ancestor="$2" parent
  while [ -n "$pid" ] && [ "$pid" -gt 1 ] 2>/dev/null; do
    [ "$pid" = "$ancestor" ] && return 0
    parent="$(ps -p "$pid" -o ppid= 2>/dev/null | tr -d ' ' || true)"
    [ -n "$parent" ] && [ "$parent" != "$pid" ] || break
    pid="$parent"
  done
  return 1
}

listener_pids() {
  lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | sort -u || true
}

port_is_listening() {
  (exec 3<>"/dev/tcp/${HOST}/${PORT}") >/dev/null 2>&1
}

stop_demo_pid() {
  local pid="$1"
  echo "       Restarting this FindCare instance (pid $pid) ..."
  if command -v pkill >/dev/null 2>&1; then
    pkill -TERM -P "$pid" 2>/dev/null || true
  fi
  kill -TERM "$pid" 2>/dev/null || true
  for _ in $(seq 1 40); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.25
  done
  if kill -0 "$pid" 2>/dev/null; then
    if command -v pkill >/dev/null 2>&1; then
      pkill -KILL -P "$pid" 2>/dev/null || true
    fi
    kill -KILL "$pid" 2>/dev/null || true
  fi
}

handoff_port() {
  local owners="" stored_pid="" stored_launcher="" owner matched=0 demo_pid=""
  local launcher_command=""

  mkdir -p "$RUNTIME_DIR"
  if command -v lsof >/dev/null 2>&1; then
    owners="$(listener_pids)"
    if [ -z "$owners" ]; then
      rm -f "$APP_PID_FILE"
      return 0
    fi
    if [ -f "$APP_PID_FILE" ]; then
      read -r stored_pid stored_launcher < "$APP_PID_FILE" || true
    fi
    if [ -n "$stored_pid" ] && kill -0 "$stored_pid" 2>/dev/null && process_is_this_demo "$stored_pid"; then
      matched=1
      for owner in $owners; do
        if ! is_descendant_of "$owner" "$stored_pid"; then
          matched=0
          break
        fi
      done
      [ "$matched" -eq 1 ] && demo_pid="$stored_pid"
    fi
    if [ -z "$demo_pid" ]; then
      matched=1
      for owner in $owners; do
        if ! process_is_this_demo "$owner"; then
          matched=0
          break
        fi
      done
      [ "$matched" -eq 1 ] && demo_pid="$(printf '%s\n' "$owners" | head -n 1)"
    fi
  else
    if ! port_is_listening; then
      rm -f "$APP_PID_FILE"
      return 0
    fi
    if [ -f "$APP_PID_FILE" ]; then
      read -r stored_pid stored_launcher < "$APP_PID_FILE" || true
    fi
    if [ -n "$stored_pid" ] && kill -0 "$stored_pid" 2>/dev/null && process_is_this_demo "$stored_pid"; then
      demo_pid="$stored_pid"
    fi
  fi

  if [ -z "$demo_pid" ]; then
    echo "ERROR: port $PORT belongs to another application and was not stopped." >&2
    echo "Choose another port, for example: PORT=8040 ./run.sh" >&2
    exit 1
  fi

  stop_demo_pid "$demo_pid"
  if [ -n "$stored_launcher" ]; then
    launcher_command="$(ps -p "$stored_launcher" -o command= 2>/dev/null || true)"
    if [[ "$launcher_command" == *"run.sh"* ]]; then
      for _ in $(seq 1 80); do
        kill -0 "$stored_launcher" 2>/dev/null || break
        sleep 0.25
      done
    fi
  fi
  rm -f "$APP_PID_FILE"

  for _ in $(seq 1 40); do
    if command -v lsof >/dev/null 2>&1; then
      [ -z "$(listener_pids)" ] && return 0
    elif ! port_is_listening; then
      return 0
    fi
    sleep 0.25
  done
  echo "ERROR: the previous FindCare process did not release port $PORT." >&2
  exit 1
}

file_sha256() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    "$PYTHON_BIN" -c 'import hashlib, pathlib, sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' "$1"
  fi
}

cleanup() {
  if [ -n "$APP_PID" ] && kill -0 "$APP_PID" 2>/dev/null; then
    kill -TERM "$APP_PID" 2>/dev/null || true
    wait "$APP_PID" 2>/dev/null || true
  fi
  if [ -n "$APP_PID" ] && [ -f "$APP_PID_FILE" ]; then
    local file_pid=""
    read -r file_pid _ < "$APP_PID_FILE" || true
    [ "$file_pid" = "$APP_PID" ] && rm -f "$APP_PID_FILE"
  fi
}
trap cleanup EXIT

wait_until_ready() {
  echo "       Waiting for the local API readiness check ..."
  for attempt in $(seq 1 180); do
    if ! kill -0 "$APP_PID" 2>/dev/null; then
      echo "ERROR: FindCare stopped before becoming ready." >&2
      return 1
    fi
    if "$VENV_PY" -c 'import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=1).read(1)' "$READY_URL" >/dev/null 2>&1; then
      echo "       Ready after ${attempt} check(s)."
      return 0
    fi
    sleep 0.5
  done
  echo "ERROR: FindCare did not become ready at $READY_URL." >&2
  return 1
}

open_browser() {
  if [ "${NO_BROWSER:-0}" = "1" ]; then
    return 0
  fi
  if command -v open >/dev/null 2>&1; then
    open "$APP_URL" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$APP_URL" >/dev/null 2>&1 || true
  else
    echo "       Open $APP_URL in a browser."
  fi
}

printf '\n============================================================\n'
printf '  FindCare Search Portable Demo\n'
printf '  URL: %s\n' "$APP_URL"
printf '============================================================\n\n'

echo "[1/5] Preparing the pinned standalone Python runtime"
bash "$SCRIPT_DIR/scripts/setup-python.sh"
if [ ! -x "$PYTHON_BIN" ]; then
  echo "ERROR: bundled Python was not installed at $PYTHON_BIN." >&2
  exit 1
fi

portable_python_version="$("$PYTHON_BIN" -c 'import platform; print(platform.python_version())')"
venv_python_version="$(cat "$VENV_RUNTIME_STAMP" 2>/dev/null || true)"
echo "[2/5] Preparing the project-local virtual environment"
if [ -d "$VENV_DIR" ] && [ "$venv_python_version" != "$portable_python_version" ]; then
  echo "       Replacing an environment not built with bundled Python $portable_python_version ..."
  rm -rf "$VENV_DIR"
fi
if [ ! -x "$VENV_PY" ]; then
  echo "       Creating .venv ..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
  printf '%s\n' "$portable_python_version" > "$VENV_RUNTIME_STAMP"
else
  echo "       Existing .venv is compatible."
fi

echo "[3/5] Checking pinned application dependencies"
requirements_hash="$(file_sha256 "$REQ_FILE")"
installed_hash="$(cat "$REQ_STAMP" 2>/dev/null || true)"
if [ "$requirements_hash" != "$installed_hash" ]; then
  echo "       Installing dependencies. First launch can take a few minutes ..."
  "$VENV_PY" -m pip install --disable-pip-version-check --cache-dir "$VENDOR_DIR/pip-cache" --upgrade pip
  "$VENV_PY" -m pip install --disable-pip-version-check --cache-dir "$VENDOR_DIR/pip-cache" -r "$REQ_FILE"
  printf '%s\n' "$requirements_hash" > "$REQ_STAMP"
else
  echo "       Dependencies are already up to date."
fi

if [ -f "$SCRIPT_DIR/.env" ]; then
  chmod 600 "$SCRIPT_DIR/.env" 2>/dev/null || true
fi

echo "[4/5] Verifying safe ownership of port $PORT"
handoff_port

echo "[5/5] Starting FindCare on $APP_URL"
PYTHONPATH=. "$VENV_PY" -m uvicorn app.main:app --host "$HOST" --port "$PORT" &
APP_PID=$!
printf '%s %s\n' "$APP_PID" "$$" > "$APP_PID_FILE"

forward_signal() {
  if command -v pkill >/dev/null 2>&1; then
    pkill -TERM -P "$APP_PID" 2>/dev/null || true
  fi
  kill -TERM "$APP_PID" 2>/dev/null || true
}
trap forward_signal INT TERM

wait_until_ready
echo
echo "FindCare is ready: $APP_URL"
echo "Press Ctrl+C to stop. Re-run ./run.sh to restart only this copy."
echo
open_browser

APP_EXIT=0
wait "$APP_PID" || APP_EXIT=$?
wait "$APP_PID" 2>/dev/null || true
trap - INT TERM
exit "$APP_EXIT"
