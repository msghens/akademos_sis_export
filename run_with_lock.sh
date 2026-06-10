#!/usr/bin/env bash
set -euo pipefail

LOCKFILE="/run/lock/akademos.lock"
LOGFILE="/home/mghens/akademos_sis_export/logs/lock.log"
MAX_LOG_SIZE=500000          # 500 KB
MAX_LOCK_AGE=86400           # 24 hours in seconds (86400). Change as needed.

timestamp() {
    date +"%Y-%m-%d %H:%M:%S"
}

rotate_logs() {
    if [ -f "$LOGFILE" ] && [ "$(stat -c%s "$LOGFILE")" -gt "$MAX_LOG_SIZE" ]; then
        mv "$LOGFILE" "${LOGFILE}.1"
        echo "$(timestamp) [INFO] Rotated lock log" > "$LOGFILE"
    fi
}

# Minimal cleanup — lockfile is NOT removed here
cleanup() {
    echo "$(timestamp) [INFO] Script exiting (PID $$)" >> "$LOGFILE"
}

trap cleanup EXIT INT TERM

rotate_logs

echo "$(timestamp) [INFO] Starting lock check" >> "$LOGFILE"

# --- PID-based + Age-based stale lock detection ---
if [ -f "$LOCKFILE" ]; then
    LOCKPID=$(cat "$LOCKFILE" 2>/dev/null || echo "invalid")

    if [[ "$LOCKPID" =~ ^[0-9]+$ ]]; then
        if kill -0 "$LOCKPID" 2>/dev/null; then
            # PID is alive → check age as safety net
            CURRENT_TIME=$(date +%s)
            LOCK_MTIME=$(stat -c %Y "$LOCKFILE" 2>/dev/null || echo 0)
            LOCK_AGE=$((CURRENT_TIME - LOCK_MTIME))

            if [ "$LOCK_AGE" -gt "$MAX_LOCK_AGE" ]; then
                echo "$(timestamp) [WARN] Lockfile PID $LOCKPID appears alive but is older than $((MAX_LOCK_AGE/3600)) hours — forcing removal" >> "$LOGFILE"
                rm -f "$LOCKFILE"
            else
                echo "$(timestamp) [WARN] Lockfile exists and PID $LOCKPID is still running (age: ${LOCK_AGE}s) — exiting" >> "$LOGFILE"
                exit 0
            fi
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
    echo "$(timestamp) [WARN] Another instance already holds the lock — exiting" >> "$LOGFILE"
    exit 0
fi

# Lock acquired — write our PID
echo $$ > "$LOCKFILE"
echo "$(timestamp) [INFO] Lock acquired successfully by PID $$" >> "$LOGFILE"

# === Your main job ===
cd /home/mghens/akademos_sis_export
source /home/mghens/akademos_sis_export/.venv/bin/activate
python ./akademos_sis_export.py >> logs/run.log 2>&1

echo "$(timestamp) [INFO] Job completed successfully (PID $$)" >> "$LOGFILE"