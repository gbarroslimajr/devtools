"""
CLI para CodeGraphAI usando Click
"""

import logging
import sys
from pathlib import Path
from typing import Optional

import click
from tqdm import tqdm

from analyzer import LLMAnalyzer, ProcedureAnalyzer
from table_analyzer import TableAnalyzer
from app.core.models import CodeGraphAIError
from config import get_config


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Configura logging

    Args:
        log_level: Nível de logging (DEBUG, INFO, WARNING, ERROR)
        log_file: Arquivo de log (opcional)
    """
    handlers = [logging.StreamHandler(sys.stdout)]

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Modo verbose (DEBUG)')
@click.option('--log-file', type=click.Path(), help='Arquivo de log')
@click.pass_context
def cli(ctx, verbose, log_file):
    """CodeGraphAI - Análise inteligente de procedures de banco de dados"""
    log_level = "DEBUG" if verbose else "INFO"
    setup_logging(log_level, log_file)
    ctx.ensure_object(dict)
    ctx.obj['config'] = get_config()


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
@click.pass_context
def analyze_files(ctx, directory, extension, output_dir, model, device,
                  export_json, export_png, export_mermaid):
    """Analisa procedures a partir de arquivos .prc"""
    config = ctx.obj['config']
    logger = logging.getLogger(__name__)

    try:
        # Resolve caminhos
        output_path = Path(output_dir) if output_dir else Path(config.output_dir)
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

        analyzer = ProcedureAnalyzer(llm)

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
@click.option('--user', required=True, help='Usuário do banco de dados')
@click.option('--password', required=True, prompt=True, hide_input=True,
              help='Senha do banco de dados')
@click.option('--dsn', help='DSN (host:port/service para Oracle, host para outros)')
@click.option('--host', help='Host do banco de dados (alternativa a --dsn)')
@click.option('--port', type=int, help='Porta do banco de dados')
@click.option('--database', help='Nome do banco de dados (obrigatório para PostgreSQL, SQL Server, MySQL)')
@click.option('--schema', help='Schema específico (opcional)')
@click.option('--limit', type=int, help='Limite de entidades para análise')
@click.option('--output-dir', '-o', type=click.Path(), help='Diretório de saída (padrão: ./output)')
@click.option('--model', help='Nome do modelo LLM (sobrescreve config)')
@click.option('--device', type=click.Choice(['cuda', 'cpu']), help='Dispositivo (sobrescreve config)')
@click.option('--export-json', is_flag=True, default=True, help='Exportar JSON (padrão: True)')
@click.option('--export-png', is_flag=True, default=True, help='Exportar grafo PNG (padrão: True)')
@click.option('--export-mermaid', is_flag=True, default=False, help='Exportar diagramas Mermaid')
@click.pass_context
def analyze(ctx, analysis_type, db_type, user, password, dsn, host, port, database, schema, limit,
           output_dir, model, device, export_json, export_png, export_mermaid):
    """Analisa tabelas e/ou procedures do banco de dados"""
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

        # Resolve caminhos
        output_path = Path(output_dir) if output_dir else Path(config.output_dir)
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

        # Variáveis para armazenar resultados
        procedure_analyzer = None
        table_analyzer = None

        # Executa análise de procedures se solicitado
        if analysis_type in ['procedures', 'both']:
            try:
                click.echo("\n" + "=" * 60)
                click.echo("ANÁLISE DE PROCEDURES")
                click.echo("=" * 60)
                procedure_analyzer = ProcedureAnalyzer(llm)
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
                table_analyzer = TableAnalyzer(llm)
                click.echo(f"Conectando ao banco {db_type.upper()} ({connection_host})...")
                table_analyzer.analyze_from_database(
                    user, password, connection_host, schema, limit,
                    db_type=db_type, database=database, port=port
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

        click.echo("\n✅ Análise concluída!")

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
        output_path.mkdir(parents=True, exist_ok=True)

        # TODO: Implementar reconstrução do analyzer a partir do JSON
        # Por enquanto, apenas informa que precisa re-analisar
        click.echo("⚠️  Exportação a partir de JSON ainda não implementada.")
        click.echo("Use 'analyze-files' ou 'analyze-db' para gerar visualizações.")

    except Exception as e:
        logger.exception("Erro ao exportar")
        click.echo(f"❌ Erro: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    cli()

