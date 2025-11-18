#!/usr/bin/env python3
"""
Script para gerar mapa de relacionamentos entre objetos Oracle.
Analisa arquivos DDL extraídos pelo extract_oracle_objects.py e gera
relacionamentos entre tabelas, views, procedures, functions, etc.
"""

import os
import sys
import re
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict

import networkx as nx
from tqdm import tqdm


# Configuração de logging
def setup_logging(log_dir: Path) -> logging.Logger:
    """
    Configura o sistema de logging com arquivo e console.

    Args:
        log_dir: Diretório onde salvar os logs

    Returns:
        Logger configurado
    """
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"relationship_map_{timestamp}.log"

    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Logging inicializado. Arquivo: {log_file}")

    return logger


def read_ddl_files(output_dir: Path, schema: str, logger: logging.Logger) -> Dict[str, Dict[str, str]]:
    """
    Lê todos os arquivos DDL do diretório output do Oracle_Schema_Exporter.

    Args:
        output_dir: Diretório base de output do Oracle_Schema_Exporter
        schema: Nome do schema
        logger: Logger

    Returns:
        Dicionário com objetos organizados por tipo: {tipo: {nome: conteudo}}
    """
    schema_dir = output_dir / schema

    if not schema_dir.exists():
        raise FileNotFoundError(f"Diretório não encontrado: {schema_dir}")

    objects = {
        'tables': {},
        'views': {},
        'procedures': {},
        'functions': {},
        'packages': {},
        'triggers': {},
        'sequences': {},
        'indexes': {},
        'constraints': {}
    }

    type_dirs = {
        'tables': 'tables',
        'views': 'views',
        'procedures': 'procedures',
        'functions': 'functions',
        'packages': 'packages',
        'triggers': 'triggers',
        'sequences': 'sequences',
        'indexes': 'indexes',
        'constraints': 'constraints'
    }

    for obj_type, dir_name in type_dirs.items():
        type_dir = schema_dir / dir_name
        if not type_dir.exists():
            logger.warning(f"Diretório não encontrado: {type_dir}")
            continue

        # Determinar extensão de arquivo
        if obj_type == 'procedures':
            ext = '.prc'
        elif obj_type == 'functions':
            ext = '.fnc'
        else:
            ext = '.sql'

        files = list(type_dir.glob(f'*{ext}'))
        logger.info(f"Lendo {len(files)} arquivos de {obj_type}...")

        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    obj_name = file_path.stem
                    objects[obj_type][obj_name] = content
            except Exception as e:
                logger.warning(f"Erro ao ler arquivo {file_path}: {str(e)}")

    return objects


def normalize_object_name(name: str) -> str:
    """
    Normaliza nome de objeto removendo aspas e convertendo para maiúsculas.

    Args:
        name: Nome do objeto

    Returns:
        Nome normalizado
    """
    # Remover aspas duplas se presentes
    name = name.strip().strip('"').strip("'")
    # Converter para maiúsculas (padrão Oracle)
    return name.upper()


