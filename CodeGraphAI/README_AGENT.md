# CodeGraphAI - Intelligence Tools & Agent 🤖

> Guia operacional das ferramentas de análise inteligente

Este documento fornece um guia prático para usar as Intelligence Tools do CodeGraphAI, incluindo o Agent, Knowledge Graph, Vector Search e Tools especializadas.

> 📖 Para detalhes técnicos e arquiteturais, consulte a [documentação oficial](.cursor/documentation/):
> - [Architecture](.cursor/documentation/architecture.md) - Arquitetura e padrões de design
> - [API Catalog](.cursor/documentation/api-catalog.md) - Referência completa de APIs
> - [Integration Flows](.cursor/documentation/integration-flows.md) - Fluxos de integração

## 🆕 O que são as Intelligence Tools?

As Intelligence Tools adicionam capacidades avançadas de análise inteligente ao CodeGraphAI:

- **Knowledge Graph Persistente**: Cache estruturado em grafo (NetworkX) para queries rápidas
- **Vector Knowledge Graph**: Busca semântica usando embeddings (RAG pipeline)
- **Static Code Analyzer**: Análise de código sem LLM usando regex avançado
- **Code Crawler**: Rastreamento recursivo de dependências e fields
- **LangChain Agent**: Agent inteligente com ferramentas especializadas
- **Query Natural**: Faça perguntas em linguagem natural sobre o código

