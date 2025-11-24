"""
Code Analysis Agent
LangChain agent that uses tools to analyze code intelligently
"""

import logging
from typing import List, Dict, Any, Optional

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
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
        self.agent_executor: Optional[AgentExecutor] = None

        self._initialize_agent()

    def _initialize_agent(self) -> None:
        """Initialize the agent executor with tools"""
        try:
            # Create prompt
            prompt = ChatPromptTemplate.from_messages([
                ("system", self._get_system_prompt()),
                ("user", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ])

            # Create agent
            agent = create_openai_tools_agent(
                llm=self.llm,
                tools=self.tools,
                prompt=prompt
            )

            # Create executor
            self.agent_executor = AgentExecutor(
                agent=agent,
                tools=self.tools,
                verbose=self.verbose,
                return_intermediate_steps=True,
                max_iterations=self.max_iterations,
                max_execution_time=self.max_execution_time,
                handle_parsing_errors=True
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

**IMPORTANTE - COMO USAR AS TOOLS:**

- SEMPRE use as tools antes de responder
- NÃO invente informações, use dados reais das tools
- Se uma tool retornar erro "não encontrado", tente variações do nome
- Para perguntas sobre campos, use analyze_field E/OU trace_field_flow
- Para perguntas sobre "o que faz", use query_procedure
- Para "quem chama" ou "dependências", use query_procedure com include_callers=true
- Para análise de impacto, use crawl_procedure

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
        Execute analysis using the agent

        Args:
            query: User question or command
            **kwargs: Additional arguments for agent

        Returns:
            Dict with answer and intermediate steps
        """
        if not self.agent_executor:
            raise RuntimeError("Agent not initialized")

        try:
            logger.info(f"Executing query: {query}")

            result = self.agent_executor.invoke({
                "input": query,
                **kwargs
            })

            # Extract tool calls from intermediate steps
            tool_calls = []
            if "intermediate_steps" in result:
                for step in result["intermediate_steps"]:
                    if len(step) >= 2:
                        action, observation = step[0], step[1]
                        tool_calls.append({
                            "tool": action.tool if hasattr(action, 'tool') else str(action),
                            "input": action.tool_input if hasattr(action, 'tool_input') else {},
                            "output": observation[:200] if isinstance(observation, str) else str(observation)[:200]
                        })

            return {
                "success": True,
                "answer": result.get("output", ""),
                "intermediate_steps": result.get("intermediate_steps", []),
                "tool_calls": tool_calls,
                "tool_call_count": len(tool_calls)
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

