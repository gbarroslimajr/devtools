"""
Módulo de cache para DDL de tabelas
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime
from dataclasses import asdict

from app.core.models import DatabaseConfig, TableInfo, ColumnInfo, IndexInfo, ForeignKeyInfo

logger = logging.getLogger(__name__)

# Versão do formato de cache (para migrações futuras)
CACHE_VERSION = "1.0"
CACHE_DIR = Path(__file__).parent.parent.parent / "cache"


class TableCache:
    """Gerencia cache de DDL de tabelas em disco"""

    @staticmethod
    def get_cache_key(config: DatabaseConfig) -> str:
        """
        Gera hash único baseado na configuração do banco (sem senha)

        Args:
            config: Configuração de conexão

        Returns:
            Hash hexadecimal de 16 caracteres
        """
        key_parts = [
            config.db_type.value,
            config.host,
            str(config.port or ''),
            config.database or '',
            config.schema or '',
            config.user
        ]
        key_string = '|'.join(key_parts)
        hash_obj = hashlib.sha256(key_string.encode())
        return hash_obj.hexdigest()[:16]

    @staticmethod
    def get_cache_dir(config: DatabaseConfig) -> Path:
        """
        Retorna diretório de cache para a configuração

        Args:
            config: Configuração de conexão

        Returns:
            Path do diretório de cache
        """
        cache_key = TableCache.get_cache_key(config)
        cache_path = CACHE_DIR / cache_key
        cache_path.mkdir(parents=True, exist_ok=True)
        return cache_path

    @staticmethod
    def get_cache_path(config: DatabaseConfig, schema: str, table_name: str) -> Path:
        """
        Retorna caminho do arquivo de cache para uma tabela

        Args:
            config: Configuração de conexão
            schema: Schema da tabela
            table_name: Nome da tabela

        Returns:
            Path do arquivo de cache
        """
        cache_dir = TableCache.get_cache_dir(config)
        # Sanitiza nome do arquivo (remove caracteres inválidos)
        safe_schema = schema.replace('/', '_').replace('\\', '_')
        safe_table = table_name.replace('/', '_').replace('\\', '_')
        filename = f"{safe_schema}.{safe_table}.json"
        return cache_dir / filename

    @staticmethod
    def load_table_from_cache(
        config: DatabaseConfig,
        schema: str,
        table_name: str
    ) -> Optional[TableInfo]:
        """
        Carrega tabela do cache se existir

        Args:
            config: Configuração de conexão
            schema: Schema da tabela
            table_name: Nome da tabela

        Returns:
            TableInfo se encontrado no cache, None caso contrário
        """
        cache_path = TableCache.get_cache_path(config, schema, table_name)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # Valida versão do cache
            metadata = cache_data.get('metadata', {})
            if metadata.get('cache_version') != CACHE_VERSION:
                logger.warning(
                    f"Versão de cache incompatível para {schema}.{table_name}, "
                    f"esperado {CACHE_VERSION}, encontrado {metadata.get('cache_version')}"
                )
                return None

            # Deserializa TableInfo
            table_data = cache_data.get('table_info', {})
            if not table_data:
                logger.warning(f"Cache inválido para {schema}.{table_name}: sem table_info")
                return None

            # Reconstrói objetos dataclass
            columns = [ColumnInfo(**col) for col in table_data.get('columns', [])]
            indexes = [IndexInfo(**idx) for idx in table_data.get('indexes', [])]
            foreign_keys = [ForeignKeyInfo(**fk) for fk in table_data.get('foreign_keys', [])]

            table_info = TableInfo(
                name=table_data['name'],
                schema=table_data['schema'],
                ddl=table_data['ddl'],
                columns=columns,
                indexes=indexes,
                foreign_keys=foreign_keys,
                primary_key_columns=table_data.get('primary_key_columns', []),
                row_count=table_data.get('row_count'),
                table_size=table_data.get('table_size'),
                business_purpose=table_data.get('business_purpose', ''),
                complexity_score=table_data.get('complexity_score', 0),
                relationships=table_data.get('relationships', {})
            )

            logger.debug(f"Cache carregado para {schema}.{table_name}")
            return table_info

        except json.JSONDecodeError as e:
            logger.warning(f"Erro ao decodificar cache para {schema}.{table_name}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Erro ao carregar cache para {schema}.{table_name}: {e}")
            return None

    @staticmethod
    def save_table_to_cache(config: DatabaseConfig, table_info: TableInfo) -> None:
        """
        Salva tabela no cache

        Args:
            config: Configuração de conexão
            table_info: Informações da tabela a salvar
        """
        cache_path = TableCache.get_cache_path(config, table_info.schema, table_info.name)

        try:
            # Prepara dados para serialização
            cache_data = {
                'metadata': {
                    'created_at': datetime.now().isoformat(),
                    'cache_version': CACHE_VERSION,
                    'db_type': config.db_type.value,
                    'schema': table_info.schema,
                    'table_name': table_info.name
                },
                'table_info': {
                    **asdict(table_info),
                    # Garante que relationships seja um dict serializável
                    'relationships': dict(table_info.relationships) if table_info.relationships else {}
                }
            }

            # Salva em arquivo
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)

            logger.debug(f"Cache salvo para {table_info.schema}.{table_info.name}")

        except Exception as e:
            logger.warning(f"Erro ao salvar cache para {table_info.schema}.{table_info.name}: {e}")
            # Não levanta exceção - cache é opcional

    @staticmethod
    def clear_cache(config: DatabaseConfig) -> None:
        """
        Limpa todo o cache de uma configuração

        Args:
            config: Configuração de conexão
        """
        cache_dir = TableCache.get_cache_dir(config)
        if cache_dir.exists():
            try:
                import shutil
                shutil.rmtree(cache_dir)
                logger.info(f"Cache limpo para configuração {TableCache.get_cache_key(config)}")
            except Exception as e:
                logger.warning(f"Erro ao limpar cache: {e}")

