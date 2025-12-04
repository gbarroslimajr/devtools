#!/bin/bash
###############################################################################
# test_cleanup.sh - Cleanup test environment
#
# USAGE:
#   ./test_cleanup.sh [--all] [--logs] [--files] [--locks]
#
# OPTIONS:
#   --all   : Remove entire test_env directory (default if no option)
#   --logs  : Remove only log files
#   --files : Remove only .GPG and .txt files
#   --locks : Remove only lock and queue files
#
###############################################################################

set -e

# Script directory
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

# Load test environment
source "$SCRIPT_DIR/gpg_env_test.sh"

# Defaults
CLEAN_ALL=false
CLEAN_LOGS=false
CLEAN_FILES=false
CLEAN_LOCKS=false

# If no arguments, clean all
if [ $# -eq 0 ]; then
  CLEAN_ALL=true
fi

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --all)
      CLEAN_ALL=true
      shift
      ;;
    --logs)
      CLEAN_LOGS=true
      shift
      ;;
    --files)
      CLEAN_FILES=true
      shift
      ;;
    --locks)
      CLEAN_LOCKS=true
      shift
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
NC='\033[0m'

print_header() {
  echo -e "\n${BLUE}=== $1 ===${NC}"
}

print_success() {
  echo -e "${GREEN}[OK]${NC} $1"
}

print_info() {
  echo -e "${YELLOW}[INFO]${NC} $1"
}

CFT_DIR="$HOMEDIR/cft"
RECV_DIR="$CFT_DIR/recv"

###############################################################################
# Clean all
###############################################################################
if [ "$CLEAN_ALL" = true ]; then
  print_header "Removing entire test environment"

  if [ -d "$HOMEDIR" ]; then
    rm -rf "$HOMEDIR"
    print_success "Removed: $HOMEDIR"
  else
    print_info "Test environment not found: $HOMEDIR"
  fi

  echo -e "\n${GREEN}Cleanup complete!${NC}"
  exit 0
fi

###############################################################################
# Clean logs
###############################################################################
if [ "$CLEAN_LOGS" = true ]; then
  print_header "Removing log files"

  if [ -d "$CFT_DIR" ]; then
    count=$(find "$CFT_DIR" -name "*.log" 2>/dev/null | wc -l)
    find "$CFT_DIR" -name "*.log" -delete 2>/dev/null
    print_success "Removed $count log files"
  else
    print_info "CFT directory not found"
  fi
fi

###############################################################################
# Clean GPG and TXT files
###############################################################################
if [ "$CLEAN_FILES" = true ]; then
  print_header "Removing .GPG and .txt files"

  if [ -d "$RECV_DIR" ]; then
    gpg_count=$(find "$RECV_DIR" -name "*.GPG" -o -name "*.gpg" 2>/dev/null | wc -l)
    txt_count=$(find "$RECV_DIR" -name "*.txt" 2>/dev/null | wc -l)

    find "$RECV_DIR" -name "*.GPG" -delete 2>/dev/null
    find "$RECV_DIR" -name "*.gpg" -delete 2>/dev/null
    find "$RECV_DIR" -name "*.txt" -delete 2>/dev/null

    print_success "Removed $gpg_count .GPG files"
    print_success "Removed $txt_count .txt files"
  else
    print_info "RECV directory not found"
  fi
fi

###############################################################################
# Clean locks and queue
###############################################################################
if [ "$CLEAN_LOCKS" = true ]; then
  print_header "Removing lock and queue files"

  if [ -d "$CFT_DIR" ]; then
    rm -f "$CFT_DIR/solaar_process.lock" 2>/dev/null && print_success "Removed: solaar_process.lock"
    rm -f "$CFT_DIR/solaar_queue.lock" 2>/dev/null && print_success "Removed: solaar_queue.lock"
    rm -f "$CFT_DIR/solaar_queue.lst" 2>/dev/null && print_success "Removed: solaar_queue.lst"
    rm -f "$CFT_DIR/solaar_queue.lst.tmp" 2>/dev/null && print_success "Removed: solaar_queue.lst.tmp"
  else
    print_info "CFT directory not found"
  fi
fi

echo -e "\n${GREEN}Cleanup complete!${NC}"

# Show remaining files
if [ -d "$HOMEDIR" ]; then
  echo -e "\n${YELLOW}Remaining in test environment:${NC}"
  find "$HOMEDIR" -type f 2>/dev/null | head -20
fi

