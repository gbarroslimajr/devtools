#!/bin/bash
###############################################################################
# decrypt_SOLAAR_v2_test.sh
#
# VERSION: 2.0-TEST - Dry-run version for concurrency testing
#
# DIFFERENCES FROM PRODUCTION:
#   - DRY_RUN mode: simulates GPG decrypt with sleep + cp
#   - Loads gpg_env_test.sh instead of gpg_env.sh
#   - SLEEP_TIME configurable for testing (default: 1 second)
#   - Detailed timestamps in logs
#   - Uses /bin/bash for better compatibility with test environment
#
# USAGE:
#   ./decrypt_SOLAAR_v2_test.sh [--sleep N]
#   Options:
#     --sleep N : Set sleep time in seconds (default: 1)
#
###############################################################################

# Default sleep time for simulating decrypt
SLEEP_TIME=${SLEEP_TIME:-1}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --sleep)
      SLEEP_TIME="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

# Script directory
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

###############################################################################
# 1. Load TEST environment (gpg_env_test.sh)
###############################################################################

ENV_FILE="$SCRIPT_DIR/tests/gpg_env_test.sh"

if [ -f "$ENV_FILE" ]; then
  . "$ENV_FILE"
else
  echo "ERROR: Test environment file '$ENV_FILE' not found!" >&2
  exit 1
fi

# Validate required variables after loading environment
REQUIRED_VARS="HOMEDIR"
for var in $REQUIRED_VARS; do
  eval "value=\$$var"
  if [ -z "$value" ]; then
    echo "ERROR: Required variable '$var' not defined in $ENV_FILE" >&2
    exit 1
  fi
done

###############################################################################
# 2. Check flock availability
###############################################################################
if ! command -v flock >/dev/null 2>&1; then
  echo "ERROR: flock command not found. Install util-linux package." >&2
  exit 1
fi

###############################################################################
# 3. Working directories (based on gpg_env_test.sh)
###############################################################################
CFT_DIR="$HOMEDIR/cft"
RECV_DIR="$CFT_DIR/recv"

QUEUE_FILE="$CFT_DIR/solaar_queue.lst"
LOCK_FILE="$CFT_DIR/solaar_process.lock"
QUEUE_LOCK_FILE="$CFT_DIR/solaar_queue.lock"

# Own log per execution with microseconds for better tracking
NOW=$(date +%Y%m%d_%H%M%S)
EXEC_LOG="$CFT_DIR/solaar_test_${NOW}_$$.log"

OWNER_USER=${USER:-$(whoami)}
OWNER_GROUP=${USERGROUP:-$(id -gn)}

# Track if we hold the process lock
PROCESS_LOCK_HELD=0

###############################################################################
# 4. Cleanup and trap handlers
###############################################################################
cleanup() {
  local exit_code=${1:-0}

  # Release process lock if we hold it
  if [ "$PROCESS_LOCK_HELD" -eq 1 ]; then
    log "Releasing process lock (cleanup)"
    exec 200<&- 2>/dev/null
    PROCESS_LOCK_HELD=0
  fi

  exit $exit_code
}

# Trap signals for graceful cleanup
trap 'log "Received INT/TERM/HUP signal"; cleanup 1' INT TERM HUP
trap 'cleanup 0' EXIT

###############################################################################
# 5. Directory validation and setup
###############################################################################

# Create directories that may not exist (with correct permissions)
[ -d "$CFT_DIR" ] || {
  mkdir -p "$CFT_DIR" || {
    echo "ERROR: Could not create CFT directory: $CFT_DIR" >&2
    exit 1
  }
}

[ -d "$RECV_DIR" ] || {
  mkdir -p "$RECV_DIR" || {
    echo "ERROR: Could not create receive directory: $RECV_DIR" >&2
    exit 1
  }
}

umask 002

log() {
  local timestamp=$(date '+%Y-%m-%d %H:%M:%S.%3N')
  echo "$timestamp [PID $$] - $*" >> "$EXEC_LOG"
  # Also echo to stdout for real-time monitoring during tests
  echo "$timestamp [PID $$] - $*"
}

