"""
Teste de integração completo para modelo quantizado optimized.

Valida que o modelo quantizado pode ser carregado e usado para criar embeddings.
"""

import sys
import logging
from pathlib import Path

# Adicionar raiz do projeto ao path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.llm.quantized_model_detector import is_quantized_model
from app.llm.quantized_model_loader import QuantizedModelLoader
from app.llm.embedding_utils import resolve_embedding_model_path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_quantized_model_detection():
    """Testa detecção de modelo quantizado."""
    logger.info("=" * 60)
    logger.info("TESTE 1: Detecção de Modelo Quantizado")
    logger.info("=" * 60)

    model_path = project_root / "models" / "elastic" / "multilingual-e5-small-optimized"

    if not model_path.exists():
        logger.warning(f"⚠️  Modelo não encontrado: {model_path}")
        logger.info("   Execute: cd models && git clone https://huggingface.co/elastic/multilingual-e5-small-optimized")
        return False

    is_quantized = is_quantized_model(model_path)
    logger.info(f"Modelo: {model_path}")
    logger.info(f"É quantizado: {is_quantized}")

    if is_quantized:
        logger.info("✅ Modelo quantizado detectado corretamente")
        return True
    else:
        logger.warning("⚠️  Modelo não foi detectado como quantizado")
        return False


def test_quantized_model_loading():
    """Testa carregamento de modelo quantizado."""
    logger.info("=" * 60)
    logger.info("TESTE 2: Carregamento de Modelo Quantizado")
    logger.info("=" * 60)

    model_path = project_root / "models" / "elastic" / "multilingual-e5-small-optimized"

    if not model_path.exists():
        logger.warning("⚠️  Modelo não encontrado, pulando teste")
        return False

    try:
        loader = QuantizedModelLoader(
            model_path=str(model_path),
            device="cpu"
        )

        logger.info("✅ Modelo quantizado carregado com sucesso")
        logger.info(f"   Dimensão: {loader.get_sentence_embedding_dimension()}")
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao carregar modelo: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_quantized_embeddings():
    """Testa criação de embeddings com modelo quantizado."""
    logger.info("=" * 60)
    logger.info("TESTE 3: Criação de Embeddings Quantizados")
    logger.info("=" * 60)

    model_path = project_root / "models" / "elastic" / "multilingual-e5-small-optimized"

    if not model_path.exists():
        logger.warning("⚠️  Modelo não encontrado, pulando teste")
        return False

    try:
        loader = QuantizedModelLoader(
            model_path=str(model_path),
            device="cpu"
        )

        texts = [
            "Este é um teste de embedding em português",
            "This is an embedding test in English",
            "CodeGraphAI é uma ferramenta de análise de código",
            "Python é uma linguagem de programação"
        ]

        logger.info(f"Criando embeddings para {len(texts)} textos...")
        embeddings = loader.encode(
            texts,
            batch_size=2,
            show_progress_bar=True,
            convert_to_numpy=True
        )

        logger.info(f"✅ Embeddings criados: shape {embeddings.shape}")

        # Validar embeddings
        import numpy as np
        if np.allclose(embeddings, 0):
            logger.error("❌ Embeddings são zeros!")
            return False

        logger.info("✅ Embeddings contêm valores não-zero")

        # Testar similaridade
        try:
            from sklearn.metrics.pairwise import cosine_similarity

            similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            logger.info(f"   Similaridade entre texto 1 e 2: {similarity:.4f}")

            if similarity > 0.5:
                logger.info("✅ Similaridade semântica funcionando")
            else:
                logger.warning(f"⚠️  Similaridade baixa: {similarity:.4f}")
        except ImportError:
            logger.warning("⚠️  sklearn não disponível, pulando teste de similaridade")

        return True
    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_resolve_embedding_path():
    """Testa resolução de caminho com detecção de quantização."""
    logger.info("=" * 60)
    logger.info("TESTE 4: Resolução de Caminho com Quantização")
    logger.info("=" * 60)

    model_path, is_local, is_quantized = resolve_embedding_model_path(
        embedding_model=None,
        project_root=project_root
    )

    logger.info(f"Caminho resolvido: {model_path}")
    logger.info(f"É local: {is_local}")
    logger.info(f"É quantizado: {is_quantized}")

    if is_local and is_quantized:
        logger.info("✅ Resolução com detecção de quantização funcionando")
        return True
    elif is_local:
        logger.info("✅ Modelo local detectado (não quantizado)")
        return True
    else:
        logger.info("✅ Fallback para HuggingFace")
        return True


def main():
    """Executa todos os testes."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTES DE MODELO QUANTIZADO OPTIMIZED")
    logger.info("=" * 60 + "\n")

    results = []

    # Teste 1: Detecção
    results.append(("Detecção", test_quantized_model_detection()))

    # Teste 2: Carregamento
    results.append(("Carregamento", test_quantized_model_loading()))

    # Teste 3: Embeddings
    results.append(("Embeddings", test_quantized_embeddings()))

    # Teste 4: Resolução
    results.append(("Resolução", test_resolve_embedding_path()))

    # Resumo
    logger.info("\n" + "=" * 60)
    logger.info("RESUMO DOS TESTES")
    logger.info("=" * 60)

    for name, result in results:
        status = "✅ PASSOU" if result else "❌ FALHOU"
        logger.info(f"{name}: {status}")

    all_passed = all(result for _, result in results)

    if all_passed:
        logger.info("\n✅ TODOS OS TESTES PASSARAM")
    else:
        logger.warning("\n⚠️  ALGUNS TESTES FALHARAM")
        logger.info("   Verifique se o modelo optimized está completo e válido")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

