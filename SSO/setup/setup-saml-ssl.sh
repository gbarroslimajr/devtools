#!/bin/bash
# setup-saml-ssl.sh
#
# Automação completa das etapas de configuração de SAML/SSL
# para aplicações Java/WebSphere.
#
# Requisitos:
#  - JDK (keytool) instalado - o script usa $JAVA_HOME/bin/keytool
#  - openssl (para fingerprints)
#  - Permissão de escrita nos diretórios de keystore
#
# Como funciona:
#  1) backup do cacerts (truststore JDK)
#  2) import dos certificados Root + Application no cacerts
#  3) processamento do certificado da aplicação → JKS (keystore da aplicação)
#  4) import do certificado SSO (IdP) no JKS
#  5) verificações + log detalhado
#

#set -euo pipefail  # aborta em erro, falha em variáveis não definidas


#═══════════════════════════════════════════════════════════════
# 0 - Variáveis de configuração (pode ser sobrescrito por export)
#═══════════════════════════════════════════════════════════════
: "${JAVA_HOME:=/usr/lib/jvm/java-8-openjdk}"
: "${APP_TRIGRAM:=myapp}"
: "${CERT_FILE:=/path/to/your/application/certificate.cer}"
# Senhas - podem ser exportadas antes da chamada ou digitadas interativamente
: "${ROOT_CERT:=/path/to/your/root/certificate.cer}"
: "${APP_CERT:=/path/to/your/application/certificate.cer}"
: "${SSO_CERT:=/path/to/your/sso/certificate.crt}"

# Senhas - podem ser exportadas antes da chamada ou digitadas interativamente
: "${CACERTS_PASS:=changeit}"
: "${JKS_PASS:=your_keystore_password}"
# Caminhos derivados

# Caminhos derivados
KEYTOOL="${JAVA_HOME}/bin/keytool"
# Determine cacerts location (fallback for JDKs without a jre directory)
if [[ -f "${JAVA_HOME}/jre/lib/security/cacerts" ]]; then
   CACERTS="${JAVA_HOME}/jre/lib/security/cacerts"
else
   CACERTS="${JAVA_HOME}/lib/security/cacerts"
fi
CACERTS_BKP="${CACERTS}.bkp_$(date +%Y%m%d%H%M%S)"
CERT_DIR="$(dirname "$CERT_FILE")"
JKS_FILE="${CERT_DIR}/${APP_TRIGRAM}-application.jks"
APP_ALIAS="${APP_TRIGRAM}-application"
SSO_ALIAS="SSO"

# Arquivo de log - será criado no diretório corrente
LOGFILE="setup-saml-ssl_$(date +%Y%m%d%H%M%S).log"
mkdir -p "$(dirname "$LOGFILE")"
# exec > "$LOGFILE"         # redireciona stdout+stderr para log (compatível com sh)
set +o pipefail
exec > >(tee -a "${LOGFILE}") 2>&1

set -o pipefail

echo "═══ INÍCIO DO SCRIPT - $(date) ═══"
echo "JAVA_HOME    = $JAVA_HOME"
echo "KEYTOOL      = $KEYTOOL"
echo "CACERTS      = $CACERTS"
echo "JKS_FILE     = $JKS_FILE"
echo "APP_ALIAS    = $APP_ALIAS"
echo "SSO_ALIAS    = $SSO_ALIAS"
echo "════════════════════════════════════════════════════════════════════"

#═══════════════════════════════════════════════════════════════
#  Funções auxiliares
#═══════════════════════════════════════════════════════════════
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') | $*"
}

# Helper to convert DER certificates to PEM if needed
to_pem() {
    local in_file="$1"
    local out_file="${in_file}.pem"
    if file "$in_file" | grep -qi "DER"; then
        openssl x509 -inform DER -in "$in_file" -out "$out_file"
        echo "$out_file"
    else
        echo "$in_file"
    fi
}

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

#═══════════════════════════════════════════════════════════════
# 1 - Backup do cacerts (truststore JDK)
#═══════════════════════════════════════════════════════════════
backup_cacerts() {
    cp -p "$CACERTS" "$CACERTS_BKP" || fail "Não foi possível criar backup de $CACERTS"
    chmod 600 "$CACERTS_BKP"
    log "Backup concluído."
}

