"""
Code Analysis Agent
LangChain agent that uses tools to analyze code intelligently
"""

import logging
from typing import List, Dict, Any, Optional

# LangChain 1.0+ imports
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)


class CodeAnalysisAgent:
    """
    Agent that uses tools to perform intelligent code analysis

    The agent can:
    - Query procedures and tables from knowledge graph
    - Analyze specific fields and trace their flow
    - Perform crawling of dependencies
    - Answer natural language questions about code
    """

    def __init__(
        self,
        llm: BaseChatModel,
        tools: List,
        verbose: bool = False,
        max_iterations: int = 15,
        max_execution_time: int = 300
    ):
        """
        Initialize Code Analysis Agent

        Args:
            llm: LangChain chat model
            tools: List of tools available to agent
            verbose: Show detailed execution
            max_iterations: Maximum tool calls
            max_execution_time: Maximum execution time in seconds
        """
        self.llm = llm
        self.tools = tools
        self.verbose = verbose
        self.max_iterations = max_iterations
        self.max_execution_time = max_execution_time
        self.agent_graph = None

        self._initialize_agent()

    def _initialize_agent(self) -> None:
        """Initialize the agent graph with tools (LangChain 1.0+ API)"""
        try:
            # Create agent using LangChain 1.0+ API
            self.agent_graph = create_agent(
                model=self.llm,
                tools=self.tools,
                system_prompt=self._get_system_prompt(),
                debug=self.verbose
            )

            logger.info(f"Agent initialized with {len(self.tools)} tools")
        except Exception as e:
            logger.error(f"Error initializing agent: {e}")
            raise

    def _get_system_prompt(self) -> str:
        """Return system prompt for the agent"""
        return """Você é um especialista em análise de código de banco de dados e stored procedures.

Você tem acesso a ferramentas (tools) que permitem:

1. **query_procedure**: Consultar informações de procedures
   - Use quando precisar saber o que uma procedure faz
   - Mostra lógica de negócio, parâmetros, dependências

2. **query_table**: Consultar estrutura de tabelas
   - Use para ver colunas, tipos, relacionamentos
   - Entender propósito de tabelas

3. **analyze_field**: Analisar campos específicos
   - Use quando perguntar sobre um campo específico
   - Mostra onde campo é usado, quem o lê/escreve

4. **trace_field_flow**: Rastrear fluxo de um campo
   - Use para entender origem e destino de dados
   - Segue o campo através de procedures

5. **crawl_procedure**: Fazer crawling de dependências
   - Use para análise de impacto
   - Ver árvore completa de dependências

6. **execute_query**: Executar queries SELECT no banco de dados
   - Use para consultar dados reais do banco (não apenas metadados)
   - Apenas queries SELECT são permitidas por segurança
   - LIMIT é aplicado automaticamente (máximo 1000 linhas)
   - Exemplo: "Quantos registros tem a tabela X?"
   - Exemplo: "Execute: SELECT * FROM users WHERE active = true LIMIT 10"

7. **sample_table_data**: Obter amostra de dados de uma tabela
   - Use para ver exemplos de dados reais
   - Entender estrutura e valores em campos
   - Exemplo: "Mostre 5 registros da tabela appointments"
   - Exemplo: "Amostra da tabela users com colunas name e email"

8. **get_field_statistics**: Estatísticas de um campo específico
   - Use para análise estatística de campos
   - Retorna: count, nulls, distinct, min, max, avg (quando aplicável)
   - Exemplo: "Qual o valor máximo do campo price na tabela products?"
   - Exemplo: "Quantos valores distintos tem o campo status na tabela orders?"

**IMPORTANTE - COMO USAR AS TOOLS:**

- SEMPRE use as tools antes de responder
- NÃO invente informações, use dados reais das tools
- Se uma tool retornar erro "não encontrado", tente variações do nome
- Para perguntas sobre campos, use analyze_field E/OU trace_field_flow
- Para perguntas sobre "o que faz", use query_procedure
- Para "quem chama" ou "dependências", use query_procedure com include_callers=true
- Para análise de impacto, use crawl_procedure
- Para consultar dados reais do banco, use execute_query, sample_table_data ou get_field_statistics
- Para perguntas sobre quantidade de registros ou valores, use execute_query ou get_field_statistics
- Para ver exemplos de dados, use sample_table_data

**FORMATO DAS RESPOSTAS:**

- Seja claro e objetivo
- Organize informações de forma estruturada
- Cite procedures e tabelas específicas
- Mencione relacionamentos importantes
- Se encontrar múltiplas informações relevantes, liste todas

**EXEMPLOS DE BOAS RESPOSTAS:**

Pergunta: "O que faz o campo status da procedure PROCESSAR_PEDIDO?"

Resposta:
```
O campo 'status' na procedure PROCESSAR_PEDIDO:

**Definição:**
- Vem da tabela PEDIDOS
- Tipo: VARCHAR2(20)
- Pode ser nulo: Não

**Uso:**
- Lido para validação de estado do pedido
- Escrito após processamento bem-sucedido
- Transformações: UPPER(status) para padronização

**Relacionamentos:**
- Usado também em VALIDAR_PEDIDO (leitura)
- Atualizado por ATUALIZAR_STATUS (escrita)

**Fluxo:**
PEDIDOS.status → PROCESSAR_PEDIDO → VALIDAR_PEDIDO
```

Sempre fundamente suas respostas com dados obtidos das tools."""

    def analyze(
        self,
        query: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute analysis using the agent (LangChain 1.0+ API)

        Args:
            query: User question or command
            **kwargs: Additional arguments for agent

        Returns:
            Dict with answer and intermediate steps
        """
        if not self.agent_graph:
            raise RuntimeError("Agent not initialized")

        try:
            logger.info(f"Executing query: {query}")

            # Invoke agent graph (LangChain 1.0+ API)
            config = {"configurable": {"thread_id": "1"}}
            result = self.agent_graph.invoke(
                {"messages": [("user", query)]},
                config=config
            )

            # Extract answer from messages (LangChain 1.0+ structure)
            messages = result.get("messages", [])
            answer = ""
            tool_calls = []

            # Process messages to extract answer and tool calls
            for msg in messages:
                # Handle different message types
                if hasattr(msg, 'content'):
                    content = msg.content
                elif isinstance(msg, dict):
                    content = msg.get("content", "")
                else:
                    content = str(msg)

                if content:
                    if isinstance(content, str):
                        answer += content + "\n"
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict):
                                if item.get("type") == "text":
                                    answer += item.get("text", "") + "\n"
                                elif item.get("type") == "tool_use":
                                    tool_calls.append({
                                        "tool": item.get("name", "unknown"),
                                        "input": item.get("input", {}),
                                        "id": item.get("id", "")
                                    })
                            elif isinstance(item, str):
                                answer += item + "\n"

                # Also check for tool calls in message attributes
                if hasattr(msg, 'tool_calls'):
                    for tool_call in msg.tool_calls:
                        tool_calls.append({
                            "tool": getattr(tool_call, 'name', 'unknown'),
                            "input": getattr(tool_call, 'args', {}),
                            "id": getattr(tool_call, 'id', '')
                        })

            # If no answer found, try to get from result directly
            if not answer.strip():
                if isinstance(result, dict):
                    # Try different possible keys
                    answer = result.get("output", result.get("response", result.get("answer", "")))
                elif hasattr(result, 'content'):
                    answer = str(result.content)
                else:
                    answer = str(result)

            # Clean answer
            answer = answer.strip()

            return {
                "success": True,
                "answer": answer if answer else "Resposta não disponível",
                "intermediate_steps": [],
                "tool_calls": tool_calls,
                "tool_call_count": len(tool_calls),
                "raw_result": result
            }

        except Exception as e:
            logger.exception(f"Error executing analysis: {e}")
            return {
                "success": False,
                "error": str(e),
                "answer": f"Erro ao executar análise: {str(e)}"
            }

    def batch_analyze(
        self,
        queries: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple queries in batch

        Args:
            queries: List of queries

        Returns:
            List of results
        """
        results = []
        for query in queries:
            result = self.analyze(query)
            results.append(result)
        return results

