#!/bin/bash
# Dark Factory session-start hook.
# Injects the using-skills meta-skill (discovery flowchart + operating behaviors)
# into every new session so routing and the non-negotiable behaviors are always live.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$(dirname "$SCRIPT_DIR")/skills"
META_SKILL="$SKILLS_DIR/using-skills/SKILL.md"

if ! command -v jq >/dev/null 2>&1; then
  echo '{"priority": "INFO", "message": "Dark Factory: jq not found on PATH; meta-skill not auto-injected. Install jq (brew install jq / apt-get install jq) to enable it. Skills remain available individually."}'
  exit 0
fi

if [ -f "$META_SKILL" ]; then
  CONTENT=$(cat "$META_SKILL")
  jq -cn --arg message "Dark Factory loaded. Route the task with the discovery flowchart and apply the core operating behaviors at all times.

$CONTENT" '{priority: "IMPORTANT", message: $message}'
else
  echo '{"priority": "INFO", "message": "Dark Factory: using-skills meta-skill not found. Skills may still be available individually."}'
fi
