# CodeGraphAI 🔍

> Análise inteligente de procedures de banco de dados usando IA local

CodeGraphAI é uma ferramenta Python que utiliza LLMs (Large Language Models) para analisar, mapear e visualizar dependências entre stored procedures de bancos de dados. Identifica relacionamentos, calcula complexidade e gera hierarquias de baixo até alto nível automaticamente.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)

## ✨ Funcionalidades

- 🤖 **Análise com IA Local** - Usa modelos LLM (GPT-OSS-120B, Llama, etc.) para entender lógica de negócio
- 📊 **Mapeamento de Dependências** - Identifica chamadas entre procedures e acessos a tabelas
- 🎯 **Hierarquia Bottom-Up** - Organiza procedures do nível mais baixo (sem dependências) até alto nível
- 📈 **Cálculo de Complexidade** - Score de 1-10 baseado em estrutura e lógica do código
- 🎨 **Visualizações Mermaid** - Gera diagramas interativos em markdown
- 💾 **Análise de Arquivos** - Trabalha com arquivos `.prc` locais (sem necessidade de conexão ao banco)
- 🔄 **Agnóstico de Banco** - Suporta Oracle, PostgreSQL, SQL Server e MySQL através de adaptadores

## 🚀 Quick Start

### Instalação

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/CodeGraphAI.git
cd CodeGraphAI

# Crie ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Instale dependências
pip install -r requirements.txt

# Configure variáveis de ambiente
# Copie o arquivo de exemplo e preencha com suas credenciais
cp example.env .env
# ou
cp example.env environment.env
# Edite .env ou environment.env com suas credenciais reais
```

### Uso Básico

```python
from analyzer import LLMAnalyzer, ProcedureAnalyzer

# 1. Inicializa analisador com modelo local
llm = LLMAnalyzer(
    model_name="gpt-oss-120b",  # ou caminho local
    device="cuda"
)

# 2. Cria analisador de procedures
analyzer = ProcedureAnalyzer(llm)

# 3. Analisa procedures de arquivos .prc
analyzer.analyze_from_files("./procedures", extension="prc")

# 4. Exporta resultados
analyzer.export_results("analysis.json")
analyzer.export_mermaid_diagram("diagram.md")
analyzer.export_mermaid_hierarchy("hierarchy.md")
```

## 📋 Requisitos

### Dependências Python

```txt
# Bancos de Dados (opcional - instale apenas os necessários)
oracledb>=1.4.0              # Oracle
psycopg2-binary>=2.9.0       # PostgreSQL
pyodbc>=5.0.0                # SQL Server (via ODBC)
mysql-connector-python>=8.0.0  # MySQL

# LangChain - Framework para LLM
langchain>=0.1.0
langchain-community>=0.0.13

# Transformers e PyTorch - Modelos de IA
transformers>=4.35.0
torch>=2.0.0
accelerate>=0.25.0
bitsandbytes>=0.41.0         # Para quantização 8-bit

# Análise de Grafos
networkx>=3.0

# Visualização
matplotlib>=3.7.0

# CLI e Utilitários
click>=8.0.0
tqdm>=4.65.0
python-dotenv>=1.0.0
```

### Hardware Recomendado

- **GPU**: NVIDIA com 24GB+ VRAM para modelos 120B (ou use quantização)
- **CPU**: 16+ cores para processamento paralelo
- **RAM**: 32GB+ recomendado
- **Storage**: Depende do tamanho do modelo

## 📂 Estrutura do Projeto

```
CodeGraphAI/
├── app/                    # Módulos principais
│   ├── core/              # Modelos e exceções
│   │   └── models.py
│   ├── io/                # Adaptadores de banco de dados
│   │   ├── base.py        # Interface abstrata
│   │   ├── factory.py     # Factory pattern
│   │   ├── oracle_loader.py
│   │   ├── postgres_loader.py
│   │   ├── mssql_loader.py
│   │   ├── mysql_loader.py
│   │   └── file_loader.py
│   └── config/            # Configuração
│       └── config.py
├── analyzer.py            # Script principal (backward compatibility)
├── main.py                # CLI
├── config.py              # Wrapper de compatibilidade
├── requirements.txt       # Dependências
├── requirements-dev.txt   # Dependências de desenvolvimento
├── README.md              # Este arquivo
├── procedures/            # Diretório com arquivos .prc
│   ├── core/
│   │   ├── calc_saldo.prc
│   │   └── valida_cliente.prc
│   └── reports/
│       └── gera_relatorio.prc
├── output/                # Resultados gerados
│   ├── analysis.json
│   ├── diagram.md
│   └── hierarchy.md
└── tests/                 # Testes
    ├── io/               # Testes dos adaptadores
    └── test_*.py
