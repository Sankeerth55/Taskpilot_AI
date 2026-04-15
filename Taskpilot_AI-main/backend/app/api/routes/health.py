from fastapi import APIRouter

from app.core.config import settings
from app.services.ai.gemini import GeminiProvider

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/ping")
async def ping() -> dict:
    """Lightweight health check for frontend connectivity."""
    return {"status": "ok"}


@router.get("/gemini")
async def gemini_health() -> dict:
    """Return Gemini configuration and model visibility without exposing secrets."""
    key_loaded = bool(settings.gemini_api_key)
    model_setting = settings.gemini_model
    resolved_model = "unknown"
    list_models_error = None

    try:
        import google.generativeai as genai
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
        provider = GeminiProvider(api_key=settings.gemini_api_key)
        resolved_model = provider._resolve_model_name(genai)
        try:
            _ = list(genai.list_models())
        except Exception as exc:  # noqa: BLE001
            list_models_error = str(exc)
    except Exception as exc:  # noqa: BLE001
        list_models_error = str(exc)

    return {
        "api_key_loaded": key_loaded,
        "model_setting": model_setting,
        "resolved_model": resolved_model,
        "list_models_error": list_models_error,
    }
