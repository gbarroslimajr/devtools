#!/bin/bash

# TODO: Add support for multiple SSH keys
# TODO: Test notifications on MacOS (if it's working)

# Default options
INTERACTIVE=true
START_SSH_AGENT=true
LOG_FILE="git_update_$(date +%Y%m%d_%H%M%S).log"
LOG_DIR="logs"
ENABLE_NOTIFICATIONS=true
MAX_DEPTH=5  # Maximum depth to search for git repositories

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to send notification
send_notification() {
    local title="$1"
    local message="$2"

    if [ "$ENABLE_NOTIFICATIONS" = true ]; then
        # Check if terminal-notifier is installed
        if command -v terminal-notifier >/dev/null 2>&1; then
            terminal-notifier -title "Git Update" \
                            -subtitle "$title" \
                            -message "$message" \
                            -group "git.update.script" \
                            -activate "com.apple.Terminal"
        else
            # Fallback to osascript
            osascript -e "display notification \"$message\" with title \"Git Update\" subtitle \"$title\""
        fi
    fi
}

# Check for terminal-notifier and install if missing
check_terminal_notifier() {
    if ! command -v terminal-notifier >/dev/null 2>&1; then
        info_log "terminal-notifier não encontrado. Tentando instalar via Homebrew..."

        # Check if Homebrew is installed
        if command -v brew >/dev/null 2>&1; then
            brew install terminal-notifier
            if [ $? -eq 0 ]; then
                info_log "terminal-notifier instalado com sucesso"
                send_notification "Setup" "terminal-notifier instalado com sucesso"
            else
                warning_log "Erro ao instalar terminal-notifier. Usando osascript como fallback"
            fi
        else
            warning_log "Homebrew não encontrado. Usando osascript como fallback"
        fi
    fi
}

# Log functions
log() {
    local timestamp=$(date +'%Y-%m-%d %H:%M:%S')
    echo -e "${GREEN}[${timestamp}]${NC} $1" | tee -a "$LOG_DIR/$LOG_FILE"
}

error_log() {
    local timestamp=$(date +'%Y-%m-%d %H:%M:%S')
    local message="$1"
    echo -e "${RED}[${timestamp}] ERROR:${NC} $message" | tee -a "$LOG_DIR/$LOG_FILE"
    send_notification "Erro" "$message"
}

warning_log() {
    local timestamp=$(date +'%Y-%m-%d %H:%M:%S')
    local message="$1"
    echo -e "${YELLOW}[${timestamp}] WARNING:${NC} $message" | tee -a "$LOG_DIR/$LOG_FILE"
    send_notification "Aviso" "$message"
}

info_log() {
    local timestamp=$(date +'%Y-%m-%d %H:%M:%S')
    echo -e "${BLUE}[${timestamp}] INFO:${NC} $1" | tee -a "$LOG_DIR/$LOG_FILE"
}

# Function to log command output
log_cmd() {
    local cmd_output
    cmd_output=$("$@" 2>&1)
    if [ -n "$cmd_output" ]; then
        echo "$cmd_output" | tee -a "$LOG_DIR/$LOG_FILE"
    fi
}

# Function to show usage
show_usage() {
    echo "Uso: $0 [opções]"
    echo "Opções:"
    echo "  -n, --non-interactive     Executa em modo não-interativo (pula repositórios com problemas)"
    echo "  --no-ssh-agent           Não inicia o SSH agent"
    echo "  --log-dir DIR           Define o diretório de logs (padrão: ./logs)"
    echo "  --no-notifications      Desativa notificações do sistema"
    echo "  -h, --help               Mostra esta ajuda"
}

# Function to handle uncommitted changes
handle_uncommitted_changes() {
    local repo_name="$1"

    if [ "$INTERACTIVE" = true ]; then
        warning_log "Mudanças não commitadas encontradas em $repo_name"
        echo -e "${YELLOW}Opções disponíveis:${NC}"
        echo "1. Stash changes (salva temporariamente)"
        echo "2. Skip this repository (pula este repositório)"
        echo "3. Show changes (mostra as mudanças)"
        echo -n "Escolha uma opção (1-3): "
        read -r choice

        case $choice in
            1)
                git stash
                return 0
                ;;
            2)
                return 1
                ;;
            3)
                git status
                echo ""
                return 1
                ;;
            *)
                error_log "Opção inválida"
                return 1
                ;;
        esac
    else
        warning_log "Mudanças não commitadas encontradas em $repo_name (pulando no modo não-interativo)"
        return 1
    fi
}

# Function to setup SSH agent
setup_ssh_agent() {
    info_log "Configurando SSH agent..."

    # Check if SSH agent is running
    if [ -z "$SSH_AGENT_PID" ]; then
        log_cmd eval $(ssh-agent -s)
        info_log "SSH agent iniciado"
    else
        info_log "SSH agent já está rodando (PID: $SSH_AGENT_PID)"
    fi

    # Check if key is already added
    ssh-add -l > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        info_log "Chave SSH já está adicionada"
    else
        info_log "Adicionando chave SSH..."
        log_cmd ssh-add ~/.ssh/id_rsa
    fi
}

