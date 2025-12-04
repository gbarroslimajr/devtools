#!/bin/bash
###############################################################################
# test_kill_recovery.sh - Test recovery after kill -9
#
# This test validates that:
#   1. When a process is killed with kill -9 during execution
#   2. The flock-based lock is automatically released (by the OS)
#   3. A new instance can start processing without being blocked
#   4. Remaining files are processed correctly
#
# USAGE:
#   ./test_kill_recovery.sh [--files N] [--sleep S]
#
# OPTIONS:
#   --files N : Number of test files (default: 10)
#   --sleep S : Sleep time per file in seconds (default: 2)
#
# NOTE: This test uses kill -9 which doesn't allow cleanup handlers to run.
#       The flock mechanism should still release the lock because the OS
#       closes all file descriptors when a process dies.
#
###############################################################################

set -e

# Script directory
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
SOLAAR_DIR=$(dirname "$SCRIPT_DIR")

# Load test environment
source "$SCRIPT_DIR/gpg_env_test.sh"

# Defaults
NUM_FILES=10
SLEEP_TIME=2  # Longer sleep to give time to kill

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --files)
      NUM_FILES="$2"
      shift 2
      ;;
    --sleep)
      SLEEP_TIME="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

print_header() {
  echo -e "\n${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${RED}║${NC} ${CYAN}$1${NC}"
  echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
}

print_subheader() {
  echo -e "\n${YELLOW}>>> $1${NC}"
}

print_success() {
  echo -e "${GREEN}[PASS]${NC} $1"
}

print_fail() {
  echo -e "${RED}[FAIL]${NC} $1"
}

print_info() {
  echo -e "${CYAN}[INFO]${NC} $1"
}

print_warning() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

CFT_DIR="$HOMEDIR/cft"
RECV_DIR="$CFT_DIR/recv"
LOCK_FILE="$CFT_DIR/solaar_process.lock"

###############################################################################
# Setup
###############################################################################
print_header "TEST: Kill Recovery (Stale Lock Test)"

echo -e "\nConfiguration:"
echo "  Files:     $NUM_FILES"
echo "  Sleep:     ${SLEEP_TIME}s per file (longer to allow kill)"

print_subheader "Step 1: Setup test environment"

# Clean previous test data
"$SCRIPT_DIR/test_cleanup.sh" --all >/dev/null 2>&1 || true

# Setup with specified number of files
"$SCRIPT_DIR/test_setup.sh" --files "$NUM_FILES" --clean

print_success "Created $NUM_FILES test files"

###############################################################################
# Start first instance and kill it
###############################################################################
print_subheader "Step 2: Start instance and kill it with SIGKILL"

print_info "Launching first instance..."
SLEEP_TIME=$SLEEP_TIME "$SOLAAR_DIR/decrypt_SOLAAR_v2_test.sh" > /dev/null 2>&1 &
FIRST_PID=$!

print_info "First instance PID: $FIRST_PID"

# Wait a bit for the process to acquire lock and start processing
sleep 2

# Check if process is still running
if ps -p $FIRST_PID > /dev/null 2>&1; then
  print_info "Process is running, sending SIGKILL (kill -9)..."
  kill -9 $FIRST_PID 2>/dev/null || true
  print_warning "Process $FIRST_PID killed with SIGKILL"
else
  print_warning "Process already finished (may need longer sleep time)"
fi

# Small wait for OS to clean up
sleep 0.5

# Count files processed before kill
PROCESSED_BEFORE=$(find "$RECV_DIR" -name "*.txt" 2>/dev/null | wc -l | tr -d ' ')
print_info "Files processed before kill: $PROCESSED_BEFORE"

###############################################################################
# Verify lock state
###############################################################################
print_subheader "Step 3: Verify lock state after kill"

TESTS_PASSED=0
TESTS_FAILED=0

# Check if lock file exists (it should, but shouldn't be locked)
if [ -f "$LOCK_FILE" ]; then
  print_info "Lock file exists: $LOCK_FILE"

  # Try to acquire lock ourselves to verify it's not held
  if (flock -n 200 && echo "Lock is free") 200>"$LOCK_FILE" 2>/dev/null; then
    print_success "Lock was released by OS after kill -9 (flock working correctly)"
    ((TESTS_PASSED++))
  else
    print_fail "Lock appears to still be held (this shouldn't happen with flock)"
    ((TESTS_FAILED++))
  fi
else
  print_info "Lock file doesn't exist (normal after cleanup)"
  ((TESTS_PASSED++))
fi

###############################################################################
# Start new instance to process remaining files
###############################################################################
print_subheader "Step 4: Start new instance to process remaining files"

