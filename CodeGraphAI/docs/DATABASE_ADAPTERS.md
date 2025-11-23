# Adaptadores de Banco de Dados - CodeGraphAI

Este documento descreve os adaptadores de banco de dados disponíveis no CodeGraphAI.

## Visão Geral

CodeGraphAI usa uma arquitetura baseada em adaptadores para suportar múltiplos bancos de dados. Cada adaptador implementa a interface `ProcedureLoaderBase` e é responsável por:

1. Conectar ao banco de dados específico
2. Listar stored procedures disponíveis
3. Extrair o código-fonte de cada procedure
4. Retornar um dicionário com nome e código das procedures

## Adaptadores Disponíveis

### Oracle (`OracleLoader`)

**Driver:** `oracledb>=1.4.0`

**Instalação:**
```bash
pip install oracledb>=1.4.0
```

**Configuração:**
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

**Queries SQL:**
- Listar procedures: `SELECT OWNER, OBJECT_NAME FROM ALL_PROCEDURES WHERE OBJECT_TYPE = 'PROCEDURE'`
- Obter código: `SELECT TEXT FROM ALL_SOURCE WHERE OWNER = :owner AND NAME = :name ORDER BY LINE`

**Formato DSN:**
- `host:port/service` (ex: `localhost:1521/ORCL`)
- Ou apenas `host` se DSN completo estiver configurado no sistema

**Troubleshooting:**
- Erro de conexão: Verifique se o Oracle Instant Client está instalado
- Procedures não encontradas: Verifique permissões do usuário (ALL_PROCEDURES, ALL_SOURCE)

---

### PostgreSQL (`PostgreSQLLoader`)

**Driver:** `psycopg2-binary>=2.9.0`

**Instalação:**
```bash
pip install psycopg2-binary>=2.9.0
```

**Configuração:**
```python
config = DatabaseConfig(
    db_type=DatabaseType.POSTGRESQL,
    user="usuario",
    password="senha",
    host="localhost",
    port=5432,
    database="meu_banco",  # Obrigatório
    schema="public"  # Opcional, padrão: public
)
```

**Queries SQL:**
- Listar procedures: `SELECT routine_schema, routine_name FROM information_schema.routines WHERE routine_type = 'PROCEDURE'`
- Obter código: `SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname = :name AND prokind = 'p'`

**Notas:**
- PostgreSQL 11+ suporta procedures (antes apenas functions)
- Schema padrão é `public`
- Usa `pg_get_functiondef()` para obter código completo

**Troubleshooting:**
- Erro de conexão: Verifique se PostgreSQL está rodando e porta está correta
- Procedures não encontradas: Verifique se está usando PostgreSQL 11+ e se há procedures (não apenas functions)

---

### SQL Server (`MSSQLLoader`)

**Driver:** `pyodbc>=5.0.0` (recomendado) ou `pymssql>=2.2.0`

**Instalação:**
```bash
# Opção 1: pyodbc (requer ODBC Driver)
pip install pyodbc>=5.0.0
# Instale também: ODBC Driver 17 for SQL Server (do site da Microsoft)

# Opção 2: pymssql (mais simples, mas menos recursos)
pip install pymssql>=2.2.0
```

**Configuração:**
```python
config = DatabaseConfig(
    db_type=DatabaseType.MSSQL,
    user="usuario",
    password="senha",
    host="localhost",
    port=1433,
    database="meu_banco",  # Obrigatório
    schema="dbo",  # Opcional, padrão: dbo
    extra_params={"driver": "ODBC Driver 17 for SQL Server"}  # Para pyodbc
)
```

**Queries SQL:**
- Listar procedures: `SELECT ROUTINE_SCHEMA, ROUTINE_NAME FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_TYPE = 'PROCEDURE'`
- Obter código: `SELECT definition FROM sys.sql_modules WHERE object_id = OBJECT_ID(:name)`

**Notas:**
- Para `pyodbc`, configure o driver ODBC no `extra_params`
- Schema padrão é `dbo`
- Suporta autenticação Windows (via `pyodbc` com `Trusted_Connection=yes`)

