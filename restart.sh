#!/usr/bin/env bash
set -euo pipefail

# Resolve project root (the directory containing this script)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env from project root (preferred for secrets like OPENAI_API_KEY)
if [ -f .env ]; then
  # export every variable defined in .env
  set -a
  # shellcheck source=/dev/null
  . ./.env
  set +a
fi

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  . "venv/bin/activate"
else
  echo "[restart.sh] venv not found. Create it with: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

# =============================
# Service environment variables
# =============================

# LLM model selection
export CREWAI_MODEL="${CREWAI_MODEL:-openai/gpt-4o-mini}"
# Optional per‑agent overrides (uncomment to use)
# export RESEARCHER_MODEL="openai/gpt-4o-mini"
# export PLANNER_MODEL="openai/gpt-4o-mini"
# export REVIEWER_MODEL="openai/gpt-4o-mini"

# Telemetry (1 = opt out)
export CREWAI_TELEMETRY_OPT_OUT="${CREWAI_TELEMETRY_OPT_OUT:-1}"

# Log file path
export TRAVEL_LOG_FILE="${TRAVEL_LOG_FILE:-logs/travel.log}"

# Force CrewAI storage into project folder to avoid permission issues
export CREWAI_STORAGE_DIR="${CREWAI_STORAGE_DIR:-$PWD/.crewai}"

# Ensure logs directory exists
mkdir -p "$(dirname "$TRAVEL_LOG_FILE")"
mkdir -p "$CREWAI_STORAGE_DIR"

echo "[restart.sh] Using model: $CREWAI_MODEL"
echo "[restart.sh] Log file:   $TRAVEL_LOG_FILE"

# Run the CLI, forwarding any user args
python main.py --log-file "$TRAVEL_LOG_FILE" "$@"
