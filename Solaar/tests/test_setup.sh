#!/bin/bash
###############################################################################
# test_setup.sh - Setup test environment for decrypt_SOLAAR_v2_test.sh
#
# USAGE:
#   ./test_setup.sh [--files N] [--clean]
#
# OPTIONS:
#   --files N : Number of .GPG test files to create (default: 10)
#   --clean   : Clean previous test data before setup
#
###############################################################################

set -e

# Script directory
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

# Load test environment
source "$SCRIPT_DIR/gpg_env_test.sh"

# Default number of files
NUM_FILES=${NUM_FILES:-10}
CLEAN_FIRST=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --files)
      NUM_FILES="$2"
      shift 2
      ;;
    --clean)
      CLEAN_FIRST=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
  echo -e "\n${BLUE}=== $1 ===${NC}"
}

print_success() {
  echo -e "${GREEN}[OK]${NC} $1"
}

print_info() {
  echo -e "${YELLOW}[INFO]${NC} $1"
}

###############################################################################
# Clean previous test data if requested
###############################################################################
if [ "$CLEAN_FIRST" = true ]; then
  print_header "Cleaning previous test data"

  if [ -d "$HOMEDIR" ]; then
    rm -rf "$HOMEDIR"
    print_success "Removed: $HOMEDIR"
  else
    print_info "Nothing to clean"
  fi
fi

###############################################################################
# Create directory structure
###############################################################################
print_header "Creating directory structure"

CFT_DIR="$HOMEDIR/cft"
RECV_DIR="$CFT_DIR/recv"
GNUPG_DIR="$HOMEDIR/cft/gnupg"

mkdir -p "$RECV_DIR"
print_success "Created: $RECV_DIR"

mkdir -p "$GNUPG_DIR"
print_success "Created: $GNUPG_DIR"

###############################################################################
# Create test GPG files
###############################################################################
print_header "Creating $NUM_FILES test .GPG files"

for i in $(seq -w 1 $NUM_FILES); do
  filename="SOLAAR_TEST_FILE_${i}.GPG"
  filepath="$RECV_DIR/$filename"

  # Create file with identifiable content
  cat > "$filepath" << EOF
Test file content for: $filename
Created at: $(date '+%Y-%m-%d %H:%M:%S.%3N')
File number: $i of $NUM_FILES
Random data: $(head -c 32 /dev/urandom | base64 2>/dev/null || echo "random_$i")
---
This is a simulated encrypted file for testing the decrypt_SOLAAR_v2_test.sh script.
EOF

  print_success "Created: $filename"
done

###############################################################################
# Summary
###############################################################################
print_header "Setup Complete"

echo -e "\nTest environment ready:"
echo "  HOMEDIR:  $HOMEDIR"
echo "  RECV_DIR: $RECV_DIR"
echo "  Files:    $NUM_FILES .GPG files"

echo -e "\n${GREEN}Files in recv directory:${NC}"
ls -la "$RECV_DIR"

echo -e "\n${YELLOW}To run tests:${NC}"
echo "  Single instance:  ./test_single_instance.sh"
echo "  Concurrent test:  ./test_concurrent.sh"
echo "  Kill recovery:    ./test_kill_recovery.sh"
echo "  Cleanup:          ./test_cleanup.sh"

