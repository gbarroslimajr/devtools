"""
Analisador de Procedures de Banco de Dados usando LangChain e LLM Local
Extrai, analisa e mapeia relacionamentos entre stored procedures
"""

import re
import json
import logging
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import asdict
from collections import defaultdict
from pathlib import Path

from langchain_core.prompts import PromptTemplate
from langchain_community.llms import HuggingFacePipeline
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import networkx as nx
import matplotlib.pyplot as plt
from tqdm import tqdm

# Importar modelos e exceções da nova arquitetura
from app.core.models import (
    ProcedureInfo,
    DatabaseType,
    DatabaseConfig,
    ProcedureLoadError,
    LLMAnalysisError,
    DependencyAnalysisError,
    ExportError,
    ValidationError,
)
from app.io.factory import create_loader
from app.io.file_loader import FileLoader
from app.llm.toon_converter import format_dependencies_prompt_example, parse_llm_response, TOON_AVAILABLE
from app.llm.token_tracker import TokenTracker
from app.llm.token_callback import TokenUsageCallback

# Configurar logger
logger = logging.getLogger(__name__)

# Constantes de configuração
class AnalysisConfig:
    """Configurações para análise de procedures"""
    MAX_CODE_LENGTH_BUSINESS_LOGIC = 2000
    MAX_CODE_LENGTH_DEPENDENCIES = 3000
    MAX_CODE_LENGTH_COMPLEXITY = 2000
    MAX_CODE_LENGTH_PARAMETERS = 500

    # Heurística de complexidade
    COMPLEXITY_LINES_THRESHOLD = 50
    COMPLEXITY_LINES_MAX_BONUS = 3
    COMPLEXITY_IF_WEIGHT = 0.5
    COMPLEXITY_LOOP_WEIGHT = 0.7
    COMPLEXITY_CURSOR_WEIGHT = 0.8
    COMPLEXITY_EXCEPTION_WEIGHT = 0.3
    COMPLEXITY_MAX_SCORE = 10

    # Parâmetros LLM
    LLM_MAX_NEW_TOKENS = 1024
    LLM_TEMPERATURE = 0.3
    LLM_TOP_P = 0.95
    LLM_REPETITION_PENALTY = 1.15

    # Visualização
    GRAPH_FIGSIZE = (20, 15)
    GRAPH_NODE_SIZE = 1000
    GRAPH_FONT_SIZE = 8
    GRAPH_DPI = 300


# Exceções e modelos importados de app.core.models
# Mantidos aqui para backward compatibility
# Re-exportar para manter compatibilidade com imports antigos
# Nota: ProcedureInfo e exceções são importados de app.core.models
# mas re-exportados aqui para manter compatibilidade

# Re-exportar classes e exceções para backward compatibility
__all__ = [
    'ProcedureInfo',
    'ProcedureLoader',
    'LLMAnalyzer',
    'ProcedureAnalyzer',
    'CodeGraphAIError',
    'ProcedureLoadError',
    'LLMAnalysisError',
    'DependencyAnalysisError',
    'ExportError',
    'ValidationError',
    'AnalysisConfig',
]


class ProcedureLoader:
    """
    Carrega procedures de diferentes fontes

    Mantido para backward compatibility. Usa os novos adaptadores internamente.
    """

    @staticmethod
    def from_files(directory_path: str, extension: str = "prc") -> Dict[str, str]:
        """
        Carrega procedures de arquivos .prc

        Args:
            directory_path: Caminho do diretório com arquivos .prc
            extension: Extensão dos arquivos (padrão: "prc")

        Returns:
            Dict com nome da procedure como chave e código-fonte como valor

        Raises:
            ProcedureLoadError: Se o diretório não existir ou houver erro ao ler arquivos
            ValidationError: Se a extensão for inválida ou arquivos estiverem vazios
        """
        # Usa FileLoader da nova arquitetura
        return FileLoader.from_files(directory_path, extension)

    @staticmethod
    def from_database(
        user: str,
        password: str,
        dsn: str,
        schema: Optional[str] = None,
        db_type: Optional[str] = None,
        database: Optional[str] = None,
        port: Optional[int] = None
    ) -> Dict[str, str]:
        """
        Carrega procedures diretamente do banco de dados

        Args:
            user: Usuário do banco de dados
            password: Senha do banco de dados
            dsn: Data Source Name (host:port/service) ou host
            schema: Schema específico (opcional)
            db_type: Tipo de banco (oracle, postgresql, mssql, mysql).
                    Se None, assume Oracle para backward compatibility

        Returns:
            Dict com schema.nome como chave e código-fonte como valor

        Raises:
            ProcedureLoadError: Se houver erro de conexão ou consulta
            ValidationError: Se credenciais estiverem vazias ou tipo de banco inválido
        """
        # Se db_type não fornecido, assume Oracle (backward compatibility)
        if db_type is None:
            db_type = DatabaseType.ORACLE
        else:
            try:
                db_type = DatabaseType(db_type.lower())
            except ValueError:
                raise ValidationError(
                    f"Tipo de banco inválido: {db_type}. "
                    f"Tipos suportados: {[dt.value for dt in DatabaseType]}"
                )

        # Para Oracle, DSN pode ser no formato host:port/service
        # Para outros bancos, DSN é apenas o host
        if db_type == DatabaseType.ORACLE:
            # Oracle: DSN pode ser completo ou precisar de parsing
            # Se contém :, assume formato host:port/service
            if ':' in dsn:
                parts = dsn.split('/')
                host_port = parts[0]
                parsed_database = parts[1] if len(parts) > 1 else None

                if ':' in host_port:
                    parsed_host, port_str = host_port.split(':')
                    try:
                        parsed_port = int(port_str)
                    except ValueError:
                        parsed_port = None
                else:
                    parsed_host = host_port
                    parsed_port = None
            else:
                # DSN simples, assume que é host completo
                parsed_host = dsn
                parsed_port = None
                parsed_database = None

            # Usa valores fornecidos ou valores parseados do DSN
            host = parsed_host
            port = port or parsed_port
            database = database or parsed_database
        else:
            # Para outros bancos, DSN é apenas host
            # Mas pode receber database e port como parâmetros separados
            host = dsn
            # Se port não foi fornecido, tenta parsear do dsn (formato host:port)
            if port is None and ':' in dsn:
                try:
                    host, port_str = dsn.split(':')
                    port = int(port_str)
                except (ValueError, IndexError):
                    pass
            # database deve ser fornecido como parâmetro para bancos não-Oracle

        # Cria DatabaseConfig
        config = DatabaseConfig(
            db_type=db_type,
            user=user,
            password=password,
            host=host,
            port=port,
            database=database,
            schema=schema
        )

        # Usa factory para criar loader apropriado
        loader = create_loader(db_type)
        return loader.load_procedures(config)


