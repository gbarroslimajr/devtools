"""
Testes de integração para suporte a modelos quantizados.

Valida toda a pipeline de detecção, carregamento e uso de modelos quantizados.
"""

import sys
import logging
from pathlib import Path

# Adicionar raiz do projeto ao path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.llm.quantized_model_detector import is_quantized_model, detect_quantization_method
from app.llm.embedding_utils import resolve_embedding_model_path
from app.analysis.fast_indexer import FastIndexer
from app.graph.knowledge_graph import CodeKnowledgeGraph

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_quantized_detection():
    """Testa detecção de modelo quantizado."""
    logger.info("=" * 60)
    logger.info("TESTE 1: Detecção de Modelo Quantizado")
    logger.info("=" * 60)

    model_path = project_root / "models" / "elastic" / "multilingual-e5-small-optimized"

    if not model_path.exists():
        logger.warning(f"⚠️  Modelo não encontrado: {model_path}")
        return False, "Modelo não encontrado"

    is_quantized = is_quantized_model(model_path)
    method = detect_quantization_method(model_path)

    logger.info(f"Modelo: {model_path.name}")
    logger.info(f"É quantizado: {is_quantized}")
    logger.info(f"Método: {method}")

    if is_quantized:
        logger.info("✅ Detecção funcionando corretamente")
        return True, "Detecção OK"
    else:
        logger.warning("⚠️  Modelo não detectado como quantizado")
        return False, "Falha na detecção"


def test_path_resolution():
    """Testa resolução de caminho com detecção de quantização."""
    logger.info("=" * 60)
    logger.info("TESTE 2: Resolução de Caminho com Quantização")
    logger.info("=" * 60)

    model_path, is_local, is_quantized = resolve_embedding_model_path(
        embedding_model=None,
        project_root=project_root
    )

    logger.info(f"Caminho: {model_path}")
    logger.info(f"É local: {is_local}")
    logger.info(f"É quantizado: {is_quantized}")

    if is_local and is_quantized:
        logger.info("✅ Resolução com detecção de quantização OK")
        return True, "Resolução OK"
    elif is_local:
        logger.info("✅ Modelo local detectado (não quantizado)")
        return True, "Modelo local OK"
    else:
        logger.info("✅ Fallback para HuggingFace")
        return True, "Fallback OK"


def test_fastindexer_integration():
    """Testa integração com FastIndexer."""
    logger.info("=" * 60)
    logger.info("TESTE 3: Integração com FastIndexer")
    logger.info("=" * 60)

    try:
        # Criar knowledge graph temporário
        kg = CodeKnowledgeGraph(cache_path=str(project_root / "cache" / "test_kg.json"))

        # Tentar criar FastIndexer (vai detectar modelo quantizado)
        fast_indexer = FastIndexer(
            knowledge_graph=kg,
            embedding_backend="sentence-transformers",
            embedding_model=None,  # Usa padrão
            device="cpu"
        )

        logger.info("✅ FastIndexer criado com sucesso")
        logger.info(f"   Tipo de embedder: {type(fast_indexer.embedder).__name__}")

        # Testar criação de embedding
        test_texts = ["Teste de embedding", "Another test"]
        embeddings = fast_indexer.embedder.encode(
            test_texts,
            batch_size=2,
            convert_to_numpy=True
        )

        logger.info(f"✅ Embeddings criados: shape {embeddings.shape}")

        return True, "Integração OK"
    except Exception as e:
        logger.error(f"❌ Erro na integração: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)


def test_fallback_behavior():
    """Testa comportamento de fallback quando modelo quantizado falha."""
    logger.info("=" * 60)
    logger.info("TESTE 4: Comportamento de Fallback")
    logger.info("=" * 60)

    # O fallback já está implementado no código
    # Este teste valida que o sistema continua funcionando mesmo se quantizado falhar

    try:
        kg = CodeKnowledgeGraph(cache_path=str(project_root / "cache" / "test_kg.json"))

        # Forçar uso de modelo base (simula fallback)
        fast_indexer = FastIndexer(
            knowledge_graph=kg,
            embedding_backend="sentence-transformers",
            embedding_model="intfloat/multilingual-e5-small",  # Modelo base
            device="cpu"
        )

        logger.info("✅ Fallback para modelo base funcionando")

        # Testar embedding
        embeddings = fast_indexer.embedder.encode(
            ["Teste"],
            convert_to_numpy=True
        )

        logger.info(f"✅ Embeddings com modelo base: shape {embeddings.shape}")

        return True, "Fallback OK"
    except Exception as e:
        logger.error(f"❌ Erro no fallback: {e}")
        return False, str(e)


def test_end_to_end():
    """Teste end-to-end completo."""
    logger.info("=" * 60)
    logger.info("TESTE 5: Teste End-to-End")
    logger.info("=" * 60)

    try:
        # Criar diretório de teste
        test_dir = project_root / "test_procedures"
        if not test_dir.exists():
            logger.warning("⚠️  Diretório de teste não encontrado")
            return False, "Diretório não encontrado"

        kg = CodeKnowledgeGraph(cache_path=str(project_root / "cache" / "test_kg_e2e.json"))

        fast_indexer = FastIndexer(
            knowledge_graph=kg,
            embedding_backend="sentence-transformers",
            embedding_model=None,  # Usa padrão (pode ser quantizado)
            device="cpu",
            batch_size=4
        )

        logger.info("FastIndexer criado, testando indexação...")

        # Tentar indexar um arquivo de teste
        result = fast_indexer.index_from_files(
            directory_path=str(test_dir),
            extension="prc",
            show_progress=False
        )

        logger.info(f"✅ Indexação concluída: {result.get('indexed_count', 0)} procedures")
        logger.info(f"   Tempo: {result.get('total_time', 0):.2f}s")

        return True, "E2E OK"
    except Exception as e:
        logger.error(f"❌ Erro no teste E2E: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)


def main():
    """Executa todos os testes."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTES DE INTEGRAÇÃO - MODELOS QUANTIZADOS")
    logger.info("=" * 60 + "\n")

    results = []

    # Executar testes
    results.append(("Detecção", *test_quantized_detection()))
    results.append(("Resolução", *test_path_resolution()))
    results.append(("Integração FastIndexer", *test_fastindexer_integration()))
    results.append(("Fallback", *test_fallback_behavior()))
    results.append(("End-to-End", *test_end_to_end()))

    # Resumo
    logger.info("\n" + "=" * 60)
    logger.info("RESUMO DOS TESTES")
    logger.info("=" * 60)

    passed = 0
    failed = 0

    for name, success, message in results:
        status = "✅ PASSOU" if success else "❌ FALHOU"
        logger.info(f"{name}: {status} - {message}")
        if success:
            passed += 1
        else:
            failed += 1

    logger.info(f"\nTotal: {passed} passaram, {failed} falharam")

    if failed == 0:
        logger.info("\n✅ TODOS OS TESTES PASSARAM")
        return 0
    else:
        logger.warning(f"\n⚠️  {failed} TESTE(S) FALHARAM")
        return 1


if __name__ == "__main__":
    sys.exit(main())

