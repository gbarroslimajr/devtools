# Oracle Relationship Mapper

Script Python para gerar mapas de relacionamentos entre objetos de um schema Oracle. Analisa arquivos DDL extraídos pelo [Oracle Schema Exporter](../Oracle_Schema_Exporter/) e identifica dependências e relacionamentos entre tabelas, views, procedures, functions, packages, triggers, sequences e outros objetos.

## Funcionalidades

- **Análise Automática**: Detecta relacionamentos entre objetos do banco de dados
- **Múltiplos Formatos de Saída**: Gera relatórios em JSON, DOT (Graphviz) e Markdown
- **Tipos de Relacionamentos Detectados**:
  - Foreign Keys entre tabelas
  - Dependências de views (SELECT, FROM, JOIN)
  - Chamadas entre procedures e functions
  - Operações DML (INSERT, UPDATE, DELETE)
  - Uso de sequences (NEXTVAL, CURRVAL)
  - Triggers e suas tabelas associadas
  - Conteúdo de packages

## Requisitos

- Python 3.7+
- Bibliotecas Python (instalar via `pip install -r scripts/requirements.txt`):
  - `networkx` - Análise e manipulação de grafos
  - `tqdm` - Barras de progresso
  - `python-dotenv` - Variáveis de ambiente (opcional)

## Instalação

1. Clone ou baixe o repositório
2. Instale as dependências:

```bash
cd Scripts/Python/Oracle_Relationship_Mapper
pip install -r scripts/requirements.txt
```

## Pré-requisitos

Antes de executar este script, você precisa ter executado o **Oracle Schema Exporter** para gerar os arquivos DDL. O script procura os arquivos no diretório:

```
../Oracle_Schema_Exporter/output/{schema}/
```

## Uso

### Execução Básica

```bash
python scripts/generate_relationship_map.py
```

O script irá:
1. Procurar automaticamente por schemas no diretório `output/` do Oracle Schema Exporter
2. Processar cada schema encontrado
3. Gerar mapas de relacionamentos em múltiplos formatos

### Estrutura de Saída

Os mapas são gerados no diretório `maps/{schema}/` com os seguintes arquivos:

- **`relationships.json`**: Estrutura completa de relacionamentos em formato JSON
  - Lista de objetos por tipo
  - Lista completa de relacionamentos
  - Estatísticas e métricas do grafo
  - Objetos mais referenciados
  - Objetos isolados

- **`relationships.dot`**: Arquivo DOT para visualização com Graphviz
  - Nós coloridos por tipo de objeto
  - Arestas rotuladas com tipo de relacionamento
  - Pode ser visualizado com ferramentas como `dot`, `neato`, ou online

- **`relationships.md`**: Relatório em Markdown
  - Estatísticas gerais
  - Tabelas de objetos por tipo
  - Top 10 objetos mais referenciados
  - Top 10 objetos que mais referenciam outros
  - Lista de objetos isolados
  - Relacionamentos por tipo
  - Amostra de relacionamentos (primeiros 100)

### Visualizando o Grafo DOT

Para visualizar o arquivo DOT, você pode usar:

```bash
# Instalar Graphviz (se ainda não tiver)
# macOS: brew install graphviz
# Ubuntu/Debian: sudo apt-get install graphviz
# Windows: baixar de https://graphviz.org/download/

# Gerar imagem PNG
dot -Tpng maps/{schema}/relationships.dot -o maps/{schema}/relationships.png

# Gerar imagem SVG
dot -Tsvg maps/{schema}/relationships.dot -o maps/{schema}/relationships.svg

# Gerar PDF
dot -Tpdf maps/{schema}/relationships.dot -o maps/{schema}/relationships.pdf
```

