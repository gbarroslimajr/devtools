#!/usr/bin/ksh
###############################################################################
# gpg_env.sh — Variáveis de ambiente para decrypt CFT/SOLAAR
#
# Este arquivo é carregado pelo decrypt_SOLAAR.sh.
# Contém APENAS:
#   - paths base
#   - home GPG
#   - credenciais GPG (PASS)
#   - usuários e grupos
# Não contém INPUTFILE/OUTPUTFILE fixos (não são usados no novo fluxo).
###############################################################################

############################
# Diretório base do projeto
############################
# Exemplo (anônimo):
# /home/dstx/projects/CPF
HOMEDIR="/home/<anonimo>/projects/CPF"


############################
# Diretorio do GnuPG
############################
# Exemplo real:
# /home/dstx/projects/CPF/cft/gnupg
HOMEDIRGPG="$HOMEDIR/cft/gnupg"


############################
# Senha da chave privada GPG
############################
# (Valor aqui deve ser substituído pela senha real do PRD/UAT —
#  mas sem expor em documentação)
PASS="<SENHA_GPG_ANONIMIZADA>"


############################
# Usuário e grupo para chown
############################
USER="cpf"
USERGROUP="TXQUA"   # ou TXPRD em produção, se aplicável


############################
# Log padrão legado (opcional)
############################
# Mantido apenas para compatibilidade com FORMEL
LOGFILE="$HOMEDIR/archives/log/gpg.log"


###############################################################################
# OBS:
# As variáveis INPUTFILE e OUTPUTFILE NÃO são usadas no fluxo SOLAAR.
# O decrypt_SOLAAR.sh processa múltiplos arquivos dinamicamente.
###############################################################################