def extract_table_references(content: str, current_object: str, obj_type: str) -> List[Tuple[str, str, str]]:
    """
    Extrai referências a tabelas do conteúdo DDL.

    Args:
        content: Conteúdo DDL
        current_object: Nome do objeto atual
        obj_type: Tipo do objeto atual

    Returns:
        Lista de tuplas (source, target, relationship_type)
    """
    relationships = []
    content_upper = content.upper()

    # Padrões para encontrar referências a tabelas
    patterns = [
        # FOREIGN KEY REFERENCES
        (r'REFERENCES\s+["\']?(\w+)["\']?', 'FOREIGN_KEY'),
        (r'FOREIGN\s+KEY.*?REFERENCES\s+["\']?(\w+)["\']?', 'FOREIGN_KEY'),
        # FROM clause
        (r'FROM\s+["\']?(\w+)["\']?', 'SELECT_FROM'),
        # JOIN clauses
        (r'JOIN\s+["\']?(\w+)["\']?', 'JOIN'),
        # INSERT INTO
        (r'INSERT\s+INTO\s+["\']?(\w+)["\']?', 'INSERT_INTO'),
        # UPDATE
        (r'UPDATE\s+["\']?(\w+)["\']?', 'UPDATE'),
        # DELETE FROM
        (r'DELETE\s+FROM\s+["\']?(\w+)["\']?', 'DELETE_FROM'),
        # CREATE TRIGGER ON
        (r'CREATE\s+TRIGGER.*?ON\s+["\']?(\w+)["\']?', 'TRIGGER_ON'),
    ]

    for pattern, rel_type in patterns:
        matches = re.finditer(pattern, content_upper, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            table_name = normalize_object_name(match.group(1))
            if table_name and table_name != current_object.upper():
                relationships.append((current_object, table_name, rel_type))

    return relationships


def extract_procedure_function_calls(content: str, current_object: str, obj_type: str) -> List[Tuple[str, str, str]]:
    """
    Extrai chamadas a procedures e functions.

    Args:
        content: Conteúdo DDL/PL-SQL
        current_object: Nome do objeto atual
        obj_type: Tipo do objeto atual

    Returns:
        Lista de tuplas (source, target, relationship_type)
    """
    relationships = []
    content_upper = content.upper()

    # Lista de palavras-chave SQL/PL-SQL para ignorar
    sql_keywords = {
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP',
        'BEGIN', 'END', 'IF', 'THEN', 'ELSE', 'LOOP', 'WHILE', 'FOR',
        'DECLARE', 'EXCEPTION', 'WHEN', 'RETURN', 'RAISE', 'COMMIT', 'ROLLBACK',
        'SYSDATE', 'SYSTIMESTAMP', 'USER', 'DUAL', 'COUNT', 'SUM', 'MAX', 'MIN',
        'AVG', 'TO_CHAR', 'TO_DATE', 'TO_NUMBER', 'SUBSTR', 'LENGTH', 'TRIM'
    }

    # Padrão 1: CALL, EXEC, EXECUTE explícitos
    pattern1 = r'(?:CALL|EXEC|EXECUTE)\s+(?:["\']?(\w+)["\']?\.)?["\']?(\w+)["\']?'
    matches1 = re.finditer(pattern1, content_upper, re.IGNORECASE | re.MULTILINE)

    for match in matches1:
        proc_name = match.group(2) or match.group(1)
        if proc_name:
            proc_name = normalize_object_name(proc_name)
            if proc_name not in sql_keywords and proc_name != current_object.upper():
                relationships.append((current_object, proc_name, 'CALLS'))

    # Padrão 2: Chamadas de função/procedure (nome seguido de parêntese)
    # Mais específico: procura por identificadores válidos seguidos de (
    pattern2 = r'\b([A-Z_][A-Z0-9_]*)\s*\('
    matches2 = re.finditer(pattern2, content_upper)

    for match in matches2:
        proc_name = normalize_object_name(match.group(1))
        # Ignorar palavras-chave e funções SQL conhecidas
        if (proc_name not in sql_keywords and
            proc_name != current_object.upper() and
            len(proc_name) > 2):  # Ignorar nomes muito curtos (provavelmente não são procedures)
            relationships.append((current_object, proc_name, 'CALLS'))

    # Remover duplicatas mantendo ordem
    seen = set()
    unique_relationships = []
    for rel in relationships:
        if rel not in seen:
            seen.add(rel)
            unique_relationships.append(rel)

    return unique_relationships


def extract_sequence_references(content: str, current_object: str, obj_type: str) -> List[Tuple[str, str, str]]:
    """
    Extrai referências a sequences (NEXTVAL, CURRVAL).

    Args:
        content: Conteúdo DDL/PL-SQL
        current_object: Nome do objeto atual
        obj_type: Tipo do objeto atual

    Returns:
        Lista de tuplas (source, target, relationship_type)
    """
    relationships = []

    # Padrão para sequences: sequence_name.NEXTVAL ou sequence_name.CURRVAL
    pattern = r'["\']?(\w+)["\']?\s*\.\s*(?:NEXTVAL|CURRVAL)'

    matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)

    for match in matches:
        seq_name = normalize_object_name(match.group(1))
        if seq_name and seq_name != current_object.upper():
            relationships.append((current_object, seq_name, 'USES_SEQUENCE'))

    return relationships


def extract_view_dependencies(content: str, current_object: str, obj_type: str) -> List[Tuple[str, str, str]]:
    """
    Extrai dependências de views (tabelas e outras views).

    Args:
        content: Conteúdo DDL da view
        current_object: Nome da view
        obj_type: Tipo do objeto (deve ser 'views')

    Returns:
        Lista de tuplas (source, target, relationship_type)
    """
    relationships = []

    if obj_type != 'views':
        return relationships

    # Views podem referenciar tabelas e outras views
    # Padrões similares aos de tabelas
    table_refs = extract_table_references(content, current_object, obj_type)

    # Marcar como VIEW_DEPENDS
    for source, target, rel_type in table_refs:
        relationships.append((source, target, 'VIEW_DEPENDS'))

    return relationships


