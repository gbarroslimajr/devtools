#!/usr/bin/env python3
"""
Script para atualizar arquivos Mermaid existentes com configurações de zoom
"""
import re
from pathlib import Path

def get_init_config(diagram_type: str) -> str:
    """
    Retorna configuração de inicialização apropriada para o tipo de diagrama

    Args:
        diagram_type: Tipo do diagrama ('er', 'graph', 'flowchart')

    Returns:
        String com configurações de inicialização
    """
    init_config = "%%{init: {\n"
    init_config += "  'theme': 'base',\n"
    init_config += "  'themeVariables': {\n"
    init_config += "    'fontSize': '16px',\n"
    init_config += "    'fontFamily': 'Arial, sans-serif',\n"
    init_config += "    'primaryColor': '#ff6b6b',\n"
    init_config += "    'primaryTextColor': '#fff',\n"
    init_config += "    'primaryBorderColor': '#c92a2a',\n"
    init_config += "    'lineColor': '#333',\n"
    init_config += "    'secondaryColor': '#ffd93d',\n"
    init_config += "    'tertiaryColor': '#51cf66'\n"
    init_config += "  },\n"

    if diagram_type == 'er':
        init_config += "  'er': {\n"
        init_config += "    'entityPadding': 15,\n"
        init_config += "    'fill': '#fff',\n"
        init_config += "    'stroke': '#333'\n"
        init_config += "  }\n"
    else:  # graph ou flowchart
        init_config += "  'flowchart': {\n"
        init_config += "    'nodeSpacing': 50,\n"
        init_config += "    'rankSpacing': 80,\n"
        init_config += "    'curve': 'basis'\n"
        init_config += "  }\n"

    init_config += "}}%%\n"
    return init_config

def detect_diagram_type(content: str) -> tuple[str, str]:
    """
    Detecta o tipo de diagrama Mermaid no conteúdo

    Args:
        content: Conteúdo do arquivo

    Returns:
        Tupla (tipo, linha_inicial) onde tipo é 'er', 'graph', 'flowchart' ou None
    """
    # Padrões para detectar tipo de diagrama
    patterns = [
        (r'```mermaid\s*\n\s*(erDiagram)', 'er', 'erDiagram'),
        (r'```mermaid\s*\n\s*(graph\s+(TD|LR|TB|RL))', 'graph', r'graph \2'),
        (r'```mermaid\s*\n\s*(flowchart\s+(TD|LR|TB|RL))', 'flowchart', r'flowchart \2'),
    ]

    for pattern, diagram_type, replacement in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return diagram_type, match.group(1)

    return None, None

def update_mermaid_file(file_path: Path) -> bool:
    """
    Atualiza um arquivo Mermaid adicionando configurações de inicialização

    Args:
        file_path: Caminho do arquivo a atualizar

    Returns:
        True se o arquivo foi atualizado, False caso contrário
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Verifica se já tem configurações de inicialização
        if '%%{init:' in content:
            print(f"  {file_path.name} já tem configurações, pulando...")
            return False

        # Detecta tipo de diagrama
        diagram_type, diagram_line = detect_diagram_type(content)

        if not diagram_type:
            print(f"  {file_path.name} não é um diagrama Mermaid reconhecido, pulando...")
            return False

        # Obtém configurações apropriadas
        init_config = get_init_config(diagram_type)

        # Substitui o início do bloco Mermaid
        # Padrão: ```mermaid\n<diagram_line>
        # Substitui por: ```mermaid\n<init_config><diagram_line>
        pattern = rf'```mermaid\s*\n\s*({re.escape(diagram_line)})'
        replacement = f'```mermaid\n{init_config}\\1'

        new_content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)

        if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"  ✓ {file_path.name} atualizado com sucesso! (tipo: {diagram_type})")
            return True
        else:
            print(f"  ✗ {file_path.name} não foi modificado (padrão não encontrado)")
            return False

    except Exception as e:
        print(f"  ✗ Erro ao processar {file_path.name}: {e}")
        return False

def find_mermaid_files(directory: Path) -> list[Path]:
    """
    Encontra todos os arquivos que contêm diagramas Mermaid

    Args:
        directory: Diretório para buscar

    Returns:
        Lista de caminhos de arquivos Mermaid
    """
    mermaid_files = []

    for md_file in directory.rglob("*.md"):
        try:
            # Lê primeiras linhas para verificar se é Mermaid
            with open(md_file, 'r', encoding='utf-8', errors='ignore') as f:
                first_lines = f.read(200)
                if '```mermaid' in first_lines:
                    mermaid_files.append(md_file)
        except Exception:
            # Ignora erros de leitura
            continue

    return mermaid_files

def main():
    """Atualiza todos os arquivos Mermaid no diretório output"""
    script_dir = Path(__file__).parent
    output_dir = script_dir / "output"

    if not output_dir.exists():
        print(f"Diretório {output_dir} não encontrado!")
        return

    print(f"Procurando arquivos Mermaid em {output_dir}...")

    mermaid_files = find_mermaid_files(output_dir)

    if not mermaid_files:
        print("Nenhum arquivo Mermaid encontrado!")
        return

    print(f"Encontrados {len(mermaid_files)} arquivo(s) Mermaid:")
    for f in mermaid_files:
        print(f"  - {f.relative_to(output_dir)}")

    print("\nAtualizando arquivos...")
    updated = 0
    for file_path in mermaid_files:
        if update_mermaid_file(file_path):
            updated += 1

    print(f"\n✓ {updated} arquivo(s) atualizado(s) com sucesso!")
    if updated < len(mermaid_files):
        skipped = len(mermaid_files) - updated
        print(f"  ({skipped} arquivo(s) já tinha(m) configurações ou não foi(ram) modificado(s))")

if __name__ == "__main__":
    main()

