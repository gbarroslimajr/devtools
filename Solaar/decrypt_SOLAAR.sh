#!/usr/bin/ksh
###############################################################################
# decrypt_SOLAAR.sh  (replaces decrypt.sh)
#
# - End-of-transfer from CFT for SOLAAR files (*.GPG)
# - Loads gpg_env.sh (paths, PASS, directories, owner, etc.)
# - Enqueues pending files
# - Processes one at a time (FIFO queue + lock)
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
# 2. Working directories (based on gpg_env.sh)
###############################################################################
CFT_DIR="$HOMEDIR/cft"
RECV_DIR="$CFT_DIR/recv"
GNUPG_DIR="$HOMEDIRGPG"

QUEUE_FILE="$CFT_DIR/solaar_queue.lst"
LOCK_FILE="$CFT_DIR/solaar_queue.lock"

# Own log per execution
NOW=$(date +%Y%m%d_%H%M%S)
EXEC_LOG="$CFT_DIR/solaar_${NOW}.log"

OWNER_USER=${USER:-"appuser"}
OWNER_GROUP=${USERGROUP:-"APPGRP_QA"}

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
# 3. Enqueue pending files
###############################################################################
enqueue_pending_files() {

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

    # Enqueue if not already in queue
    if ! grep -qx "$fname" "$QUEUE_FILE" 2>/dev/null; then
      echo "$fname" >> "$QUEUE_FILE"
      log "File enqueued: $fname"
    fi
  done
}

###############################################################################
# 4. Process queue with lock
###############################################################################
process_queue() {

  if [ -f "$LOCK_FILE" ]; then
    log "Lock found. Another instance is running. Exiting."
    return 0
  fi

  echo $$ > "$LOCK_FILE"
  log "LOCK created: $LOCK_FILE (PID $$)"

  while [ -s "$QUEUE_FILE" ]; do
    FILE_IN_QUEUE=$(head -n 1 "$QUEUE_FILE")

    tail -n +2 "$QUEUE_FILE" > "${QUEUE_FILE}.tmp" 2>/dev/null
    mv -f "${QUEUE_FILE}.tmp" "$QUEUE_FILE"

    [ -n "$FILE_IN_QUEUE" ] && decrypt_single_file "$FILE_IN_QUEUE"
  done

  rm -f "$LOCK_FILE"
  log "LOCK removed."
}

###############################################################################
# 5. Decrypt single file
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
log "Start decrypt_SOLAAR.sh — loaded via gpg_env.sh"

enqueue_pending_files
process_queue

log "End decrypt_SOLAAR.sh"
log "========================================================================"

exit 0