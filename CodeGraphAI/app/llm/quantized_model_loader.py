"""
Carregador para modelos quantizados de embedding.

Carrega modelos quantizados que não podem ser carregados diretamente pelo
sentence-transformers devido a tensores quantizados que requerem weights_only=False.
"""

from pathlib import Path
from typing import List, Union, Optional
import logging
import torch
import numpy as np
from contextlib import contextmanager

try:
    from transformers import AutoModel, AutoTokenizer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

logger = logging.getLogger(__name__)


@contextmanager
def allow_quantized_loading():
    """
    Context manager para permitir carregamento de tensores quantizados.

    PyTorch 2.6+ usa weights_only=True por padrão, que não suporta tensores quantizados.
    Este context manager temporariamente desabilita essa restrição.

    WARNING: Usar apenas com modelos locais confiáveis.
    """
    import transformers.modeling_utils as modeling_utils

    # Patch torch.load
    original_torch_load = torch.load

    def patched_torch_load(*args, **kwargs):
        """Patch torch.load para permitir tensores quantizados."""
        kwargs['weights_only'] = False
        return original_torch_load(*args, **kwargs)

    # Patch load_state_dict do transformers também
    original_load_state_dict = modeling_utils.load_state_dict

    def patched_load_state_dict(checkpoint_file, *args, **kwargs):
        """Patch load_state_dict para permitir tensores quantizados."""
        # Sempre usar weights_only=False para modelos quantizados
        kwargs['weights_only'] = False
        return original_load_state_dict(checkpoint_file, *args, **kwargs)

    # Aplicar patches
    torch.load = patched_torch_load
    modeling_utils.load_state_dict = patched_load_state_dict

    try:
        yield
    finally:
        # Restaurar
        torch.load = original_torch_load
        modeling_utils.load_state_dict = original_load_state_dict


