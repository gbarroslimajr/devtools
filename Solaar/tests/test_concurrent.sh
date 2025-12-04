#!/bin/bash
###############################################################################
# test_concurrent.sh - Test concurrent instances (race condition test)
#
# This is the CRITICAL test for validating the concurrency fix.
# It validates that when multiple instances run simultaneously:
#   1. Only ONE instance acquires the process lock and processes files
#   2. Other instances only enqueue and exit gracefully
#   3. No file is processed twice (no race condition)
#   4. No file is missed
#   5. Logs show correct behavior
#
# USAGE:
#   ./test_concurrent.sh [--files N] [--instances I] [--sleep S]
#
# OPTIONS:
#   --files N     : Number of test files (default: 10)
#   --instances I : Number of concurrent instances (default: 5)
#   --sleep S     : Sleep time per file in seconds (default: 0.5)
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
NUM_INSTANCES=5
SLEEP_TIME=0.5

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --files)
      NUM_FILES="$2"
      shift 2
      ;;
    --instances)
      NUM_INSTANCES="$2"
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
  echo -e "\n${MAGENTA}╔══════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${MAGENTA}║${NC} ${CYAN}$1${NC}"
  echo -e "${MAGENTA}╚══════════════════════════════════════════════════════════════╝${NC}"
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

CFT_DIR="$HOMEDIR/cft"
RECV_DIR="$CFT_DIR/recv"

###############################################################################
# Setup
###############################################################################
print_header "TEST: Concurrent Instances (Race Condition Test)"

echo -e "\nConfiguration:"
echo "  Files:     $NUM_FILES"
echo "  Instances: $NUM_INSTANCES"
echo "  Sleep:     ${SLEEP_TIME}s per file"

print_subheader "Step 1: Setup test environment"

# Clean previous test data
"$SCRIPT_DIR/test_cleanup.sh" --all >/dev/null 2>&1 || true

# Setup with specified number of files
"$SCRIPT_DIR/test_setup.sh" --files "$NUM_FILES" --clean

print_success "Created $NUM_FILES test files"

# Count initial files
INITIAL_GPG=$(find "$RECV_DIR" -name "*.GPG" -o -name "*.gpg" 2>/dev/null | wc -l | tr -d ' ')

print_info "Initial state: $INITIAL_GPG .GPG files"

###############################################################################
# Launch concurrent instances
###############################################################################
print_subheader "Step 2: Launching $NUM_INSTANCES concurrent instances"

PIDS=()
START_TIME=$(date +%s.%3N)

# Launch all instances simultaneously
for i in $(seq 1 $NUM_INSTANCES); do
  print_info "Launching instance $i..."
  SLEEP_TIME=$SLEEP_TIME "$SOLAAR_DIR/decrypt_SOLAAR_v2_test.sh" > /dev/null 2>&1 &
  PIDS+=($!)
  # Small delay to make race condition more likely
  sleep 0.01
done

print_info "All $NUM_INSTANCES instances launched"
print_info "PIDs: ${PIDS[*]}"

# Wait for all instances to complete
print_subheader "Step 3: Waiting for all instances to complete"

for pid in "${PIDS[@]}"; do
  wait "$pid" 2>/dev/null || true
done

END_TIME=$(date +%s.%3N)
DURATION=$(echo "$END_TIME - $START_TIME" | bc)

print_success "All instances completed in ${DURATION}s"

###############################################################################
# Validate results
###############################################################################
print_subheader "Step 4: Validating results (CRITICAL TESTS)"

FINAL_GPG=$(find "$RECV_DIR" -name "*.GPG" -o -name "*.gpg" 2>/dev/null | wc -l | tr -d ' ')
FINAL_TXT=$(find "$RECV_DIR" -name "*.txt" 2>/dev/null | wc -l | tr -d ' ')

TESTS_PASSED=0
TESTS_FAILED=0

# Test 1: All files processed (exactly once)
echo -e "\n${CYAN}--- Core Functionality Tests ---${NC}"

if [ "$FINAL_TXT" -eq "$NUM_FILES" ]; then
  print_success "All $NUM_FILES files were processed"
  ((TESTS_PASSED++))
else
  print_fail "Expected $NUM_FILES .txt files, found $FINAL_TXT"
  ((TESTS_FAILED++))
fi

# Test 2: No duplicate files
UNIQUE_TXT=$(find "$RECV_DIR" -name "*.txt" -exec basename {} \; | sort | uniq | wc -l | tr -d ' ')
if [ "$UNIQUE_TXT" -eq "$FINAL_TXT" ]; then
  print_success "No duplicate .txt files"
  ((TESTS_PASSED++))
else
  print_fail "Found duplicate files! Unique: $UNIQUE_TXT, Total: $FINAL_TXT"
  ((TESTS_FAILED++))
fi

