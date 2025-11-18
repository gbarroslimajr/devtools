#!/usr/bin/env python3
"""
Script para extrair objetos DDL de um schema Oracle.
Extrai tabelas, views, procedures, functions, packages, triggers, sequences, indexes e constraints.
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

try:
    import cx_Oracle
except ImportError:
    try:
        import oracledb as cx_Oracle
    except ImportError:
        print("Erro: Biblioteca cx_Oracle ou oracledb não encontrada.")
        print("Instale com: pip install cx_Oracle")
        sys.exit(1)

from tqdm import tqdm


# Configuração de logging
def setup_logging(log_dir: Path) -> logging.Logger:
    """
    Configura o sistema de logging com arquivo e console.

    Args:
        log_dir: Diretório onde salvar os logs

    Returns:
        Logger configurado
    """
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"extract_{timestamp}.log"

    # Formato do log
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Logging inicializado. Arquivo: {log_file}")

    return logger


def load_environment(env_file: Path) -> Dict[str, str]:
    """
    Carrega variáveis de ambiente do arquivo .env.

    Args:
        env_file: Caminho para o arquivo environment.env

    Returns:
        Dicionário com as variáveis de ambiente
    """
    if not env_file.exists():
        raise FileNotFoundError(f"Arquivo de ambiente não encontrado: {env_file}")

    load_dotenv(env_file)

    config = {
        'host': os.getenv('ORACLE_HOST'),
        'port': os.getenv('ORACLE_PORT', '1521'),
        'service_name': os.getenv('ORACLE_SERVICE_NAME'),
        'sid': os.getenv('ORACLE_SID'),
        'user': os.getenv('ORACLE_USER'),
        'password': os.getenv('ORACLE_PASSWORD'),
        'schema': os.getenv('ORACLE_SCHEMA')
    }

    # Validação
    if not config['host']:
        raise ValueError("ORACLE_HOST não definido no environment.env")
    if not config['user']:
        raise ValueError("ORACLE_USER não definido no environment.env")
    if not config['password']:
        raise ValueError("ORACLE_PASSWORD não definido no environment.env")
    if not config['schema']:
        raise ValueError("ORACLE_SCHEMA não definido no environment.env")
    if not config['service_name'] and not config['sid']:
        raise ValueError("ORACLE_SERVICE_NAME ou ORACLE_SID deve ser definido no environment.env")

    return config


def get_oracle_connection(config: Dict[str, str], logger: logging.Logger):
    """
    Cria conexão com o banco Oracle.

    Args:
        config: Dicionário com configurações de conexão
        logger: Logger para registrar eventos

    Returns:
        Conexão Oracle
    """
    # Montar DSN
    if config['service_name']:
        dsn = f"{config['host']}:{config['port']}/{config['service_name']}"
    else:
        dsn = f"{config['host']}:{config['port']}:{config['sid']}"

    try:
        logger.info(f"Conectando ao Oracle em {config['host']}:{config['port']}...")
        connection = cx_Oracle.connect(
            user=config['user'],
            password=config['password'],
            dsn=dsn
        )
        logger.info("Conexão estabelecida com sucesso")
        return connection
    except Exception as e:
        logger.error(f"Erro ao conectar ao banco: {str(e)}")
        raise


def validate_schema(connection, schema: str, logger: logging.Logger) -> bool:
    """
    Valida se o schema existe e o usuário tem acesso.

    Args:
        connection: Conexão Oracle
        schema: Nome do schema
        logger: Logger

    Returns:
        True se schema é válido
    """
    cursor = connection.cursor()
    try:
        # Verificar se o schema existe
        query = """
            SELECT COUNT(*)
            FROM ALL_USERS
            WHERE USERNAME = UPPER(:schema)
        """
        cursor.execute(query, {'schema': schema})
        count = cursor.fetchone()[0]

        if count == 0:
            logger.warning(f"Schema {schema} não encontrado. Tentando usar schema do usuário atual.")
            # Se não encontrar, pode ser que o usuário esteja tentando extrair seu próprio schema
            return True

        logger.info(f"Schema {schema} validado com sucesso")
        return True
    except Exception as e:
        logger.error(f"Erro ao validar schema: {str(e)}")
        return False
    finally:
        cursor.close()


def create_output_directories(base_dir: Path, schema: str) -> Dict[str, Path]:
    """
    Cria estrutura de diretórios para salvar os arquivos extraídos.

    Args:
        base_dir: Diretório base de saída
        schema: Nome do schema

    Returns:
        Dicionário com caminhos dos diretórios por tipo
    """
    schema_dir = base_dir / schema

    directories = {
        'tables': schema_dir / 'tables',
        'views': schema_dir / 'views',
        'procedures': schema_dir / 'procedures',
        'functions': schema_dir / 'functions',
        'packages': schema_dir / 'packages',
        'triggers': schema_dir / 'triggers',
        'sequences': schema_dir / 'sequences',
        'indexes': schema_dir / 'indexes',
        'constraints': schema_dir / 'constraints'
    }

    for dir_path in directories.values():
        dir_path.mkdir(parents=True, exist_ok=True)

    return directories


def get_ddl(connection, object_type: str, object_name: str, schema: str, logger: logging.Logger) -> Optional[str]:
    """
    Extrai DDL de um objeto usando DBMS_METADATA.GET_DDL.

    Args:
        connection: Conexão Oracle
        object_type: Tipo do objeto (TABLE, VIEW, PROCEDURE, etc.)
        object_name: Nome do objeto
        schema: Nome do schema
        logger: Logger

    Returns:
        DDL do objeto ou None em caso de erro
    """
    cursor = connection.cursor()
    try:
        # Configurar DBMS_METADATA para não incluir storage clauses
        cursor.execute("BEGIN DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'STORAGE', false); END;")
        cursor.execute("BEGIN DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'TABLESPACE', false); END;")
        cursor.execute("BEGIN DBMS_METADATA.SET_TRANSFORM_PARAM(DBMS_METADATA.SESSION_TRANSFORM, 'SEGMENT_ATTRIBUTES', false); END;")

        # Extrair DDL
        query = """
            SELECT DBMS_METADATA.GET_DDL(:object_type, :object_name, :schema)
            FROM DUAL
        """
        cursor.execute(query, {
            'object_type': object_type,
            'object_name': object_name,
            'schema': schema.upper()
        })

        result = cursor.fetchone()
        if result and result[0]:
            ddl_value = result[0]
            # Tratar diferentes tipos de retorno (LOB, string, etc.)
            if hasattr(ddl_value, 'read'):
                return ddl_value.read()
            elif isinstance(ddl_value, (str, bytes)):
                return str(ddl_value) if isinstance(ddl_value, str) else ddl_value.decode('utf-8')
            else:
                return str(ddl_value)
        return None
    except Exception as e:
        logger.warning(f"Erro ao extrair DDL de {object_type} {schema}.{object_name}: {str(e)}")
        return None
    finally:
        cursor.close()


def save_ddl_to_file(ddl: str, file_path: Path, logger: logging.Logger) -> bool:
    """
    Salva DDL em arquivo.

    Args:
        ddl: Conteúdo DDL
        file_path: Caminho do arquivo
        logger: Logger

    Returns:
        True se salvou com sucesso
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(ddl)
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar arquivo {file_path}: {str(e)}")
        return False


