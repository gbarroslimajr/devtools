"""
Loader de procedures a partir de arquivos
"""

import logging
from pathlib import Path
from typing import Dict

from app.core.models import DatabaseConfig, DatabaseType, ProcedureLoadError, ValidationError
from app.io.base import ProcedureLoaderBase
from app.io.factory import register_loader

logger = logging.getLogger(__name__)


class FileLoader(ProcedureLoaderBase):
    """Loader de procedures a partir de arquivos .prc"""

    def __init__(self, directory_path: str, extension: str = "prc"):
        """
        Inicializa o loader de arquivos

        Args:
            directory_path: Caminho do diretório com arquivos
            extension: Extensão dos arquivos (padrão: "prc")
        """
        self.directory_path = directory_path
        self.extension = extension

    def get_database_type(self) -> DatabaseType:
        """
        FileLoader não representa um banco específico.
        Retorna ORACLE como padrão para compatibilidade.
        """
        return DatabaseType.ORACLE  # Valor padrão, não usado para arquivos

    def load_procedures(self, config: DatabaseConfig = None) -> Dict[str, str]:
        """
        Carrega procedures de arquivos

        Args:
            config: Não usado para file loader, mantido para compatibilidade

        Returns:
            Dict com nome da procedure como chave e código-fonte como valor

        Raises:
            ProcedureLoadError: Se houver erro ao carregar arquivos
            ValidationError: Se a extensão for inválida
        """
        # Validação
        if not self.extension or not self.extension.strip():
            raise ValidationError("Extensão de arquivo não pode ser vazia")

        proc_dir = Path(self.directory_path)
        if not proc_dir.exists():
            raise ProcedureLoadError(f"Diretório não encontrado: {self.directory_path}")

        if not proc_dir.is_dir():
            raise ProcedureLoadError(f"Caminho não é um diretório: {self.directory_path}")

        procedures = {}

        # Busca todos os arquivos com a extensão especificada
        for file_path in proc_dir.rglob(f"*.{self.extension}"):
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
            raise ProcedureLoadError(
                f"Nenhum arquivo .{self.extension} encontrado em {self.directory_path}"
            )

        logger.info(f"Total de {len(procedures)} procedures carregadas de {self.directory_path}")
        return procedures

    @staticmethod
    def from_files(directory_path: str, extension: str = "prc") -> Dict[str, str]:
        """
        Método estático para compatibilidade com código existente

        Args:
            directory_path: Caminho do diretório
            extension: Extensão dos arquivos

        Returns:
            Dict com procedures carregadas
        """
        loader = FileLoader(directory_path, extension)
        return loader.load_procedures()

# FileLoader não precisa ser registrado no factory pois não usa DatabaseConfig