```

## 🎯 Casos de Uso

### 1. Análise de Arquivos Locais (Recomendado)

```python
analyzer = ProcedureAnalyzer(llm)
analyzer.analyze_from_files("./procedures", "prc")
```

**Vantagens:**

- ✅ Mais rápido (sem latência de rede)
- ✅ Funciona offline
- ✅ Versionável com Git
- ✅ Sem necessidade de credenciais

### 2. Análise Direta do Banco

```python
analyzer.analyze_from_database(
    user="usuario",
    password="senha",
    dsn="localhost:1521/ORCL",
    schema="MEU_SCHEMA"
)
```

**Quando usar:**

- Procedures não estão em arquivos
- Precisa de metadados adicionais do banco
- Análise ad-hoc de ambiente de produção

### 3. Análise Híbrida

```python
# Carrega de arquivos
analyzer.analyze_from_files("./procedures")

# Compara com banco para validar sincronização
from analyzer import ProcedureLoader
db_procs = ProcedureLoader.from_database(user, password, dsn)

file_set = set(analyzer.procedures.keys())
db_set = set(db_procs.keys())

print(f"Apenas em arquivos: {file_set - db_set}")
print(f"Apenas no banco: {db_set - file_set}")
```

## 📊 Tipos de Visualização

### 1. Diagrama de Dependências

```python
analyzer.export_mermaid_diagram("diagram.md", max_nodes=50)
```

Gera grafo mostrando todas as dependências com cores por complexidade:

- 🔴 **Vermelho**: Alta complexidade (8-10)
- 🟡 **Amarelo**: Média complexidade (5-7)
- 🟢 **Verde**: Baixa complexidade (1-4)

### 2. Hierarquia por Níveis

```python
analyzer.export_mermaid_hierarchy("hierarchy.md")
```

Organiza procedures em árvore hierárquica:

- **Nível 0**: Procedures base (sem dependências)
- **Nível 1**: Dependem apenas do nível 0
- **Nível N**: Dependem até o nível N-1

### 3. Flowchart Detalhado

```python
analyzer.export_mermaid_flowchart("SCHEMA.PROCEDURE_NAME")
```

Mostra fluxo completo de uma procedure:

- Parâmetros de entrada/saída
- Tabelas acessadas
- Procedures chamadas
- Lógica de negócio

## 🔧 Configuração Avançada

### Configuração de Ambiente

CodeGraphAI usa variáveis de ambiente para configuração. O projeto inclui um arquivo `example.env` como template.

**Primeiros passos:**

1. Copie o arquivo de exemplo:
```bash
cp example.env .env
# ou
cp example.env environment.env
```

2. Edite o arquivo copiado (`.env` ou `environment.env`) com suas credenciais reais:
   - API keys para OpenAI, Anthropic ou GenFactory
   - Credenciais de banco de dados
   - Caminhos de certificados SSL (se necessário)

3. **IMPORTANTE**: Os arquivos `.env` e `environment.env` estão no `.gitignore` e não serão commitados. Nunca commite credenciais reais!

**Ordem de prioridade:**
- O sistema carrega primeiro `.env` (se existir)
- Se `.env` não existir, carrega `environment.env`
- Se nenhum existir, usa valores padrão

**Arquivos:**
- `example.env`: Template versionado no Git (sem credenciais)
- `.env`: Suas credenciais locais (não versionado)
- `environment.env`: Suas credenciais locais (não versionado)

### Suporte a Múltiplos Bancos de Dados

CodeGraphAI suporta múltiplos bancos de dados através de adaptadores:

- **Oracle**: Usa `oracledb` (padrão para backward compatibility)
- **PostgreSQL**: Usa `psycopg2-binary`
- **SQL Server**: Usa `pyodbc` ou `pymssql`
- **MySQL**: Usa `mysql-connector-python` ou `pymysql`

**Instalação de drivers:**
```bash
# Instalar apenas o necessário
pip install oracledb>=1.4.0                    # Oracle
pip install psycopg2-binary>=2.9.0              # PostgreSQL
pip install pyodbc>=5.0.0                       # SQL Server
pip install mysql-connector-python>=8.0.0       # MySQL
```

**Uso via CLI:**
```bash
# Oracle (padrão)
python main.py analyze-db --user user --password pass --dsn localhost:1521/ORCL

# PostgreSQL
python main.py analyze-db --db-type postgresql --user user --password pass \
    --host localhost --port 5432 --database meu_banco

# SQL Server
python main.py analyze-db --db-type mssql --user user --password pass \
    --host localhost --port 1433 --database meu_banco

