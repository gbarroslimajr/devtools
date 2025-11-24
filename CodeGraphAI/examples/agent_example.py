"""
Exemplo de uso do Code Analysis Agent
Demonstra como usar o agent com tools para análise inteligente de código
"""

import sys
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))


def example_1_basic_query():
    """Exemplo 1: Query básica de procedure"""
    print("=" * 70)
    print("EXEMPLO 1: Query Básica de Procedure")
    print("=" * 70)

    from app.graph.knowledge_graph import CodeKnowledgeGraph
    from app.analysis.code_crawler import CodeCrawler
    from app.tools import init_tools, get_all_tools
    from app.agents.code_analysis_agent import CodeAnalysisAgent
    from analyzer import LLMAnalyzer
    from app.config.config import get_config

    # Load config
    config = get_config()

    # Initialize LLM
    print("Inicializando LLM...")
    llm_analyzer = LLMAnalyzer(config=config)
    chat_model = llm_analyzer.get_chat_model()

    # Load knowledge graph
    print("Carregando knowledge graph...")
    knowledge_graph = CodeKnowledgeGraph(cache_path="./cache/knowledge_graph.json")

    # Initialize crawler
    crawler = CodeCrawler(knowledge_graph)

    # Initialize tools
    print("Inicializando tools...")
    init_tools(knowledge_graph, crawler)
    tools = get_all_tools()
    print(f"✓ {len(tools)} tools disponíveis\n")

    # Create agent
    agent = CodeAnalysisAgent(
        llm=chat_model,
        tools=tools,
        verbose=True
    )

    # Execute query
    question = "O que faz a procedure PROCESSAR_PEDIDO?"
    print(f"Pergunta: {question}\n")

    result = agent.analyze(question)

    if result["success"]:
        print("\nResposta:")
        print("-" * 70)
        print(result["answer"])
        print("-" * 70)
        print(f"\nTools utilizadas: {result['tool_call_count']}")
    else:
        print(f"Erro: {result['error']}")


def example_2_field_analysis():
    """Exemplo 2: Análise de campo específico"""
    print("\n\n" + "=" * 70)
    print("EXEMPLO 2: Análise de Campo Específico")
    print("=" * 70)

    from app.graph.knowledge_graph import CodeKnowledgeGraph
    from app.analysis.code_crawler import CodeCrawler
    from app.tools import init_tools, get_all_tools
    from app.agents.code_analysis_agent import CodeAnalysisAgent
    from analyzer import LLMAnalyzer
    from app.config.config import get_config

    config = get_config()
    llm_analyzer = LLMAnalyzer(config=config)
    chat_model = llm_analyzer.get_chat_model()

    knowledge_graph = CodeKnowledgeGraph(cache_path="./cache/knowledge_graph.json")
    crawler = CodeCrawler(knowledge_graph)

    init_tools(knowledge_graph, crawler)
    tools = get_all_tools()

    agent = CodeAnalysisAgent(
        llm=chat_model,
        tools=tools,
        verbose=False  # Menos verboso
    )

    question = "O que faz o campo 'status' na procedure VALIDAR_USUARIO? De onde ele vem e para onde vai?"
    print(f"Pergunta: {question}\n")

    result = agent.analyze(question)

    if result["success"]:
        print("\nResposta:")
        print("-" * 70)
        print(result["answer"])
        print("-" * 70)


def example_3_impact_analysis():
    """Exemplo 3: Análise de impacto"""
    print("\n\n" + "=" * 70)
    print("EXEMPLO 3: Análise de Impacto")
    print("=" * 70)

    from app.graph.knowledge_graph import CodeKnowledgeGraph
    from app.analysis.code_crawler import CodeCrawler
    from app.tools import init_tools, get_all_tools
    from app.agents.code_analysis_agent import CodeAnalysisAgent
    from analyzer import LLMAnalyzer
    from app.config.config import get_config

    config = get_config()
    llm_analyzer = LLMAnalyzer(config=config)
    chat_model = llm_analyzer.get_chat_model()

    knowledge_graph = CodeKnowledgeGraph(cache_path="./cache/knowledge_graph.json")
    crawler = CodeCrawler(knowledge_graph)

    init_tools(knowledge_graph, crawler)
    tools = get_all_tools()

    agent = CodeAnalysisAgent(
        llm=chat_model,
        tools=tools,
        verbose=False
    )

    question = "Se eu modificar a procedure CALCULAR_SALDO, quais outras procedures serão impactadas?"
    print(f"Pergunta: {question}\n")

    result = agent.analyze(question)

    if result["success"]:
        print("\nResposta:")
        print("-" * 70)
        print(result["answer"])
        print("-" * 70)


