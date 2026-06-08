#!/usr/bin/env bash
set -euo pipefail

LOCKFILE="/run/lock/akademos.lock"
LOGFILE="/home/mghens/akademos_sis_export/logs/lock.log"
MAX_LOG_SIZE=500000 # 500 KB

timestamp() {
    date +"%Y-%m-%d %H:%M:%S"
}

rotate_logs() {
    if [ -f "$LOGFILE" ] && [ "$(stat -c%s "$LOGFILE")" -gt "$MAX_LOG_SIZE" ]; then
        mv "$LOGFILE" "${LOGFILE}.1"
        echo "$(timestamp) [INFO] Rotated lock log" > "$LOGFILE"
    fi
}

cleanup() {
    echo "$(timestamp) [INFO] Cleaning up lockfile" >> "$LOGFILE"
    rm -f "$LOCKFILE"
}

trap cleanup EXIT INT TERM

rotate_logs

echo "$(timestamp) [INFO] Checking for stale lockfile" >> "$LOGFILE"

# --- PID-based stale lock detection ---
if [ -f "$LOCKFILE" ]; then
    LOCKPID=$(cat "$LOCKFILE" 2>/dev/null || true)
    if [[ "$LOCKPID" =~ ^[0-9]+$ ]]; then
        if kill -0 "$LOCKPID" 2>/dev/null; then
            echo "$(timestamp) [WARN] Lockfile exists and PID $LOCKPID is alive — exiting" >> "$LOGFILE"
            exit 0
        else
            echo "$(timestamp) [WARN] Stale lockfile detected (PID $LOCKPID not running) — removing" >> "$LOGFILE"
            rm -f "$LOCKFILE"
        fi
    else
        echo "$(timestamp) [WARN] Lockfile exists but contains invalid PID — removing" >> "$LOGFILE"
        rm -f "$LOCKFILE"
    fi
fi

# Acquire lock using flock
exec 200>"$LOCKFILE"
if ! flock -n 200; then
    echo "$(timestamp) [WARN] Lock already held — exiting" >> "$LOGFILE"
    exit 0
fi

# Lock acquired — now write our PID
echo $$ > "$LOCKFILE"
echo "$(timestamp) [INFO] Lock acquired successfully by PID $$" >> "$LOGFILE"

# --- Your original job ---
cd /home/mghens/akademos_sis_export
source /home/mghens/akademos_sis_export/.venv/bin/activate
python ./akademos_sis_export.py >> logs/run.log 2>&1