"""
CLI para CodeGraphAI usando Click
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime
from contextlib import contextmanager

import click
from tqdm import tqdm

from analyzer import LLMAnalyzer, ProcedureAnalyzer
from table_analyzer import TableAnalyzer
from app.core.models import CodeGraphAIError, DatabaseConfig, DatabaseType
from app.core.dry_mode import DryRunValidator, DryRunResult
from app.io.factory import create_loader
from config import get_config


class TeeFileHandler(logging.Handler):
    """Handler que escreve em arquivo e também em stdout simultaneamente"""

    def __init__(self, file_path: Path):
        super().__init__()
        self.file_path = file_path
        self.file = None
        self.stdout = sys.stdout
        # Abre arquivo imediatamente
        try:
            self.file = open(self.file_path, 'a', encoding='utf-8')
        except Exception as e:
            # Se não conseguir abrir, continua sem arquivo
            logging.getLogger(__name__).warning(f"Erro ao abrir arquivo de log: {e}")
            self.file = None

    def close(self):
        """Fecha o arquivo quando handler é fechado"""
        if self.file:
            try:
                self.file.close()
            except Exception:
                pass
            self.file = None
        super().close()

    def emit(self, record):
        """Escreve log em arquivo e stdout"""
        try:
            msg = self.format(record) + '\n'
            if self.file:
                try:
                    self.file.write(msg)
                    self.file.flush()
                except Exception:
                    # Se falhar ao escrever no arquivo, continua apenas com stdout
                    pass
            self.stdout.write(msg)
            self.stdout.flush()
        except Exception:
            self.handleError(record)


def generate_log_filename(command_name: str, log_dir: Path) -> Path:
    """
    Gera nome de arquivo de log com timestamp e comando

    Args:
        command_name: Nome do comando executado
        log_dir: Diretório onde salvar o log

    Returns:
        Path completo do arquivo de log
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Normaliza nome do comando (remove hífens, substitui por underscore)
    safe_command = command_name.replace('-', '_')
    filename = f"{safe_command}_{timestamp}.log"
    return log_dir / filename


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    auto_log: bool = False,
    command_name: Optional[str] = None,
    log_dir: Optional[str] = None
) -> Optional[Path]:
    """
    Configura logging com suporte a auto-logging

    Args:
        log_level: Nível de logging (DEBUG, INFO, WARNING, ERROR)
        log_file: Arquivo de log (opcional, sobrescreve auto-logging)
        auto_log: Se True, cria arquivo de log automaticamente
        command_name: Nome do comando (para auto-logging)
        log_dir: Diretório para logs (para auto-logging)

    Returns:
        Path do arquivo de log criado (se houver), None caso contrário
    """
    handlers = []
    log_file_path = None

    # Determina arquivo de log
    if log_file:
        # Usuário forneceu arquivo explicitamente
        log_file_path = Path(log_file)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
    elif auto_log and command_name and log_dir:
        # Auto-logging habilitado
        try:
            log_dir_path = Path(log_dir)
            log_dir_path.mkdir(parents=True, exist_ok=True)
            log_file_path = generate_log_filename(command_name, log_dir_path)
            logging.getLogger(__name__).info(f"Log será salvo em: {log_file_path}")
        except Exception as e:
            logging.getLogger(__name__).warning(f"Erro ao criar arquivo de log automático: {e}")
            log_file_path = None

    # Configura handlers
    if log_file_path:
        # Usa TeeFileHandler para escrever em arquivo e stdout
        try:
            tee_handler = TeeFileHandler(log_file_path)
            handlers.append(tee_handler)
        except Exception as e:
            # Se falhar, usa apenas console
            logging.getLogger(__name__).warning(f"Erro ao criar handler de arquivo: {e}, usando apenas console")
            handlers.append(logging.StreamHandler(sys.stdout))
    else:
        # Apenas console
        handlers.append(logging.StreamHandler(sys.stdout))

    # Configura logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers,
        force=True  # Força reconfiguração se já foi configurado
    )

    return log_file_path


def echo_with_log(message: str, **kwargs):
    """
    Wrapper para click.echo que também escreve no log

    Args:
        message: Mensagem a exibir
        **kwargs: Argumentos adicionais para click.echo
    """
    click.echo(message, **kwargs)
    # Também loga a mensagem (sem emojis para logs mais limpos)
    logger = logging.getLogger(__name__)
    # Remove emojis e caracteres especiais para log mais limpo
    clean_message = message
    # Loga como INFO se não for erro
    if kwargs.get('err', False):
        logger.error(clean_message)
    else:
        logger.info(clean_message)


