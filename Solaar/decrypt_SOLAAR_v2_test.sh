#!/bin/bash
###############################################################################
# decrypt_SOLAAR_v2_test.sh
#
# VERSION: 2.1-TEST - Dry-run version for concurrency testing
#
# DIFFERENCES FROM PRODUCTION:
#   - DRY_RUN mode: simulates GPG decrypt with sleep + cp
#   - Loads gpg_env_test.sh instead of gpg_env.sh
#   - SLEEP_TIME configurable for testing (default: 1 second)
#   - Detailed timestamps in logs
#   - Uses /bin/bash for better compatibility with test environment
#   - Fixed output file name (CAR_OFSAPAC_REV.txt - parametrizable)
#   - Wait for output file to be processed before processing next GPG
#
# USAGE:
#   ./decrypt_SOLAAR_v2_test.sh [--sleep N]
#   Options:
#     --sleep N : Set sleep time in seconds (default: 1)
#
# CONFIGURATION:
#   - OUTPUT_FILE_NAME: Name of output file (default: CAR_OFSAPAC_REV.txt)
#     Can be overridden by setting environment variable before execution
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
# 3. Output file configuration (parametrizable)
###############################################################################
OUTPUT_FILE_NAME="${OUTPUT_FILE_NAME:-CAR_OFSAPAC_REV.txt}"
POLL_INTERVAL=5
MAX_WAIT_TIME=600

###############################################################################
# 4. Working directories (based on gpg_env_test.sh)
###############################################################################
CFT_DIR="$HOMEDIR/cft"
RECV_DIR="$CFT_DIR/recv"
OUTPUT_FILE="$RECV_DIR/$OUTPUT_FILE_NAME"

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
# 5. Cleanup and trap handlers
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
# 6. Directory validation and setup
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
# 7. Wait for output file to be processed
###############################################################################
wait_for_output_file() {
  local elapsed=0
  local start_time=$(date +%s)

  while [ -f "$OUTPUT_FILE" ]; do
    if [ $elapsed -ge $MAX_WAIT_TIME ]; then
      log "ERROR: Timeout waiting for $OUTPUT_FILE to disappear (${MAX_WAIT_TIME}s)"
      return 1
    fi

    log "Waiting for $OUTPUT_FILE to be processed (elapsed: ${elapsed}s)..."
    sleep $POLL_INTERVAL
    elapsed=$(($(date +%s) - start_time))
  done

  log "Output file $OUTPUT_FILE disappeared, ready to process next GPG file"
  return 0
}

###############################################################################
# 8. Enqueue pending files (with queue lock protection)
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

      # Enqueue if not already in queue (protected by lock)
      if ! grep -qx "$fname" "$QUEUE_FILE" 2>/dev/null; then
        echo "$fname" >> "$QUEUE_FILE"
        log "File enqueued: $fname"
      fi
    done
  ) 201>"$QUEUE_LOCK_FILE"
}

###############################################################################
# 9. Get next file from queue (atomic operation)
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
# 10. Process queue with atomic lock (flock)
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

    # Wait for output file to be processed before processing next GPG file
    if ! wait_for_output_file; then
      log "WARN: Timeout waiting for output file. Skipping file: $FILE_IN_QUEUE"
      continue
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
# 11. Decrypt single file (DRY-RUN: simulates with sleep + cp)
###############################################################################
decrypt_single_file() {
  fname="$1"
  input_file="$RECV_DIR/$fname"

  log "Starting decrypt (DRY-RUN): $fname -> $OUTPUT_FILE"
  local start_time=$(date +%s.%3N)

  if [ ! -f "$input_file" ]; then
    log "ERROR: File not found: $input_file"
    return 1
  fi

  # Remove output file if it exists (should not happen after wait_for_output_file, but safety check)
  rm -f "$OUTPUT_FILE" 2>/dev/null

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
  } > "$OUTPUT_FILE"

  local end_time=$(date +%s.%3N)
  local duration=$(echo "$end_time - $start_time" | bc)

  if [ $? -ne 0 ]; then
    log "ERROR decrypting (DRY-RUN): $fname"
    return 1
  fi

  chmod 664 "$OUTPUT_FILE" 2>/dev/null

  log "Decrypt completed (DRY-RUN): $fname -> $OUTPUT_FILE (${duration}s)"
  return 0
}

###############################################################################
# MAIN
###############################################################################
log "========================================================================"
log "Start decrypt_SOLAAR_v2_test.sh (DRY-RUN) - PID $$"
log "Output file: $OUTPUT_FILE"
log "Poll interval: ${POLL_INTERVAL}s, Max wait: ${MAX_WAIT_TIME}s"
log "SLEEP_TIME: ${SLEEP_TIME}s"
log "HOMEDIR: $HOMEDIR"
log "RECV_DIR: $RECV_DIR"

enqueue_pending_files
process_queue

log "End decrypt_SOLAAR_v2_test.sh"
log "========================================================================"

exit 0