# Test 3: Each GPG has corresponding TXT
MISSING_TXT=0
for gpg_file in "$RECV_DIR"/*.GPG "$RECV_DIR"/*.gpg; do
  [ ! -f "$gpg_file" ] && continue

  fname=$(basename "$gpg_file")
  txt_file="$RECV_DIR/${fname%.[Gg][Pp][Gg]}.txt"

  if [ ! -f "$txt_file" ]; then
    ((MISSING_TXT++))
  fi
done

if [ "$MISSING_TXT" -eq 0 ]; then
  print_success "All .GPG files have corresponding .txt"
  ((TESTS_PASSED++))
else
  print_fail "$MISSING_TXT files missing their .txt output"
  ((TESTS_FAILED++))
fi

# Test 4: Analyze logs for concurrency behavior
echo -e "\n${CYAN}--- Concurrency Behavior Tests ---${NC}"

LOG_FILES=$(ls -t "$CFT_DIR"/solaar_test_*.log 2>/dev/null)
LOG_COUNT=$(echo "$LOG_FILES" | wc -l | tr -d ' ')

print_info "Found $LOG_COUNT log files"

# Count instances that acquired lock
LOCK_ACQUIRED=$(grep -l "LOCK acquired" $LOG_FILES 2>/dev/null | wc -l | tr -d ' ')

if [ "$LOCK_ACQUIRED" -eq 1 ]; then
  print_success "Only 1 instance acquired the process lock"
  ((TESTS_PASSED++))
else
  print_fail "Expected 1 instance to acquire lock, but $LOCK_ACQUIRED did"
  ((TESTS_FAILED++))
fi

# Count instances that found lock already held
LOCK_BLOCKED=$(grep -l "Another instance is processing" $LOG_FILES 2>/dev/null | wc -l | tr -d ' ')

EXPECTED_BLOCKED=$((NUM_INSTANCES - 1))
if [ "$LOCK_BLOCKED" -ge 1 ]; then
  print_success "$LOCK_BLOCKED instance(s) correctly detected another instance running"
  ((TESTS_PASSED++))
else
  print_fail "Expected at least 1 instance to be blocked, but $LOCK_BLOCKED were"
  ((TESTS_FAILED++))
fi

# Test 5: Total decrypt operations equals file count (no duplicates in processing)
TOTAL_DECRYPTS=0
for log in $LOG_FILES; do
  count=$(grep -c "Decrypt completed" "$log" 2>/dev/null || echo 0)
  TOTAL_DECRYPTS=$((TOTAL_DECRYPTS + count))
done

if [ "$TOTAL_DECRYPTS" -eq "$NUM_FILES" ]; then
  print_success "Total decrypt operations: $TOTAL_DECRYPTS (matches file count)"
  ((TESTS_PASSED++))
else
  print_fail "Total decrypt operations: $TOTAL_DECRYPTS (expected $NUM_FILES)"
  ((TESTS_FAILED++))
fi

# Test 6: Check for any duplicate processing (same file processed by multiple PIDs)
echo -e "\n${CYAN}--- Duplicate Detection Tests ---${NC}"

DUPLICATE_FOUND=false
for txt_file in "$RECV_DIR"/*.txt; do
  [ ! -f "$txt_file" ] && continue

  # Each TXT file has a header showing which PID processed it
  PID_LINE=$(head -1 "$txt_file" 2>/dev/null | grep "Decrypted by PID" || true)
  if [ -z "$PID_LINE" ]; then
    print_info "Warning: $(basename $txt_file) missing PID header"
  fi
done

# Check if any file was processed multiple times by checking logs
for i in $(seq -w 1 $NUM_FILES); do
  filename="SOLAAR_TEST_FILE_${i}.GPG"
  PROCESS_COUNT=$(grep -l "Starting decrypt.*$filename" $LOG_FILES 2>/dev/null | wc -l | tr -d ' ')

  if [ "$PROCESS_COUNT" -gt 1 ]; then
    print_fail "File $filename was processed by $PROCESS_COUNT instances!"
    DUPLICATE_FOUND=true
  fi
done

if [ "$DUPLICATE_FOUND" = false ]; then
  print_success "No file was processed by multiple instances"
  ((TESTS_PASSED++))
else
  print_fail "Some files were processed multiple times (race condition detected!)"
  ((TESTS_FAILED++))
fi

# Test 7: Queue is empty after processing
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
# Detailed log analysis
###############################################################################
print_subheader "Step 5: Detailed log analysis"

echo -e "\nPer-instance breakdown:"
for log in $LOG_FILES; do
  log_name=$(basename "$log")
  pid=$(echo "$log_name" | grep -oE '[0-9]+\.log' | sed 's/\.log//')
  acquired=$(grep -c "LOCK acquired" "$log" 2>/dev/null || echo 0)
  blocked=$(grep -c "Another instance" "$log" 2>/dev/null || echo 0)
  processed=$(grep -c "Decrypt completed" "$log" 2>/dev/null || echo 0)
  enqueued=$(grep -c "File enqueued" "$log" 2>/dev/null || echo 0)

  if [ "$acquired" -gt 0 ]; then
    echo -e "  ${GREEN}$log_name${NC}: acquired lock, processed $processed files, enqueued $enqueued"
  else
    echo -e "  ${YELLOW}$log_name${NC}: blocked (another instance running), enqueued $enqueued"
  fi
done

###############################################################################
# Summary
###############################################################################
print_header "TEST SUMMARY"

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))

echo -e "\nResults:"
echo -e "  ${GREEN}Passed:${NC} $TESTS_PASSED"
echo -e "  ${RED}Failed:${NC} $TESTS_FAILED"
echo -e "  Total:  $TOTAL_TESTS"

echo -e "\nExecution details:"
echo "  Concurrent instances: $NUM_INSTANCES"
echo "  Files to process: $NUM_FILES"
echo "  Files processed: $FINAL_TXT"
echo "  Total duration: ${DURATION}s"
echo "  Instances that acquired lock: $LOCK_ACQUIRED"
echo "  Instances blocked: $LOCK_BLOCKED"

if [ "$TESTS_FAILED" -eq 0 ]; then
  echo -e "\n${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}║     ALL CONCURRENCY TESTS PASSED - NO RACE CONDITIONS!       ║${NC}"
  echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}\n"
  exit 0
else
  echo -e "\n${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${RED}║  SOME TESTS FAILED - POTENTIAL RACE CONDITION DETECTED!      ║${NC}"
  echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}\n"
  exit 1
fi

