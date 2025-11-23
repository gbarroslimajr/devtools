# CodeGraphAI - Open Questions

## Table of Contents

- [Overview](#overview)
- [Technical Questions](#technical-questions)
- [Architectural Decisions](#architectural-decisions)
- [Feature Requests](#feature-requests)
- [Limitations](#limitations)
- [Related Documentation](#related-documentation)

---

## Overview

Este documento lista questões técnicas em aberto, decisões arquiteturais pendentes e limitações conhecidas do CodeGraphAI.

---

## Technical Questions

### 1. Thread-Safety do LLM

**Questão:** O LLM (HuggingFacePipeline) é thread-safe para processamento paralelo?

**Status:** Não testado
**Impacto:** Alto (afeta implementação de paralelização)
**Ação Necessária:** Testes de concorrência

**Opções:**
- Usar ProcessPoolExecutor (isolamento completo)
- Usar ThreadPoolExecutor (compartilha memória)
- Verificar thread-safety do HuggingFacePipeline

---

### 2. Limitação de ROUTINE_DEFINITION no MySQL

**Questão:** Como lidar com truncamento de `ROUTINE_DEFINITION` em algumas versões do MySQL?

**Status:** Conhecido, não resolvido
**Impacto:** Médio (afeta análise completa)
**Ação Necessária:** Implementar alternativa

**Opções:**
- Usar `SHOW CREATE PROCEDURE` (pode ter limitações)
- Avisar usuário sobre limitação
- Documentar versões afetadas

---

### 3. Validação de JSON do LLM

**Questão:** Como melhorar robustez do parsing de JSON retornado pelo LLM?

**Status:** Parcialmente resolvido
**Impacto:** Médio (pode causar falhas silenciosas)
**Ação Necessária:** Implementar retry e fallback

**Opções:**
- Retry com prompts diferentes
- Fallback para regex quando JSON inválido
- Validação mais rigorosa

---

### 4. Cache de Análise

**Questão:** Qual estratégia de cache usar? Arquivo, banco, ou memória?

**Status:** Não decidido
**Impacto:** Baixo (otimização)
**Ação Necessária:** Decisão de design

**Opções:**
- Arquivo JSON simples
- SQLite para cache
- Redis para cache distribuído
- Memória (apenas sessão atual)

---

### 5. Processamento Assíncrono

**Questão:** Deve usar async/await para I/O de banco?

**Status:** Não decidido
**Impacto:** Baixo (otimização)
**Ação Necessária:** Avaliar benefícios vs complexidade

**Opções:**
- Manter síncrono (simples)
- Migrar para async (mais complexo, mas escalável)

---

## Architectural Decisions

### 1. SQLAlchemy como Abstração

**Questão:** Deve adicionar SQLAlchemy como camada adicional?

**Status:** Em discussão
**Impacto:** Médio (afeta arquitetura)
**Prós:**
- Suporte a mais bancos facilmente
- Abstração de queries
- Migrations

**Contras:**
- Complexidade adicional
- Overhead de performance
- Pode não ser necessário

**Decisão Pendente:** Avaliar necessidade real

---

### 2. Estrutura de Dados para Cache

**Questão:** Como estruturar dados de cache?

**Status:** Não decidido
**Impacto:** Baixo
**Opções:**
- Hash do código → resultado completo
- Hash do código → hash de dependências
- Estrutura hierárquica

---

### 3. Versionamento de Procedures

**Questão:** Como versionar procedures para análise incremental?

**Status:** Não decidido
**Impacto:** Médio
**Opções:**
- Timestamp de modificação
- Hash do código
- Checksum
- Versionamento explícito

---

### 4. Formato de Exportação

**Questão:** Deve adicionar mais formatos de exportação?

**Status:** Não decidido
**Impacto:** Baixo
**Opções:**
- GraphML
- DOT (Graphviz)
- CSV
- Excel

---

## Feature Requests

### 1. Análise de Impacto

**Status:** Planejado
**Prioridade:** Baixa
**Descrição:** Identificar procedures afetadas por mudanças

**Questões:**
- Como determinar impacto?
- Visualização de impacto?
- Integração com Git?

---

### 2. Análise de Triggers e Functions

**Status:** Planejado
**Prioridade:** Baixa
**Descrição:** Estender análise além de procedures

**Questões:**
- Como integrar com análise atual?
- Diferentes tipos de dependências?
- Visualização unificada?

---

### 3. Dashboard Web

**Status:** Planejado
**Prioridade:** Baixa
**Descrição:** Interface web para visualização

**Questões:**
- Framework (Flask/FastAPI)?
- Frontend (React/Vue)?
- Deploy (Docker/Cloud)?

---

### 4. API REST

**Status:** Planejado
**Prioridade:** Baixa
**Descrição:** API para integração

**Questões:**
- Framework (FastAPI/Flask)?
- Autenticação?
- Rate limiting?
- Versionamento?

---

## Limitations

### 1. Performance Sequencial

**Limitação:** Análise é sequencial, lenta para muitos procedures

**Impacto:** Alto
**Mitigação Planejada:** Processamento paralelo

---

### 2. Requisitos de Hardware

**Limitação:** Requer GPU potente para modelos grandes

**Impacto:** Médio
**Mitigação:** Suporte a modelos menores, quantização

---

### 3. Dependências Opcionais

**Limitação:** Drivers de banco são opcionais, podem não estar instalados

**Impacto:** Baixo
**Mitigação:** Validação de dependências, mensagens claras

---

### 4. Limitações de LLM

**Limitação:** LLM pode não entender código complexo perfeitamente

**Impacto:** Médio
**Mitigação:** Fallback heurístico, validação

---

### 5. Truncamento MySQL

**Limitação:** `ROUTINE_DEFINITION` pode estar truncado

**Impacto:** Médio
**Mitigação:** Avisar usuário, implementar alternativa

---

## Related Documentation

- [Project Overview](project-overview.md) - Visão geral
- [Architecture Details](architecture.md) - Arquitetura
- [Improvement Roadmap](improvement-roadmap.md) - Roadmap
- [Performance Analysis](performance-analysis.md) - Performance

---

Generated on: 2024-11-23 16:45:00

