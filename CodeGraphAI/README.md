# CodeGraphAI 🔍

> Análise inteligente de procedures e tabelas de banco de dados usando IA

CodeGraphAI é uma ferramenta Python que utiliza LLMs (Large Language Models) para analisar, mapear e visualizar dependências entre stored procedures e tabelas de bancos de dados. Identifica relacionamentos, calcula complexidade e gera hierarquias automaticamente.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)

**Requisitos de Python:**
- **Mínimo**: Python 3.8+
- **Recomendado**: Python 3.9+ ou superior
- **Testado**: Python 3.10, 3.11

## 📚 Documentação

Para informações técnicas detalhadas, consulte a [documentação oficial](.cursor/documentation/):

- **[Project Overview](.cursor/documentation/project-overview.md)** - Visão geral do projeto, funcionalidades e arquitetura
- **[Architecture](.cursor/documentation/architecture.md)** - Detalhes arquiteturais e padrões de design
- **[API Catalog](.cursor/documentation/api-catalog.md)** - Referência completa de APIs
- **[Integration Flows](.cursor/documentation/integration-flows.md)** - Fluxos de integração e exemplos
- **[Database Adapters](.cursor/documentation/database-adapters.md)** - Guia dos adaptadores de banco
- **[Security Overview](.cursor/documentation/security-overview.md)** - Segurança e gerenciamento de credenciais
- **[Performance Analysis](.cursor/documentation/performance-analysis.md)** - Performance e otimizações

## ✨ Funcionalidades Principais

- 🤖 **Análise com IA** - LLMs locais ou via API (OpenAI, Anthropic, GenFactory)
- 📊 **Mapeamento de Dependências** - Identifica relacionamentos entre procedures e tabelas
- 🗄️ **Análise de Tabelas** - Estrutura completa (DDL, relacionamentos, índices)
- 🎯 **Hierarquia Automática** - Organização bottom-up por níveis de dependência
- 📈 **Cálculo de Complexidade** - Score de 1-10 baseado em estrutura e lógica
- 🎨 **Visualizações Mermaid** - Diagramas interativos em markdown
- 🔎 **Busca Semântica** - Vector Knowledge Graph com RAG para descoberta inteligente
- 💬 **Query Natural** - Perguntas em linguagem natural sobre o código
- 🔄 **Agnóstico de Banco** - Suporta Oracle, PostgreSQL, SQL Server e MySQL

> 📖 Para detalhes completos sobre funcionalidades, veja [Project Overview](.cursor/documentation/project-overview.md)

## 🚀 Quick Start

### Instalação

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/CodeGraphAI.git
cd CodeGraphAI

# Crie ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Instale dependências
pip install -r requirements.txt

# Configure variáveis de ambiente
cp example.env .env
# Edite .env com suas credenciais reais
```

### Uso Básico

```bash
# Análise de procedures e tabelas (PostgreSQL)
python main.py analyze --analysis-type=both \
    --db-type postgresql \
    --user postgres --password senha \
    --host localhost --port 5432 \
    --database meu_banco --schema public

# Análise de arquivos locais
python main.py analyze-files --directory ./procedures

# Query inteligente (requer análise prévia)
python main.py query "O que faz a procedure PROCESSAR_PEDIDO?"
```

> 📖 Para mais exemplos e casos de uso, veja [Integration Flows](.cursor/documentation/integration-flows.md)

## 📋 Requisitos

### Versão do Python

- **Mínimo**: Python 3.8+
- **Recomendado**: Python 3.9+ ou superior
- **Testado**: Python 3.10, 3.11

> **Nota**: Python 3.9+ é recomendado para melhor compatibilidade com `chromadb` e outras dependências modernas.

### Dependências Python

Instale apenas os drivers necessários para seu banco:

```bash
# Oracle
pip install oracledb>=1.4.0

# PostgreSQL
pip install psycopg2-binary>=2.9.0

# SQL Server
pip install pyodbc>=5.0.0