###############################################################################
# 6. Enqueue pending files (with queue lock protection)
###############################################################################
enqueue_pending_files() {
  # Use flock with subshell for queue operations
  (
    flock -w 5 201 || {
      log "WARN: Could not acquire queue lock for enqueue. Skipping."
      exit 1
    }

    [ -f "$QUEUE_FILE" ] || touch "$QUEUE_FILE"

    for f in "$RECV_DIR"/*.GPG "$RECV_DIR"/*.gpg; do
      [ ! -f "$f" ] && continue

      fname=$(basename "$f")
      out_txt="$RECV_DIR/${fname%.[Gg][Pp][Gg]}.txt"

      # If corresponding TXT already exists, do not enqueue
      if [ -f "$out_txt" ]; then
        log "File already processed, TXT found. Ignoring: $fname"
        continue
      fi

      # Enqueue if not already in queue (protected by lock)
      if ! grep -qx "$fname" "$QUEUE_FILE" 2>/dev/null; then
        echo "$fname" >> "$QUEUE_FILE"
        log "File enqueued: $fname"
      fi
    done
  ) 201>"$QUEUE_LOCK_FILE"
}

###############################################################################
# 7. Get next file from queue (atomic operation)
###############################################################################
get_next_from_queue() {
  # Use flock with subshell - output is captured by caller
  (
    flock -w 5 201 || {
      echo ""
      exit 1
    }

    if [ ! -s "$QUEUE_FILE" ]; then
      echo ""
      exit 0
    fi

    # Read first line
    result=$(head -n 1 "$QUEUE_FILE")

    # Remove first line atomically (while holding lock)
    tail -n +2 "$QUEUE_FILE" > "${QUEUE_FILE}.tmp" 2>/dev/null
    mv -f "${QUEUE_FILE}.tmp" "$QUEUE_FILE"

    echo "$result"
  ) 201>"$QUEUE_LOCK_FILE"
}

###############################################################################
# 8. Process queue with atomic lock (flock)
###############################################################################
process_queue() {
  # Open lock file on file descriptor 200
  exec 200>"$LOCK_FILE"

  # Try to acquire exclusive lock (non-blocking)
  if ! flock -n 200; then
    log "Another instance is processing. This instance will only enqueue."
    exec 200<&-
    return 0
  fi

  # We now hold the lock
  PROCESS_LOCK_HELD=1
  log "LOCK acquired: $LOCK_FILE (PID $$)"

  # Process all items in queue
  local processed_count=0
  while true; do
    FILE_IN_QUEUE=$(get_next_from_queue)

    # Empty result means queue is empty or error
    if [ -z "$FILE_IN_QUEUE" ]; then
      break
    fi

    decrypt_single_file "$FILE_IN_QUEUE"
    ((processed_count++))
  done

  # Release lock
  log "LOCK released: $LOCK_FILE (processed $processed_count files)"
  PROCESS_LOCK_HELD=0
  exec 200<&-
}

###############################################################################
# 9. Decrypt single file (DRY-RUN: simulates with sleep + cp)
###############################################################################
decrypt_single_file() {
  fname="$1"
  input_file="$RECV_DIR/$fname"
  output_file="$RECV_DIR/${fname%.[Gg][Pp][Gg]}.txt"

  log "Starting decrypt (DRY-RUN): $fname"
  local start_time=$(date +%s.%3N)

  if [ ! -f "$input_file" ]; then
    log "ERROR: File not found: $input_file"
    return 1
  fi

  # Double-check: if output already exists, skip (safety net)
  if [ -f "$output_file" ]; then
    log "WARN: Output file already exists, skipping: $output_file"
    return 0
  fi

  rm -f "$output_file" 2>/dev/null

  ###########################################################################
  # DRY-RUN MODE: Simulate GPG decrypt with sleep + cp
  ###########################################################################
  log "DRY-RUN: Simulating decrypt with sleep ${SLEEP_TIME}s..."
  sleep "$SLEEP_TIME"

  # Copy content (simulating decryption)
  # Add metadata to output to track which PID processed it
  {
    echo "# Decrypted by PID $$ at $(date '+%Y-%m-%d %H:%M:%S')"
    echo "# Original file: $fname"
    echo "# Sleep time: ${SLEEP_TIME}s"
    echo "---"
    cat "$input_file"
  } > "$output_file"

  local end_time=$(date +%s.%3N)
  local duration=$(echo "$end_time - $start_time" | bc)

  if [ $? -ne 0 ]; then
    log "ERROR decrypting (DRY-RUN): $fname"
    return 1
  fi

  chmod 664 "$output_file" 2>/dev/null

  log "Decrypt completed (DRY-RUN): $output_file (${duration}s)"
  return 0
}

###############################################################################
# MAIN
###############################################################################
log "========================================================================"
log "Start decrypt_SOLAAR_v2_test.sh (DRY-RUN) - PID $$"
log "SLEEP_TIME: ${SLEEP_TIME}s"
log "HOMEDIR: $HOMEDIR"
log "RECV_DIR: $RECV_DIR"

enqueue_pending_files
process_queue

log "End decrypt_SOLAAR_v2_test.sh"
log "========================================================================"

exit 0

