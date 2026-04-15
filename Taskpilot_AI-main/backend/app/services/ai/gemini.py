from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import time

from app.services.ai.base import LLMProvider
from app.core.config import settings

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Google Gemini AI provider using google-generativeai package."""

    _MODEL_NAME = settings.gemini_model or "auto"
    _MAX_RETRIES = 2
    _BASE_DELAY_SECONDS = 4
    _MIN_REQUEST_INTERVAL_SECONDS = 2
    _CACHE_TTL_SECONDS = 300
    _CACHE_MAX_ENTRIES = 256

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key
        self._client = None
        self._request_lock = asyncio.Lock()
        self._last_request_ts = 0.0
        self._cache: dict[str, tuple[float, str]] = {}
        
        if self.api_key:
            logger.info("GeminiProvider initialized with API key")
        else:
            logger.warning("GeminiProvider initialized WITHOUT API key - will return empty responses")

    async def generate(self, prompt: str) -> str:
        """Generate response using Gemini API."""
        if not self.api_key:
            logger.warning("No API key available - returning empty response")
            return ""  # Silent fallback when no API key

        cache_key = self._prompt_cache_key(prompt)
        cached = self._read_cache(cache_key)
        if cached is not None:
            logger.info("Gemini cache hit (length: %s chars)", len(cached))
            return cached

        try:
            import google.generativeai as genai
        except ImportError as e:
            logger.error(f"google.generativeai library not installed: {e}")
            return ""

        last_error: str | None = None
        async with self._request_lock:
            cached_after_lock = self._read_cache(cache_key)
            if cached_after_lock is not None:
                logger.info("Gemini cache hit after lock (length: %s chars)", len(cached_after_lock))
                return cached_after_lock

            # Configure on first use
            if not self._client:
                logger.info("Configuring Gemini API client...")
                genai.configure(api_key=self.api_key)
                model_name = self._resolve_model_name(genai)
                logger.info("Initializing Gemini model: %s", model_name)
                self._client = genai.GenerativeModel(model_name)

            await self._wait_for_rate_limit()

            for attempt in range(self._MAX_RETRIES + 1):
                try:
                    if attempt > 0:
                        backoff = self._compute_backoff(attempt)
                        logger.warning(
                            "Retrying Gemini request after %.1fs (attempt %s/%s)",
                            backoff,
                            attempt,
                            self._MAX_RETRIES,
                        )
                        await asyncio.sleep(backoff)

                    logger.info(
                        "Sending request to Gemini API (model: %s, prompt length: %s chars)",
                        self._MODEL_NAME,
                        len(prompt),
                    )
                    response = await self._client.generate_content_async(prompt)

                    if response and response.text:
                        text = response.text.strip()
                        logger.info("Received response from Gemini API (length: %s chars)", len(text))
                        self._write_cache(cache_key, text)
                        return text

                    last_error = "Gemini API returned empty response"
                    logger.warning(last_error)
                except Exception as e:
                    last_error = str(e)
                    if not self._is_retryable_error(last_error):
                        logger.error("Gemini API non-retryable error: %s", last_error)
                        break
                    logger.warning("Gemini API retryable error: %s", last_error)

        logger.error("Gemini API failed after retries: %s", last_error)
        return ""

    def _wait_for_rate_limit(self) -> asyncio.Future:
        now = time.monotonic()
        elapsed = now - self._last_request_ts
        if elapsed < self._MIN_REQUEST_INTERVAL_SECONDS:
            delay = self._MIN_REQUEST_INTERVAL_SECONDS - elapsed
            logger.info("Rate limiting Gemini request for %.2fs", delay)
            self._last_request_ts = now + delay
            return asyncio.sleep(delay)
        self._last_request_ts = now
        return asyncio.sleep(0)

    def _compute_backoff(self, attempt: int) -> float:
        base = self._BASE_DELAY_SECONDS * (2 ** (attempt - 1))
        jitter = random.uniform(0.0, 0.6)
        return base + jitter

    def _is_retryable_error(self, message: str) -> bool:
        lowered = message.lower()
        return any(token in lowered for token in ("429", "resource_exhausted", "quota", "rate limit"))

    def _prompt_cache_key(self, prompt: str) -> str:
        normalized = " ".join(prompt.split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _read_cache(self, key: str) -> str | None:
        entry = self._cache.get(key)
        if not entry:
            return None
        ts, value = entry
        if (time.time() - ts) > self._CACHE_TTL_SECONDS:
            self._cache.pop(key, None)
            return None
        return value

    def _write_cache(self, key: str, value: str) -> None:
        if len(self._cache) >= self._CACHE_MAX_ENTRIES:
            oldest_key = min(self._cache.items(), key=lambda item: item[1][0])[0]
            self._cache.pop(oldest_key, None)
        self._cache[key] = (time.time(), value)

    def _resolve_model_name(self, genai_module) -> str:
        configured = (self._MODEL_NAME or "").strip()
        if not configured or configured.lower() == "auto":
            try:
                models = list(genai_module.list_models())
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to list Gemini models: %s", exc)
                return "models/gemini-2.0-flash"

            # Prefer any model that supports generateContent.
            candidates = [
                m for m in models
                if hasattr(m, "supported_generation_methods")
                and "generateContent" in m.supported_generation_methods
            ]

            preferred = [
                "models/gemini-2.0-flash",
                "models/gemini-1.5-flash",
                "models/gemini-1.5-pro",
            ]
            for pref in preferred:
                if any(getattr(m, "name", "") == pref for m in candidates):
                    return pref
            if candidates:
                return getattr(candidates[0], "name", "models/gemini-2.0-flash")
            return "models/gemini-2.0-flash"

        if not configured.startswith("models/"):
            return f"models/{configured}"
        return configured
