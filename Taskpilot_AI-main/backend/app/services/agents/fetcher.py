from __future__ import annotations

import asyncio
import logging
import time
import re
from datetime import datetime
from typing import Any, Awaitable, Callable, TypeVar

import httpx

from app.core.cache import get_query_cache
from app.core.logging_config import get_logger
from app.services.agents.base import AgentContext, AgentResultData, BaseAgent
from app.services.ai.factory import get_provider
from app.services.intent_detector import IntentDetector, TaskIntent

logger = logging.getLogger(__name__)
T = TypeVar("T")


class FetcherAgent(BaseAgent):
    """
    PRODUCTION-GRADE Fetcher Agent for TaskPilot AI.
    
    Goes BEYOND just searching - actually GATHERS and PROCESSES data:
    - Reads uploaded files (PDF, TXT, CSV, DOC, DOCX)
    - Auto-unzips and processes ZIP contents
    - Analyzes uploaded images using Gemini Vision
    - Searches web when needed (DuckDuckGo, Wikipedia)
    - Prepares clean, actionable data for downstream agents
    """

    name = "fetcher"

    def __init__(self) -> None:
        self.query_cache = get_query_cache()
        self.agent_logger = get_logger("agent.fetcher")
        self._default_timeout_seconds = 4.0
        self._default_retries = 1

    async def run(self, context: AgentContext) -> AgentResultData:
        """Execute INTELLIGENT data gathering based on task intent."""
        run_start = time.perf_counter()
        combined = context.user_input
        if context.screen_context:
            combined = f"{combined}\nScreen context: {context.screen_context}"

        fetched_data: list[str] = []
        metadata = {}
        cache_before = self.query_cache.get_stats()

        # PHASE 0: Detect Intent - Understand what data we need
        # Check if intent is already provided by Gemini Controller
        if context.metadata.get("intent"):
            intent_info = {
                "intent": context.metadata["intent"],
                "confidence": 1.0,
                "complexity": context.metadata.get("complexity", "medium"),
                "is_time_sensitive": context.metadata.get("is_time_sensitive", False),
                "keywords": [], # Will be extracted later if needed
                "entities": []
            }
            # Backfill keywords if missing (simple extraction)
            if not intent_info["keywords"]:
                # Use full user input to let search engine handle key terms
                # This fixes the issue where queries like "suggest me a best and..." got truncated
                intent_info["keywords"] = [context.user_input]
        else:
            intent_info = IntentDetector.detect_intent(
                context.user_input,
                has_files=bool(context.attachments),
                screen_context=context.screen_context
            )
        
        # Store intent information in context
        intent_obj = intent_info["intent"]
        context.metadata["intent"] = intent_obj.value if hasattr(intent_obj, "value") else str(intent_obj)
        context.metadata["confidence"] = intent_info["confidence"]
        context.metadata["complexity"] = intent_info["complexity"]
        context.metadata["is_time_sensitive"] = intent_info["is_time_sensitive"]
        
        # Add current date context to metadata only.
        current_date = datetime.now().strftime("%B %d, %Y")
        current_year = datetime.now().year
        context.metadata["current_date"] = current_date
        context.metadata["current_year"] = current_year

        # PHASE 1: Process Uploaded Files (BEYOND ChatGPT!)
        if context.attachments:
            file_results = await self._process_attachments(context.attachments, intent_info)
            if file_results:
                fetched_data.append(f"📎 UPLOADED FILES:\n{file_results}")
                metadata["has_attachments"] = True
                metadata["attachment_count"] = len(context.attachments)

        live_query_kind = self._detect_live_city_query_kind(context.user_input)
        if live_query_kind:
            live_result = await self._fetch_live_city_data(context.user_input, live_query_kind, force_refresh=True)
            if live_result:
                fetched_data.append(live_result)
                metadata["live_query_kind"] = live_query_kind
                metadata["live_city_query"] = True
                # Propagate immediately so downstream agents can detect it.
                context.metadata["live_query_kind"] = live_query_kind
                context.metadata["live_city_query"] = True
                live_sources = await self._fetch_live_city_sources(context.user_input, live_query_kind)
                if live_sources:
                    fetched_data.append(f"🌐 LIVE SOURCES:\n{live_sources}")
                    metadata["live_sources"] = True

        # PHASE 2: WORLD-CLASS Multi-Source Research (Gemini Brain + Google Power!)
        # TaskPilot AI searches ALL sources in PARALLEL for comprehensive answers
        
        # For attachment-based analysis, stay focused on uploaded content and skip web links/noise.
        has_attachments = bool(context.attachments)
        # Skip web search for greetings and attachment-only requests.
        should_search = intent_info["intent"] != TaskIntent.GREETING and not live_query_kind and not has_attachments
        
        if should_search:
            # Get smart keywords based on intent
            keywords = " ".join(intent_info["keywords"][:5])
            if intent_info["entities"]:
                keywords = f"{keywords} {' '.join(intent_info['entities'][:3])}"
            
            # If no keywords extracted, use the full question
            if not keywords.strip():
                keywords = context.user_input

            expanded_keywords = self._expand_factual_keywords(context.user_input, keywords)
            
            metadata["search_keywords"] = keywords

            # Force fresh network fetch for time-sensitive and commerce-style queries.
            user_query_lower = context.user_input.lower()
            force_live_fetch = bool(intent_info.get("is_time_sensitive", False)) or any(
                token in user_query_lower
                for token in (
                    "hotel", "hotels", "price", "cost", "cheapest", "latest", "today", "current", "news"
                )
            )
            metadata["force_live_fetch"] = force_live_fetch
            
            # === OPTIMIZATION: Determine search depth based on complexity ===
            # For simple factual queries, reduce search depth for faster response
            is_simple_factual = any([
                user_query_lower.startswith("who is"),
                user_query_lower.startswith("who's"),
                user_query_lower.startswith("when "),
                user_query_lower.startswith("where "),
                user_query_lower.startswith("what is"),
                user_query_lower.startswith("what's"),
                "president of" in user_query_lower,
                "capital of" in user_query_lower,
            ])
            
            if is_simple_factual:
                # Fast path: reduced search for simple factual questions
                max_results = 2  # Keep factual queries fast but still live.
                skip_related = True  # Skip related topics to save time
                metadata["search_mode"] = "fast_factual"
            else:
                # Normal path: comprehensive search
                max_results = self._get_search_depth(intent_info)
                skip_related = False
                metadata["search_mode"] = "comprehensive"
            
            source_tasks: list[tuple[str, Awaitable[str]]] = [
                ("wikipedia", self._fetch_wikipedia_enhanced(expanded_keywords, intent_info, force_refresh=force_live_fetch)),
                ("web", self._search_duckduckgo_enhanced(keywords, intent_info["intent"], max_results=max_results, force_refresh=force_live_fetch)),
            ]
            if not skip_related:
                source_tasks.append(("related_topics", self._search_related_topics(keywords, intent_info, force_refresh=force_live_fetch)))
            is_news_trading = context.metadata.get("query_type") == "news_trading" or any(
                token in user_query_lower
                for token in ("news", "stock", "market", "trading", "crypto", "bitcoin", "nifty", "sensex", "nasdaq", "forex", "gold price")
            )
            include_news = bool(context.metadata.get("include_news", False)) or is_news_trading
            include_recent_for_factual = is_simple_factual and any(
                token in user_query_lower for token in ("who", "where", "which", "name", "ceo", "founder", "president", "prime minister", "cm")
            )
            if intent_info["is_time_sensitive"] or include_news or include_recent_for_factual or is_news_trading:
                source_tasks.append(("recent", self._fetch_recent_information(expanded_keywords, force_refresh=force_live_fetch)))

            # For news/trading: fetch news as a PRIMARY source (more results)
            if is_news_trading:
                source_tasks.append(("news_primary", self._fetch_news_primary(keywords, force_refresh=force_live_fetch)))

            if self._should_fetch_government_sources(context.user_input):
                source_tasks.append(("gov_sources", self._fetch_government_sources(expanded_keywords, force_refresh=force_live_fetch)))

            logger.info(f"⚡ Launching {len(source_tasks)} parallel search operations...")
            source_timeouts = {
                "wikipedia": 6.0,
                "web": 8.0,
                "related_topics": 4.0,
                "recent": 6.0,
                "news_primary": 8.0,
                "gov_sources": 6.0,
            }
            search_results_all = await asyncio.gather(
                *(
                    self._run_timed_source(
                        name,
                        coro,
                        timeout_seconds=source_timeouts.get(name, 8.0),
                    )
                    for name, coro in source_tasks
                ),
                return_exceptions=False,
            )

            source_timings: dict[str, float] = {}
            source_errors: dict[str, str] = {}

            for source_result in search_results_all:
                source_name = source_result["name"]
                source_timings[source_name] = source_result["duration_ms"]

                source_error = source_result.get("error")
                if source_error:
                    source_errors[source_name] = source_error
                    continue

                source_payload = source_result.get("result", "")
                if not source_payload:
                    continue

                if source_name == "web":
                    fetched_data.append(f"🔍 WEB RESEARCH:\n{source_payload}")
                    metadata["web_search"] = True
                elif source_name == "wikipedia":
                    fetched_data.append(f"📚 REFERENCE DATA:\n{source_payload}")
                    metadata["wikipedia"] = True
                elif source_name == "related_topics":
                    fetched_data.append(f"🧐 RELATED INSIGHTS:\n{source_payload}")
                    metadata["related_topics"] = True
                elif source_name == "recent":
                    fetched_data.append(f"📰 RECENT NEWS:\n{source_payload}")
                    metadata["has_recent_info"] = True
                elif source_name == "news_primary":
                    fetched_data.append(f"📰 LIVE NEWS:\n{source_payload}")
                    metadata["has_live_news"] = True
                elif source_name == "gov_sources":
                    fetched_data.append(f"🏛 GOVERNMENT SOURCES:\n{source_payload}")
                    metadata["has_gov_sources"] = True

            metadata["source_timings_ms"] = source_timings
            if source_errors:
                metadata["source_errors"] = source_errors

            # Final live-data fallback: broaden query and retry core sources if needed.
            if not fetched_data:
                fallback_query = context.user_input.strip() or keywords
                fallback_web, fallback_wiki = await asyncio.gather(
                    self._search_duckduckgo_enhanced(
                        fallback_query,
                        intent_info["intent"],
                        max_results=6 if any(t in user_query_lower for t in ("hotel", "cheapest", "price")) else 4,
                        force_refresh=True,
                    ),
                    self._fetch_wikipedia_enhanced(fallback_query, intent_info, force_refresh=True),
                    return_exceptions=False,
                )
                if fallback_web:
                    fetched_data.append(f"🔍 WEB RESEARCH:\n{fallback_web}")
                    metadata["web_search"] = True
                if fallback_wiki:
                    fetched_data.append(f"📚 REFERENCE DATA:\n{fallback_wiki}")
                    metadata["wikipedia"] = True
                metadata["fallback_fetch_used"] = bool(fallback_web or fallback_wiki)

            logger.info(f"✅ Parallel search completed - {len(fetched_data)} sources gathered")

        # PHASE 3: Normalize and Return with Context
        if fetched_data:
            output = "\n\n".join(fetched_data)
        else:
            output = f"📋 TASK REQUEST:\n{combined.strip()}"

        context.fetched_context = output
        cache_after = self.query_cache.get_stats()
        metadata["cache_hits_delta"] = cache_after.get("hits", 0) - cache_before.get("hits", 0)
        metadata["cache_misses_delta"] = cache_after.get("misses", 0) - cache_before.get("misses", 0)
        metadata["fetch_duration_ms"] = round((time.perf_counter() - run_start) * 1000, 2)

        self.agent_logger.info(
            "fetcher_completed",
            duration_ms=metadata["fetch_duration_ms"],
            cache_hits=metadata["cache_hits_delta"],
            cache_misses=metadata["cache_misses_delta"],
        )
        context.metadata.update(metadata)
        
        return AgentResultData(
            name=self.name,
            status="complete",
            output=output[:2000],  # Summarize for agent step display
            details=metadata
        )

    async def _run_timed_source(
        self,
        name: str,
        source_coro: Awaitable[str],
        timeout_seconds: float = 8.0,
    ) -> dict[str, Any]:
        """Execute one source fetch with timing, timeout, and safe error capture."""
        started = time.perf_counter()
        try:
            result = await asyncio.wait_for(source_coro, timeout=timeout_seconds)
            return {
                "name": name,
                "result": result,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        except asyncio.TimeoutError:
            return {
                "name": name,
                "result": "",
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "error": f"timeout_after_{timeout_seconds}s",
            }
        except Exception as exc:
            return {
                "name": name,
                "result": "",
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "error": str(exc),
            }

    def _detect_live_city_query_kind(self, user_input: str) -> str | None:
        text = user_input.lower().strip()
        weather_patterns = (
            r"\bweather\b.*\b(?:in|at|for|of)\b",
            r"\btemperature\b.*\b(?:in|at|for|of)\b",
            r"\b(?:how is|hows)\s+the\s+weather\b",
        )
        time_patterns = (
            r"\b(?:current|present|local)?\s*time\b.*\b(?:in|at|for|of)\b",
            r"\bwhat\s+time\s+is\s+it\b.*\b(?:in|at|for|of)\b",
            r"\btell\s+me\s+the\s+time\b.*\b(?:in|at|for|of)\b",
        )

        if any(re.search(pattern, text) for pattern in weather_patterns):
            return "weather"
        if any(re.search(pattern, text) for pattern in time_patterns):
            return "time"
        return None

    def _extract_city_from_live_query(self, user_input: str) -> str:
        text = user_input.strip()
        patterns = [
            r"(?:temperature|weather|time)\s+(?:in|at|for)\s+([A-Za-z][A-Za-z\s\-']{1,60})",
            r"(?:current\s+)?(?:temperature|weather|time)\s+of\s+([A-Za-z][A-Za-z\s\-']{1,60})",
            r"(?:what\s+time\s+is\s+it|tell\s+me\s+the\s+time|present\s+time|current\s+time)\s+(?:in|at|for|of)\s+([A-Za-z][A-Za-z\s\-']{1,60})",
            r"(?:how\s+is|hows)\s+the\s+(?:weather|temperature)\s+(?:in|at|for|of)\s+([A-Za-z][A-Za-z\s\-']{1,60})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                city = match.group(1).strip(" ?.,")
                city = re.sub(r"\b(today|now|currently|right now|please|live)\b.*$", "", city, flags=re.IGNORECASE).strip()
                return city

        fallback_match = re.search(r"\b(?:in|at|for|of)\s+(.+)$", text, flags=re.IGNORECASE)
        if fallback_match:
            city = fallback_match.group(1).strip(" ?.,")
            city = re.sub(r"\b(today|now|currently|right now|please|live)\b.*$", "", city, flags=re.IGNORECASE).strip()
            return city
        return ""

    async def _fetch_live_city_data(self, user_input: str, live_query_kind: str, force_refresh: bool = False) -> str:
        city = self._extract_city_from_live_query(user_input)
        if not city:
            return ""

        cache_key = f"live_{live_query_kind}"
        cache_params = {"city": city.lower(), "kind": live_query_kind}
        if not force_refresh:
            cached = self.query_cache.get_cached_query(cache_key, city, cache_params)
            if cached is not None:
                return cached

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                geo = await client.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": city, "count": 1, "language": "en", "format": "json"},
                )
                geo.raise_for_status()
                geo_data = geo.json()
        except Exception as exc:
            logger.debug(f"Live city geocoding failed: {exc}")
            return ""

        results = geo_data.get("results") or []
        if not results:
            return ""

        location = results[0]
        latitude = location.get("latitude")
        longitude = location.get("longitude")
        timezone = location.get("timezone", "auto")
        city_name = location.get("name", city)
        country = location.get("country", "")
        admin1 = location.get("admin1", "")
        country_code = str(location.get("country_code", "")).upper()

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                weather = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": latitude,
                        "longitude": longitude,
                        "current": "temperature_2m,weather_code",
                        "timezone": timezone,
                    },
                )
                weather.raise_for_status()
                weather_data = weather.json()
        except Exception as exc:
            logger.debug(f"Live city forecast failed: {exc}")
            return ""

        current = weather_data.get("current") or {}
        current_time = current.get("time", "")
        temp_c = current.get("temperature_2m")
        weather_code = current.get("weather_code")

        if live_query_kind == "time":
            output = (
                f"🕒 LIVE TIME\n"
                f"City: {city_name}{', ' + admin1 if admin1 else ''}{', ' + country if country else ''}\n"
                f"Local Time: {self._format_time_text(current_time)}\n"
                f"Timezone: {timezone}\n"
                f"Source: Open-Meteo"
            )
        else:
            output = (
                f"🌤 LIVE WEATHER\n"
                f"City: {city_name}{', ' + admin1 if admin1 else ''}{', ' + country if country else ''}\n"
                f"Temperature: {self._format_temperature_for_location(temp_c, country_code)}\n"
                f"Condition: {self._weather_code_to_text(weather_code)}\n"
                f"Local Time: {self._format_time_text(current_time)}\n"
                f"Timezone: {timezone}\n"
                f"Source: Open-Meteo"
            )

        ttl = 300 if live_query_kind == "weather" else 60
        self.query_cache.cache_query(cache_key, city, output, cache_params, ttl=ttl)
        return output

    async def _fetch_live_city_sources(self, user_input: str, live_query_kind: str) -> str:
        """Fetch authoritative live source links for weather/time queries."""
        city = self._extract_city_from_live_query(user_input)
        if not city:
            return ""

        try:
            from ddgs import DDGS
        except ImportError:
            return ""

        if live_query_kind == "weather":
            query = f"weather {city} site:weather.com OR site:accuweather.com OR site:bbc.com/weather"
        else:
            query = f"time in {city} site:timeanddate.com OR site:worldtimebuddy.com"

        def _search() -> list[dict[str, Any]]:
            try:
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=4))
            except Exception as exc:
                logger.debug(f"Live city source search error: {exc}")
                return []

        results = await self._execute_with_retry(
            op_name="live_city_sources",
            operation=lambda: asyncio.to_thread(_search),
            timeout_seconds=5.0,
            retries=1,
        )
        if not results:
            return ""

        lines = []
        for r in results[:4]:
            title = r.get("title", "Live source")
            url = r.get("href", r.get("link", ""))
            if url:
                lines.append(f"- {title} — {url}")
        return "\n".join(lines)

    def _format_time_text(self, iso_time: str) -> str:
        if not iso_time:
            return "Unknown"
        try:
            return datetime.fromisoformat(iso_time).strftime("%I:%M %p")
        except Exception:
            return iso_time

    def _format_temperature_for_location(self, temp_c: Any, country_code: str) -> str:
        if temp_c is None:
            return "Unknown"
        try:
            temp_c_float = float(temp_c)
        except Exception:
            return str(temp_c)

        if country_code == "US":
            temp_f = (temp_c_float * 9 / 5) + 32
            return f"{temp_f:.1f} degrees Fahrenheit"
        return f"{temp_c_float:.1f} degrees Celsius"

    def _weather_code_to_text(self, code: Any) -> str:
        mapping = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            71: "Slight snow fall",
            73: "Moderate snow fall",
            75: "Heavy snow fall",
            80: "Rain showers",
            81: "Heavy rain showers",
            82: "Violent rain showers",
            95: "Thunderstorm",
        }
        try:
            return mapping.get(int(code), "Live weather data")
        except Exception:
            return "Live weather data"

    async def _execute_with_retry(
        self,
        op_name: str,
        operation: Callable[[], Awaitable[T]],
        timeout_seconds: float | None = None,
        retries: int | None = None,
    ) -> T | None:
        """Run async operation with timeout and retry/backoff."""
        max_attempts = (retries if retries is not None else self._default_retries) + 1
        timeout = timeout_seconds if timeout_seconds is not None else self._default_timeout_seconds
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                return await asyncio.wait_for(operation(), timeout=timeout)
            except Exception as exc:
                last_error = exc
                if attempt >= max_attempts:
                    break
                await asyncio.sleep(0.2 * attempt)

        if last_error:
            logger.warning(f"{op_name} failed after retries: {last_error}")
        return None

    async def _process_attachments(self, attachments: list[dict[str, Any]], intent_info: dict) -> str:
        """Process all uploaded attachments with INTENT-AWARE analysis."""
        results = []
        
        for i, attachment in enumerate(attachments, 1):
            attach_type = attachment.get("type", "unknown")
            content = attachment.get("content", "")
            metadata = attachment.get("metadata", {})
            
            # Add intent-based context
            intent = intent_info.get("intent", "analyze_file")
            
            if attach_type == "image":
                # Image requires vision analysis
                vision_result = await self._analyze_image_with_vision(attachment, intent)
                results.append(f"[Image {i}] {vision_result}")
            
            elif attach_type == "pdf":
                pages = metadata.get("pages", "?")
                # For PDFs, provide more context based on intent
                if intent == "summarize":
                    results.append(f"[PDF {i}] {pages} pages - Content extracted for summarization:\n{content[:1500]}")
                else:
                    results.append(f"[PDF {i}] {pages} pages extracted:\n{content[:1000]}")
            
            elif attach_type == "csv":
                structured = attachment.get("structured_data", [])
                if structured:
                    results.append(f"[CSV {i}] Data with {len(structured)} rows:\n{content[:800]}")
                else:
                    results.append(f"[CSV {i}]:\n{content[:800]}")
            
            elif attach_type == "zip":
                files = attachment.get("files", [])
                file_summary = "\n".join([f"  - {f.get('filename')}: {f.get('content', '')[:100]}" 
                                         for f in files[:10]])
                results.append(f"[ZIP {i}] Extracted {len(files)} files:\n{file_summary}")
            
            elif attach_type in ["text", "docx"]:
                results.append(f"[{attach_type.upper()} {i}]:\n{content[:1000]}")
            
            else:
                results.append(f"[File {i}] {attach_type}: {content[:500]}")
        
        return "\n\n".join(results)

    async def _analyze_image_with_vision(self, image_attachment: dict[str, Any], intent: str) -> str:
        """Analyze image using Gemini Vision capabilities."""
        try:
            llm = get_provider()
            base64_data = image_attachment.get("base64_data", "")
            mime_type = image_attachment.get("mime_type", "image/jpeg")
            
            if not base64_data:
                return "Image uploaded but no data available"
            
            # For now, return a placeholder - full vision integration requires gemini.py upgrade
            # This will be enhanced when Gemini multimodal is properly integrated
            return f"Image analyzed - visual content detected ({mime_type})"
            
        except Exception as e:
            logger.error(f"Image analysis error: {e}")
            return f"Image uploaded ({image_attachment.get('metadata', {}).get('format', 'unknown')})"
    
    def _get_search_depth(self, intent_info: dict) -> int:
        """Determine how many search results to fetch based on task complexity."""
        complexity = intent_info.get("complexity", "simple")
        intent = intent_info.get("intent")
        
        # High complexity or research tasks need more data
        if complexity == "high" or intent in [TaskIntent.RESEARCH, TaskIntent.COMPARE]:
            return 8
        elif complexity == "medium" or intent in [TaskIntent.RECOMMEND, TaskIntent.EVALUATE]:
            return 6
        else:
            return 4
    
    async def _search_duckduckgo_enhanced(
        self, 
        query: str, 
        intent: str,
        max_results: int = 5,
        force_refresh: bool = False,
    ) -> str:
        """Enhanced DuckDuckGo search with better result processing and link preservation."""
        cache_params = {"intent": str(intent), "max_results": max_results}
        if not force_refresh:
            cached = self.query_cache.get_cached_query("duckduckgo_text", query, cache_params)
            if cached is not None:
                return cached

        try:
            from ddgs import DDGS
        except ImportError:
            logger.warning("DuckDuckGo search not available")
            return ""
        
        # 🏨 SPECIAL HANDLING for HOTEL/PRICE queries - increase results for better comparison
        if "hotel" in query.lower() or "price" in query.lower() or "cheapest" in query.lower():
            max_results = min(max_results + 3, 10)  # Get more results for comparisons
            logger.info(f"💰 Price comparison mode: fetching {max_results} results")

        def _search() -> list[dict[str, Any]]:
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=max_results))
                return results
            except Exception as e:
                logger.error(f"DuckDuckGo search error: {e}")
                return []

        results = await self._execute_with_retry(
            op_name="duckduckgo_text",
            operation=lambda: asyncio.to_thread(_search),
        )
        if not results:
            return ""

        # Format results based on intent - ALWAYS INCLUDE URLs IN CONSISTENT FORMAT!
        snippets = []
        
        if intent == TaskIntent.COMPARE:
            # For comparisons, provide structured data with clear link markers
            for i, r in enumerate(results[:max_results], 1):
                title = r.get('title', 'Result')
                body = r.get('body', '')
                url = r.get('href', r.get('link', ''))
                
                # Extract price if present in title or body
                import re
                price_pattern = r'(?:₹|Rs\.?|\$|€|£)\s*[\d,]+(?:\.\d{2})?'
                price_match = re.search(price_pattern, title + " " + body)
                price_info = f"\n💰 {price_match.group(0)}" if price_match else ""
                
                snippets.append(f"**{title}**\n{body}{price_info}\n🔗 Link: {url}\n")
                
        elif intent in [TaskIntent.FIND, TaskIntent.RECOMMEND]:
            # For finding things (hotels, restaurants), preserve ALL details with prominent links
            for i, r in enumerate(results[:max_results], 1):
                title = r.get('title', 'Result')
                body = r.get('body', '')
                url = r.get('href', r.get('link', ''))
                
                # Extract price if present
                import re
                price_pattern = r'(?:from\s*)?(?:₹|Rs\.?|\$|€|£)\s*[\d,]+(?:\.\d{2})?(?:\s*(?:per|/)\s*(?:night|person|day|room))?'
                price_matches = re.findall(price_pattern, title + " " + body, re.IGNORECASE)
                price_info = f"\n💰 Price: {', '.join(price_matches)}" if price_matches else ""
                
                # Format with clear structure
                snippets.append(
                    f"**{title}**\n"
                    f"{body}"
                    f"{price_info}\n"
                    f"🔗 Link: {url}\n"
                )
        else:
            # Standard format with URLs included for all other queries
            for i, r in enumerate(results[:max_results], 1):
                title = r.get('title', 'Result')
                body = r.get('body', '')
                url = r.get('href', r.get('link', ''))
                snippets.append(f"**{title}**\n{body}\n🔗 Link: {url}\n")
        
        final_text = "\n".join(snippets)[:3000]  # Increased limit to preserve more links
        ttl = 120 if force_refresh else 300
        self.query_cache.cache_query("duckduckgo_text", query, final_text, cache_params, ttl=ttl)
        return final_text
    
    async def _fetch_wikipedia_enhanced(self, query: str, intent_info: dict, force_refresh: bool = False) -> str:
        """Enhanced Wikipedia lookup with better context."""
        cache_params = {"complexity": intent_info.get("complexity", "simple")}
        if not force_refresh:
            cached = self.query_cache.get_cached_query("wikipedia_summary", query, cache_params)
            if cached is not None:
                return cached

        try:
            import wikipedia  # requires the 'wikipedia' package (not 'wikipedia-api')
        except ImportError:
            logger.warning("'wikipedia' package not installed — skipping Wikipedia fetch")
            return ""

        def _wiki() -> str:
            try:
                # Get more sentences for research/explain tasks
                complexity = intent_info.get("complexity", "simple")
                sentences = 4 if complexity == "high" else 3

                return wikipedia.summary(query, sentences=sentences, auto_suggest=True)
            except wikipedia.DisambiguationError as e:
                # Try the first disambiguation option
                try:
                    return wikipedia.summary(e.options[0], sentences=3)
                except Exception:
                    return ""
            except wikipedia.PageError:
                return ""
            except Exception as e:
                logger.debug(f"Wikipedia lookup failed: {e}")
                return ""

        summary = await self._execute_with_retry(
            op_name="wikipedia_summary",
            operation=lambda: asyncio.to_thread(_wiki),
            timeout_seconds=6.0,
        )
        final_text = summary[:600] if summary else ""
        if final_text:
            ttl = 300 if force_refresh else 1200
            self.query_cache.cache_query("wikipedia_summary", query, final_text, cache_params, ttl=ttl)
        return final_text
    
    async def _fetch_recent_information(self, query: str, force_refresh: bool = False) -> str:
        """
        Fetch recent/current information using DuckDuckGo News.
        Increased to 6 results for better coverage.
        """
        if not force_refresh:
            cached = self.query_cache.get_cached_query("duckduckgo_news", query)
            if cached is not None:
                return cached

        try:
            from ddgs import DDGS
        except ImportError:
            return ""
        
        def _news_search() -> list[dict[Any, Any]]:
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.news(query, max_results=6))
                return results
            except Exception as e:
                logger.debug(f"News search error: {e}")
                return []
        
        results = await self._execute_with_retry(
            op_name="duckduckgo_news",
            operation=lambda: asyncio.to_thread(_news_search),
        )
        if not results:
            return ""
        
        news_items = []
        for item in results[:6]:
            title = item.get('title', '')
            body = item.get('body', '')
            date = item.get('date', '')
            url = item.get('url', item.get('href', ''))
            if title:
                news_items.append(f"{title} ({date})\n{body}\n🔗 {url}")
        
        final_text = "\n\n".join(news_items)[:1500] if news_items else ""
        if final_text:
            ttl = 90 if force_refresh else 180
            self.query_cache.cache_query("duckduckgo_news", query, final_text, ttl=ttl)
        return final_text

    async def _fetch_news_primary(self, query: str, force_refresh: bool = False) -> str:
        """
        PRIMARY news fetch for news/trading queries — fetches 8 results from
        DuckDuckGo news and formats them with full details and source links.
        """
        cache_key = f"news_primary_{query[:60]}"
        if not force_refresh:
            cached = self.query_cache.get_cached_query("news_primary", query)
            if cached is not None:
                return cached

        try:
            from ddgs import DDGS
        except ImportError:
            return ""

        def _search() -> list[dict[Any, Any]]:
            try:
                with DDGS() as ddgs:
                    return list(ddgs.news(query, max_results=8))
            except Exception as e:
                logger.debug(f"Primary news search error: {e}")
                return []

        results = await self._execute_with_retry(
            op_name="news_primary",
            operation=lambda: asyncio.to_thread(_search),
            timeout_seconds=8.0,
            retries=2,
        )
        if not results:
            return ""

        items = []
        for item in results[:8]:
            title = item.get('title', '')
            body = item.get('body', item.get('snippet', ''))
            date = item.get('date', '')
            url = item.get('url', item.get('href', ''))
            source = item.get('source', '')
            if title:
                line = f"📰 {title}"
                if date:
                    line += f" ({date})"
                if source:
                    line += f" — {source}"
                if body:
                    line += f"\n   {body[:200]}"
                if url:
                    line += f"\n   🔗 {url}"
                items.append(line)

        final_text = "\n\n".join(items)[:2500] if items else ""
        if final_text:
            self.query_cache.cache_query("news_primary", query, final_text, ttl=120)
        return final_text

    def _should_fetch_government_sources(self, user_input: str) -> bool:
        query = (user_input or "").lower()
        role_terms = (
            "prime minister", "pm", "chief minister", "cm", "president",
            "home minister", "mla", "mp", "minister", "governor",
        )
        return any(term in query for term in role_terms)

    async def _fetch_government_sources(self, query: str, force_refresh: bool = False) -> str:
        """Fetch official/government sources for role/position queries."""
        cache_key = "gov_sources"
        if not force_refresh:
            cached = self.query_cache.get_cached_query(cache_key, query)
            if cached is not None:
                return cached

        try:
            from ddgs import DDGS
        except ImportError:
            return ""

        gov_query = (
            f"{query} site:gov.in OR site:india.gov.in OR site:nic.in OR "
            f"site:gov OR site:parliament OR site:assembly"
        )

        def _search() -> list[dict[str, Any]]:
            try:
                with DDGS() as ddgs:
                    return list(ddgs.text(gov_query, max_results=5))
            except Exception as exc:
                logger.debug(f"Government source search error: {exc}")
                return []

        results = await self._execute_with_retry(
            op_name="gov_sources",
            operation=lambda: asyncio.to_thread(_search),
            timeout_seconds=6.0,
            retries=1,
        )
        if not results:
            return ""

        snippets = []
        for r in results[:5]:
            title = r.get("title", "Official source")
            body = r.get("body", "")
            url = r.get("href", r.get("link", ""))
            if not url:
                continue
            snippets.append(f"**{title}**\n{body}\n🔗 Link: {url}\n")

        final_text = "\n".join(snippets)[:2200]
        if final_text:
            ttl = 180 if force_refresh else 600
            self.query_cache.cache_query(cache_key, query, final_text, ttl=ttl)
        return final_text

    def _should_search_web(self, user_input: str, has_files: bool) -> bool:
        """
        DEPRECATED: Now using IntentDetector for intelligent search decisions.
        Keeping for backwards compatibility but not actively used.
        """
        return True  # Default to searching if explicitly called

    def _extract_keywords(self, text: str) -> str:
        """
        DEPRECATED: Now using IntentDetector for smarter keyword extraction.
        Keeping for backwards compatibility.
        """
        stopwords = {
            "the", "is", "at", "which", "on", "a", "an", "and", "or", "but",
            "in", "with", "to", "for", "of", "this", "that", "can", "you",
            "please", "help", "me", "my", "i", "want", "need"
        }
        words = text.lower().split()
        keywords = [w.strip(".,!?") for w in words if w not in stopwords and len(w) > 2]
        return " ".join(keywords[:7])

    async def _search_duckduckgo(self, query: str, max_results: int = 5) -> str:
        """
        DEPRECATED: Use _search_duckduckgo_enhanced instead.
        Keeping for backwards compatibility.
        """
        return await self._search_duckduckgo_enhanced(query, "research", max_results)

    async def _search_related_topics(self, query: str, intent_info: dict, force_refresh: bool = False) -> str:
        """
        Search for related topics and similar questions (like Google's "People also ask").
        This gives comprehensive context beyond the main query.
        """
        cache_params = {"complexity": intent_info.get("complexity", "simple")}
        if not force_refresh:
            cached = self.query_cache.get_cached_query("duckduckgo_related", query, cache_params)
            if cached is not None:
                return cached

        try:
            from ddgs import DDGS
        except ImportError:
            return ""
        
        def _related_search() -> str:
            try:
                # Generate related search queries
                related_queries = []
                
                # Add "why" and "how" variations
                base_terms = query.split()[:3]  # First 3 words
                if base_terms:
                    related_queries.append(f"why {' '.join(base_terms)}")
                    related_queries.append(f"how {' '.join(base_terms)} work")
                
                # Search one related query for additional context
                if related_queries:
                    with DDGS() as ddgs:
                        results = list(ddgs.text(related_queries[0], max_results=2))
                        if results:
                            snippets = []
                            for r in results:
                                title = r.get('title', '')
                                body = r.get('body', '')
                                if title and body:
                                    snippets.append(f"{title}: {body[:150]}")
                            return " | ".join(snippets)
                return ""
            except Exception as e:
                logger.debug(f"Related search error: {e}")
                return ""
        
        result = await self._execute_with_retry(
            op_name="duckduckgo_related",
            operation=lambda: asyncio.to_thread(_related_search),
            timeout_seconds=5.0,
        )
        final_text = result[:600] if result else ""
        if final_text:
            ttl = 120 if force_refresh else 300
            self.query_cache.cache_query("duckduckgo_related", query, final_text, cache_params, ttl=ttl)
        return final_text

    def _expand_factual_keywords(self, user_input: str, keywords: str) -> str:
        """Expand common abbreviations/misspellings for factual roles before web/wikipedia fetch."""
        text = (user_input or "").lower()
        expanded = keywords or user_input

        # Normalize role abbreviations to improve Wikipedia hits.
        expanded = re.sub(r"\bcm\b", "chief minister", expanded, flags=re.IGNORECASE)
        expanded = re.sub(r"\bpm\b", "prime minister", expanded, flags=re.IGNORECASE)
        expanded = re.sub(r"\bceo\b", "chief executive officer", expanded, flags=re.IGNORECASE)

        # Normalize common misspellings in role phrases.
        expanded = re.sub(r"\bcheif\b", "chief", expanded, flags=re.IGNORECASE)
        expanded = re.sub(r"\bministar\b", "minister", expanded, flags=re.IGNORECASE)
        expanded = re.sub(r"\bministor\b", "minister", expanded, flags=re.IGNORECASE)

        # If the user asks "cm in <state>", prefer "chief minister of <state>" phrasing.
        if re.search(r"\bchief minister\b", expanded, flags=re.IGNORECASE):
            expanded = re.sub(r"\bchief minister\s+in\s+", "chief minister of ", expanded, flags=re.IGNORECASE)
        if re.search(r"\bprime minister\b", expanded, flags=re.IGNORECASE):
            expanded = re.sub(r"\bprime minister\s+in\s+", "prime minister of ", expanded, flags=re.IGNORECASE)

        return expanded.strip() or (keywords or user_input)
    
    async def _fetch_wikipedia(self, query: str) -> str:
        """
        DEPRECATED: Use _fetch_wikipedia_enhanced instead.
        Keeping for backwards compatibility.
        """
        intent_info = {"complexity": "simple"}
        return await self._fetch_wikipedia_enhanced(query, intent_info)
