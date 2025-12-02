#!/usr/bin/ksh
###############################################################################
# gpg_env.sh — Environment variables for decrypt CFT/SOLAAR
#
# This file is loaded by decrypt_SOLAAR.sh.
# Contains ONLY:
#   - base paths
#   - GPG home
#   - GPG credentials (PASS)
#   - users and groups
# Does not contain fixed INPUTFILE/OUTPUTFILE (not used in new flow).
###############################################################################

############################
# Project base directory
############################
# Example:
# /home/user/projects/PROJECT_NAME
HOMEDIR="/home/user/projects/PROJECT_NAME"


############################
# GnuPG directory
############################
# Example:
# /home/user/projects/PROJECT_NAME/cft/gnupg
HOMEDIRGPG="$HOMEDIR/cft/gnupg"


############################
# GPG private key password
############################
# (Value here must be replaced with real PRD/UAT password —
#  but without exposing in documentation)
PASS="<GPG_PASSWORD_PLACEHOLDER>"


############################
# User and group for chown
############################
USER="appuser"
USERGROUP="APPGRP_QA"   # or APPGRP_PROD in production, if applicable


############################
# Legacy default log (optional)
############################
# Kept only for FORMEL compatibility
LOGFILE="$HOMEDIR/archives/log/gpg.log"


###############################################################################
# NOTE:
# INPUTFILE and OUTPUTFILE variables are NOT used in SOLAAR flow.
# decrypt_SOLAAR.sh processes multiple files dynamically.
###############################################################################

