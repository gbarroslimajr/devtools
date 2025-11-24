# CodeGraphAI - Database Adapters

## Table of Contents

- [Overview](#overview)
- [Adapter Architecture](#adapter-architecture)
- [Oracle Adapter](#oracle-adapter)
- [PostgreSQL Adapter](#postgresql-adapter)
- [SQL Server Adapter](#sql-server-adapter)
- [MySQL Adapter](#mysql-adapter)
- [File Loader](#file-loader)
- [Adding New Adapters](#adding-new-adapters)
- [Related Documentation](#related-documentation)

---

## Overview

CodeGraphAI usa uma arquitetura baseada em adaptadores para suportar múltiplos bancos de dados. Cada adaptador implementa a interface `ProcedureLoaderBase` e é responsável por:

1. Conectar ao banco de dados específico
2. Listar stored procedures disponíveis
3. Extrair o código-fonte de cada procedure
4. Retornar um dicionário com nome e código das procedures

**Interface Base:** `app/io/base.py`
**Factory:** `app/io/factory.py`
**Documentação Detalhada:** `docs/DATABASE_ADAPTERS.md`

---

## Adapter Architecture

### Interface Abstrata

```python
class ProcedureLoaderBase(ABC):
    @abstractmethod
    def load_procedures(self, config: DatabaseConfig) -> Dict[str, str]:
        """Carrega procedures do banco"""
        pass

    @abstractmethod
    def get_database_type(self) -> DatabaseType:
        """Retorna o tipo de banco suportado"""
        pass
```

### Factory Pattern

```python
from app.io.factory import create_loader
from app.core.models import DatabaseType

loader = create_loader(DatabaseType.ORACLE)
procedures = loader.load_procedures(config)
```

### Registro Automático

Cada adaptador se registra automaticamente ao ser importado usando o decorator `@register_loader`.

---

## Oracle Adapter

**Classe:** `OracleLoader`
**Arquivo:** `app/io/oracle_loader.py`
**Driver:** `oracledb>=1.4.0`

### Instalação

```bash
pip install oracledb>=1.4.0
```

### Configuração

```python
from app.core.models import DatabaseConfig, DatabaseType

config = DatabaseConfig(
    db_type=DatabaseType.ORACLE,
    user="usuario",
    password="senha",
    host="localhost:1521/ORCL",  # DSN completo
    schema="MEU_SCHEMA"  # Opcional
)
```

### Queries SQL

**Listar procedures:**
```sql
SELECT OWNER, OBJECT_NAME
FROM ALL_PROCEDURES
WHERE OBJECT_TYPE = 'PROCEDURE'
  AND (OWNER = :schema OR :schema IS NULL)
```

**Obter código-fonte:**
```sql
SELECT TEXT
FROM ALL_SOURCE
WHERE OWNER = :owner
  AND NAME = :name
ORDER BY LINE
```

### Formato DSN

- `host:port/service` (ex: `localhost:1521/ORCL`)
- Ou apenas `host` se DSN completo estiver configurado no sistema

### Troubleshooting

- **Erro de conexão:** Verifique se o Oracle Instant Client está instalado
- **Procedures não encontradas:** Verifique permissões do usuário (ALL_PROCEDURES, ALL_SOURCE)

---

## PostgreSQL Adapter

**Classe:** `PostgreSQLLoader`
**Arquivo:** `app/io/postgres_loader.py`
**Driver:** `psycopg2-binary>=2.9.0`

### Instalação

```bash
pip install psycopg2-binary>=2.9.0
```

### Configuração

```python
config = DatabaseConfig(
    db_type=DatabaseType.POSTGRESQL,
    user="usuario",
    password="senha",
    host="localhost",
    port=5432,
    database="meu_banco",
    schema="public"  # Opcional, padrão: public
)
```

### Queries SQL

**Listar procedures:**
```sql
SELECT routine_schema, routine_name
FROM information_schema.routines
WHERE routine_type = 'PROCEDURE'
  AND (routine_schema = :schema OR :schema IS NULL)
```

**Obter código-fonte:**
```sql
SELECT pg_get_functiondef(oid) as definition
FROM pg_proc
WHERE proname = :name
  AND pronamespace = (
    SELECT oid FROM pg_namespace WHERE nspname = :schema
  )
```

### Requisitos

- PostgreSQL 11+ (suporte a stored procedures)

---

## SQL Server Adapter

**Classe:** `MSSQLLoader`
**Arquivo:** `app/io/mssql_loader.py`
**Driver:** `pyodbc>=5.0.0` ou `pymssql>=2.2.0`

### Instalação

```bash
pip install pyodbc>=5.0.0
# ou
pip install pymssql>=2.2.0
```

**Nota:** `pyodbc` requer ODBC Driver instalado no sistema.

### Configuração

```python
config = DatabaseConfig(
    db_type=DatabaseType.MSSQL,
    user="usuario",
    password="senha",
    host="localhost",
    port=1433,
    database="meu_banco",
    schema="dbo"  # Opcional, padrão: dbo
)
```

### Queries SQL

**Listar procedures:**
```sql
SELECT ROUTINE_SCHEMA, ROUTINE_NAME
FROM INFORMATION_SCHEMA.ROUTINES
WHERE ROUTINE_TYPE = 'PROCEDURE'
  AND (ROUTINE_SCHEMA = :schema OR :schema IS NULL)
```

**Obter código-fonte:**
```sql
SELECT definition
FROM sys.sql_modules
WHERE object_id = OBJECT_ID(:schema + '.' + :name)
```

### Troubleshooting

- **Erro ODBC:** Instale Microsoft ODBC Driver for SQL Server
- **Autenticação:** Suporta Windows Authentication e SQL Authentication

---

## MySQL Adapter

**Classe:** `MySQLLoader`
**Arquivo:** `app/io/mysql_loader.py`
**Driver:** `mysql-connector-python>=8.0.0` ou `pymysql>=1.0.0`

### Instalação

```bash
pip install mysql-connector-python>=8.0.0
# ou
pip install pymysql>=1.0.0
```

### Configuração

```python
config = DatabaseConfig(
    db_type=DatabaseType.MYSQL,
    user="usuario",
    password="senha",
    host="localhost",
    port=3306,
    database="meu_banco"
    # MySQL não usa schema separado
)
```

### Queries SQL

**Listar procedures:**
```sql
SELECT ROUTINE_SCHEMA, ROUTINE_NAME
FROM INFORMATION_SCHEMA.ROUTINES
WHERE ROUTINE_TYPE = 'PROCEDURE'
  AND ROUTINE_SCHEMA = :database
```

**Obter código-fonte:**
```sql
SELECT ROUTINE_DEFINITION
FROM INFORMATION_SCHEMA.ROUTINES
WHERE ROUTINE_SCHEMA = :database
  AND ROUTINE_NAME = :name
```

### Limitações

- `ROUTINE_DEFINITION` pode estar truncado em algumas versões do MySQL
- Requer permissões em `INFORMATION_SCHEMA`

---

## File Loader

**Classe:** `FileLoader`
**Arquivo:** `app/io/file_loader.py`

### Uso

```python
from app.io.file_loader import FileLoader

procedures = FileLoader.from_files(
    directory_path="./procedures",
    extension="prc"
)
```

### Formato de Arquivo

- Um arquivo por procedure
- Nome do arquivo = nome da procedure
- Extensão padrão: `.prc`
- Encoding: UTF-8

### Estrutura de Diretório

```
procedures/
├── core/
│   ├── calc_saldo.prc
│   └── valida_cliente.prc
└── reports/
    └── gera_relatorio.prc
```

---

## Adding New Adapters

### Passos

1. **Criar arquivo do loader:**
   ```python
   # app/io/novo_loader.py
   from app.io.base import ProcedureLoaderBase
   from app.core.models import DatabaseType, DatabaseConfig
   from app.io.factory import register_loader

   @register_loader(DatabaseType.NOVO_BANCO)
   class NovoBancoLoader(ProcedureLoaderBase):
       def get_database_type(self) -> DatabaseType:
           return DatabaseType.NOVO_BANCO

       def load_procedures(self, config: DatabaseConfig) -> Dict[str, str]:
           # Implementação
           pass
   ```

2. **Adicionar DatabaseType:**
   ```python
   # app/core/models.py
   class DatabaseType(str, Enum):
       # ... existentes
       NOVO_BANCO = "novo_banco"
   ```

3. **Atualizar factory:**
   ```python
   # app/io/factory.py
   module_map = {
       # ... existentes
       DatabaseType.NOVO_BANCO: "app.io.novo_loader",
   }
   ```

4. **Adicionar driver ao requirements.txt:**
   ```txt
   # Novo Banco
   driver-novo-banco>=1.0.0
   ```

5. **Criar testes:**
   ```python
   # tests/io/test_novo_loader.py
   ```

6. **Documentar:**
   - Atualizar `docs/DATABASE_ADAPTERS.md`
   - Adicionar exemplo em `README.md`

---

## Related Documentation

- [Project Overview](project-overview.md) - Visão geral
- [Architecture Details](architecture.md) - Arquitetura
- [API Catalog](api-catalog.md) - Referência de APIs
- [Integration Flows](integration-flows.md) - Fluxos de uso

---

Generated on: 2025-01-27 12:00:00