def extract_tables(connection, schema: str, output_dir: Path, logger: logging.Logger) -> int:
    """Extrai DDL de todas as tabelas do schema."""
    cursor = connection.cursor()
    count = 0

    try:
        query = """
            SELECT TABLE_NAME
            FROM ALL_TABLES
            WHERE OWNER = UPPER(:schema)
            ORDER BY TABLE_NAME
        """
        cursor.execute(query, {'schema': schema})
        tables = [row[0] for row in cursor.fetchall()]

        logger.info(f"Encontradas {len(tables)} tabelas")

        for table_name in tqdm(tables, desc="Extraindo tabelas", unit="tabela"):
            ddl = get_ddl(connection, 'TABLE', table_name, schema, logger)
            if ddl:
                file_path = output_dir / f"{table_name}.sql"
                if save_ddl_to_file(ddl, file_path, logger):
                    count += 1

        return count
    finally:
        cursor.close()


def extract_views(connection, schema: str, output_dir: Path, logger: logging.Logger) -> int:
    """Extrai DDL de todas as views do schema."""
    cursor = connection.cursor()
    count = 0

    try:
        query = """
            SELECT VIEW_NAME
            FROM ALL_VIEWS
            WHERE OWNER = UPPER(:schema)
            ORDER BY VIEW_NAME
        """
        cursor.execute(query, {'schema': schema})
        views = [row[0] for row in cursor.fetchall()]

        logger.info(f"Encontradas {len(views)} views")

        for view_name in tqdm(views, desc="Extraindo views", unit="view"):
            ddl = get_ddl(connection, 'VIEW', view_name, schema, logger)
            if ddl:
                file_path = output_dir / f"{view_name}.sql"
                if save_ddl_to_file(ddl, file_path, logger):
                    count += 1

        return count
    finally:
        cursor.close()


