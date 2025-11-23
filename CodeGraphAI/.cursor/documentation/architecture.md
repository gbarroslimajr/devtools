# CodeGraphAI - Architecture Details

## Table of Contents

- [Architectural Patterns](#architectural-patterns)
- [Component Diagram](#component-diagram)
- [Data Flow](#data-flow)
- [Design Decisions](#design-decisions)
- [Module Structure](#module-structure)
- [Related Documentation](#related-documentation)

---

## Architectural Patterns

### 1. Strategy Pattern

**Aplicação:** Adaptadores de banco de dados

Cada banco de dados tem sua própria implementação de `ProcedureLoaderBase`, permitindo que o sistema troque dinamicamente a estratégia de carregamento sem modificar o código cliente.

**Benefícios:**
- Extensibilidade: Fácil adicionar novos bancos
- Manutenibilidade: Mudanças em um adaptador não afetam outros
- Testabilidade: Cada adaptador pode ser testado isoladamente

### 2. Factory Pattern

**Aplicação:** Criação de loaders (`app/io/factory.py`)

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

### 3. Chain of Responsibility (implícito)

**Aplicação:** Pipeline de análise

O fluxo de análise passa por múltiplas etapas:
1. Carregamento de procedures
2. Análise de lógica de negócio (LLM)
3. Extração de dependências
4. Cálculo de complexidade
5. Construção de grafo
6. Exportação

Cada etapa pode ser executada independentemente.

### 4. Adapter Pattern

**Aplicação:** Adaptação de diferentes bancos para interface comum

Cada loader adapta a API específica do banco para a interface `ProcedureLoaderBase`.

---

## Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              main.py (Click Commands)                 │   │
│  │  - analyze-files                                     │   │
│  │  - analyze-db                                        │   │
│  │  - export                                            │   │
│  └───────────────────┬──────────────────────────────────┘   │
└──────────────────────┼──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   Analysis Layer                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │          ProcedureAnalyzer                           │   │
│  │  - analyze_from_files()                              │   │
│  │  - analyze_from_database()                           │   │
│  │  - export_results()                                  │   │
│  │  - visualize_dependencies()                          │   │
│  └───────┬───────────────────────────┬──────────────────┘   │
│          │                           │                        │
│  ┌───────▼────────┐        ┌─────────▼──────────┐           │
│  │  LLMAnalyzer   │        │  ProcedureLoader    │           │
│  │  - analyze()   │        │  (Factory)          │           │
│  └────────────────┘        └──────────┬───────────┘           │
└──────────────────────────────────────┼────────────────────────┘
                                       │
┌──────────────────────────────────────▼────────────────────────┐
│                      I/O Layer                                  │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │         ProcedureLoaderBase (ABC)                         │ │
│  └───────┬──────────┬──────────┬──────────┬──────────────┘ │
│          │          │          │          │                  │
│  ┌───────▼──┐ ┌─────▼────┐ ┌───▼──────┐ ┌──▼──────┐         │
│  │  Oracle  │ │PostgreSQL│ │  MSSQL   │ │  MySQL  │         │
│  │  Loader  │ │  Loader  │ │  Loader  │ │  Loader │         │
│  └──────────┘ └──────────┘ └──────────┘ └─────────┘         │
└──────────────────────────────────────────────────────────────┘
                       │
┌───────────────────────▼───────────────────────────────────────┐
│                    Core Layer                                  │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Models:                                                 │ │
│  │  - ProcedureInfo                                         │ │
│  │  - DatabaseConfig                                        │ │
│  │  - DatabaseType (Enum)                                   │ │
│  │  - Exceptions                                            │ │
│  └──────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
                       │
┌───────────────────────▼───────────────────────────────────────┐
│                 Configuration Layer                            │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Config:                                                 │ │
│  │  - Environment variables                                 │ │
│  │  - .env / environment.env                                │ │
│  │  - Database-specific settings                            │ │
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
   │   ├─> Constrói grafo (NetworkX)
   │   │
   │   └─> Calcula níveis hierárquicos
   │
   └─> Exporta resultados (JSON, PNG, Mermaid)
```

### Fluxo de Análise de Banco de Dados

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

### 3. Prompts Genéricos

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

### 4. Configuração Flexível

**Decisão:** Suportar múltiplos métodos de configuração

**Razão:** Flexibilidade para diferentes ambientes

**Métodos:**
1. Variáveis de ambiente (`.env` / `environment.env`)
2. Parâmetros CLI
3. Classe `Config` com defaults

### 5. Exceções Customizadas

**Decisão:** Hierarquia de exceções específicas

**Razão:** Melhor tratamento de erros e debugging

**Hierarquia:**
```
CodeGraphAIError (base)
├── ProcedureLoadError
├── LLMAnalysisError
├── DependencyAnalysisError
├── ExportError
└── ValidationError
```

---

## Module Structure

### `app/core/`

**Responsabilidade:** Modelos de dados e exceções

**Arquivos:**
- `models.py`: `ProcedureInfo`, `DatabaseConfig`, `DatabaseType`, exceções

### `app/io/`

**Responsabilidade:** Carregamento de procedures

**Arquivos:**
- `base.py`: Interface abstrata `ProcedureLoaderBase`
- `factory.py`: Factory pattern
- `oracle_loader.py`: Adaptador Oracle
- `postgres_loader.py`: Adaptador PostgreSQL
- `mssql_loader.py`: Adaptador SQL Server
- `mysql_loader.py`: Adaptador MySQL
- `file_loader.py`: Carregamento de arquivos

### `app/config/`

**Responsabilidade:** Configuração

**Arquivos:**
- `config.py`: Classe `Config` com carregamento de `.env`

### `analyzer.py`

**Responsabilidade:** Análise de procedures

**Classes:**
- `LLMAnalyzer`: Análise com LLM
- `ProcedureAnalyzer`: Orquestração
- `ProcedureLoader`: Wrapper para backward compatibility

### `main.py`

**Responsabilidade:** Interface CLI

**Comandos:**
- `analyze-files`: Análise de arquivos
- `analyze-db`: Análise de banco
- `export`: Exportação (parcial)

---

## Related Documentation

- [Project Overview](project-overview.md) - Visão geral do projeto
- [API Catalog](api-catalog.md) - Referência de APIs
- [Integration Flows](integration-flows.md) - Fluxos detalhados
- [Database Adapters](database-adapters.md) - Detalhes dos adaptadores

---

Generated on: 2024-11-23 16:45:00

