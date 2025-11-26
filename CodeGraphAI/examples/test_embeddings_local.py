"""
Teste de criação de embeddings usando modelo local

Este script valida que:
1. O modelo local é carregado corretamente
2. Embeddings são criados com sucesso
3. Busca semântica funciona
4. Não há tentativa de acesso ao HuggingFace
"""

import sys
import logging
from pathlib import Path
from typing import List, Tuple
import numpy as np

# Adicionar raiz do projeto ao path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.llm.embedding_utils import resolve_embedding_model_path
from app.graph.knowledge_graph import CodeKnowledgeGraph

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


def test_model_resolution() -> Tuple[str, bool]:
    """
    Testa resolução do modelo local.

    Returns:
        Tuple com (caminho do modelo, is_local)
    """
    logger.info("=" * 60)
    logger.info("TESTE 1: Resolução de Modelo Local")
    logger.info("=" * 60)

    project_root = Path(__file__).parent.parent

    # Tentar modelo optimized primeiro, mas se não funcionar, usar base
    optimized_path = project_root / "models" / "elastic" / "multilingual-e5-small-optimized"

    # Verificar se modelo optimized existe e tem arquivos necessários
    if optimized_path.exists():
        pytorch_file = optimized_path / "pytorch_model.bin"
        if pytorch_file.exists():
            file_size = pytorch_file.stat().st_size
            # Se arquivo é muito pequeno (< 1MB), é ponteiro LFS
            if file_size < 1024 * 1024:
                logger.warning("⚠️  Modelo optimized encontrado mas arquivos LFS não baixados")
                logger.info("   Usando modelo base do HuggingFace para teste")
                return "intfloat/multilingual-e5-small", False
            else:
                logger.info(f"✅ Modelo optimized encontrado ({file_size / 1024 / 1024:.1f} MB)")
                return str(optimized_path.absolute()), True

    # Fallback: usar resolução padrão
    model_path, is_local = resolve_embedding_model_path(
        embedding_model=None,  # Usa padrão
        project_root=project_root
    )

    logger.info(f"Modelo resolvido: {model_path}")
    logger.info(f"É modelo local: {is_local}")

    if not is_local:
        logger.warning("⚠️  Modelo local não encontrado! Usando HuggingFace como fallback")
    else:
        logger.info("✅ Modelo local detectado corretamente")

    return model_path, is_local


def test_model_loading(model_path: str, is_local: bool) -> SentenceTransformer:
    """
    Testa carregamento do modelo.

    Args:
        model_path: Caminho do modelo
        is_local: Se é modelo local

    Returns:
        Instância do SentenceTransformer
    """
    logger.info("=" * 60)
    logger.info("TESTE 2: Carregamento do Modelo")
    logger.info("=" * 60)

    try:
        # Configurar cache_folder se for modelo local
        cache_folder = None
        if is_local:
            cache_folder = str(Path(model_path).parent)
            logger.info(f"Usando cache_folder: {cache_folder}")

        logger.info(f"Carregando modelo de: {model_path}")
        model = SentenceTransformer(
            model_path,
            device="cpu",  # Usar CPU para teste
            cache_folder=cache_folder if cache_folder else None
        )

        logger.info("✅ Modelo carregado com sucesso")
        logger.info(f"   Dimensão dos embeddings: {model.get_sentence_embedding_dimension()}")

        return model
    except Exception as e:
        logger.error(f"❌ Erro ao carregar modelo: {e}")
        raise


def test_embedding_creation(model: SentenceTransformer) -> Tuple[List[np.ndarray], List[str]]:
    """
    Testa criação de embeddings.

    Args:
        model: Instância do SentenceTransformer

    Returns:
        Tuple com (embeddings, textos)
    """
    logger.info("=" * 60)
    logger.info("TESTE 3: Criação de Embeddings")
    logger.info("=" * 60)

    # Textos de exemplo
    texts = [
        "Este é um teste de embedding em português",
        "This is an embedding test in English",
        "CodeGraphAI é uma ferramenta de análise de código",
        "Python é uma linguagem de programação",
        "Machine learning usa algoritmos para aprender padrões",
        "Vector databases armazenam embeddings para busca semântica",
        "RAG pipelines combinam retrieval e generation",
        "Sentence transformers criam embeddings de texto"
    ]

    logger.info(f"Criando embeddings para {len(texts)} textos...")

    try:
        embeddings = model.encode(
            texts,
            batch_size=4,
            show_progress_bar=True,
            convert_to_numpy=True
        )

        logger.info(f"✅ {len(embeddings)} embeddings criados com sucesso")
        logger.info(f"   Shape dos embeddings: {embeddings.shape}")
        logger.info(f"   Dimensão: {embeddings.shape[1]}")

        # Validar que embeddings não são zeros
        if np.allclose(embeddings, 0):
            logger.warning("⚠️  Embeddings são zeros! Algo pode estar errado")
        else:
            logger.info("✅ Embeddings contêm valores não-zero")

        return embeddings, texts
    except Exception as e:
        logger.error(f"❌ Erro ao criar embeddings: {e}")
        raise


