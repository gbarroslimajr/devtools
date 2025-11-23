"""
Módulo LLM para CodeGraphAI
Suporta modelos locais e via API
"""

from app.llm.genfactory_client import GenFactoryClient
from app.llm.langchain_wrapper import GenFactoryLLM
from app.llm.toon_converter import (
    json_to_toon,
    toon_to_json,
    format_toon_example,
    format_dependencies_prompt_example,
    parse_llm_response,
    TOON_AVAILABLE
)

__all__ = [
    'GenFactoryClient',
    'GenFactoryLLM',
    'json_to_toon',
    'toon_to_json',
    'format_toon_example',
    'format_dependencies_prompt_example',
    'parse_llm_response',
    'TOON_AVAILABLE'
]

