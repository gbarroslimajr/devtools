#!/bin/bash
###############################################################################
# test_single_instance.sh - Test single instance processing
#
# This test validates that a single instance of the script correctly:
#   1. Enqueues all pending .GPG files
#   2. Processes all files in order (FIFO)
#   3. Creates corresponding .txt files
#   4. No files are missed or duplicated
#
# USAGE:
#   ./test_single_instance.sh [--files N] [--sleep S]
#
# OPTIONS:
#   --files N : Number of test files (default: 5)
#   --sleep S : Sleep time per file in seconds (default: 0.5)
#
###############################################################################

set -e

# Script directory
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
SOLAAR_DIR=$(dirname "$SCRIPT_DIR")

# Load test environment
source "$SCRIPT_DIR/gpg_env_test.sh"

# Defaults
NUM_FILES=5
SLEEP_TIME=0.5

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
NC='\033[0m'

print_header() {
  echo -e "\n${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}║${NC} ${CYAN}$1${NC}"
  echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
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
print_header "TEST: Single Instance Processing"

print_subheader "Step 1: Setup test environment"

# Clean previous test data
"$SCRIPT_DIR/test_cleanup.sh" --all >/dev/null 2>&1 || true

# Setup with specified number of files
"$SCRIPT_DIR/test_setup.sh" --files "$NUM_FILES" --clean

print_success "Created $NUM_FILES test files"

# Count initial files
INITIAL_GPG=$(find "$RECV_DIR" -name "*.GPG" -o -name "*.gpg" 2>/dev/null | wc -l | tr -d ' ')
INITIAL_TXT=$(find "$RECV_DIR" -name "*.txt" 2>/dev/null | wc -l | tr -d ' ')

print_info "Initial state: $INITIAL_GPG .GPG files, $INITIAL_TXT .txt files"

###############################################################################
# Execute single instance
###############################################################################
print_subheader "Step 2: Running single instance (sleep=${SLEEP_TIME}s per file)"

START_TIME=$(date +%s.%3N)

# Run the test script
SLEEP_TIME=$SLEEP_TIME "$SOLAAR_DIR/decrypt_SOLAAR_v2_test.sh"

END_TIME=$(date +%s.%3N)
DURATION=$(echo "$END_TIME - $START_TIME" | bc)

print_info "Execution time: ${DURATION}s"

###############################################################################
# Validate results
###############################################################################
print_subheader "Step 3: Validating results"

FINAL_GPG=$(find "$RECV_DIR" -name "*.GPG" -o -name "*.gpg" 2>/dev/null | wc -l | tr -d ' ')
FINAL_TXT=$(find "$RECV_DIR" -name "*.txt" 2>/dev/null | wc -l | tr -d ' ')

TESTS_PASSED=0
TESTS_FAILED=0

# Test 1: All files processed
if [ "$FINAL_TXT" -eq "$NUM_FILES" ]; then
  print_success "All $NUM_FILES files were processed"
  ((TESTS_PASSED++))
else
  print_fail "Expected $NUM_FILES .txt files, found $FINAL_TXT"
  ((TESTS_FAILED++))
fi

# Test 2: Original GPG files still exist
if [ "$FINAL_GPG" -eq "$NUM_FILES" ]; then
  print_success "Original .GPG files preserved"
  ((TESTS_PASSED++))
else
  print_fail "Expected $NUM_FILES .GPG files, found $FINAL_GPG"
  ((TESTS_FAILED++))
fi

# Test 3: Each GPG has corresponding TXT
MISSING_TXT=0
for gpg_file in "$RECV_DIR"/*.GPG "$RECV_DIR"/*.gpg; do
  [ ! -f "$gpg_file" ] && continue

  fname=$(basename "$gpg_file")
  txt_file="$RECV_DIR/${fname%.[Gg][Pp][Gg]}.txt"

  if [ ! -f "$txt_file" ]; then
    print_fail "Missing TXT for: $fname"
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

# Test 4: No duplicate processing (check logs)
LOG_FILE=$(ls -t "$CFT_DIR"/solaar_test_*.log 2>/dev/null | head -1)
if [ -n "$LOG_FILE" ]; then
  PROCESSED_COUNT=$(grep -c "Decrypt completed" "$LOG_FILE" 2>/dev/null || echo 0)

  if [ "$PROCESSED_COUNT" -eq "$NUM_FILES" ]; then
    print_success "No duplicate processing (processed exactly $NUM_FILES files)"
    ((TESTS_PASSED++))
  else
    print_fail "Expected $NUM_FILES 'Decrypt completed' entries, found $PROCESSED_COUNT"
    ((TESTS_FAILED++))
  fi
else
  print_fail "Log file not found"
  ((TESTS_FAILED++))
fi

# Test 5: Queue is empty after processing
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

echo -e "\nExecution details:"
echo "  Files processed: $FINAL_TXT"
echo "  Duration: ${DURATION}s"
echo "  Avg per file: $(echo "scale=2; $DURATION / $NUM_FILES" | bc)s"

if [ "$TESTS_FAILED" -eq 0 ]; then
  echo -e "\n${GREEN}=== ALL TESTS PASSED ===${NC}\n"
  exit 0
else
  echo -e "\n${RED}=== SOME TESTS FAILED ===${NC}\n"
  exit 1
fi

