# CodeGraphAI - Security Overview

## Table of Contents

- [Overview](#overview)
- [Credential Management](#credential-management)
- [Environment Variables](#environment-variables)
- [Best Practices](#best-practices)
- [Security Considerations](#security-considerations)
- [Related Documentation](#related-documentation)

---

## Overview

Este documento descreve as práticas de segurança do CodeGraphAI, focando no gerenciamento de credenciais e configurações sensíveis.

---

## Credential Management

### Arquivos de Configuração

O CodeGraphAI suporta dois arquivos de configuração:

1. **`environment.env`** (template, versionado)
   - Contém variáveis de exemplo
   - Pode ser commitado no repositório
   - Serve como documentação

2. **`.env`** (local, não versionado)
   - Contém credenciais reais
   - **NUNCA deve ser commitado**
   - Está no `.gitignore`

### Estrutura Recomendada

```bash
# 1. Copie o template
cp environment.env .env

# 2. Edite .env com suas credenciais reais
# (não será commitado)

# 3. O código carrega automaticamente
```

### Ordem de Carregamento

O sistema tenta carregar na seguinte ordem:

1. `.env` (se existir)
2. `environment.env` (se `.env` não existir)
3. Variáveis de ambiente do sistema
4. Valores padrão

---

## Environment Variables

### Variáveis de Banco de Dados

**⚠️ SENSÍVEIS - NÃO COMMITAR**

```bash
# Oracle
CODEGRAPHAI_DB_USER=usuario_real
CODEGRAPHAI_DB_PASSWORD=senha_real
CODEGRAPHAI_DB_HOST=localhost:1521/ORCL
CODEGRAPHAI_DB_SCHEMA=MEU_SCHEMA

# PostgreSQL / SQL Server / MySQL
CODEGRAPHAI_DB_TYPE=postgresql
CODEGRAPHAI_DB_USER=usuario_real
CODEGRAPHAI_DB_PASSWORD=senha_real
CODEGRAPHAI_DB_HOST=localhost
CODEGRAPHAI_DB_PORT=5432
CODEGRAPHAI_DB_NAME=meu_banco
```

### Variáveis de LLM

**⚠️ PODE CONTER CAMINHOS SENSÍVEIS**

```bash
CODEGRAPHAI_MODEL_NAME=gpt-oss-120b
CODEGRAPHAI_DEVICE=cuda
CODEGRAPHAI_LLM_MAX_NEW_TOKENS=1024
CODEGRAPHAI_LLM_TEMPERATURE=0.3
```

### Variáveis de Sistema

**✅ SEGURAS - PODE COMMITAR**

```bash
CODEGRAPHAI_OUTPUT_DIR=./output
CODEGRAPHAI_LOG_LEVEL=INFO
```

---

## Best Practices

### 1. Nunca Commitar Credenciais

✅ **Correto:**
```bash
# .gitignore já protege .env
.env
*.env.local
```

❌ **Incorreto:**
```bash
# NUNCA faça isso
git add .env
git commit -m "Add credentials"
```

### 2. Use Variáveis de Ambiente em Produção

✅ **Correto:**
```bash
# Em produção, use variáveis de ambiente do sistema
export CODEGRAPHAI_DB_USER=usuario
export CODEGRAPHAI_DB_PASSWORD=senha
python main.py analyze-db ...
```

### 3. Rotacione Credenciais Regularmente

- Mude senhas periodicamente
- Use credenciais com permissões mínimas necessárias
- Revogue credenciais antigas

### 4. Permissões de Arquivo

```bash
# Proteja .env com permissões restritas
chmod 600 .env
```

### 5. Não Logar Credenciais

O código já evita logar senhas:

```python
# ✅ Correto - não loga senha
logger.info(f"Conectando ao banco {db_type}...")

# ❌ Incorreto - nunca faça isso
logger.info(f"Senha: {password}")
```

---

## Security Considerations

### 1. Conexões de Banco de Dados

- **Criptografia:** Use SSL/TLS quando disponível
- **Timeout:** Configure timeouts apropriados
- **Pooling:** Evite manter conexões abertas desnecessariamente

### 2. Modelos LLM

- **Local:** Modelos são executados localmente (mais seguro)
- **Caminhos:** Verifique caminhos de modelos para evitar path traversal
- **Permissões:** Modelos devem estar em diretórios protegidos

### 3. Arquivos de Saída

- **Permissões:** Arquivos gerados devem ter permissões apropriadas
- **Conteúdo:** JSON pode conter código-fonte sensível
- **Localização:** Não salve em diretórios públicos

### 4. CLI

- **Senhas:** Use `--password` com `prompt=True` (não aparece no histórico)
- **Histórico:** Evite passar senhas via argumentos CLI
- **Logs:** Verifique se logs não contêm credenciais

### 5. Dependências

- **Atualizações:** Mantenha dependências atualizadas
- **Vulnerabilidades:** Monitore CVE para dependências
- **Auditoria:** Use `pip-audit` ou similar

---

## Checklist de Segurança

Antes de fazer deploy:

- [ ] `.env` está no `.gitignore`
- [ ] `environment.env` não contém credenciais reais
- [ ] Credenciais têm permissões mínimas necessárias
- [ ] Senhas são fortes e únicas
- [ ] Conexões usam SSL/TLS quando disponível
- [ ] Logs não contêm credenciais
- [ ] Arquivos de saída têm permissões apropriadas
- [ ] Dependências estão atualizadas
- [ ] Não há credenciais hardcoded no código

---

## Related Documentation

- [Project Overview](project-overview.md) - Visão geral
- [Configuration](api-catalog.md#configuration) - Referência de configuração
- [Integration Flows](integration-flows.md) - Exemplos de uso

---

Generated on: 2024-11-23 16:45:00

