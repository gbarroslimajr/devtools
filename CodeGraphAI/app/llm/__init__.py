"""
Módulo LLM para CodeGraphAI
Suporta modelos locais e via API
"""

from app.llm.genfactory_client import GenFactoryClient
from app.llm.langchain_wrapper import GenFactoryLLM

__all__ = ['GenFactoryClient', 'GenFactoryLLM']

