# CodeGraphAI - Integration Flows

## Table of Contents

- [Overview](#overview)
- [File Analysis Flow](#file-analysis-flow)
- [Database Analysis Flow](#database-analysis-flow)
- [Table Analysis Flow](#table-analysis-flow)
- [Query Flow (Agent)](#query-flow-agent)
- [Export Flow](#export-flow)
- [CLI Usage Examples](#cli-usage-examples)
- [Programmatic Usage](#programmatic-usage)
- [Related Documentation](#related-documentation)

---

## Overview

Este documento descreve os fluxos de integração e uso do CodeGraphAI, incluindo diagramas de sequência e exemplos práticos.

---

## File Analysis Flow

### Diagrama de Sequência

```
User
 │
 ├─> CLI: analyze-files
 │    │
 │    ├─> ProcedureAnalyzer.analyze_from_files()
 │    │    │
 │    │    ├─> ProcedureLoader.from_files()
 │    │    │    │
 │    │    │    └─> FileLoader.from_files()
 │    │    │         │
 │    │    │         ├─> Lê arquivos .prc
 │    │    │         │
 │    │    │         └─> Retorna Dict[str, str]
 │    │    │
 │    │    ├─> Para cada procedure:
 │    │    │    │
 │    │    │    ├─> LLMAnalyzer.analyze_business_logic()
 │    │    │    │    │
 │    │    │    │    └─> LLM Chain → business_logic
 │    │    │    │
 │    │    │    ├─> LLMAnalyzer.analyze_dependencies()
 │    │    │    │    │
 │    │    │    │    ├─> Regex extraction
 │    │    │    │    │
 │    │    │    │    └─> LLM validation → dependencies
 │    │    │    │
 │    │    │    ├─> LLMAnalyzer.analyze_complexity()
 │    │    │    │    │
 │    │    │    │    ├─> LLM analysis
 │    │    │    │    │
 │    │    │    │    └─> Heuristic fallback → complexity_score
 │    │    │    │
 │    │    │    └─> Cria ProcedureInfo
 │    │    │
 │    │    ├─> Constrói grafo (NetworkX)
 │    │    │
 │    │    └─> Calcula níveis hierárquicos
 │    │
 │    └─> Exporta resultados
 │
 └─> Retorna estatísticas
```

### Exemplo CLI

```bash
# Análise básica
python main.py analyze-files \
    --directory ./procedures \
    --extension prc \
    --output-dir ./output

# Com exportação Mermaid
python main.py analyze-files \
    --directory ./procedures \
    --extension prc \
    --export-mermaid \
    --output-dir ./output

# Com modelo customizado
python main.py analyze-files \
    --directory ./procedures \
    --model llama-2-7b \
    --device cpu \
    --output-dir ./output
```

### Exemplo Programático

```python
from analyzer import LLMAnalyzer, ProcedureAnalyzer

# Inicializa LLM
llm = LLMAnalyzer(
    model_name="gpt-oss-120b",
    device="cuda"
)

# Cria analisador
analyzer = ProcedureAnalyzer(llm)

# Analisa arquivos
analyzer.analyze_from_files("./procedures", "prc")

# Exporta resultados
analyzer.export_results("analysis.json")
analyzer.export_mermaid_diagram("diagram.md")
analyzer.export_mermaid_hierarchy("hierarchy.md")
```

---

## Database Analysis Flow

### Diagrama de Sequência

```
User
 │
 ├─> CLI: analyze-db
 │    │
 │    ├─> Valida parâmetros
 │    │
 │    ├─> ProcedureAnalyzer.analyze_from_database()
 │    │    │
 │    │    ├─> Determina DatabaseType
 │    │    │
 │    │    ├─> Cria DatabaseConfig
 │    │    │
 │    │    ├─> Factory.create_loader(db_type)
 │    │    │    │
 │    │    │    ├─> Verifica registry
 │    │    │    │
 │    │    │    ├─> Importa loader se necessário
 │    │    │    │
 │    │    │    └─> Retorna loader específico
 │    │    │
 │    │    ├─> loader.load_procedures(config)
 │    │    │    │
 │    │    │    ├─> Conecta ao banco
 │    │    │    │
 │    │    │    ├─> Executa query para listar procedures
 │    │    │    │
 │    │    │    ├─> Para cada procedure:
 │    │    │    │    │
 │    │    │    │    └─> Executa query para obter código
 │    │    │    │
 │    │    │    └─> Retorna Dict[str, str]
 │    │    │
 │    │    └─> Continua como análise de arquivos...
 │    │
 │    └─> Exporta resultados
 │
 └─> Retorna estatísticas
```

### Exemplo CLI - Oracle

```bash
python main.py analyze-db \
    --db-type oracle \
    --user usuario \
    --password senha \
    --dsn localhost:1521/ORCL \
    --schema MEU_SCHEMA \
    --limit 100 \
    --output-dir ./output
```

### Exemplo CLI - PostgreSQL

```bash
python main.py analyze-db \
    --db-type postgresql \
    --user usuario \
    --password senha \
    --host localhost \
    --port 5432 \
    --database meu_banco \
    --schema public \
    --output-dir ./output
```

### Exemplo CLI - SQL Server

```bash
python main.py analyze-db \
    --db-type mssql \
    --user usuario \
    --password senha \
    --host localhost \
    --port 1433 \
    --database meu_banco \
    --schema dbo \
    --output-dir ./output
```

### Exemplo CLI - MySQL

```bash
python main.py analyze-db \
    --db-type mysql \
    --user usuario \
    --password senha \
    --host localhost \
    --port 3306 \
    --database meu_banco \
    --output-dir ./output
```

### Exemplo Programático

```python
from analyzer import LLMAnalyzer, ProcedureAnalyzer
from app.core.models import DatabaseType, DatabaseConfig

# Inicializa LLM
llm = LLMAnalyzer()

# Cria analisador
analyzer = ProcedureAnalyzer(llm)

# Analisa do banco
analyzer.analyze_from_database(
    user="usuario",
    password="senha",
    dsn="localhost:1521/ORCL",
    schema="MEU_SCHEMA",
    db_type="oracle"
)

# Exporta resultados
analyzer.export_results("analysis.json")
```

---

## Table Analysis Flow

### Diagrama de Sequência

```
User
 │
 ├─> CLI: analyze --analysis-type=tables
 │    │
 │    ├─> TableAnalyzer.analyze_from_database()
 │    │    │
 │    │    ├─> TableFactory.create_loader(db_type)
 │    │    │    └─> Retorna table loader específico
 │    │    │
 │    │    ├─> loader.load_tables(config)
 │    │    │    └─> Conecta ao banco e extrai tabelas
 │    │    │        └─> Retorna List[TableInfo]
 │    │    │
 │    │    ├─> Batch Processing (padrão: 5 tabelas)
 │    │    │    │
 │    │    │    ├─> Para cada batch:
 │    │    │    │    │
 │    │    │    │    ├─> ThreadPoolExecutor (padrão: 2 workers)
 │    │    │    │    │    │
 │    │    │    │    │    ├─> Para cada tabela (paralelo):
 │    │    │    │    │    │    │
 │    │    │    │    │    │    ├─> Extrai DDL, colunas, índices, FKs
 │    │    │    │    │    │    │
 │    │    │    │    │    │    ├─> LLMAnalyzer.analyze_table_purpose()
 │    │    │    │    │    │    │    └─> LLM Chain → business_purpose
 │    │    │    │    │    │    │
 │    │    │    │    │    │    ├─> Calcula complexity_score (heurística)
 │    │    │    │    │    │    │
 │    │    │    │    │    │    └─> Cria TableInfo
 │    │    │    │    │    │
 │    │    │    │    │    └─> Aguarda conclusão do batch
 │    │    │    │    │
 │    │    │    │    └─> Próximo batch
 │    │    │    │
 │    │    │    └─> Cache de análise
 │    │    │
 │    │    ├─> KnowledgeGraph.add_table()
 │    │    │    └─> Adiciona ao grafo
 │    │    │
 │    │    ├─> Constrói grafo de relacionamentos (NetworkX)
 │    │    │
 │    │    └─> Calcula hierarquia por FKs
 │    │
 │    └─> Exporta resultados (JSON, PNG, Mermaid)
 │
 └─> Retorna estatísticas
```

### Exemplo CLI

```bash
# Análise de tabelas apenas
python main.py analyze --analysis-type=tables \
    --db-type postgresql \
    --user postgres --password senha \
    --host localhost --port 5432 \
    --database meu_banco --schema public \
    --batch-size 5 \
    --parallel-workers 2

# Análise completa (tabelas + procedures)
python main.py analyze --analysis-type=both \
    --db-type postgresql \
    --user postgres --password senha \
    --host localhost --port 5432 \
    --database meu_banco --schema public \
    --batch-size 5 \
    --parallel-workers 2
```

### Exemplo Programático

```python
from table_analyzer import TableAnalyzer
from analyzer import LLMAnalyzer
from app.core.models import DatabaseType, DatabaseConfig

# Inicializa LLM
llm = LLMAnalyzer(llm_mode='api', config=config)

# Cria analisador de tabelas
table_analyzer = TableAnalyzer(llm)

# Analisa tabelas do banco
table_analyzer.analyze_from_database(
    user="postgres",
    password="senha",
    host="localhost",
    port=5432,
    database="meu_banco",
    schema="public",
    db_type="postgresql",
    batch_size=5,
    parallel_workers=2
)

# Exporta resultados
table_analyzer.export_results("table_analysis.json")
table_analyzer.visualize_relationships("relationship_graph.png")
table_analyzer.export_mermaid_diagram("table_diagram.md")
```

---

## Query Flow (Agent)

### Diagrama de Sequência

```
User
 │
 ├─> CLI: query "pergunta em linguagem natural"
 │    │
 │    ├─> Carrega KnowledgeGraph do cache
 │    │    └─> cache/knowledge_graph.json
 │    │
 │    ├─> Inicializa CodeAnalysisAgent
 │    │    │
 │    │    ├─> Cria LangChain agent com tools:
 │    │    │    - query_procedure
 │    │    │    - query_table
 │    │    │    - analyze_field
 │    │    │    - trace_field_flow
 │    │    │    - crawl_procedure
 │    │    │    - execute_query (opcional)
 │    │    │
 │    │    └─> Configura system prompt
 │    │
 │    ├─> Agent.analyze(pergunta)
 │    │    │
 │    │    ├─> Agent escolhe tool apropriada
 │    │    │    │
 │    │    │    ├─> Tool executa query no KnowledgeGraph
 │    │    │    │    └─> Retorna informações
 │    │    │    │
 │    │    │    └─> Agent processa resultado
 │    │    │
 │    │    ├─> Se necessário, escolhe outra tool
 │    │    │    └─> Múltiplas iterações (max: 15)
 │    │    │
 │    │    └─> Agent sintetiza resposta final
 │    │
 │    └─> Retorna resposta ao usuário
 │
 └─> Exibe resposta formatada
```

### Exemplo CLI

```bash
# Query básica
python main.py query "O que faz a procedure PROCESSAR_PEDIDO?"

# Análise de campo
python main.py query "Analise o campo status da procedure VALIDAR_USUARIO"

# Análise de impacto
python main.py query "Se eu modificar CALCULAR_SALDO, quais procedures serão impactadas?"

# Rastreamento de campo
python main.py query "De onde vem o campo email usado em CRIAR_USUARIO?"

# Modo verbose (mostra tools utilizadas)
python main.py query "Quem chama VALIDAR_USUARIO?" --verbose

# Com configuração de banco para execute_query
python main.py query "Quantos registros tem a tabela PEDIDOS?" \
    --db-type postgresql \
    --db-user postgres \
    --db-password senha \
    --db-host localhost \
    --db-port 5432 \
    --db-database meu_banco
```

### Exemplo Programático

```python
from app.graph.knowledge_graph import CodeKnowledgeGraph
from app.analysis.code_crawler import CodeCrawler
from app.tools import init_tools, get_all_tools
from app.agents.code_analysis_agent import CodeAnalysisAgent
from analyzer import LLMAnalyzer
from app.config.config import get_config

# Setup
config = get_config()
llm_analyzer = LLMAnalyzer(config=config)
chat_model = llm_analyzer.get_chat_model()

# Load knowledge graph
knowledge_graph = CodeKnowledgeGraph(cache_path="./cache/knowledge_graph.json")
crawler = CodeCrawler(knowledge_graph)

# Initialize tools
init_tools(knowledge_graph, crawler)
tools = get_all_tools()

# Create agent
agent = CodeAnalysisAgent(
    llm=chat_model,
    tools=tools,
    verbose=True,
    max_iterations=15
)

# Query
result = agent.analyze("O que faz a procedure PROCESSAR_PEDIDO?")
if result["success"]:
    print(result["answer"])
    print(f"Tools usadas: {result['tool_call_count']}")
```

---

## Export Flow

### Diagrama de Sequência

```
User
 │
 ├─> ProcedureAnalyzer.export_*()
 │    │
 │    ├─> export_results()
 │    │    │
 │    │    ├─> Serializa ProcedureInfo
 │    │    │
 │    │    └─> Escreve JSON
 │    │
 │    ├─> visualize_dependencies()
 │    │    │
 │    │    ├─> Constrói grafo NetworkX
 │    │    │
 │    │    ├─> Layout (spring_layout)
 │    │    │
 │    │    └─> Renderiza PNG (matplotlib)
 │    │
 │    ├─> export_mermaid_diagram()
 │    │    │
 │    │    ├─> Gera código Mermaid
 │    │    │
 │    │    └─> Escreve .md
 │    │
 │    └─> export_mermaid_hierarchy()
 │         │
 │         ├─> Agrupa por níveis
 │         │
 │         └─> Gera hierarquia Mermaid
 │
 └─> Arquivos gerados
```

### Formatos de Exportação

#### JSON

```json
{
  "procedures": {
    "calc_saldo": {
      "name": "calc_saldo",
      "schema": "core",
      "parameters": [...],
      "called_procedures": ["valida_conta"],
      "called_tables": ["contas", "transacoes"],
      "business_logic": "...",
      "complexity_score": 7,
      "dependencies_level": 0
    }
  },
  "metadata": {
    "total_procedures": 10,
    "analysis_date": "2024-11-23T16:45:00"
  }
}
```

#### Mermaid Diagram

```mermaid
graph TD
    CALC_SALDO["CALC_SALDO\n[Nível 0, Complex: 7]"]:::medium
    VALIDA_CONTA["VALIDA_CONTA\n[Nível 0, Complex: 3]"]:::low
    GERA_RELATORIO["GERA_RELATORIO\n[Nível 1, Complex: 9]"]:::high

    GERA_RELATORIO --> CALC_SALDO
    GERA_RELATORIO --> VALIDA_CONTA
```

#### PNG

Grafo visual gerado com matplotlib, mostrando:
- Nós: Procedures
- Arestas: Dependências
- Cores: Níveis de complexidade

---

## CLI Usage Examples

### Análise Completa

```bash
# Verbose mode
python main.py --verbose analyze-files \
    --directory ./procedures \
    --export-json \
    --export-png \
    --export-mermaid \
    --output-dir ./output
```

### Com Logging

```bash
python main.py \
    --log-file ./logs/analysis.log \
    analyze-db \
    --db-type oracle \
    --user usuario \
    --password senha \
    --dsn localhost:1521/ORCL
```

### Análise Limitada

```bash
python main.py analyze-db \
    --db-type postgresql \
    --user usuario \
    --password senha \
    --host localhost \
    --database meu_banco \
    --limit 50 \
    --output-dir ./output
```

---

## Programmatic Usage

### Exemplo Completo

```python
import logging
from analyzer import LLMAnalyzer, ProcedureAnalyzer
from app.core.models import DatabaseType

# Configura logging
logging.basicConfig(level=logging.INFO)

# Inicializa LLM
llm = LLMAnalyzer(
    model_name="gpt-oss-120b",
    device="cuda",
    max_new_tokens=1024,
    temperature=0.3
)

# Cria analisador
analyzer = ProcedureAnalyzer(llm)

# Analisa procedures
analyzer.analyze_from_files("./procedures", "prc")

# Acessa resultados
for name, procedure in analyzer.procedures.items():
    print(f"{name}: complexidade {procedure.complexity_score}")

# Obtém hierarquia
hierarchy = analyzer.get_procedure_hierarchy()
for level, procedures in sorted(hierarchy.items()):
    print(f"Nível {level}: {len(procedures)} procedures")

# Exporta tudo
analyzer.export_results("analysis.json")
analyzer.visualize_dependencies("graph.png")
analyzer.export_mermaid_diagram("diagram.md")
analyzer.export_mermaid_hierarchy("hierarchy.md")
```

### Exemplo com Tratamento de Erros

```python
from analyzer import ProcedureAnalyzer, LLMAnalyzer
from app.core.models import (
    CodeGraphAIError,
    ProcedureLoadError,
    LLMAnalysisError
)

try:
    llm = LLMAnalyzer()
    analyzer = ProcedureAnalyzer(llm)

    analyzer.analyze_from_database(
        user="usuario",
        password="senha",
        dsn="localhost:1521/ORCL"
    )

except ProcedureLoadError as e:
    print(f"Erro ao carregar procedures: {e}")
except LLMAnalysisError as e:
    print(f"Erro na análise LLM: {e}")
except CodeGraphAIError as e:
    print(f"Erro geral: {e}")
```

---

## Related Documentation

- [Project Overview](project-overview.md) - Visão geral
- [Architecture Details](architecture.md) - Arquitetura
- [API Catalog](api-catalog.md) - Referência de APIs
- [Database Adapters](database-adapters.md) - Adaptadores

---

Generated on: 2025-01-27 12:00:00

