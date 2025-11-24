# CodeGraphAI - API Catalog

## Table of Contents

- [Overview](#overview)
- [Core Classes](#core-classes)
- [I/O Classes](#io-classes)
- [Analysis Classes](#analysis-classes)
- [Configuration](#configuration)
- [Exceptions](#exceptions)
- [Related Documentation](#related-documentation)

---

## Overview

Este documento fornece uma referência completa das APIs públicas do CodeGraphAI. Todas as classes e métodos documentados aqui são parte da API pública e podem ser usados por código externo.

---

## Core Classes

### `ProcedureInfo`

**Localização:** `app/core/models.py`

**Descrição:** Dataclass que armazena informações sobre uma stored procedure analisada.

**Atributos:**

| Atributo | Tipo | Descrição |
|----------|------|-----------|
| `name` | `str` | Nome da procedure |
| `schema` | `str` | Schema do banco de dados |
| `source_code` | `str` | Código-fonte completo |
| `parameters` | `List[Dict[str, str]]` | Lista de parâmetros (nome, tipo, direção) |
| `called_procedures` | `Set[str]` | Procedures chamadas por esta |
| `called_tables` | `Set[str]` | Tabelas acessadas |
| `business_logic` | `str` | Descrição da lógica de negócio (gerada por LLM) |
| `complexity_score` | `int` | Score de complexidade (1-10) |
| `dependencies_level` | `int` | Nível hierárquico (0 = sem dependências) |

**Exemplo:**
```python
from app.core.models import ProcedureInfo

procedure = ProcedureInfo(
    name="calc_saldo",
    schema="core",
    source_code="CREATE PROCEDURE...",
    parameters=[{"name": "conta_id", "type": "INT", "direction": "IN"}],
    called_procedures={"valida_conta"},
    called_tables={"contas", "transacoes"},
    business_logic="Calcula saldo da conta...",
    complexity_score=7,
    dependencies_level=0
)
```

### `DatabaseConfig`

**Localização:** `app/core/models.py`

**Descrição:** Dataclass para configuração de conexão com banco de dados.

**Atributos:**

| Atributo | Tipo | Descrição |
|----------|------|-----------|
| `db_type` | `DatabaseType` | Tipo de banco (Enum) |
| `user` | `str` | Usuário do banco |
| `password` | `str` | Senha do banco |
| `host` | `str` | Host ou DSN |
| `port` | `Optional[int]` | Porta (opcional) |
| `database` | `Optional[str]` | Nome do banco (opcional) |
| `schema` | `Optional[str]` | Schema específico (opcional) |
| `extra_params` | `Dict[str, str]` | Parâmetros extras (opcional) |

**Métodos:**

- `get_connection_string() -> str`: Retorna string de conexão formatada

**Exemplo:**
```python
from app.core.models import DatabaseConfig, DatabaseType

config = DatabaseConfig(
    db_type=DatabaseType.POSTGRESQL,
    user="usuario",
    password="senha",
    host="localhost",
    port=5432,
    database="meu_banco"
)
```

### `DatabaseType`

**Localização:** `app/core/models.py`

**Descrição:** Enum com tipos de banco de dados suportados.

**Valores:**
- `ORACLE = "oracle"`
- `POSTGRESQL = "postgresql"`
- `MSSQL = "mssql"`
- `MYSQL = "mysql"`

---

## I/O Classes

### `ProcedureLoaderBase`

**Localização:** `app/io/base.py`

**Descrição:** Interface abstrata para carregadores de procedures.

**Métodos Abstratos:**

- `load_procedures(config: DatabaseConfig) -> Dict[str, str]`: Carrega procedures do banco
- `get_database_type() -> DatabaseType`: Retorna tipo de banco suportado

**Métodos Concretos:**

- `test_connection(config: DatabaseConfig) -> bool`: Testa conexão
- `validate_config(config: DatabaseConfig) -> None`: Valida configuração

### `ProcedureLoader`

**Localização:** `analyzer.py` (wrapper para backward compatibility)

**Descrição:** Classe estática para carregar procedures (mantida para compatibilidade).

**Métodos Estáticos:**

- `from_files(directory_path: str, extension: str = "prc") -> Dict[str, str]`
- `from_database(user: str, password: str, dsn: str, schema: Optional[str] = None, db_type: Optional[str] = None) -> Dict[str, str]`

**Exemplo:**
```python
from analyzer import ProcedureLoader

# De arquivos
procedures = ProcedureLoader.from_files("./procedures", "prc")

# De banco
procedures = ProcedureLoader.from_database(
    user="usuario",
    password="senha",
    dsn="localhost:1521/ORCL",
    schema="MEU_SCHEMA"
)
```

### Factory Functions

**Localização:** `app/io/factory.py`

**Funções:**

- `create_loader(db_type: DatabaseType) -> ProcedureLoaderBase`: Cria loader baseado no tipo
- `get_available_loaders() -> List[DatabaseType]`: Lista loaders disponíveis

**Exemplo:**
```python
from app.io.factory import create_loader
from app.core.models import DatabaseType

loader = create_loader(DatabaseType.ORACLE)
procedures = loader.load_procedures(config)
```

---

## Analysis Classes

### `LLMAnalyzer`

**Localização:** `analyzer.py`

**Descrição:** Analisador de código usando LLM (local ou via API).

**Construtor:**
```python
LLMAnalyzer(
    model_name: Optional[str] = None,
    device: Optional[str] = None,
    llm_mode: Optional[str] = None,
    config: Optional[Config] = None
)
```

**Métodos:**

- `analyze_business_logic(code: str, proc_name: str) -> str`: Analisa lógica de negócio
- `extract_dependencies(code: str) -> Tuple[Set[str], Set[str]]`: Extrai dependências
- `analyze_complexity(code: str, proc_name: str) -> int`: Calcula complexidade

**Exemplos:**

**Modo Local (backward compatible):**
```python
from analyzer import LLMAnalyzer

# Forma antiga (ainda funciona)
llm = LLMAnalyzer(model_name="gpt-oss-120b", device="cuda")

# Forma nova
llm = LLMAnalyzer(model_name="gpt-oss-120b", device="cuda", llm_mode="local")
```

**Modo API (GenFactory, OpenAI, Anthropic):**
```python
from analyzer import LLMAnalyzer
from config import get_config

config = get_config()
config.llm_mode = 'api'
config.llm_provider = 'openai'  # ou 'anthropic', 'genfactory_llama70b', etc.

llm = LLMAnalyzer(llm_mode="api", config=config)
logic = llm.analyze_business_logic(code, "calc_saldo")
```

**Exemplo com OpenAI:**
```python
from analyzer import LLMAnalyzer
from config import get_config

config = get_config()
config.llm_mode = 'api'
config.llm_provider = 'openai'
config.openai = {
    'api_key': 'sk-...',
    'model': 'gpt-5.1',
    'timeout': 60,
    'temperature': 0.3,
    'max_tokens': 4000
}

llm = LLMAnalyzer(config=config)
```

**Exemplo com Anthropic:**
```python
from analyzer import LLMAnalyzer
from config import get_config

config = get_config()
config.llm_mode = 'api'
config.llm_provider = 'anthropic'
config.anthropic = {
    'api_key': 'sk-ant-...',
    'model': 'claude-sonnet-4-5-20250929',
    'timeout': 60,
    'temperature': 0.3,
    'max_tokens': 4000
}

llm = LLMAnalyzer(config=config)
```

### `ProcedureAnalyzer`

**Localização:** `analyzer.py`

**Descrição:** Orquestrador principal da análise de procedures.

**Construtor:**
```python
ProcedureAnalyzer(llm: LLMAnalyzer)
```

**Métodos:**

- `analyze_from_files(directory_path: str, extension: str = "prc") -> None`
- `analyze_from_database(user: str, password: str, dsn: str, schema: Optional[str] = None, limit: Optional[int] = None, db_type: Optional[str] = None) -> None`
- `export_results(output_file: str) -> None`: Exporta JSON
- `visualize_dependencies(output_file: str) -> None`: Exporta grafo PNG
- `export_mermaid_diagram(output_file: str) -> None`: Exporta diagrama Mermaid
- `export_mermaid_hierarchy(output_file: str) -> None`: Exporta hierarquia Mermaid
- `get_procedure_hierarchy() -> Dict[int, List[str]]`: Retorna hierarquia por níveis

**Propriedades:**

- `procedures: Dict[str, ProcedureInfo]`: Dicionário de procedures analisadas

**Exemplo:**
```python
from analyzer import LLMAnalyzer, ProcedureAnalyzer

llm = LLMAnalyzer()
analyzer = ProcedureAnalyzer(llm)

# Analisa arquivos
analyzer.analyze_from_files("./procedures", "prc")

# Exporta resultados
analyzer.export_results("analysis.json")
analyzer.export_mermaid_diagram("diagram.md")
```

---

## Configuration

### `DefaultConfig`

**Localização:** `app/config/config.py`

**Descrição:** Classe com valores padrão centralizados para todas as configurações.

**Atributos Principais:**

| Atributo | Tipo | Valor Padrão | Descrição |
|----------|------|--------------|-----------|
| `MODEL_NAME` | `str` | `'gpt-oss-120b'` | Nome do modelo LLM local |
| `DEVICE` | `str` | `'cuda'` | Dispositivo padrão |
| `LLM_MODE` | `str` | `'local'` | Modo LLM padrão |
| `LLM_PROVIDER` | `str` | `'genfactory_llama70b'` | Provider padrão |
| `OPENAI_MODEL` | `str` | `'gpt-5.1'` | Modelo OpenAI padrão |
| `ANTHROPIC_MODEL` | `str` | `'claude-sonnet-4-5-20250929'` | Modelo Anthropic padrão |
| `DB_TYPE` | `str` | `'oracle'` | Tipo de banco padrão |
| `OUTPUT_DIR` | `str` | `'./output'` | Diretório de saída padrão |
| `LOG_LEVEL` | `str` | `'INFO'` | Nível de log padrão |

**Exemplo:**
```python
from app.config.config import DefaultConfig

# Usar valores padrão
model_name = DefaultConfig.MODEL_NAME
openai_model = DefaultConfig.OPENAI_MODEL
```

### `LLMProvider`

**Localização:** `app/core/models.py`

**Descrição:** Enum com providers LLM disponíveis.

**Valores:**
- `GENFACTORY_LLAMA70B = "genfactory_llama70b"`
- `GENFACTORY_CODESTRAL = "genfactory_codestral"`
- `GENFACTORY_GPTOSS120B = "genfactory_gptoss120b"`
- `OPENAI = "openai"`
- `ANTHROPIC = "anthropic"`

**Métodos:**

- `from_string(value: str) -> LLMProvider`: Cria provider a partir de string com validação

**Exemplo:**
```python
from app.core.models import LLMProvider

# Usar Enum
provider = LLMProvider.OPENAI
assert provider.value == 'openai'

# Validar string
try:
    provider = LLMProvider.from_string('openai')
except ValueError as e:
    print(f"Provider inválido: {e}")
```

### `Config`

**Localização:** `app/config/config.py`

**Descrição:** Classe de configuração centralizada.

**Construtor:**
```python
Config()  # Carrega de .env / environment.env automaticamente
```

**Atributos Principais:**

| Atributo | Tipo | Descrição |
|----------|------|-----------|
| `model_name` | `str` | Nome do modelo LLM |
| `device` | `str` | Dispositivo (cuda/cpu) |
| `db_type` | `DatabaseType` | Tipo de banco padrão |
| `db_host` | `Optional[str]` | Host do banco |
| `db_port` | `Optional[int]` | Porta do banco |
| `output_dir` | `str` | Diretório de saída |
| `llm_mode` | `str` | Modo LLM ('local' ou 'api') |
| `llm_provider` | `str` | Provider LLM selecionado |
| `openai` | `Optional[dict]` | Configuração OpenAI (se modo api) |
| `anthropic` | `Optional[dict]` | Configuração Anthropic (se modo api) |
| `_provider_config_map` | `dict` | Mapeamento de providers para configurações |

**Métodos Helper (estáticos):**

- `_getenv_int(key: str, default: int) -> int`: Obtém variável de ambiente como int
- `_getenv_float(key: str, default: float) -> float`: Obtém variável de ambiente como float
- `_getenv_bool(key: str, default: bool) -> bool`: Obtém variável de ambiente como bool
- `_parse_ca_bundle_path(env_var: str) -> list`: Processa CA bundle path

**Métodos Helper (instância):**

- `_load_genfactory_config(provider_prefix: str, default_name: str, default_model: str) -> dict`: Carrega configuração GenFactory
- `_load_simple_api_config(provider: str, api_key_var: str, model_var: str, default_model: str, ...) -> dict`: Carrega configuração API simples
- `_get_db_value(oracle_var: str, generic_var: str, fallback: Optional[str]) -> Optional[str]`: Obtém valor de banco com fallback

**Função Helper:**

- `get_config() -> Config`: Retorna instância singleton de Config

**Exemplo:**
```python
from app.config.config import get_config

config = get_config()
print(config.model_name)
print(config.openai['model'] if config.openai else 'N/A')
```

---

## LLM Classes

### `GenFactoryClient`

**Localização:** `app/llm/genfactory_client.py`

**Descrição:** Cliente HTTP para API GenFactory.

**Construtor:**
```python
GenFactoryClient(config: Dict[str, Any])
```

**Parâmetros:**
- `config`: Dicionário com configuração:
  - `base_url`: URL base da API
  - `model`: Nome do modelo
  - `authorization_token`: Token de autorização
  - `timeout`: Timeout em milissegundos
  - `verify_ssl`: Se deve verificar SSL
  - `ca_bundle_path`: Lista de caminhos de certificados CA

**Métodos:**
- `chat(messages: List[Dict[str, str]], **kwargs) -> str`: Envia mensagem e retorna resposta

**Exemplo:**
```python
from app.llm.genfactory_client import GenFactoryClient

config = {
    'base_url': 'https://api.example.com',
    'model': 'meta-llama-3.3-70b-instruct',
    'authorization_token': 'token',
    'timeout': 20000,
    'verify_ssl': True,
    'ca_bundle_path': ['/path/to/cert.cer']
}

client = GenFactoryClient(config)
response = client.chat([{'role': 'user', 'content': 'Hello'}])
```

### `GenFactoryLLM`

**Localização:** `app/llm/langchain_wrapper.py`

**Descrição:** Wrapper LangChain para GenFactoryClient, permite usar com LLMChain.

**Construtor:**
```python
GenFactoryLLM(genfactory_client: GenFactoryClient, **kwargs)
```

**Exemplo:**
```python
from app.llm.genfactory_client import GenFactoryClient
from app.llm.langchain_wrapper import GenFactoryLLM

client = GenFactoryClient(config)
llm = GenFactoryLLM(client)
```

### OpenAI Integration

**Localização:** `analyzer.py` (método `_init_openai_llm`)

**Descrição:** Integração com OpenAI usando LangChain `ChatOpenAI`. Suporta modelos mais recentes (gpt-5.1, gpt-5-mini, gpt-5-nano) e Azure OpenAI.

**Configuração via `Config`:**
```python
config.openai = {
    'api_key': 'sk-...',
    'model': 'gpt-5.1',  # ou gpt-5-mini, gpt-5-nano
    'base_url': None,  # Opcional para Azure OpenAI
    'timeout': 60,
    'temperature': 0.3,
    'max_tokens': 4000
}
```

**Modelos Suportados:**
- `gpt-5.1`: Modelo mais recente e mais capaz (padrão)
- `gpt-5-mini`: Versão mais rápida e econômica, ideal para tarefas simples
- `gpt-5-nano`: Versão mais compacta, para uso em larga escala

**Uso:**
```python
from analyzer import LLMAnalyzer
from config import get_config

config = get_config()
config.llm_mode = 'api'
config.llm_provider = 'openai'
config.openai = {
    'api_key': 'sk-...',
    'model': 'gpt-5.1',
    'base_url': None,
    'timeout': 60,
    'temperature': 0.3,
    'max_tokens': 4000
}

llm = LLMAnalyzer(config=config)
```

**Azure OpenAI:**
Para usar Azure OpenAI, configure `base_url`:
```python
config.openai['base_url'] = 'https://seu-recurso.openai.azure.com/'
```

**Referência:** [LangChain OpenAI Documentation](https://docs.langchain.com/oss/python/langchain/models)

### Anthropic Claude Integration

**Localização:** `analyzer.py` (método `_init_anthropic_llm`)

**Descrição:** Integração com Anthropic Claude usando LangChain `ChatAnthropic`. Suporta Claude Sonnet 4.5 (modelo mais recente).

**Configuração via `Config`:**
```python
config.anthropic = {
    'api_key': 'sk-ant-...',
    'model': 'claude-sonnet-4-5-20250929',  # Claude Sonnet 4.5
    'timeout': 60,
    'temperature': 0.3,
    'max_tokens': 4000
}
```

**Modelos Suportados:**
- `claude-sonnet-4-5-20250929`: Claude Sonnet 4.5 (modelo mais recente, padrão)
- `claude-sonnet-4-5`: Alias para o modelo mais recente

**Uso:**
```python
from analyzer import LLMAnalyzer
from config import get_config

config = get_config()
config.llm_mode = 'api'
config.llm_provider = 'anthropic'
config.anthropic = {
    'api_key': 'sk-ant-...',
    'model': 'claude-sonnet-4-5-20250929',
    'timeout': 60,
    'temperature': 0.3,
    'max_tokens': 4000
}

llm = LLMAnalyzer(config=config)
```

**Referência:** [LangChain Anthropic Documentation](https://docs.langchain.com/oss/python/langchain/models)

### Provider Comparison

| Provider | Modelos | Melhor Para | Requisitos |
|----------|---------|-------------|------------|
| **GenFactory** | Llama 70B, Codestral, GPT-OSS-120B | Ambientes corporativos | Token de autorização, certificados SSL |
| **OpenAI** | gpt-5.1, gpt-5-mini, gpt-5-nano | Análises rápidas e escaláveis | API key OpenAI |
| **Anthropic** | Claude Sonnet 4.5 | Análises complexas e raciocínio profundo | API key Anthropic |

---

## Exceptions

Todas as exceções herdam de `CodeGraphAIError`:

**Hierarquia:**
```
CodeGraphAIError (base)
├── ProcedureLoadError
├── LLMAnalysisError
├── DependencyAnalysisError
├── ExportError
└── ValidationError
```

**Localização:** `app/core/models.py`

**Uso:**
```python
from app.core.models import ProcedureLoadError, ValidationError

try:
    loader.load_procedures(config)
except ProcedureLoadError as e:
    print(f"Erro ao carregar: {e}")
except ValidationError as e:
    print(f"Configuração inválida: {e}")
```

---

## Related Documentation

- [Project Overview](project-overview.md) - Visão geral
- [Architecture Details](architecture.md) - Arquitetura
- [Database Adapters](database-adapters.md) - Adaptadores
- [Integration Flows](integration-flows.md) - Exemplos de uso

---

Generated on: 2024-11-23 16:45:00