# MySQL
python main.py analyze-db --db-type mysql --user user --password pass \
    --host localhost --port 3306 --database meu_banco
```

**Variáveis de ambiente:**
```bash
CODEGRAPHAI_DB_TYPE=postgresql
CODEGRAPHAI_DB_HOST=localhost
CODEGRAPHAI_DB_PORT=5432
CODEGRAPHAI_DB_NAME=meu_banco
CODEGRAPHAI_DB_USER=usuario
CODEGRAPHAI_DB_PASSWORD=senha
CODEGRAPHAI_DB_SCHEMA=public
```

### Modelos LLM Suportados

#### Modo Local (HuggingFace)

```python
# Modelos Locais
llm = LLMAnalyzer(model_name="gpt-oss-120b", device="cuda")
llm = LLMAnalyzer(model_name="meta-llama/Llama-2-70b-hf", device="cuda")
llm = LLMAnalyzer(model_name="mistralai/Mixtral-8x7B-v0.1", device="cuda")

# Caminho local
llm = LLMAnalyzer(model_name="/path/to/local/model", device="cuda")

# CPU (mais lento)
llm = LLMAnalyzer(model_name="gpt-oss-120b", device="cpu")
```

#### Modo API (GenFactory - BNP Paribas)

CodeGraphAI suporta LLM via API GenFactory, permitindo usar modelos remotos sem necessidade de GPU local.

**Configuração:**

1. Copie `example.env` para `.env` ou `environment.env` e configure:
```bash
# Copie o template
cp example.env .env
# ou
cp example.env environment.env

# Edite o arquivo com suas credenciais
CODEGRAPHAI_LLM_MODE=api
CODEGRAPHAI_LLM_PROVIDER=genfactory_llama70b  # ou genfactory_codestral, genfactory_gptoss120b

# Provider: Llama 70B
CODEGRAPHAI_GENFACTORY_LLAMA70B_BASE_URL=https://genfactory-ai.analytics.cib.echonet/genai/api/v2
CODEGRAPHAI_GENFACTORY_LLAMA70B_MODEL=meta-llama-3.3-70b-instruct
CODEGRAPHAI_GENFACTORY_LLAMA70B_AUTHORIZATION_TOKEN=seu_token_aqui
CODEGRAPHAI_GENFACTORY_LLAMA70B_TIMEOUT=20000
CODEGRAPHAI_GENFACTORY_LLAMA70B_VERIFY_SSL=true
CODEGRAPHAI_GENFACTORY_LLAMA70B_CA_BUNDLE_PATH=caminho/cert1.cer;caminho/cert2.cer
```

2. Use no código:
```python
from analyzer import LLMAnalyzer
from config import get_config

config = get_config()
llm = LLMAnalyzer(llm_mode='api', config=config)
```

**Providers Disponíveis:**
- `genfactory_llama70b`: Meta Llama 3.3 70B Instruct
- `genfactory_codestral`: Codestral Latest
- `genfactory_gptoss120b`: GPT-OSS-120B

**Vantagens do Modo API:**
- Não requer GPU local
- Não requer download de modelos grandes
- Acesso a modelos atualizados
- Escalabilidade automática

#### Modo API (OpenAI)

CodeGraphAI suporta modelos OpenAI via API, incluindo os modelos mais recentes (gpt-5.1, gpt-5-mini, gpt-5-nano).

**Configuração:**

1. Copie `example.env` para `.env` ou `environment.env` e configure:
```bash
# Copie o template
cp example.env .env
# ou
cp example.env environment.env

# Edite o arquivo com suas credenciais
CODEGRAPHAI_LLM_MODE=api
CODEGRAPHAI_LLM_PROVIDER=openai

# OpenAI Configuration
CODEGRAPHAI_OPENAI_API_KEY=sk-...
CODEGRAPHAI_OPENAI_MODEL=gpt-5.1  # ou gpt-5-mini, gpt-5-nano
CODEGRAPHAI_OPENAI_BASE_URL=https://api.openai.com/v1  # Opcional para Azure OpenAI
CODEGRAPHAI_OPENAI_TIMEOUT=60
CODEGRAPHAI_OPENAI_TEMPERATURE=0.3
CODEGRAPHAI_OPENAI_MAX_TOKENS=4000
```

2. Use no código:
```python
from analyzer import LLMAnalyzer
from config import get_config

