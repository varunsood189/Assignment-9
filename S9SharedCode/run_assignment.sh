#!/usr/bin/env bash
# Assignment 9 end-to-end runner (does not modify flow.py or run_demo.sh).
#
# Usage:
#   ./run_assignment.sh              run primary HF task + HTML report
#   ./run_assignment.sh laptops      run laptops comparison + report
#   ./run_assignment.sh all          run all four comparison tasks
#   ./run_assignment.sh report [sid] generate report only
#   ./run_assignment.sh tests        run unit tests (29)
#   ./run_assignment.sh wipe         clear sessions + FAISS + logs
#
# Prerequisites (once):
#   cd code && uv sync && uv run playwright install chromium
#   cd ../llm_gatewayV9 && uv run main.py   # separate terminal

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CODE_DIR="$SCRIPT_DIR/code"
GW_DIR="$SCRIPT_DIR/../llm_gatewayV9"

gateway_is_up() {
  curl -sf http://localhost:8109/v1/routers >/dev/null 2>&1
}

start_gateway() {
  if gateway_is_up; then
    echo "[assignment] V9 gateway already on :8109"
    return
  fi
  echo "[assignment] starting gateway from $GW_DIR ..."
  ( cd "$GW_DIR" && uv run main.py &>/tmp/gw_v9.log ) &
  for i in $(seq 1 45); do
    sleep 1
    if gateway_is_up; then
      echo "[assignment] gateway up after ${i}s"
      return
    fi
  done
  echo "[assignment] ERROR: gateway did not start — see /tmp/gw_v9.log" >&2
  exit 1
}

run_primary() {
  ( cd "$CODE_DIR" && uv run python assignment_runner.py )
}

run_task() {
  local key="$1"
  ( cd "$CODE_DIR" && uv run python run_comparisons.py "$key" )
}

run_all_tasks() {
  ( cd "$CODE_DIR" && uv run python run_comparisons.py all )
}

generate_report() {
  local sid="${1:-}"
  if [[ -n "$sid" ]]; then
    ( cd "$CODE_DIR" && uv run python html_report.py "$sid" )
  else
    ( cd "$CODE_DIR" && uv run python html_report.py )
  fi
}

run_tests() {
  ( cd "$CODE_DIR" && uv run pytest tests/ -v --no-header )
}

wipe() {
  rm -rf \
    "$CODE_DIR/state/sessions" \
    "$CODE_DIR/state/artifacts" \
    "$CODE_DIR/state/index.faiss" \
    "$CODE_DIR/state/index_ids.json" \
    "$CODE_DIR/state/memory.json" \
    "$CODE_DIR/.last_session_id" \
    "$SCRIPT_DIR/logs"
  mkdir -p "$CODE_DIR/state/sessions" "$SCRIPT_DIR/logs"
  echo "[assignment] wiped sessions, FAISS, memory, logs"
}

case "${1:-all}" in
  gateway)  start_gateway ;;
  report)   generate_report "${2:-}" ;;
  tests)    start_gateway; run_tests ;;
  wipe)     wipe ;;
  all)      start_gateway; run_all_tasks ;;
  laptops|ai_tools|hf_text_gen|cnc_training|1|2|3|4)
    start_gateway
    run_task "$1"
    ;;
  primary|"")
    start_gateway
    run_primary
    ;;
  *)
    echo "Usage: $0 [primary|all|laptops|hf_text_gen|report [sid]|tests|wipe|gateway]" >&2
    exit 2
    ;;
esac
