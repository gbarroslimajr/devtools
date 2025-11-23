"""
Analisador de Procedures Oracle usando LangChain e LLM Local
Extrai, analisa e mapeia relacionamentos entre procedures do Oracle
"""

import re
import json
import logging
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict
from pathlib import Path

import oracledb
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_community.llms import HuggingFacePipeline
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import networkx as nx
import matplotlib.pyplot as plt
from tqdm import tqdm

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


# Exceções customizadas
class CodeGraphAIError(Exception):
    """Exceção base para erros do CodeGraphAI"""
    pass


class ProcedureLoadError(CodeGraphAIError):
    """Erro ao carregar procedures"""
    pass


class LLMAnalysisError(CodeGraphAIError):
    """Erro na análise com LLM"""
    pass


class DependencyAnalysisError(CodeGraphAIError):
    """Erro na análise de dependências"""
    pass


class ExportError(CodeGraphAIError):
    """Erro na exportação de resultados"""
    pass


class ValidationError(CodeGraphAIError):
    """Erro de validação"""
    pass


@dataclass
class ProcedureInfo:
    """Informações sobre uma procedure"""
    name: str
    schema: str
    source_code: str
    parameters: List[Dict[str, str]]
    called_procedures: Set[str]
    called_tables: Set[str]
    business_logic: str
    complexity_score: int
    dependencies_level: int


