# CodeGraphAI - Intelligence Tools & Agent 🤖

> Sistema inteligente de análise de código com Agent, Knowledge Graph e Tools especializadas

## 🆕 O que há de novo?

Esta versão adiciona capacidades avançadas de análise inteligente ao CodeGraphAI:

- **Knowledge Graph Persistente**: Cache estruturado em grafo (NetworkX) para queries rápidas
- **Static Code Analyzer**: Análise de código sem LLM usando regex avançado
- **Code Crawler**: Rastreamento recursivo de dependências e fields
- **LangChain Agent**: Agent inteligente com ferramentas especializadas
- **Query Natural**: Faça perguntas em linguagem natural sobre o código

## 🚀 Quick Start

### 1. Execute Análise Tradicional (popula Knowledge Graph)

```bash
# Analisa procedures e popula knowledge graph
python main.py analyze --analysis-type=procedures \
    --db-type postgresql \
    --user postgres --password senha \
    --host localhost --database mydb --schema public
```

Isso criará `cache/knowledge_graph.json` com o grafo persistente.

### 2. Faça Queries com o Agent

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
```

## 🛠️ Tools Disponíveis

O agent tem acesso a 5 tools especializadas:

### 1. query_procedure

Consulta informações de procedures:
- Lógica de negócio, parâmetros, dependências
- Quem chama a procedure (callers)
- Complexidade

**Uso pelo Agent:**
```
User: "O que faz a procedure PROCESSAR_PEDIDO?"
Agent: *usa query_procedure*
```

### 2. query_table

Consulta estrutura de tabelas:
- Colunas, tipos, constraints
- Relacionamentos (foreign keys)
- Propósito de negócio

**Uso pelo Agent:**
```
User: "Mostre a estrutura da tabela PEDIDOS"
Agent: *usa query_table*
```

### 3. analyze_field

Analisa campo específico:
- Onde é usado (read/write)
- Transformações aplicadas
- Relacionamentos

**Uso pelo Agent:**
```
User: "Analise o campo status"
Agent: *usa analyze_field*
```

### 4. trace_field_flow

Rastreia fluxo de campo:
- Origem dos dados
- Destino final
- Caminho completo através de procedures

**Uso pelo Agent:**
```
User: "De onde vem o campo email?"
Agent: *usa trace_field_flow*
```

### 5. crawl_procedure

Crawling de dependências:
- Árvore completa de dependências
- Análise de impacto
- Procedures e tabelas envolvidas

**Uso pelo Agent:**
```
User: "Qual o impacto de modificar VALIDAR_USUARIO?"
Agent: *usa crawl_procedure*
```

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

### Uso Direto das Tools (sem Agent)

```python
from app.graph.knowledge_graph import CodeKnowledgeGraph
from app.analysis.code_crawler import CodeCrawler
from app.tools import init_tools
from app.tools.graph_tools import query_procedure
from app.tools.field_tools import analyze_field
from app.tools.crawler_tools import crawl_procedure
import json

# Setup
knowledge_graph = CodeKnowledgeGraph(cache_path="./cache/knowledge_graph.json")
crawler = CodeCrawler(knowledge_graph)
init_tools(knowledge_graph, crawler)

# Usar tools diretamente
result = query_procedure("PROCESSAR_PEDIDO", include_dependencies=True)
data = json.loads(result)
print(data["data"]["business_logic"])

# Analisar campo
result = analyze_field("status", procedure_name="PROCESSAR_PEDIDO")
data = json.loads(result)
print(data["data"]["usage"])

# Crawling
result = crawl_procedure("PROCESSAR_PEDIDO", max_depth=3)
data = json.loads(result)
print(f"Total procedures: {data['statistics']['total_procedures']}")
```

## 📚 Exemplos Completos

Veja `examples/agent_example.py` para exemplos detalhados:

1. **Query básica de procedure**
2. **Análise de campo específico**
3. **Análise de impacto**
4. **Batch queries** (múltiplas perguntas)
5. **Uso programático direto das tools**

Execute os exemplos:

```bash
python examples/agent_example.py
```

## 🏗️ Arquitetura

### Visão Geral

```
Análise Tradicional → Knowledge Graph → Cache (JSON)
                                          ↓
                                        Agent
                                          ↓
                                    Tools (5x)
                                          ↓
                        ┌─────────────────┼─────────────────┐
                        ↓                 ↓                 ↓
                  Graph Tools      Field Tools      Crawler Tools
                (query_procedure)  (analyze_field)  (crawl_procedure)
                (query_table)      (trace_field_flow)
