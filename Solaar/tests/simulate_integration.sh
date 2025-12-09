#!/bin/bash
###############################################################################
# simulate_integration.sh - Simula sistema de integração que processa e remove arquivo
#
# Este script simula o comportamento do sistema de integração que:
#   1. Detecta o arquivo CAR_OFSAPAC_REV.txt
#   2. Processa (simula com sleep)
#   3. Remove o arquivo quando termina
#
# USAGE:
#   ./simulate_integration.sh [--file FILE] [--delay N] [--watch]
#
# OPTIONS:
#   --file FILE : Arquivo para monitorar (default: CAR_OFSAPAC_REV.txt)
#   --delay N   : Tempo de processamento em segundos (default: 3)
#   --watch     : Modo watch - monitora continuamente
#
###############################################################################

OUTPUT_FILE_NAME="${OUTPUT_FILE_NAME:-CAR_OFSAPAC_REV.txt}"
PROCESS_DELAY=${PROCESS_DELAY:-3}
WATCH_MODE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --file)
      OUTPUT_FILE_NAME="$2"
      shift 2
      ;;
    --delay)
      PROCESS_DELAY="$2"
      shift 2
      ;;
    --watch)
      WATCH_MODE=true
      shift
      ;;
    *)
      shift
      ;;
  esac
done

# Load test environment to get RECV_DIR
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
source "$SCRIPT_DIR/gpg_env_test.sh" 2>/dev/null || {
  echo "Warning: Could not load gpg_env_test.sh, using default paths"
  HOMEDIR="${HOMEDIR:-/tmp/test_env}"
}

# Build RECV_DIR path (same logic as decrypt script)
RECV_DIR="${RECV_DIR:-$HOMEDIR/cft/recv}"
OUTPUT_FILE="$RECV_DIR/$OUTPUT_FILE_NAME"

echo "Simulating integration system..."
echo "  Watching: $OUTPUT_FILE"
echo "  Process delay: ${PROCESS_DELAY}s"
echo "  Watch mode: $WATCH_MODE"
echo ""

if [ "$WATCH_MODE" = true ]; then
  # Watch mode - continuously monitor
  while true; do
    if [ -f "$OUTPUT_FILE" ]; then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] Found $OUTPUT_FILE, processing..."
      sleep "$PROCESS_DELAY"
      rm -f "$OUTPUT_FILE"
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] Processed and removed $OUTPUT_FILE"
    else
      sleep 1
    fi
  done
else
  # Single run mode - wait for file, process, exit
  echo "Waiting for $OUTPUT_FILE to appear..."

  # Wait up to 60 seconds for file to appear
  for i in {1..60}; do
    if [ -f "$OUTPUT_FILE" ]; then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] Found $OUTPUT_FILE, processing..."
      sleep "$PROCESS_DELAY"
      rm -f "$OUTPUT_FILE"
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] Processed and removed $OUTPUT_FILE"
      exit 0
    fi
    sleep 1
  done

  echo "Timeout: File did not appear within 60 seconds"
  exit 1
fi