**Troubleshooting:**
- Erro de conexão: Verifique se SQL Server está acessível e porta está correta
- Erro de driver: Instale ODBC Driver 17 for SQL Server
- Procedures não encontradas: Verifique permissões e se está conectado ao database correto

---

### MySQL (`MySQLLoader`)

**Driver:** `mysql-connector-python>=8.0.0` (recomendado) ou `pymysql>=1.0.0`

**Instalação:**
```bash
# Opção 1: mysql-connector-python (oficial)
pip install mysql-connector-python>=8.0.0

# Opção 2: pymysql (alternativa)
pip install pymysql>=1.0.0
```

**Configuração:**
```python
config = DatabaseConfig(
    db_type=DatabaseType.MYSQL,
    user="usuario",
    password="senha",
    host="localhost",
    port=3306,
    database="meu_banco",  # Obrigatório
    schema=None  # MySQL não usa schema separado, usa database
)
```

**Queries SQL:**
- Listar procedures: `SELECT ROUTINE_SCHEMA, ROUTINE_NAME FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_TYPE = 'PROCEDURE'`
- Obter código: `SELECT ROUTINE_DEFINITION FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_SCHEMA = :schema AND ROUTINE_NAME = :name`

**Notas:**
- MySQL não usa schema separado como outros bancos (usa database)
- `ROUTINE_DEFINITION` pode estar truncado para procedures grandes
- Suporta ambos os drivers automaticamente

**Troubleshooting:**
- Erro de conexão: Verifique se MySQL está rodando e porta está correta
- Procedures não encontradas: Verifique permissões e se está conectado ao database correto
- Código truncado: Limitação do `INFORMATION_SCHEMA.ROUTINES` - considere usar `SHOW CREATE PROCEDURE`

---

## Uso Programático

### Usando Factory Pattern

```python
from app.core.models import DatabaseConfig, DatabaseType
from app.io.factory import create_loader

# Cria configuração
config = DatabaseConfig(
    db_type=DatabaseType.POSTGRESQL,
    user="user",
    password="pass",
    host="localhost",
    port=5432,
    database="mydb"
)

# Cria loader usando factory
loader = create_loader(DatabaseType.POSTGRESQL)

# Carrega procedures
procedures = loader.load_procedures(config)
```

### Usando ProcedureLoader (Backward Compatibility)

```python
from analyzer import ProcedureLoader

# Oracle (padrão)
procedures = ProcedureLoader.from_database(
    user="user",
    password="pass",
    dsn="localhost:1521/ORCL"
)

# Outros bancos
procedures = ProcedureLoader.from_database(
    user="user",
    password="pass",
    dsn="localhost",
    db_type="postgresql"  # ou "mssql", "mysql"
)
```

## Adicionando Novo Adaptador

Para adicionar suporte a um novo banco de dados:

1. Criar novo arquivo em `app/io/` (ex: `app/io/newdb_loader.py`)
2. Implementar `ProcedureLoaderBase`
3. Registrar no factory usando `register_loader()`
4. Adicionar `DatabaseType` em `app/core/models.py`
5. Adicionar dependência em `requirements.txt`
6. Criar testes em `tests/io/`

Exemplo:
```python
from app.io.base import ProcedureLoaderBase
from app.io.factory import register_loader
from app.core.models import DatabaseType

class NewDBLoader(ProcedureLoaderBase):
    def get_database_type(self) -> DatabaseType:
        return DatabaseType.NEWDB

    def load_procedures(self, config: DatabaseConfig) -> Dict[str, str]:
        # Implementação
        pass

register_loader(DatabaseType.NEWDB, NewDBLoader)
```

## Limitações Conhecidas

1. **MySQL**: `ROUTINE_DEFINITION` pode estar truncado para procedures muito grandes
2. **PostgreSQL**: Requer PostgreSQL 11+ para suporte a procedures
3. **SQL Server**: Requer driver ODBC instalado para `pyodbc`
4. **Oracle**: Requer Oracle Instant Client instalado

## Suporte e Contribuições

Para reportar problemas ou sugerir melhorias nos adaptadores, abra uma issue no repositório.

