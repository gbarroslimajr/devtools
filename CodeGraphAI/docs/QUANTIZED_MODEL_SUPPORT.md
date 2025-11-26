# Suporte para Modelos Quantizados

## Visão Geral

O CodeGraphAI implementa suporte para modelos de embedding quantizados, especificamente o modelo `multilingual-e5-small-optimized` da Elastic.

## Status Atual

### ✅ Implementado
- Detecção automática de modelos quantizados
- Carregador especializado (`QuantizedModelLoader`)
- Integração com `FastIndexer` e `VectorKnowledgeGraph`
- Fallback automático para modelo base quando quantizado falha

### ⚠️ Limitação Conhecida
O modelo `multilingual-e5-small-optimized` usa quantização per-layer customizada pela Elastic que requer:
- Suporte específico de quantização do PyTorch (backend `QuantizedCPU`)
- Possivelmente bibliotecas específicas da Elastic
- Versão específica do PyTorch com suporte completo a quantização

**Erro comum:**
```
NotImplementedError: Could not run 'aten::_empty_affine_quantized' with arguments from the 'QuantizedMeta' backend
```

## Solução Atual

O sistema implementa **fallback automático**:

1. Detecta modelo quantizado
2. Tenta carregar com `QuantizedModelLoader`
3. Se falhar (erro de quantização), faz fallback para modelo base `intfloat/multilingual-e5-small`
4. Logs informativos em cada etapa

## Como Funciona

### Detecção de Quantização

O sistema detecta modelos quantizados através de:
- Nome do modelo ("optimized", "quantized")
- Conteúdo do README.md (menção a "quantized")
- Presença de `quantization_config.json`
- Estrutura do arquivo `pytorch_model.bin`

### Carregamento

Quando um modelo quantizado é detectado:

```python
from app.llm.quantized_model_loader import QuantizedModelLoader

loader = QuantizedModelLoader(
    model_path="./models/elastic/multilingual-e5-small-optimized",
    device="cpu"
)

embeddings = loader.encode(["texto de exemplo"])
```

### Integração Automática

O `FastIndexer` e `VectorKnowledgeGraph` detectam automaticamente e usam o carregador apropriado:

```python
# Automático - detecta e usa QuantizedModelLoader se necessário
fast_indexer = FastIndexer(
    knowledge_graph=kg,
    embedding_model=None  # Usa padrão (pode ser quantizado)
)
```

## Alternativas

### Opção 1: Usar Modelo Base (Recomendado)
O modelo base `intfloat/multilingual-e5-small` funciona perfeitamente:

```python
fast_indexer = FastIndexer(
    knowledge_graph=kg,
    embedding_model="intfloat/multilingual-e5-small"
)
```

### Opção 2: Aguardar Suporte Completo
O modelo optimized pode funcionar no futuro quando:
- PyTorch adicionar suporte completo ao formato de quantização usado
- Bibliotecas específicas da Elastic estiverem disponíveis
- Versão customizada do PyTorch for disponibilizada

## Arquitetura Técnica

### QuantizedModelLoader

**Localização:** `app/llm/quantized_model_loader.py`

**Características:**
- Carrega modelo via `transformers.AutoModel` diretamente
- Usa `weights_only=False` para permitir tensores quantizados
- Implementa interface compatível com `SentenceTransformer`
- Faz mean pooling manual para embeddings de sentença

**Interface:**
```python
class QuantizedModelLoader:
    def encode(
        self,
        sentences: Union[str, List[str]],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        convert_to_numpy: bool = True
    ) -> np.ndarray

    def get_sentence_embedding_dimension(self) -> int
```

### Detecção

**Localização:** `app/llm/quantized_model_detector.py`

**Função principal:**
```python
def is_quantized_model(model_path: Path) -> bool
```

## Testes

### Teste de Integração
```bash
python3 examples/test_quantized_embeddings.py
```

### Testes Unitários
```bash
pytest tests/llm/test_quantized_model_loader.py
```

## Troubleshooting

### Erro: "aten::_empty_affine_quantized"
**Causa:** PyTorch não tem suporte completo ao formato de quantização usado.

**Solução:** O sistema faz fallback automático para modelo base. Se quiser forçar modelo base:
```python
embedding_model="intfloat/multilingual-e5-small"
```

### Erro: "tokenizer.json" vazio
**Causa:** Arquivo é ponteiro LFS não baixado.

**Solução:** O sistema usa tokenizer do modelo base automaticamente como fallback.

### Erro: "weights_only"
**Causa:** PyTorch 2.6+ requer weights_only=True por padrão.

**Solução:** O `QuantizedModelLoader` usa `weights_only=False` automaticamente (apenas modelos locais).

## Referências

- [Elastic ELSERv2 Quantization](https://www.elastic.co/search-labs/blog/articles/introducing-elser-v2-part-1#quantization)
- [PyTorch Quantization](https://pytorch.org/docs/stable/quantization.html)
- [Modelo Base](https://huggingface.co/intfloat/multilingual-e5-small)
- [Modelo Optimized](https://huggingface.co/elastic/multilingual-e5-small-optimized)