class ProcedureLoader:
    """Carrega procedures de diferentes fontes"""

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
        from pathlib import Path

        # Validação
        if not extension or not extension.strip():
            raise ValidationError("Extensão de arquivo não pode ser vazia")

        proc_dir = Path(directory_path)
        if not proc_dir.exists():
            raise ProcedureLoadError(f"Diretório não encontrado: {directory_path}")

        if not proc_dir.is_dir():
            raise ProcedureLoadError(f"Caminho não é um diretório: {directory_path}")

        procedures = {}

        # Busca todos os arquivos com a extensão especificada
        for file_path in proc_dir.rglob(f"*.{extension}"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()

                # Validação: arquivo não pode estar vazio
                if not content:
                    logger.warning(f"Arquivo vazio ignorado: {file_path.name}")
                    continue

                # Usa nome do arquivo sem extensão como identificador
                proc_name = file_path.stem.upper()
                procedures[proc_name] = content

                logger.info(f"Carregado: {file_path.name}")
            except UnicodeDecodeError as e:
                logger.error(f"Erro de codificação ao ler {file_path}: {e}")
                raise ProcedureLoadError(f"Erro ao decodificar arquivo {file_path}: {e}")
            except Exception as e:
                logger.error(f"Erro ao ler {file_path}: {e}")
                raise ProcedureLoadError(f"Erro ao ler arquivo {file_path}: {e}")

        if not procedures:
            raise ProcedureLoadError(f"Nenhum arquivo .{extension} encontrado em {directory_path}")

        logger.info(f"Total de {len(procedures)} procedures carregadas de {directory_path}")
        return procedures

    @staticmethod
    def from_database(user: str, password: str, dsn: str, schema: Optional[str] = None) -> Dict[str, str]:
        """
        Carrega procedures diretamente do banco Oracle

        Args:
            user: Usuário do banco de dados
            password: Senha do banco de dados
            dsn: Data Source Name (host:port/service)
            schema: Schema específico (opcional)

        Returns:
            Dict com schema.nome como chave e código-fonte como valor

        Raises:
            ProcedureLoadError: Se houver erro de conexão ou consulta
            ValidationError: Se credenciais estiverem vazias
        """
        # Validação
        if not user or not user.strip():
            raise ValidationError("Usuário do banco não pode ser vazio")
        if not password or not password.strip():
            raise ValidationError("Senha do banco não pode ser vazia")
        if not dsn or not dsn.strip():
            raise ValidationError("DSN não pode ser vazio")

        try:
            connection = oracledb.connect(user=user, password=password, dsn=dsn)
            cursor = connection.cursor()

            # Lista procedures
            query = "SELECT OWNER, OBJECT_NAME FROM ALL_PROCEDURES WHERE OBJECT_TYPE = 'PROCEDURE'"
            if schema:
                # Previne SQL injection usando bind variables
                query += " AND OWNER = :schema"
                cursor.execute(query, schema=schema)
            else:
                cursor.execute(query)

            proc_list = cursor.fetchall()

            procedures = {}
            for owner, proc_name in proc_list:
                try:
                    # Busca código fonte
                    cursor.execute("""
                        SELECT TEXT FROM ALL_SOURCE
                        WHERE OWNER = :owner AND NAME = :name
                        ORDER BY LINE
                    """, owner=owner, name=proc_name)

                    lines = cursor.fetchall()
                    source = ''.join([line[0] for line in lines])

                    # Validação: código não pode estar vazio
                    if not source.strip():
                        logger.warning(f"Procedure vazia ignorada: {owner}.{proc_name}")
                        continue

                    full_name = f"{owner}.{proc_name}"
                    procedures[full_name] = source
                    logger.info(f"Carregado: {full_name}")
                except Exception as e:
                    logger.error(f"Erro ao carregar {owner}.{proc_name}: {e}")
                    # Continua com outras procedures mesmo se uma falhar

            connection.close()

            if not procedures:
                raise ProcedureLoadError("Nenhuma procedure encontrada no banco de dados")

            logger.info(f"Total de {len(procedures)} procedures carregadas do banco")
            return procedures

        except oracledb.Error as e:
            logger.error(f"Erro de conexão Oracle: {e}")
            raise ProcedureLoadError(f"Erro ao conectar ao banco Oracle: {e}")
        except Exception as e:
            logger.error(f"Erro inesperado ao carregar procedures do banco: {e}")
            raise ProcedureLoadError(f"Erro ao carregar procedures do banco: {e}")


class LLMAnalyzer:
    """Analisa procedures usando LLM local"""

    def __init__(self, model_name: str = "gpt-oss-120b", device: str = "cuda"):
        """
        Inicializa o modelo LLM local

        Args:
            model_name: Nome ou caminho do modelo HuggingFace
            device: Dispositivo para execução ("cuda" ou "cpu")

        Raises:
            LLMAnalysisError: Se houver erro ao carregar o modelo
        """
        logger.info(f"Carregando modelo {model_name}...")

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

            # Templates de prompts
            self._setup_prompts()
            logger.info("Modelo LLM carregado com sucesso")

        except Exception as e:
            logger.error(f"Erro ao carregar modelo LLM: {e}")
            raise LLMAnalysisError(f"Erro ao carregar modelo {model_name}: {e}")

    def _setup_prompts(self) -> None:
        """Configura templates de prompts para análise"""

        # Análise de lógica de negócio
        self.business_logic_prompt = PromptTemplate(
            input_variables=["code", "proc_name"],
            template="""Analise a seguinte procedure Oracle e descreva sua lógica de negócio em português de forma concisa:

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
        self.dependencies_prompt = PromptTemplate(
            input_variables=["code"],
            template="""Analise o código Oracle abaixo e identifique:

1. Todas as procedures/functions chamadas (formato: schema.procedure ou apenas procedure)
2. Todas as tabelas acessadas (SELECT, INSERT, UPDATE, DELETE)

Código:
{code}

Retorne no formato JSON:
{{
    "procedures": ["proc1", "schema.proc2", ...],
    "tables": ["table1", "schema.table2", ...]
}}

JSON:"""
        )

        # Avaliação de complexidade
        self.complexity_prompt = PromptTemplate(
            input_variables=["code"],
            template="""Avalie a complexidade da seguinte procedure Oracle em uma escala de 1 a 10, considerando:
- Número de linhas
- Estruturas de controle (IFs, LOOPs)
- Número de tabelas/procedures utilizadas
- Lógica de negócio

Código:
{code}

Retorne apenas um número de 1 a 10:"""
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
            chain = LLMChain(llm=self.llm, prompt=self.business_logic_prompt)
            truncated_code = code[:AnalysisConfig.MAX_CODE_LENGTH_BUSINESS_LOGIC]
            result = chain.run(code=truncated_code, proc_name=proc_name)
            return result.strip()
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
            chain = LLMChain(llm=self.llm, prompt=self.dependencies_prompt)
            truncated_code = code[:AnalysisConfig.MAX_CODE_LENGTH_DEPENDENCIES]
            result = chain.run(code=truncated_code)

            # Parse JSON response com validação
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                try:
                    deps = json.loads(json_match.group())
                    # Validação: garantir que é um dict com as chaves esperadas
                    if isinstance(deps, dict):
                        if 'procedures' in deps and isinstance(deps['procedures'], list):
                            procedures.update(deps['procedures'])
                        if 'tables' in deps and isinstance(deps['tables'], list):
                            tables.update(deps['tables'])
                except json.JSONDecodeError as e:
                    logger.warning(f"Erro ao parsear JSON do LLM: {e}, usando apenas regex")
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
            chain = LLMChain(llm=self.llm, prompt=self.complexity_prompt)
            truncated_code = code[:AnalysisConfig.MAX_CODE_LENGTH_COMPLEXITY]
            result = chain.run(code=truncated_code)

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

    def analyze_from_database(self, user: str, password: str, dsn: str,
                              schema: Optional[str] = None, limit: Optional[int] = None,
                              show_progress: bool = True) -> None:
        """
        Analisa procedures diretamente do banco de dados

        Args:
            user: Usuário do banco de dados
            password: Senha do banco de dados
            dsn: Data Source Name
            schema: Schema específico (opcional)
            limit: Limite de procedures para análise (opcional)
            show_progress: Mostrar barra de progresso (padrão: True)

        Raises:
            ProcedureLoadError: Se houver erro ao carregar do banco
        """
        # Carrega procedures do banco
        proc_db = ProcedureLoader.from_database(user, password, dsn, schema)

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