#═══════════════════════════════════════════════════════════════
# 2 - Importar Root e Application no cacerts
#═══════════════════════════════════════════════════════════════
import_root_app_to_cacerts() {
    # Validar existência dos certificados antes da importação
    [[ -f "$ROOT_CERT" ]] || fail "Root certificate not found: $ROOT_CERT"
    [[ -f "$APP_CERT" ]] || fail "Application certificate not found: $APP_CERT"

    for cert in "$ROOT_CERT" "$APP_CERT"; do
        # Garantir que o certificado está em PEM; converter se necessário
        cert_pem=$(to_pem "$cert")
        alias_name=$(basename "$cert_pem" .cer | tr '[:upper:]' '[:lower:]' | tr -d ' .')
        log "Importando $cert_pem com alias $alias_name no cacerts"
        $KEYTOOL -importcert \
        -keystore "$CACERTS" \
        -storepass "$CACERTS_PASS" \
        -alias "$alias_name" \
        -file "$cert_pem" \
        -noprompt \
        -trustcacerts || fail "Falha ao importar $cert"
    done
    log "Importação para cacerts concluída."
}

#═══════════════════════════════════════════════════════════════
# 3 - Processar certificado → JKS (keystore da aplicação)
#═══════════════════════════════════════════════════════════════
convert_cert_to_jks() {
    log "Processando arquivo de certificado ($CERT_FILE) → JKS ($JKS_FILE)"
    if [[ ! -f "$CERT_FILE" ]]; then
        fail "Arquivo não encontrado: $CERT_FILE"
    fi

    # Verificar se é um arquivo PKCS12 ou certificado simples
    if file "$CERT_FILE" | grep -qi "PKCS12\|keystore"; then
        log "Detectado arquivo PKCS12, convertendo..."
        $KEYTOOL -importkeystore \
        -deststoretype JKS \
        -destkeystore "$JKS_FILE" \
        -deststorepass "$JKS_PASS" \
        -destkeypass "$JKS_PASS" \
        -destalias "$APP_ALIAS" \
        -srckeystore "$CERT_FILE" \
        -srcstoretype PKCS12 \
        -srcstorepass "$JKS_PASS" \
        -srcalias "$APP_ALIAS" \
        -noprompt || fail "Falha ao converter PKCS12 para JKS"
    else
        log "Detectado certificado simples, criando JKS e importando..."
        # Criar JKS vazio primeiro
        $KEYTOOL -genkeypair \
        -keystore "$JKS_FILE" \
        -storepass "$JKS_PASS" \
        -alias "temp" \
        -dname "CN=temp" \
        -keypass "$JKS_PASS" \
        -noprompt

        # Remover a chave temporária
        $KEYTOOL -delete \
        -keystore "$JKS_FILE" \
        -storepass "$JKS_PASS" \
        -alias "temp" \
        -noprompt

        # Importar o certificado
        $KEYTOOL -importcert \
        -keystore "$JKS_FILE" \
        -storepass "$JKS_PASS" \
        -alias "$APP_ALIAS" \
        -file "$CERT_FILE" \
        -noprompt || fail "Falha ao importar certificado no JKS"
    fi

    chmod 600 "$JKS_FILE"
    log "Processamento concluído."
}

#═══════════════════════════════════════════════════════════════
# 4 - Importar certificado SSO no JKS
#═══════════════════════════════════════════════════════════════
import_sso_to_jks() {
    # Validar existência do certificado SSO antes da importação
    [[ -f "$SSO_CERT" ]] || fail "SSO certificate not found: $SSO_CERT"

    # Garantir que o certificado está em PEM; converter se necessário
    sso_cert_pem=$(to_pem "$SSO_CERT")
    [[ -f "$sso_cert_pem" ]] || fail "Converted SSO certificate not found: $sso_cert_pem"

    log "Importando certificado SSO ($sso_cert_pem) como alias $SSO_ALIAS no JKS"
    $KEYTOOL -importcert \
    -trustcacerts \
    -keystore "$JKS_FILE" \
    -storepass "$JKS_PASS" \
    -alias "$SSO_ALIAS" \
    -file "$sso_cert_pem" \
    -noprompt || fail "Falha ao importar certificado SSO"
    log "Importação SSO concluída."
}

