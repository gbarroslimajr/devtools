#!/usr/bin/ksh
###############################################################################
# decrypt_SOLAAR_v2.sh
#
# VERSION: 2.0 - Concurrency-safe implementation
#
# CHANGES FROM v1:
#   - Atomic lock using flock (eliminates race conditions)
#   - Separate lock for queue operations
#   - Trap handlers for automatic cleanup on termination
#   - Protected queue read/write operations
#
# REQUIREMENTS:
#   - flock command (util-linux package on Linux)
#
# - End-of-transfer from CFT for SOLAAR files (*.GPG)
# - Loads gpg_env.sh (paths, PASS, directories, owner, etc.)
# - Enqueues pending files
# - Processes one at a time (FIFO queue + atomic lock)
# - Creates LOG per execution
###############################################################################

# Script directory
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

###############################################################################
# 1. Load environment (gpg_env.sh)
#    - Defines: HOMEDIR, HOMEDIRGPG, LOGFILE, PASS, USER, USERGROUP etc.
#    - WE DO NOT USE INPUTFILE/OUTPUTFILE FROM FILE (only paths/credentials)
###############################################################################

ENV_FILE="$SCRIPT_DIR/gpg_env.sh"

if [ -f "$ENV_FILE" ]; then
  . "$ENV_FILE"
else
  echo "ERROR: Environment file '$ENV_FILE' not found!" >&2
  exit 1
fi

# Validate required variables after loading environment
REQUIRED_VARS="HOMEDIR HOMEDIRGPG PASS"
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
# 3. Working directories (based on gpg_env.sh)
###############################################################################
CFT_DIR="$HOMEDIR/cft"
RECV_DIR="$CFT_DIR/recv"
GNUPG_DIR="$HOMEDIRGPG"

QUEUE_FILE="$CFT_DIR/solaar_queue.lst"
LOCK_FILE="$CFT_DIR/solaar_process.lock"
QUEUE_LOCK_FILE="$CFT_DIR/solaar_queue.lock"

# Own log per execution
NOW=$(date +%Y%m%d_%H%M%S)
EXEC_LOG="$CFT_DIR/solaar_${NOW}.log"

OWNER_USER=${USER:-"appuser"}
OWNER_GROUP=${USERGROUP:-"APPGRP_QA"}

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

# Validate existence of critical directories
[ -d "$GNUPG_DIR" ] || {
  echo "ERROR: GPG directory does not exist: $GNUPG_DIR" >&2
  exit 1
}

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
  echo "$(date '+%Y-%m-%d %H:%M:%S') - $*" >> "$EXEC_LOG"
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
  while true; do
    FILE_IN_QUEUE=$(get_next_from_queue)

    # Empty result means queue is empty or error
    if [ -z "$FILE_IN_QUEUE" ]; then
      break
    fi

    decrypt_single_file "$FILE_IN_QUEUE"
  done

  # Release lock
  log "LOCK released: $LOCK_FILE"
  PROCESS_LOCK_HELD=0
  exec 200<&-
}

###############################################################################
# 9. Decrypt single file
###############################################################################
decrypt_single_file() {
  fname="$1"
  input_file="$RECV_DIR/$fname"
  output_file="$RECV_DIR/${fname%.[Gg][Pp][Gg]}.txt"

  log "Starting decrypt: $fname"

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

  gpg --homedir "$GNUPG_DIR" \
      --batch --yes --pinentry-mode=loopback \
      --output "$output_file" \
      --decrypt --passphrase "$PASS" \
      --no-mdc-warning --ignore-mdc-error \
      "$input_file" >> "$EXEC_LOG" 2>&1

  if [ $? -ne 0 ]; then
    log "ERROR decrypting: $fname"
    return 1
  fi

  chmod 664 "$output_file" 2>/dev/null
  chown "$OWNER_USER":"$OWNER_GROUP" "$output_file" 2>/dev/null

  log "Decrypt completed: $output_file"
  return 0
}

###############################################################################
# MAIN
###############################################################################
log "========================================================================"
log "Start decrypt_SOLAAR_v2.sh (concurrency-safe) - PID $$"

enqueue_pending_files
process_queue

log "End decrypt_SOLAAR_v2.sh"
log "========================================================================"

exit 0