# Function to update a git repository
update_repo() {
    local repo_path="$1"
    local repo_name="$(basename "$repo_path")"
    local initial_dir="$(pwd)"

    info_log "Verificando repositório: $repo_name"

    # Change to repository directory
    cd "$repo_path" || {
        error_log "Não foi possível acessar o diretório $repo_name"
        return 1
    }

    # Check if directory is a git repository
    if [ ! -d .git ]; then
        warning_log "$repo_name não é um repositório Git. Pulando..."
        cd "$initial_dir"
        return 1
    fi

    # Get current branch
    local current_branch=$(git symbolic-ref --short HEAD 2>/dev/null || echo "DETACHED")
    info_log "Branch atual: $current_branch"

    # Check for uncommitted changes
    if [ -n "$(git status --porcelain)" ]; then
        handle_uncommitted_changes "$repo_name"
        if [ $? -eq 1 ]; then
            cd "$initial_dir"
            return 1
        fi
    fi

    # Fetch all remotes
    log "Executando git fetch..."
    if ! git fetch --all; then
        error_log "Erro ao executar git fetch em $repo_name"
        cd "$initial_dir"
        return 1
    fi

    # Check if pull is needed
    local LOCAL=$(git rev-parse @ 2>/dev/null)
    local REMOTE=$(git rev-parse @{u} 2>/dev/null)
    local BASE=$(git merge-base @ @{u} 2>/dev/null)

    if [ $? -ne 0 ]; then
        warning_log "Branch não tem upstream configurado em $repo_name"
        cd "$initial_dir"
        return 1
    fi

    if [ "$LOCAL" = "$REMOTE" ]; then
        info_log "Repositório $repo_name já está atualizado"
    elif [ "$LOCAL" = "$BASE" ]; then
        log "Executando git pull..."
        if ! git pull; then
            error_log "Erro ao executar git pull em $repo_name"
            cd "$initial_dir"
            return 1
        fi
        log "Repositório $repo_name atualizado com sucesso!"
        send_notification "Atualizado" "Repositório $repo_name atualizado com sucesso"
    elif [ "$REMOTE" = "$BASE" ]; then
        warning_log "Existem commits locais não enviados em $repo_name"
        cd "$initial_dir"
        return 1
    else
        warning_log "Branches divergiram em $repo_name"
        cd "$initial_dir"
        return 1
    fi

    cd "$initial_dir"
    return 0
}

# Function to find git repositories recursively
find_git_repos() {
    local base_path="$1"
    local current_depth="$2"

    # Check if we've exceeded the maximum depth
    if [ "$current_depth" -gt "$MAX_DEPTH" ]; then
        return
    fi

    # Check if current directory is a git repository
    if [ -d "$base_path/.git" ]; then
        echo "$base_path"
        return
    fi

    # Search in subdirectories
    for dir in "$base_path"/*/; do
        if [ -d "$dir" ]; then
            # Skip the .git directory itself
            if [[ "$dir" == *"/.git/"* ]]; then
                continue
            fi
            find_git_repos "$dir" $((current_depth + 1))
        fi
    done
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--non-interactive)
            INTERACTIVE=false
            shift
            ;;
        --no-ssh-agent)
            START_SSH_AGENT=false
            shift
            ;;
        --log-dir)
            LOG_DIR="$2"
            mkdir -p "$LOG_DIR"
            shift 2
            ;;
        --no-notifications)
            ENABLE_NOTIFICATIONS=false
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            error_log "Opção desconhecida: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main function
main() {
    # Check for terminal-notifier if notifications are enabled
    if [ "$ENABLE_NOTIFICATIONS" = true ]; then
        check_terminal_notifier
    fi

    send_notification "Iniciando" "Começando atualização dos repositórios Git"
    info_log "Iniciando script de atualização"
    info_log "Arquivo de log: $LOG_DIR/$LOG_FILE"

    # Setup SSH agent if requested
    if [ "$START_SSH_AGENT" = true ]; then
        setup_ssh_agent
    fi

    log "Iniciando busca por repositórios Git..."
    if [ "$INTERACTIVE" = false ]; then
        info_log "Executando em modo não-interativo"
    fi

    # Save current directory
    local initial_dir="$(pwd)"

    # Counters
    local success_count=0
    local total_repos=0
    local skipped_repos=0
    local found_repos=()

    # Find all git repositories recursively
    while IFS= read -r repo_path; do
        found_repos+=("$repo_path")
    done < <(find_git_repos "$initial_dir" 1)

    # Update each repository
    for repo_path in "${found_repos[@]}"; do
        ((total_repos++))
        info_log "Processando repositório encontrado: $repo_path"
        if update_repo "$repo_path"; then
            ((success_count++))
        else
            ((skipped_repos++))
        fi
    done

    # Summary
    echo "----------------------------------------"
    log "Atualização concluída!"
    log "Repositórios atualizados com sucesso: $success_count"
    warning_log "Repositórios pulados (com problemas): $skipped_repos"
    info_log "Total de repositórios Git encontrados: $total_repos"
    info_log "Log completo disponível em: $LOG_DIR/$LOG_FILE"

    # Final notification
    send_notification "Concluído" "Atualizados: $success_count, Pulados: $skipped_repos, Total: $total_repos"

    # Cleanup SSH agent if we started it
    if [ "$START_SSH_AGENT" = true ]; then
        if [ -n "$SSH_AGENT_PID" ]; then
            info_log "Encerrando SSH agent..."
            ssh-agent -k > /dev/null
        fi
    fi
}

# Execute main function
main