#═══════════════════════════════════════════════════════════════
# 5 - Verificações / fingerprints
#═══════════════════════════════════════════════════════════════
#
# 5b - Verificar consistência entre .cer original e certificado no JKS
#═══════════════════════════════════════════════════════════════
verify_cert_consistency() {
    # Arquivo temporário onde o certificado será exportado do JKS
    local tmp_cert="${TMPDIR:-/tmp}/cert_from_jks.cer"

    # Exporta o certificado do JKS em formato PEM (RFC)
    $KEYTOOL -exportcert \
    -keystore "$JKS_FILE" \
    -storepass "$JKS_PASS" \
    -alias "$APP_ALIAS" \
    -rfc -file "$tmp_cert" \
    || fail "Falha ao exportar certificado do JKS para $tmp_cert"

    # Calcula fingerprint SHA-256 do certificado original (pode ser DER ou PEM)
    local orig_fingerprint
    if file "$APP_CERT" | grep -qi "DER"; then
        orig_fingerprint=$(openssl x509 -inform DER -in "$APP_CERT" -noout -fingerprint -sha256)
    else
        orig_fingerprint=$(openssl x509 -inform PEM -in "$APP_CERT" -noout -fingerprint -sha256)
    fi

    # Calcula fingerprint SHA-256 do certificado exportado do JKS (já está em PEM)
    local jks_fingerprint
    jks_fingerprint=$(openssl x509 -inform PEM -in "$tmp_cert" -noout -fingerprint -sha256)

    log "Fingerprint do certificado original: $orig_fingerprint"
    log "Fingerprint do certificado exportado do JKS: $jks_fingerprint"

    if [[ "$orig_fingerprint" == "$jks_fingerprint" ]]; then
        log "✅ Consistência verificada: os fingerprints são idênticos."
    else
        log "⚠ Inconsistência detectada: os fingerprints diferem."
        log "   • Verifique se o certificado foi importado corretamente."
        # Opcional: abortar a execução
        # fail "Inconsistência entre certificado original e JKS"
    fi

    # Remove o arquivo temporário
    rm -f "$tmp_cert"
}

#═══════════════════════════════════════════════════════════════
# Funções auxiliares adicionais (menu interativo)
#═══════════════════════════════════════════════════════════════

# Configura todos os passos de configuração de certificados
configure_certificates() {
    backup_cacerts
    import_root_app_to_cacerts
    convert_cert_to_jks
    import_sso_to_jks
    verify_keystores
    final_message
}

# Verifica variáveis de ambiente e caminhos críticos
check_vars_and_paths() {
    log "Verificando variáveis de ambiente e caminhos ..."
    : "${JAVA_HOME:?JAVA_HOME não definido}"
    : "${KEYTOOL:?KEYTOOL não definido}"
    for f in "$ROOT_CERT" "$APP_CERT" "$SSO_CERT" "$CERT_FILE"; do
        [[ -f "$f" ]] && log "Encontrado: $f" || log "Ausente: $f"
    done
    [[ -d "$(dirname "$JKS_FILE")" ]] && log "Diretório JKS existe" || log "Diretório JKS não encontrado"
    log "Verificação concluída."
}

# Exibe informações resumidas das configurações
show_info() {
    echo "═══ CONFIGURAÇÕES ATUAIS ═══"
    echo "JAVA_HOME    = $JAVA_HOME"
    echo "KEYTOOL      = $KEYTOOL"
    echo "CACERTS      = $CACERTS"
    echo "JKS_FILE     = $JKS_FILE"
    echo "APP_ALIAS    = $APP_ALIAS"
    echo "SSO_ALIAS    = $SSO_ALIAS"
    echo "ROOT_CERT    = $ROOT_CERT"
    echo "APP_CERT     = $APP_CERT"
    echo "SSO_CERT     = $SSO_CERT"
    echo "CERT_FILE    = $CERT_FILE"
    echo "════════════════════════════════════════════════════════════════════"
    echo "Aliases no cacerts:"
    $KEYTOOL -list -keystore "$CACERTS" -storepass "$CACERTS_PASS" \
    | grep -E "$(basename "$ROOT_CERT" .cer|tr '[:upper:]' '[:lower:]')|$(basename "$APP_CERT" .cer|tr '[:upper:]' '[:lower:]')" || echo "Nenhum alias encontrado"
    echo "Aliases no JKS:"
    $KEYTOOL -list -keystore "$JKS_FILE" -storepass "$JKS_PASS" \
    | grep -E "$APP_ALIAS|$SSO_ALIAS" || echo "Nenhum alias encontrado"
}