# MySQL
pip install mysql-connector-python>=8.0.0
```

### Hardware Recomendado

- **GPU**: NVIDIA com 24GB+ VRAM para modelos 120B (ou use quantização)
- **CPU**: 16+ cores para processamento paralelo
- **RAM**: 32GB+ recomendado

> 📖 Para detalhes completos de dependências, veja [Project Overview - Environment & Dependencies](.cursor/documentation/project-overview.md#environment--dependencies)

## ⚙️ Configuração

### Variáveis de Ambiente

CodeGraphAI usa variáveis de ambiente para configuração. Copie `example.env` para `.env` ou `environment.env`:

```bash
cp example.env .env
# Edite .env com suas credenciais
```

**Ordem de prioridade:**

1. `.env` (se existir)
2. `environment.env` (se `.env` não existir)
3. Valores padrão

> ⚠️ **IMPORTANTE**: Nunca commite arquivos `.env` ou `environment.env` com credenciais reais!

### Configuração de LLM

CodeGraphAI suporta múltiplos providers de LLM:

- **Local (HuggingFace)**: Modelos locais via transformers
- **OpenAI**: gpt-5.1, gpt-5-mini, gpt-5-nano
- **Anthropic**: Claude Sonnet 4.5
- **GenFactory**: Llama 70B, Codestral, GPT-OSS-120B

Configure no `.env`:

```bash
CODEGRAPHAI_LLM_MODE=api  # ou 'local'
CODEGRAPHAI_LLM_PROVIDER=openai  # ou 'anthropic', 'genfactory_llama70b', etc.

# OpenAI
CODEGRAPHAI_OPENAI_API_KEY=sk-...
CODEGRAPHAI_OPENAI_MODEL=gpt-5.1

# Anthropic
CODEGRAPHAI_ANTHROPIC_API_KEY=sk-ant-...
CODEGRAPHAI_ANTHROPIC_MODEL=claude-sonnet-4-5-20250929
```

> 📖 Para configuração completa de LLMs, veja [Project Overview - Modelos LLM](.cursor/documentation/project-overview.md#modelos-llm-suportados)

### Configuração de Embeddings (Busca Semântica)

Para habilitar busca semântica com Vector Knowledge Graph:

```bash
CODEGRAPHAI_EMBEDDING_BACKEND=sentence-transformers
CODEGRAPHAI_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CODEGRAPHAI_VECTOR_STORE_PATH=./cache/vector_store
```

> 📖 Para detalhes sobre Vector Knowledge Graph, veja [Architecture - Vector Knowledge Graph](.cursor/documentation/architecture.md#8-vector-knowledge-graph-e-busca-semântica)

## 💻 Comandos CLI

### `analyze` - Análise de Banco de Dados

Analisa procedures e/ou tabelas do banco de dados.

```bash
python main.py analyze [OPÇÕES]
```

**Argumentos principais:**

- `--analysis-type [tables|procedures|both]`: Tipo de análise (padrão: `both`)
- `--db-type [oracle|postgresql|mssql|mysql]`: Tipo de banco
- `--user USER`: Usuário do banco
- `--password PASSWORD`: Senha do banco
- `--host HOST`: Host do banco
- `--port PORT`: Porta do banco
- `--database DATABASE`: Nome do banco
- `--dsn DSN`: DSN completo (Oracle)
- `--schema SCHEMA`: Schema específico
- `--limit N`: Limite de entidades
- `--export-json`: Exportar JSON
- `--export-png`: Exportar grafo PNG
- `--export-mermaid`: Exportar diagramas Mermaid
- `--output-dir PATH`: Diretório de saída
- `--dry-run`: Modo dry-run (valida sem executar)

**Exemplos:**

```bash
# PostgreSQL - Análise completa
python main.py analyze --analysis-type=both \
    --db-type postgresql \
    --user postgres --password senha \
    --host localhost --port 5432 \
    --database meu_banco --schema public \
    --export-json --export-png --export-mermaid