```

### Componentes

#### 1. Knowledge Graph (`app/graph/knowledge_graph.py`)

Grafo persistente em NetworkX que armazena:
- **Nodes**: procedures, tables, fields
- **Edges**: calls, accesses, reads, writes, references

Cache em JSON para carregamento rápido entre sessões.

#### 2. Static Code Analyzer (`app/analysis/static_analyzer.py`)

Análise de código sem LLM usando regex:
- Extração de procedures chamadas
- Extração de tabelas acessadas
- Extração de campos e seu uso (read/write/transform)
- Extração de parâmetros e variáveis

#### 3. Code Crawler (`app/analysis/code_crawler.py`)

Rastreamento recursivo:
- Crawling de procedures e dependências
- Tracing de campos através de procedures
- Análise de impacto de mudanças
- Field flow tracking

#### 4. LangChain Tools (`app/tools/`)

5 tools especializadas decoradas com `@tool`:
- `query_procedure`: Consulta de procedures
- `query_table`: Consulta de tabelas
- `analyze_field`: Análise de campos
- `trace_field_flow`: Rastreamento de campos
- `crawl_procedure`: Crawling de dependências

#### 5. LangChain Agent (`app/agents/code_analysis_agent.py`)

Agent que:
- Recebe perguntas em linguagem natural
- Escolhe tools apropriadas
- Executa raciocínio multi-step
- Retorna resposta estruturada

### Estrutura de Arquivos

```
CodeGraphAI/
├── app/
│   ├── graph/
│   │   └── knowledge_graph.py       # Knowledge Graph
│   ├── analysis/
│   │   ├── static_analyzer.py       # Static Analyzer
│   │   ├── code_crawler.py          # Code Crawler
│   │   └── models.py                # Data models
│   ├── tools/
│   │   ├── __init__.py              # Tool registry
│   │   ├── graph_tools.py           # Graph tools
│   │   ├── field_tools.py           # Field tools
│   │   └── crawler_tools.py         # Crawler tools
│   └── agents/
│       └── code_analysis_agent.py   # LangChain Agent
├── cache/
│   └── knowledge_graph.json         # Cached graph
├── examples/
│   └── agent_example.py             # Usage examples
└── tests/
    ├── analysis/
    │   ├── test_static_analyzer.py
    │   └── test_crawler.py
    └── tools/
        └── test_graph_tools.py
```

## ✅ Vantagens

### Performance
- **Queries rápidas**: Grafo em memória (< 100ms)
- **Sem LLM para queries**: Static analyzer + grafo
- **Cache persistente**: Sessões futuras são instantâneas

### Precisão
- **Análise estruturada**: Regex avançado e grafo
- **Rastreabilidade**: Caminho completo de campos
- **Validação**: Dados reais do código, não alucinações

### Inteligência
- **Agent**: Escolhe tools apropriadas automaticamente
- **Multi-step**: Raciocínio complexo com múltiplas tools
- **Natural**: Perguntas em linguagem natural

### Escalabilidade
- **Incremental**: Atualiza apenas o necessário
- **Cache**: Persistência entre sessões
- **Parallel-safe**: Queries concorrentes no grafo

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

### Knowledge Graph Options

```python
knowledge_graph = CodeKnowledgeGraph(
    cache_path="./cache/knowledge_graph.json"
)

# Estatísticas
stats = knowledge_graph.get_statistics()
print(stats)

# Limpar cache
knowledge_graph.clear()
knowledge_graph.save_to_cache()
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

## 📊 Casos de Uso

### 1. Análise de Impacto

**Cenário**: Você precisa modificar uma procedure e quer saber o impacto.

```bash
python main.py query "Se eu modificar CALCULAR_SALDO, quais procedures serão impactadas?"
```

O agent:
1. Usa `crawl_procedure` para mapear dependências
2. Usa `query_procedure` com `include_callers=true`
3. Retorna lista completa de impacto

### 2. Rastreamento de Dados

**Cenário**: Você quer saber de onde vem um campo específico.

```bash
python main.py query "De onde vem o campo 'email' usado em CRIAR_USUARIO?"
```

O agent:
1. Usa `analyze_field` para encontrar uso
2. Usa `trace_field_flow` para rastrear origem
3. Mostra caminho completo dos dados

### 3. Documentação Automática

**Cenário**: Você precisa documentar uma procedure.

```bash
python main.py query "Documente a procedure PROCESSAR_PEDIDO: o que faz, parâmetros, dependências"
```

O agent:
1. Usa `query_procedure` para informações básicas
2. Usa `crawl_procedure` para dependências
3. Gera documentação estruturada

### 4. Code Review

**Cenário**: Você está revisando código e quer entender complexidade.

```bash
python main.py query "Analise a complexidade da procedure VALIDAR_USUARIO e suas dependências"
```

O agent:
1. Usa `query_procedure` para complexidade
2. Usa `crawl_procedure` para dependências
3. Calcula complexidade total

## 🚧 Roadmap

- [x] ✅ Knowledge Graph persistente
- [x] ✅ Static Code Analyzer
- [x] ✅ Code Crawler com field tracing
- [x] ✅ LangChain Agent com tools
- [x] ✅ CLI para queries naturais
- [x] ✅ Exemplos e documentação
- [x] ✅ Testes unitários
- [ ] SQL Query Tools (executar SELECT no banco)
- [ ] Web UI para queries interativas
- [ ] Exportação de reports (PDF, HTML)
- [ ] Integração com IDEs (VS Code extension)

## 📝 Notas

### Dependências Adicionais

Certifique-se de ter as dependências do LangChain instaladas:

```bash
pip install langchain>=0.1.0 langchain-core>=0.1.0
```

### Cache do Knowledge Graph

O cache é salvo em `cache/knowledge_graph.json`. Para regenerar:

```bash
# Limpe o cache
rm cache/knowledge_graph.json

# Execute análise novamente
python main.py analyze --analysis-type=procedures ...
```

### Troubleshooting

**Agent não encontra informações:**
- Verifique se o cache existe: `ls cache/knowledge_graph.json`
- Re-execute análise para popular o grafo

**Tools retornam erro:**
- Verifique logs com `--verbose`
- Confirme que knowledge graph foi inicializado

**Performance lenta:**
- Verifique tamanho do grafo: `knowledge_graph.get_statistics()`
- Considere limitar análise com `--limit`

## 🤝 Contribuindo

Contribuições são bem-vindas! Áreas de interesse:

- Novos tipos de análise
- Mais tools especializadas
- Melhorias no agent prompt
- Testes adicionais
- Documentação

## 📄 Licença

MIT License - veja LICENSE para detalhes.

---

**CodeGraphAI** - Análise inteligente de código de banco de dados