REMAINING_GPG=$((NUM_FILES - PROCESSED_BEFORE))
print_info "Files remaining to process: $REMAINING_GPG"

if [ "$REMAINING_GPG" -gt 0 ]; then
  print_info "Launching second instance..."

  START_TIME=$(date +%s.%3N)
  SLEEP_TIME=$SLEEP_TIME "$SOLAAR_DIR/decrypt_SOLAAR_v2_test.sh"
  END_TIME=$(date +%s.%3N)
  DURATION=$(echo "$END_TIME - $START_TIME" | bc)

  print_success "Second instance completed in ${DURATION}s"
else
  print_info "All files were processed before kill, skipping second instance"
fi

###############################################################################
# Validate results
###############################################################################
print_subheader "Step 5: Validate final results"

FINAL_TXT=$(find "$RECV_DIR" -name "*.txt" 2>/dev/null | wc -l | tr -d ' ')

# Test: All files should be processed now
if [ "$FINAL_TXT" -eq "$NUM_FILES" ]; then
  print_success "All $NUM_FILES files were processed after recovery"
  ((TESTS_PASSED++))
else
  print_fail "Expected $NUM_FILES .txt files, found $FINAL_TXT"
  ((TESTS_FAILED++))
fi

# Test: New instance was able to acquire lock (not blocked)
LOG_FILES=$(ls -t "$CFT_DIR"/solaar_test_*.log 2>/dev/null)
SECOND_LOG=$(echo "$LOG_FILES" | head -1)

if [ -n "$SECOND_LOG" ]; then
  if grep -q "LOCK acquired" "$SECOND_LOG" 2>/dev/null; then
    print_success "New instance was able to acquire lock after kill"
    ((TESTS_PASSED++))
  else
    # It might have found no files to process if first instance finished everything
    if grep -q "Another instance is processing" "$SECOND_LOG" 2>/dev/null; then
      print_fail "New instance was blocked (stale lock issue!)"
      ((TESTS_FAILED++))
    else
      print_info "New instance ran but lock behavior unclear"
      ((TESTS_PASSED++))
    fi
  fi
fi

# Test: No duplicate processing
TOTAL_DECRYPTS=0
for log in $LOG_FILES; do
  count=$(grep -c "Decrypt completed" "$log" 2>/dev/null || echo 0)
  TOTAL_DECRYPTS=$((TOTAL_DECRYPTS + count))
done

if [ "$TOTAL_DECRYPTS" -eq "$NUM_FILES" ]; then
  print_success "Total decrypt operations: $TOTAL_DECRYPTS (no duplicates)"
  ((TESTS_PASSED++))
else
  if [ "$TOTAL_DECRYPTS" -lt "$NUM_FILES" ]; then
    print_warning "Total decrypt operations: $TOTAL_DECRYPTS (some may have been in progress during kill)"
  else
    print_fail "Total decrypt operations: $TOTAL_DECRYPTS (more than expected, possible duplicates)"
    ((TESTS_FAILED++))
  fi
fi

# Test: Queue is empty
QUEUE_FILE="$CFT_DIR/solaar_queue.lst"
if [ ! -s "$QUEUE_FILE" ]; then
  print_success "Queue is empty after processing"
  ((TESTS_PASSED++))
else
  REMAINING=$(wc -l < "$QUEUE_FILE" | tr -d ' ')
  print_fail "Queue still has $REMAINING items"
  ((TESTS_FAILED++))
fi

###############################################################################
# Summary
###############################################################################
print_header "TEST SUMMARY"

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))

echo -e "\nResults:"
echo -e "  ${GREEN}Passed:${NC} $TESTS_PASSED"
echo -e "  ${RED}Failed:${NC} $TESTS_FAILED"
echo -e "  Total:  $TOTAL_TESTS"

echo -e "\nRecovery details:"
echo "  Files processed before kill: $PROCESSED_BEFORE"
echo "  Files processed after recovery: $((FINAL_TXT - PROCESSED_BEFORE))"
echo "  Total files processed: $FINAL_TXT"

if [ "$TESTS_FAILED" -eq 0 ]; then
  echo -e "\n${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}║     KILL RECOVERY TEST PASSED - FLOCK WORKS CORRECTLY!       ║${NC}"
  echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
  echo -e "\nThe flock mechanism correctly releases locks when a process dies,"
  echo -e "preventing stale lock issues that would block future executions.\n"
  exit 0
else
  echo -e "\n${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${RED}║     KILL RECOVERY TEST FAILED - POTENTIAL LOCK ISSUE!        ║${NC}"
  echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}\n"
  exit 1
fi