def extract_package_content(content: str, current_object: str, obj_type: str,
                           all_procedures: Dict[str, str],
                           all_functions: Dict[str, str]) -> List[Tuple[str, str, str]]:
    """
    Extrai relacionamentos de packages (procedures e functions dentro do package).

    Args:
        content: Conteúdo DDL do package
        current_object: Nome do package
        obj_type: Tipo do objeto
        all_procedures: Dicionário de todas as procedures
        all_functions: Dicionário de todas as functions

    Returns:
        Lista de tuplas (source, target, relationship_type)
    """
    relationships = []

    if obj_type != 'packages':
        return relationships

    # Verificar se procedures/functions com mesmo nome existem
    # (podem estar dentro do package)
    content_upper = content.upper()

    # Procurar por definições de procedures/functions no package
    proc_pattern = r'PROCEDURE\s+["\']?(\w+)["\']?'
    func_pattern = r'FUNCTION\s+["\']?(\w+)["\']?'

    for match in re.finditer(proc_pattern, content_upper, re.IGNORECASE):
        proc_name = normalize_object_name(match.group(1))
        if proc_name in all_procedures:
            relationships.append((current_object, proc_name, 'CONTAINS_PROCEDURE'))

    for match in re.finditer(func_pattern, content_upper, re.IGNORECASE):
        func_name = normalize_object_name(match.group(1))
        if func_name in all_functions:
            relationships.append((current_object, func_name, 'CONTAINS_FUNCTION'))

    return relationships


def analyze_relationships(objects: Dict[str, Dict[str, str]], logger: logging.Logger) -> Tuple[nx.DiGraph, List[Dict]]:
    """
    Analisa relacionamentos entre objetos e constrói grafo.

    Args:
        objects: Dicionário de objetos por tipo
        logger: Logger

    Returns:
        Tupla (grafo NetworkX, lista de relacionamentos com metadados)
    """
    graph = nx.DiGraph()
    relationships_list = []

    # Adicionar todos os objetos como nós no grafo
    for obj_type, obj_dict in objects.items():
        for obj_name in obj_dict.keys():
            graph.add_node(obj_name, type=obj_type)

    logger.info("Analisando relacionamentos...")

    # Analisar cada tipo de objeto
    total_objects = sum(len(obj_dict) for obj_dict in objects.values())

    with tqdm(total=total_objects, desc="Analisando objetos") as pbar:
        for obj_type, obj_dict in objects.items():
            for obj_name, content in obj_dict.items():
                # Extrair diferentes tipos de relacionamentos

                # Referências a tabelas
                table_refs = extract_table_references(content, obj_name, obj_type)
                for source, target, rel_type in table_refs:
                    if target in graph:
                        graph.add_edge(source, target, relationship=rel_type)
                        relationships_list.append({
                            'source': source,
                            'target': target,
                            'type': rel_type,
                            'source_type': obj_type
                        })

                # Chamadas a procedures/functions
                if obj_type in ['procedures', 'functions', 'packages', 'triggers']:
                    proc_calls = extract_procedure_function_calls(content, obj_name, obj_type)
                    for source, target, rel_type in proc_calls:
                        if target in graph:
                            graph.add_edge(source, target, relationship=rel_type)
                            relationships_list.append({
                                'source': source,
                                'target': target,
                                'type': rel_type,
                                'source_type': obj_type
                            })

                # Referências a sequences
                seq_refs = extract_sequence_references(content, obj_name, obj_type)
                for source, target, rel_type in seq_refs:
                    if target in graph:
                        graph.add_edge(source, target, relationship=rel_type)
                        relationships_list.append({
                            'source': source,
                            'target': target,
                            'type': rel_type,
                            'source_type': obj_type
                        })

                # Dependências de views
                if obj_type == 'views':
                    view_deps = extract_view_dependencies(content, obj_name, obj_type)
                    for source, target, rel_type in view_deps:
                        if target in graph:
                            graph.add_edge(source, target, relationship=rel_type)
                            relationships_list.append({
                                'source': source,
                                'target': target,
                                'type': rel_type,
                                'source_type': obj_type
                            })

                # Conteúdo de packages
                if obj_type == 'packages':
                    pkg_content = extract_package_content(
                        content, obj_name, obj_type,
                        objects.get('procedures', {}),
                        objects.get('functions', {})
                    )
                    for source, target, rel_type in pkg_content:
                        if target in graph:
                            graph.add_edge(source, target, relationship=rel_type)
                            relationships_list.append({
                                'source': source,
                                'target': target,
                                'type': rel_type,
                                'source_type': obj_type
                            })

                pbar.update(1)

    logger.info(f"Total de relacionamentos encontrados: {len(relationships_list)}")

    return graph, relationships_list