def extract_procedures(connection, schema: str, output_dir: Path, logger: logging.Logger) -> int:
    """Extrai DDL de todas as procedures do schema."""
    cursor = connection.cursor()
    count = 0

    try:
        query = """
            SELECT DISTINCT OBJECT_NAME
            FROM ALL_PROCEDURES
            WHERE OWNER = UPPER(:schema)
            AND OBJECT_TYPE = 'PROCEDURE'
            ORDER BY OBJECT_NAME
        """
        cursor.execute(query, {'schema': schema})
        procedures = [row[0] for row in cursor.fetchall()]

        logger.info(f"Encontradas {len(procedures)} procedures")

        for proc_name in tqdm(procedures, desc="Extraindo procedures", unit="procedure"):
            ddl = get_ddl(connection, 'PROCEDURE', proc_name, schema, logger)
            if ddl:
                file_path = output_dir / f"{proc_name}.prc"
                if save_ddl_to_file(ddl, file_path, logger):
                    count += 1

        return count
    finally:
        cursor.close()


def extract_functions(connection, schema: str, output_dir: Path, logger: logging.Logger) -> int:
    """Extrai DDL de todas as functions do schema."""
    cursor = connection.cursor()
    count = 0

    try:
        query = """
            SELECT DISTINCT OBJECT_NAME
            FROM ALL_PROCEDURES
            WHERE OWNER = UPPER(:schema)
            AND OBJECT_TYPE = 'FUNCTION'
            ORDER BY OBJECT_NAME
        """
        cursor.execute(query, {'schema': schema})
        functions = [row[0] for row in cursor.fetchall()]

        logger.info(f"Encontradas {len(functions)} functions")

        for func_name in tqdm(functions, desc="Extraindo functions", unit="function"):
            ddl = get_ddl(connection, 'FUNCTION', func_name, schema, logger)
            if ddl:
                file_path = output_dir / f"{func_name}.fnc"
                if save_ddl_to_file(ddl, file_path, logger):
                    count += 1

        return count
    finally:
        cursor.close()


def extract_packages(connection, schema: str, output_dir: Path, logger: logging.Logger) -> int:
    """Extrai DDL de todos os packages do schema."""
    cursor = connection.cursor()
    count = 0

    try:
        query = """
            SELECT DISTINCT OBJECT_NAME
            FROM ALL_OBJECTS
            WHERE OWNER = UPPER(:schema)
            AND OBJECT_TYPE = 'PACKAGE'
            ORDER BY OBJECT_NAME
        """
        cursor.execute(query, {'schema': schema})
        packages = [row[0] for row in cursor.fetchall()]

        logger.info(f"Encontrados {len(packages)} packages")

        for pkg_name in tqdm(packages, desc="Extraindo packages", unit="package"):
            ddl = get_ddl(connection, 'PACKAGE', pkg_name, schema, logger)
            if ddl:
                file_path = output_dir / f"{pkg_name}.sql"
                if save_ddl_to_file(ddl, file_path, logger):
                    count += 1

        return count
    finally:
        cursor.close()


def extract_triggers(connection, schema: str, output_dir: Path, logger: logging.Logger) -> int:
    """Extrai DDL de todos os triggers do schema."""
    cursor = connection.cursor()
    count = 0

    try:
        query = """
            SELECT TRIGGER_NAME
            FROM ALL_TRIGGERS
            WHERE OWNER = UPPER(:schema)
            ORDER BY TRIGGER_NAME
        """
        cursor.execute(query, {'schema': schema})
        triggers = [row[0] for row in cursor.fetchall()]

        logger.info(f"Encontrados {len(triggers)} triggers")

        for trigger_name in tqdm(triggers, desc="Extraindo triggers", unit="trigger"):
            ddl = get_ddl(connection, 'TRIGGER', trigger_name, schema, logger)
            if ddl:
                file_path = output_dir / f"{trigger_name}.sql"
                if save_ddl_to_file(ddl, file_path, logger):
                    count += 1

        return count
    finally:
        cursor.close()


def extract_sequences(connection, schema: str, output_dir: Path, logger: logging.Logger) -> int:
    """Extrai DDL de todas as sequences do schema."""
    cursor = connection.cursor()
    count = 0

    try:
        query = """
            SELECT SEQUENCE_NAME
            FROM ALL_SEQUENCES
            WHERE SEQUENCE_OWNER = UPPER(:schema)
            ORDER BY SEQUENCE_NAME
        """
        cursor.execute(query, {'schema': schema})
        sequences = [row[0] for row in cursor.fetchall()]

        logger.info(f"Encontradas {len(sequences)} sequences")

        for seq_name in tqdm(sequences, desc="Extraindo sequences", unit="sequence"):
            ddl = get_ddl(connection, 'SEQUENCE', seq_name, schema, logger)
            if ddl:
                file_path = output_dir / f"{seq_name}.sql"
                if save_ddl_to_file(ddl, file_path, logger):
                    count += 1

        return count
    finally:
        cursor.close()