class QuantizedModelLoader:
    """
    Carregador para modelos quantizados de embedding.

    Contorna limitações do sentence-transformers com modelos quantizados
    carregando diretamente via transformers e criando wrapper compatível.

    Implementa interface compatível com SentenceTransformer para uso transparente.
    """

    def __init__(
        self,
        model_path: str,
        device: str = "cpu",
        trust_remote_code: bool = False
    ):
        """
        Inicializa carregador de modelo quantizado.

        Args:
            model_path: Caminho do modelo quantizado (diretório local)
            device: Dispositivo ("cpu" ou "cuda")
            trust_remote_code: Se deve confiar em código remoto (não recomendado)

        Raises:
            ImportError: Se transformers não estiver instalado
            ValueError: Se modelo não puder ser carregado
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "transformers não está instalado. "
                "Instale com: pip install transformers>=4.29.0"
            )

        self.model_path = Path(model_path)
        self.device = device
        self.trust_remote_code = trust_remote_code

        if not self.model_path.exists():
            raise ValueError(f"Modelo não encontrado: {model_path}")

        logger.info(f"Carregando modelo quantizado de: {model_path}")
        logger.warning(
            "Usando weights_only=False para carregar tensores quantizados. "
            "Apenas use com modelos locais confiáveis."
        )

        # Carregar tokenizer
        # Se tokenizer local não estiver disponível (LFS), usar do modelo base
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                str(self.model_path),
                trust_remote_code=trust_remote_code
            )
        except Exception as e:
            logger.warning(
                f"Erro ao carregar tokenizer local: {e}. "
                "Tentando usar tokenizer do modelo base..."
            )
            # Fallback: usar tokenizer do modelo base
            # multilingual-e5-small-optimized é baseado em multilingual-e5-small
            try:
                base_model_name = "intfloat/multilingual-e5-small"
                self.tokenizer = AutoTokenizer.from_pretrained(
                    base_model_name,
                    trust_remote_code=trust_remote_code
                )
                logger.info(f"Tokenizer do modelo base carregado: {base_model_name}")
            except Exception as e2:
                raise ValueError(
                    f"Erro ao carregar tokenizer (local e base): {e2}. "
                    "Verifique conexão ou baixe tokenizer localmente."
                ) from e2

        # Carregar modelo com suporte a quantização
        # NOTA: Modelos quantizados da Elastic podem requerer bibliotecas específicas
        # ou versões específicas do PyTorch com suporte completo a quantização
        try:
            with allow_quantized_loading():
                self.model = AutoModel.from_pretrained(
                    str(self.model_path),
                    trust_remote_code=trust_remote_code,
                    torch_dtype=torch.float32  # Modelos quantizados podem usar float32
                )
        except (NotImplementedError, OSError) as e:
            # Erro específico de quantização - modelo pode requerer suporte adicional
            error_msg = str(e)
            if "aten::_empty_affine_quantized" in error_msg or "QuantizedMeta" in error_msg:
                raise ValueError(
                    f"Modelo quantizado requer suporte específico de quantização do PyTorch. "
                    f"Erro: {e}. "
                    "O modelo optimized da Elastic pode requerer bibliotecas específicas ou "
                    "versão customizada do PyTorch. "
                    "Considere usar o modelo base 'intfloat/multilingual-e5-small' como alternativa."
                ) from e
            else:
                raise ValueError(
                    f"Erro ao carregar modelo quantizado: {e}. "
                    "Verifique se o modelo está completo e válido."
                ) from e
        except Exception as e:
            raise ValueError(
                f"Erro ao carregar modelo quantizado: {e}. "
                "Verifique se o modelo está completo e válido."
            ) from e

        # Mover modelo para device
        self.model.to(device)
        self.model.eval()  # Modo avaliação

        # Obter dimensão de embedding
        try:
            # Tentar obter do config
            from transformers import AutoConfig
            config = AutoConfig.from_pretrained(str(self.model_path))
            self.embedding_dimension = config.hidden_size
        except Exception:
            # Fallback: inferir da primeira camada
            if hasattr(self.model, 'embeddings'):
                self.embedding_dimension = self.model.embeddings.word_embeddings.embedding_dim
            else:
                # Default para multilingual-e5-small
                self.embedding_dimension = 384

        logger.info(f"Modelo quantizado carregado com sucesso (dimensão: {self.embedding_dimension})")

    def encode(
        self,
        sentences: Union[str, List[str]],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        convert_to_numpy: bool = True,
        normalize_embeddings: bool = False
    ) -> np.ndarray:
        """
        Cria embeddings de textos.

        Compatível com interface do SentenceTransformer.

        Args:
            sentences: Texto único ou lista de textos
            batch_size: Tamanho do batch para processamento
            show_progress_bar: Mostrar barra de progresso
            convert_to_numpy: Converter para numpy array
            normalize_embeddings: Normalizar embeddings (L2 norm)

        Returns:
            Array de embeddings (n_samples, embedding_dim)
        """
        # Normalizar entrada para lista
        if isinstance(sentences, str):
            sentences = [sentences]

        if not sentences:
            return np.array([])

        all_embeddings = []

        # Processar em batches
        iterator = range(0, len(sentences), batch_size)
        if show_progress_bar:
            try:
                from tqdm import tqdm
                iterator = tqdm(iterator, desc="Encoding")
            except ImportError:
                pass

        with torch.no_grad():
            for i in iterator:
                batch = sentences[i:i + batch_size]

                # Tokenizar
                encoded = self.tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=512,  # Default para modelos BERT-like
                    return_tensors="pt"
                )

                # Mover para device
                encoded = {k: v.to(self.device) for k, v in encoded.items()}

                # Forward pass
                outputs = self.model(**encoded)

                # Mean pooling
                embeddings = self._mean_pooling(
                    outputs.last_hidden_state,
                    encoded['attention_mask']
                )

                # Normalizar se solicitado
                if normalize_embeddings:
                    embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

                all_embeddings.append(embeddings.cpu())

        # Concatenar todos os batches
        result = torch.cat(all_embeddings, dim=0)

        # Converter para numpy se solicitado
        if convert_to_numpy:
            return result.numpy()
        return result

    def _mean_pooling(
        self,
        model_outputs: torch.Tensor,
        attention_mask: torch.Tensor
    ) -> torch.Tensor:
        """
        Mean pooling para obter embeddings de sentença.

        Args:
            model_outputs: Outputs do modelo (last_hidden_state)
            attention_mask: Máscara de atenção

        Returns:
            Embeddings de sentença (batch_size, hidden_size)
        """
        # Expandir attention mask para dimensão dos embeddings
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(model_outputs.size()).float()

        # Somar embeddings ponderados pela máscara
        sum_embeddings = torch.sum(model_outputs * input_mask_expanded, 1)

        # Somar máscara (número de tokens válidos)
        sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)

        # Média
        return sum_embeddings / sum_mask

    def get_sentence_embedding_dimension(self) -> int:
        """
        Retorna dimensão dos embeddings.

        Returns:
            Dimensão dos embeddings
        """
        return self.embedding_dimension

    def __repr__(self) -> str:
        """Representação string do carregador."""
        return f"QuantizedModelLoader(model_path={self.model_path}, device={self.device})"

