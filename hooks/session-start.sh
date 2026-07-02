#!/bin/bash
# Dark Factory session-start hook.
# Prints the using-skills meta-skill (discovery flowchart + operating behaviors)
# to stdout. Claude Code adds a SessionStart hook's plain stdout to context, so
# routing and the non-negotiable behaviors are live in every session — including
# after resume, /clear, and compaction.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
META_SKILL="$(dirname "$SCRIPT_DIR")/skills/using-skills/SKILL.md"

if [ -f "$META_SKILL" ]; then
  echo "Dark Factory loaded. Route the task with the discovery flowchart and apply the core operating behaviors at all times."
  echo
  cat "$META_SKILL"
else
  echo "Dark Factory: using-skills meta-skill not found at $META_SKILL. Skills remain available individually."
fi