# Oracle - Apenas procedures
python main.py analyze --analysis-type=procedures \
    --db-type oracle \
    --user usuario --password senha \
    --dsn localhost:1521/ORCL --schema MEU_SCHEMA

# Com otimização (batch processing)
python main.py analyze --analysis-type=tables \
    --db-type postgresql \
    --user postgres --password senha \
    --host localhost --port 5432 \
    --database meu_banco \
    --batch-size 5 --parallel-workers 2
```

> 📖 Para referência completa de argumentos e exemplos, veja [Integration Flows - CLI Usage Examples](.cursor/documentation/integration-flows.md#cli-usage-examples)

### `analyze-files` - Análise de Arquivos Locais

Analisa procedures a partir de arquivos `.prc` locais.

```bash
python main.py analyze-files --directory ./procedures [OPÇÕES]
```

**Argumentos:**

- `--directory, -d PATH`: Diretório com arquivos `.prc` (obrigatório)
- `--extension, -e EXT`: Extensão dos arquivos (padrão: `prc`)
- `--output-dir, -o PATH`: Diretório de saída
- `--export-json`: Exportar JSON
- `--export-png`: Exportar grafo PNG
- `--export-mermaid`: Exportar diagramas Mermaid
- `--dry-run`: Modo dry-run

**Exemplo:**

```bash
python main.py analyze-files --directory ./procedures \
    --export-json --export-png --export-mermaid
```

### `query` - Query Inteligente com Agent

Faz queries inteligentes usando Agent com busca semântica. Permite perguntar em linguagem natural sobre procedures, tabelas e campos.

```bash
python main.py query "PERGUNTA" [OPÇÕES]
```

**Pré-requisito:** Execute análise primeiro para popular o knowledge graph:

```bash
# 1. Execute análise
python main.py analyze --analysis-type=procedures \
    --db-type postgresql \
    --user postgres --password senha \
    --host localhost --port 5432 \
    --database meu_banco

# 2. Faça queries
python main.py query "O que faz a procedure PROCESSAR_PEDIDO?"
```

**Argumentos:**

- `PERGUNTA`: Pergunta em linguagem natural (obrigatório)
- `--verbose`: Mostrar execução detalhada
- `--max-iterations N`: Número máximo de iterações (padrão: 15)
- `--cache-path PATH`: Caminho do cache (padrão: `./cache/knowledge_graph.json`)

**Exemplos de Perguntas:**

```bash
# Consultas básicas
python main.py query "O que faz a procedure PROCESSAR_PEDIDO?"
python main.py query "Quem chama a procedure VALIDAR_USUARIO?"
python main.py query "Mostre a estrutura da tabela PEDIDOS"

# Busca semântica (usa Vector Knowledge Graph)
python main.py query "Quais tabelas estão relacionadas a pagamentos e transações financeiras?"
python main.py query "Encontre procedures que calculam valores ou fazem cálculos matemáticos"

# Análise de impacto
python main.py query "Se eu modificar CALCULAR_SALDO, quais procedures serão impactadas?"

# Rastreamento de campo
python main.py query "De onde vem o campo email usado em CRIAR_USUARIO?"
```

> 📖 Para guia completo do Agent e Tools, veja [README_AGENT.md](README_AGENT.md) e [Integration Flows - Query Flow](.cursor/documentation/integration-flows.md#query-flow-agent)

### `test-connection` - Teste de Conexão

Testa conectividade com banco de dados.

```bash
python main.py test-connection --db-type postgresql \
    --user postgres --password senha \
    --host localhost --port 5432 --database meu_banco
