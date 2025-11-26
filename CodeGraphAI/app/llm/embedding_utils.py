"""
Utilitários para carregamento de modelos de embedding.

Seguindo padrões de produção para RAG pipelines e embeddings locais.
"""

from pathlib import Path
from typing import Optional, Tuple
import logging

from app.llm.quantized_model_detector import is_quantized_model

logger = logging.getLogger(__name__)

# Arquivos obrigatórios para validar modelo local
REQUIRED_MODEL_FILES = [
    "config.json",
    "tokenizer_config.json"
]


def resolve_embedding_model_path(
    embedding_model: Optional[str],
    project_root: Optional[Path] = None
) -> Tuple[str, bool, bool]:
    """
    Resolve embedding model path com validação robusta.

    Args:
        embedding_model: Nome do modelo ou caminho local
        project_root: Raiz do projeto (default: detecta automaticamente)

    Returns:
        Tuple[str, bool, bool]: (caminho_resolvido, is_local, is_quantized)
            - caminho_resolvido: Caminho absoluto ou nome do modelo HuggingFace
            - is_local: True se modelo é local, False se é HuggingFace
            - is_quantized: True se modelo é quantizado, False caso contrário

    Raises:
        ValueError: Se modelo local especificado não existe ou está incompleto
    """
    if project_root is None:
        # Detectar raiz do projeto (assumindo estrutura CodeGraphAI/app/...)
        project_root = Path(__file__).parent.parent.parent

    default_local = project_root / "models" / "elastic" / "multilingual-e5-small-optimized"

    # Caso 1: embedding_model é None - tentar modelo padrão local
    if embedding_model is None:
        if _validate_local_model(default_local):
            is_quantized = is_quantized_model(default_local)
            logger.info(f"Usando modelo local padrão: {default_local} (quantized: {is_quantized})")
            return str(default_local.absolute()), True, is_quantized
        logger.info("Modelo local padrão não encontrado, usando HuggingFace fallback")
        return "sentence-transformers/all-MiniLM-L6-v2", False, False

    # Caso 2: embedding_model é caminho absoluto ou relativo
    model_path = Path(embedding_model)

    # Se é caminho relativo, tentar resolver em relação ao project_root
    if not model_path.is_absolute():
        # Tentar como caminho relativo ao project_root
        candidate = project_root / model_path
        if candidate.exists() and candidate.is_dir():
            model_path = candidate
        # Tentar como caminho relativo ao diretório atual
        elif not model_path.exists():
            model_path = Path.cwd() / model_path

    # Verificar se é diretório local válido
    if model_path.exists() and model_path.is_dir():
        if _validate_local_model(model_path):
            is_quantized = is_quantized_model(model_path)
            logger.info(f"Usando modelo local: {model_path.absolute()} (quantized: {is_quantized})")
            return str(model_path.absolute()), True, is_quantized
        else:
            raise ValueError(
                f"Modelo local em {model_path} está incompleto. "
                f"Arquivos obrigatórios ausentes: {_get_missing_files(model_path)}"
            )

    # Caso 3: Tentar como subdiretório de models/
    local_candidate = project_root / "models" / embedding_model
    if local_candidate.exists() and local_candidate.is_dir():
        if _validate_local_model(local_candidate):
            is_quantized = is_quantized_model(local_candidate)
            logger.info(f"Usando modelo local de models/: {local_candidate.absolute()} (quantized: {is_quantized})")
            return str(local_candidate.absolute()), True, is_quantized

    # Caso 4: Fallback - tratar como nome de modelo HuggingFace
    logger.info(f"Tratando '{embedding_model}' como modelo HuggingFace")
    return embedding_model, False, False


def _validate_local_model(model_path: Path) -> bool:
    """
    Valida se diretório contém modelo sentence-transformers válido.

    Args:
        model_path: Caminho do diretório do modelo

    Returns:
        True se modelo é válido, False caso contrário
    """
    if not model_path.exists() or not model_path.is_dir():
        return False

    # Verificar arquivos obrigatórios
    for required_file in REQUIRED_MODEL_FILES:
        if not (model_path / required_file).exists():
            return False

    return True


def _get_missing_files(model_path: Path) -> list[str]:
    """
    Retorna lista de arquivos obrigatórios ausentes.

    Args:
        model_path: Caminho do diretório do modelo

    Returns:
        Lista de nomes de arquivos ausentes
    """
    missing = []
    for required_file in REQUIRED_MODEL_FILES:
        if not (model_path / required_file).exists():
            missing.append(required_file)
    return missing

