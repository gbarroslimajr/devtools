"""
Dry-run mode para validação e simulação de execuções.

Este módulo fornece funcionalidades para validar configurações
e simular operações sem executar conexões reais de banco ou chamadas LLM.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

from app.core.models import DatabaseConfig, DatabaseType, ValidationError
from app.config.config import Config

logger = logging.getLogger(__name__)


@dataclass
class DryRunResult:
    """Resultado de uma validação dry-run"""
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)
    estimated_operations: Dict[str, Any] = field(default_factory=dict)

    def add_error(self, message: str) -> None:
        """Adiciona erro ao resultado"""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        """Adiciona warning ao resultado"""
        self.warnings.append(message)

    def add_info(self, message: str) -> None:
        """Adiciona informação ao resultado"""
        self.info.append(message)


class DryRunValidator:
    """Validador para modo dry-run"""

    def __init__(self, config: Optional[Config] = None):
        """
        Inicializa o validador

        Args:
            config: Configuração do CodeGraphAI (opcional)
        """
        if config is None:
            from config import get_config
            config = get_config()
        self.config = config

    def validate_database_config(
            self,
            db_type: str,
            user: str,
            password: str,
            host: str,
            port: Optional[int] = None,
            database: Optional[str] = None,
            schema: Optional[str] = None
    ) -> DryRunResult:
        """
        Valida configuração de banco de dados sem conectar

        Args:
            db_type: Tipo de banco (oracle, postgresql, mssql, mysql)
            user: Usuário
            password: Senha
            host: Host
            port: Porta
            database: Nome do banco
            schema: Schema

        Returns:
            DryRunResult com resultado da validação
        """
        result = DryRunResult(is_valid=True)

        # Valida tipo de banco
        try:
            db_type_enum = DatabaseType(db_type.lower())
        except ValueError:
            result.add_error(f"Tipo de banco inválido: {db_type}")
            return result

        # Valida parâmetros obrigatórios
        if not user or not user.strip():
            result.add_error("Usuário do banco não pode ser vazio")

        if not password or not password.strip():
            result.add_error("Senha do banco não pode ser vazia")

        if not host or not host.strip():
            result.add_error("Host do banco não pode ser vazio")

        # Validações específicas por tipo de banco
        if db_type_enum != DatabaseType.ORACLE:
            if not database:
                result.add_error(f"Database é obrigatório para {db_type}")
            else:
                result.add_info(f"Database: {database}")

        # Valida porta
        if port is not None:
            if port < 1 or port > 65535:
                result.add_error(f"Porta inválida: {port} (deve estar entre 1 e 65535)")
            else:
                result.add_info(f"Porta: {port}")
        else:
            # Porta padrão por tipo
            default_ports = {
                DatabaseType.ORACLE: 1521,
                DatabaseType.POSTGRESQL: 5432,
                DatabaseType.MSSQL: 1433,
                DatabaseType.MYSQL: 3306
            }
            default_port = default_ports.get(db_type_enum)
            if default_port:
                result.add_info(f"Porta padrão será usada: {default_port}")

        # Valida schema
        if schema:
            result.add_info(f"Schema: {schema}")

        # Simula criação de DatabaseConfig
        if result.is_valid:
            try:
                db_config = DatabaseConfig(
                    db_type=db_type_enum,
                    user=user,
                    password="***" if password else "",  # Não expor senha
                    host=host,
                    port=port,
                    database=database,
                    schema=schema
                )
                result.add_info(f"Configuração de banco válida: {db_type} em {host}")
                result.estimated_operations["connection_string"] = db_config.get_connection_string()
            except ValidationError as e:
                result.add_error(f"Erro ao criar DatabaseConfig: {e}")

        return result

    def validate_llm_config(
            self,
            llm_mode: Optional[str] = None,
            llm_provider: Optional[str] = None,
            model_name: Optional[str] = None,
            device: Optional[str] = None
    ) -> DryRunResult:
        """
        Valida configuração de LLM sem inicializar modelo

        Args:
            llm_mode: Modo LLM (local ou api)
            llm_provider: Provider API (se modo api)
            model_name: Nome do modelo (se modo local)
            device: Dispositivo (se modo local)

        Returns:
            DryRunResult com resultado da validação
        """
        result = DryRunResult(is_valid=True)

        # Usa valores do config se não fornecidos
        mode = llm_mode or self.config.llm_mode
        provider = llm_provider or self.config.llm_provider
        model = model_name or self.config.model_name
        dev = device or self.config.device

        # Valida modo
        if mode not in ['local', 'api']:
            result.add_error(f"Modo LLM inválido: {mode} (deve ser 'local' ou 'api')")
            return result

        result.add_info(f"Modo LLM: {mode}")

        if mode == 'api':
            # Valida provider
            valid_providers = ['genfactory_llama70b', 'genfactory_codestral',
                               'genfactory_gptoss120b', 'openai', 'anthropic']
            if provider not in valid_providers:
                result.add_error(f"Provider inválido: {provider}")
                result.add_info(f"Providers válidos: {', '.join(valid_providers)}")
            else:
                result.add_info(f"Provider: {provider}")

                # Valida configuração específica do provider
                if provider == 'openai':
                    if not self.config.openai or not self.config.openai.get('api_key'):
                        result.add_warning("OpenAI API key não configurada")
                    else:
                        result.add_info(f"Modelo OpenAI: {self.config.openai.get('model', 'N/A')}")

                elif provider == 'anthropic':
                    if not self.config.anthropic or not self.config.anthropic.get('api_key'):
                        result.add_warning("Anthropic API key não configurada")
                    else:
                        result.add_info(f"Modelo Anthropic: {self.config.anthropic.get('model', 'N/A')}")

                elif provider.startswith('genfactory_'):
                    genfactory_config = getattr(self.config, provider, None)
                    if not genfactory_config or not genfactory_config.get('authorization_token'):
                        result.add_warning(f"GenFactory {provider} token não configurado")
                    else:
                        result.add_info(f"Modelo GenFactory: {genfactory_config.get('model', 'N/A')}")

        else:  # modo local
            if not model:
                result.add_error("Nome do modelo é obrigatório no modo local")
            else:
                result.add_info(f"Modelo local: {model}")

            if dev not in ['cuda', 'cpu']:
                result.add_warning(f"Dispositivo '{dev}' pode não ser suportado")
            else:
                result.add_info(f"Dispositivo: {dev}")

        return result

    def validate_analysis_params(
            self,
            analysis_type: str,
            limit: Optional[int] = None,
            output_dir: Optional[str] = None
    ) -> DryRunResult:
        """
        Valida parâmetros de análise

        Args:
            analysis_type: Tipo de análise (tables, procedures, both)
            limit: Limite de entidades
            output_dir: Diretório de saída

        Returns:
            DryRunResult com resultado da validação
        """
        result = DryRunResult(is_valid=True)

        # Valida tipo de análise
        if analysis_type not in ['tables', 'procedures', 'both']:
            result.add_error(f"Tipo de análise inválido: {analysis_type}")
            return result

        result.add_info(f"Tipo de análise: {analysis_type}")

        # Valida limit
        if limit is not None:
            if limit < 1:
                result.add_error(f"Limit deve ser maior que 0, recebido: {limit}")
            else:
                result.add_info(f"Limit: {limit} entidades")
                result.estimated_operations["limit"] = limit

        # Valida output_dir
        if output_dir:
            output_path = Path(output_dir)
            try:
                # Tenta criar diretório (não cria, apenas valida)
                if not output_path.exists():
                    result.add_info(f"Diretório de saída será criado: {output_path}")
                else:
                    result.add_info(f"Diretório de saída: {output_path}")

                # Verifica permissões
                if output_path.exists() and not output_path.is_dir():
                    result.add_error(f"Caminho de saída não é um diretório: {output_path}")
                elif output_path.exists():
                    # Verifica se é gravável
                    test_file = output_path / '.codegraphai_test'
                    try:
                        test_file.touch()
                        test_file.unlink()
                        result.add_info("Diretório de saída é gravável")
                    except PermissionError:
                        result.add_error(f"Sem permissão de escrita em: {output_path}")
            except Exception as e:
                result.add_error(f"Erro ao validar diretório de saída: {e}")
        else:
            default_output = Path(self.config.output_dir)
            result.add_info(f"Usando diretório padrão: {default_output}")

        return result

    def validate_full_analysis(
            self,
            analysis_type: str,
            db_type: str,
            user: str,
            password: str,
            host: str,
            port: Optional[int] = None,
            database: Optional[str] = None,
            schema: Optional[str] = None,
            limit: Optional[int] = None,
            output_dir: Optional[str] = None,
            llm_mode: Optional[str] = None,
            llm_provider: Optional[str] = None
    ) -> DryRunResult:
        """
        Validação completa de uma análise (banco + LLM + parâmetros)

        Returns:
            DryRunResult consolidado
        """
        result = DryRunResult(is_valid=True)

        # Valida banco
        db_result = self.validate_database_config(
            db_type, user, password, host, port, database, schema
        )
        result.errors.extend(db_result.errors)
        result.warnings.extend(db_result.warnings)
        result.info.extend(db_result.info)
        result.estimated_operations.update(db_result.estimated_operations)

        # Valida LLM
        llm_result = self.validate_llm_config(llm_mode, llm_provider)
        result.errors.extend(llm_result.errors)
        result.warnings.extend(llm_result.warnings)
        result.info.extend(llm_result.info)

        # Valida parâmetros
        params_result = self.validate_analysis_params(analysis_type, limit, output_dir)
        result.errors.extend(params_result.errors)
        result.warnings.extend(params_result.warnings)
        result.info.extend(params_result.info)
        result.estimated_operations.update(params_result.estimated_operations)

        # Determina validade final
        result.is_valid = len(result.errors) == 0

        return result
