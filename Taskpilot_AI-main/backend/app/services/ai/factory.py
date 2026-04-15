import logging

from app.core.config import settings
from app.services.ai.base import LLMProvider
from app.services.ai.gemini import GeminiProvider

logger = logging.getLogger(__name__)


def get_provider() -> LLMProvider:
    """Get LLM provider based on configuration.
    
    API keys are read from Settings which loads .env file.
    If no API key is available, providers will return empty responses,
    triggering fallback behavior in agents.
    """
    provider = settings.llm_provider.lower()
    api_key = settings.gemini_api_key
    
    # Log API key status (masked for security)
    if api_key:
        logger.info(f"GEMINI_API_KEY loaded: {api_key[:10]}...{api_key[-4:]}")
    else:
        logger.warning("GEMINI_API_KEY not found - will use fallback responses")
    
    if provider == "gemini":
        return GeminiProvider(api_key=api_key or None)
    
    # Default to Gemini
    return GeminiProvider(api_key=api_key or None)
