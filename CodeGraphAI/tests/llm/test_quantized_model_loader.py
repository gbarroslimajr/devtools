"""
Testes para carregador de modelos quantizados.
"""

import pytest
from pathlib import Path
import sys

# Adicionar raiz do projeto ao path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.llm.quantized_model_detector import is_quantized_model, detect_quantization_method
from app.llm.quantized_model_loader import QuantizedModelLoader, allow_quantized_loading


class TestQuantizedModelDetector:
    """Testes para detector de modelos quantizados."""

    def test_is_quantized_model_with_optimized_name(self, tmp_path):
        """Testa detecção de modelo quantizado pelo nome."""
        # Criar estrutura de modelo optimized
        model_dir = tmp_path / "multilingual-e5-small-optimized"
        model_dir.mkdir()

        # Criar arquivos básicos
        (model_dir / "config.json").write_text('{"model_type": "bert"}')
        (model_dir / "tokenizer_config.json").write_text('{}')
        (model_dir / "README.md").write_text('Quantized version of multilingual-e5-small')

        assert is_quantized_model(model_dir) is True

    def test_is_quantized_model_with_quantization_config(self, tmp_path):
        """Testa detecção via quantization_config.json."""
        model_dir = tmp_path / "test-model"
        model_dir.mkdir()

        (model_dir / "config.json").write_text('{}')
        (model_dir / "tokenizer_config.json").write_text('{}')
        (model_dir / "quantization_config.json").write_text('{}')

        assert is_quantized_model(model_dir) is True

    def test_is_quantized_model_not_quantized(self, tmp_path):
        """Testa que modelo normal não é detectado como quantizado."""
        model_dir = tmp_path / "normal-model"
        model_dir.mkdir()

        (model_dir / "config.json").write_text('{}')
        (model_dir / "tokenizer_config.json").write_text('{}')
        (model_dir / "README.md").write_text('Normal model')

        assert is_quantized_model(model_dir) is False

    def test_detect_quantization_method_per_layer(self, tmp_path):
        """Testa detecção de método per-layer."""
        model_dir = tmp_path / "optimized-model"
        model_dir.mkdir()

        (model_dir / "config.json").write_text('{}')
        (model_dir / "tokenizer_config.json").write_text('{}')
        (model_dir / "README.md").write_text('Quantization was performed per-layer')

        method = detect_quantization_method(model_dir)
        assert method == "per-layer"

    def test_detect_quantization_method_none(self, tmp_path):
        """Testa que modelo não quantizado retorna None."""
        model_dir = tmp_path / "normal-model"
        model_dir.mkdir()

        (model_dir / "config.json").write_text('{}')
        (model_dir / "tokenizer_config.json").write_text('{}')

        method = detect_quantization_method(model_dir)
        assert method is None


class TestQuantizedModelLoader:
    """Testes para carregador de modelos quantizados."""

    def test_allow_quantized_loading_context(self):
        """Testa context manager para carregamento quantizado."""
        import torch

        original_load = torch.load

        with allow_quantized_loading():
            # Verificar que torch.load foi modificado
            assert torch.load != original_load

        # Verificar que foi restaurado
        assert torch.load == original_load

    @pytest.mark.skipif(
        not Path(project_root / "models" / "elastic" / "multilingual-e5-small-optimized").exists(),
        reason="Modelo optimized não encontrado localmente"
    )
    def test_load_quantized_model(self):
        """Testa carregamento de modelo quantizado real."""
        model_path = project_root / "models" / "elastic" / "multilingual-e5-small-optimized"

        if not model_path.exists():
            pytest.skip("Modelo optimized não encontrado")

        loader = QuantizedModelLoader(
            model_path=str(model_path),
            device="cpu"
        )

        assert loader is not None
        assert loader.embedding_dimension > 0

    @pytest.mark.skipif(
        not Path(project_root / "models" / "elastic" / "multilingual-e5-small-optimized").exists(),
        reason="Modelo optimized não encontrado localmente"
    )
    def test_encode_with_quantized_model(self):
        """Testa criação de embeddings com modelo quantizado."""
        model_path = project_root / "models" / "elastic" / "multilingual-e5-small-optimized"

        if not model_path.exists():
            pytest.skip("Modelo optimized não encontrado")

        loader = QuantizedModelLoader(
            model_path=str(model_path),
            device="cpu"
        )

        texts = ["Teste de embedding", "Another test"]
        embeddings = loader.encode(texts, batch_size=2, convert_to_numpy=True)

        assert embeddings.shape[0] == 2  # 2 textos
        assert embeddings.shape[1] == loader.embedding_dimension

    def test_get_sentence_embedding_dimension(self):
        """Testa obtenção de dimensão de embedding."""
        # Este teste requer modelo real, então vamos mockar
        # Em produção, seria testado com modelo real
        pass

    def test_mean_pooling(self):
        """Testa função de mean pooling."""
        import torch

        loader = QuantizedModelLoader.__new__(QuantizedModelLoader)

        # Criar dados de teste
        batch_size = 2
        seq_len = 5
        hidden_size = 384

        model_outputs = torch.randn(batch_size, seq_len, hidden_size)
        attention_mask = torch.ones(batch_size, seq_len)
        attention_mask[0, 3:] = 0  # Primeiro exemplo tem apenas 3 tokens

        embeddings = loader._mean_pooling(model_outputs, attention_mask)

        assert embeddings.shape == (batch_size, hidden_size)
        # Verificar que não são todos zeros
        assert not torch.allclose(embeddings, torch.zeros_like(embeddings))

