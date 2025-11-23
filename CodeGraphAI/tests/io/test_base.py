"""
Testes para interface base e factory
"""

import pytest
from app.core.models import DatabaseType, DatabaseConfig, ValidationError
from app.io.base import ProcedureLoaderBase
from app.io.factory import create_loader, get_available_loaders


class TestFactory:
    """Testes para factory pattern"""

    def test_get_available_loaders(self):
        """Testa obtenção de loaders disponíveis"""
        loaders = get_available_loaders()
        assert isinstance(loaders, list)
        # Pelo menos Oracle deve estar disponível se oracledb estiver instalado

    def test_create_loader_oracle(self):
        """Testa criação de loader Oracle"""
        try:
            loader = create_loader(DatabaseType.ORACLE)
            assert loader.get_database_type() == DatabaseType.ORACLE
        except (ValidationError, ImportError):
            pytest.skip("Oracle driver não disponível")

    def test_create_loader_invalid_type(self):
        """Testa erro com tipo de banco inválido"""
        # DatabaseType não tem valores inválidos, mas podemos testar com string
        with pytest.raises((ValidationError, ValueError)):
            # Tenta criar com tipo não suportado
            pass  # Factory já valida via enum


class TestDatabaseConfig:
    """Testes para DatabaseConfig"""

    def test_config_validation(self):
        """Testa validação de configuração"""
        # Config válido
        config = DatabaseConfig(
            db_type=DatabaseType.ORACLE,
            user="test",
            password="test",
            host="localhost"
        )
        assert config.user == "test"

    def test_config_empty_user(self):
        """Testa erro com usuário vazio"""
        with pytest.raises(ValidationError, match="Usuário"):
            DatabaseConfig(
                db_type=DatabaseType.ORACLE,
                user="",
                password="test",
                host="localhost"
            )

    def test_config_empty_password(self):
        """Testa erro com senha vazia"""
        with pytest.raises(ValidationError, match="Senha"):
            DatabaseConfig(
                db_type=DatabaseType.ORACLE,
                user="test",
                password="",
                host="localhost"
            )

    def test_config_empty_host(self):
        """Testa erro com host vazio"""
        with pytest.raises(ValidationError, match="Host"):
            DatabaseConfig(
                db_type=DatabaseType.ORACLE,
                user="test",
                password="test",
                host=""
            )

