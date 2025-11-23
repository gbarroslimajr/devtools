"""
Testes para FileLoader
"""

import pytest
import tempfile
from pathlib import Path
from app.io.file_loader import FileLoader
from app.core.models import ProcedureLoadError, ValidationError


class TestFileLoader:
    """Testes para FileLoader"""

    def test_load_valid_files(self):
        """Testa carregamento de arquivos válidos"""
        with tempfile.TemporaryDirectory() as tmpdir:
            proc_dir = Path(tmpdir) / "procedures"
            proc_dir.mkdir()

            (proc_dir / "proc1.prc").write_text("CREATE PROCEDURE PROC1 AS BEGIN NULL; END;")
            (proc_dir / "proc2.prc").write_text("CREATE PROCEDURE PROC2 AS BEGIN NULL; END;")

            loader = FileLoader(str(proc_dir), "prc")
            procedures = loader.load_procedures()

            assert len(procedures) == 2
            assert "PROC1" in procedures
            assert "PROC2" in procedures

    def test_load_nonexistent_directory(self):
        """Testa erro com diretório inexistente"""
        loader = FileLoader("/diretorio/inexistente", "prc")
        with pytest.raises(ProcedureLoadError):
            loader.load_procedures()

    def test_load_empty_directory(self):
        """Testa erro com diretório vazio"""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = FileLoader(tmpdir, "prc")
            with pytest.raises(ProcedureLoadError):
                loader.load_procedures()

    def test_from_files_static_method(self):
        """Testa método estático from_files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            proc_dir = Path(tmpdir) / "procedures"
            proc_dir.mkdir()

            (proc_dir / "proc1.prc").write_text("CREATE PROCEDURE PROC1 AS BEGIN NULL; END;")

            procedures = FileLoader.from_files(str(proc_dir), "prc")
            assert len(procedures) == 1
            assert "PROC1" in procedures