def export_to_json(graph: nx.DiGraph, relationships_list: List[Dict],
                   objects: Dict[str, Dict[str, str]], schema: str,
                   output_file: Path, logger: logging.Logger):
    """
    Exporta relacionamentos para formato JSON.

    Args:
        graph: Grafo NetworkX
        relationships_list: Lista de relacionamentos
        objects: Dicionário de objetos
        schema: Nome do schema
        output_file: Arquivo de saída
        logger: Logger
    """
    # Calcular estatísticas
    stats = {
        'total_objects': sum(len(obj_dict) for obj_dict in objects.values()),
        'total_relationships': len(relationships_list),
        'objects_by_type': {obj_type: len(obj_dict) for obj_type, obj_dict in objects.items()}
    }

    # Calcular graus de entrada e saída
    in_degrees = dict(graph.in_degree())
    out_degrees = dict(graph.out_degree())

    # Objetos mais referenciados (maior grau de entrada)
    most_referenced = sorted(in_degrees.items(), key=lambda x: x[1], reverse=True)[:10]

    # Objetos que mais referenciam outros (maior grau de saída)
    most_referencing = sorted(out_degrees.items(), key=lambda x: x[1], reverse=True)[:10]

    data = {
        'schema': schema,
        'generated_at': datetime.now().isoformat(),
        'statistics': stats,
        'objects': {
            obj_type: list(obj_dict.keys())
            for obj_type, obj_dict in objects.items()
        },
        'relationships': relationships_list,
        'graph_metrics': {
            'most_referenced': [{'object': obj, 'count': count} for obj, count in most_referenced],
            'most_referencing': [{'object': obj, 'count': count} for obj, count in most_referencing],
            'isolated_objects': [node for node in graph.nodes() if graph.degree(node) == 0]
        }
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"JSON exportado para: {output_file}")


def export_to_dot(graph: nx.DiGraph, objects: Dict[str, Dict[str, str]],
                  output_file: Path, logger: logging.Logger):
    """
    Exporta grafo para formato DOT (Graphviz).

    Args:
        graph: Grafo NetworkX
        objects: Dicionário de objetos
        output_file: Arquivo de saída
        logger: Logger
    """
    # Mapear tipos para cores
    type_colors = {
        'tables': 'lightblue',
        'views': 'lightgreen',
        'procedures': 'lightcoral',
        'functions': 'lightyellow',
        'packages': 'lightpink',
        'triggers': 'lightgray',
        'sequences': 'lightcyan',
        'indexes': 'wheat',
        'constraints': 'lavender'
    }

    dot_content = ['digraph Relationships {', '  rankdir=LR;', '  node [shape=box, style=filled];', '']

    # Adicionar nós com cores por tipo
    for node in graph.nodes():
        node_type = graph.nodes[node].get('type', 'unknown')
        color = type_colors.get(node_type, 'white')
        label = node.replace('_', '\\n')
        dot_content.append(f'  "{node}" [fillcolor={color}, label="{label}"];')

    dot_content.append('')

    # Adicionar arestas
    for source, target, data in graph.edges(data=True):
        rel_type = data.get('relationship', 'RELATED')
        dot_content.append(f'  "{source}" -> "{target}" [label="{rel_type}"];')

    dot_content.append('}')

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(dot_content))

    logger.info(f"DOT exportado para: {output_file}")