def extract_indexes(connection, schema: str, output_dir: Path, logger: logging.Logger) -> int:
    """Extrai DDL de todos os indexes do schema."""
    cursor = connection.cursor()
    count = 0

    try:
        query = """
            SELECT INDEX_NAME
            FROM ALL_INDEXES
            WHERE OWNER = UPPER(:schema)
            AND INDEX_TYPE != 'LOB'
            ORDER BY INDEX_NAME
        """
        cursor.execute(query, {'schema': schema})
        indexes = [row[0] for row in cursor.fetchall()]

        logger.info(f"Encontrados {len(indexes)} indexes")

        for idx_name in tqdm(indexes, desc="Extraindo indexes", unit="index"):
            ddl = get_ddl(connection, 'INDEX', idx_name, schema, logger)
            if ddl:
                file_path = output_dir / f"{idx_name}.sql"
                if save_ddl_to_file(ddl, file_path, logger):
                    count += 1

        return count
    finally:
        cursor.close()


def extract_constraints(connection, schema: str, output_dir: Path, logger: logging.Logger) -> int:
    """Extrai DDL de todas as constraints do schema."""
    cursor = connection.cursor()
    count = 0

    try:
        query = """
            SELECT CONSTRAINT_NAME
            FROM ALL_CONSTRAINTS
            WHERE OWNER = UPPER(:schema)
            AND CONSTRAINT_TYPE IN ('P', 'U', 'R', 'C', 'V', 'O')
            ORDER BY CONSTRAINT_NAME
        """
        cursor.execute(query, {'schema': schema})
        constraints = [row[0] for row in cursor.fetchall()]

        logger.info(f"Encontradas {len(constraints)} constraints")

        for constraint_name in tqdm(constraints, desc="Extraindo constraints", unit="constraint"):
            ddl = get_ddl(connection, 'CONSTRAINT', constraint_name, schema, logger)
            if ddl:
                file_path = output_dir / f"{constraint_name}.sql"
                if save_ddl_to_file(ddl, file_path, logger):
                    count += 1

        return count
    finally:
        cursor.close()


def main():
    """Função principal do script."""
    # Determinar diretórios base
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    env_file = project_dir / "environment.env"
    output_dir = project_dir / "output"
    log_dir = project_dir / "log"

    # Configurar logging
    logger = setup_logging(log_dir)

    try:
        # Carregar configurações
        logger.info("Carregando configurações do environment.env...")
        config = load_environment(env_file)
        schema = config['schema']

        # Conectar ao banco
        connection = get_oracle_connection(config, logger)

        try:
            # Validar schema
            if not validate_schema(connection, schema, logger):
                logger.error(f"Schema {schema} inválido ou sem acesso")
                sys.exit(1)

            # Criar estrutura de diretórios
            logger.info(f"Criando estrutura de diretórios para schema: {schema}")
            dirs = create_output_directories(output_dir, schema)

            # Estatísticas
            stats = {}

            # Extrair objetos
            logger.info("Iniciando extração de objetos...")

            stats['tables'] = extract_tables(connection, schema, dirs['tables'], logger)
            stats['views'] = extract_views(connection, schema, dirs['views'], logger)
            stats['procedures'] = extract_procedures(connection, schema, dirs['procedures'], logger)
            stats['functions'] = extract_functions(connection, schema, dirs['functions'], logger)
            stats['packages'] = extract_packages(connection, schema, dirs['packages'], logger)
            stats['triggers'] = extract_triggers(connection, schema, dirs['triggers'], logger)
            stats['sequences'] = extract_sequences(connection, schema, dirs['sequences'], logger)
            stats['indexes'] = extract_indexes(connection, schema, dirs['indexes'], logger)
            stats['constraints'] = extract_constraints(connection, schema, dirs['constraints'], logger)

            # Relatório final
            logger.info("=" * 60)
            logger.info("RELATÓRIO DE EXTRAÇÃO")
            logger.info("=" * 60)
            total = 0
            for obj_type, count in stats.items():
                logger.info(f"  {obj_type.capitalize()}: {count} objetos extraídos")
                total += count
            logger.info("=" * 60)
            logger.info(f"  TOTAL: {total} objetos extraídos")
            logger.info("=" * 60)
            logger.info(f"Arquivos salvos em: {output_dir / schema}")
            logger.info("Processo concluído com sucesso!")

        finally:
            connection.close()
            logger.info("Conexão fechada")

    except FileNotFoundError as e:
        logger.error(f"Arquivo não encontrado: {str(e)}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Erro de configuração: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Erro fatal: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

