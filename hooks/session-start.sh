#!/bin/bash
# The hook routes opted-in sessions; durable execution belongs to the worker.
set -eu
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MARKER="${PWD}/.darkfactory"
if [ -f "$MARKER" ]; then
  CHOICE="$(tr -d '[:space:]' < "$MARKER")"
  case "$CHOICE" in
    ignore) exit 0 ;;
    engage)
      printf '%s\n' 'DarkFactory routing engaged. Runtime approval and final human acceptance remain separate.'
      cat "$(dirname "$SCRIPT_DIR")/skills/using-skills/SKILL.md"
      ;;
    *) printf '%s\n' 'DarkFactory marker is invalid; clarify engage / ignore before activating.' ;;
  esac
else
  printf '%s\n' 'DarkFactory is available. Ask once whether to engage / ignore before loading its workflow.'
fi
