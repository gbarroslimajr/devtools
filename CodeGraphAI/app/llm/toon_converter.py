"""
Módulo de conversão TOON (Token-Oriented Object Notation) para CodeGraphAI
Otimiza uso de tokens ao enviar dados estruturados para LLMs
"""

import json
import logging
from typing import Dict, Any, Optional

try:
    from toon_format import encode, decode

    TOON_AVAILABLE = True
except ImportError:
    TOON_AVAILABLE = False

logger = logging.getLogger(__name__)


def _escape_template_braces(text: str) -> str:
    """
    Escapa chaves em strings para uso em templates LangChain PromptTemplate.

    No LangChain, chaves literais `{` e `}` devem ser escapadas como `{{` e `}}`
    para evitar que sejam interpretadas como variáveis do template.

    Args:
        text: String contendo chaves que devem ser escapadas

    Returns:
        String com chaves escapadas ({{ e }})

    Examples:
        >>> _escape_template_braces('{"key": "value"}')
        '{{"key": "value"}}'
    """
    if not text:
        return text
    return text.replace("{", "{{").replace("}", "}}")


def json_to_toon(data: Dict[str, Any]) -> str:
    """
    Converte dict/JSON para formato TOON

    Args:
        data: Dicionário Python ou estrutura JSON

    Returns:
        String no formato TOON

    Raises:
        ValueError: Se TOON não estiver disponível ou houver erro na conversão
    """
    if not TOON_AVAILABLE:
        raise ValueError("Biblioteca toon-python não está disponível. Instale com: pip install toon-python")

    try:
        return encode(data)
    except Exception as e:
        logger.warning(f"Erro ao converter para TOON: {e}, usando JSON")
        raise ValueError(f"Erro ao converter para TOON: {e}") from e


def toon_to_json(toon_str: str) -> Dict[str, Any]:
    """
    Converte TOON para dict/JSON

    Args:
        toon_str: String no formato TOON

    Returns:
        Dicionário Python equivalente

    Raises:
        ValueError: Se TOON não estiver disponível ou houver erro no parsing
    """
    if not TOON_AVAILABLE:
        raise ValueError("Biblioteca toon-python não está disponível. Instale com: pip install toon-python")

    try:
        return decode(toon_str)
    except Exception as e:
        logger.warning(f"Erro ao parsear TOON: {e}")
        raise ValueError(f"Erro ao parsear TOON: {e}") from e


def format_toon_example(data: Dict[str, Any]) -> str:
    """
    Formata exemplo TOON para uso em prompts LLM

    Args:
        data: Dicionário Python com dados de exemplo

    Returns:
        String formatada com exemplo TOON ou JSON (fallback)
    """
    try:
        toon_str = json_to_toon(data)
        return f"Formato TOON:\n{toon_str}"
    except Exception as e:
        logger.debug(f"Não foi possível converter para TOON: {e}, usando JSON como fallback")
        # Fallback para JSON formatado
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        return f"Formato JSON:\n{json_str}"


def format_dependencies_prompt_example(use_toon: bool = False) -> str:
    """
    Formata exemplo de resposta para prompt de dependências.

    Retorna string formatada com exemplo JSON ou TOON, com chaves escapadas
    para uso em templates LangChain PromptTemplate. As chaves `{` e `}` no
    JSON/TOON são escapadas como `{{` e `}}` para evitar interpretação como
    variáveis do template.

    Args:
        use_toon: Se True, usa formato TOON; caso contrário, usa JSON

    Returns:
        String com exemplo formatado e chaves escapadas para LangChain

    Note:
        As chaves no JSON/TOON são escapadas para compatibilidade com
        PromptTemplate do LangChain, que interpreta `{var}` como variável.
    """
    example_data = {
        "procedures": ["proc1", "schema.proc2", "proc3"],
        "tables": ["table1", "schema.table2", "table3"]
    }

    if use_toon and TOON_AVAILABLE:
        try:
            toon_str = json_to_toon(example_data)
            json_str = json.dumps(example_data, indent=2, ensure_ascii=False)
            # Escapar chaves no JSON e TOON para evitar interpretação como variáveis
            escaped_toon = _escape_template_braces(toon_str)
            escaped_json = _escape_template_braces(json_str)
            return f"Retorne no formato TOON:\n{escaped_toon}\n\nOu no formato JSON:\n{escaped_json}"
        except Exception as e:
            logger.debug(f"Erro ao formatar exemplo TOON: {e}, usando JSON")
            # Fallback para JSON
            json_str = json.dumps(example_data, indent=2, ensure_ascii=False)
            escaped_json = _escape_template_braces(json_str)
            return f"Retorne no formato JSON:\n{escaped_json}"
    else:
        # JSON padrão
        json_str = json.dumps(example_data, indent=2, ensure_ascii=False)
        escaped_json = _escape_template_braces(json_str)
        return f"Retorne no formato JSON:\n{escaped_json}"


def parse_llm_response(response: str, use_toon: bool = False) -> Optional[Dict[str, Any]]:
    """
    Tenta parsear resposta do LLM, tentando TOON primeiro se habilitado, depois JSON

    Args:
        response: Resposta do LLM
        use_toon: Se True, tenta parsear TOON primeiro

    Returns:
        Dicionário parseado ou None se falhar
    """
    if not response or not response.strip():
        return None

    # Se TOON está habilitado e disponível, tenta parsear TOON primeiro
    if use_toon and TOON_AVAILABLE:
        try:
            # Procura por padrão TOON na resposta
            # TOON geralmente tem formato [N]{fields}: ou similar
            if '[' in response and '{' in response and ':' in response:
                # Tenta extrair bloco TOON
                lines = response.split('\n')
                toon_lines = []
                in_toon_block = False
                for line in lines:
                    if '[' in line and '{' in line and ':' in line:
                        in_toon_block = True
                        toon_lines.append(line)
                    elif in_toon_block:
                        if line.strip() and not line.strip().startswith('{') and not line.strip().startswith('['):
                            toon_lines.append(line)
                        else:
                            break

                if toon_lines:
                    toon_str = '\n'.join(toon_lines)
                    return toon_to_json(toon_str)
        except Exception as e:
            logger.debug(f"Erro ao parsear TOON da resposta: {e}, tentando JSON")

    # Fallback para JSON
    try:
        # Procura por bloco JSON na resposta
        json_match = None
        import re
        # Tenta encontrar objeto JSON completo
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.finditer(json_pattern, response, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue
        return None
    except Exception as e:
        logger.debug(f"Erro ao parsear JSON da resposta: {e}")
        return None
