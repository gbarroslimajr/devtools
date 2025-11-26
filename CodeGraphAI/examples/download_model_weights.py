"""
Script para baixar os pesos do modelo diretamente do HuggingFace
sem necessidade de git-lfs
"""

import sys
from pathlib import Path

try:
    from huggingface_hub import hf_hub_download
except ImportError:
    print("Instalando huggingface_hub...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "huggingface_hub"])
    from huggingface_hub import hf_hub_download

def download_model_files():
    """Baixa os arquivos de pesos do modelo."""
    model_dir = Path(__file__).parent.parent / "models" / "elastic" / "multilingual-e5-small-optimized"
    repo_id = "elastic/multilingual-e5-small-optimized"

    print(f"Baixando arquivos do modelo para: {model_dir}")
    print(f"Repositório: {repo_id}")

    # Arquivos que precisam ser baixados
    files_to_download = [
        "pytorch_model.bin",
        "sentencepiece.bpe.model"
    ]

    for filename in files_to_download:
        print(f"\nBaixando {filename}...")
        try:
            local_path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=str(model_dir),
                local_dir_use_symlinks=False
            )
            print(f"✅ {filename} baixado: {local_path}")
        except Exception as e:
            print(f"❌ Erro ao baixar {filename}: {e}")

if __name__ == "__main__":
    download_model_files()