Ou use ferramentas online como:
- [Graphviz Online](https://dreampuf.github.io/GraphvizOnline/)
- [WebGraphviz](http://www.webgraphviz.com/)

## Tipos de Relacionamentos

O script detecta os seguintes tipos de relacionamentos:

| Tipo | Descrição | Exemplo |
|------|-----------|---------|
| `FOREIGN_KEY` | Chave estrangeira entre tabelas | `REFERENCES TABLE_B` |
| `SELECT_FROM` | SELECT de uma tabela | `SELECT * FROM TABLE_A` |
| `JOIN` | JOIN com uma tabela | `JOIN TABLE_B ON ...` |
| `INSERT_INTO` | INSERT em uma tabela | `INSERT INTO TABLE_A` |
| `UPDATE` | UPDATE em uma tabela | `UPDATE TABLE_A SET ...` |
| `DELETE_FROM` | DELETE de uma tabela | `DELETE FROM TABLE_A` |
| `TRIGGER_ON` | Trigger associado a uma tabela | `CREATE TRIGGER ... ON TABLE_A` |
| `VIEW_DEPENDS` | View que depende de tabela/view | View que faz SELECT de tabela |
| `CALLS` | Chamada a procedure/function | `CALL PROCEDURE_NAME()` |
| `USES_SEQUENCE` | Uso de sequence | `SEQUENCE_NAME.NEXTVAL` |
| `CONTAINS_PROCEDURE` | Package contém procedure | Package com definição de procedure |
| `CONTAINS_FUNCTION` | Package contém function | Package com definição de function |

## Estrutura do Projeto

```
Oracle_Relationship_Mapper/
├── scripts/
│   ├── generate_relationship_map.py  # Script principal
│   └── requirements.txt               # Dependências Python
├── maps/                              # Mapas gerados (criado automaticamente)
│   └── {schema}/
│       ├── relationships.json
│       ├── relationships.dot
│       └── relationships.md
├── log/                               # Logs (criado automaticamente)
│   └── relationship_map_YYYYMMDD_HHMMSS.log
└── README.md                          # Este arquivo
```

## Logs

O script gera logs detalhados em `log/relationship_map_YYYYMMDD_HHMMSS.log` com:
- Informações sobre arquivos lidos
- Relacionamentos detectados
- Erros e avisos
- Estatísticas do processamento

## Exemplo de Saída JSON

```json
{
  "schema": "MY_SCHEMA",
  "generated_at": "2024-01-15T10:30:00",
  "statistics": {
    "total_objects": 150,
    "total_relationships": 320,
    "objects_by_type": {
      "tables": 50,
      "views": 20,
      "procedures": 30,
      "functions": 15,
      ...
    }
  },
  "relationships": [
    {
      "source": "PROC_INSERT_USER",
      "target": "USERS",
      "type": "INSERT_INTO",
      "source_type": "procedures"
    },
    ...
  ],
  "graph_metrics": {
    "most_referenced": [...],
    "most_referencing": [...],
    "isolated_objects": [...]
  }
}
```

## Solução de Problemas

### Erro: "Diretório de output não encontrado"

Certifique-se de que você executou o `extract_oracle_objects.py` primeiro e que os arquivos DDL estão em `../Oracle_Schema_Exporter/output/{schema}/`.

### Erro: "Nenhum schema encontrado"

Verifique se há diretórios de schemas dentro do diretório `output/` do Oracle Schema Exporter.

### Relacionamentos não detectados

O script usa expressões regulares para detectar relacionamentos. Alguns padrões complexos ou não convencionais podem não ser detectados. Verifique os logs para mais detalhes.

## Limitações

- A detecção de relacionamentos é baseada em análise de texto (regex), não em análise sintática completa
- Alguns padrões complexos de PL/SQL podem não ser detectados
- Chamadas dinâmicas (EXECUTE IMMEDIATE) não são detectadas
- Referências a objetos de outros schemas podem não ser identificadas corretamente se não estiverem qualificadas

## Contribuindo

Para melhorar a detecção de relacionamentos, você pode:
- Adicionar novos padrões regex nas funções de extração
- Melhorar a normalização de nomes de objetos
- Adicionar suporte a novos tipos de relacionamentos

## Licença

Este projeto faz parte do repositório devtools.

## Relacionado

- [Oracle Schema Exporter](../Oracle_Schema_Exporter/) - Script para extrair objetos DDL do Oracle

