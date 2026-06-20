#!/usr/bin/env bash
# Session 10 Computer-Use assignment runner.
#
# Runs three canonical desktop tasks (plus optional vision demo) through the
# full orchestrator (flow.py). Each task records a cua-driver trajectory under
# state/sessions/<sid>/computer/.
#
# Prerequisites:
#   - V9 gateway on :8109  (cd ../llm_gatewayV9 && uv run main.py)
#   - cua-driver installed and AT-SPI OK  (cua-driver doctor)
#   - X11 session with DISPLAY set
#   - VS Code snap installed for the Electron/CDP task
#
# Usage:
#   ./run_computer_assignment.sh           run all three required tasks
#   ./run_computer_assignment.sh calc42    deterministic Calculator (Layer 2a)
#   ./run_computer_assignment.sh calca11y  Calculator keypad via AX+LLM (Layer 2b)
#   ./run_computer_assignment.sh noteread   Layer-1 file extract (optional)
#   ./run_computer_assignment.sh vscodefiles  VS Code + electron_debugging_port
#   ./run_computer_assignment.sh calcvision   vision keypad task (Layer 3)
#   ./run_computer_assignment.sh direct-calc42  bypass planner (skill-only smoke)
#   ./run_computer_assignment.sh tests     pytest computer tests only

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CODE_DIR="$SCRIPT_DIR/code"
LOG_DIR="$SCRIPT_DIR/logs/computer"
NOTE_FILE="${HOME}/assignment9-note.txt"
PROJECT_DIR="${HOME}/Documents/workspace/Assignment-9"

mkdir -p "$LOG_DIR"

usage() {
  sed -n '2,22p' "$0"
}

precheck() {
  if ! curl -sf http://localhost:8109/v1/routers >/dev/null; then
    echo "[computer] V9 gateway is not responding at http://localhost:8109" >&2
    echo "           start it:  cd $SCRIPT_DIR/../llm_gatewayV9 && uv run main.py" >&2
    exit 1
  fi
  if ! command -v cua-driver >/dev/null; then
    echo "[computer] cua-driver not found on PATH" >&2
    exit 1
  fi
  cua-driver status >/dev/null 2>&1 || cua-driver serve &
  sleep 1
}

prepare_note() {
  cat > "$NOTE_FILE" <<'EOF'
Session 10 assignment note — Layer 1 file extract demo.
The quick brown fox jumps over the lazy dog.
EOF
  echo "[computer] wrote $NOTE_FILE"
}

query_for() {
  case "$1" in
    calc42)      echo "Open the Calculator app and compute 42 times 567. Report the numeric result shown on the display." ;;
    calca11y)    echo "Open Calculator in basic mode. Click the on-screen keypad buttons to compute 7 plus 3 (press 7, then plus, then 3, then equals). Do not type the expression with the keyboard. Report the numeric result on the display." ;;
    noteread)    echo "Read the file ~/assignment9-note.txt and return its full text verbatim." ;;
    vscodefiles) echo "Open Visual Studio Code on the Assignment-9 project folder with remote debugging enabled, then list the top 3 file or folder names visible in the Explorer sidebar." ;;
    calcvision)  echo "Open Calculator and compute 99 times 99 by interacting with the on-screen buttons (do not use a typed expression shortcut). Report the result shown on the display." ;;
    *) return 1 ;;
  esac
}

describe() {
  case "$1" in
    calc42)
      cat <<'EOF'
TASK: calc42  (zero-vision — Layer 2a deterministic)
  App       gnome-calculator
  Workflow  calculator-eval (expression parsed from goal, click =)
  Expected  path=deterministic, result line in content
EOF
      ;;
    calca11y)
      cat <<'EOF'
TASK: calca11y  (Layer 2b — AX tree + cheap text LLM)
  App       gnome-calculator --mode=basic
  Goal      click keypad 7 + 3 = (no typed expression shortcut)
  Expected  path=a11y (may escalate to vision if AX fails)
EOF
      ;;
    noteread)
      cat <<'EOF'
TASK: noteread  (zero-vision — Layer 1 file extract)
  App       desktop (no interaction)
  Files     ~/assignment9-note.txt
  Expected  path=extract, verbatim note text
EOF
      ;;
    vscodefiles)
      cat <<'EOF'
TASK: vscodefiles  (Electron CDP — metadata.electron_debugging_port=9222)
  App       Visual Studio Code (relaunched with --remote-debugging-port=9222)
  Goal      top 3 Explorer sidebar entries via CDP execute_javascript
  Expected  path=electron
EOF
      ;;
    calcvision)
      cat <<'EOF'
TASK: calcvision  (vision/a11y — optional fourth demo)
  App       gnome-calculator
  Goal      click keypad buttons for 99×99 (no workflow shortcut)
  Expected  path=a11y or path=vision
EOF
      ;;
  esac
}

run_flow() {
  local id="$1"
  local q log sid
  q=$(query_for "$id") || { echo "[computer] unknown task: $id" >&2; usage; exit 2; }

  echo
  echo "===================================================================="
  describe "$id"
  echo "===================================================================="
  log="$LOG_DIR/$id.log"
  ( cd "$CODE_DIR" && uv run python flow.py "$q" 2>&1 ) | tee "$log"

  sid=$(ls -t "$CODE_DIR/state/sessions" 2>/dev/null | head -1)
  if [[ -n "$sid" ]]; then
    echo "$id" > "$CODE_DIR/state/sessions/$sid/task_key.txt"
    describe "$id" > "$CODE_DIR/state/sessions/$sid/architecture_note.txt"
    python3 "$SCRIPT_DIR/replay_viewer.py" "$sid" || true
    echo
    echo "[computer] log        -> $log"
    echo "[computer] session    -> $CODE_DIR/state/sessions/$sid/"
    echo "[computer] trajectory -> $CODE_DIR/state/sessions/$sid/computer/"
    echo "[computer] report     -> $CODE_DIR/state/sessions/$sid/report.html"
  fi
}

run_direct() {
  local id="$1"
  echo
  echo "===================================================================="
  echo "DIRECT skill smoke (no planner) — $id"
  echo "===================================================================="
  ( cd "$CODE_DIR" && uv run python run_computer_direct.py "$id" 2>&1 ) | tee "$LOG_DIR/direct-$id.log"
}

run_pytest() {
  ( cd "$CODE_DIR" && uv run pytest tests/test_computer.py tests/test_demos.py -v --no-header )
}

case "${1:-all}" in
  -h|--help|help) usage; exit 0 ;;
  tests) precheck; run_pytest ;;
  prepare) prepare_note ;;
  direct-calc42) precheck; prepare_note; run_direct calc42 ;;
  direct-noteread) precheck; prepare_note; run_direct noteread ;;
  direct-vscodefiles) precheck; prepare_note; run_direct vscodefiles ;;
  calc42|calca11y|noteread|vscodefiles|calcvision)
    precheck
    prepare_note
    run_flow "$1"
    ;;
  all)
    precheck
    prepare_note
    for id in calc42 calca11y vscodefiles calcvision; do
      run_flow "$id"
    done
    echo
    echo "[computer] Done — four tasks: 2a deterministic, 2b a11y, electron, vision."
    echo "[computer] Optional Layer-1 extract: ./run_computer_assignment.sh noteread"
    echo "[computer] See SESSION10_README.md for submission checklist."
    ;;
  *)
    echo "[computer] unknown command: $1" >&2
    usage
    exit 2
    ;;
esac