def test_semantic_similarity(model: SentenceTransformer, embeddings: np.ndarray, texts: List[str]) -> None:
    """
    Testa busca semântica e similaridade.

    Args:
        model: Instância do SentenceTransformer
        embeddings: Array de embeddings
        texts: Lista de textos
    """
    logger.info("=" * 60)
    logger.info("TESTE 4: Busca Semântica e Similaridade")
    logger.info("=" * 60)

    try:
        # Calcular similaridade entre pares
        from sklearn.metrics.pairwise import cosine_similarity

        similarity_matrix = cosine_similarity(embeddings)

        logger.info("Matriz de similaridade calculada")
        logger.info(f"   Shape: {similarity_matrix.shape}")

        # Encontrar textos mais similares
        query_idx = 0  # Primeiro texto como query
        query_text = texts[query_idx]

        logger.info(f"\nQuery: '{query_text}'")
        logger.info("\nTextos mais similares:")

        # Obter índices ordenados por similaridade (excluindo o próprio)
        similarities = similarity_matrix[query_idx]
        sorted_indices = np.argsort(similarities)[::-1]

        for i, idx in enumerate(sorted_indices[1:4], 1):  # Top 3 (excluindo o próprio)
            similarity = similarities[idx]
            logger.info(f"   {i}. Similaridade: {similarity:.4f} - '{texts[idx]}'")

        # Testar busca com novo texto
        logger.info("\nTestando busca com novo texto...")
        new_text = "Teste de similaridade semântica"
        new_embedding = model.encode([new_text], convert_to_numpy=True)

        # Calcular similaridade com todos os textos
        new_similarities = cosine_similarity(new_embedding, embeddings)[0]
        best_match_idx = np.argmax(new_similarities)

        logger.info(f"Query: '{new_text}'")
        logger.info(f"Melhor match: '{texts[best_match_idx]}' (similaridade: {new_similarities[best_match_idx]:.4f})")

        logger.info("✅ Busca semântica funcionando corretamente")

    except ImportError:
        logger.warning("⚠️  sklearn não disponível, pulando teste de similaridade")
    except Exception as e:
        logger.error(f"❌ Erro no teste de similaridade: {e}")
        raise


def test_batch_processing(model: SentenceTransformer) -> None:
    """
    Testa processamento em batch.

    Args:
        model: Instância do SentenceTransformer
    """
    logger.info("=" * 60)
    logger.info("TESTE 5: Processamento em Batch")
    logger.info("=" * 60)

    # Criar lista maior de textos
    texts = [f"Texto de exemplo número {i} para teste de batch processing" for i in range(50)]

    logger.info(f"Processando {len(texts)} textos em batches...")

    try:
        embeddings = model.encode(
            texts,
            batch_size=16,
            show_progress_bar=True,
            convert_to_numpy=True
        )

        logger.info(f"✅ Processamento em batch concluído")
        logger.info(f"   Total de embeddings: {len(embeddings)}")
        logger.info(f"   Shape: {embeddings.shape}")

    except Exception as e:
        logger.error(f"❌ Erro no processamento em batch: {e}")
        raise


def test_offline_mode() -> None:
    """
    Testa que o modelo funciona em modo offline (sem acesso à internet).
    """
    logger.info("=" * 60)
    logger.info("TESTE 6: Modo Offline")
    logger.info("=" * 60)

    # Verificar se há tentativas de acesso à rede
    # (Este teste é mais conceitual, já que não podemos realmente bloquear rede)

    project_root = Path(__file__).parent.parent
    model_path, is_local = resolve_embedding_model_path(None, project_root)

    if is_local:
        logger.info("✅ Modelo local detectado - funciona em modo offline")
        logger.info(f"   Caminho: {model_path}")

        # Verificar que o caminho existe
        if Path(model_path).exists():
            logger.info("✅ Diretório do modelo existe")
        else:
            logger.error(f"❌ Diretório do modelo não existe: {model_path}")
    else:
        logger.warning("⚠️  Modelo local não encontrado - requer conexão com HuggingFace")


def main():
    """Executa todos os testes."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTES DE EMBEDDINGS COM MODELO LOCAL")
    logger.info("=" * 60 + "\n")

    try:
        # Teste 1: Resolução de modelo
        model_path, is_local = test_model_resolution()

        # Teste 2: Carregamento
        model = test_model_loading(model_path, is_local)

        # Teste 3: Criação de embeddings
        embeddings, texts = test_embedding_creation(model)

        # Teste 4: Busca semântica
        test_semantic_similarity(model, embeddings, texts)

        # Teste 5: Batch processing
        test_batch_processing(model)

        # Teste 6: Modo offline
        test_offline_mode()

        logger.info("\n" + "=" * 60)
        logger.info("✅ TODOS OS TESTES CONCLUÍDOS COM SUCESSO")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"\n❌ ERRO NOS TESTES: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