config = get_config()
llm = LLMAnalyzer(llm_mode='api', config=config)
```

**Modelos Disponíveis:**
- `gpt-5.1`: Modelo mais recente e mais capaz (padrão)
- `gpt-5-mini`: Versão mais rápida e econômica, ideal para tarefas simples
- `gpt-5-nano`: Versão mais compacta, para uso em larga escala

**Quando usar cada modelo:**
- **gpt-5.1**: Para análises complexas que requerem maior capacidade de raciocínio
- **gpt-5-mini**: Para análises rápidas e tarefas simples
- **gpt-5-nano**: Para processamento em larga escala com muitos procedures

**Azure OpenAI:**
Para usar Azure OpenAI, configure `CODEGRAPHAI_OPENAI_BASE_URL` com o endpoint do Azure:
```bash
CODEGRAPHAI_OPENAI_BASE_URL=https://seu-recurso.openai.azure.com/
```

**Referência:** [LangChain OpenAI Documentation](https://docs.langchain.com/oss/python/langchain/models)

#### Modo API (Anthropic Claude)

CodeGraphAI suporta Anthropic Claude via API, incluindo o modelo mais recente Claude Sonnet 4.5.

**Configuração:**

1. Copie `example.env` para `.env` ou `environment.env` e configure:
```bash
# Copie o template
cp example.env .env
# ou
cp example.env environment.env

# Edite o arquivo com suas credenciais
CODEGRAPHAI_LLM_MODE=api
CODEGRAPHAI_LLM_PROVIDER=anthropic

# Anthropic Claude Configuration
CODEGRAPHAI_ANTHROPIC_API_KEY=sk-ant-...
CODEGRAPHAI_ANTHROPIC_MODEL=claude-sonnet-4-5-20250929
CODEGRAPHAI_ANTHROPIC_TIMEOUT=60
CODEGRAPHAI_ANTHROPIC_TEMPERATURE=0.3
CODEGRAPHAI_ANTHROPIC_MAX_TOKENS=4000
```

2. Use no código:
```python
from analyzer import LLMAnalyzer
from config import get_config

config = get_config()
llm = LLMAnalyzer(llm_mode='api', config=config)
```

**Modelo Disponível:**
- `claude-sonnet-4-5-20250929`: Claude Sonnet 4.5 (modelo mais recente, padrão)
- `claude-sonnet-4-5`: Alias para o modelo mais recente

**Vantagens do Claude Sonnet 4.5:**
- Excelente para análise de código e raciocínio complexo
- Suporte a contextos longos
- Alta qualidade em tarefas de análise e extração

**Referência:** [LangChain Anthropic Documentation](https://docs.langchain.com/oss/python/langchain/models)

### Quantização para Economia de Memória

Por padrão, usa quantização 8-bit. Para modelos menores:

```python
# Desabilitar quantização (requer mais VRAM)
# Edite em analyzer.py:
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    device_map="auto",
    load_in_8bit=False,  # Altere aqui
    torch_dtype="auto"
)
```

### Ajuste de Prompts

Edite os templates em `LLMAnalyzer._setup_prompts()` para customizar análises:

```python
self.business_logic_prompt = PromptTemplate(
    input_variables=["code", "proc_name"],
    template="""Seu prompt customizado aqui..."""
)
```

## 📈 Exemplo de Output

### JSON (analysis.json)

```json
{
  "procedures": {
    "CALC_SALDO": {
      "name": "CALC_SALDO",
      "schema": "FINANCEIRO",
      "complexity_score": 7,
      "dependencies_level": 0,
      "called_procedures": ["VALIDA_CONTA", "BUSCA_HISTORICO"],
      "called_tables": ["CONTAS", "TRANSACOES"],
      "business_logic": "Calcula saldo atual de uma conta..."
    }
  },
  "hierarchy": {
    "0": ["CALC_SALDO", "VALIDA_CONTA"],
    "1": ["GERA_RELATORIO"],
    "2": ["EXPORTA_DADOS"]
  },
  "statistics": {
    "total_procedures": 45,
    "avg_complexity": 5.8,
    "max_dependency_level": 4
  }
}
```

### Mermaid Diagram

```mermaid
graph TD
    CALC_SALDO["CALC_SALDO\n[Nível 0, Complex: 7]"]:::medium
    VALIDA_CONTA["VALIDA_CONTA\n[Nível 0, Complex: 3]"]:::low
    GERA_RELATORIO["GERA_RELATORIO\n[Nível 1, Complex: 9]"]:::high

    GERA_RELATORIO --> CALC_SALDO
    GERA_RELATORIO --> VALIDA_CONTA

    classDef high fill:#ff6b6b,stroke:#c92a2a,color:#fff
    classDef medium fill:#ffd93d,stroke:#f59f00,color:#000
    classDef low fill:#51cf66,stroke:#2b8a3e,color:#000
```

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor:

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 🗺
