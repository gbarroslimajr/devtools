"""
Testes para ProcedureLoader
"""

import pytest
import tempfile
import os
from pathlib import Path
from analyzer import ProcedureLoader
from app.core.models import ProcedureLoadError, ValidationError


class TestProcedureLoaderFromFiles:
    """Testes para ProcedureLoader.from_files()"""

    def test_load_valid_files(self):
        """Testa carregamento de arquivos válidos"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Cria arquivos de teste
            proc_dir = Path(tmpdir) / "procedures"
            proc_dir.mkdir()

            (proc_dir / "proc1.prc").write_text("CREATE PROCEDURE PROC1 AS BEGIN NULL; END;")
            (proc_dir / "proc2.prc").write_text("CREATE PROCEDURE PROC2 AS BEGIN NULL; END;")

            procedures = ProcedureLoader.from_files(str(proc_dir), "prc")

            assert len(procedures) == 2
            assert "PROC1" in procedures
            assert "PROC2" in procedures

    def test_load_nonexistent_directory(self):
        """Testa erro com diretório inexistente"""
        with pytest.raises(ProcedureLoadError):
            ProcedureLoader.from_files("/diretorio/inexistente", "prc")

    def test_load_empty_directory(self):
        """Testa erro com diretório vazio"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ProcedureLoadError):
                ProcedureLoader.from_files(tmpdir, "prc")

    def test_load_empty_files(self):
        """Testa que arquivos vazios são ignorados"""
        with tempfile.TemporaryDirectory() as tmpdir:
            proc_dir = Path(tmpdir) / "procedures"
            proc_dir.mkdir()

            (proc_dir / "proc1.prc").write_text("CREATE PROCEDURE PROC1 AS BEGIN NULL; END;")
            (proc_dir / "proc2.prc").write_text("")  # Arquivo vazio

            procedures = ProcedureLoader.from_files(str(proc_dir), "prc")

            assert len(procedures) == 1
            assert "PROC1" in procedures

    def test_invalid_extension(self):
        """Testa validação de extensão"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValidationError):
                ProcedureLoader.from_files(tmpdir, "")


class TestProcedureLoaderFromDatabase:
    """Testes para ProcedureLoader.from_database()"""

    def test_validation_empty_user(self):
        """Testa validação de usuário vazio"""
        with pytest.raises(ValidationError, match="Usuário"):
            ProcedureLoader.from_database("", "pass", "dsn")

    def test_validation_empty_password(self):
        """Testa validação de senha vazia"""
        with pytest.raises(ValidationError, match="Senha"):
            ProcedureLoader.from_database("user", "", "dsn")

    def test_validation_empty_dsn(self):
        """Testa validação de DSN/host vazio"""
        # Agora a validação é feita no DatabaseConfig que valida host
        with pytest.raises(ValidationError):
            ProcedureLoader.from_database("user", "pass", "")

