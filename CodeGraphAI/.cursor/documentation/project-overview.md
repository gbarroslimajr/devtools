# CodeGraphAI - Project Overview

## Table of Contents

- [Executive Summary](#executive-summary)
- [High-Level Architecture](#high-level-architecture)
- [Key Components](#key-components)
- [Database Support](#database-support)
- [Problems Identified](#problems-identified)
- [Recommendations](#recommendations)
- [Constraints](#constraints)
- [Related Documentation](#related-documentation)

---

## Executive Summary

**CodeGraphAI** é uma ferramenta Python para análise inteligente de stored procedures usando LLMs (Large Language Models) locais. O projeto foi recentemente refatorado para suportar múltiplos bancos de dados (Oracle, PostgreSQL, SQL Server, MySQL) através de uma arquitetura baseada em adaptadores, mantendo backward compatibility com código existente.

**Status:** Ativo, em desenvolvimento
**Versão:** 1.0.0
**Python:** 3.8+
**Licença:** MIT

### Objetivo Principal

Automatizar a análise, mapeamento e visualização de dependências entre stored procedures de bancos de dados, identificando relacionamentos, calculando complexidade e gerando hierarquias bottom-up automaticamente.

### Principais Funcionalidades

- 🤖 **Análise com IA Local** - Usa modelos LLM (GPT-OSS-120B, Llama, etc.) para entender lógica de negócio
- 📊 **Mapeamento de Dependências** - Identifica chamadas entre procedures e acessos a tabelas
- 🎯 **Hierarquia Bottom-Up** - Organiza procedures do nível mais baixo (sem dependências) até alto nível
- 📈 **Cálculo de Complexidade** - Score de 1-10 baseado em estrutura e lógica do código
- 🎨 **Visualizações Mermaid** - Gera diagramas interativos em markdown
- 💾 **Análise de Arquivos** - Trabalha com arquivos `.prc` locais (sem necessidade de conexão ao banco)
- 🔄 **Agnóstico de Banco** - Suporta Oracle, PostgreSQL, SQL Server e MySQL através de adaptadores

---

## High-Level Architecture

### Padrão Arquitetural

**Monolítico Modular** com separação clara de responsabilidades:

```
┌─────────────────────────────────────────┐
│           CLI (main.py)                  │
│         Interface do Usuário             │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│      ProcedureAnalyzer                   │
│      Orquestração de Análise             │
└──────┬───────────────────┬───────────────┘
       │                   │
┌──────▼──────┐    ┌───────▼──────────────┐
│ LLMAnalyzer │    │  ProcedureLoader     │
│  Análise IA │    │  (Factory Pattern)   │
└─────────────┘    └───────┬──────────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
    ┌─────────▼──┐  ┌─────▼────┐  ┌───▼──────┐
    │   Oracle   │  │PostgreSQL │  │  MSSQL   │
    │   Loader   │  │  Loader   │  │  Loader  │
    └────────────┘  └───────────┘  └──────────┘
```

### Camadas Principais

1. **Camada de I/O** (`app/io/`)
   - Interface abstrata: `ProcedureLoaderBase`
   - Adaptadores específicos por banco (Oracle, PostgreSQL, MSSQL, MySQL)
   - Factory pattern para criação dinâmica
   - File loader para arquivos locais

2. **Camada Core** (`app/core/`)
   - Modelos de dados: `ProcedureInfo`, `DatabaseConfig`
   - Exceções customizadas: `CodeGraphAIError`, `ProcedureLoadError`, etc.
   - Enums: `DatabaseType`

3. **Camada de Análise** (`analyzer.py`)
   - `LLMAnalyzer`: Análise de código usando LLM local
   - `ProcedureAnalyzer`: Orquestração completa da análise
   - NetworkX para construção de grafos de dependências
   - Exportação de resultados (JSON, PNG, Mermaid)

4. **Camada de Configuração** (`app/config/`)
   - Gerenciamento centralizado de configuração
   - Suporte a variáveis de ambiente (`.env` / `environment.env`)
   - Configuração por banco de dados

5. **Camada de Interface** (`main.py`)
   - CLI usando Click
   - Comandos: `analyze-files`, `analyze-db`, `export`
   - Logging estruturado

---

## Key Components

### 1. ProcedureLoader (Factory Pattern)

**Responsabilidade:** Carregar procedures de diferentes fontes

**Implementações:**
- `OracleLoader`: Oracle Database (padrão, backward compatible)
- `PostgreSQLLoader`: PostgreSQL
- `MSSQLLoader`: SQL Server
- `MySQLLoader`: MySQL
- `FileLoader`: Arquivos `.prc` locais

**Padrão:** Strategy + Factory

**Localização:** `app/io/`

### 2. LLMAnalyzer

**Responsabilidade:** Análise de código usando LLM local

**Funcionalidades:**
- Análise de lógica de negócio (prompts genéricos, não específicos de banco)
- Extração de dependências (regex + LLM para validação)
- Cálculo de complexidade (LLM com fallback heurístico)

**Tecnologias:**
- LangChain para orquestração
- Transformers (HuggingFace) para modelos
- PyTorch para execução

**Localização:** `analyzer.py`

### 3. ProcedureAnalyzer

**Responsabilidade:** Orquestrar análise completa de procedures

**Funcionalidades:**
- Análise em lote de procedures
- Construção de grafo de dependências (NetworkX)
- Cálculo de níveis hierárquicos (bottom-up)
- Exportação de resultados:
  - JSON estruturado
  - Grafo PNG (matplotlib)
  - Diagramas Mermaid (hierarquia e dependências)

**Localização:** `analyzer.py`

### 4. CLI (main.py)

**Responsabilidade:** Interface de linha de comando

**Comandos:**
- `analyze-files`: Análise de arquivos `.prc` locais
- `analyze-db`: Análise direta do banco de dados
- `export`: Exportação de visualizações (parcialmente implementado)

**Opções:**
- Suporte a múltiplos bancos (`--db-type`, `--host`, `--port`, `--database`)
- Configuração de modelo LLM (`--model`, `--device`)
- Exportação flexível (`--export-json`, `--export-png`, `--export-mermaid`)

---

## Database Support

### Bancos Suportados

| Banco | Driver | Status | Observações |
|-------|--------|--------|-------------|
| Oracle | `oracledb` | ✅ Implementado | Padrão (backward compatibility) |
| PostgreSQL | `psycopg2-binary` | ✅ Implementado | Requer PostgreSQL 11+ |
| SQL Server | `pyodbc` | ✅ Implementado | Requer ODBC Driver |
| MySQL | `mysql-connector-python` | ✅ Implementado | Suporta múltiplos drivers |

### Arquitetura de Adaptadores

- **Interface Abstrata:** `ProcedureLoaderBase` (`app/io/base.py`)
- **Factory Pattern:** Criação dinâmica baseada em `DatabaseType` (`app/io/factory.py`)
- **Registro Automático:** Loaders se registram ao importar módulo
- **Validação de Dependências:** Verifica se driver necessário está instalado
- **Extensibilidade:** Fácil adicionar novos adaptadores

### Configuração

Suporta configuração via:
- Variáveis de ambiente (`.env` / `environment.env`)
- Parâmetros CLI
- Classe `Config` (`app/config/config.py`)

---

## Problems Identified

### Resolvidos ✅

1. ~~**Acoplamento ao Oracle**~~ → Resolvido com arquitetura de adaptadores
2. ~~**Falta de estrutura modular**~~ → Resolvido com estrutura `app/`
3. ~~**Prompts específicos Oracle**~~ → Atualizados para genéricos
4. ~~**Falta de testes**~~ → Estrutura de testes criada
5. ~~**Logging com print()**~~ → Substituído por logging estruturado
6. ~~**Falta de exceções customizadas**~~ → Implementadas em `app/core/models.py`

### Em Aberto ⚠️

1. **Performance:** Análise sequencial pode ser lenta para muitos procedures
   - Oportunidade: Processamento paralelo/assíncrono

2. **Limitações MySQL:** `ROUTINE_DEFINITION` pode estar truncado em algumas versões
   - Requer implementação alternativa ou warning ao usuário

3. **Validação de Saída LLM:** JSON parsing pode falhar silenciosamente
   - Melhorar tratamento de erros e retry logic

4. **Documentação de API:** Falta documentação detalhada de métodos públicos
   - Criar docstrings completas e exemplos

5. **Exportação de JSON:** Comando `export` ainda não implementado completamente
   - Reconstruir `ProcedureAnalyzer` a partir de JSON

---

## Recommendations

### Curto Prazo

1. **Adicionar processamento paralelo** para análise de múltiplas procedures
2. **Melhorar validação de saída LLM** com retry e fallback robusto
3. **Adicionar cache** para resultados de análise LLM (evitar re-análise)
4. **Criar documentação de API** completa com exemplos
5. **Implementar comando export** completamente

### Médio Prazo

1. **Implementar SQLAlchemy** como camada de abstração adicional (opcional)
2. **Adicionar suporte a mais bancos** (SQLite, MariaDB, etc.)
3. **Criar dashboard web** para visualização interativa
4. **Adicionar métricas de performance** e profiling
5. **Implementar análise incremental** (apenas procedures modificadas)

### Longo Prazo

1. **Distribuir processamento** com Dask ou similar
2. **API REST** para integração com outras ferramentas
3. **Integração com CI/CD** para análise contínua
4. **Suporte a análise de triggers e functions** além de procedures
5. **Análise de impacto** (quais procedures são afetadas por mudanças)

---

## Constraints

### Técnicos

- **Hardware:** Requer GPU NVIDIA (24GB+ VRAM) para modelos grandes (120B)
- **Python:** Versão mínima 3.8
- **Dependências:** Drivers de banco são opcionais mas necessários para uso
- **Memória:** Modelos LLM grandes consomem muita RAM/VRAM
- **Quantização:** Suporta quantização 8-bit para reduzir uso de memória

### Arquiteturais

- **Backward Compatibility:** Mantida para código existente
- **Extensibilidade:** Fácil adicionar novos adaptadores
- **Testabilidade:** Estrutura permite testes isolados
- **Modularidade:** Separação clara de responsabilidades

### Operacionais

- **Credenciais:** Devem ser gerenciadas via `.env` (não versionado)
- **Modelos LLM:** Devem ser baixados/instalados separadamente
- **Drivers de Banco:** Devem ser instalados conforme necessidade
- **Configuração:** Suporta múltiplos métodos (env vars, CLI, config class)

---

## Related Documentation

- [Architecture Details](architecture.md) - Arquitetura detalhada e padrões de design
- [Database Adapters](database-adapters.md) - Guia completo dos adaptadores de banco
- [API Catalog](api-catalog.md) - Referência de APIs e classes públicas
- [Integration Flows](integration-flows.md) - Fluxos de integração e sequência
- [Security Overview](security-overview.md) - Segurança e gerenciamento de credenciais
- [Performance Analysis](performance-analysis.md) - Performance e otimizações
- [Improvement Roadmap](improvement-roadmap.md) - Roadmap de melhorias planejadas
- [Open Questions](open-questions.md) - Questões técnicas em aberto

---

Generated on: 2024-11-23 16:45:00

