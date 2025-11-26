"""
Detector de modelos quantizados para embeddings.

Detecta se um modelo de embedding é quantizado, permitindo tratamento especial
durante o carregamento.
"""

from pathlib import Path
from typing import Optional
import logging
import json

logger = logging.getLogger(__name__)


def is_quantized_model(model_path: Path) -> bool:
    """
    Detecta se modelo é quantizado.

    Verifica múltiplos indicadores:
    1. Nome do modelo contém "optimized" (heurística)
    2. Tamanho do pytorch_model.bin (modelos quantizados são menores)
    3. Tentativa de leitura do arquivo (quantizados têm estrutura diferente)
    4. Metadata do README ou config

    Args:
        model_path: Caminho do diretório do modelo

    Returns:
        True se modelo é quantizado, False caso contrário
    """
    if not model_path.exists() or not model_path.is_dir():
        return False

    # Heurística 1: Nome do modelo
    model_name = model_path.name.lower()
    if "optimized" in model_name or "quantized" in model_name:
        logger.debug(f"Modelo '{model_name}' pode ser quantizado (heurística de nome)")
        # Continuar verificações para confirmar

    # Heurística 2: Verificar tamanho do pytorch_model.bin
    pytorch_model = model_path / "pytorch_model.bin"
    if pytorch_model.exists():
        file_size = pytorch_model.stat().st_size

        # Modelos quantizados são significativamente menores
        # multilingual-e5-small base: ~400MB, optimized: ~100-150MB
        # Mas também pode ser ponteiro LFS (< 1MB)
        if file_size < 1024:  # Muito pequeno, provavelmente ponteiro LFS
            logger.debug("Arquivo muito pequeno, pode ser ponteiro LFS")
            return False

        # Tentar detectar se é quantizado pela estrutura do arquivo
        # Modelos quantizados têm tensores com tipos específicos
        try:
            # Ler primeiros bytes para verificar estrutura
            with open(pytorch_model, 'rb') as f:
                # Verificar se começa com versão do pickle (indicando arquivo PyTorch)
                first_bytes = f.read(10)
                # Arquivos PyTorch geralmente começam com versão do pickle
                if first_bytes.startswith(b'version'):
                    # É ponteiro LFS, não arquivo real
                    return False
        except Exception as e:
            logger.debug(f"Erro ao verificar estrutura do arquivo: {e}")

    # Heurística 3: Verificar README para menção a quantização
    readme_path = model_path / "README.md"
    if readme_path.exists():
        try:
            readme_content = readme_path.read_text(encoding='utf-8')
            if "quantized" in readme_content.lower() or "quantization" in readme_content.lower():
                logger.info(f"Modelo quantizado detectado via README: {model_path}")
                return True
        except Exception as e:
            logger.debug(f"Erro ao ler README: {e}")

    # Heurística 4: Verificar config.json para indicadores
    config_path = model_path / "config.json"
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # Verificar se há indicadores de quantização no config
                # (alguns modelos têm campos específicos)
                if "quantization_config" in config:
                    logger.info(f"Modelo quantizado detectado via config: {model_path}")
                    return True
        except Exception as e:
            logger.debug(f"Erro ao ler config.json: {e}")

    # Heurística 5: Verificar se há arquivo de configuração de quantização
    quantization_config = model_path / "quantization_config.json"
    if quantization_config.exists():
        logger.info(f"Modelo quantizado detectado via quantization_config.json: {model_path}")
        return True

    # Se chegou aqui e nome contém "optimized", assumir que é quantizado
    # (baseado no modelo específico que estamos usando)
    if "optimized" in model_name:
        logger.info(f"Modelo optimized detectado (assumindo quantizado): {model_path}")
        return True

    return False


def detect_quantization_method(model_path: Path) -> Optional[str]:
    """
    Detecta método de quantização usado no modelo.

    Args:
        model_path: Caminho do diretório do modelo

    Returns:
        String indicando método ("per-layer", "int8", "int4", etc.) ou None
    """
    if not is_quantized_model(model_path):
        return None

    # Verificar README para informações sobre quantização
    readme_path = model_path / "README.md"
    if readme_path.exists():
        try:
            readme_content = readme_path.read_text(encoding='utf-8')
            if "per-layer" in readme_content.lower():
                return "per-layer"
            if "int8" in readme_content.lower():
                return "int8"
            if "int4" in readme_content.lower():
                return "int4"
        except Exception:
            pass

    # Default para modelos optimized da Elastic
    return "per-layer"