class LLMAnalyzer:
    """Analisa procedures usando LLM (local ou via API)"""

    def __init__(self, model_name: Optional[str] = None,
                 device: Optional[str] = None,
                 llm_mode: Optional[str] = None,
                 config: Optional[Any] = None):
        """
        Inicializa o modelo LLM (local ou via API)

        Args:
            model_name: Nome ou caminho do modelo HuggingFace (apenas modo local)
            device: Dispositivo para execução "cuda" ou "cpu" (apenas modo local)
            llm_mode: Modo de execução "local" ou "api" (se None, lê de config)
            config: Instância de Config (opcional, será carregada se None)

        Raises:
            LLMAnalysisError: Se houver erro ao carregar o modelo
        """
        # Carregar config se não fornecido
        if config is None:
            from config import get_config
            config = get_config()

        self.config = config

        # Inicializar tracker e callback de tokens
        self.token_tracker = TokenTracker()
        self.token_callback = TokenUsageCallback(self.token_tracker)

        # Determinar modo LLM
        if llm_mode is None:
            llm_mode = config.llm_mode

        self.llm_mode = llm_mode

        # Inicializar LLM baseado no modo
        if self.llm_mode == 'api':
            self._init_api_llm()
        else:
            # Modo local (backward compatibility)
            # Usar parâmetros fornecidos ou valores do config
            model = model_name or config.model_name
            dev = device or config.device
            self._init_local_llm(model, dev)

        # Templates de prompts (comum para ambos os modos)
        self._setup_prompts()
        logger.info(f"Modelo LLM carregado com sucesso (modo: {self.llm_mode})")

    def _init_local_llm(self, model_name: str, device: str) -> None:
        """
        Inicializa modelo LLM local (HuggingFace)

        Args:
            model_name: Nome ou caminho do modelo HuggingFace
            device: Dispositivo para execução ("cuda" ou "cpu")

        Raises:
            LLMAnalysisError: Se houver erro ao carregar o modelo
        """
        logger.info(f"Carregando modelo local {model_name}...")

        try:
            # Configuração para modelo local grande
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                device_map="auto",
                load_in_8bit=True,  # Usa quantização para economizar memória
                torch_dtype="auto"
            )

            # Pipeline do HuggingFace
            pipe = pipeline(
                "text-generation",
                model=model,
                tokenizer=tokenizer,
                max_new_tokens=AnalysisConfig.LLM_MAX_NEW_TOKENS,
                temperature=AnalysisConfig.LLM_TEMPERATURE,
                top_p=AnalysisConfig.LLM_TOP_P,
                repetition_penalty=AnalysisConfig.LLM_REPETITION_PENALTY
            )

            self.llm = HuggingFacePipeline(pipeline=pipe)

        except Exception as e:
            logger.error(f"Erro ao carregar modelo LLM local: {e}")
            raise LLMAnalysisError(f"Erro ao carregar modelo {model_name}: {e}")

    def _init_api_llm(self) -> None:
        """
        Inicializa modelo LLM via API (factory pattern)

        Raises:
            LLMAnalysisError: Se houver erro ao inicializar API
        """
        logger.info(f"Inicializando LLM via API (provider: {self.config.llm_provider})...")

        try:
            provider = self.config.llm_provider

            if provider.startswith('genfactory_'):
                self._init_genfactory_llm(provider)
            elif provider == 'openai':
                self._init_openai_llm()
            elif provider == 'anthropic':
                self._init_anthropic_llm()
            else:
                raise LLMAnalysisError(f"Provider não suportado: {provider}")

        except LLMAnalysisError:
            raise
        except Exception as e:
            logger.error(f"Erro ao inicializar LLM via API: {e}")
            raise LLMAnalysisError(f"Erro ao inicializar LLM via API: {e}")

    def _init_genfactory_llm(self, provider: str) -> None:
        """
        Inicializa GenFactory LLM

        Args:
            provider: Nome do provider GenFactory (genfactory_llama70b, genfactory_codestral, genfactory_gptoss120b)

        Raises:
            LLMAnalysisError: Se houver erro ao inicializar GenFactory
        """
        # Selecionar configuração do provider
        if provider == 'genfactory_llama70b':
            provider_config = self.config.genfactory_llama70b
        elif provider == 'genfactory_codestral':
            provider_config = self.config.genfactory_codestral
        elif provider == 'genfactory_gptoss120b':
            provider_config = self.config.genfactory_gptoss120b
        else:
            raise LLMAnalysisError(f"Provider GenFactory não suportado: {provider}")

        # Validar configuração
        if not provider_config:
            raise LLMAnalysisError(f"Configuração do provider {provider} não encontrada")

        if not provider_config.get('authorization_token'):
            raise LLMAnalysisError(f"Authorization token é obrigatório para {provider}")

        if not provider_config.get('base_url'):
            raise LLMAnalysisError(f"Base URL é obrigatória para {provider}")

        # Criar cliente GenFactory
        from app.llm.genfactory_client import GenFactoryClient
        from app.llm.langchain_wrapper import GenFactoryLLM

        client = GenFactoryClient(provider_config)

        # Criar wrapper LangChain com callback
        self.llm = GenFactoryLLM(client, callbacks=[self.token_callback])

        logger.info(f"GenFactory LLM inicializado: {provider_config.get('name', provider)}")

    def _init_openai_llm(self) -> None:
        """
        Inicializa OpenAI via LangChain usando ChatOpenAI

        Raises:
            LLMAnalysisError: Se houver erro ao inicializar OpenAI
        """
        from langchain_openai import ChatOpenAI

        config = self.config.openai

        if not config or not config.get('api_key'):
            raise LLMAnalysisError("OpenAI API key é obrigatória")

        kwargs = {
            'model': config.get('model', 'gpt-5.1'),
            'temperature': config.get('temperature', 0.3),
            'max_tokens': config.get('max_tokens', 4000),
            'timeout': config.get('timeout', 60),
        }

        # Base URL customizado (para Azure OpenAI)
        if config.get('base_url'):
            kwargs['base_url'] = config['base_url']

        self.llm = ChatOpenAI(
            api_key=config['api_key'],
            callbacks=[self.token_callback],
            **kwargs
        )

        logger.info(f"OpenAI inicializado: {kwargs['model']}")

    def _init_anthropic_llm(self) -> None:
        """
        Inicializa Anthropic Claude via LangChain usando ChatAnthropic

        Raises:
            LLMAnalysisError: Se houver erro ao inicializar Anthropic
        """
        from langchain_anthropic import ChatAnthropic

        config = self.config.anthropic

        if not config or not config.get('api_key'):
            raise LLMAnalysisError("Anthropic API key é obrigatória")

        self.llm = ChatAnthropic(
            api_key=config['api_key'],
            model=config.get('model', 'claude-sonnet-4-5-20250929'),
            temperature=config.get('temperature', 0.3),
            max_tokens=config.get('max_tokens', 4000),
            timeout=config.get('timeout', 60),
            callbacks=[self.token_callback]
        )

        logger.info(f"Anthropic Claude inicializado: {config.get('model')}")

    def _setup_prompts(self) -> None:
        """Configura templates de prompts para análise"""

        # Análise de lógica de negócio
        self.business_logic_prompt = PromptTemplate(
            input_variables=["code", "proc_name"],
            template="""Analise a seguinte stored procedure e descreva sua lógica de negócio em português de forma concisa:

Procedure: {proc_name}

Código:
{code}

Forneça uma descrição clara do que esta procedure faz, incluindo:
1. Objetivo principal
2. Principais operações realizadas
3. Regras de negócio aplicadas

Resposta:"""
        )

        # Identificação de dependências
        # Usa TOON se habilitado na configuração, senão usa JSON
        use_toon = getattr(self.config, 'llm_use_toon', False) and TOON_AVAILABLE
        example_format = format_dependencies_prompt_example(use_toon=use_toon)

        self.dependencies_prompt = PromptTemplate(
            input_variables=["code"],
            template=f"""Analise o código SQL/PL-SQL abaixo e identifique:

1. Todas as procedures/functions chamadas (formato: schema.procedure ou apenas procedure)
2. Todas as tabelas acessadas (SELECT, INSERT, UPDATE, DELETE)

Código:
{{code}}

{example_format}"""
        )

        # Avaliação de complexidade
        self.complexity_prompt = PromptTemplate(
            input_variables=["code"],
            template="""Avalie a complexidade da seguinte stored procedure em uma escala de 1 a 10, considerando:
- Número de linhas
- Estruturas de controle (IFs, LOOPs)
- Número de tabelas/procedures utilizadas
- Lógica de negócio

Código:
{code}

Retorne apenas um número de 1 a 10:"""
        )

        # Análise de propósito de tabela
        self.table_purpose_prompt = PromptTemplate(
            input_variables=["ddl", "table_name", "columns"],
            template="""Analise a seguinte tabela de banco de dados e descreva seu propósito de negócio em português:

Tabela: {table_name}
Colunas: {columns}

DDL:
{ddl}

Forneça uma descrição clara do propósito desta tabela no contexto do negócio, incluindo:
1. Qual entidade ou conceito do negócio esta tabela representa
2. Qual o papel principal desta tabela no sistema
3. Principais relacionamentos sugeridos pelas foreign keys

Resposta:"""
        )

    def analyze_business_logic(self, code: str, proc_name: str) -> str:
        """
        Analisa lógica de negócio usando LLM

        Args:
            code: Código-fonte da procedure
            proc_name: Nome da procedure

        Returns:
            Descrição da lógica de negócio

        Raises:
            LLMAnalysisError: Se houver erro na análise
        """
        try:
            # Definir operação para tracking de tokens
            use_toon = getattr(self.config, 'llm_use_toon', False) and TOON_AVAILABLE
            self.token_callback.set_operation("analyze_business_logic", use_toon=use_toon)

            truncated_code = code[:AnalysisConfig.MAX_CODE_LENGTH_BUSINESS_LOGIC]
            chain = self.business_logic_prompt | self.llm
            result = chain.invoke(
                {"code": truncated_code, "proc_name": proc_name},
                config={"callbacks": [self.token_callback]}
            )
            # Se result for um objeto com content, extrair o content
            if hasattr(result, 'content'):
                return result.content.strip()
            return str(result).strip()
        except Exception as e:
            logger.error(f"Erro ao analisar lógica de negócio de {proc_name}: {e}")
            raise LLMAnalysisError(f"Erro ao analisar lógica de negócio: {e}")

    def extract_dependencies(self, code: str) -> Tuple[Set[str], Set[str]]:
        """
        Extrai dependências (procedures e tabelas) usando LLM e regex

        Args:
            code: Código-fonte da procedure

        Returns:
            Tupla (procedures, tables) com sets de dependências
        """
        # Primeiro tenta com regex (mais rápido e confiável)
        procedures = self._extract_procedures_regex(code)
        tables = self._extract_tables_regex(code)

        # Depois complementa com LLM para casos mais complexos
        try:
            # Definir operação para tracking de tokens
            use_toon = getattr(self.config, 'llm_use_toon', False) and TOON_AVAILABLE
            self.token_callback.set_operation("extract_dependencies", use_toon=use_toon)

            truncated_code = code[:AnalysisConfig.MAX_CODE_LENGTH_DEPENDENCIES]
            chain = self.dependencies_prompt | self.llm
            result = chain.invoke(
                {"code": truncated_code},
                config={"callbacks": [self.token_callback]}
            )
            # Se result for um objeto com content, extrair o content
            if hasattr(result, 'content'):
                result = result.content
            else:
                result = str(result)

            # Parse response (TOON ou JSON) com validação
            deps = parse_llm_response(result, use_toon=use_toon)

            if deps:
                # Validação: garantir que é um dict com as chaves esperadas
                if isinstance(deps, dict):
                    if 'procedures' in deps and isinstance(deps['procedures'], list):
                        procedures.update(deps['procedures'])
                    if 'tables' in deps and isinstance(deps['tables'], list):
                        tables.update(deps['tables'])
                else:
                    logger.warning(f"Resposta do LLM não é um dict válido: {type(deps)}, usando apenas regex")
            else:
                logger.warning(f"Não foi possível parsear resposta do LLM (TOON ou JSON), usando apenas regex")
        except Exception as e:
            logger.warning(f"LLM dependency extraction failed: {e}, using regex only")

        return procedures, tables

    def _extract_procedures_regex(self, code: str) -> Set[str]:
        """
        Extrai procedures usando regex

        Args:
            code: Código-fonte da procedure

        Returns:
            Set com nomes de procedures chamadas
        """
        procedures = set()

        # Padrões comuns de chamadas
        patterns = [
            r'(?i)(?:EXECUTE|EXEC|CALL)\s+([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)',
            r'(?i)([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)\s*\(',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, code)
            for match in matches:
                proc = match.group(1).upper()
                # Filtra funções SQL built-in
                if proc not in ['TO_DATE', 'TO_CHAR', 'NVL', 'DECODE', 'COUNT',
                               'SUM', 'MAX', 'MIN', 'AVG', 'SUBSTR', 'TRIM']:
                    procedures.add(proc)

        return procedures

    def _extract_tables_regex(self, code: str) -> Set[str]:
        """
        Extrai tabelas usando regex

        Args:
            code: Código-fonte da procedure

        Returns:
            Set com nomes de tabelas acessadas
        """
        tables = set()

        patterns = [
            r'(?i)FROM\s+([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)',
            r'(?i)INTO\s+([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)',
            r'(?i)UPDATE\s+([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)',
            r'(?i)DELETE\s+FROM\s+([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, code)
            for match in matches:
                table = match.group(1).upper()
                tables.add(table)

        return tables

    def calculate_complexity(self, code: str) -> int:
        """
        Calcula score de complexidade (1-10)

        Args:
            code: Código-fonte da procedure

        Returns:
            Score de complexidade entre 1 e 10
        """
        try:
            # Definir operação para tracking de tokens
            use_toon = getattr(self.config, 'llm_use_toon', False) and TOON_AVAILABLE
            self.token_callback.set_operation("calculate_complexity", use_toon=use_toon)

            truncated_code = code[:AnalysisConfig.MAX_CODE_LENGTH_COMPLEXITY]
            chain = self.complexity_prompt | self.llm
            result = chain.invoke(
                {"code": truncated_code},
                config={"callbacks": [self.token_callback]}
            )
            # Se result for um objeto com content, extrair o content
            if hasattr(result, 'content'):
                result = result.content
            else:
                result = str(result)

            # Extrai número da resposta com validação
            score_match = re.search(r'\b([1-9]|10)\b', result)
            if score_match:
                score = int(score_match.group(1))
                # Validação: garantir que está no range correto
                if 1 <= score <= AnalysisConfig.COMPLEXITY_MAX_SCORE:
                    return score
                else:
                    logger.warning(f"Score fora do range, usando heurística: {score}")
        except Exception as e:
            logger.warning(f"LLM complexity calculation failed: {e}, using heuristic")

        # Fallback: heurística simples
        return self._calculate_complexity_heuristic(code)

    def _calculate_complexity_heuristic(self, code: str) -> int:
        """
        Cálculo heurístico de complexidade

        Args:
            code: Código-fonte da procedure

        Returns:
            Score de complexidade entre 1 e 10
        """
        score = 1

        lines = len(code.split('\n'))
        score += min(lines // AnalysisConfig.COMPLEXITY_LINES_THRESHOLD,
                    AnalysisConfig.COMPLEXITY_LINES_MAX_BONUS)

        score += len(re.findall(r'(?i)\bIF\b', code)) * AnalysisConfig.COMPLEXITY_IF_WEIGHT
        score += len(re.findall(r'(?i)\bLOOP\b', code)) * AnalysisConfig.COMPLEXITY_LOOP_WEIGHT
        score += len(re.findall(r'(?i)\bCURSOR\b', code)) * AnalysisConfig.COMPLEXITY_CURSOR_WEIGHT
        score += len(re.findall(r'(?i)\bEXCEPTION\b', code)) * AnalysisConfig.COMPLEXITY_EXCEPTION_WEIGHT

        return min(int(score), AnalysisConfig.COMPLEXITY_MAX_SCORE)

    def analyze_table_purpose(self, ddl: str, table_name: str, columns: List[str]) -> str:
        """
        Analisa propósito de negócio de uma tabela usando LLM

        Args:
            ddl: DDL completo da tabela
            table_name: Nome da tabela
            columns: Lista de nomes de colunas

        Returns:
            Descrição do propósito de negócio

        Raises:
            LLMAnalysisError: Se houver erro na análise
        """
        try:
            # Definir operação para tracking de tokens
            use_toon = getattr(self.config, 'llm_use_toon', False) and TOON_AVAILABLE
            self.token_callback.set_operation("analyze_table_purpose", use_toon=use_toon)

            # Limita tamanho do DDL para não exceder limites do LLM
            max_ddl_length = 2000
            truncated_ddl = ddl[:max_ddl_length] if len(ddl) > max_ddl_length else ddl
            columns_str = ', '.join(columns[:20])  # Limita a 20 colunas para o prompt

            chain = self.table_purpose_prompt | self.llm
            result = chain.invoke(
                {
                    "ddl": truncated_ddl,
                    "table_name": table_name,
                    "columns": columns_str
                },
                config={"callbacks": [self.token_callback]}
            )
            # Se result for um objeto com content, extrair o content
            if hasattr(result, 'content'):
                return result.content.strip()
            return str(result).strip()
        except Exception as e:
            logger.error(f"Erro ao analisar propósito da tabela {table_name}: {e}")
            raise LLMAnalysisError(f"Erro ao analisar propósito da tabela: {e}")

    def get_token_statistics(self) -> Dict[str, Any]:
        """
        Retorna estatísticas de uso de tokens

        Returns:
            Dict com estatísticas detalhadas de tokens
        """
        return self.token_tracker.get_statistics()


class ProcedureAnalyzer:
    """Orquestra análise completa de procedures"""

    def __init__(self, llm_analyzer: LLMAnalyzer):
        """
        Inicializa o analisador de procedures

        Args:
            llm_analyzer: Instância do LLMAnalyzer para análise com IA
        """
        self.llm = llm_analyzer
        self.procedures: Dict[str, ProcedureInfo] = {}
        self.dependency_graph = nx.DiGraph()

    def analyze_from_files(self, directory_path: str, extension: str = "prc",
                          show_progress: bool = True) -> None:
        """
        Analisa procedures a partir de arquivos .prc

        Args:
            directory_path: Caminho do diretório com arquivos
            extension: Extensão dos arquivos (padrão: "prc")
            show_progress: Mostrar barra de progresso (padrão: True)

        Raises:
            ProcedureLoadError: Se houver erro ao carregar arquivos
        """
        # Carrega procedures dos arquivos
        proc_files = ProcedureLoader.from_files(directory_path, extension)

        logger.info(f"Iniciando análise de {len(proc_files)} procedures...")

        # Usa tqdm para progress bar se solicitado
        iterator = tqdm(proc_files.items(), desc="Analisando procedures",
                       total=len(proc_files), disable=not show_progress) if show_progress else proc_files.items()

        for proc_name, source_code in iterator:
            if show_progress:
                iterator.set_postfix({"current": proc_name[:30]})
            logger.debug(f"Analisando {proc_name}...")

            try:
                proc_info = self._analyze_procedure_from_code(proc_name, source_code)
                self.procedures[proc_name] = proc_info
            except Exception as e:
                logger.error(f"Erro ao analisar {proc_name}: {e}")
                # Continua com outras procedures mesmo se uma falhar

        # Calcula níveis de dependência
        logger.info("Calculando níveis de dependência...")
        self._calculate_dependency_levels()

        logger.info("Análise concluída!")

    def analyze_from_database(
        self,
        user: str,
        password: str,
        dsn: str,
        schema: Optional[str] = None,
        limit: Optional[int] = None,
        show_progress: bool = True,
        db_type: Optional[str] = None,
        database: Optional[str] = None,
        port: Optional[int] = None
    ) -> None:
        """
        Analisa procedures diretamente do banco de dados

        Args:
            user: Usuário do banco de dados
            password: Senha do banco de dados
            dsn: Data Source Name (host:port/service para Oracle, host para outros)
            schema: Schema específico (opcional)
            limit: Limite de procedures para análise (opcional)
            show_progress: Mostrar barra de progresso (padrão: True)
            db_type: Tipo de banco (oracle, postgresql, mssql, mysql).
                    Se None, assume Oracle para backward compatibility

        Raises:
            ProcedureLoadError: Se houver erro ao carregar do banco
        """
        # Carrega procedures do banco usando novo método
        proc_db = ProcedureLoader.from_database(user, password, dsn, schema, db_type, database, port)

        if limit and limit > 0:
            proc_db = dict(list(proc_db.items())[:limit])
            logger.info(f"Limitando análise a {limit} procedures")

        logger.info(f"Iniciando análise de {len(proc_db)} procedures...")

        # Usa tqdm para progress bar se solicitado
        iterator = tqdm(proc_db.items(), desc="Analisando procedures",
                       total=len(proc_db), disable=not show_progress) if show_progress else proc_db.items()

        for proc_name, source_code in iterator:
            if show_progress:
                iterator.set_postfix({"current": proc_name[:30]})
            logger.debug(f"Analisando {proc_name}...")

            try:
                proc_info = self._analyze_procedure_from_code(proc_name, source_code)
                self.procedures[proc_name] = proc_info
            except Exception as e:
                logger.error(f"Erro ao analisar {proc_name}: {e}")
                # Continua com outras procedures mesmo se uma falhar

        # Calcula níveis de dependência
        logger.info("Calculando níveis de dependência...")
        self._calculate_dependency_levels()

        logger.info("Análise concluída!")

    def _analyze_procedure_from_code(self, proc_name: str, source_code: str) -> ProcedureInfo:
        """
        Analisa uma procedure a partir do código-fonte

        Args:
            proc_name: Nome da procedure
            source_code: Código-fonte da procedure

        Returns:
            ProcedureInfo com informações analisadas

        Raises:
            DependencyAnalysisError: Se houver erro na análise de dependências
        """
        # Validação
        if not source_code or not source_code.strip():
            raise ValidationError(f"Código-fonte vazio para procedure {proc_name}")

        # Extrai schema do nome (se houver)
        if '.' in proc_name:
            schema, name = proc_name.split('.', 1)
        else:
            schema = "UNKNOWN"
            name = proc_name

        # Extrai parâmetros do código-fonte
        parameters = self._extract_parameters_from_code(source_code)

        # Análise com LLM
        try:
            business_logic = self.llm.analyze_business_logic(source_code, name)
            procedures, tables = self.llm.extract_dependencies(source_code)
            complexity = self.llm.calculate_complexity(source_code)
        except LLMAnalysisError as e:
            logger.error(f"Erro na análise LLM de {proc_name}: {e}")
            raise DependencyAnalysisError(f"Erro ao analisar dependências de {proc_name}: {e}")

        # Validação: complexity_score deve estar no range 1-10
        if not (1 <= complexity <= AnalysisConfig.COMPLEXITY_MAX_SCORE):
            logger.warning(f"Complexity score inválido para {proc_name}: {complexity}, ajustando para 5")
            complexity = 5

        # Cria grafo de dependências
        self.dependency_graph.add_node(proc_name)

        for dep_proc in procedures:
            self.dependency_graph.add_edge(proc_name, dep_proc)

        return ProcedureInfo(
            name=name,
            schema=schema,
            source_code=source_code,
            parameters=parameters,
            called_procedures=procedures,
            called_tables=tables,
            business_logic=business_logic,
            complexity_score=complexity,
            dependencies_level=0  # Será calculado depois
        )

    def _extract_parameters_from_code(self, code: str) -> List[Dict[str, str]]:
        """
        Extrai parâmetros da assinatura da procedure no código

        Args:
            code: Código-fonte da procedure

        Returns:
            Lista de dicionários com informações dos parâmetros
        """
        params = []

        # Regex para extrair parâmetros da definição
        # Exemplo: (p_id IN NUMBER, p_name OUT VARCHAR2)
        param_pattern = r'(?i)\(\s*([^)]+)\s*\)'
        truncated_code = code[:AnalysisConfig.MAX_CODE_LENGTH_PARAMETERS]
        match = re.search(param_pattern, truncated_code)

        if match:
            param_str = match.group(1)
            # Divide por vírgulas
            param_list = re.split(r',(?![^(]*\))', param_str)

            for idx, param in enumerate(param_list, 1):
                param = param.strip()
                if param:
                    # Tenta extrair: nome, direção (IN/OUT/IN OUT), tipo
                    parts = param.split()
                    if len(parts) >= 2:
                        param_name = parts[0]

                        # Identifica direção
                        direction = "IN"
                        if "OUT" in param.upper():
                            direction = "IN OUT" if "IN" in param.upper() else "OUT"

                        # Tipo é o que sobra
                        param_type = ' '.join(parts[1:]).replace('IN', '').replace('OUT', '').strip()

                        params.append({
                            'name': param_name,
                            'type': param_type,
                            'direction': direction,
                            'position': idx
                        })

        return params

    def _calculate_dependency_levels(self) -> None:
        """
        Calcula níveis hierárquicos de dependência (bottom-up)
        Melhora o tratamento de dependências cíclicas
        """
        if not self.procedures:
            logger.warning("Nenhuma procedure para calcular níveis de dependência")
            return

        # Detecta ciclos antes de tentar ordenação topológica
        cycles = list(nx.simple_cycles(self.dependency_graph))
        if cycles:
            logger.warning(f"Dependências cíclicas detectadas: {len(cycles)} ciclo(s)")
            for cycle in cycles[:5]:  # Mostra apenas os primeiros 5 ciclos
                logger.warning(f"Ciclo detectado: {' -> '.join(cycle)} -> {cycle[0]}")

        try:
            # Tenta ordenação topológica (reversed para bottom-up)
            topo_order = list(reversed(list(nx.topological_sort(self.dependency_graph))))

            levels = {}
            for node in topo_order:
                if node in self.procedures:
                    # Nível = max(níveis das dependências) + 1
                    successors = list(self.dependency_graph.successors(node))
                    if not successors:
                        levels[node] = 0  # Nível base
                    else:
                        max_dep_level = max([levels.get(s, 0) for s in successors
                                            if s in self.procedures], default=-1)
                        levels[node] = max_dep_level + 1

            # Atualiza procedures com níveis
            for proc_name, level in levels.items():
                if proc_name in self.procedures:
                    self.procedures[proc_name].dependencies_level = level

        except nx.NetworkXError as e:
            logger.error(f"Erro ao calcular níveis de dependência: {e}")
            # Em caso de erro, atribui nível 0 a todas
            for proc_name in self.procedures:
                self.procedures[proc_name].dependencies_level = 0
            logger.warning("Níveis de dependência podem estar imprecisos devido a ciclos")

    def get_procedure_hierarchy(self) -> Dict[int, List[str]]:
        """
        Retorna procedures organizadas por nível hierárquico

        Returns:
            Dict com nível como chave e lista de procedures como valor
        """
        hierarchy = defaultdict(list)

        for proc_name, proc_info in self.procedures.items():
            hierarchy[proc_info.dependencies_level].append(proc_name)

        return dict(sorted(hierarchy.items()))

    def export_results(self, output_file: str = "procedure_analysis.json") -> None:
        """
        Exporta resultados para JSON

        Args:
            output_file: Caminho do arquivo de saída

        Raises:
            ExportError: Se houver erro ao exportar
        """
        if not self.procedures:
            raise ExportError("Nenhuma procedure para exportar")

        try:
            # Coletar estatísticas de tokens
            token_stats = None
            token_metrics_list = None
            if hasattr(self.llm, 'get_token_statistics'):
                token_stats = self.llm.get_token_statistics()
            if hasattr(self.llm, 'token_tracker'):
                token_metrics_list = [
                    {
                        'request_id': m.request_id,
                        'operation': m.operation,
                        'tokens_in': m.tokens_in,
                        'tokens_out': m.tokens_out,
                        'tokens_total': m.tokens_total,
                        'timestamp': m.timestamp.isoformat(),
                        'use_toon': m.use_toon
                    }
                    for m in self.llm.token_tracker.get_all_metrics()
                ]

            results = {
                'procedures': {
                    name: {
                        **asdict(info),
                        'called_procedures': list(info.called_procedures),
                        'called_tables': list(info.called_tables)
                    }
                    for name, info in self.procedures.items()
                },
                'hierarchy': self.get_procedure_hierarchy(),
                'statistics': {
                    'total_procedures': len(self.procedures),
                    'avg_complexity': sum(p.complexity_score for p in self.procedures.values()) / len(self.procedures) if self.procedures else 0,
                    'max_dependency_level': max(p.dependencies_level for p in self.procedures.values()) if self.procedures else 0
                }
            }

            # Adicionar métricas de tokens se disponíveis
            if token_stats or token_metrics_list:
                results['token_metrics'] = {}
                if token_stats:
                    results['token_metrics']['statistics'] = token_stats
                if token_metrics_list:
                    results['token_metrics']['detailed'] = token_metrics_list

                # Adicionar comparação TOON se disponível
                if hasattr(self.llm, 'token_tracker'):
                    toon_comparison = self.llm.token_tracker.get_toon_comparison()
                    if toon_comparison:
                        # Converter para formato serializável
                        serializable_comparison = {}
                        for key, value in toon_comparison.items():
                            if isinstance(value, dict):
                                serializable_comparison[key] = {
                                    k: v.isoformat() if hasattr(v, 'isoformat') else v
                                    for k, v in value.items()
                                }
                            else:
                                serializable_comparison[key] = value
                        results['token_metrics']['toon_comparison'] = serializable_comparison

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            logger.info(f"Resultados exportados para {output_file}")
        except Exception as e:
            logger.error(f"Erro ao exportar resultados: {e}")
            raise ExportError(f"Erro ao exportar resultados para {output_file}: {e}")

    def visualize_dependencies(self, output_file: str = "dependency_graph.png") -> None:
        """
        Visualiza grafo de dependências

        Args:
            output_file: Caminho do arquivo de saída

        Raises:
            ExportError: Se houver erro ao exportar
        """
        if not self.dependency_graph.nodes():
            raise ExportError("Grafo de dependências vazio")

        try:
            plt.figure(figsize=AnalysisConfig.GRAPH_FIGSIZE)

            # Layout hierárquico
            pos = nx.spring_layout(self.dependency_graph, k=2, iterations=50)

            # Cores por nível
            colors = []
            for node in self.dependency_graph.nodes():
                if node in self.procedures:
                    level = self.procedures[node].dependencies_level
                    colors.append(level)
                else:
                    colors.append(-1)

            nx.draw(
                self.dependency_graph,
                pos,
                node_color=colors,
                node_size=AnalysisConfig.GRAPH_NODE_SIZE,
                cmap=plt.cm.viridis,
                with_labels=True,
                font_size=AnalysisConfig.GRAPH_FONT_SIZE,
                arrows=True,
                edge_color='gray',
                alpha=0.7
            )

            plt.title("Grafo de Dependências de Procedures", fontsize=16)
            plt.savefig(output_file, dpi=AnalysisConfig.GRAPH_DPI, bbox_inches='tight')
            plt.close()  # Fecha a figura para liberar memória

            logger.info(f"Grafo exportado para {output_file}")
        except Exception as e:
            logger.error(f"Erro ao exportar grafo: {e}")
            raise ExportError(f"Erro ao exportar grafo para {output_file}: {e}")

    def export_mermaid_diagram(self, output_file: str = "diagram.md", max_nodes: int = 50) -> None:
        """
        Exporta diagrama Mermaid de dependências

        Args:
            output_file: Caminho do arquivo de saída
            max_nodes: Número máximo de nós no diagrama (para evitar sobrecarga)

        Raises:
            ExportError: Se houver erro ao exportar
        """
        if not self.dependency_graph.nodes():
            raise ExportError("Grafo de dependências vazio")

        try:
            nodes = list(self.dependency_graph.nodes())[:max_nodes]

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("```mermaid\ngraph TD\n")

                # Adiciona nós com cores por complexidade
                for node in nodes:
                    if node in self.procedures:
                        info = self.procedures[node]
                        complexity_class = "high" if info.complexity_score >= 8 else \
                                         "medium" if info.complexity_score >= 5 else "low"
                        label = f"{node}\\n[Nível {info.dependencies_level}, Complex: {info.complexity_score}]"
                        f.write(f'    {node.replace(".", "_").replace("-", "_")}["{label}"]:::{complexity_class}\n')

                # Adiciona arestas
                for edge in self.dependency_graph.edges():
                    if edge[0] in nodes and edge[1] in nodes:
                        source = edge[0].replace(".", "_").replace("-", "_")
                        target = edge[1].replace(".", "_").replace("-", "_")
                        f.write(f"    {source} --> {target}\n")

                # Define classes de estilo
                f.write("""
    classDef high fill:#ff6b6b,stroke:#c92a2a,color:#fff
    classDef medium fill:#ffd93d,stroke:#f59f00,color:#000
    classDef low fill:#51cf66,stroke:#2b8a3e,color:#000
```\n""")

            logger.info(f"Diagrama Mermaid exportado para {output_file}")
        except Exception as e:
            logger.error(f"Erro ao exportar diagrama Mermaid: {e}")
            raise ExportError(f"Erro ao exportar diagrama Mermaid: {e}")

    def export_mermaid_hierarchy(self, output_file: str = "hierarchy.md") -> None:
        """
        Exporta hierarquia Mermaid organizada por níveis

        Args:
            output_file: Caminho do arquivo de saída

        Raises:
            ExportError: Se houver erro ao exportar
        """
        if not self.procedures:
            raise ExportError("Nenhuma procedure para exportar")

        try:
            hierarchy = self.get_procedure_hierarchy()

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("```mermaid\ngraph TD\n")

                # Organiza por níveis
                for level in sorted(hierarchy.keys()):
                    level_procs = hierarchy[level]
                    for proc in level_procs:
                        if proc in self.procedures:
                            info = self.procedures[proc]
                            complexity_class = "high" if info.complexity_score >= 8 else \
                                             "medium" if info.complexity_score >= 5 else "low"
                            label = f"{proc}\\n[Nível {level}, Complex: {info.complexity_score}]"
                            proc_id = proc.replace(".", "_").replace("-", "_")
                            f.write(f'    {proc_id}["{label}"]:::{complexity_class}\n')

                            # Adiciona arestas para dependências
                            for dep in info.called_procedures:
                                if dep in self.procedures:
                                    dep_id = dep.replace(".", "_").replace("-", "_")
                                    f.write(f"    {proc_id} --> {dep_id}\n")

                # Define classes de estilo
                f.write("""
    classDef high fill:#ff6b6b,stroke:#c92a2a,color:#fff
    classDef medium fill:#ffd93d,stroke:#f59f00,color:#000
    classDef low fill:#51cf66,stroke:#2b8a3e,color:#000
```\n""")

            logger.info(f"Hierarquia Mermaid exportada para {output_file}")
        except Exception as e:
            logger.error(f"Erro ao exportar hierarquia Mermaid: {e}")
            raise ExportError(f"Erro ao exportar hierarquia Mermaid: {e}")

    def export_mermaid_flowchart(self, proc_name: str, output_file: Optional[str] = None) -> None:
        """
        Exporta flowchart Mermaid detalhado de uma procedure específica

        Args:
            proc_name: Nome da procedure
            output_file: Caminho do arquivo de saída (opcional, usa nome da procedure se não fornecido)

        Raises:
            ExportError: Se a procedure não for encontrada ou houver erro ao exportar
        """
        if proc_name not in self.procedures:
            raise ExportError(f"Procedure {proc_name} não encontrada")

        if output_file is None:
            safe_name = proc_name.replace(".", "_").replace("-", "_")
            output_file = f"{safe_name}_flowchart.md"

        try:
            info = self.procedures[proc_name]

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# Flowchart: {proc_name}\n\n")
                f.write(f"**Complexidade:** {info.complexity_score}/10\n")
                f.write(f"**Nível de Dependência:** {info.dependencies_level}\n\n")
                f.write("```mermaid\nflowchart TD\n")
                f.write(f'    Start([Início: {proc_name}])\n')

                # Parâmetros
                if info.parameters:
                    f.write(f'    Params[Parâmetros: {len(info.parameters)}]\n')
                    f.write("    Start --> Params\n")
                    for param in info.parameters:
                        f.write(f'    Params --> P{param["position"]}["{param["name"]}: {param["type"]} ({param["direction"]})"]\n')

                # Procedures chamadas
                if info.called_procedures:
                    f.write('    Procs[Procedures Chamadas]\n')
                    f.write("    Start --> Procs\n")
                    for dep_proc in info.called_procedures:
                        f.write(f'    Procs --> Proc_{dep_proc.replace(".", "_").replace("-", "_")}["{dep_proc}"]\n')

                # Tabelas acessadas
                if info.called_tables:
                    f.write('    Tables[Tabelas Acessadas]\n')
                    f.write("    Start --> Tables\n")
                    for table in info.called_tables:
                        f.write(f'    Tables --> Table_{table.replace(".", "_").replace("-", "_")}["{table}"]\n')

                f.write(f'    End([Fim])\n')
                f.write("    Start --> End\n")
                f.write("```\n\n")
                f.write(f"## Lógica de Negócio\n\n{info.business_logic}\n")

            logger.info(f"Flowchart Mermaid exportado para {output_file}")
        except Exception as e:
            logger.error(f"Erro ao exportar flowchart Mermaid: {e}")
            raise ExportError(f"Erro ao exportar flowchart Mermaid: {e}")


# ============= EXEMPLOS DE USO =============

if __name__ == "__main__":
    # Configurar logging básico
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # ===== OPÇÃO 1: ANÁLISE A PARTIR DE ARQUIVOS .prc (RECOMENDADO) =====
    print("=" * 60)
    print("ANÁLISE DE PROCEDURES A PARTIR DE ARQUIVOS .prc")
    print("=" * 60)

    # Inicializa apenas o analisador LLM
    llm = LLMAnalyzer(
        model_name="gpt-oss-120b",  # ou caminho local: "/path/to/model"
        device="cuda"
    )

    # Cria analisador
    analyzer = ProcedureAnalyzer(llm)

    # Analisa procedures dos arquivos
    analyzer.analyze_from_files(
        directory_path="./procedures",  # Diretório com arquivos .prc
        extension="prc"
    )

    # Visualiza resultados
    hierarchy = analyzer.get_procedure_hierarchy()
    print("\n" + "=" * 60)
    print("HIERARQUIA DE PROCEDURES (Bottom-Up)")
    print("=" * 60)
    for level in sorted(hierarchy.keys()):
        print(f"\n📊 Nível {level} - {len(hierarchy[level])} procedures:")
        for proc in hierarchy[level]:
            info = analyzer.procedures[proc]
            print(f"\n  🔹 {proc}")
            print(f"     Complexidade: {info.complexity_score}/10")
            print(f"     Dependências: {len(info.called_procedures)} procedures, {len(info.called_tables)} tabelas")
            print(f"     Lógica: {info.business_logic[:150]}...")

    # Exporta resultados
    analyzer.export_results("procedures_analysis.json")
    analyzer.visualize_dependencies("dependencies_graph.png")
    analyzer.export_mermaid_diagram("diagram.md")
    analyzer.export_mermaid_hierarchy("hierarchy.md")

    print("\n" + "=" * 60)
    print("✅ Análise concluída! Arquivos gerados:")
    print("   - procedures_analysis.json")
    print("   - dependencies_graph.png")
    print("   - diagram.md")
    print("   - hierarchy.md")
    print("=" * 60)