@click.group(invoke_without_command=True)
@click.option('--verbose', '-v', is_flag=True, help='Modo verbose (DEBUG)')
@click.option('--log-file', type=click.Path(), help='Arquivo de log (sobrescreve auto-logging)')
@click.option('--no-auto-log', is_flag=True, default=False, help='Desabilita criação automática de logs')
@click.pass_context
def cli(ctx, verbose, log_file, no_auto_log):
    """CodeGraphAI - Análise inteligente de procedures de banco de dados"""
    ctx.ensure_object(dict)
    config = get_config()
    ctx.obj['config'] = config

    # Detecta comando sendo executado
    command_name = None
    if ctx.invoked_subcommand:
        command_name = ctx.invoked_subcommand
    else:
        # Se não há subcomando, usa 'cli' como nome
        command_name = 'cli'

    # Determina se deve usar auto-logging
    use_auto_log = False
    if not log_file and not no_auto_log and config.auto_log_enabled:
        use_auto_log = True

    # Configura logging
    log_level = "DEBUG" if verbose else config.log_level
    log_file_path = setup_logging(
        log_level=log_level,
        log_file=log_file,
        auto_log=use_auto_log,
        command_name=command_name,
        log_dir=config.log_dir
    )

    # Armazena path do log no contexto para uso posterior
    ctx.obj['log_file_path'] = log_file_path

    # Se log foi criado, informa ao usuário
    if log_file_path:
        logger = logging.getLogger(__name__)
        logger.info(f"Log de execução salvo em: {log_file_path}")

    # Se não há subcomando, mostra help
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
@click.option('--directory', '-d', required=True, type=click.Path(exists=True, file_okay=False),
              help='Diretório com arquivos .prc')
