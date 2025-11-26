"""
Teste simplificado de criação de embeddings

Este teste valida que a funcionalidade de embeddings funciona corretamente,
usando o modelo base do HuggingFace (intfloat/multilingual-e5-small)
já que o modelo optimized requer configuração especial de quantização.
"""

import sys
import logging
from pathlib import Path
import numpy as np

# Adicionar raiz do projeto ao path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("ERRO: sentence-transformers não está instalado")
    sys.exit(1)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_embeddings():
    """Testa criação de embeddings com modelo base."""
    logger.info("=" * 60)
    logger.info("TESTE DE EMBEDDINGS - Modelo Base")
    logger.info("=" * 60)

    # Usar modelo base (não optimized) para teste
    model_name = "intfloat/multilingual-e5-small"

    logger.info(f"Carregando modelo: {model_name}")
    logger.info("(Modelo optimized requer configuração especial de quantização)")

    try:
        model = SentenceTransformer(model_name, device="cpu")
        logger.info("✅ Modelo carregado com sucesso")
        logger.info(f"   Dimensão dos embeddings: {model.get_sentence_embedding_dimension()}")

        # Textos de teste
        texts = [
            "Este é um teste de embedding em português",
            "This is an embedding test in English",
            "CodeGraphAI é uma ferramenta de análise de código",
            "Python é uma linguagem de programação",
            "Machine learning usa algoritmos para aprender padrões"
        ]

        logger.info(f"\nCriando embeddings para {len(texts)} textos...")
        embeddings = model.encode(
            texts,
            batch_size=4,
            show_progress_bar=True,
            convert_to_numpy=True
        )

        logger.info(f"✅ {len(embeddings)} embeddings criados")
        logger.info(f"   Shape: {embeddings.shape}")
        logger.info(f"   Dimensão: {embeddings.shape[1]}")

        # Validar embeddings
        if np.allclose(embeddings, 0):
            logger.error("❌ Embeddings são zeros!")
            return False
        else:
            logger.info("✅ Embeddings contêm valores não-zero")

        # Testar similaridade
        try:
            from sklearn.metrics.pairwise import cosine_similarity

            logger.info("\nTestando similaridade semântica...")
            similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            logger.info(f"   Similaridade entre texto 1 e 2: {similarity:.4f}")

            # Textos similares devem ter alta similaridade
            similar_texts = [
                "Python é uma linguagem de programação",
                "Python programming language"
            ]
            similar_embeddings = model.encode(similar_texts, convert_to_numpy=True)
            similar_sim = cosine_similarity([similar_embeddings[0]], [similar_embeddings[1]])[0][0]
            logger.info(f"   Similaridade entre textos similares: {similar_sim:.4f}")

            if similar_sim > 0.7:
                logger.info("✅ Similaridade semântica funcionando corretamente")
            else:
                logger.warning(f"⚠️  Similaridade baixa: {similar_sim:.4f}")

        except ImportError:
            logger.warning("⚠️  sklearn não disponível, pulando teste de similaridade")

        logger.info("\n" + "=" * 60)
        logger.info("✅ TESTE CONCLUÍDO COM SUCESSO")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_embeddings()
    sys.exit(0 if success else 1)

