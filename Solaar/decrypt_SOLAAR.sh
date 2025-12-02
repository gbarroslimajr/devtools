#!/usr/bin/ksh
###############################################################################
# decrypt_SOLAAR.sh  (substitui decrypt.sh)
#
# - End-of-transfer do CFT para arquivos SOLAAR (*.GPG)
# - Carrega o gpg_env.sh (paths, PASS, diretórios, owner, etc.)
# - Enfileira arquivos pendentes
# - Processa 1 por vez (fila FIFO + lock)
# - Cria LOG por execução
###############################################################################

# Diretório do script
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

###############################################################################
# 1. Carrega o ambiente (gpg_env.sh)
#    - Define: HOMEDIR, HOMEDIRGPG, LOGFILE, PASS, USER, USERGROUP etc.
#    - NÃO USAMOS INPUTFILE/OUTPUTFILE DO ARQUIVO (só paths/credenciais)
###############################################################################

ENV_FILE="$SCRIPT_DIR/gpg_env.sh"

if [ -f "$ENV_FILE" ]; then
  . "$ENV_FILE"
else
  echo "ERRO: Arquivo de ambiente '$ENV_FILE' não encontrado!"
  exit 1
fi

# Valida variáveis obrigatórias após carregar ambiente
REQUIRED_VARS="HOMEDIR HOMEDIRGPG PASS"
for var in $REQUIRED_VARS; do
  eval "value=\$$var"
  if [ -z "$value" ]; then
    echo "ERRO: Variável obrigatória '$var' não definida em $ENV_FILE" >&2
    exit 1
  fi
done

###############################################################################
# 2. Diretórios de trabalho (baseados no gpg_env.sh)
###############################################################################
CFT_DIR="$HOMEDIR/cft"
RECV_DIR="$CFT_DIR/recv"
GNUPG_DIR="$HOMEDIRGPG"

QUEUE_FILE="$CFT_DIR/solaar_queue.lst"
LOCK_FILE="$CFT_DIR/solaar_queue.lock"

# Log próprio por execução
NOW=$(date +%Y%m%d_%H%M%S)
EXEC_LOG="$CFT_DIR/solaar_${NOW}.log"

OWNER_USER=${USER:-"cpf"}
OWNER_GROUP=${USERGROUP:-"TXQUA"}

# Valida existência de diretórios críticos
[ -d "$GNUPG_DIR" ] || {
  echo "ERRO: Diretório GPG não existe: $GNUPG_DIR" >&2
  exit 1
}

# Cria diretórios que podem não existir (com permissões corretas)
[ -d "$CFT_DIR" ] || {
  mkdir -p "$CFT_DIR" || {
    echo "ERRO: Não foi possível criar diretório CFT: $CFT_DIR" >&2
    exit 1
  }
}

[ -d "$RECV_DIR" ] || {
  mkdir -p "$RECV_DIR" || {
    echo "ERRO: Não foi possível criar diretório de recebimento: $RECV_DIR" >&2
    exit 1
  }
}

umask 002

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') - $*" >> "$EXEC_LOG"
}

###############################################################################
# 3. Enfileirar arquivos pendentes
###############################################################################
enqueue_pending_files() {

  [ -f "$QUEUE_FILE" ] || touch "$QUEUE_FILE"

  for f in "$RECV_DIR"/*.GPG "$RECV_DIR"/*.gpg; do
    [ ! -f "$f" ] && continue

    fname=$(basename "$f")
    out_txt="$RECV_DIR/${fname%.[Gg][Pp][Gg]}.txt"

    # Se já existe TXT correspondente, não enfileira
    if [ -f "$out_txt" ]; then
      log "Arquivo já processado, TXT encontrado. Ignorando: $fname"
      continue
    fi

    # Enfileira se ainda não está na fila
    if ! grep -qx "$fname" "$QUEUE_FILE" 2>/dev/null; then
      echo "$fname" >> "$QUEUE_FILE"
      log "Arquivo enfileirado: $fname"
    fi
  done
}

###############################################################################
# 4. Processar fila com lock
###############################################################################
process_queue() {

  if [ -f "$LOCK_FILE" ]; then
    log "Lock encontrado. Outra instância está rodando. Encerrando."
    return 0
  fi

  echo $$ > "$LOCK_FILE"
  log "LOCK criado: $LOCK_FILE (PID $$)"

  while [ -s "$QUEUE_FILE" ]; do
    FILE_IN_QUEUE=$(head -n 1 "$QUEUE_FILE")

    tail -n +2 "$QUEUE_FILE" > "${QUEUE_FILE}.tmp" 2>/dev/null
    mv -f "${QUEUE_FILE}.tmp" "$QUEUE_FILE"

    [ -n "$FILE_IN_QUEUE" ] && decrypt_single_file "$FILE_IN_QUEUE"
  done

  rm -f "$LOCK_FILE"
  log "LOCK removido."
}

###############################################################################
# 5. Decriptar arquivo único
###############################################################################
decrypt_single_file() {

  fname="$1"
  input_file="$RECV_DIR/$fname"
  output_file="$RECV_DIR/${fname%.[Gg][Pp][Gg]}.txt"

  log "Iniciando decrypt: $fname"

  if [ ! -f "$input_file" ]; then
    log "ERRO: Arquivo não encontrado: $input_file"
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
    log "ERRO ao decriptar: $fname"
    return 1
  fi

  chmod 664 "$output_file" 2>/dev/null
  chown "$OWNER_USER":"$OWNER_GROUP" "$output_file" 2>/dev/null

  log "Decrypt concluído: $output_file"
  return 0
}

###############################################################################
# MAIN
###############################################################################
log "========================================================================"
log "Início decrypt_SOLAAR.sh — carregado via gpg_env.sh"

enqueue_pending_files
process_queue

log "Fim decrypt_SOLAAR.sh"
log "========================================================================"

exit 0