def export_to_markdown(graph: nx.DiGraph, relationships_list: List[Dict],
                       objects: Dict[str, Dict[str, str]], schema: str,
                       output_file: Path, logger: logging.Logger):
    """
    Exporta relatório para formato Markdown.

    Args:
        graph: Grafo NetworkX
        relationships_list: Lista de relacionamentos
        objects: Dicionário de objetos
        schema: Nome do schema
        output_file: Arquivo de saída
        logger: Logger
    """
    lines = []

    lines.append(f"# Mapa de Relacionamentos - Schema: {schema}")
    lines.append(f"\n**Gerado em:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Estatísticas
    total_objects = sum(len(obj_dict) for obj_dict in objects.values())
    lines.append("## Estatísticas\n")
    lines.append(f"- **Total de objetos:** {total_objects}")
    lines.append(f"- **Total de relacionamentos:** {len(relationships_list)}\n")

    lines.append("### Objetos por Tipo\n")
    lines.append("| Tipo | Quantidade |")
    lines.append("|------|------------|")
    for obj_type, obj_dict in objects.items():
        lines.append(f"| {obj_type.capitalize()} | {len(obj_dict)} |")
    lines.append("")

    # Objetos mais referenciados
    in_degrees = dict(graph.in_degree())
    most_referenced = sorted(in_degrees.items(), key=lambda x: x[1], reverse=True)[:10]

    if most_referenced:
        lines.append("### Objetos Mais Referenciados\n")
        lines.append("| Objeto | Referências |")
        lines.append("|--------|-------------|")
        for obj, count in most_referenced:
            lines.append(f"| {obj} | {count} |")
        lines.append("")

    # Objetos que mais referenciam
    out_degrees = dict(graph.out_degree())
    most_referencing = sorted(out_degrees.items(), key=lambda x: x[1], reverse=True)[:10]

    if most_referencing:
        lines.append("### Objetos que Mais Referenciam Outros\n")
        lines.append("| Objeto | Referências |")
        lines.append("|--------|-------------|")
        for obj, count in most_referencing:
            lines.append(f"| {obj} | {count} |")
        lines.append("")

    # Objetos isolados
    isolated = [node for node in graph.nodes() if graph.degree(node) == 0]
    if isolated:
        lines.append(f"### Objetos Isolados ({len(isolated)})\n")
        lines.append(", ".join(isolated))
        lines.append("")

    # Relacionamentos por tipo
    rel_by_type = defaultdict(int)
    for rel in relationships_list:
        rel_by_type[rel['type']] += 1

    if rel_by_type:
        lines.append("### Relacionamentos por Tipo\n")
        lines.append("| Tipo | Quantidade |")
        lines.append("|------|------------|")
        for rel_type, count in sorted(rel_by_type.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"| {rel_type} | {count} |")
        lines.append("")

    # Lista de relacionamentos (limitada)
    lines.append("## Relacionamentos\n")
    lines.append("| Origem | Tipo | Destino |")
    lines.append("|--------|------|---------|")

    # Limitar a 100 relacionamentos para não ficar muito grande
    for rel in relationships_list[:100]:
        lines.append(f"| {rel['source']} | {rel['type']} | {rel['target']} |")

    if len(relationships_list) > 100:
        lines.append(f"\n*Mostrando 100 de {len(relationships_list)} relacionamentos. Ver arquivo JSON para lista completa.*")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    logger.info(f"Markdown exportado para: {output_file}")


def main():
    """Função principal do script."""
    # Determinar diretórios
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    mapper_dir = project_dir

    # Diretório de output do Oracle_Schema_Exporter
    exporter_dir = project_dir.parent / "Oracle_Schema_Exporter"
    output_dir = exporter_dir / "output"

    maps_dir = mapper_dir / "maps"
    log_dir = mapper_dir / "log"

    # Configurar logging
    logger = setup_logging(log_dir)

    try:
        # Verificar se o diretório de output existe
        if not output_dir.exists():
            logger.error(f"Diretório de output não encontrado: {output_dir}")
            logger.error("Execute primeiro o extract_oracle_objects.py para gerar os arquivos DDL.")
            sys.exit(1)

        # Listar schemas disponíveis
        schemas = [d.name for d in output_dir.iterdir() if d.is_dir()]

        if not schemas:
            logger.error(f"Nenhum schema encontrado em {output_dir}")
            sys.exit(1)

        logger.info(f"Schemas encontrados: {', '.join(schemas)}")

        # Processar cada schema
        for schema in schemas:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processando schema: {schema}")
            logger.info(f"{'='*60}")

            try:
                # Ler arquivos DDL
                objects = read_ddl_files(output_dir, schema, logger)

                # Verificar se há objetos
                total_objects = sum(len(obj_dict) for obj_dict in objects.values())
                if total_objects == 0:
                    logger.warning(f"Nenhum objeto encontrado para o schema {schema}")
                    continue

                # Analisar relacionamentos
                graph, relationships_list = analyze_relationships(objects, logger)

                # Criar diretório de saída
                schema_maps_dir = maps_dir / schema
                schema_maps_dir.mkdir(parents=True, exist_ok=True)

                # Exportar em diferentes formatos
                logger.info("Gerando relatórios...")

                export_to_json(graph, relationships_list, objects, schema,
                             schema_maps_dir / "relationships.json", logger)

                export_to_dot(graph, objects, schema_maps_dir / "relationships.dot", logger)

                export_to_markdown(graph, relationships_list, objects, schema,
                                 schema_maps_dir / "relationships.md", logger)

                logger.info(f"Relatórios gerados em: {schema_maps_dir}")

            except Exception as e:
                logger.error(f"Erro ao processar schema {schema}: {str(e)}", exc_info=True)
                continue

        logger.info("\nProcesso concluído com sucesso!")

    except Exception as e:
        logger.error(f"Erro fatal: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