> 📖 Para visão geral completa, veja [Project Overview - Intelligence Tools](.cursor/documentation/project-overview.md#intelligence-tools)

## 🚀 Quick Start

### 1. Execute Análise Tradicional (popula Knowledge Graph)

Primeiro, execute análise para popular o knowledge graph:

```bash
# Análise de procedures
python main.py analyze --analysis-type=procedures \
    --db-type postgresql \
    --user postgres --password senha \
    --host localhost --port 5432 \
    --database meu_banco --schema public

# Análise de tabelas
python main.py analyze --analysis-type=tables \
    --db-type postgresql \
    --user postgres --password senha \
    --host localhost --port 5432 \
    --database meu_banco --schema public

# Análise completa (procedures + tabelas)
python main.py analyze --analysis-type=both \
    --db-type postgresql \
    --user postgres --password senha \
    --host localhost --port 5432 \
    --database meu_banco --schema public
```

Isso criará `cache/knowledge_graph.json` com o grafo persistente.

### 2. Configure Busca Semântica (Opcional)

Para habilitar busca semântica com Vector Knowledge Graph, configure no `.env`:

```bash
CODEGRAPHAI_EMBEDDING_BACKEND=sentence-transformers
CODEGRAPHAI_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CODEGRAPHAI_VECTOR_STORE_PATH=./cache/vector_store
```

> 📖 Para detalhes sobre Vector Knowledge Graph, veja [Architecture - Vector Knowledge Graph](.cursor/documentation/architecture.md#8-vector-knowledge-graph-e-busca-semântica)

### 3. Faça Queries com o Agent

```bash
# Query básica
python main.py query "O que faz a procedure PROCESSAR_PEDIDO?"

# Busca semântica (se Vector Knowledge Graph configurado)
python main.py query "Quais tabelas estão relacionadas a pagamentos e transações financeiras?"

# Análise de campo
python main.py query "Analise o campo status da procedure VALIDAR_USUARIO"

# Análise de impacto
python main.py query "Se eu modificar CALCULAR_SALDO, quais procedures serão impactadas?"

# Rastreamento de campo
python main.py query "De onde vem o campo email usado em CRIAR_USUARIO?"

# Modo verbose (mostra tools utilizadas)
python main.py query "Quem chama VALIDAR_USUARIO?" --verbose
```

## 🛠️ Tools Disponíveis

O agent tem acesso a múltiplas tools especializadas:

### Tools Básicas

1. **query_procedure**: Consulta informações de procedures
   - Lógica de negócio, parâmetros, dependências
   - Quem chama a procedure (callers)
   - Complexidade

2. **query_table**: Consulta estrutura de tabelas
   - Colunas, tipos, constraints
   - Relacionamentos (foreign keys)
   - Propósito de negócio

3. **analyze_field**: Analisa campo específico
   - Onde é usado (read/write)
   - Transformações aplicadas
   - Relacionamentos

4. **trace_field_flow**: Rastreia fluxo de campo
   - Origem dos dados
   - Destino final
   - Caminho completo através de procedures

5. **crawl_procedure**: Crawling de dependências
   - Árvore completa de dependências
   - Análise de impacto
   - Procedures e tabelas envolvidas

### Tools de Busca Semântica (se Vector Knowledge Graph habilitado)

6. **semantic_search_tables**: Busca semântica de tabelas
   - Encontra tabelas por significado, não apenas por nome
   - Usa embeddings para similaridade semântica

7. **semantic_search_procedures**: Busca semântica de procedures
   - Encontra procedures por significado
   - Baseado em lógica de negócio e contexto

8. **hybrid_search**: Busca híbrida
   - Combina busca semântica + relacionamentos estruturais
   - Melhor precisão e recall

> 📖 Para referência completa das tools, veja [API Catalog - Graph Classes](.cursor/documentation/api-catalog.md#graph-classes) e [Integration Flows - Query Flow](.cursor/documentation/integration-flows.md#query-flow-agent)

## 💻 Uso Programático

### Exemplo Básico

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

### Exemplo com Vector Knowledge Graph

```python
from app.graph.knowledge_graph import CodeKnowledgeGraph
from app.graph.vector_knowledge_graph import VectorKnowledgeGraph
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

# Initialize Vector Knowledge Graph (busca semântica)
vector_kg = VectorKnowledgeGraph(
    knowledge_graph=knowledge_graph,
    embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    vector_store_path="./cache/vector_store"
)

# Initialize crawler
crawler = CodeCrawler(knowledge_graph)

# Initialize tools (inclui vector tools se vector_kg disponível)
init_tools(knowledge_graph, crawler, vector_kg=vector_kg)
tools = get_all_tools()

# Create agent
agent = CodeAnalysisAgent(
    llm=chat_model,
    tools=tools,
    verbose=True,
    max_iterations=15
)

# Query com busca semântica
result = agent.analyze(
    "Quais tabelas estão relacionadas a pagamentos e transações financeiras?"
)
if result["success"]:
    print(result["answer"])

# Uso direto do VectorKnowledgeGraph
semantic_results = vector_kg.semantic_search(
    "tabelas de clientes e usuários",
    top_k=5,
    node_type="table"
)

for result in semantic_results:
    print(f"{result.node_id}: {result.similarity:.3f}")
```

> 📖 Para mais exemplos programáticos, veja [Integration Flows - Programmatic Usage](.cursor/documentation/integration-flows.md#programmatic-usage)

## 📊 Casos de Uso

### 1. Análise de Impacto

**Cenário**: Você precisa modificar uma procedure e quer saber o impacto.

```bash
python main.py query "Se eu modificar CALCULAR_SALDO, quais procedures serão impactadas?"
```

O agent usa `crawl_procedure` e `query_procedure` para mapear dependências e retornar lista completa de impacto.

### 2. Busca Semântica

**Cenário**: Você quer encontrar tabelas relacionadas a um conceito, mas não sabe o nome exato.

```bash
python main.py query "Quais tabelas estão relacionadas a pagamentos e transações financeiras?"
```

O agent usa `semantic_search_tables` ou `hybrid_search` para encontrar tabelas por significado.

### 3. Rastreamento de Dados

**Cenário**: Você quer saber de onde vem um campo específico.

```bash
python main.py query "De onde vem o campo 'email' usado em CRIAR_USUARIO?"
```

O agent usa `analyze_field` e `trace_field_flow` para rastrear origem dos dados.

### 4. Documentação Automática

**Cenário**: Você precisa documentar uma procedure.

```bash
python main.py query "Documente a procedure PROCESSAR_PEDIDO: o que faz, parâmetros, dependências"
```

O agent usa múltiplas tools para gerar documentação estruturada.

> 📖 Para mais casos de uso, veja [Integration Flows - Query Flow](.cursor/documentation/integration-flows.md#query-flow-agent)

## 🔧 Configuração Avançada

### Agent Configuration

```python
agent = CodeAnalysisAgent(
    llm=chat_model,
    tools=tools,
    verbose=True,              # Mostra execução detalhada
    max_iterations=15,         # Máximo de tool calls
    max_execution_time=300     # Timeout em segundos
)
```

### Vector Knowledge Graph Options

```python
vector_kg = VectorKnowledgeGraph(
    knowledge_graph=knowledge_graph,
    embedding_backend="sentence-transformers",
    embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    vector_store_path="./cache/vector_store",
    batch_size=32,
    device="cpu"  # ou "cuda"
)
```

### Crawler Options

```python
crawler = CodeCrawler(knowledge_graph)

# Crawling com configuração
result = crawler.crawl_procedure(
    proc_name="PROCESSAR_PEDIDO",
    max_depth=5,              # Profundidade máxima
    include_tables=True       # Incluir tabelas
)

# Field tracing
trace = crawler.trace_field(
    field_name="status",
    start_procedure="PROCESSAR_PEDIDO",
    max_depth=10
)
```

> 📖 Para configuração completa, veja [API Catalog](.cursor/documentation/api-catalog.md)

## 🧪 Testes

Execute os testes unitários:

```bash
# Todos os testes
python -m pytest tests/

# Apenas static analyzer
python -m pytest tests/analysis/test_static_analyzer.py

# Apenas crawler
python -m pytest tests/analysis/test_crawler.py

# Apenas tools
python -m pytest tests/tools/test_graph_tools.py

# Com coverage
python -m pytest tests/ --cov=app --cov-report=html
```

## 🚧 Troubleshooting

### Agent não encontra informações

- Verifique se o cache existe: `ls cache/knowledge_graph.json`
- Re-execute análise para popular o grafo
- Use `--verbose` para ver detalhes

### Tools retornam erro

- Verifique logs com `--verbose`
- Confirme que knowledge graph foi inicializado
- Verifique se Vector Knowledge Graph está configurado corretamente (se usando busca semântica)

### Performance lenta

- Verifique tamanho do grafo: `knowledge_graph.get_statistics()`
- Considere limitar análise com `--limit`
- Reduza `--max-iterations` se necessário
- Para Vector Knowledge Graph, verifique se indexação foi concluída

### Busca semântica não funciona

- Verifique se dependências estão instaladas: `sentence-transformers`, `chromadb`
- Confirme configuração no `.env`
- Verifique se indexação foi executada (primeira busca indexa automaticamente)

> 📖 Para mais troubleshooting, veja [Integration Flows - Troubleshooting](.cursor/documentation/integration-flows.md#troubleshooting)

## 📚 Documentação Adicional

- **[Architecture](.cursor/documentation/architecture.md)** - Arquitetura detalhada e padrões de design
- **[API Catalog](.cursor/documentation/api-catalog.md)** - Referência completa de APIs
- **[Integration Flows](.cursor/documentation/integration-flows.md)** - Fluxos de integração e exemplos
- **[Project Overview](.cursor/documentation/project-overview.md)** - Visão geral do projeto

## 🗺️ Roadmap

Para visualizar o roadmap completo de melhorias planejadas, incluindo prioridades e estimativas, consulte a [documentação oficial](.cursor/documentation/improvement-roadmap.md).

---

**CodeGraphAI** - Análise inteligente de código de banco de dados

---
Generated on: 2025-11-24 19:39:51