```

## 📊 Formatos de Saída

### JSON

Metadados completos em formato JSON:

- `procedure_analysis.json`: Análise de procedures
- `table_analysis.json`: Análise de tabelas

### Visualizações

- **PNG**: Grafos de dependências e relacionamentos
- **Mermaid**: Diagramas interativos em markdown
  - Diagrama de dependências
  - Hierarquia por níveis
  - Diagrama ER (tabelas)

> 📖 Para detalhes sobre visualizações, veja [Integration Flows - Export Flow](.cursor/documentation/integration-flows.md#export-flow)

## 🔧 Configuração Avançada

### Dry-Run Mode

Valida configurações sem executar análises:

```bash
python main.py analyze --dry-run --analysis-type=both \
    --user postgres --password senha \
    --host localhost --database meu_banco
```

### Batch Processing e Paralelismo

Otimize análise de tabelas com batch processing:

```bash
python main.py analyze --analysis-type=tables \
    --batch-size 5 --parallel-workers 2 \
    --db-type postgresql ...
```

- `--batch-size N`: Tamanho do batch (padrão: 5, `1` desabilita)
- `--parallel-workers N`: Workers paralelos (padrão: 2, `1` desabilita)

### Sistema de Logs

Logs são criados automaticamente em `logs/`:

```bash
# Configurar via variáveis de ambiente
CODEGRAPHAI_LOG_DIR=./logs
CODEGRAPHAI_AUTO_LOG_ENABLED=true
CODEGRAPHAI_LOG_LEVEL=INFO

# Desabilitar auto-logging
python main.py --no-auto-log analyze ...

# Especificar arquivo de log
python main.py analyze --log-file logs/custom.log ...
```

> 📖 Para configuração completa, veja [Project Overview - Configuração Avançada](.cursor/documentation/project-overview.md#configuração-avançada)

## 🆕 Intelligence Tools

CodeGraphAI inclui ferramentas avançadas de análise:

- **Knowledge Graph Persistente**: Cache estruturado para queries rápidas
- **Vector Knowledge Graph**: Busca semântica com embeddings
- **Static Code Analyzer**: Análise sem LLM usando regex
- **Code Crawler**: Rastreamento recursivo de dependências
- **LangChain Agent**: Agent inteligente com tools especializadas
- **Query Natural**: Perguntas em linguagem natural

> 📖 Para guia completo das Intelligence Tools, veja [README_AGENT.md](README_AGENT.md)

## 📂 Estrutura do Projeto

```text
CodeGraphAI/
├── app/                    # Módulos principais
│   ├── core/              # Modelos e exceções
│   ├── io/                # Adaptadores de banco de dados
│   ├── llm/               # Integração com LLMs
│   ├── config/            # Configuração
│   ├── graph/             # Knowledge Graph e Vector Search
│   ├── analysis/          # Static Analysis & Crawling
│   ├── tools/             # LangChain Tools
│   └── agents/            # LangChain Agent
├── cache/                 # Knowledge Graph e Vector Store cache
├── examples/              # Exemplos de uso
├── output/                # Resultados gerados
└── tests/                 # Testes
```

> 📖 Para estrutura completa, veja [Architecture - Module Structure](.cursor/documentation/architecture.md#module-structure)

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor:

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📚 Documentação Completa

- **[Project Overview](.cursor/documentation/project-overview.md)** - Visão geral e funcionalidades
- **[Architecture](.cursor/documentation/architecture.md)** - Arquitetura e padrões de design
- **[API Catalog](.cursor/documentation/api-catalog.md)** - Referência de APIs
- **[Integration Flows](.cursor/documentation/integration-flows.md)** - Fluxos e exemplos
- **[Database Adapters](.cursor/documentation/database-adapters.md)** - Adaptadores de banco
- **[README_AGENT.md](README_AGENT.md)** - Guia das Intelligence Tools
- **[Security Overview](.cursor/documentation/security-overview.md)** - Segurança
- **[Performance Analysis](.cursor/documentation/performance-analysis.md)** - Performance

## 🗺️ Roadmap

Para visualizar o roadmap completo de melhorias planejadas, incluindo prioridades e estimativas, consulte a [documentação oficial](.cursor/documentation/improvement-roadmap.md).

---

**CodeGraphAI** - Análise inteligente de código de banco de dados

---
Generated on: 2025-11-24 19:39:51