@click.option('--extension', '-e', default='prc', help='Extensão dos arquivos (padrão: prc)')
@click.option('--output-dir', '-o', type=click.Path(), help='Diretório de saída (padrão: ./output)')
@click.option('--model', help='Nome do modelo LLM (sobrescreve config)')
@click.option('--device', type=click.Choice(['cuda', 'cpu']), help='Dispositivo (sobrescreve config)')
@click.option('--export-json', is_flag=True, default=True, help='Exportar JSON (padrão: True)')
@click.option('--export-png', is_flag=True, default=True, help='Exportar grafo PNG (padrão: True)')
@click.option('--export-mermaid', is_flag=True, default=False, help='Exportar diagramas Mermaid')
@click.option('--dry-run', is_flag=True, default=False, help='Modo dry-run: valida sem executar')
@click.pass_context
def analyze_files(ctx, directory, extension, output_dir, model, device,
                  export_json, export_png, export_mermaid, dry_run):
    """Analisa procedures a partir de arquivos .prc"""
    config = ctx.obj['config']
    logger = logging.getLogger(__name__)

    try:
        # Modo dry-run: valida sem executar
        if dry_run:
            click.echo("\n" + "=" * 60)
            click.echo("🔍 DRY-RUN MODE - Validação de Configuração")
            click.echo("=" * 60)

            validator = DryRunValidator(config)
            result = DryRunResult(is_valid=True)

            # Valida diretório
            dir_path = Path(directory)
            if not dir_path.exists():
                result.add_error(f"Diretório não existe: {directory}")
            elif not dir_path.is_dir():
                result.add_error(f"Caminho não é um diretório: {directory}")
            else:
                result.add_info(f"Diretório: {directory}")

                # Verifica arquivos .prc
                pattern = f"*.{extension}"
                prc_files = list(dir_path.rglob(pattern))
                if not prc_files:
                    result.add_warning(f"Nenhum arquivo .{extension} encontrado em {directory}")
                else:
                    result.add_info(f"Arquivos encontrados: {len(prc_files)}")
                    result.estimated_operations["files_count"] = len(prc_files)

            # Valida LLM
            llm_result = validator.validate_llm_config(
                model_name=model,
                device=device
            )
            result.errors.extend(llm_result.errors)
            result.warnings.extend(llm_result.warnings)
            result.info.extend(llm_result.info)

            # Valida output_dir
            params_result = validator.validate_analysis_params(
                analysis_type='procedures',  # analyze_files sempre analisa procedures
                output_dir=output_dir
            )
            result.errors.extend(params_result.errors)
            result.warnings.extend(params_result.warnings)
            result.info.extend(params_result.info)
            result.estimated_operations.update(params_result.estimated_operations)

            # Determina validade final
            result.is_valid = len(result.errors) == 0

            # Exibe erros
            if result.errors:
                click.echo("\n❌ Erros:")
                for error in result.errors:
                    click.echo(f"   - {error}", err=True)

            # Exibe warnings
            if result.warnings:
                click.echo("\n⚠️  Avisos:")
                for warning in result.warnings:
                    click.echo(f"   - {warning}")

            # Exibe informações
            if result.info:
                click.echo("\n✅ Informações:")
                for info in result.info:
                    click.echo(f"   - {info}")

            # Exibe estimativas
            if result.estimated_operations:
                click.echo("\n📊 Estimativas:")
                for key, value in result.estimated_operations.items():
                    click.echo(f"   - {key}: {value}")

            # Resumo final
            click.echo("\n" + "=" * 60)
            if result.is_valid:
                click.echo("✅ Validação concluída com sucesso!")
                click.echo("   Execute sem --dry-run para realizar a análise.")
                sys.exit(0)
            else:
                click.echo("❌ Validação falhou!")
                click.echo("   Corrija os erros antes de executar a análise.")
                sys.exit(1)

        # Resolve caminhos
        output_path = Path(output_dir) if output_dir else Path(config.output_dir)
        format_subdir = "toon-format" if config.llm_use_toon else "json-format"
        output_path = output_path / format_subdir
        output_path.mkdir(parents=True, exist_ok=True)

        # Configura modelo baseado no modo
        if config.llm_mode == 'api':
            click.echo(f"Inicializando LLM via API (provider: {config.llm_provider})...")
            llm = LLMAnalyzer(llm_mode='api', config=config)
        else:
            # Modo local
            model_name = model or config.model_name
            device_name = device or config.device
            click.echo(f"Carregando modelo local {model_name}...")
            llm = LLMAnalyzer(model_name=model_name, device=device_name, config=config)

        # Cria Knowledge Graph para persistência
        from app.graph.knowledge_graph import CodeKnowledgeGraph
        knowledge_graph = CodeKnowledgeGraph(cache_path="./cache/knowledge_graph.json")

        analyzer = ProcedureAnalyzer(llm, knowledge_graph=knowledge_graph)

        click.echo(f"Analisando procedures de {directory}...")
        analyzer.analyze_from_files(directory, extension)

        # Exporta resultados
        if export_json:
            json_file = output_path / "procedure_analysis.json"
            analyzer.export_results(str(json_file))
            click.echo(f"✓ JSON exportado: {json_file}")

        if export_png:
            png_file = output_path / "dependency_graph.png"
            analyzer.visualize_dependencies(str(png_file))
            click.echo(f"✓ Grafo PNG exportado: {png_file}")

        if export_mermaid:
            diagram_file = output_path / "diagram.md"
            hierarchy_file = output_path / "hierarchy.md"
            analyzer.export_mermaid_diagram(str(diagram_file))
            analyzer.export_mermaid_hierarchy(str(hierarchy_file))
            click.echo(f"✓ Diagrama Mermaid exportado: {diagram_file}")
            click.echo(f"✓ Hierarquia Mermaid exportada: {hierarchy_file}")

        # Mostra estatísticas
        hierarchy = analyzer.get_procedure_hierarchy()
        click.echo("\n" + "=" * 60)
        click.echo("ESTATÍSTICAS")
        click.echo("=" * 60)
        click.echo(f"Total de procedures: {len(analyzer.procedures)}")
        if analyzer.procedures:
            avg_complexity = sum(p.complexity_score for p in analyzer.procedures.values()) / len(analyzer.procedures)
            max_level = max(p.dependencies_level for p in analyzer.procedures.values())
            click.echo(f"Complexidade média: {avg_complexity:.2f}/10")
            click.echo(f"Nível máximo de dependência: {max_level}")
            click.echo(f"\nHierarquia por níveis:")
            for level in sorted(hierarchy.keys()):
                click.echo(f"  Nível {level}: {len(hierarchy[level])} procedures")

        click.echo("\n✅ Análise concluída!")

    except CodeGraphAIError as e:
        click.echo(f"❌ Erro: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        logger.exception("Erro inesperado")
        click.echo(f"❌ Erro inesperado: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--analysis-type',
              type=click.Choice(['tables', 'procedures', 'both']),
              default='both',
              help='Tipo de análise: tables (apenas tabelas), procedures (apenas procedures), both (ambos)')
@click.option('--db-type', type=click.Choice(['oracle', 'postgresql', 'mssql', 'mysql']),
              default=None, help='Tipo de banco de dados (padrão: postgresql)')
@click.option('--user', default=None, help='Usuário do banco de dados (usa CODEGRAPHAI_DB_USER do env se não fornecido)')
@click.option('--password', default=None, prompt=False, hide_input=True,
              help='Senha do banco de dados (usa CODEGRAPHAI_DB_PASSWORD do env se não fornecido)')
@click.option('--dsn', default=None, help='DSN (host:port/service para Oracle, host para outros)')
@click.option('--host', default=None, help='Host do banco de dados (usa CODEGRAPHAI_DB_HOST do env se não fornecido)')
@click.option('--port', type=int, default=None, help='Porta do banco de dados (usa CODEGRAPHAI_DB_PORT do env se não fornecido)')
@click.option('--database', default=None, help='Nome do banco de dados (usa CODEGRAPHAI_DB_NAME do env se não fornecido)')
@click.option('--schema', default=None, help='Schema específico (usa CODEGRAPHAI_DB_SCHEMA do env se não fornecido)')
@click.option('--limit', type=int, help='Limite de entidades para análise')
@click.option('--output-dir', '-o', type=click.Path(), help='Diretório de saída (padrão: ./output)')
@click.option('--model', help='Nome do modelo LLM (sobrescreve config)')
@click.option('--device', type=click.Choice(['cuda', 'cpu']), help='Dispositivo (sobrescreve config)')
@click.option('--export-json', is_flag=True, default=True, help='Exportar JSON (padrão: True)')
@click.option('--export-png', is_flag=True, default=True, help='Exportar grafo PNG (padrão: True)')
@click.option('--export-mermaid', is_flag=True, default=False, help='Exportar diagramas Mermaid')
@click.option('--batch-size', type=int, default=None, help='Tamanho do batch para análise de tabelas (padrão: 5, 1 desabilita batch)')
@click.option('--parallel-workers', type=int, default=None, help='Número de workers paralelos para análise de tabelas (padrão: 2, 1 desabilita paralelismo)')
@click.option('--no-cache', is_flag=True, default=False, help='Força atualização ignorando cache existente')
@click.option('--dry-run', is_flag=True, default=False, help='Modo dry-run: valida sem executar')
@click.pass_context
def analyze(ctx, analysis_type, db_type, user, password, dsn, host, port, database, schema, limit,
           output_dir, model, device, export_json, export_png, export_mermaid, batch_size, parallel_workers, no_cache, dry_run):
    """Analisa tabelas e/ou procedures do banco de dados"""
    config = ctx.obj['config']
    logger = logging.getLogger(__name__)

    try:
        # Usa valores do config se parâmetros não foram fornecidos
        # Determina tipo de banco primeiro para usar a lógica correta
        if db_type is None:
            db_type = config.db_type.value if config.db_type else 'postgresql'

        # Para PostgreSQL e outros bancos não-Oracle, prioriza valores genéricos (DB_*)
        # Para Oracle, usa valores Oracle específicos
        import os
        if db_type == 'oracle':
            user = user or config.oracle_user
            password = password or config.oracle_password
            host = host or config.oracle_dsn or config.db_host
            schema = schema or config.oracle_schema or config.db_schema
        else:
            # Para PostgreSQL, MySQL, SQL Server, etc, usa valores genéricos primeiro
            user = user or os.getenv('CODEGRAPHAI_DB_USER') or config.oracle_user
            password = password or os.getenv('CODEGRAPHAI_DB_PASSWORD') or config.oracle_password
            host = host or config.db_host or config.oracle_dsn
            schema = schema or config.db_schema or config.oracle_schema

        port = port or (int(config.db_port) if config.db_port else None)
        database = database or config.db_database


        # Validação de parâmetros
        if not dsn and not host:
            click.echo("❌ Erro: --dsn ou --host deve ser fornecido (ou defina CODEGRAPHAI_DB_HOST no environment.env)", err=True)
            sys.exit(1)

        if not user:
            click.echo("❌ Erro: --user deve ser fornecido (ou defina CODEGRAPHAI_DB_USER no environment.env)", err=True)
            sys.exit(1)

        if not password:
            click.echo("❌ Erro: --password deve ser fornecido (ou defina CODEGRAPHAI_DB_PASSWORD no environment.env)", err=True)
            sys.exit(1)

        # Para bancos não-Oracle, database é obrigatório
        if db_type != 'oracle' and not database:
            click.echo(f"❌ Erro: --database é obrigatório para {db_type} (ou defina CODEGRAPHAI_DB_NAME no environment.env)", err=True)
            sys.exit(1)

        # Resolve host/dsn
        if dsn:
            connection_host = dsn
        else:
            connection_host = host

        # Modo dry-run: valida sem executar
        if dry_run:
            click.echo("\n" + "=" * 60)
            click.echo("🔍 DRY-RUN MODE - Validação de Configuração")
            click.echo("=" * 60)

            validator = DryRunValidator(config)
            result = validator.validate_full_analysis(
                analysis_type=analysis_type,
                db_type=db_type,
                user=user,
                password=password,
                host=connection_host,
                port=port,
                database=database,
                schema=schema,
                limit=limit,
                output_dir=output_dir,
                llm_mode=config.llm_mode,
                llm_provider=config.llm_provider
            )

            # Exibe erros
            if result.errors:
                click.echo("\n❌ Erros:")
                for error in result.errors:
                    click.echo(f"   - {error}", err=True)

            # Exibe warnings
            if result.warnings:
                click.echo("\n⚠️  Avisos:")
                for warning in result.warnings:
                    click.echo(f"   - {warning}")

            # Exibe informações
            if result.info:
                click.echo("\n✅ Informações:")
                for info in result.info:
                    click.echo(f"   - {info}")

            # Exibe estimativas
            if result.estimated_operations:
                click.echo("\n📊 Estimativas:")
                for key, value in result.estimated_operations.items():
                    click.echo(f"   - {key}: {value}")

            # Resumo final
            click.echo("\n" + "=" * 60)
            if result.is_valid:
                click.echo("✅ Validação concluída com sucesso!")
                click.echo("   Execute sem --dry-run para realizar a análise.")
                sys.exit(0)
            else:
                click.echo("❌ Validação falhou!")
                click.echo("   Corrija os erros antes de executar a análise.")
                sys.exit(1)

        # Resolve caminhos
        output_path = Path(output_dir) if output_dir else Path(config.output_dir)
        format_subdir = "toon-format" if config.llm_use_toon else "json-format"
        output_path = output_path / format_subdir
        output_path.mkdir(parents=True, exist_ok=True)

        # Configura modelo baseado no modo
        if config.llm_mode == 'api':
            click.echo(f"Inicializando LLM via API (provider: {config.llm_provider})...")
            llm = LLMAnalyzer(llm_mode='api', config=config)
        else:
            # Modo local
            model_name = model or config.model_name
            device_name = device or config.device
            click.echo(f"Carregando modelo local {model_name}...")
            llm = LLMAnalyzer(model_name=model_name, device=device_name, config=config)

        # Cria Knowledge Graph para persistência (usado por ambos analyzers)
        from app.graph.knowledge_graph import CodeKnowledgeGraph
        knowledge_graph = CodeKnowledgeGraph(cache_path="./cache/knowledge_graph.json")
        click.echo("Knowledge Graph inicializado para cache de análise")

        # Variáveis para armazenar resultados
        procedure_analyzer = None
        table_analyzer = None

        # Executa análise de procedures se solicitado
        if analysis_type in ['procedures', 'both']:
            try:
                click.echo("\n" + "=" * 60)
                click.echo("ANÁLISE DE PROCEDURES")
                click.echo("=" * 60)
                procedure_analyzer = ProcedureAnalyzer(llm, knowledge_graph=knowledge_graph)
                click.echo(f"Conectando ao banco {db_type.upper()} ({connection_host})...")
                procedure_analyzer.analyze_from_database(
                    user, password, connection_host, schema, limit,
                    db_type=db_type, database=database, port=port
                )

                # Exporta resultados de procedures
                if export_json:
                    json_file = output_path / "procedure_analysis.json"
                    procedure_analyzer.export_results(str(json_file))
                    click.echo(f"✓ JSON exportado: {json_file}")

                if export_png:
                    png_file = output_path / "dependency_graph.png"
                    procedure_analyzer.visualize_dependencies(str(png_file))
                    click.echo(f"✓ Grafo PNG exportado: {png_file}")

                if export_mermaid:
                    diagram_file = output_path / "procedure_diagram.md"
                    hierarchy_file = output_path / "procedure_hierarchy.md"
                    procedure_analyzer.export_mermaid_diagram(str(diagram_file))
                    procedure_analyzer.export_mermaid_hierarchy(str(hierarchy_file))
                    click.echo(f"✓ Diagrama Mermaid exportado: {diagram_file}")
                    click.echo(f"✓ Hierarquia Mermaid exportada: {hierarchy_file}")

            except Exception as e:
                logger.exception("Erro ao analisar procedures")
                click.echo(f"⚠️  Erro ao analisar procedures: {e}", err=True)
                if analysis_type == 'procedures':
                    # Se era apenas procedures, falha completamente
                    raise

        # Executa análise de tabelas se solicitado
        if analysis_type in ['tables', 'both']:
            try:
                click.echo("\n" + "=" * 60)
                click.echo("ANÁLISE DE TABELAS")
                click.echo("=" * 60)
                table_analyzer = TableAnalyzer(llm, knowledge_graph=knowledge_graph)
                click.echo(f"Conectando ao banco {db_type.upper()} ({connection_host})...")

                # Usa valores do config se não fornecidos via CLI
                effective_batch_size = batch_size if batch_size is not None else config.batch_size
                effective_parallel_workers = parallel_workers if parallel_workers is not None else config.max_parallel_workers

                if effective_batch_size and effective_batch_size > 1:
                    click.echo(f"Usando batch processing (tamanho: {effective_batch_size}, workers: {effective_parallel_workers})")

                table_analyzer.analyze_from_database(
                    user, password, connection_host, schema, limit,
                    db_type=db_type, database=database, port=port,
                    batch_size=effective_batch_size,
                    parallel_workers=effective_parallel_workers,
                    use_cache=True,
                    force_update=no_cache
                )

                # Exporta resultados de tabelas
                if export_json:
                    json_file = output_path / "table_analysis.json"
                    table_analyzer.export_results(str(json_file))
                    click.echo(f"✓ JSON exportado: {json_file}")

                if export_png:
                    png_file = output_path / "relationship_graph.png"
                    table_analyzer.visualize_relationships(str(png_file))
                    click.echo(f"✓ Grafo PNG exportado: {png_file}")

                if export_mermaid:
                    diagram_file = output_path / "table_diagram.md"
                    hierarchy_file = output_path / "table_hierarchy.md"
                    table_analyzer.export_mermaid_diagram(str(diagram_file))
                    table_analyzer.export_mermaid_hierarchy(str(hierarchy_file))
                    click.echo(f"✓ Diagrama Mermaid ER exportado: {diagram_file}")
                    click.echo(f"✓ Hierarquia Mermaid exportada: {hierarchy_file}")

            except Exception as e:
                logger.exception("Erro ao analisar tabelas")
                click.echo(f"⚠️  Erro ao analisar tabelas: {e}", err=True)
                if analysis_type == 'tables':
                    # Se era apenas tabelas, falha completamente
                    raise

        # Mostra estatísticas
        click.echo("\n" + "=" * 60)
        click.echo("ESTATÍSTICAS")
        click.echo("=" * 60)

        # Estatísticas de procedures
        if procedure_analyzer:
            hierarchy = procedure_analyzer.get_procedure_hierarchy()
            click.echo("\nESTATÍSTICAS - PROCEDURES")
            click.echo("-" * 60)
            click.echo(f"Total de procedures: {len(procedure_analyzer.procedures)}")
            if procedure_analyzer.procedures:
                avg_complexity = sum(p.complexity_score for p in procedure_analyzer.procedures.values()) / len(procedure_analyzer.procedures)
                max_level = max(p.dependencies_level for p in procedure_analyzer.procedures.values())
                click.echo(f"Complexidade média: {avg_complexity:.2f}/10")
                click.echo(f"Nível máximo de dependência: {max_level}")
                if hierarchy:
                    click.echo(f"\nHierarquia por níveis:")
                    for level in sorted(hierarchy.keys()):
                        click.echo(f"  Nível {level}: {len(hierarchy[level])} procedures")

        # Estatísticas de tabelas
        if table_analyzer:
            hierarchy = table_analyzer.get_table_hierarchy()
            click.echo("\nESTATÍSTICAS - TABELAS")
            click.echo("-" * 60)
            click.echo(f"Total de tabelas: {len(table_analyzer.tables)}")
            if table_analyzer.tables:
                avg_complexity = sum(t.complexity_score for t in table_analyzer.tables.values()) / len(table_analyzer.tables)
                total_fks = sum(len(t.foreign_keys) for t in table_analyzer.tables.values())
                total_indexes = sum(len(t.indexes) for t in table_analyzer.tables.values())
                click.echo(f"Complexidade média: {avg_complexity:.2f}/10")
                click.echo(f"Total de foreign keys: {total_fks}")
                click.echo(f"Total de índices: {total_indexes}")
                if hierarchy:
                    click.echo(f"\nHierarquia por níveis (baseado em FKs):")
                    for level in sorted(hierarchy.keys()):
                        click.echo(f"  Nível {level}: {len(hierarchy[level])} tabelas")

        # Resumo geral quando ambos
        if analysis_type == 'both' and procedure_analyzer and table_analyzer:
            click.echo("\nRESUMO GERAL")
            click.echo("-" * 60)
            total_entities = len(procedure_analyzer.procedures) + len(table_analyzer.tables)
            click.echo(f"Total de entidades analisadas: {total_entities}")
            click.echo(f"  - Procedures: {len(procedure_analyzer.procedures)}")
            click.echo(f"  - Tabelas: {len(table_analyzer.tables)}")

        # Estatísticas de tokens
        click.echo("\nESTATÍSTICAS - TOKENS LLM")
        click.echo("-" * 60)

        # Coletar estatísticas de tokens do LLM analyzer
        token_stats = None
        if procedure_analyzer and hasattr(procedure_analyzer, 'llm') and hasattr(procedure_analyzer.llm, 'get_token_statistics'):
            token_stats = procedure_analyzer.llm.get_token_statistics()
        elif table_analyzer and hasattr(table_analyzer, 'llm') and hasattr(table_analyzer.llm, 'get_token_statistics'):
            token_stats = table_analyzer.llm.get_token_statistics()

        if token_stats and token_stats.get('total_requests', 0) > 0:
            total = token_stats.get('total_tokens', {})
            click.echo(f"Total de requisições LLM: {token_stats.get('total_requests', 0)}")
            click.echo(f"Tokens de entrada (prompt): {total.get('prompt_tokens', 0):,}")
            click.echo(f"Tokens de saída (completion): {total.get('completion_tokens', 0):,}")
            click.echo(f"Total de tokens: {total.get('total_tokens', 0):,}")

            # Média por requisição
            avg = token_stats.get('average_tokens_per_request', {})
            click.echo(f"\nMédia por requisição:")
            click.echo(f"  - Entrada: {avg.get('prompt_tokens', 0):.1f}")
            click.echo(f"  - Saída: {avg.get('completion_tokens', 0):.1f}")
            click.echo(f"  - Total: {avg.get('total_tokens', 0):.1f}")

            # Por operação
            by_op = token_stats.get('by_operation', {})
            if by_op:
                click.echo(f"\nTokens por operação:")
                for op, op_stats in by_op.items():
                    op_total = op_stats.get('tokens_total', 0)
                    op_count = op_stats.get('count', 0)
                    click.echo(f"  - {op}: {op_total:,} tokens ({op_count} requisições)")

            # Comparação TOON (se aplicável)
            if procedure_analyzer and hasattr(procedure_analyzer, 'llm') and hasattr(procedure_analyzer.llm, 'token_tracker'):
                toon_comparison = procedure_analyzer.llm.token_tracker.get_toon_comparison()
            elif table_analyzer and hasattr(table_analyzer, 'llm') and hasattr(table_analyzer.llm, 'token_tracker'):
                toon_comparison = table_analyzer.llm.token_tracker.get_toon_comparison()
            else:
                toon_comparison = None

            if toon_comparison:
                click.echo(f"\nCOMPARAÇÃO TOON:")
                if toon_comparison.get('without_toon'):
                    savings_pct = toon_comparison.get('overall_savings_percent', 0)
                    savings_tokens = toon_comparison.get('overall_savings_tokens', 0)
                    click.echo(f"  - Economia: {savings_pct:.1f}% ({savings_tokens:,} tokens)")
                    click.echo(f"  - Com TOON: {toon_comparison['with_toon']['total_tokens']:,} tokens")
                    click.echo(f"  - Sem TOON: {toon_comparison['without_toon']['total_tokens']:,} tokens")
                else:
                    click.echo(f"  - TOON foi usado em todas as requisições")
                    click.echo(f"  - Total: {toon_comparison['with_toon']['total_tokens']:,} tokens")
        else:
            click.echo("Nenhuma métrica de tokens disponível (modo local ou métricas não coletadas)")

        click.echo("\n✅ Análise concluída!")

    except CodeGraphAIError as e:
        click.echo(f"❌ Erro: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        logger.exception("Erro inesperado")
        click.echo(f"❌ Erro inesperado: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--db-type', type=click.Choice(['oracle', 'postgresql', 'mssql', 'mysql']),
              default=None, help='Tipo de banco de dados (padrão: postgresql)')
@click.option('--user', required=True, help='Usuário do banco de dados')
@click.option('--password', required=True, prompt=True, hide_input=True,
              help='Senha do banco de dados')
@click.option('--dsn', help='DSN (host:port/service para Oracle, host para outros)')
@click.option('--host', help='Host do banco de dados (alternativa a --dsn)')
@click.option('--port', type=int, help='Porta do banco de dados')
@click.option('--database', help='Nome do banco de dados (obrigatório para PostgreSQL, SQL Server, MySQL)')
@click.option('--schema', help='Schema específico (opcional, não usado no teste)')
@click.pass_context
def test_connection(ctx, db_type, user, password, dsn, host, port, database, schema):
    """Testa conexão com banco de dados sem carregar dados"""
    config = ctx.obj['config']
    logger = logging.getLogger(__name__)

    try:
        # Validação de parâmetros
        if not dsn and not host:
            click.echo("❌ Erro: --dsn ou --host deve ser fornecido", err=True)
            sys.exit(1)

        # Determina tipo de banco (default: postgresql)
        if db_type is None:
            db_type = 'postgresql'

        # Para bancos não-Oracle, database é obrigatório
        if db_type != 'oracle' and not database:
            click.echo(f"❌ Erro: --database é obrigatório para {db_type}", err=True)
            sys.exit(1)

        # Resolve host/dsn
        if dsn:
            connection_host = dsn
        else:
            connection_host = host

        # Cria DatabaseConfig
        try:
            db_type_enum = DatabaseType(db_type.lower())
        except ValueError:
            click.echo(f"❌ Erro: Tipo de banco inválido: {db_type}", err=True)
            sys.exit(1)

        # Para Oracle, constrói DSN se necessário
        if db_type_enum == DatabaseType.ORACLE:
            # Se database fornecido, constrói DSN
            if database and port:
                connection_host = f"{connection_host}:{port}/{database}"
            elif database:
                connection_host = f"{connection_host}/{database}"

        db_config = DatabaseConfig(
            db_type=db_type_enum,
            user=user,
            password=password,
            host=connection_host,
            port=port,
            database=database,
            schema=schema
        )

        # Cria loader e testa conexão
        click.echo(f"Testando conexão com {db_type.upper()} ({connection_host})...")
        loader = create_loader(db_type_enum)

        try:
            success = loader.test_connection_only(db_config)
            if success:
                click.echo("✅ Conexão bem-sucedida!")
                click.echo(f"   Tipo: {db_type.upper()}")
                click.echo(f"   Host: {connection_host}")
                if database:
                    click.echo(f"   Database: {database}")
                if schema:
                    click.echo(f"   Schema: {schema}")
                sys.exit(0)
            else:
                click.echo("❌ Falha na conexão (retornou False)", err=True)
                sys.exit(1)
        except CodeGraphAIError as e:
            click.echo(f"❌ Erro ao conectar: {e}", err=True)
            logger.exception("Erro de conexão")
            sys.exit(1)

    except CodeGraphAIError as e:
        click.echo(f"❌ Erro: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        logger.exception("Erro inesperado")
        click.echo(f"❌ Erro inesperado: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--input', '-i', required=True, type=click.Path(exists=True),
              help='Arquivo JSON de análise')
@click.option('--output-dir', '-o', type=click.Path(), help='Diretório de saída')
@click.option('--format', type=click.Choice(['png', 'mermaid', 'both']), default='both',
              help='Formato de exportação')
@click.pass_context
def export(ctx, input, output_dir, format):
    """Exporta visualizações a partir de análise JSON existente"""
    import json

    config = ctx.obj['config']
    logger = logging.getLogger(__name__)

    try:
        # Carrega análise JSON
        with open(input, 'r', encoding='utf-8') as f:
            data = json.load(f)

        click.echo(f"Carregando análise de {input}...")

        # Resolve caminhos
        output_path = Path(output_dir) if output_dir else Path(config.output_dir)
        format_subdir = "toon-format" if config.llm_use_toon else "json-format"
        output_path = output_path / format_subdir
        output_path.mkdir(parents=True, exist_ok=True)

        # TODO: Implementar reconstrução do analyzer a partir do JSON
        # Por enquanto, apenas informa que precisa re-analisar
        click.echo("⚠️  Exportação a partir de JSON ainda não implementada.")
        click.echo("Use 'analyze-files' ou 'analyze-db' para gerar visualizações.")

    except Exception as e:
        logger.exception("Erro ao exportar")
        click.echo(f"❌ Erro: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('question')
@click.option('--verbose/--no-verbose', default=False, help='Mostrar execução detalhada do agent')
@click.option('--max-iterations', type=int, default=15, help='Número máximo de iterações do agent')
@click.option('--cache-path', default='./cache/knowledge_graph.json', help='Caminho do cache do knowledge graph')
@click.option('--db-type', type=click.Choice(['oracle', 'postgresql', 'mssql', 'mysql']),
              help='Tipo de banco de dados (opcional, necessário para query tools)')
@click.option('--db-user', help='Usuário do banco de dados (opcional)')
@click.option('--db-password', help='Senha do banco de dados (opcional)')
@click.option('--db-host', help='Host do banco de dados (opcional)')
@click.option('--db-port', type=int, help='Porta do banco de dados (opcional)')
@click.option('--db-database', help='Nome do banco de dados (opcional, obrigatório para PostgreSQL, SQL Server, MySQL)')
@click.option('--db-schema', help='Schema do banco de dados (opcional)')
@click.option('--db-dsn', help='DSN completo para Oracle (host:port/service) (opcional)')
@click.pass_context
def query(ctx, question, verbose, max_iterations, cache_path,
          db_type, db_user, db_password, db_host, db_port, db_database, db_schema, db_dsn):
    """
    Faz query inteligente usando agent com tools

    Exemplos:

    \b
    python main.py query "O que faz a procedure PROCESSAR_PEDIDO?"
    python main.py query "Analise o campo status da procedure VALIDAR_USUARIO"
    python main.py query "Quem chama a procedure CALCULAR_SALDO?"
    """
    try:
        # Import tools and agent
        from app.graph.knowledge_graph import CodeKnowledgeGraph
        from app.analysis.code_crawler import CodeCrawler
        from app.tools import init_tools, get_all_tools
        from app.agents.code_analysis_agent import CodeAnalysisAgent
        from analyzer import LLMAnalyzer
        from app.config.config import get_config

        click.echo("=" * 60)
        click.echo("CODE ANALYSIS AGENT - Query Mode")
        click.echo("=" * 60)

        # Check if cache exists
        cache_file = Path(cache_path)
        if not cache_file.exists():
            click.echo(f"⚠️  Cache não encontrado: {cache_path}")
            click.echo("Execute 'python main.py analyze' primeiro para criar o knowledge graph.")
            sys.exit(1)

        # Load config
        click.echo("Carregando configuração...")
        config = get_config()

        # Initialize LLM
        click.echo("Inicializando LLM...")
        llm_analyzer = LLMAnalyzer(config=config)
        chat_model = llm_analyzer.get_chat_model()

        # Load knowledge graph
        click.echo(f"Carregando knowledge graph de {cache_path}...")
        knowledge_graph = CodeKnowledgeGraph(cache_path=cache_path)
        stats = knowledge_graph.get_statistics()
        click.echo(f"✓ Carregado: {stats['total_nodes']} nós, {stats['total_edges']} arestas")

        # Initialize crawler
        crawler = CodeCrawler(knowledge_graph)

        # Create DatabaseConfig - use CLI params if provided, otherwise use config from environment.env
        db_config = None

        try:
            from app.core.models import DatabaseConfig, DatabaseType

            # Get values: CLI params take priority, fallback to config
            final_db_type = db_type or (config.db_type.value if config.db_type else None)
            final_db_user = db_user or config.oracle_user
            final_db_password = db_password or config.oracle_password
            final_db_host = db_host or config.db_host
            final_db_port = db_port or (int(config.db_port) if config.db_port else None)
            final_db_database = db_database or config.db_database
            final_db_schema = db_schema or config.db_schema

            # Check if we have enough info to create DatabaseConfig
            # db_dsn tem prioridade sobre db_host
            has_host_or_dsn = db_dsn or final_db_host

            if final_db_type and final_db_user and final_db_password and has_host_or_dsn:
                # For non-Oracle, database is required
                if final_db_type.lower() != 'oracle' and not final_db_database:
                    click.echo("⚠️  Database name é obrigatório para bancos não-Oracle. Query tools não estarão disponíveis.", err=True)
                    click.echo("   Configure CODEGRAPHAI_DB_NAME em environment.env ou use --db-database")
                else:
                    db_type_enum = DatabaseType(final_db_type.lower())

                    # Determine connection host: db_dsn tem prioridade
                    if db_dsn:
                        connection_host = db_dsn
                    elif final_db_type.lower() == 'oracle':
                        # For Oracle, construct DSN if needed
                        connection_host = final_db_host
                        if final_db_database and final_db_port:
                            connection_host = f"{connection_host}:{final_db_port}/{final_db_database}"
                        elif final_db_database:
                            connection_host = f"{connection_host}/{final_db_database}"
                        elif final_db_port:
                            connection_host = f"{connection_host}:{final_db_port}"
                    else:
                        connection_host = final_db_host

                    db_config = DatabaseConfig(
                        db_type=db_type_enum,
                        user=final_db_user,
                        password=final_db_password,
                        host=connection_host,
                        port=final_db_port,
                        database=final_db_database,
                        schema=final_db_schema
                    )
                    source = "do environment.env" if not (db_type or db_user or db_host) else "dos parâmetros CLI"
                    click.echo(f"✓ Configuração de banco de dados carregada ({source})")
            else:
                click.echo("⚠️  Configuração de banco incompleta. Query tools não estarão disponíveis.", err=True)
                click.echo("   Configure em environment.env ou forneça via CLI: --db-type, --db-user, --db-password, --db-host")
        except Exception as e:
            click.echo(f"⚠️  Erro ao criar configuração de banco: {e}. Query tools não estarão disponíveis.", err=True)

        # Initialize tools
        click.echo("Inicializando tools...")
        init_tools(knowledge_graph, crawler, db_config=db_config)
        tools = get_all_tools()
        click.echo(f"✓ {len(tools)} tools disponíveis")

        # Create agent
        click.echo("Criando agent...")
        agent = CodeAnalysisAgent(
            llm=chat_model,
            tools=tools,
            verbose=verbose,
            max_iterations=max_iterations
        )

        # Execute query
        click.echo("\n" + "=" * 60)
        click.echo(f"PERGUNTA: {question}")
        click.echo("=" * 60 + "\n")

        result = agent.analyze(question)

        if result.get("success"):
            click.echo("RESPOSTA:")
            click.echo("-" * 60)
            click.echo(result["answer"])
            click.echo("-" * 60)

            if result.get("tool_calls"):
                click.echo(f"\n📊 Tools utilizadas: {result['tool_call_count']}")
                if verbose:
                    for i, tool_call in enumerate(result["tool_calls"], 1):
                        click.echo(f"  {i}. {tool_call['tool']}")
        else:
            click.echo(f"❌ Erro: {result.get('error', 'Erro desconhecido')}", err=True)
            sys.exit(1)

        click.echo("\n" + "=" * 60)
        click.echo("Query concluída!")
        click.echo("=" * 60)

    except ImportError as e:
        click.echo(f"❌ Erro de importação: {e}", err=True)
        click.echo("\nVerifique se as dependências estão instaladas:")
        click.echo("  pip install langchain langchain-core")
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Erro: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    cli()

