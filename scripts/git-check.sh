#!/usr/bin/env bash
# Verify Assignment 9 is safe to commit (no secrets, no session blobs staged).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

fail=0

echo "== git-check: Assignment 9 =="
echo "Root: $ROOT"
echo

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: not a git repository. Run: git init" >&2
  exit 1
fi

# Patterns that must never appear in the index
FORBIDDEN=(
  '.env'
  '**/.env'
  '**/.venv/**'
  '**/state/sessions/s9-*'
  '**/state/memory.json'
  '**/state/index.faiss'
  '**/logs/*.log'
  '**/logs/*_replay.html'
  '**/*.db'
)

echo "-- staged files (first 30) --"
git diff --cached --name-only | head -30
echo

echo "-- forbidden paths check --"
while IFS= read -r f; do
  case "$f" in
    *.env.example|*/.env.example) continue ;;
    *.env|*/.env|*/.env.*) echo "BLOCKED: $f"; fail=1 ;;
    */.venv/*|*/__pycache__/*) echo "BLOCKED: $f"; fail=1 ;;
    */state/sessions/s9-*|*/state/sessions/s8-*) echo "BLOCKED: $f"; fail=1 ;;
    */state/memory.json|*/state/index.faiss|*/state/index_ids.json) echo "BLOCKED: $f"; fail=1 ;;
    */logs/*.log|*/logs/*_replay.html) echo "BLOCKED: $f"; fail=1 ;;
    *.db) echo "BLOCKED: $f"; fail=1 ;;
  esac
done < <(git diff --cached --name-only)

echo "-- secret-like content in staged diff --"
if git diff --cached | grep -qiE '(api[_-]?key|secret|password|token)\s*=\s*[^$\s][^\s]{8,}'; then
  echo "BLOCKED: possible secret value in staged diff"
  fail=1
else
  echo "OK: no obvious secret literals in staged diff"
fi

echo
echo "-- untracked (should be mostly ignored runtime) --"
git status --short --untracked-files=all | grep '^??' | head -20 || true

echo
if [[ "$fail" -eq 0 ]]; then
  echo "PASS: safe to commit (still review 'git diff --cached' yourself)."
  exit 0
fi
echo "FAIL: fix blocked paths before committing." >&2
exit 1
