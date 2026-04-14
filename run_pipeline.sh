#!/usr/bin/env bash
# run_pipeline.sh — Start the Knowledge Base background pipeline.
#
# Launches two processes:
#   1. feed_poller.py   — polls RSS/Atom feeds, writes entries to raw/inbox/feeds/
#   2. inbox_watcher.py — watches raw/inbox/ and ingests new files into the vault
#
# Both run in the background. PIDs are written to metadata/.pipeline.pid so the
# processes can be stopped cleanly with:
#
#   kill $(cat metadata/.pipeline.pid)
#
# Usage:
#   ./run_pipeline.sh              # start with defaults
#   ./run_pipeline.sh --stop       # stop running pipeline
#   ./run_pipeline.sh --status     # show whether pipeline is running

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${SCRIPT_DIR}/.venv/bin/python"
PID_FILE="${SCRIPT_DIR}/metadata/.pipeline.pid"
LOG_DIR="${SCRIPT_DIR}/logs"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log() { echo "[$(date '+%H:%M:%S')] $*"; }

ensure_python() {
    if [[ ! -x "${PYTHON}" ]]; then
        echo "ERROR: Python not found at ${PYTHON}" >&2
        echo "       Activate the venv or set PYTHON to the correct interpreter." >&2
        exit 1
    fi
}

pids_running() {
    [[ -f "${PID_FILE}" ]] || return 1
    local all_running=true
    while IFS= read -r pid; do
        [[ -n "${pid}" ]] || continue
        kill -0 "${pid}" 2>/dev/null || all_running=false
    done < "${PID_FILE}"
    [[ "${all_running}" == "true" ]]
}

# ---------------------------------------------------------------------------
# --stop
# ---------------------------------------------------------------------------

do_stop() {
    if [[ ! -f "${PID_FILE}" ]]; then
        log "Pipeline is not running (no PID file found)."
        return 0
    fi
    log "Stopping pipeline..."
    while IFS= read -r pid; do
        [[ -n "${pid}" ]] || continue
        if kill -0 "${pid}" 2>/dev/null; then
            kill "${pid}" && log "  Stopped PID ${pid}"
        else
            log "  PID ${pid} already gone"
        fi
    done < "${PID_FILE}"
    rm -f "${PID_FILE}"
    log "Done."
}

# ---------------------------------------------------------------------------
# --status
# ---------------------------------------------------------------------------

do_status() {
    if pids_running; then
        log "Pipeline is running."
        while IFS= read -r pid; do
            [[ -n "${pid}" ]] || continue
            echo "  PID ${pid}: $(ps -p "${pid}" -o comm= 2>/dev/null || echo 'unknown')"
        done < "${PID_FILE}"
    else
        log "Pipeline is not running."
    fi
}

# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------

do_start() {
    ensure_python

    if pids_running; then
        log "Pipeline is already running. Use --stop to stop it first."
        exit 1
    fi

    mkdir -p "${LOG_DIR}" "${SCRIPT_DIR}/metadata"

    log "Starting feed_poller.py..."
    "${PYTHON}" "${SCRIPT_DIR}/scripts/feed_poller.py" \
        >> "${LOG_DIR}/feed_poller.log" 2>&1 &
    POLLER_PID=$!

    log "Starting inbox_watcher.py..."
    "${PYTHON}" "${SCRIPT_DIR}/scripts/inbox_watcher.py" \
        >> "${LOG_DIR}/inbox_watcher.log" 2>&1 &
    WATCHER_PID=$!

    printf '%s\n%s\n' "${POLLER_PID}" "${WATCHER_PID}" > "${PID_FILE}"

    log "Pipeline started."
    log "  feed_poller  PID : ${POLLER_PID}  -> logs/feed_poller.log"
    log "  inbox_watcher PID: ${WATCHER_PID}  -> logs/inbox_watcher.log"
    log "  PID file         : metadata/.pipeline.pid"
    log ""
    log "Stop with:  ./run_pipeline.sh --stop"
    log "Status:     ./run_pipeline.sh --status"
}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

case "${1:-}" in
    --stop)   do_stop   ;;
    --status) do_status ;;
    "")       do_start  ;;
    *)
        echo "Usage: $0 [--stop | --status]" >&2
        exit 1
        ;;
esac
