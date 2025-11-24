# CodeGraphAI - Architecture Details

## Table of Contents

- [Architectural Patterns](#architectural-patterns)
- [Component Diagram](#component-diagram)
- [Data Flow](#data-flow)
- [Design Decisions](#design-decisions)
- [Module Structure](#module-structure)
- [Intelligence Layer](#intelligence-layer)
- [Related Documentation](#related-documentation)

---

## Architectural Patterns

### 1. Strategy Pattern

**Aplicação:** Adaptadores de banco de dados

Cada banco de dados tem sua própria implementação de `ProcedureLoaderBase` e `TableLoaderBase`, permitindo que o sistema troque dinamicamente a estratégia de carregamento sem modificar o código cliente.

**Benefícios:**
- Extensibilidade: Fácil adicionar novos bancos
- Manutenibilidade: Mudanças em um adaptador não afetam outros
- Testabilidade: Cada adaptador pode ser testado isoladamente

### 2. Factory Pattern

**Aplicação:** Criação de loaders (`app/io/factory.py`, `app/io/table_factory.py`)

O factory cria instâncias de loaders baseado no tipo de banco, abstraindo a lógica de criação.

**Implementação:**
```python
def create_loader(db_type: DatabaseType) -> ProcedureLoaderBase:
    loader_class = _LOADER_REGISTRY[db_type]
    return loader_class()
```

**Benefícios:**
- Desacoplamento: Cliente não conhece classes concretas
- Centralização: Lógica de criação em um único lugar
- Extensibilidade: Registro dinâmico de novos loaders

### 3. Singleton Pattern

**Aplicação:** Configuração (`app/config/config.py`)

A classe `Config` implementa Singleton thread-safe usando double-check locking pattern.

**Implementação:**
```python
class Config:
    _instance: Optional['Config'] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> 'Config':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
```

**Benefícios:**
- Thread-safety: Garante uma única instância mesmo em ambientes concorrentes
- Acesso global: Configuração disponível em qualquer lugar
- Lazy initialization: Carrega apenas quando necessário

### 4. Chain of Responsibility (implícito)

**Aplicação:** Pipeline de análise

O fluxo de análise passa por múltiplas etapas:
1. Carregamento de procedures/tabelas
2. Análise de lógica de negócio (LLM)
3. Extração de dependências
4. Cálculo de complexidade
5. Construção de grafo
6. População do Knowledge Graph
7. Exportação

Cada etapa pode ser executada independentemente.

### 5. Adapter Pattern

**Aplicação:** Adaptação de diferentes bancos para interface comum

Cada loader adapta a API específica do banco para a interface `ProcedureLoaderBase` ou `TableLoaderBase`.

### 6. Agent Pattern (LangChain)

**Aplicação:** CodeAnalysisAgent para queries inteligentes

O agent usa tools especializadas para responder perguntas em linguagem natural sobre o código.

**Benefícios:**
- Extensibilidade: Fácil adicionar novas tools
- Flexibilidade: Agent escolhe tools automaticamente
- Modularidade: Cada tool tem responsabilidade única

---

## Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              main.py (Click Commands)                 │   │
│  │  - analyze (procedures/tables/both)                   │   │
│  │  - analyze-files                                      │   │
│  │  - query (Agent)                                      │   │
│  │  - test-connection                                    │   │
│  └───────────────────┬──────────────────────────────────┘   │
└──────────────────────┼──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   Analysis Layer                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │          ProcedureAnalyzer                           │   │
│  │  - analyze_from_files()                             │   │
│  │  - analyze_from_database()                          │   │
│  │  - export_results()                                 │   │
│  │  - visualize_dependencies()                         │   │
│  └───────────────────┬──────────────────────────────────┘   │
│  ┌───────────────────▼──────────────────────────────────┐   │
│  │          TableAnalyzer                                │   │
│  │  - analyze_from_database()                           │   │
│  │  - batch processing                                   │   │
│  │  - parallel workers                                  │   │
│  └───────────────────┬──────────────────────────────────┘   │
│                      │                                        │
│  ┌───────────────────▼──────────────────────────────────┐   │
│  │          LLMAnalyzer                                  │   │
│  │  - analyze_business_logic()                          │   │
│  │  - analyze_dependencies()                            │   │
│  │  - analyze_complexity()                              │   │
│  │  - analyze_table_purpose()                           │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Intelligence Layer                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │       CodeAnalysisAgent (LangChain)                  │   │
│  │  - analyze() (natural language queries)              │   │
│  └───────────────────┬──────────────────────────────────┘   │
│  ┌───────────────────▼──────────────────────────────────┐   │
│  │       CodeKnowledgeGraph (NetworkX)                   │   │
│  │  - add_procedure()                                    │   │
│  │  - add_table()                                        │   │
│  │  - get_procedure_context()                            │   │
│  │  - save_to_cache()                                    │   │
│  └───────────────────┬──────────────────────────────────┘   │
│  ┌───────────────────▼──────────────────────────────────┐   │
│  │       StaticCodeAnalyzer                              │   │
│  │  - analyze_code() (regex-based)                      │   │
│  └───────────────────┬──────────────────────────────────┘   │
│  ┌───────────────────▼──────────────────────────────────┐   │
│  │       CodeCrawler                                    │   │
│  │  - crawl_dependencies()                              │   │
│  │  - trace_field_flow()                                 │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                      I/O Layer                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │         ProcedureLoaderBase (ABC)                         │ │
│  │         TableLoaderBase (ABC)                             │ │
│  └───────┬──────────┬──────────┬──────────┬──────────────┘ │
│          │          │          │          │                  │
│  ┌───────▼──┐ ┌─────▼────┐ ┌───▼──────┐ ┌──▼──────┐         │
│  │  Oracle  │ │PostgreSQL│ │  MSSQL   │ │  MySQL  │         │
│  │  Loader  │ │  Loader  │ │  Loader  │ │  Loader │         │
│  └──────────┘ └──────────┘ └──────────┘ └─────────┘         │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │         FileLoader                                        │ │
│  │         TableCache                                        │ │
│  └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
                       │
┌───────────────────────▼───────────────────────────────────────┐
│                    Core Layer                                  │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Models:                                                 │ │
│  │  - ProcedureInfo                                         │ │
│  │  - TableInfo                                             │ │
│  │  - DatabaseConfig                                        │ │
│  │  - DatabaseType (Enum)                                   │ │
│  │  - LLMProvider (Enum)                                    │ │
│  │  - Exceptions                                            │ │
│  │  - DryRunValidator                                       │ │
│  └──────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
                       │
┌───────────────────────▼───────────────────────────────────────┐
│                 Configuration Layer                            │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Config (Singleton Thread-Safe):                        │ │
│  │  - Environment variables                                 │ │
│  │  - .env / environment.env                                │ │
│  │  - Database-specific settings                            │ │
│  │  - LLM provider settings                                 │ │
│  └──────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Fluxo de Análise de Arquivos

```
1. CLI (main.py)
   │
   ├─> ProcedureAnalyzer.analyze_from_files()
   │   │
   │   ├─> ProcedureLoader.from_files()
   │   │   └─> FileLoader.from_files()
   │   │       └─> Retorna Dict[str, str] (nome -> código)
   │   │
   │   ├─> Para cada procedure:
   │   │   │
   │   │   ├─> LLMAnalyzer.analyze_business_logic()
   │   │   │   └─> LLM Chain → business_logic
   │   │   │
   │   │   ├─> LLMAnalyzer.analyze_dependencies()
   │   │   │   └─> Regex + LLM → dependencies
   │   │   │
   │   │   ├─> LLMAnalyzer.analyze_complexity()
   │   │   │   └─> LLM + Heurística → complexity_score
   │   │   │
   │   │   └─> Cria ProcedureInfo
   │   │
   │   ├─> StaticCodeAnalyzer.analyze_code()
   │   │   └─> Extrai fields usados (regex)
   │   │
   │   ├─> KnowledgeGraph.add_procedure()
   │   │   └─> Adiciona ao grafo
   │   │
   │   ├─> Constrói grafo (NetworkX)
   │   │
   │   └─> Calcula níveis hierárquicos
   │
   └─> Exporta resultados (JSON, PNG, Mermaid)
```

### Fluxo de Análise de Banco de Dados (Procedures)

```
1. CLI (main.py)
   │
   ├─> ProcedureAnalyzer.analyze_from_database()
   │   │
   │   ├─> Determina DatabaseType
   │   │
   │   ├─> Cria DatabaseConfig
   │   │
   │   ├─> Factory.create_loader(db_type)
   │   │   └─> Retorna loader específico
   │   │
   │   ├─> loader.load_procedures(config)
   │   │   └─> Conecta ao banco e extrai procedures
   │   │       └─> Retorna Dict[str, str]
   │   │
   │   └─> Continua como análise de arquivos...
   │
   └─> Exporta resultados
```

### Fluxo de Análise de Banco de Dados (Tabelas)

```
1. CLI (main.py)
   │
   ├─> TableAnalyzer.analyze_from_database()
   │   │
   │   ├─> Determina DatabaseType
   │   │
   │   ├─> Cria DatabaseConfig
   │   │
   │   ├─> TableFactory.create_loader(db_type)
   │   │   └─> Retorna table loader específico
   │   │
   │   ├─> loader.load_tables(config)
   │   │   └─> Conecta ao banco e extrai tabelas
   │   │       └─> Retorna List[TableInfo]
   │   │
   │   ├─> Batch Processing (padrão: 5 tabelas)
   │   │   │
   │   │   ├─> Para cada batch:
   │   │   │   │
   │   │   │   ├─> ThreadPoolExecutor (padrão: 2 workers)
   │   │   │   │   │
   │   │   │   │   ├─> Para cada tabela (paralelo):
   │   │   │   │   │   │
   │   │   │   │   │   ├─> Extrai DDL, colunas, índices, FKs
   │   │   │   │   │   │
   │   │   │   │   │   ├─> LLMAnalyzer.analyze_table_purpose()
   │   │   │   │   │   │   └─> LLM Chain → business_purpose
   │   │   │   │   │   │
   │   │   │   │   │   ├─> Calcula complexity_score (heurística)
   │   │   │   │   │   │
   │   │   │   │   │   └─> Cria TableInfo
   │   │   │   │   │
   │   │   │   │   └─> Aguarda conclusão do batch
   │   │   │   │
   │   │   │   └─> Próximo batch
   │   │   │
   │   │   └─> Cache de análise
   │   │
   │   ├─> KnowledgeGraph.add_table()
   │   │   └─> Adiciona ao grafo
   │   │
   │   ├─> Constrói grafo de relacionamentos (NetworkX)
   │   │
   │   └─> Calcula hierarquia por FKs
   │
   └─> Exporta resultados (JSON, PNG, Mermaid)
```

### Fluxo de Query com Agent

```
1. CLI (main.py)
   │
   ├─> query "pergunta em linguagem natural"
   │   │
   │   ├─> Carrega KnowledgeGraph do cache
   │   │   └─> cache/knowledge_graph.json
   │   │
   │   ├─> Inicializa CodeAnalysisAgent
   │   │   │
   │   │   ├─> Cria LangChain agent com tools:
   │   │   │   - query_procedure
   │   │   │   - query_table
   │   │   │   - analyze_field
   │   │   │   - trace_field_flow
   │   │   │   - crawl_procedure
   │   │   │   - execute_query (opcional)
   │   │   │
   │   │   └─> Configura system prompt
   │   │
   │   ├─> Agent.analyze(pergunta)
   │   │   │
   │   │   ├─> Agent escolhe tool apropriada
   │   │   │   │
   │   │   │   ├─> Tool executa query no KnowledgeGraph
   │   │   │   │   └─> Retorna informações
   │   │   │   │
   │   │   │   └─> Agent processa resultado
   │   │   │
   │   │   ├─> Se necessário, escolhe outra tool
   │   │   │   └─> Múltiplas iterações (max: 15)
   │   │   │
   │   │   └─> Agent sintetiza resposta final
   │   │
   │   └─> Retorna resposta ao usuário
```

---

## Design Decisions

### 1. Backward Compatibility

**Decisão:** Manter `ProcedureLoader` em `analyzer.py` como wrapper

**Razão:** Código existente não precisa ser modificado

**Implementação:**
- `ProcedureLoader.from_database()` usa factory internamente
- `ProcedureLoader.from_files()` delega para `FileLoader`
- Re-exporta classes e exceções via `__all__`

### 2. Factory com Registro Dinâmico

**Decisão:** Loaders se registram automaticamente ao importar

**Razão:** Facilita adicionar novos adaptadores sem modificar factory

**Implementação:**
- Decorator `@register_loader` nos loaders
- Registry `_LOADER_REGISTRY` em `factory.py`
- Importação lazy quando necessário

### 3. Singleton Thread-Safe para Config

**Decisão:** Config usa Singleton com double-check locking

**Razão:** Garante uma única instância mesmo em ambientes concorrentes

**Implementação:**
- Thread-safe usando `threading.Lock`
- Double-check locking pattern
- Lazy initialization

### 4. Prompts Genéricos

**Decisão:** Remover referências específicas a "Oracle" dos prompts

**Razão:** Funciona com qualquer banco de dados

**Antes:**
```
"Analise a seguinte procedure Oracle..."
```

**Depois:**
```
"Analise a seguinte stored procedure..."
```

### 5. Configuração Flexível

**Decisão:** Suportar múltiplos métodos de configuração

**Razão:** Flexibilidade para diferentes ambientes

**Métodos:**
1. Variáveis de ambiente (`.env` / `environment.env`)
2. Parâmetros CLI
3. Classe `Config` com defaults

### 6. Exceções Customizadas

**Decisão:** Hierarquia de exceções específicas

**Razão:** Melhor tratamento de erros e debugging

**Hierarquia:**
```
CodeGraphAIError (base)
├── ProcedureLoadError
├── TableLoadError
├── LLMAnalysisError
├── DependencyAnalysisError
├── ExportError
└── ValidationError
```

### 7. Knowledge Graph Persistente

**Decisão:** Usar NetworkX MultiDiGraph com persistência em JSON

**Razão:**
- Queries rápidas sem re-análise
- Cache de resultados
- Suporte a queries complexas

**Implementação:**
- NetworkX MultiDiGraph para estrutura
- JSON para persistência
- Cache em `cache/knowledge_graph.json`

### 8. Batch Processing e Paralelismo

**Decisão:** Implementar batch processing e paralelismo para análise de tabelas

**Razão:**
- Reduz chamadas LLM (batch)
- Acelera análise (paralelismo)
- Melhor uso de recursos

**Implementação:**
- Batch processing: 5 tabelas por batch (configurável)
- ThreadPoolExecutor: 2 workers (configurável)
- Cache para evitar re-análise

### 9. Agent com Tools Especializadas

**Decisão:** Usar LangChain Agent com tools especializadas

**Razão:**
- Flexibilidade: Agent escolhe tools automaticamente
- Extensibilidade: Fácil adicionar novas tools
- Modularidade: Cada tool tem responsabilidade única

**Implementação:**
- LangChain 1.0+ `create_agent`
- 5-6 tools especializadas
- System prompt customizado

---

## Module Structure

### `app/core/`

**Responsabilidade:** Modelos de dados e exceções

**Arquivos:**
- `models.py`: `ProcedureInfo`, `TableInfo`, `DatabaseConfig`, `DatabaseType`, `LLMProvider`, exceções
- `dry_mode.py`: `DryRunValidator` para validação sem execução

### `app/io/`

**Responsabilidade:** Carregamento de procedures e tabelas

**Arquivos:**
- `base.py`: Interface abstrata `ProcedureLoaderBase`
- `table_base.py`: Interface abstrata `TableLoaderBase`
- `factory.py`: Factory pattern para procedures
- `table_factory.py`: Factory pattern para tabelas
- `oracle_loader.py`, `oracle_table_loader.py`: Adaptador Oracle
- `postgres_loader.py`, `postgres_table_loader.py`: Adaptador PostgreSQL
- `mssql_loader.py`, `mssql_table_loader.py`: Adaptador SQL Server
- `mysql_loader.py`, `mysql_table_loader.py`: Adaptador MySQL
- `file_loader.py`: Carregamento de arquivos
- `table_cache.py`: Cache de análise de tabelas

### `app/config/`

**Responsabilidade:** Configuração

**Arquivos:**
- `config.py`: Classe `Config` (Singleton thread-safe) com carregamento de `.env`

### `app/llm/`

**Responsabilidade:** Integração com LLMs

**Arquivos:**
- `langchain_wrapper.py`: Wrapper LangChain para diferentes providers
- `genfactory_client.py`: Cliente GenFactory API
- `token_tracker.py`: Tracking de uso de tokens
- `token_callback.py`: Callback para tracking
- `toon_converter.py`: Conversão para formato TOON (otimização)

### `app/graph/`

**Responsabilidade:** Knowledge Graph

**Arquivos:**
- `knowledge_graph.py`: `CodeKnowledgeGraph` usando NetworkX

### `app/analysis/`

**Responsabilidade:** Análise estática e crawling

**Arquivos:**
- `static_analyzer.py`: `StaticCodeAnalyzer` (regex-based)
- `code_crawler.py`: `CodeCrawler` (dependency crawling)
- `on_demand_analyzer.py`: `OnDemandAnalyzer` (lazy analysis)

### `app/agents/`

**Responsabilidade:** LangChain Agent

**Arquivos:**
- `code_analysis_agent.py`: `CodeAnalysisAgent` para queries inteligentes

### `app/tools/`

**Responsabilidade:** LangChain Tools

**Arquivos:**
- `graph_tools.py`: Tools de query no grafo
- `field_tools.py`: Tools de análise de campos
- `crawler_tools.py`: Tools de crawling
- `query_tools.py`: Tools de query no banco

### `analyzer.py`

**Responsabilidade:** Análise de procedures

**Classes:**
- `LLMAnalyzer`: Análise com LLM
- `ProcedureAnalyzer`: Orquestração
- `ProcedureLoader`: Wrapper para backward compatibility

### `table_analyzer.py`

**Responsabilidade:** Análise de tabelas

**Classes:**
- `TableAnalyzer`: Orquestração com batch processing e paralelismo

### `main.py`

**Responsabilidade:** Interface CLI

**Comandos:**
- `analyze`: Análise de banco (procedures e/ou tabelas)
- `analyze-files`: Análise de arquivos
- `query`: Query inteligente com Agent
- `test-connection`: Teste de conexão

---

## Intelligence Layer

### CodeKnowledgeGraph

**Responsabilidade:** Grafo persistente para cache e queries

**Tecnologias:**
- NetworkX MultiDiGraph
- JSON para persistência

**Funcionalidades:**
- Armazena procedures, tabelas e fields como nós
- Armazena relacionamentos como arestas (calls, accesses, reads, writes)
- Queries de contexto rápidas
- Estatísticas do grafo

### StaticCodeAnalyzer

**Responsabilidade:** Análise de código sem LLM

**Tecnologias:**
- Regex avançado
- Análise de AST (parcial)

**Funcionalidades:**
- Extração de fields usados
- Detecção de operações (read/write)
- Transformações aplicadas
- Contextos de uso

### CodeCrawler

**Responsabilidade:** Rastreamento recursivo de dependências

**Funcionalidades:**
- Árvore completa de dependências
- Análise de impacto
- Field tracing
- Procedures e tabelas envolvidas

### CodeAnalysisAgent

**Responsabilidade:** Agent inteligente para queries em linguagem natural

**Tecnologias:**
- LangChain 1.0+ (create_agent)
- BaseChatModel (qualquer provider)

**Tools Disponíveis:**
1. `query_procedure`: Consulta informações de procedures
2. `query_table`: Consulta estrutura de tabelas
3. `analyze_field`: Analisa campos específicos
4. `trace_field_flow`: Rastreia fluxo de campos
5. `crawl_procedure`: Crawling de dependências
6. `execute_query`: Executa queries SELECT (opcional)

**Funcionalidades:**
- Processa perguntas em linguagem natural
- Escolhe tools apropriadas automaticamente
- Múltiplas iterações para queries complexas
- Integração com Knowledge Graph

---

## Related Documentation

- [Project Overview](project-overview.md) - Visão geral do projeto
- [API Catalog](api-catalog.md) - Referência de APIs
- [Integration Flows](integration-flows.md) - Fluxos detalhados
- [Database Adapters](database-adapters.md) - Detalhes dos adaptadores
- [Performance Analysis](performance-analysis.md) - Análise de performance

---

Generated on: 2025-01-27 12:00:00
