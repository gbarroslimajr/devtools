# CodeGraphAI - Project Overview

## Table of Contents

- [Executive Summary](#executive-summary)
- [High-Level Architecture](#high-level-architecture)
- [Key Components](#key-components)
- [Intelligence Tools](#intelligence-tools)
- [Database Support](#database-support)
- [Environment & Dependencies](#environment--dependencies)
- [Testing & Quality](#testing--quality)
- [Execution & Setup](#execution--setup)
- [Problems Identified](#problems-identified)
- [Recommendations](#recommendations)
- [Constraints](#constraints)
- [Related Documentation](#related-documentation)

---

## Executive Summary

**CodeGraphAI** é uma ferramenta Python para análise inteligente de stored procedures e tabelas de banco de dados usando LLMs (Large Language Models). O projeto utiliza IA local ou via API para mapear dependências, calcular complexidade e gerar visualizações hierárquicas.

**Status:** Ativo, em desenvolvimento contínuo
**Versão:** 1.0.0+
**Python:** 3.9+ (recomendado) ou 3.8+ (mínimo)
**Licença:** MIT

### Objetivo Principal

Automatizar a análise, mapeamento e visualização de dependências entre stored procedures e tabelas de bancos de dados, identificando relacionamentos, calculando complexidade e gerando hierarquias bottom-up automaticamente. Permite escolher entre analisar apenas procedures, apenas tabelas ou ambos.

### Principais Funcionalidades

#### Funcionalidades Core
- 🤖 **Análise com IA Local/API** - Usa modelos LLM (GPT-OSS-120B, Llama, Claude, OpenAI) para entender lógica de negócio
- 📊 **Mapeamento de Dependências** - Identifica chamadas entre procedures e acessos a tabelas
- 🗄️ **Análise de Tabelas** - Analisa estrutura de tabelas (DDL, relacionamentos, índices, foreign keys)
- 🎯 **Hierarquia Bottom-Up** - Organiza procedures e tabelas do nível mais baixo (sem dependências) até alto nível
- 📈 **Cálculo de Complexidade** - Score de 1-10 baseado em estrutura e lógica do código
- 🎨 **Visualizações Mermaid** - Gera diagramas interativos em markdown (procedures e tabelas)
- 💾 **Análise de Arquivos** - Trabalha com arquivos `.prc` locais (sem necessidade de conexão ao banco)
- 🔄 **Agnóstico de Banco** - Suporta Oracle, PostgreSQL, SQL Server e MySQL através de adaptadores
- 🎛️ **Análise Flexível** - Escolha entre analisar tabelas, procedures ou ambos com flag `--analysis-type`

#### Intelligence Tools
- 🧠 **Knowledge Graph Persistente** - Cache estruturado em grafo (NetworkX) para queries rápidas
- 🔍 **Static Code Analyzer** - Análise de código sem LLM usando regex avançado
- 🕷️ **Code Crawler** - Rastreamento recursivo de dependências e fields
- 🤖 **LangChain Agent** - Agent inteligente com ferramentas especializadas
- 💬 **Query Natural** - Faça perguntas em linguagem natural sobre o código
- 🔗 **Field Tracing** - Rastreamento completo de origem e destino de campos
- 📊 **Impact Analysis** - Análise de impacto de mudanças em procedures
- 🔎 **Vector Knowledge Graph** - Busca semântica usando embeddings (sentence-transformers)
- 🎯 **Hybrid Search** - Combina busca vetorial + relacionamentos estruturais do grafo
- 📦 **RAG Pipeline** - Retrieval-Augmented Generation para descoberta inteligente de tabelas/procedures

---

## High-Level Architecture

### Padrão Arquitetural

**Arquitetura em Camadas** com padrões Factory, Strategy e Singleton:

```
┌─────────────────────────────────────────┐
│         CLI Layer (main.py)             │
│  - Click commands                       │
│  - User interface                       │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│      Analysis Layer                     │
│  - ProcedureAnalyzer                    │
│  - TableAnalyzer                        │
│  - LLMAnalyzer                          │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│      Intelligence Layer                │
│  - CodeAnalysisAgent (LangChain)        │
│  - Knowledge Graph (NetworkX)           │
│  - Static Analyzer                      │
│  - Code Crawler                         │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│      IO Layer (Adapters)                │
│  - Factory Pattern                     │
│  - Base Loaders (procedures/tables)    │
│  - Database-specific loaders           │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│      Configuration Layer                │
│  - Config (Singleton)                  │
│  - Environment variables                │
└─────────────────────────────────────────┘
```

### Estrutura de Diretórios

```
CodeGraphAI/
├── app/                          # Módulos principais
│   ├── agents/                  # LangChain Agent
│   │   └── code_analysis_agent.py
│   ├── analysis/                 # Análise estática e crawling
│   │   ├── static_analyzer.py   # Regex-based analysis
│   │   ├── code_crawler.py      # Dependency crawling
│   │   └── on_demand_analyzer.py # Lazy analysis
│   ├── config/                   # Configuração
│   │   └── config.py             # Singleton config
│   ├── core/                     # Modelos e exceções
│   │   ├── models.py            # Dataclasses
│   │   └── dry_mode.py          # Dry-run validation
│   ├── graph/                    # Knowledge Graph
│   │   └── knowledge_graph.py   # NetworkX-based graph
│   ├── io/                       # Database adapters
│   │   ├── base.py              # Base loader (procedures)
│   │   ├── table_base.py        # Base loader (tables)
│   │   ├── factory.py           # Factory (procedures)
│   │   ├── table_factory.py     # Factory (tables)
│   │   ├── *_loader.py          # Database-specific loaders
│   │   └── table_cache.py       # Table analysis cache
│   ├── llm/                      # LLM integration
│   │   ├── langchain_wrapper.py # LangChain integration
│   │   ├── genfactory_client.py # GenFactory API client
│   │   ├── token_tracker.py     # Token usage tracking
│   │   └── toon_converter.py    # TOON format optimization
│   └── tools/                     # LangChain tools
│       ├── graph_tools.py        # Graph queries
│       ├── field_tools.py        # Field analysis
│       ├── crawler_tools.py      # Crawling tools
│       └── query_tools.py         # Database queries
├── analyzer.py                   # LLMAnalyzer + ProcedureAnalyzer
├── table_analyzer.py             # TableAnalyzer
├── main.py                       # CLI entrypoint
├── config.py                     # Wrapper (backward compat)
├── tests/                        # Testes unitários (~186 testes)
├── cache/                        # Knowledge graph cache
├── output/                       # Resultados gerados
└── examples/                     # Exemplos de uso
```

### Camadas Principais

1. **Camada de I/O** (`app/io/`)
   - Interface abstrata: `ProcedureLoaderBase`, `TableLoaderBase`
   - Adaptadores específicos por banco (Oracle, PostgreSQL, MSSQL, MySQL)
   - Factory pattern para criação dinâmica
   - File loader para arquivos locais
   - Cache de análise de tabelas

2. **Camada Core** (`app/core/`)
   - Modelos de dados: `ProcedureInfo`, `TableInfo`, `DatabaseConfig`
   - Exceções customizadas: `CodeGraphAIError`, `ProcedureLoadError`, etc.
   - Enums: `DatabaseType`, `LLMProvider`
   - Dry-run validation

3. **Camada de Análise** (`analyzer.py`, `table_analyzer.py`)
   - `LLMAnalyzer`: Análise de código usando LLM (local ou API)
   - `ProcedureAnalyzer`: Orquestração completa da análise de procedures
   - `TableAnalyzer`: Análise de tabelas com batch processing e paralelismo
   - NetworkX para construção de grafos de dependências
   - Exportação de resultados (JSON, PNG, Mermaid)

4. **Camada de Intelligence** (`app/agents/`, `app/graph/`, `app/analysis/`)
   - `CodeAnalysisAgent`: LangChain agent para queries em linguagem natural
   - `CodeKnowledgeGraph`: Grafo persistente para cache e queries
   - `StaticCodeAnalyzer`: Análise regex-based (sem LLM)
   - `CodeCrawler`: Rastreamento recursivo de dependências

5. **Camada de Configuração** (`app/config/`)
   - Gerenciamento centralizado de configuração (Singleton thread-safe)
   - Suporte a variáveis de ambiente (`.env` / `environment.env`)
   - Configuração por banco de dados
   - Suporte a múltiplos providers LLM (OpenAI, Anthropic, GenFactory)

6. **Camada de Interface** (`main.py`)
   - CLI usando Click
   - Comandos: `analyze`, `analyze-files`, `query`, `test-connection`
   - Logging estruturado com auto-logging
   - Dry-run mode para validação

---

## Key Components

### 1. ProcedureLoader / TableLoader (Factory Pattern)

**Responsabilidade:** Carregar procedures e tabelas de diferentes fontes

**Implementações:**
- `OracleLoader` / `OracleTableLoader`: Oracle Database
- `PostgreSQLLoader` / `PostgreSQLTableLoader`: PostgreSQL
- `MSSQLLoader` / `MSSQLTableLoader`: SQL Server
- `MySQLLoader` / `MySQLTableLoader`: MySQL
- `FileLoader`: Arquivos `.prc` locais

**Padrão:** Strategy + Factory

**Localização:** `app/io/`

### 2. LLMAnalyzer

**Responsabilidade:** Análise de código usando LLM (local ou via API)

**Funcionalidades:**
- Análise de lógica de negócio (prompts genéricos)
- Extração de dependências (regex + LLM para validação)
- Cálculo de complexidade (LLM com fallback heurístico)
- Análise de propósito de tabelas
- Tracking de tokens (com suporte a TOON)

**Tecnologias:**
- LangChain para orquestração
- Transformers (HuggingFace) para modelos locais
- PyTorch para execução local
- OpenAI/Anthropic SDK para APIs

**Modos:**
- Local: HuggingFace models (requer GPU)
- API: OpenAI, Anthropic, GenFactory

**Localização:** `analyzer.py`

### 3. ProcedureAnalyzer

**Responsabilidade:** Orquestrar análise completa de procedures

**Funcionalidades:**
- Análise em lote de procedures
- Construção de grafo de dependências (NetworkX)
- Cálculo de níveis hierárquicos (bottom-up)
- Integração com Knowledge Graph
- Exportação de resultados:
  - JSON estruturado
  - Grafo PNG (matplotlib)
  - Diagramas Mermaid (hierarquia e dependências)

**Localização:** `analyzer.py`

### 4. TableAnalyzer

**Responsabilidade:** Orquestrar análise completa de tabelas

**Funcionalidades:**
- Análise de estrutura (DDL, colunas, índices, FKs)
- Batch processing (padrão: 5 tabelas por batch)
- Paralelismo (padrão: 2 workers)
- Cache de análise (evita re-análise)
- Construção de grafo de relacionamentos
- Exportação de resultados (JSON, PNG, Mermaid)

**Otimizações:**
- Processamento em batch reduz chamadas LLM
- Paralelismo acelera análise de múltiplas tabelas
- Cache evita re-análise de tabelas não modificadas

**Localização:** `table_analyzer.py`

### 5. CodeAnalysisAgent

**Responsabilidade:** Agent inteligente para queries em linguagem natural

**Funcionalidades:**
- Processa perguntas em linguagem natural
- Usa 5 tools especializadas:
  - `query_procedure`: Consulta informações de procedures
  - `query_table`: Consulta estrutura de tabelas
  - `analyze_field`: Analisa campos específicos
  - `trace_field_flow`: Rastreia fluxo de campos
  - `crawl_procedure`: Crawling de dependências
  - `execute_query`: Executa queries SELECT (opcional)
- Integração com Knowledge Graph
- Suporte a múltiplas iterações

**Tecnologias:**
- LangChain 1.0+ (create_agent)
- BaseChatModel (qualquer provider)

**Localização:** `app/agents/code_analysis_agent.py`

### 6. CodeKnowledgeGraph

**Responsabilidade:** Grafo persistente para cache e queries rápidas

**Funcionalidades:**
- Armazena procedures, tabelas e fields como nós
- Armazena relacionamentos como arestas (calls, accesses, reads, writes)
- Persistência em JSON (`cache/knowledge_graph.json`)
- Queries rápidas de contexto
- Estatísticas do grafo

**Tecnologias:**
- NetworkX MultiDiGraph

**Localização:** `app/graph/knowledge_graph.py`

### 7. CLI (main.py)

**Responsabilidade:** Interface de linha de comando

**Comandos:**
- `analyze`: Análise de banco de dados (procedures e/ou tabelas)
- `analyze-files`: Análise de arquivos `.prc` locais
- `query`: Query inteligente usando Agent
- `test-connection`: Teste de conectividade com banco

**Opções:**
- Suporte a múltiplos bancos (`--db-type`, `--host`, `--port`, `--database`)
- Configuração de modelo LLM (`--model`, `--device`)
- Tipo de análise (`--analysis-type`: tables, procedures, both)
- Exportação flexível (`--export-json`, `--export-png`, `--export-mermaid`)
- Batch processing e paralelismo (`--batch-size`, `--parallel-workers`)
- Dry-run mode (`--dry-run`)
- Auto-logging configurável

---

## Intelligence Tools

### Knowledge Graph

**Descrição:** Cache estruturado em grafo (NetworkX) para queries rápidas

**Funcionalidades:**
- Persistência em JSON
- Armazena procedures, tabelas e fields
- Relacionamentos: calls, accesses, reads, writes
- Queries de contexto rápidas

**Uso:**
```python
from app.graph.knowledge_graph import CodeKnowledgeGraph

kg = CodeKnowledgeGraph(cache_path="./cache/knowledge_graph.json")
kg.add_procedure(proc_info)
context = kg.get_procedure_context("SCHEMA.PROCEDURE_NAME")
```

### Static Code Analyzer

**Descrição:** Análise de código sem LLM usando regex avançado

**Funcionalidades:**
- Extração de fields usados
- Detecção de operações (read/write)
- Transformações aplicadas
- Contextos de uso

**Localização:** `app/analysis/static_analyzer.py`

### Code Crawler

**Descrição:** Rastreamento recursivo de dependências e fields

**Funcionalidades:**
- Árvore completa de dependências
- Análise de impacto
- Field tracing
- Procedures e tabelas envolvidas

**Localização:** `app/analysis/code_crawler.py`

### LangChain Agent

**Descrição:** Agent inteligente com tools especializadas

**Funcionalidades:**
- Processa perguntas em linguagem natural
- Escolhe tools apropriadas automaticamente
- Múltiplas iterações para queries complexas
- Integração com Knowledge Graph

**Localização:** `app/agents/code_analysis_agent.py`

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

- **Interface Abstrata:** `ProcedureLoaderBase`, `TableLoaderBase`
- **Factory Pattern:** Criação dinâmica baseada em `DatabaseType`
- **Registro Automático:** Loaders se registram ao importar módulo
- **Validação de Dependências:** Verifica se driver necessário está instalado
- **Extensibilidade:** Fácil adicionar novos adaptadores

### Configuração

Suporta configuração via:
- Variáveis de ambiente (`.env` / `environment.env`)
- Parâmetros CLI
- Classe `Config` (Singleton thread-safe)

---

## Environment & Dependencies

### Python Version

- **Mínimo:** Python 3.8+ (3.9+ recomendado)
- **Configurado em:** `pyproject.toml` (target-version: py38-py311)

### Gerenciamento de Dependências

- **Arquivo principal:** `requirements.txt`
- **Desenvolvimento:** `requirements-dev.txt`
- **Instalação:** `pip install -r requirements.txt`

### Dependências Principais

**Core:**
- `langchain>=1.0.0` - Framework LLM e agents
- `langchain-core>=1.0.0` - Core LangChain
- `langchain-community>=0.0.13` - Community integrations
- `networkx>=3.0` - Grafos
- `click>=8.0.0` - CLI
- `python-dotenv>=1.0.0` - Environment variables

**LLM (Local):**
- `transformers>=4.35.0` - HuggingFace models
- `torch>=2.0.0` - PyTorch
- `accelerate>=0.25.0` - Model acceleration
- `bitsandbytes>=0.41.0` - Quantização 8-bit

**LLM (API):**
- `openai>=1.0.0` - OpenAI SDK
- `langchain-openai>=0.1.0` - LangChain OpenAI
- `anthropic>=0.18.0` - Anthropic SDK
- `langchain-anthropic>=0.1.0` - LangChain Anthropic
- `requests>=2.31.0` - HTTP requests

**Database (Opcional):**
- `oracledb>=1.4.0` - Oracle
- `psycopg2-binary>=2.9.0` - PostgreSQL
- `pyodbc>=5.0.0` - SQL Server
- `mysql-connector-python>=8.0.0` - MySQL

**Visualização:**
- `matplotlib>=3.7.0` - Gráficos
- `tqdm>=4.65.0` - Progress bars

**Otimização:**
- `toon-python @ git+...` - TOON format (otimização de tokens)

**Desenvolvimento:**
- `pytest>=7.0.0` - Testes
- `black>=23.0.0` - Formatação
- `mypy>=1.0.0` - Type checking
- `isort>=5.12.0` - Import sorting
- `flake8>=6.0.0` - Linting

### Virtual Environment

O projeto não define um gerenciador específico. Recomendado:
- `venv` (built-in)
- `poetry` (não configurado, mas compatível)
- `pipenv` (não configurado)

---

## Testing & Quality

### Estrutura de Testes

**Framework:** pytest

**Estrutura:**
```
tests/
├── conftest.py              # Fixtures globais
├── test_config.py           # Testes de configuração
├── test_llm_analyzer.py     # Testes LLM
├── test_procedure_analyzer.py
├── test_table_analyzer.py
├── analysis/                # Testes de análise estática
├── core/                    # Testes de core
├── io/                      # Testes de loaders
├── llm/                     # Testes de integração LLM
└── tools/                   # Testes de tools
```

**Total de Testes:** ~186 funções de teste

### Cobertura

- `pytest-cov` disponível em `requirements-dev.txt`
- Não há configuração explícita de cobertura no `pyproject.toml`

### Ferramentas de Qualidade

**Configuradas em `pyproject.toml`:**

1. **Black** (formatação)
   - Line length: 100
   - Target: Python 3.8-3.11

2. **isort** (imports)
   - Profile: black
   - Line length: 100

3. **mypy** (type checking)
   - Python version: 3.9 (recomendado) ou 3.8 (mínimo)
   - `ignore_missing_imports=true` para algumas libs
   - Exclui: tests/, build/, dist/

4. **pytest**
   - Test paths: `tests`
   - Verbose mode padrão

---

## Execution & Setup

### Como o Projeto Executa

**Entry Point:** `main.py`

**Comandos CLI (Click):**

1. `analyze` - Análise de banco de dados
   ```bash
   python main.py analyze --analysis-type=both --db-type postgresql ...
   ```

2. `analyze-files` - Análise de arquivos .prc
   ```bash
   python main.py analyze-files --directory ./procedures
   ```

3. `query` - Query com Agent
   ```bash
   python main.py query "O que faz a procedure X?"
   ```

4. `test-connection` - Teste de conexão
   ```bash
   python main.py test-connection --db-type postgresql ...
   ```

### Setup Local

**1. Clone e Ambiente Virtual:**
```bash
cd CodeGraphAI
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

**2. Instalar Dependências:**
```bash
pip install -r requirements.txt
# Para desenvolvimento:
pip install -r requirements-dev.txt
```

**3. Configurar Ambiente:**
```bash
cp example.env .env
# ou
cp example.env environment.env
# Edite com suas credenciais
```

**4. Instalar Drivers de Banco (opcional):**
```bash
# Apenas os necessários
pip install psycopg2-binary  # PostgreSQL
# ou
pip install oracledb  # Oracle
```

**5. Executar Testes:**
```bash
pytest
# ou com cobertura:
pytest --cov=app --cov-report=html
```

### Dependências Externas

**Banco de Dados:**
- PostgreSQL, Oracle, SQL Server, MySQL (opcional)
- Apenas para análise de banco
- Análise de arquivos não requer banco

**LLM:**
- Modo Local: GPU recomendada (24GB+ VRAM para modelos 120B)
- Modo API: Requer API keys (OpenAI, Anthropic, GenFactory)

**Sistema:**
- Python 3.8+
- Git (para toon-python)

---

## Problems Identified

### Resolvidos ✅

1. ~~**Acoplamento ao Oracle**~~ → Resolvido com arquitetura de adaptadores
2. ~~**Falta de estrutura modular**~~ → Resolvido com estrutura `app/`
3. ~~**Prompts específicos Oracle**~~ → Atualizados para genéricos
4. ~~**Falta de testes**~~ → Estrutura de testes criada (~186 testes)
5. ~~**Logging com print()**~~ → Substituído por logging estruturado
6. ~~**Falta de exceções customizadas**~~ → Implementadas em `app/core/models.py`
7. ~~**Falta de análise de tabelas**~~ → Implementado `TableAnalyzer` com batch/paralelismo
8. ~~**Falta de queries inteligentes**~~ → Implementado Agent com LangChain

### Em Aberto ⚠️

1. **Performance:** Análise sequencial de procedures pode ser lenta
   - Oportunidade: Processamento paralelo/assíncrono
   - Status: Planejado no roadmap

2. **Limitações MySQL:** `ROUTINE_DEFINITION` pode estar truncado em algumas versões
   - Requer implementação alternativa ou warning ao usuário

3. **Validação de Saída LLM:** JSON parsing pode falhar silenciosamente
   - Melhorar tratamento de erros e retry logic

4. **Documentação de API:** Falta documentação detalhada de métodos públicos
   - Criar docstrings completas e exemplos

5. **Cache de Knowledge Graph:** Pode ficar desatualizado
   - Não há invalidação automática
   - Requer estratégia de versionamento

6. **Docker Support:** Não há Dockerfile ou docker-compose
   - Facilitaria setup e deployment

7. **CI/CD:** Não há pipeline de CI/CD configurado
   - Testes automáticos
   - Linting automático

---

## Recommendations

### Curto Prazo

1. **Adicionar processamento paralelo** para análise de procedures
2. **Melhorar validação de saída LLM** com retry e fallback robusto
3. **Adicionar cache** para resultados de análise LLM (evitar re-análise)
4. **Criar documentação de API** completa com exemplos
5. **Implementar invalidação de cache** para Knowledge Graph

### Médio Prazo

1. **Docker Support** - Dockerfile e docker-compose para ambiente isolado
2. **CI/CD Pipeline** - GitHub Actions / GitLab CI para testes automáticos
3. **Melhorar type hints** - Cobertura completa de type hints, mypy strict mode
4. **Logging estruturado** - JSON logging para produção, log rotation
5. **Métricas e Observabilidade** - Prometheus metrics, OpenTelemetry tracing

### Longo Prazo

1. **Distribuir processamento** com Dask ou similar
2. **API REST** para integração com outras ferramentas
3. **Integração com CI/CD** para análise contínua
4. **Suporte a análise de triggers e functions** além de procedures
5. **Análise de impacto** (quais procedures são afetadas por mudanças)
6. **Interface Web interativa** para visualização

---

## Constraints

### Técnicos

- **Hardware:** Requer GPU NVIDIA (24GB+ VRAM) para modelos grandes (120B) em modo local
- **Python:** Versão mínima 3.8
- **Dependências:** Drivers de banco são opcionais mas necessários para uso
- **Memória:** Modelos LLM grandes consomem muita RAM/VRAM
- **Quantização:** Suporta quantização 8-bit para reduzir uso de memória
- **Modo API:** Requer API keys e conexão com internet

### Arquiteturais

- **Backward Compatibility:** Mantida para código existente
- **Extensibilidade:** Fácil adicionar novos adaptadores
- **Testabilidade:** Estrutura permite testes isolados
- **Modularidade:** Separação clara de responsabilidades
- **Thread-Safety:** Config usa Singleton thread-safe

### Operacionais

- **Credenciais:** Devem ser gerenciadas via `.env` (não versionado)
- **Modelos LLM:** Devem ser baixados/instalados separadamente (modo local)
- **Drivers de Banco:** Devem ser instalados conforme necessidade
- **Configuração:** Suporta múltiplos métodos (env vars, CLI, config class)
- **Cache:** Knowledge Graph cache pode crescer significativamente

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

---
Generated on: 2025-11-24 19:39:51