def example_4_batch_queries():
    """Exemplo 4: Múltiplas queries em batch"""
    print("\n\n" + "=" * 70)
    print("EXEMPLO 4: Batch Queries")
    print("=" * 70)

    from app.graph.knowledge_graph import CodeKnowledgeGraph
    from app.analysis.code_crawler import CodeCrawler
    from app.tools import init_tools, get_all_tools
    from app.agents.code_analysis_agent import CodeAnalysisAgent
    from analyzer import LLMAnalyzer
    from app.config.config import get_config

    config = get_config()
    llm_analyzer = LLMAnalyzer(config=config)
    chat_model = llm_analyzer.get_chat_model()

    knowledge_graph = CodeKnowledgeGraph(cache_path="./cache/knowledge_graph.json")
    crawler = CodeCrawler(knowledge_graph)

    init_tools(knowledge_graph, crawler)
    tools = get_all_tools()

    agent = CodeAnalysisAgent(
        llm=chat_model,
        tools=tools,
        verbose=False
    )

    questions = [
        "Quantas procedures chamam VALIDAR_USUARIO?",
        "Quais tabelas são acessadas pela procedure PROCESSAR_PEDIDO?",
        "Qual a complexidade da procedure CALCULAR_SALDO?"
    ]

    print("Executando múltiplas queries...\n")

    results = agent.batch_analyze(questions)

    for i, (question, result) in enumerate(zip(questions, results), 1):
        print(f"\n{i}. {question}")
        print("-" * 70)
        if result["success"]:
            print(result["answer"])
        else:
            print(f"Erro: {result['error']}")


def example_5_programmatic_usage():
    """Exemplo 5: Uso programático direto das tools (sem agent)"""
    print("\n\n" + "=" * 70)
    print("EXEMPLO 5: Uso Programático Direto das Tools")
    print("=" * 70)

    from app.graph.knowledge_graph import CodeKnowledgeGraph
    from app.analysis.code_crawler import CodeCrawler
    from app.tools import init_tools
    from app.tools.graph_tools import query_procedure
    from app.tools.field_tools import analyze_field
    from app.tools.crawler_tools import crawl_procedure
    import json

    knowledge_graph = CodeKnowledgeGraph(cache_path="./cache/knowledge_graph.json")
    crawler = CodeCrawler(knowledge_graph)

    init_tools(knowledge_graph, crawler)

    print("\n1. Consultar procedure diretamente:")
    result = query_procedure("PROCESSAR_PEDIDO", include_dependencies=True)
    data = json.loads(result)
    if data["success"]:
        print(f"   Procedure: {data['data']['procedure_name']}")
        print(f"   Complexidade: {data['data']['complexity_score']}")
        print(f"   Dependências: {data['data'].get('total_dependencies', 0)}")

    print("\n2. Analisar campo específico:")
    result = analyze_field("status", procedure_name="PROCESSAR_PEDIDO")
    data = json.loads(result)
    if data["success"]:
        print(f"   Campo: {data['data']['field_name']}")
        print(f"   Usado em: {len(data['data']['usage']['used_in_procedures'])} procedures")

    print("\n3. Fazer crawling de dependências:")
    result = crawl_procedure("PROCESSAR_PEDIDO", max_depth=3)
    data = json.loads(result)
    if data["success"]:
        print(f"   Total procedures: {data['statistics']['total_procedures']}")
        print(f"   Total tabelas: {data['statistics']['total_tables']}")


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 20 + "CODE ANALYSIS AGENT" + " " * 29 + "║")
    print("║" + " " * 24 + "Exemplos de Uso" + " " * 29 + "║")
    print("╚" + "=" * 68 + "╝")

    try:
        # Verifica se cache existe
        cache_path = Path("./cache/knowledge_graph.json")
        if not cache_path.exists():
            print("\n⚠️  Cache do knowledge graph não encontrado!")
            print("Execute 'python main.py analyze' primeiro para criar o knowledge graph.\n")
            sys.exit(1)

        # Executa exemplos
        example_1_basic_query()
        example_2_field_analysis()
        example_3_impact_analysis()
        example_4_batch_queries()
        example_5_programmatic_usage()

        print("\n\n" + "=" * 70)
        print("✓ Todos os exemplos executados com sucesso!")
        print("=" * 70)

    except ImportError as e:
        print(f"\n❌ Erro de importação: {e}")
        print("Instale as dependências: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