# Apaga todas as configurações criadas pelo script
erase_configurations() {
    log "Removendo keystore JKS ..."
    rm -f "$JKS_FILE"
    log "Removendo backup do cacerts ..."
    rm -f "$CACERTS_BKP"
    log "Removendo log ..."
    rm -f "$LOGFILE"
    log "Todas as configurações foram apagadas."
}

# Exibe o menu de opções ao usuário
show_menu() {
    while true; do
        echo "═══ MENU DE OPÇÕES ═══"
        echo "1) Configurar certificados"
        echo "2) Checar variáveis e caminhos"
        echo "3) Checar consistência de certificados"
        echo "4) Exibir informações de certificados e paths"
        echo "5) Apagar configurações de certificado"
        echo "0) Sair"
        read -p "Selecione uma opção [0-5]: " opt
        echo
        case "$opt" in
            1) configure_certificates ;;
            2) check_vars_and_paths ;;
            3) verify_cert_consistency ;;
            4) show_info ;;
            5) erase_configurations ;;
            0) exit 0 ;;
            *) echo "Opção inválida." ;;
        esac
    done
}

verify_keystores() {
    log "Listando conteúdo do cacerts (filtrando pelos aliases que criamos)"
    $KEYTOOL -list -keystore "$CACERTS" -storepass "$CACERTS_PASS" \
    | grep -E "$(basename "$ROOT_CERT" .cer|tr '[:upper:]' '[:lower:]')|$(basename "$APP_CERT" .cer|tr '[:upper:]' '[:lower:]')" \
    || { log "Nenhum dos aliases esperados encontrado no cacerts (pode ser que já existam)."; }

    log "Listando conteúdo do JKS"
    $KEYTOOL -list -keystore "$JKS_FILE" -storepass "$JKS_PASS" \
    | grep -E "$APP_ALIAS|$SSO_ALIAS" \
    || { log "Alias $APP_ALIAS ou $SSO_ALIAS não encontrados no JKS."; }

    # Fingerprints (SHA-256) - útil para auditoria / comparação com IdP
    log "Fingerprint (SHA-256) do certificado da aplicação (extraído do JKS):"
    $KEYTOOL -exportcert -keystore "$JKS_FILE" -storepass "$JKS_PASS" \
    -alias "$APP_ALIAS" -rfc | openssl x509 -noout -fingerprint -sha256 -inform PEM

    log "Fingerprint (SHA-256) do certificado SSO (do arquivo .cer):"
    openssl x509 -noout -fingerprint -sha256 -inform PEM -in "$SSO_CERT"
}

#═══════════════════════════════════════════════════════════════
# 6 - Finalização
#═══════════════════════════════════════════════════════════════
final_message() {
    echo "════════════════════════════════════════════════════════════════════"
    log "Todas as etapas concluídas com sucesso."
    log "Backup do cacerts: $CACERTS_BKP"
    log "Keystore da aplicação: $JKS_FILE"
    log "Log completo salvo em: $LOGFILE"
    echo "  ✓  Não esqueça de:"
    echo "     • Atualizar as propriedades da aplicação (application.yml / server.xml) apontando para $JKS_FILE"
    echo "     • Reiniciar o servidor WebSphere / Spring Boot"
    echo "     • Testar o fluxo SAML (login → IdP → Assertion)."
    echo "════════════════════════════════════════════════════════════════════"
}

#═══════════════════════════════════════════════════════════════
# Execução sequencial (modo interativo)
#═══════════════════════════════════════════════════════════════
# Se o script for chamado com --no-interactive, executa a configuração completa sem menu
# if [[ "$1" = "--no-interactive" ]]; then
# configure_certificates
# exit 0
# fi

# Caso contrário, exibe o menu de opções
show_menu
