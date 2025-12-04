#!/bin/bash
###############################################################################
# gpg_env_test.sh - Test environment variables for decrypt_SOLAAR_v2_test.sh
#
# This file is loaded by decrypt_SOLAAR_v2_test.sh
# Contains ONLY test paths - no real GPG credentials needed for dry-run
###############################################################################

# Get the script directory (tests/)
TEST_SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

############################
# Test base directory
############################
HOMEDIR="$TEST_SCRIPT_DIR/test_env"

############################
# GnuPG directory (not used in dry-run, but defined for compatibility)
############################
HOMEDIRGPG="$HOMEDIR/cft/gnupg"

############################
# GPG password (not used in dry-run)
############################
PASS="test_password_not_used"

############################
# User and group for chown (use current user in tests)
############################
USER=$(whoami)
USERGROUP=$(id -gn)

############################
# Export for subprocesses
############################
export HOMEDIR HOMEDIRGPG PASS USER USERGROUP

