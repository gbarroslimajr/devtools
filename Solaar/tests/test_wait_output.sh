#!/bin/bash
###############################################################################
# test_wait_output.sh - Test wait for output file functionality
#
# Este teste valida que:
#   1. Script aguarda arquivo CAR_OFSAPAC_REV.txt desaparecer antes de processar próximo GPG
#   2. Sistema de integração simulado remove o arquivo corretamente
#   3. Script continua processando após arquivo ser removido
#
# USAGE:
#   ./test_wait_output.sh [--files N] [--delay D]
#
# OPTIONS:
#   --files N : Número de arquivos GPG (default: 3)
#   --delay D : Delay do simulador de integração em segundos (default: 2)
#
###############################################################################

set -e

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
SOLAAR_DIR=$(dirname "$SCRIPT_DIR")

source "$SCRIPT_DIR/gpg_env_test.sh"

NUM_FILES=3
INTEGRATION_DELAY=2

while [[ $# -gt 0 ]]; do
  case $1 in
    --files)
      NUM_FILES="$2"
      shift 2
      ;;
    --delay)
      INTEGRATION_DELAY="$2"
      shift 2
      ;;
    *)
      shift
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
OUTPUT_FILE="$RECV_DIR/CAR_OFSAPAC_REV.txt"

###############################################################################
# Setup
###############################################################################
print_header "TEST: Wait for Output File Functionality"

print_subheader "Step 1: Setup test environment"

"$SCRIPT_DIR/test_cleanup.sh" --all >/dev/null 2>&1 || true
"$SCRIPT_DIR/test_setup.sh" --files "$NUM_FILES" --clean

print_success "Created $NUM_FILES test files"

###############################################################################
# Start integration simulator in background
###############################################################################
print_subheader "Step 2: Start integration simulator"

"$SCRIPT_DIR/simulate_integration.sh" --delay "$INTEGRATION_DELAY" --watch > /tmp/integration_sim.log 2>&1 &
SIMULATOR_PID=$!

print_success "Integration simulator started (PID: $SIMULATOR_PID)"
print_info "Simulator will process files with ${INTEGRATION_DELAY}s delay"

# Small delay to let simulator start
sleep 1

###############################################################################
# Run decrypt script
###############################################################################
print_subheader "Step 3: Run decrypt script"

START_TIME=$(date +%s)
SLEEP_TIME=0.5 "$SOLAAR_DIR/decrypt_SOLAAR_v2_test.sh" > /tmp/decrypt_test.log 2>&1 &
DECRYPT_PID=$!

print_info "Decrypt script started (PID: $DECRYPT_PID)"

# Wait for completion
wait $DECRYPT_PID 2>/dev/null || true
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

print_success "Decrypt script completed in ${DURATION}s"

###############################################################################
# Stop simulator
###############################################################################
print_subheader "Step 4: Stop integration simulator"

kill $SIMULATOR_PID 2>/dev/null || true
wait $SIMULATOR_PID 2>/dev/null || true

print_success "Simulator stopped"

###############################################################################
# Validate results
###############################################################################
print_subheader "Step 5: Validate results"

TESTS_PASSED=0
TESTS_FAILED=0

# Check logs for wait messages
LOG_FILE=$(ls -t "$CFT_DIR"/solaar_test_*.log 2>/dev/null | head -1)

if [ -n "$LOG_FILE" ]; then
  WAIT_COUNT=$(grep -c "Waiting for.*CAR_OFSAPAC_REV.txt" "$LOG_FILE" 2>/dev/null || echo 0)
  DISAPPEARED_COUNT=$(grep -c "Output file.*disappeared" "$LOG_FILE" 2>/dev/null || echo 0)

  if [ "$WAIT_COUNT" -gt 0 ]; then
    print_success "Script waited for output file ($WAIT_COUNT times)"
    ((TESTS_PASSED++))
  else
    print_fail "No wait messages found in logs"
    ((TESTS_FAILED++))
  fi

  if [ "$DISAPPEARED_COUNT" -gt 0 ]; then
    print_success "Script detected file disappearance ($DISAPPEARED_COUNT times)"
    ((TESTS_PASSED++))
  else
    print_fail "No 'disappeared' messages found in logs"
    ((TESTS_FAILED++))
  fi
else
  print_fail "Log file not found"
  ((TESTS_FAILED++))
fi

# Check that output file doesn't exist (should have been processed)
if [ ! -f "$OUTPUT_FILE" ]; then
  print_success "Output file was processed and removed"
  ((TESTS_PASSED++))
else
  print_fail "Output file still exists: $OUTPUT_FILE"
  ((TESTS_FAILED++))
fi

# Check simulator logs
if grep -q "Processed and removed" /tmp/integration_sim.log 2>/dev/null; then
  PROCESSED_COUNT=$(grep -c "Processed and removed" /tmp/integration_sim.log)
  print_success "Integration simulator processed $PROCESSED_COUNT file(s)"
  ((TESTS_PASSED++))
else
  print_fail "Integration simulator did not process any files"
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
echo "  Files: $NUM_FILES"
echo "  Duration: ${DURATION}s"
echo "  Integration delay: ${INTEGRATION_DELAY}s"

if [ "$TESTS_FAILED" -eq 0 ]; then
  echo -e "\n${GREEN}=== ALL TESTS PASSED ===${NC}\n"
  exit 0
else
  echo -e "\n${RED}=== SOME TESTS FAILED ===${NC}\n"
  exit 1
fi

