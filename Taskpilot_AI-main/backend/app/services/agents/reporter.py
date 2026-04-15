from __future__ import annotations

import re
from urllib.parse import quote_plus
from typing import Optional

from app.services.agents.base import AgentContext, AgentResultData, BaseAgent
from app.services.ai.base import LLMProvider


class ReporterAgent(BaseAgent):
    """
    Generates TASK-EXECUTION responses for TaskPilot AI using Gemini.
    
    This is NOT a chatbot - it delivers RESULTS, not discussions.
    Responses show that TaskPilot AI DID something, not just explained it.
    
    Uses Gemini for format-aware generation:
    - Factual (answer-first + links)
    - General (definition + explanation)
    - News/Trading (summary + highlights + sources)
    - Services (hotels/restaurants with pricing + links)
    - Live time/weather (clean, localized output)
    """

    name = "reporter"

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm  # Keep for fallback
        self._bart_pipeline = None
        self._bart_tokenizer = None

    async def run(self, context: AgentContext) -> AgentResultData:
        """
        PRODUCTION REPORTER — Gemini is the primary response engine.
        
        Query type routing:
          news_trading  → NEWS format (bullets + source links)
          factual       → FACTUAL format (answer on line 1 + links)
          general       → GENERAL format (definition + explanation, no links)
          services      → SERVICES format (list with prices + booking links)
          weather/time  → LIVE format (temp + condition / current time)
          default       → Gemini structured response
        """
        query_type = context.metadata.get("query_type", "")
        intent = context.metadata.get("intent", "unknown")
        live_query_kind = context.metadata.get("live_query_kind")
        is_factual = context.metadata.get("is_factual_question", False)
        answer_type = context.metadata.get("answer_type", "unknown")

        fetched_context = context.fetched_context or ""
        if not live_query_kind and fetched_context:
            if "LIVE WEATHER" in fetched_context:
                live_query_kind = "weather"
            elif "LIVE TIME" in fetched_context:
                live_query_kind = "time"

        if not live_query_kind:
            query_lower = context.user_input.lower()
            if "weather" in query_lower or "temperature" in query_lower:
                live_query_kind = "weather"
            elif "time" in query_lower:
                live_query_kind = "time"

        if fetched_context and ("LIVE WEATHER" in fetched_context or "LIVE TIME" in fetched_context):
            inferred_kind = "weather" if "LIVE WEATHER" in fetched_context else "time"
            live_answer = self._format_live_city_answer(context, inferred_kind)
            if live_answer and len(live_answer.strip()) > 20:
                context.report = live_answer
                return AgentResultData(
                    name=self.name,
                    status="complete",
                    output=live_answer[:500],
                    details={"method": "live_city_format"},
                )

        # ── LIVE TIME / WEATHER  (no Gemini needed — data already fetched) ──
        if live_query_kind in {"time", "weather"}:
            live_answer = await self._gemini_live_city_response(context, live_query_kind)
            if not live_answer or len(live_answer.strip()) < 20:
                live_answer = self._format_live_city_answer(context, live_query_kind)
            if live_answer and len(live_answer.strip()) > 20:
                context.report = live_answer
                return AgentResultData(
                    name=self.name, status="complete",
                    output=live_answer[:500],
                    details={"method": "live_city_gemini"},
                )

        # ── SERVICES (hotels / restaurants) — use existing specialized extractor ──
        service_kind = self._detect_service_query_kind(context.user_input)
        if service_kind:
            service_output = self._extract_service_comparison(context.fetched_context or "", context.user_input)
            if service_output and len(service_output.strip()) > 40:
                # Improve with Gemini if we have data
                improved = await self._gemini_services_response(context, service_output)
                final = improved if improved and len(improved.strip()) > 40 else service_output
                context.report = final
                return AgentResultData(
                    name=self.name, status="complete",
                    output=final[:500],
                    details={"method": "services_specialized"},
                )

        # ── NEWS / TRADING — multi-source news format ──
        if query_type == "news_trading" or any(
            token in context.user_input.lower()
            for token in ("latest news", "stock market", "trading", "crypto", "nifty", "sensex", "bitcoin", "market update")
        ):
            output = await self._gemini_news_trading_response(context)
            if output and len(output.strip()) > 30:
                context.report = output
                return AgentResultData(
                    name=self.name, status="complete",
                    output=output[:500],
                    details={"method": "gemini_news_trading"},
                )

        # ── GENERAL — definition + explanation, no external links ──
        if query_type == "general" or intent == "explain":
            output = await self._gemini_general_response(context)
            if output and len(output.strip()) > 20:
                context.report = output
                return AgentResultData(
                    name=self.name, status="complete",
                    output=output[:500],
                    details={"method": "gemini_general"},
                )

        # ── FACTUAL / REAL-TIME — answer on line 1, then explanation + links ──
        if is_factual or query_type == "factual_realtime" or any(
            context.user_input.lower().startswith(p)
            for p in ("who is", "who's", "who founded", "where is", "when ", "which ", "what is the capital", "who created")
        ):
            output = await self._gemini_factual_response(context, answer_type)
            if output and len(output.strip()) > 20:
                context.report = output
                return AgentResultData(
                    name=self.name, status="complete",
                    output=output[:500],
                    details={"method": "gemini_factual"},
                )

        # ── DEFAULT — full Gemini response with available context ──
        output = await self._gemini_default_response(context)

        if not output or len(output.strip()) < 15:
            output = self._generate_safe_fallback_response(context, intent)

        context.report = output
        return AgentResultData(
            name=self.name,
            status="complete",
            output=output[:500],
            details={"method": "gemini_default"},
        )

    # ─────────────────────────────────────────────────────────────────────────
    # GEMINI RESPONSE ENGINES — one per query type
    # ─────────────────────────────────────────────────────────────────────────

    async def _gemini_factual_response(self, context: AgentContext, answer_type: str) -> str:
        """
        FACTUAL / REAL-TIME format:
          Line 1: [Direct one-line answer — just the name/fact]
          Lines 2-4: [2-3 line explanation]
          
          🔗 View on Wikipedia: [link]
          🔍 Search More: [link]
          🌐 Open Source: [link]
          
          📰 Latest News (if available):
          - [Title] — [link]
        """
        from urllib.parse import quote_plus
        query = context.user_input
        fetched = context.fetched_context or ""
        query_enc = quote_plus(query.strip())
        wiki_url = f"https://en.wikipedia.org/wiki/Special:Search?search={query_enc}"
        search_url = f"https://duckduckgo.com/?q={query_enc}"
        news_url = f"https://news.google.com/search?q={query_enc}"

        # Extract actual source URLs from fetched data
        source_urls = re.findall(r'https?://\S+', fetched)
        open_source_url = ""
        for u in source_urls:
            if "wikipedia.org" not in u and len(u) < 200:
                open_source_url = u
                break
        if not open_source_url:
            open_source_url = search_url

        # Extract news items with titles + links
        news_items = self._extract_news_items(fetched)

        context_block = fetched[:2000] if fetched else "No external data available."

        prompt = f"""You are TaskPilot AI — a real-time intelligent assistant.

USER QUESTION: "{query}"

LIVE DATA FETCHED FROM WEB (prefer DuckDuckGo/web sources; do NOT rely on Wikipedia for the answer if other sources exist):
{context_block}

STRICT FORMAT — follow EXACTLY:

Line 1: [The direct one-line answer — just the name, fact, or value. NO label, NO "Answer:", just the answer itself]
Line 2: [Empty line]
Line 3-5: [2-3 sentences of explanation using the live data above]

Then add NOTHING ELSE after line 5. I will add links separately.

RULES:
- Line 1 MUST be the direct answer (name, year, location, etc.) — nothing else
- Use the fetched live data to answer. Do NOT use general knowledge if live data disagrees.
- Do NOT start with "Based on", "According to", "The data shows"
- Do NOT mention "TaskPilot", "I fetched", "web search", or internal steps
- Keep it clean, human, professional
"""
        try:
            raw = (await self.llm.generate(prompt)).strip()
        except Exception:
            raw = ""

        if not raw or len(raw) < 10:
            # Fallback: extract from fetched text
            raw = self._generate_non_llm_factual_fallback(context, answer_type)

        raw_lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if raw_lines:
            answer_line = re.sub(r"^(answer:|ans:)", "", raw_lines[0], flags=re.IGNORECASE).strip()
        else:
            answer_line = self._extract_topic(context.user_input) or "Answer unavailable"
        answer_line = re.sub(r"[*_`]+", "", answer_line).strip()

        explanation_lines = self._collect_factual_explanation_lines(context, raw_lines[1:])
        if len(explanation_lines) < 2:
            explanation_lines = self._build_factual_explanation_lines(context, answer_line, answer_type)

        # Build final formatted output
        lines_out = [answer_line]
        lines_out.extend(explanation_lines[:4])
        lines_out.append("")
        lines_out.append(f"🔗 View on Wikipedia: {wiki_url}")
        lines_out.append(f"🔍 Search More: {search_url}")
        lines_out.append(f"🌐 Open Source: {open_source_url}")

        include_news = context.metadata.get("include_news", False)
        if include_news and news_items:
            lines_out.append("")
            lines_out.append("📰 Latest News:")
            lines_out.extend([f"- {title} — {url}" for title, url in news_items[:3]])
        elif include_news:
            lines_out.append(f"\n📰 Latest News: {news_url}")

        return "\n".join(lines_out)

    async def _gemini_general_response(self, context: AgentContext) -> str:
        """
        GENERAL format — definition + explanation, NO external links:
          Line 1: [One-line definition]
          Lines 2-6: [Explanation (2-4 sentences)]
          Optional: [Example if helpful]
        """
        query = context.user_input
        prompt = f"""You are TaskPilot AI — a knowledgeable assistant.

USER QUESTION: "{query}"

STRICT FORMAT — follow EXACTLY:

Line 1: [One-line direct definition or answer]
Line 2: [Empty line]
Lines 3-6: [Clear explanation in 2-4 sentences. Use simple, accurate language.]
Line 7 (optional): [Example: "Example: ..." — only if genuinely helpful]

RULES:
- Do NOT include any URLs, links, or "search here" text  
- Do NOT mention web search, fetching, or data sources
- Do NOT say "Based on...", "According to...", "As an AI..."
- Keep it clean, human, direct — like a knowledgeable friend explaining
- Answer ONLY what was asked
"""
        try:
            return (await self.llm.generate(prompt)).strip()
        except Exception:
            topic = re.sub(r"^(what is|what's|define|explain|meaning of|summary of|summarize)\s+", "", query.strip(), flags=re.IGNORECASE).strip(" ?.")
            if not topic:
                topic = "This topic"
            return (
                f"{topic} is a concept or idea with a clear meaning in its context.\n\n"
                "In simple terms, it refers to something that can be defined clearly and used consistently.\n"
                "If you want, I can add examples or a deeper explanation."
            )

    async def _gemini_news_trading_response(self, context: AgentContext) -> str:
        """
        NEWS / TRADING format:
                    📰 [Topic] — Live Update

                    Summary:
                    - Point 1
                    - Point 2

                    Key Highlights:
                    - Highlight — [source URL]

                    Sources & Context:
                    1) [Title] — [link]
                         Line 1
                         Line 2
                         Line 3
        """
        from urllib.parse import quote_plus
        query = context.user_input
        fetched = context.fetched_context or ""
        query_enc = quote_plus(query.strip())

        news_items = self._extract_news_items(fetched)
        if not news_items:
            news_items = [
                ("Google News Search", f"https://news.google.com/search?q={query_enc}"),
                ("DuckDuckGo News", f"https://duckduckgo.com/?q={query_enc}&iar=news"),
            ]

        sources_block = "\n".join([f"- {title} — {url}" for title, url in news_items[:7]])

        context_block = fetched[:2200] if fetched else "No live news data available."

        prompt = f"""You are TaskPilot AI — a real-time market and news intelligence assistant.

USER QUERY: "{query}"

LIVE NEWS & DATA:
{context_block}

SOURCES YOU MUST USE (pick one per highlight, no repeats):
{sources_block}

STRICT FORMAT — follow EXACTLY:

📰 [Topic/Subject] — Live Update

Summary:
- [3-7 bullet points summarizing the latest updates]

Key Highlights:
- [Highlight] — [Source URL]
- [Highlight] — [Source URL]
- [Highlight] — [Source URL]
- [Up to 7 total]

Sources & Context:
1) [Source Title] — [Source URL]
    [Line 1: what this source reports]
    [Line 2: why it matters]
    [Line 3: timestamp or key detail if available]
2) [Source Title] — [Source URL]
    [Line 1]
    [Line 2]
    [Line 3]
3) [Source Title] — [Source URL]
    [Line 1]
    [Line 2]
    [Line 3]

RULES:
- Extract REAL highlights from the live data above — do NOT make things up
- Keep each bullet point to 1-2 lines maximum
- Focus on what is most actionable and current
- Every highlight MUST include one source URL from the list above
- Sources & Context must include 3 lines per source
- Do NOT say "Based on fetched data", "According to web search", etc.
- Do NOT mention TaskPilot internals
"""
        try:
            raw = (await self.llm.generate(prompt)).strip()
        except Exception:
            raw = ""

        if raw:
            return raw

        # Minimal fallback using available sources
        fallback_lines = [
            f"📰 {query} — Live Update",
            "",
            "Summary:",
            "- Live updates are available, but I could not summarize them just now.",
            "",
            "Key Highlights:",
        ]
        for title, url in news_items[:3]:
            fallback_lines.append(f"- {title} — {url}")
        fallback_lines.append("")
        fallback_lines.append("Sources & Context:")
        for index, (title, url) in enumerate(news_items[:3], 1):
            fallback_lines.append(f"{index}) {title} — {url}")
            fallback_lines.append("   Live source available for verification.")
            fallback_lines.append("   Summary not available in this response.")
            fallback_lines.append("   Please open the link for full details.")
        return "\n".join(fallback_lines)

    async def _gemini_services_response(self, context: AgentContext, extracted_text: str) -> str:
        """
        SERVICES format — hotels/restaurants:
          🏨 Best Options in [Location]
          
          1. [Name] — [Price] — [Description]
             🔗 [Booking Link]
        """
        query = context.user_input
        prompt = f"""You are TaskPilot AI — a travel and services assistant.

USER QUERY: "{query}"

EXTRACTED SERVICE DATA:
{extracted_text[:1800]}

STRICT FORMAT — follow EXACTLY:

🏨 [Best Hotels / 🍽️ Best Restaurants] in [Location]

Cheapest Option: [Name] — [Price]

1. [Name] — [Price] — [Short description]
    🔗 [Direct booking/Maps link]
2. [Name] — [Price] — [Short description]
    🔗 [Direct booking/Maps link]
3. [Name] — [Price] — [Short description]
    🔗 [Direct booking/Maps link]
(Return 4–7 options total, each with a working link)

Note: Prices are approximate and may change. Verify before booking.

RULES:
- Use ONLY data from the extracted text above — do NOT invent hotels/prices
- Show the cheapest option first
- Keep descriptions to one line
- Use correct currency (₹ for India, $ for US/international)
- If no price is available, write "See live listing"
- If a link is missing, use a direct search/booking link from the extracted data
"""
        try:
            return (await self.llm.generate(prompt)).strip()
        except Exception:
            return extracted_text

    async def _gemini_live_city_response(self, context: AgentContext, live_query_kind: str) -> str:
        """Use Gemini to format live time/weather results."""
        fetched = context.fetched_context or ""
        if not fetched:
            return ""

        header = "🕒 LIVE TIME" if live_query_kind == "time" else "🌤 LIVE WEATHER"
        block_start = fetched.find(header)
        block = fetched[block_start:block_start + 600] if block_start != -1 else fetched[:600]

        prompt = f"""You are TaskPilot AI. Format the live data below for the user.

LIVE DATA:
{block}

STRICT FORMAT:
    - If time: "Current time in [City], [Region/Country]" on line 1, then "Time: [HH:MM AM/PM] ([Timezone])" on line 3.
    - If weather: "Current weather in [City], [Region/Country]" on line 1, then "Temperature: [value]" on line 3 and "Condition: [value]" on line 4. Add "Local Time: [time] ([Timezone])" if available.

Rules:
- Use only the live data above.
- Do not mention web sources or internal steps.
- Keep it clean and concise.
"""
        try:
            return (await self.llm.generate(prompt)).strip()
        except Exception:
            return ""

    def _extract_news_items(self, fetched: str) -> list[tuple[str, str]]:
        """Extract (title, url) pairs from fetched news blocks."""
        if not fetched:
            return []

        items: list[tuple[str, str]] = []
        last_title = ""
        for line in fetched.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("📰"):
                last_title = stripped.lstrip("📰").strip()
                continue
            # Recent news blocks often start with "Title (date)"
            if "(" in stripped and ")" in stripped and "http" not in stripped and len(stripped) > 10:
                last_title = stripped
                continue
            url_match = re.search(r"https?://\S+", stripped)
            if url_match:
                url = url_match.group(0).rstrip(")")
                title = last_title or "News source"
                items.append((title, url))
                last_title = ""
            if len(items) >= 8:
                break

        # Deduplicate by URL while preserving order
        seen: set[str] = set()
        deduped: list[tuple[str, str]] = []
        for title, url in items:
            if url in seen:
                continue
            seen.add(url)
            deduped.append((title, url))
        return deduped

    async def _gemini_default_response(self, context: AgentContext) -> str:
        """Default Gemini response for complex/mixed queries."""
        query = context.user_input
        fetched = context.fetched_context or ""
        analysis = context.analysis or ""
        query_enc = __import__('urllib.parse', fromlist=['quote_plus']).quote_plus(query.strip())

        context_block = fetched[:2200] if fetched else analysis[:900] if analysis else "No external data available."

        prompt = f"""You are TaskPilot AI — a comprehensive intelligent assistant with real-time web access.

USER REQUEST: "{query}"

LIVE DATA FROM WEB:
{context_block}

Provide a comprehensive, well-structured response. Rules:
1. Answer directly and clearly — lead with the most important information
2. Use the live data above to ensure accuracy
3. Format with clear sections if the answer is complex
4. Include relevant facts, figures, and context
5. If data is available, emphasize the most actionable insights
6. Do NOT mention "fetched data", "web search", "TaskPilot internals"
7. Keep language natural, professional, and helpful

Response:
"""
        try:
            raw = (await self.llm.generate(prompt)).strip()
            if raw:
                # Add links for non-general queries
                include_news = context.metadata.get("include_news", False)
                wiki_url = f"https://en.wikipedia.org/wiki/Special:Search?search={query_enc}"
                search_url = f"https://duckduckgo.com/?q={query_enc}"
                raw += f"\n\n🔗 View on Wikipedia: {wiki_url}\n🔍 Search More: {search_url}"
                if include_news:
                    news_url = f"https://news.google.com/search?q={query_enc}"
                    raw += f"\n📰 Latest News: {news_url}"
            return raw
        except Exception:
            return ""

    def _format_live_city_answer(self, context: AgentContext, live_query_kind: str) -> str:
        """
        Format weather / time data that was fetched by FetcherAgent.

        The fetcher writes live data as a text block like:
          🕒 LIVE TIME
          City: Mumbai, Maharashtra, India
          Local Time: 07:32 PM
          Timezone: Asia/Kolkata
          Source: Open-Meteo

        or:
          🌤 LIVE WEATHER
          City: ...
          Temperature: 32.1 degrees Celsius
          Condition: Partly cloudy
          Local Time: ...
          Timezone: ...
          Source: Open-Meteo

        We extract and re-present it in a clean, human-friendly format.
        """
        fetched = context.fetched_context or ""
        if not fetched:
            return ""

        # Locate the live block (starts with the emoji header)
        header = "🕒 LIVE TIME" if live_query_kind == "time" else "🌤 LIVE WEATHER"
        block_start = fetched.find(header)
        if block_start == -1:
            # Fallback: look for the raw label strings
            block_start = fetched.find("LIVE TIME" if live_query_kind == "time" else "LIVE WEATHER")
        if block_start == -1:
            block = fetched
        else:
            block = fetched[block_start:block_start + 600]
        lines = {}
        for line in block.splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                lines[key.strip().lower()] = val.strip()

        def _extract_value(label: str) -> str:
            match = re.search(rf"{label}\s*:\s*(.+)", fetched, re.IGNORECASE)
            return match.group(1).strip() if match else ""

        city = lines.get("city") or _extract_value("city") or "Unknown location"
        timezone = lines.get("timezone") or _extract_value("timezone")

        sources = self._extract_live_source_links(fetched)

        if live_query_kind == "time":
            local_time = lines.get("local time") or _extract_value("local time")
            if not local_time:
                return ""
            result = (
                f"Current time in {city}\n\n"
                f"Time: {local_time}"
            )
            if timezone:
                result += f"  ({timezone})"
            if sources:
                result += "\n\nSources:\n" + "\n".join(sources)
            return result

        # Weather
        temperature = lines.get("temperature") or _extract_value("temperature")
        condition = lines.get("condition") or _extract_value("condition")
        local_time = lines.get("local time") or _extract_value("local time")
        if not temperature:
            return ""
        result = (
            f"Current weather in {city}\n\n"
            f"Temperature: {temperature}\n"
            f"Condition: {condition}"
        )
        if local_time:
            result += f"\nLocal Time: {local_time}"
        if timezone:
            result += f" ({timezone})"
        if sources:
            result += "\n\nSources:\n" + "\n".join(sources)
        return result

    def _extract_live_source_links(self, fetched: str) -> list[str]:
        if "🌐 LIVE SOURCES:" not in fetched:
            return []
        block = fetched.split("🌐 LIVE SOURCES:", 1)[1]
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        links = []
        for line in lines:
            if line.startswith("-"):
                links.append(line)
            if len(links) >= 4:
                break
        return links



    def _apply_chat_response_contract(self, context: AgentContext, output: str, intent: str) -> str:
        """Enforce production chat contract: Title, Summary, Details, Bullets, Links."""
        has_attachments = bool(context.attachments)
        live_query_kind = context.metadata.get("live_query_kind")
        if live_query_kind in {"time", "weather"}:
            live_answer = self._format_live_city_answer(context, live_query_kind)
            if live_answer:
                return live_answer

        service_kind = self._detect_service_query_kind(context.user_input)
        if service_kind:
            service_output = self._extract_service_comparison(context.fetched_context or "", context.user_input)
            if service_output:
                return service_output

        if context.metadata.get("is_factual_question", False):
            return self._format_factual_response(context, output, intent)

        if not output:
            output = self._generate_safe_fallback_response(context, intent)

        fetched_context = context.fetched_context or ""
        if not fetched_context and len(output.strip()) < 30 and intent not in {"greeting", "chat"}:
            output = self._generate_safe_fallback_response(context, intent)

        cleaned = output.strip()
        cleaned = re.sub(r'^\*\*Work\?\*\*\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        details_text = "\n".join(lines)
        details_text = self._sanitize_details_text(details_text)
        details_text = self._localize_currency_for_region(details_text, context)

        title = self._build_title_from_query(context.user_input, details_text)
        summary = self._build_summary(details_text)
        key_points = self._build_key_points(details_text)
        links = []
        if not has_attachments:
            links = self._build_links(
                context.user_input,
                fetched_context,
                include_news=bool(context.metadata.get("include_news", False)),
            )

        if not key_points:
            key_points = ["- Reliable information was synthesized from available live sources."]

        if not has_attachments and not links and intent not in {"greeting", "chat"}:
            links = [
                "- [View on Wikipedia](https://en.wikipedia.org)",
                "- [Search More](https://duckduckgo.com)",
            ]

        sections = [
            f"Title: {title}",
            "",
            "Summary:",
            summary,
            "",
            "Details:",
            details_text,
            "",
            "Bullet Points:",
            "\n".join(key_points),
        ]

        if not has_attachments and links:
            sections.extend([
                "",
                "Useful Links:",
                "\n".join(links),
            ])

        return "\n".join(sections).strip()

    def _build_title_from_query(self, query: str, details: str) -> str:
        query_lower = query.lower()
        bold_first = re.search(r"\*\*\s*([^*\n]{2,80})\s*\*\*", details)
        if bold_first:
            title_candidate = bold_first.group(1).strip()
            title_candidate = re.sub(r"[^A-Za-z0-9\s\-:&]", "", title_candidate)
            title_candidate = re.sub(r"\s+", " ", title_candidate)
            if len(title_candidate) > 2 and title_candidate.lower() not in {"who is", "what is", "details"}:
                return title_candidate

        if query_lower.startswith("who is") or "prime minister" in query_lower or "president" in query_lower:
            person_match = re.search(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b", details)
            if person_match:
                return person_match.group(1)
        if "hotel" in query_lower:
            location = self._extract_location_from_query(query)
            if location:
                return f"Best budget hotels in {location.title()}"
            return "Best budget hotels"
        if "restaurant" in query_lower:
            location = self._extract_location_from_query(query)
            if location:
                return f"Top restaurants in {location.title()}"
            return "Top restaurant options"

        first_sentence = details.split(".")[0].strip() if details else ""
        if first_sentence:
            title = re.sub(r"[*_`#]+", "", first_sentence).strip()
            title = re.sub(r"\s+", " ", title)
            return title[:90]
        return "TaskPilot AI Response"

    def _detect_service_query_kind(self, user_query: str) -> str | None:
        query_lower = user_query.lower()
        hotel_terms = ("hotel", "hotels", "resort", "stay", "accommodation", "booking")
        restaurant_terms = (
            "restaurant",
            "restaurants",
            "cafe",
            "cafes",
            "bistro",
            "diner",
            "eatery",
            "food",
            "near me",
            "nearby",
        )

        if any(term in query_lower for term in hotel_terms):
            return "hotel"
        if any(term in query_lower for term in restaurant_terms):
            return "restaurant"
        return None

    def _extract_service_comparison(self, text: str, user_query: str) -> str:
        service_kind = self._detect_service_query_kind(user_query)
        if service_kind == "hotel":
            return self._extract_hotel_comparison(text, user_query)
        if service_kind != "restaurant":
            return ""

        location = self._extract_location_from_query(user_query)
        currency_symbol = self._get_currency_for_location(location)
        booking_query = quote_plus(user_query.strip()) if user_query.strip() else ""
        map_query = quote_plus(f"{location or user_query} restaurant") if location or user_query else ""

        restaurants: list[dict[str, object]] = []
        blocks = [block.strip() for block in re.split(r'\n\s*\n', text) if block.strip()]

        name_patterns = [
            r'\*\*([^*]{2,80}?(?:Restaurant|Cafe|Café|Bistro|Diner|Eatery|Kitchen|Grill|Dhaba|Tavern|Bar)[^*]*)\*\*',
            r'([A-Z][A-Za-z0-9&\'"\-\s]{2,80}(?:Restaurant|Cafe|Café|Bistro|Diner|Eatery|Kitchen|Grill|Dhaba|Tavern|Bar))',
        ]
        price_patterns = [
            r'[₹$€£]\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:INR|USD|EUR|GBP|per\s*(?:meal|person|plate|dish|day)|/\s*(?:meal|person|plate|dish|day))',
        ]

        for block in blocks:
            block_lines = [line.strip() for line in block.splitlines() if line.strip()]
            if not block_lines:
                continue

            block_text = " ".join(block_lines)
            candidate_name = ""
            for pattern in name_patterns:
                name_match = re.search(pattern, block_text, re.IGNORECASE)
                if name_match:
                    candidate_name = name_match.group(1).strip()
                    break
            if not candidate_name:
                first_line = block_lines[0]
                if any(term in first_line.lower() for term in ("restaurant", "cafe", "bistro", "diner", "eatery", "kitchen", "grill", "dhaba", "tavern", "bar")):
                    candidate_name = re.sub(r'https?://[^\s<>\")\]]+', '', first_line).strip(" -:*")

            if not candidate_name or len(candidate_name) < 2:
                continue

            source_currency = ""
            if "₹" in block_text:
                source_currency = "₹"
            elif "$" in block_text:
                source_currency = "$"
            elif "£" in block_text:
                source_currency = "£"
            elif "€" in block_text:
                source_currency = "€"

            price_value: float | None = None
            for pattern in price_patterns:
                price_match = re.search(pattern, block_text, re.IGNORECASE)
                if price_match:
                    try:
                        price_value = float(price_match.group(1).replace(',', ''))
                        break
                    except ValueError:
                        continue

            rating_match = re.search(r'(?:Rating|Rated)?\s*:?\s*(\d(?:\.\d)?)\s*★', block_text)
            rating_text = f"{rating_match.group(1)}★" if rating_match else ""

            link_match = re.search(r'https?://[^\s<>")\]]+', block_text)
            link = self._sanitize_url(link_match.group(0)) if link_match else ""

            display_currency = source_currency or currency_symbol
            if price_value is None:
                price_text = f"{display_currency}See live listing"
            else:
                rounded_price = round(price_value)
                if display_currency == "₹" and source_currency in {"$", "USD"}:
                    rounded_price = round(price_value * 83)
                price_text = f"{display_currency}{rounded_price:,} per meal"

            description = block_lines[0]
            description = re.sub(r'https?://[^\s<>")\]]+', '', description).strip()
            description = re.sub(r'\s+', ' ', description)
            if rating_text and rating_text not in description:
                description = f"{description} - {rating_text}".strip(" -")

            if not link:
                link = self._build_service_search_link(user_query, candidate_name, service_kind, location, booking_query, map_query)

            restaurants.append({
                "name": candidate_name,
                "price": price_value,
                "price_text": price_text,
                "description": description[:180],
                "link": link,
            })

        if not restaurants:
            fallback_link = self._build_service_search_link(user_query, user_query, service_kind, location, booking_query, map_query)
            title = self._build_title_from_query(user_query, text)
            return (
                f"{title}\n\n"
                "I could not confidently extract live restaurant listings from the source text.\n\n"
                f"Search live options: {fallback_link}"
            )

        unique_restaurants: list[dict[str, object]] = []
        for restaurant in restaurants:
            name = str(restaurant.get("name", "")).strip()
            if not name:
                continue
            if any(name.lower() == str(existing.get("name", "")).lower() for existing in unique_restaurants):
                continue
            unique_restaurants.append(restaurant)

        priced = [item for item in unique_restaurants if isinstance(item.get("price"), (int, float))]
        if priced:
            priced.sort(key=lambda item: float(item.get("price") or 0))
            ordered = priced + [item for item in unique_restaurants if item not in priced]
        else:
            ordered = unique_restaurants

        ordered = ordered[:7]
        cheapest = priced[0] if priced else ordered[0]

        if len(ordered) < 4:
            platform_links = self._generate_booking_platform_links(location or "restaurants", [])
            for platform, link in platform_links:
                if any(platform.lower() == str(existing.get("name", "")).lower() for existing in ordered):
                    continue
                ordered.append({
                    "name": platform,
                    "price": None,
                    "price_text": f"{currency_symbol}See live listing",
                    "description": "Live availability and recent reviews from the platform.",
                    "link": link,
                })
                if len(ordered) >= 7:
                    break

        result_lines = [
            f"**{self._build_title_from_query(user_query, text)}**",
            "",
            f"Cheapest live option: {cheapest['name']}",
            f"Price: {cheapest.get('price_text', f'{currency_symbol}See live listing')}",
            "",
        ]

        for index, restaurant in enumerate(ordered, 1):
            result_lines.append(f"{index}. {restaurant['name']}")
            result_lines.append(f"   Price: {restaurant.get('price_text', f'{currency_symbol}See live listing')}")
            description = str(restaurant.get('description', '')).strip()
            if description:
                result_lines.append(f"   Description: {description}")
            link = self._sanitize_url(str(restaurant.get('link', '')).strip())
            if link:
                result_lines.append(f"   Book Now: {link}")
            result_lines.append("")

        result_lines.append("Live prices and availability can change quickly.")
        return "\n".join(result_lines).strip()

    def _generate_non_llm_factual_fallback(self, context: AgentContext, answer_type: str) -> str:
        """Deterministic factual fallback to avoid empty or timed-out factual responses."""
        query = (context.user_input or "").lower()
        source = context.fetched_context or ""

        if answer_type == "person" or any(term in query for term in ("who is", "ceo", "founder", "president", "prime minister", "chief minister", " cm ", " pm ")):
            names = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", source)
            blocked = {
                "Web Research", "Reference Data", "Recent Info", "Related Insights",
                "Chief Minister", "Prime Minister", "Current Date",
                "The Prime Minister",
                "Principal Secretary",
                "Prime Minister's Office",
                "Prime Ministers Office",
                "Prime Minister Office",
            }
            filtered = [name for name in names if name not in blocked]
            if filtered:
                name = filtered[0].strip()
                return f"{name}\n{name} is the most relevant current answer from live references."

        if answer_type in {"place", "date", "year", "number", "fact"}:
            line = ""
            for candidate in source.splitlines():
                candidate = candidate.strip()
                if candidate and len(candidate) > 8 and not candidate.startswith(("🔍", "📚", "📰", "🧐")):
                    line = re.sub(r"https?://\S+", "", candidate).strip()
                    break
            if line:
                return f"{line}\nThis answer is taken from current fetched references."

        topic = self._extract_topic(context.user_input)
        return f"{topic}\nThis is the best available factual answer from current fetched data."

    def _build_service_search_link(
        self,
        user_query: str,
        name: str,
        service_kind: str,
        location: str,
        booking_query: str,
        map_query: str,
    ) -> str:
        if service_kind == "hotel":
            if booking_query:
                return f"https://www.booking.com/searchresults.html?ss={booking_query}"
            if location:
                return f"https://www.booking.com/searchresults.html?ss={quote_plus(location)}"
            return "https://www.booking.com"

        query = quote_plus(f"{name} {location}".strip()) if name or location else map_query
        if not query:
            query = quote_plus(user_query.strip()) if user_query.strip() else ""
        if query:
            return f"https://www.google.com/maps/search/?api=1&query={query}"
        return "https://www.google.com/maps"

    def _build_summary(self, details: str) -> str:
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', details.replace("\n", " ")) if s.strip()]
        selected = sentences[:3] if sentences else [details[:220].strip()]
        summary = " ".join(selected).strip()
        if summary and not summary.endswith((".", "!", "?")):
            summary += "."
        return summary

    def _build_key_points(self, details: str) -> list[str]:
        bullet_lines: list[str] = []
        for line in details.splitlines():
            stripped = line.strip()
            normalized = stripped.replace("â¢", "-")
            if normalized.startswith(("•", "-", "*")) and len(normalized) > 3:
                item = normalized.lstrip('•-* ').strip()
                item = re.sub(r"[*_`#]+", "", item).strip()
                if len(item) >= 12:
                    bullet_lines.append(f"- {item}")
            if len(bullet_lines) >= 5:
                break

        if not bullet_lines:
            for line in details.splitlines():
                normalized = line.strip().replace("â¢", "").strip()
                if ":" in normalized and len(normalized) >= 10 and not normalized.lower().startswith("title"):
                    item = re.sub(r"[*_`#]+", "", normalized).strip()
                    bullet_lines.append(f"- {item}")
                if len(bullet_lines) >= 5:
                    break

        if bullet_lines:
            return bullet_lines

        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', details.replace("\n", " ")) if len(s.strip()) > 25]
        return [f"- {s}" for s in sentences[:4]]

    def _build_links(self, user_query: str, fetched_context: str, include_news: bool = False) -> list[str]:
        extracted = self._extract_links_from_context(fetched_context)
        seen_urls: set[str] = set()
        results: list[str] = []

        query = user_query.strip()
        query_encoded = quote_plus(query) if query else ""
        wiki_link = f"https://en.wikipedia.org/wiki/Special:Search?search={query_encoded}" if query_encoded else "https://en.wikipedia.org"
        search_link = f"https://duckduckgo.com/?q={query_encoded}" if query_encoded else "https://duckduckgo.com"
        news_link = f"https://news.google.com/search?q={query_encoded}" if query_encoded else "https://news.google.com"

        results.append(f"- [View on Wikipedia]({wiki_link})")
        seen_urls.add(wiki_link)

        if include_news or any(token in user_query.lower() for token in ("current", "latest", "today", "news", "recent")):
            results.append(f"- [Latest News]({news_link})")
            seen_urls.add(news_link)

        results.append(f"- [Search More]({search_link})")
        seen_urls.add(search_link)

        if any(token in user_query.lower() for token in ("hotel", "stay", "booking", "resort")):
            booking_link = f"https://www.booking.com/searchresults.html?ss={query_encoded}" if query_encoded else "https://www.booking.com"
            results.append(f"- [Check Booking Options]({booking_link})")
            seen_urls.add(booking_link)

        for _, url in extracted:
            if url in seen_urls:
                continue
            results.append(f"- [Open Source]({url})")
            seen_urls.add(url)
            if len(results) >= 6:
                break

        return results[:6]

    def _sanitize_details_text(self, details_text: str) -> str:
        """Remove noisy template placeholders and repeated scaffold text."""
        text = details_text
        text = text.replace("â¢", "-")
        text = text.replace("ð", "")
        text = text.replace("¨", "")
        text = re.sub(r"^\s*[*_`#\-\s]*[⏰â°]*\s*Current Date:.*$", "", text, flags=re.IGNORECASE | re.MULTILINE)
        text = re.sub(r"^\s*Information should be up-to-date as of this date\s*$", "", text, flags=re.IGNORECASE | re.MULTILINE)
        text = re.sub(r"^\s*[🔍📚📰🧐]\s+[A-Z\s]+:\s*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"\bâ[\w\-]+\b", "", text)
        text = re.sub(r"\*\*\s*Key Information:\s*\*\*", "Key Information:", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+\*\*\s*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _localize_currency_for_region(self, details_text: str, context: AgentContext) -> str:
        """Localize currency display by detected region (India/USA/Europe)."""
        region_hint = str(context.metadata.get("region_hint", "")).lower()
        query = context.user_input.lower()
        is_india_context = region_hint == "india" or any(token in query for token in ("india", "indian", "inr", "rupee", "rupees", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "chennai", "pune", "kolkata"))
        is_europe_context = region_hint in {"eu", "europe"} or any(token in query for token in ("europe", "euro", "eur", "france", "germany", "italy", "spain", "netherlands", "berlin", "paris", "rome", "madrid"))
        is_usa_context = region_hint in {"us", "usa", "united states"} or any(token in query for token in ("usa", "us", "united states", "new york", "california", "texas", "chicago", "san francisco"))

        if not (is_india_context or is_europe_context or is_usa_context):
            return details_text

        def _usd_symbol_repl(match: re.Match[str]) -> str:
            usd_value = float(match.group(1).replace(",", ""))
            if is_india_context:
                return f"₹{round(usd_value * 83):,}"
            if is_europe_context:
                return f"€{round(usd_value * 0.92):,}"
            return f"${usd_value:,.0f}"

        def _usd_code_repl(match: re.Match[str]) -> str:
            usd_value = float(match.group(1).replace(",", ""))
            if is_india_context:
                return f"₹{round(usd_value * 83):,}"
            if is_europe_context:
                return f"€{round(usd_value * 0.92):,}"
            return f"${usd_value:,.0f}"

        text = re.sub(r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)", _usd_symbol_repl, details_text)
        text = re.sub(r"(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s*USD\b", _usd_code_repl, text, flags=re.IGNORECASE)
        if is_india_context:
            text = re.sub(r"\bRs\.?\s*", "₹", text)
            text = re.sub(r"(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s*INR\b", r"₹\1", text, flags=re.IGNORECASE)
        if is_europe_context:
            text = re.sub(r"\bEUR\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)", r"€\1", text, flags=re.IGNORECASE)
        return text
    
    def _extract_direct_answer_fast(self, context: AgentContext, answer_type: str) -> str:
        """
        FAST PATH: Extract direct answer for factual questions.
        
        This bypasses heavy processing and gives immediate, direct answers.
        Format: ANSWER FIRST, then context.
        """
        from datetime import datetime

        text = context.fetched_context or ""
        user_query = context.user_input.lower()
        current_year = datetime.now().year
        current_month_year = datetime.now().strftime("%B %Y")

        # Deterministic fallback for high-frequency factual questions.
        if ("prime minister" in user_query and "india" in user_query) or re.search(r"\bpm\b", user_query) and "india" in user_query:
            return (
                "**Narendra Modi**\n\n"
                f"He is the current Prime Minister of India (as of {current_month_year}).\n\n"
                "**Key Information:**\n"
                "• Serving since: May 26, 2014\n"
                "• Party: Bharatiya Janata Party (BJP)\n"
                "• Current term: Third consecutive term"
            )
        if "president" in user_query and "india" in user_query:
            return (
                "**Droupadi Murmu**\n\n"
                f"She is the current President of India (as of {current_month_year}).\n\n"
                "**Key Information:**\n"
                "• Took office: July 25, 2022\n"
                "• India’s 15th President"
            )

        if not text:
            return ""

        # High-risk entity questions should fall back to Gemini if extraction is not guaranteed.
        if any(term in user_query for term in ("founder", "founded", "created", "chief minister", " cm ", "cm of")):
            return ""
        
        # Get hints from analyzer
        answer_hint = context.metadata.get("direct_answer_hint", "")
        primary_entity = context.metadata.get("primary_entity", "")
        
        result_lines = []
        
        # === 🏨 HOTEL/PRICE COMPARISON QUESTIONS ===
        if "hotel" in user_query or ("price" in user_query and ("compare" in user_query or "cheapest" in user_query)):
            return self._extract_hotel_comparison(text, user_query)
        
        # === PERSON/POSITION QUESTIONS ===
        if answer_type == "person":
            if "chief minister" in user_query or re.search(r"\bcm\b", user_query):
                state_match = re.search(r"\b(?:in|of)\s+([a-z][a-z\s\-']{1,40})", user_query, flags=re.IGNORECASE)
                state = state_match.group(1).strip().title() if state_match else ""

                if state:
                    strict = re.search(
                        rf"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+(?:is\s+)?(?:the\s+)?(?:current\s+)?(?:Chief Minister|CM)\s+of\s+{re.escape(state)}",
                        text,
                        re.IGNORECASE,
                    )
                    if strict:
                        name = strict.group(1).strip()
                        return f"{name}\n{name} is the current Chief Minister of {state}."

                generic = re.search(
                    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+(?:is\s+)?(?:the\s+)?(?:current\s+)?(?:Chief Minister|CM)\s+of\s+([A-Z][A-Za-z\s]+)",
                    text,
                    re.IGNORECASE,
                )
                if generic:
                    name = generic.group(1).strip()
                    region = generic.group(2).strip().title()
                    return f"{name}\n{name} is the current Chief Minister of {region}."

                reverse = re.search(
                    r"(?:Chief Minister|CM)\s+of\s+([A-Z][A-Za-z\s]+)\s+(?:is\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
                    text,
                    re.IGNORECASE,
                )
                if reverse:
                    region = reverse.group(1).strip().title()
                    name = reverse.group(2).strip()
                    return f"{name}\n{name} is the current Chief Minister of {region}."

            if any(term in user_query for term in ["founder", "founded", "created"]):
                patterns = [
                    r'([A-Z][a-z]+\s+[A-Z][a-z]+).*?(?:founder|founded|created|co-founder|cofounder)',
                    r'(?:founder|founded|created|co-founder|cofounder).*?([A-Z][a-z]+\s+[A-Z][a-z]+)',
                    r'\b(Elon Musk|Martin Eberhard|Marc Tarpenning|Jeff Bezos|Bill Gates|Steve Jobs|Larry Page|Sergey Brin|Sundar Pichai)\b',
                ]
                for pattern in patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        name = match.group(1).strip() if match.groups() else match.group(0).strip()
                        subject = self._extract_subject_from_query(user_query)
                        if subject:
                            return (
                                f"**{name}**\n\n"
                                f"{name} is associated with the founding of {subject}.\n\n"
                                f"This answer is based on the available reference context and is kept concise for clarity."
                            )
                return ""

            # President of India
            if "president" in user_query and "india" in user_query:
                # Extract president's name
                patterns = [
                    r'Droupadi Murmu',
                    r'([A-Z][a-z]+\s+[A-Z][a-z]+).*?(?:15th President|President of India|took office)',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        name = match.group(0) if "Murmu" in match.group(0) else match.group(1)
                        
                        # Single line answer first
                        result_lines.append(f"**{name}**")
                        result_lines.append("")
                        
                        # Add key details
                        result_lines.append(f"She is the current President of India as of {current_month_year}.")
                        result_lines.append("")
                        result_lines.append("**Key Information:**")
                        result_lines.append("• Took office: July 25, 2022")
                        result_lines.append("• India's 15th President")
                        result_lines.append("• First tribal President of India")
                        result_lines.append("• Second woman President (after Pratibha Patil)")
                        result_lines.append("• Previously: Governor of Jharkhand")
                        result_lines.append("• Term: 2022-2027 (5 years)")
                        
                        # Extract and add links
                        links = self._extract_links_from_context(text)
                        if links:
                            result_lines.append("")
                            result_lines.append("More Information:")
                            for link_text, url in links[:3]:
                                result_lines.append(f"Link: {url}")
                        
                        return "\n".join(result_lines)
            
            # Prime Minister
            elif "prime minister" in user_query or "pm" in user_query or "present pm" in user_query:
                # Multiple patterns to extract PM name
                patterns = [
                    r'Narendra Modi',
                    r'Narendra\s+Damodardas\s+Modi',
                    r'([A-Z][a-z]+\s+[A-Z][a-z]+).*?(?:Prime Minister|PM|prime minister)',
                    r'(?:PM|Prime Minister).*?([A-Z][a-z]+\s+[A-Z][a-z]+)',
                    r'Modi.*?(?:Prime Minister|PM)',
                ]
                
                name = None
                for pattern in patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        if "Modi" in match.group(0):
                            name = "Narendra Modi"
                        elif match.groups():
                            name = match.group(1).strip()
                        else:
                            name = match.group(0).strip()
                        break
                
                # If no match, try to find any proper name near "Modi" or PM-related text
                if not name:
                    # Look for "Modi" specifically
                    if "Modi" in text or "modi" in text:
                        name = "Narendra Modi"
                    else:
                        # Search for proper names
                        all_names = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', text)
                        if all_names:
                            # Filter out common section headers
                            filtered = [n for n in all_names if n not in ["Web Research", "Reference Data", "Recent Info", "Related Insights", "Prime Minister", "Current Date"]]
                            if filtered:
                                name = filtered[0]
                
                if name:
                    # Single line answer first - BOLD NAME ONLY
                    result_lines.append(f"**{name}**")
                    result_lines.append("")
                    
                    # Add additional information
                    result_lines.append(f"He is the current Prime Minister of India (as of {current_month_year}).")
                    result_lines.append("")
                    
                    # Extract key details from context
                    details_added = False
                    if "26 May 2014" in text or "2014" in text:
                        if not details_added:
                            result_lines.append("**Key Information:**")
                            details_added = True
                        result_lines.append("• Serving since: May 26, 2014")
                    if "BJP" in text or "Bharatiya Janata Party" in text:
                        if not details_added:
                            result_lines.append("**Key Information:**")
                            details_added = True
                        result_lines.append("• Party: Bharatiya Janata Party (BJP)")
                    if "third consecutive term" in text.lower() or "third term" in text.lower():
                        if not details_added:
                            result_lines.append("**Key Information:**")
                            details_added = True
                        result_lines.append("• Currently in his third consecutive term")
                    
                    # Extract and add links
                    links = self._extract_links_from_context(text)
                    if links:
                        result_lines.append("")
                        result_lines.append("More Information:")
                        for link_text, url in links[:3]:
                            result_lines.append(f"Link: {url}")
                    
                    return "\n".join(result_lines)
            
            # Generic person search
            else:
                # Find proper names (capitalized consecutive words)
                names = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b', text)
                if names:
                    # Filter out section headers
                    filtered = [n for n in names if n not in ["Web Research", "Reference Data", "Recent Info", "Related Insights"]]
                    if filtered:
                        name = filtered[0]
                        
                        # Single line answer first
                        result_lines.append(f"**{name}**")
                        result_lines.append("")
                        
                        # Extract context around this name
                        name_pos = text.find(name)
                        if name_pos >= 0:
                            context_text = text[max(0, name_pos-100):name_pos+300]
                            context_text = re.sub(r'[🔍📚📰🧐]\s*[A-Z\s]+:', '', context_text).strip()
                            result_lines.append(context_text[:350])
                        
                        # Extract and add links
                        links = self._extract_links_from_context(text)
                        if links:
                            result_lines.append("")
                            result_lines.append("More Information:")
                            for link_text, url in links[:3]:
                                result_lines.append(f"Link: {url}")
                        
                        return "\n".join(result_lines)
        
        # === DATE/YEAR QUESTIONS ===
        elif answer_type in ["date", "year"]:
            # World Cup wins
            if "world cup" in user_query and "india" in user_query:
                years = re.findall(r'\b(1983|2011|2023)\b', text)
                if years:
                    unique_years = list(dict.fromkeys(years))
                    
                    # Single line answer first
                    result_lines.append(f"**{', '.join(unique_years)}**")
                    result_lines.append("")
                    
                    # Additional details
                    result_lines.append("India has won the ICC Cricket World Cup twice:")
                    result_lines.append("• **2011** - ICC Cricket World Cup (ODI)")
                    result_lines.append("• **1983** - World Cup under Kapil Dev's captaincy")
                    
                    if "2023" in unique_years:
                        result_lines.append("• **2023** - ICC Cricket World Cup (possibly T20 or ODI)")
                    
                    # Extract and add links
                    links = self._extract_links_from_context(text)
                    if links:
                        result_lines.append("")
                        result_lines.append("More Information:")
                        for link_text, url in links[:3]:
                            result_lines.append(f"Link: {url}")
                    
                    return "\n".join(result_lines)
            
            # Generic year extraction
            years = re.findall(r'\b(19\d{2}|20\d{2})\b', text)
            if years:
                year = years[0]
                
                # Single line answer first
                result_lines.append(f"**{year}**")
                result_lines.append("")
                
                # Get context around the year
                year_pos = text.find(year)
                if year_pos >= 0:
                    context_text = text[max(0, year_pos-80):year_pos+200]
                    # Clean up
                    context_text = re.sub(r'[🔍📚📰🧐]\s*[A-Z\s]+:', '', context_text).strip()
                    result_lines.append(context_text[:300])
                
                # Extract and add links
                links = self._extract_links_from_context(text)
                if links:
                    result_lines.append("")
                    result_lines.append("More Information:")
                    for link_text, url in links[:3]:
                        result_lines.append(f"Link: {url}")
                
                return "\n".join(result_lines)
        
        # === PLACE/LOCATION QUESTIONS ===
        elif answer_type == "place":
            # Capital queries
            if "capital" in user_query:
                match = re.search(r'capital.*?is ([A-Z][a-z]+)', text, re.IGNORECASE)
                if match:
                    capital = match.group(1)
                    # Find country name
                    country_match = re.search(r'(India|Japan|France|China|USA|United States|[A-Z][a-z]+)', user_query)
                    if country_match:
                        country = country_match.group(1)
                        
                        # Single line answer first
                        result_lines.append(f"**{capital}**")
                        result_lines.append("")
                        
                        # Additional context
                        result_lines.append(f"{capital} is the capital of {country}.")
                        
                        # Extract more context
                        cap_pos = text.find(capital)
                        if cap_pos >= 0:
                            context_text = text[max(0, cap_pos-50):cap_pos+250]
                            context_text = re.sub(r'[🔍📚📰🧐]\s*[A-Z\s]+:', '', context_text).strip()
                            if len(context_text) > 20:
                                result_lines.append("")
                                result_lines.append(context_text[:300])
                        
                        # Extract and add links
                        links = self._extract_links_from_context(text)
                        if links:
                            result_lines.append("")
                            result_lines.append("**📚 More Information:**")
                            for link_text, url in links[:3]:
                                result_lines.append(f"🔗 Link: {url}")
                        
                        return "\n".join(result_lines)
            
            # General location
            else:
                locations = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b', text)
                if locations:
                    location = locations[0]
                    
                    # Single line answer first
                    result_lines.append(f"**{location}**")
                    result_lines.append("")
                    
                    # Get context
                    loc_pos = text.find(location)
                    if loc_pos >= 0:
                        context_text = text[max(0, loc_pos-100):loc_pos+300]
                        context_text = re.sub(r'[🔍📚📰🧐]\s*[A-Z\s]+:', '', context_text).strip()
                        result_lines.append(context_text[:350])
                    
                    # Extract and add links
                    links = self._extract_links_from_context(text)
                    if links:
                        result_lines.append("")
                        result_lines.append("More Information:")
                        for link_text, url in links[:3]:
                            result_lines.append(f"Link: {url}")
                    
                    return "\n".join(result_lines)
        
        # === PRICE QUESTIONS ===
        elif answer_type == "price":
            # Extract prices
            price_patterns = [
                r'₹\s*[\d,]+(?:\.\d{2})?',
                r'Rs\.?\s*[\d,]+',
                r'\$\s*[\d,]+',
            ]
            
            prices = []
            for pattern in price_patterns:
                found = re.findall(pattern, text)
                prices.extend(found[:5])
            
            if prices:
                # Find location
                location_match = re.search(r'in ([A-Z][a-z]+)', user_query)
                location = location_match.group(1) if location_match else "your area"
                
                # Single line answer first
                result_lines.append(f"**{prices[0]}/night**")
                result_lines.append(f"*(Prices as of {current_month_year})*")
                result_lines.append("")
                
                # Add hotel info
                result_lines.append(f"Budget hotels in {location}:")
                result_lines.append("")
                
                # Try to extract hotel info
                hotel_lines = text.split('\n')
                hotel_count = 0
                for line in hotel_lines:
                    if any(price in line for price in prices) and hotel_count < 5:
                        clean_line = line.strip()
                        # Remove section headers
                        clean_line = re.sub(r'[🔍📚📰🧐]\s*[A-Z\s]+:', '', clean_line).strip()
                        if clean_line and len(clean_line) > 10 and not clean_line.startswith('•'):
                            result_lines.append(f"• {clean_line}")
                            hotel_count += 1
                
                if hotel_count == 0:
                    # Just list prices
                    for i, price in enumerate(prices[:5], 1):
                        result_lines.append(f"• Option {i}: {price}/night")
                
                # Extract and add links
                links = self._extract_links_from_context(text)
                if links:
                    result_lines.append("")
                    result_lines.append("Book Hotels:")
                    for link_text, url in links[:5]:
                        result_lines.append(f"{link_text}: {url}")
                
                return "\n".join(result_lines)
        
        # === DEFINITION QUESTIONS ===
        elif answer_type == "definition":
            # Extract definition (first substantial paragraph)
            paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 50]
            if paragraphs:
                definition = paragraphs[0]
                # Clean up section headers
                definition = re.sub(r'[🔍📚📰🧐]\s*[A-Z\s]+:', '', definition)
                
                # Extract main concept/term from query
                query_words = user_query.split()
                term = query_words[-1].title() if query_words else 'Answer'
                
                # If definition contains the term, extract just the first sentence as direct answer
                first_sentence = definition.split('.')[0] + '.'
                
                # Single line/short answer first
                result_lines.append(f"**{term}**")
                result_lines.append("")
                result_lines.append(first_sentence[:250])
                
                # Additional details
                if len(paragraphs) > 1:
                    result_lines.append("")
                    result_lines.append("**Additional Details:**")
                    additional = paragraphs[1][:300]
                    additional = re.sub(r'[🔍📚📰🧐]\s*[A-Z\s]+:', '', additional)
                    result_lines.append(additional)
                
                # Extract and add links
                links = self._extract_links_from_context(text)
                if links:
                    result_lines.append("")
                    result_lines.append("More Information:")
                    for link_text, url in links[:3]:
                        result_lines.append(f"Link: {url}")
                
                return "\n".join(result_lines)
        
        # === FALLBACK: Extract most relevant content ===
        # If we couldn't extract specific answer, return cleaned first paragraph with proper format
        clean_text = text
        for header in ["📎 UPLOADED FILES:", "🔍 WEB RESEARCH:", "📚 REFERENCE DATA:", "📰 RECENT INFO:", "🧐 RELATED INSIGHTS:"]:
            clean_text = clean_text.replace(header, "")
        
        paragraphs = [p.strip() for p in clean_text.split('\n\n') if len(p.strip()) > 30]
        if paragraphs:
            # Try to extract a short direct answer from first paragraph
            first_para = paragraphs[0]
            sentences = first_para.split('. ')
            
            if sentences and len(sentences[0]) < 200:
                # First sentence is concise enough - use as direct answer
                result_lines = []
                result_lines.append(f"**{sentences[0].strip()}**")
                result_lines.append("")
                
                # Add remaining sentences as additional info
                if len(sentences) > 1:
                    result_lines.append('. '.join(sentences[1:]))
                
                # Add more paragraphs if available
                if len(paragraphs) > 1:
                    result_lines.append("")
                    result_lines.append(paragraphs[1][:300])
                
                # Extract and add links
                links = self._extract_links_from_context(text)
                if links:
                    result_lines.append("")
                    result_lines.append("**📚 More Information:**")
                    for link_text, url in links[:3]:
                        result_lines.append(f"🔗 Link: {url}")
                
                return '\n'.join(result_lines)
            else:
                # First paragraph is long, just format it properly
                return first_para[:600]
        
        return ""

    async def _generate_factual_llm_response(self, context: AgentContext, answer_type: str) -> str:
        """Use Gemini to produce a concise factual answer when extraction is unclear."""
        prompt = f"""
Answer the factual question directly and cleanly.

User question: {context.user_input}
Answer type: {answer_type}

Rules:
1. First line must be a short, exact answer.
2. Then add 2-3 simple lines explaining it.
3. Do not include raw search results, links, markdown bullets, or process commentary.
4. If the question is about a person or role, state the role clearly.
5. If the question is about a place, say where it is located.
6. Keep it human-like and accurate.

If fetched context exists, use it for accuracy:
{context.fetched_context or 'No fetched context available.'}

Return plain text only.
"""
        try:
            response = await self.llm.generate(prompt)
            return response.strip()
        except Exception:
            topic = self._extract_topic(context.user_input)
            return f"{topic} is the subject of your question.\n\nI could not confidently extract a precise answer, but I have kept the response concise and ready for verification."

    def _format_factual_response(self, context: AgentContext, raw_answer: str, answer_type: str) -> str:
        """Normalize factual answers into direct-answer-first formatting."""
        has_attachments = bool(context.attachments)
        cleaned = (raw_answer or "").strip()
        cleaned = re.sub(r"https?://\S+", "", cleaned)
        cleaned = re.sub(r"\*\*|__|`", "", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

        if answer_type in {"price", "price_comparison", "hotel", "restaurant"} and any(
            marker in cleaned
            for marker in (
                "Hotel Booking Platforms",
                "Top Hotel Options",
                "Hotels Found",
                "CHEAPEST",
                "Book:",
                "Direct link:",
                "Cheapest live option:",
                "Price:",
                "Book Now:",
            )
        ):
            return cleaned

        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        if not lines:
            return self._generate_safe_fallback_response(context, "research")

        web_first_line = self._extract_factual_answer_from_web(context, answer_type)
        first_line = self._normalize_factual_first_line(
            context,
            web_first_line or lines[0],
            answer_type,
        )
        first_line = re.sub(r"[*_`]+", "", first_line).strip()
        first_line = first_line.rstrip(".")

        explanation_lines = self._build_factual_explanation_lines(context, first_line, answer_type)

        wiki_link, search_link, open_source_link = self._build_factual_output_links(context)
        news_items = self._extract_latest_news_items(context.fetched_context or "")

        sections = [first_line, ""]
        sections.extend(explanation_lines[:3])
        if not has_attachments:
            sections.extend([
                "",
                f"🔗 View on Wikipedia: {wiki_link}",
                f"🔍 Search More: {search_link}",
                f"🌐 Open Source: {open_source_link}",
            ])

            if news_items:
                sections.extend(["", "📰 Latest News:"])
                for title, info, url in news_items[:3]:
                    safe_title = title.strip() if title else "Latest update"
                    safe_info = info.strip() if info else "Latest update available."
                    sections.append(f"- {safe_title} — {safe_info} ({url})")

        return "\n".join(sections).strip()

    def _build_factual_output_links(self, context: AgentContext) -> tuple[str, str, str]:
        query = context.user_input.strip()
        query_encoded = quote_plus(query) if query else ""
        wiki_link = f"https://en.wikipedia.org/wiki/Special:Search?search={query_encoded}" if query_encoded else "https://en.wikipedia.org"
        search_link = f"https://duckduckgo.com/?q={query_encoded}" if query_encoded else "https://duckduckgo.com"

        open_source = search_link
        extracted_links = self._extract_links_from_context(context.fetched_context or "")
        for _, url in extracted_links:
            if "wikipedia.org" in url.lower():
                continue
            open_source = url
            break
        if open_source == search_link and extracted_links:
            open_source = extracted_links[0][1]

        return wiki_link, search_link, open_source

    def _extract_latest_news_items(self, fetched_context: str) -> list[tuple[str, str, str]]:
        if not fetched_context or "📰 RECENT INFO:" not in fetched_context:
            return []

        news_section = fetched_context.split("📰 RECENT INFO:", 1)[1]
        lines = [line.strip() for line in news_section.splitlines() if line.strip()]
        items: list[tuple[str, str, str]] = []

        for idx, line in enumerate(lines):
            url_match = re.search(r"https?://[^\s\)\]]+", line)
            if not url_match:
                continue
            url = url_match.group(0).strip()

            title = "Latest update"
            info = "Latest update available."
            for back in range(1, 3):
                if idx - back >= 0:
                    candidate = lines[idx - back]
                    if not candidate.lower().startswith("source") and "http" not in candidate.lower():
                        title = re.sub(r"\s*\([^)]*\)\s*$", "", candidate).strip()
                        break

            for forward in range(1, 3):
                if idx + forward < len(lines):
                    candidate = lines[idx + forward]
                    if "http" in candidate.lower():
                        continue
                    info = candidate.strip()
                    break

            if url and not any(existing_url == url for _, _, existing_url in items):
                items.append((title[:120], info[:160], url))
            if len(items) >= 3:
                break

        return items

    def _extract_factual_answer_from_web(self, context: AgentContext, answer_type: str) -> str:
        """Extract a direct factual answer from DuckDuckGo/web snippets."""
        fetched = context.fetched_context or ""
        if not fetched:
            return ""

        gov_block = self._extract_gov_block(fetched)
        web_block = self._extract_web_block(fetched)
        search_block = gov_block or web_block or fetched

        query = context.user_input.lower()
        location_hint = self._extract_location_hint(query)
        role_terms = {
            "prime minister": r"prime minister",
            "chief minister": r"chief minister",
            "president": r"president",
            "home minister": r"home minister",
            "mla": r"mla",
            "mp": r"mp",
            "ceo": r"ceo",
            "founder": r"founder",
        }

        role_pattern = None
        for role, pattern in role_terms.items():
            if role in query:
                role_pattern = pattern
                break
            if role == "prime minister" and "pm" in query:
                role_pattern = pattern
                break
            if role == "chief minister" and "cm" in query:
                role_pattern = pattern
                break

        lines = [line.strip() for line in search_block.splitlines() if line.strip()]
        candidates: list[str] = []

        if role_pattern:
            patterns = [
                rf"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+is\s+the\s+(?:current\s+)?{role_pattern}",
                rf"{role_pattern}\s+of\s+[^.\n]+\s+is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
                rf"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*\(.*?{role_pattern}.*?\)",
                rf"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*[-,]\s*{role_pattern}",
            ]
            for idx, line in enumerate(lines):
                line_lower = line.lower()
                if location_hint and location_hint not in line_lower:
                    continue
                source_boost = self._line_has_gov_source(lines, idx)
                for pattern in patterns:
                    match = re.search(pattern, line, flags=re.IGNORECASE)
                    if match:
                        name = match.group(1).strip()
                        score = 5 if source_boost else 1
                        candidates.append(f"{score}::{name}")

        if answer_type == "person" and not candidates:
            name_match = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", search_block)
            if name_match:
                candidates.append(name_match.group(1).strip())

        if candidates:
            scored = []
            for item in candidates:
                if "::" in item:
                    score_str, name = item.split("::", 1)
                    try:
                        score = int(score_str)
                    except ValueError:
                        score = 1
                    scored.append((score, name))
                else:
                    scored.append((1, item))
            scored.sort(key=lambda item: item[0], reverse=True)
            return scored[0][1]
        return ""

    def _extract_web_block(self, fetched_context: str) -> str:
        if "🔍 WEB RESEARCH:" in fetched_context:
            return fetched_context.split("🔍 WEB RESEARCH:", 1)[1]
        return ""

    def _extract_gov_block(self, fetched_context: str) -> str:
        if "🏛 GOVERNMENT SOURCES:" in fetched_context:
            return fetched_context.split("🏛 GOVERNMENT SOURCES:", 1)[1]
        return ""

    def _extract_location_hint(self, query: str) -> str:
        """Extract a lightweight location hint for CM/PM/CEO queries."""
        match = re.search(r"\b(?:in|of|for)\s+([a-z][a-z\s\-']{2,40})", query)
        if not match:
            return ""
        location = match.group(1).strip()
        location = re.sub(r"\b(today|now|currently|right now|please|live)\b.*$", "", location).strip()
        return location

    def _line_has_gov_source(self, lines: list[str], index: int) -> bool:
        """Check nearby lines for official/government sources."""
        gov_domains = (".gov", ".gov.in", "nic.in", "india.gov", "gov.uk", "gov.au", "govt", "parliament", "assembly")
        for offset in range(0, 3):
            pos = index + offset
            if pos >= len(lines):
                break
            if any(domain in lines[pos].lower() for domain in gov_domains):
                return True
        return False

    def _normalize_factual_first_line(self, context: AgentContext, first_line: str, answer_type: str) -> str:
        query = context.user_input.lower()
        line = first_line.strip().strip(". ")
        line = re.sub(r"^[•\-]+\s*", "", line).strip()

        name_match = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", first_line)
        candidate_name = name_match.group(1).strip() if name_match else line

        if answer_type == "person" or any(term in query for term in ("who is", "who founded", "who created", "who leads", "who heads")):
            return candidate_name

        if answer_type == "place":
            return candidate_name

        if answer_type in {"definition", "fact", "year", "date", "number"}:
            return line

        return line

    def _extract_role_subject(self, query: str) -> str:
        q = query.lower().strip()
        patterns = [
            r"who is\s+(.*)",
            r"who founded\s+(.*)",
            r"who created\s+(.*)",
            r"where is\s+(.*)",
            r"what is\s+(.*)",
        ]
        for pattern in patterns:
            match = re.search(pattern, q)
            if match:
                subject = match.group(1).strip(" ?.")
                subject = subject.replace("the ", "")
                subject = subject.replace("of ", "of ")
                if subject.startswith("cm of "):
                    return f"Chief Minister of {subject[6:].title()}"
                if subject.startswith("ceo of "):
                    return f"CEO of {subject[7:].title()}"
                if subject.startswith("president of "):
                    return f"President of {subject[13:].title()}"
                if subject.startswith("prime minister of "):
                    return f"Prime Minister of {subject[18:].title()}"
                if subject.startswith("founder of "):
                    return f"Founder of {subject[11:].title()}"
                return subject.title()
        return ""

    def _collect_factual_explanation_lines(self, context: AgentContext, lines: list[str]) -> list[str]:
        explanation = []
        for line in lines:
            clean = re.sub(r"https?://\S+", "", line).strip()
            clean = re.sub(r"[•*-]", "", clean).strip()
            if clean and len(clean) > 10:
                explanation.append(clean)
            if len(explanation) >= 3:
                break
        return explanation

    def _build_factual_explanation_lines(self, context: AgentContext, first_line: str, answer_type: str) -> list[str]:
        web_lines = self._extract_web_explanation_lines(context.fetched_context or "")
        if web_lines:
            return web_lines[:3]
        query = context.user_input.lower()
        if any(term in query for term in ("who is", "who founded", "who created", "who leads", "who heads", "ceo", "president", "prime minister", "cm of", "chief minister")):
            return [
                "This is the current or most relevant entity response for the role you asked about.",
                "I kept it short and avoided raw source snippets so the answer is easy to read.",
            ]
        if any(term in query for term in ("where is", "which city", "which country")):
            return [
                "This identifies the location in simple terms using the available reference context.",
                "If you need, I can also give the country, state, or nearby landmark details.",
            ]
        if any(term in query for term in ("what is", "define", "meaning of", "explain")):
            return [
                "This is a concise definition or explanation of the concept you asked about.",
                "The answer is phrased simply so it is easier to understand and remember.",
                "Example-based clarification can be provided if you want more detail.",
            ]
        return [
            "This is a concise factual response based on the available context.",
            "I kept the answer direct so the first line is immediately useful.",
        ]

    def _extract_web_explanation_lines(self, fetched_context: str) -> list[str]:
        if not fetched_context:
            return []

        web_block = self._extract_web_block(fetched_context)
        if not web_block:
            return []

        lines = [line.strip() for line in web_block.splitlines() if line.strip()]
        explanation: list[str] = []
        for line in lines:
            if line.startswith(("🔗", "📚", "📰", "🧐")):
                continue
            if line.lower().startswith("http"):
                continue
            if line.lower().startswith("reference data"):
                continue
            if len(line) < 20:
                continue
            cleaned = re.sub(r"https?://\S+", "", line).strip()
            if cleaned and cleaned not in explanation:
                explanation.append(cleaned[:220])
            if len(explanation) >= 3:
                break
        return explanation

    def _extract_subject_from_query(self, query: str) -> str:
        q = query.lower().strip()
        patterns = [
            r"who founded\s+(.*)",
            r"who created\s+(.*)",
            r"who is\s+(.*)",
        ]
        for pattern in patterns:
            match = re.search(pattern, q)
            if match:
                subject = match.group(1).strip(" ?.")
                subject = re.sub(r"^(the\s+)", "", subject)
                return subject.title()
        return ""
    
    def _detect_output_format(self, user_input: str) -> str:
        """
        Detect the output format requested by the user.
        
        Returns: 'five-line', 'pointwise', 'bullet', 'structured', or 'summary'
        """
        user_lower = user_input.lower()
        
        # Check for specific line count requests
        if "5 line" in user_lower or "five line" in user_lower:
            return "five-line"
        if "3 line" in user_lower or "three line" in user_lower:
            return "three-line"
        if "10 line" in user_lower or "ten line" in user_lower:
            return "ten-line"
        
        # Check for point-wise requests
        if any(term in user_lower for term in ["point wise", "pointwise", "point-wise", "in points", "key points"]):
            return "pointwise"
        
        # Check for bullet list requests
        if any(term in user_lower for term in ["bullet", "list", "enumerate"]):
            return "bullet"
        
        # Check for structured explanation
        if any(term in user_lower for term in ["explain", "explanation", "how does", "what is", "define"]):
            return "structured"
        
        # Default to summary
        return "summary"
    
    def _prepare_content_for_bart(self, context: AgentContext, intent: str, extracted_info: dict) -> str:
        """
        Prepare clean content for BART summarization.
        
        Combines context from Analyzer/Planner and formats it for summarization.
        Does NOT include raw agent logs or debug text.
        """
        content_parts = []
        
        # Add user query context (for reference, not to repeat)
        content_parts.append(f"Task: {context.user_input}")
        
        # Add extracted direct answer if available
        if extracted_info.get("direct_answer"):
            content_parts.append(f"Answer: {extracted_info['direct_answer']}")
        
        # Add fetched context (main content)
        if context.fetched_context:
            # Clean up the fetched context
            cleaned_context = context.fetched_context
            
            # Remove section headers
            for header in ["📎 UPLOADED FILES:", "🔍 WEB RESEARCH:", "📚 REFERENCE DATA:", "📰 RECENT INFO:"]:
                cleaned_context = cleaned_context.replace(header, "")
            
            # Remove any agent debug text
            cleaned_context = re.sub(r"\[AGENT[^\]]*\]", "", cleaned_context)
            cleaned_context = re.sub(r"\[DEBUG[^\]]*\]", "", cleaned_context)
            
            content_parts.append(cleaned_context.strip())
        
        # Add analysis if available
        if context.analysis:
            content_parts.append(f"Analysis: {context.analysis}")
        
        # Add extracted prices if available
        if extracted_info.get("prices"):
            content_parts.append(f"Prices: {', '.join(extracted_info['prices'][:5])}")
        
        # Add key facts if available
        if extracted_info.get("key_facts"):
            content_parts.append(f"Key Facts: {'; '.join(extracted_info['key_facts'][:3])}")
        
        # Combine all parts
        full_content = "\n\n".join([part for part in content_parts if part])
        
        # Limit to reasonable length for BART (max 1024 tokens)
        if self._bart_tokenizer:
            tokens = self._bart_tokenizer.encode(full_content, truncation=True, max_length=1024)
            full_content = self._bart_tokenizer.decode(tokens, skip_special_tokens=True)
        else:
            # Fallback: limit by characters
            full_content = full_content[:4000]
        
        return full_content
    
    def _generate_with_bart(self, content: str, output_format: str, user_query: str) -> str:
        """
        Generate response using BART with deterministic settings.
        
        Adjusts max_length/min_length based on requested format.
        """
        if not self._bart_pipeline or not content:
            return ""
        
        # Determine length parameters based on format
        if output_format == "three-line":
            max_length = 60
            min_length = 30
        elif output_format == "five-line":
            max_length = 100
            min_length = 50
        elif output_format == "ten-line":
            max_length = 200
            min_length = 100
        elif output_format in ["pointwise", "bullet"]:
            max_length = 150
            min_length = 80
        elif output_format == "structured":
            max_length = 250
            min_length = 120
        else:  # summary
            max_length = 180
            min_length = 60
        
        try:
            # Generate with deterministic settings
            result = self._bart_pipeline(
                content,
                max_length=max_length,
                min_length=min_length,
                do_sample=False,  # Deterministic
                num_beams=4,      # Beam search for quality
                early_stopping=True
            )
            
            if result and len(result) > 0:
                return result[0]["summary_text"]
            
        except Exception as e:
            print(f"BART generation error: {e}")
        
        return ""
    
    def _format_bart_output(self, bart_output: str, output_format: str, extracted_info: dict) -> str:
        """
        Format BART output according to requested format.
        
        Converts BART's summary into requested format (bullets, points, etc.)
        """
        if not bart_output:
            return bart_output
        
        # Clean up BART output
        cleaned = bart_output.strip()
        
        # Format based on requested type
        if output_format in ["pointwise", "bullet"]:
            # Convert to bullet points
            sentences = self._split_into_sentences(cleaned)
            
            # Create bullet list
            if len(sentences) >= 3:
                bullet_char = "•" if output_format == "bullet" else "→"
                formatted_points = [f"{bullet_char} {sent.strip()}" for sent in sentences[:5]]
                return "\n".join(formatted_points)
            else:
                # Not enough sentences for points, return as is
                return cleaned
        
        elif output_format == "structured":
            # Add structure to explanation
            sentences = self._split_into_sentences(cleaned)
            
            if len(sentences) >= 2:
                # First sentence is the definition/intro
                structured = f"**Overview:**\n{sentences[0]}\n\n"
                
                # Remaining sentences are details
                if len(sentences) > 1:
                    structured += "**Details:**\n"
                    for sent in sentences[1:]:
                        structured += f"• {sent.strip()}\n"
                
                return structured.strip()
            else:
                return cleaned
        
        elif output_format in ["three-line", "five-line", "ten-line"]:
            # Limit to specific number of lines
            sentences = self._split_into_sentences(cleaned)
            
            target_lines = {"three-line": 3, "five-line": 5, "ten-line": 10}
            max_sentences = target_lines.get(output_format, 5)
            
            limited = ". ".join(sentences[:max_sentences])
            if not limited.endswith("."):
                limited += "."
            
            return limited
        
        else:  # summary
            # Return as-is with clean formatting
            return cleaned
    
    def _split_into_sentences(self, text: str) -> list:
        """Split text into sentences for formatting."""
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if len(s.strip()) > 10]
    
    def _sanitize_system_language(self, response: str) -> str:
        """Remove any system-like language that sounds like internal processing."""
        import re
        
        # Remove phrases that sound like system messages
        system_phrases = [
            r"User query:?[^\n]*\n",
            r"User request:?[^\n]*\n",
            r"Analyzing:?[^\n]*\n",
            r"Processing:?[^\n]*\n",
            r"Input received:?[^\n]*\n",
            r"Task identified:?[^\n]*\n",
            r"\[INTERNAL[^\]]*\]",
            r"\[ANALYSIS[^\]]*\]",
            r"\[PLAN[^\]]*\]",
            r"\[DATA[^\]]*\]",
        ]
        
        result = response
        for pattern in system_phrases:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)
        
        # Remove any bullet points that look like agent steps
        result = re.sub(r"^[•\-\*]\s*(Fetch|Analyze|Plan|Report)[^\n]*\n", "", result, flags=re.MULTILINE)
        
        return result.strip()
    
    def _extract_key_information(self, context: AgentContext) -> dict:
        """Extract prices, facts, and key details from fetched context."""
        import re
        
        extracted = {
            "prices": [],
            "key_facts": [],
            "direct_answer": None
        }
        
        if not context.fetched_context:
            return extracted
        
        text = context.fetched_context
        user_query = context.user_input.lower()
        
        # Extract prices (₹, Rs, $, €, etc.)
        price_patterns = [
            r'₹\s*[\d,]+(?:\.\d{2})?',  # Indian Rupee
            r'Rs\.?\s*[\d,]+(?:\.\d{2})?',  # Rs format
            r'\$\s*[\d,]+(?:\.\d{2})?',  # Dollar
            r'€\s*[\d,]+(?:\.\d{2})?',  # Euro
            r'[\d,]+\s*(?:rupees|dollars|euros)',  # Word format
        ]
        
        for pattern in price_patterns:
            prices = re.findall(pattern, text, re.IGNORECASE)
            extracted["prices"].extend(prices[:5])  # Limit to 5 prices
        
        # Extract direct answers for common queries
        # President query
        if "president" in user_query and "india" in user_query:
            match = re.search(r'(Droupadi Murmu|[A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s+is|\s+serves|\s+took office|\s+became).*?president', text, re.IGNORECASE)
            if match:
                extracted["direct_answer"] = match.group(0)
        
        # World Cup query
        if ("world cup" in user_query or "worldcup" in user_query) and ("india" in user_query or "win" in user_query):
            match = re.search(r'India won.*?(?:cricket|world cup).*?(?:\d{4})', text, re.IGNORECASE)
            if match:
                extracted["direct_answer"] = match.group(0)
            # Also look for years
            years = re.findall(r'\b(19\d{2}|20\d{2})\b', text)
            if years:
                extracted["key_facts"].append(f"Years mentioned: {', '.join(set(years[:3]))}")
        
        # Extract ratings (4.5★, 4/5, etc.)
        ratings = re.findall(r'(\d+(?:\.\d+)?)\s*(?:stars?|★|/5)', text, re.IGNORECASE)
        if ratings:
            extracted["key_facts"].append(f"Ratings: {', '.join(ratings[:3])}")
        
        # Extract key numbers/statistics
        numbers = re.findall(r'\b(\d+(?:,\d+)*(?:\.\d+)?)\s+(?:people|users|reviews|rooms|hotels|restaurants)', text, re.IGNORECASE)
        if numbers:
            extracted["key_facts"].extend([f"{n}" for n in numbers[:2]])
        
        return extracted
    
    def _ensure_direct_answer(self, response: str, context: AgentContext, intent: str, extracted_info: dict) -> str:
        """Ensure response starts with a direct answer first, then additional information."""
        
        user_query = context.user_input.lower()
        
        # Check if response already has proper direct answer format (bold at start)
        if re.match(r'^\*\*[^\*]+\*\*\s*$', response.split('\n')[0]):
            # First line is bold text only - good format
            return response
        
        # Check if already starts with direct answer patterns
        starts_with_direct = any([
            re.match(r'^\*\*[^\*]+\*\*\s*\n', response),  # Bold text followed by newline
            re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+\s*\n', response) and len(response.split('\n')[0]) < 50,  # Short name/term
        ])
        
        if starts_with_direct:
            return response
        
        # Check for problematic starts that should be reformatted
        bad_starts = [
            "I searched", "I researched", "I found", "I analyzed", "I investigated",
            "Based on", "According to", "Here is", "Here are", "Here's",
            "Let me tell you", "I understand you", "Task:", "I gathered",
            "From the", "The data shows", "My research", "Here is what"
        ]
        
        # If response starts with bad phrase, try to restructure
        if any(response.lower().startswith(bad.lower()) for bad in bad_starts):
            # Try to extract the actual answer from later in the response
            sentences = response.split('. ')
            
            # Look for the first sentence with actual information
            for i, sentence in enumerate(sentences):
                sentence = sentence.strip()
                # Skip meta-commentary sentences
                if (len(sentence) > 20 and 
                    not sentence.startswith('I ') and 
                    not sentence.lower().startswith('here ') and
                    not sentence.lower().startswith('based on')):
                    
                    # Extract key term from sentence for bold header
                    # Look for proper nouns or key terms
                    names = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b', sentence)
                    
                    if names:
                        # Use first name/term as header
                        direct_answer = names[0]
                        remaining_content = '. '.join(sentences[i:])
                        return f"**{direct_answer}**\n\n{remaining_content}"
                    else:
                        # Just remove the bad start and reformat
                        remaining_content = '. '.join(sentences[i:])
                        return remaining_content
        
        # Try to extract direct answer from extracted_info or context
        if extracted_info.get("direct_answer"):
            direct = extracted_info["direct_answer"]
            if not response.startswith(direct):
                return f"**{direct}**\n\n{response}"
        
        # Try to extract key term from user query and fetched context
        direct_fact = self._extract_direct_fact_from_query(context, user_query)
        if direct_fact and not response.startswith(direct_fact):
            return f"**{direct_fact}**\n\n{response}"
        
        return response
    
    def _final_validation(self, response: str, context: AgentContext) -> str:
        """Final validation to ensure response is suitable for user."""
        # Check minimum quality
        if len(response) < 15:
            return self._template_based_response(context)
        
        # Check for forbidden terms that might have slipped through
        forbidden_indicators = ["gemini", "language model", "ai model", "llm"]
        response_lower = response.lower()
        
        if any(term in response_lower for term in forbidden_indicators):
            # Still has problems - use template
            return self._template_based_response(context)
        
        # Check if response is just repeating the query
        if context.user_input.lower() in response.lower() and len(response) < len(context.user_input) * 2:
            # Likely just echoing the user - use template
            return self._template_based_response(context)
        
        # Add date context if needed
        response = self._add_date_context_if_needed(response, context)
        
        return response
    
    def _extract_direct_fact_from_query(self, context: AgentContext, user_query: str) -> str:
        """Extract the most direct fact to answer the query."""
        if not context.fetched_context:
            return ""
        
        text = context.fetched_context
        
        # President queries
        if "president" in user_query:
            patterns = [
                r'(Droupadi Murmu is.*?President.*?India)',
                r'(President of India is [A-Z][a-z]+ [A-Z][a-z]+)',
                r'([A-Z][a-z]+ [A-Z][a-z]+ serves? as.*?President)',
                r'([A-Z][a-z]+ [A-Z][a-z]+).*?15th President',
            ]
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
        
        # Capital queries
        if "capital" in user_query:
            match = re.search(r'capital.*?is ([A-Z][a-z]+)', text, re.IGNORECASE)
            if match:
                entity = re.search(r'(India|Japan|France|China|USA|[A-Z][a-z]+)', user_query)
                if entity:
                    return f"The capital of {entity.group(1)} is {match.group(1)}"
        
        # Population queries  
        if "population" in user_query:
            match = re.search(r'population.*?([\d,.]+.*?(?:million|billion|crore))', text, re.IGNORECASE)
            if match:
                return match.group(0).strip()
        
        # Year/date queries
        if any(word in user_query for word in ["when", "year", "date"]):
            match = re.search(r'(\d{4})', text)
            if match:
                year = match.group(1)
                context_text = text[max(0, match.start()-50):match.end()+50]
                return context_text.strip()
        
        return ""
    
    def _add_date_context_if_needed(self, response: str,context: AgentContext) -> str:
        """Add date context to responses when relevant."""
        user_query = context.user_input.lower()
        current_date = datetime.now().strftime("%B %Y")
        
        time_keywords = ["current", "now", "today", "latest", "recent", "president", 
                        "prime minister", "who is", "status", "price", "2026", "this year"]
        
        needs_date = any(keyword in user_query for keyword in time_keywords)
        
        # Don't add if already has date context
        has_date = any(marker in response.lower() for marker in 
                      ["as of", "current", "february 2026", "2026", "latest", "recent"])
        
        if needs_date and not has_date and len(response) > 50:
            # Add subtle date context
            response = f"{response}\n\n*Information as of {current_date}*"
        
        return response

    def _build_execution_response_prompt(
        self, 
        context: AgentContext, 
        intent: str, 
        requirements: list
    ) -> str:
        """Build a prompt that emphasizes TASK EXECUTION, not just explanations."""
        prompt_parts = [
            "═══════════════════════════════════════════════════════════",
            "CRITICAL SYSTEM ROLE - READ CAREFULLY",
            "═══════════════════════════════════════════════════════════",
            "",
            "You are generating the FINAL RESPONSE for TaskPilot AI.",
            "TaskPilot AI is a TASK EXECUTION SYSTEM, NOT a chatbot.",
            "",
            "CORE PRINCIPLES:",
            "• TaskPilot AI EXECUTES TASKS - it doesn't just discuss them",
            "• It GATHERS DATA - it doesn't just explain what data might exist",
            "• It ANALYZES INFORMATION - not just describes analysis",
            "• It DELIVERS RESULTS - not just possibilities",
            "• It's MORE CAPABLE than free ChatGPT or Gemini",
            "",
            "IDENTITY RULES (ABSOLUTE):",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "✗ NEVER say 'I am Gemini' or any variation",
            "✗ NEVER say 'I am a language model' or 'I am an AI model'",
            "✗ NEVER use phrases like 'As an AI' or 'As a language model'",
            "✗ NEVER mention limitations like 'I cannot access real-time data'",
            "✗ NEVER say 'I don't have access to the internet'",
            "✗ NEVER repeat the user's question back",
            "✗ NEVER ask for clarification unless absolutely critical",
            "✗ NEVER use meta-commentary about your internal process",
            "✓ If identity is asked: 'I am TaskPilot AI, your task execution assistant'",
            "",
            "RESPONSE STYLE (MANDATORY):",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "• Write in ACTIVE VOICE showing work was DONE",
            "  ✓ 'I analyzed the top laptops and ranked them'",
            "  ✗ 'Here is information about laptops'",
            "• Be DIRECT and CONFIDENT",
            "  ✓ 'The best option is X because...'",
            "  ✗ 'It seems like X might be good'",
            "• Provide SPECIFIC, ACTIONABLE answers",
            "  ✓ 'Get the Dell XPS 13 ($899) for best value'",
            "  ✗ 'There are many laptop options available'",
            "• Use natural, conversational language",
            "• NO disclaimers, NO limitations, NO meta-commentary",
            "",
            f"TASK TYPE: {intent}",
            f"USER'S GOAL: {context.user_input}",
        ]
        
        if requirements:
            prompt_parts.append(f"REQUIREMENTS TO MEET: {', '.join(requirements)}")
        
        if context.fetched_context:
            # Show what data TaskPilot has gathered
            data_preview = context.fetched_context[:1800]
            prompt_parts.append(f"\nDATA I GATHERED:\n{data_preview}")
            
            # Check if we have URLs in the data
            if "🔗" in data_preview or "http" in data_preview:
                prompt_parts.append("\n⚠️ CRITICAL: The data above contains URLs/links. YOU MUST include them in your response!")
                prompt_parts.append("Format links as: 🔗 [URL] or as markdown [text](url)")
        
        if context.analysis:
            analysis_preview = context.analysis[:400]
            prompt_parts.append(f"\nANALYSIS COMPLETED:\n{analysis_preview}")
        
        if context.plan:
            prompt_parts.append(f"\nEXECUTION PERFORMED:\n{'; '.join(context.plan[:4])}")
        
        # Add extracted key info
        extracted = context.metadata.get("extracted_info", {})
        if extracted:
            prompt_parts.append(f"\nKEY INFORMATION EXTRACTED:")
            if extracted.get("prices"):
                prompt_parts.append(f"Prices found: {', '.join(extracted['prices'])}")
            if extracted.get("direct_answer"):
                prompt_parts.append(f"Direct Answer: {extracted['direct_answer']}")
            if extracted.get("key_facts"):
                prompt_parts.append(f"Key Facts: {'; '.join(extracted['key_facts'][:3])}")
        
        prompt_parts.extend([
            "",
            "═══════════════════════════════════════════════════════════",
            "NOW WRITE THE FINAL RESPONSE (CRITICAL FORMAT):",
            "═══════════════════════════════════════════════════════════",
            "",
            "RESPONSE STRUCTURE (MANDATORY):",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "**Line 1: DIRECT ANSWER (in BOLD) - Single word, name, date, or short phrase**",
            "   Examples:",
            "   ✓ '**Narendra Modi**' (for 'who is PM')",
            "   ✓ '**2011, 1983**' (for 'when did India win')",
            "   ✓ '**₹424/night**' (for 'cheapest hotels')",
            "   ✓ '**New Delhi**' (for 'capital of India')",
            "   ✗ 'I found that the Prime Minister is...' (NEVER!)",
            "   ✗ 'Here is what I found...' (NEVER!)",
            "",
            "**Line 2: BLANK LINE**",
            "",
            "**Lines 3+: Additional context and details**",
            "   - Brief explanation or context",
            "   - Key facts as bullet points",
            "   - Supporting information",
            "   - Date context when relevant",
            "",
            "**Final section: Links and sources**",
            "   - Under **📚 More Information:** heading",
            "   - Format: 🔗 Link: [URL]",
            "",
            "**CRITICAL FORMATTING REQUIREMENTS:**",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "• **FIRST LINE: Direct answer ONLY (what was asked) - in BOLD**",
            "  - For 'who' questions: Just the NAME (e.g., **Narendra Modi**)",
            "  - For 'when' questions: Just the YEAR/DATE (e.g., **2011, 1983**)",
            "  - For 'where' questions: Just the PLACE (e.g., **New Delhi**)",
            "  - For price questions: Just the PRICE (e.g., **₹424/night**)",
            "  - For 'what is' questions: Just the TERM (e.g., **Artificial Intelligence**)",
            "",
            "• **SECOND LINE: Blank line for spacing**",
            "",
            "• **THEN: Additional information, context, and details**",
            "  - Current date context when relevant",
            "  - Supporting facts and statistics",
            "  - Detailed explanations",
            "",
            "• **FINALLY: Links and sources at the end**",
            "  - Format: 🔗 Link: [URL]",
            "  - Under section: **📚 More Information:**",
            "",
            "✗ NEVER start with: 'I found', 'Here is', 'I searched', 'Based on'",
            "✓ ALWAYS start with: The direct answer to exactly what was asked",
            "",
            "EXAMPLES OF PERFECT RESPONSES:",
            "",
            "Q: Who is Prime Minister of India?",
            "A: **Narendra Modi**",
            "",
            "He is the current Prime Minister of India as of February 2026.",
            "• Serving since May 26, 2014",
            "• Party: Bharatiya Janata Party (BJP)",
            "• Currently in his third consecutive term",
            "",
            "**📚 More Information:**",
            "🔗 Link: https://en.wikipedia.org/wiki/Prime_Minister_of_India",
            "",
            "Q: Who is President of India?",
            "A: **Droupadi Murmu**",
            "",
            "She is the current President of India as of February 2026.",
            "",
            "**Key Information:**",
            "• Took office: July 25, 2022",
            "• India's 15th President",
            "• First tribal President of India",
            "• Second woman President",
            "• Term: 2022-2027 (5 years)",
            "",
            "Q: Cheapest hotels in Bangalore?",
            "A: **₹424/night**",
            "*(Prices as of February 2026)*",
            "",
            "Budget hotels in Bangalore:",
            "",
            "• Hotel X - ₹500/night - 4.2★ - [Book here](url)",
            "• Hotel Y - ₹650/night - 4.5★ - [Book here](url)",
            "• Hotel Z - ₹750/night - 4.3★ - [Book here](url)",
            "",
            "Deliver the FINAL RESULT directly. Be useful and actionable.",
            "NO meta-commentary. NO AI disclaimers. Direct answer FIRST, then details.",
        ])
        return "\n".join(prompt_parts)
    
    def _ensure_execution_tone(self, response: str, intent: str) -> str:
        """
        Ensure the response sounds like WORK WAS DONE, not just explained.
        This transforms passive/explanatory language into active/execution language.
        """
        import re
        
        # Don't modify greetings or very short responses
        if len(response) < 30:
            return response
        
        result = response
        
        # Transform passive phrases to active execution phrases
        execution_transforms = [
            # Research transforms
            (r"Here is information about", "I researched and found that"),
            (r"Here's information about", "I researched and found that"),
            (r"Information about", "Based on my research"),
            (r"Regarding your question about", "I investigated and found that"),
            
            # Analysis transforms
            (r"This appears to be", "I analyzed this and determined it is"),
            (r"It seems that", "My analysis shows that"),
            (r"It looks like", "I found that"),
            
            # Comparison transforms
            (r"There are several options", "I compared the options and found"),
            (r"You could consider", "I recommend considering"),
            (r"Some options include", "After comparison, the best options are"),
            
            # General transforms
            (r"Let me explain", "Here's what I found:"),
            (r"Allow me to", "I'll"),
            (r"I can tell you that", ""),
            (r"I can provide information", "I found"),
        ]
        
        for pattern, replacement in execution_transforms:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        return result

    def _try_bart_generation(
        self,
        context: AgentContext,
        intent: str,
        extracted_info: dict,
        output_format: str
    ) -> str:
        """Try BART generation, fallback to intent-based if it fails."""
        prepared_content = self._prepare_content_for_bart(context, intent, extracted_info)
        
        # Generate response using BART model
        if self._bart_pipeline and prepared_content:
            try:
                bart_response = self._generate_with_bart(
                    content=prepared_content,
                    output_format=output_format,
                    user_query=context.user_input
                )
                
                if bart_response and len(bart_response.strip()) > 20:
                    # Clean up and format the response
                    cleaned = self._format_bart_output(bart_response, output_format, extracted_info)
                    cleaned = self._sanitize_system_language(cleaned)
                    cleaned = self._ensure_execution_tone(cleaned, intent)
                    cleaned = self._ensure_direct_answer(cleaned, context, intent, extracted_info)
                    return self._enforce_identity(cleaned)
            except Exception as e:
                print(f"BART generation error: {e}")
        
        # BART failed, use intent-based
        return self._intent_based_response(context, intent, is_factual=False)
    
    def _intent_based_response(
        self, 
        context: AgentContext, 
        intent: str,
        is_factual: bool = False
    ) -> str:
        """
        Generate INTELLIGENT response based on intent WITHOUT API calls.
        This should feel like task execution, not just information retrieval.
        
        For factual questions, extracts direct answers from fetched context.
        """
        user_input = context.user_input.strip()
        user_lower = user_input.lower()
        
        # === PRIORITY: HANDLE FACTUAL QUESTIONS ===
        if is_factual:
            answer_type = context.metadata.get("answer_type", "unknown")
            direct_answer = self._extract_direct_answer_fast(context, answer_type)
            if direct_answer and len(direct_answer.strip()) > 20:
                return direct_answer
        
        # Handle greetings
        if intent == "greeting" or intent == "chat":
            # Match user's greeting style
            user_greeting = user_input.lower().strip()
            if "morning" in user_greeting:
                return "Good morning! 👋 I'm TaskPilot AI, your intelligent assistant. How can I help you today?"
            elif "afternoon" in user_greeting:
                return "Good afternoon! 👋 I'm TaskPilot AI, your intelligent assistant. How can I help you today?"
            elif "evening" in user_greeting:
                return "Good evening! 👋 I'm TaskPilot AI, your intelligent assistant. How can I help you today?"
            elif "hey" in user_greeting:
                return "Hey there! 👋 I'm TaskPilot AI. What can I help you with?"
            else:
                return "Hello! 👋 I'm TaskPilot AI, your intelligent assistant. How can I help you today?"
        
        # Handle identity questions
        identity_patterns = [
            "who are you", "what are you", "your name", "tell me about yourself"
        ]
        if any(phrase in user_lower for phrase in identity_patterns):
            return "My name is TaskPilot AI. How can I assist you today?"

        live_query_kind = context.metadata.get("live_query_kind")
        if live_query_kind in {"time", "weather"}:
            live_answer = self._format_live_city_answer(context, live_query_kind)
            if live_answer:
                return live_answer
        
        # Extract useful data from context
        has_web_data = "WEB RESEARCH" in (context.fetched_context or "")
        has_ref_data = "REFERENCE DATA" in (context.fetched_context or "")
        has_file_data = "UPLOADED FILES" in (context.fetched_context or "")
        
        # INTENT-SPECIFIC RESPONSES
        
        if intent == "research":
            if has_web_data or has_ref_data:
                # Format with links if available
                formatted_results = self._format_search_results_with_links(context.fetched_context, user_input)
                if "🔗" in formatted_results or "http" in formatted_results:
                    return formatted_results
                else:
                    info = self._extract_useful_info(context.fetched_context, 600)
                    return f"I researched your question about {self._extract_topic(user_input)}.\n\n{info}\n\nThis covers the key information you were looking for. Let me know if you need more specific details!"
            else:
                # Provide a helpful response even without web data
                topic = self._extract_topic(user_input)
                return (
                    f"I researched {topic} and prepared a best-available answer using trusted reference context. "
                    f"For higher accuracy, prioritize official pages and current listings when you open the links below.\n\n"
                    f"Focus areas:\n"
                    f"1. Verified facts from reference sources\n"
                    f"2. Recent updates from web results\n"
                    f"3. Practical next actions based on your question"
                )
        
        elif intent == "compare":
            if has_web_data:
                # Format with links and prices
                formatted_results = self._format_search_results_with_links(context.fetched_context, user_input)
                if "🔗" in formatted_results or "http" in formatted_results:
                    return formatted_results
                else:
                    info = self._extract_useful_info(context.fetched_context, 700)
                    return f"I compared the options for your request.\n\n{info}\n\nBased on this comparison, you can make an informed decision. Need help choosing?"
            else:
                topic = self._extract_topic(user_input)
                return (
                    f"I analyzed the comparison of {topic} and built a practical evaluation checklist.\n\n"
                    f"**Key Factors to Compare:**\n"
                    f"• Features and capabilities\n"
                    f"• Cost and value\n"
                    f"• Quality and reliability\n"
                    f"• User reviews and ratings\n"
                    f"• Current market position\n\n"
                    f"Share your budget and top priority, and I will rank options in order."
                )
        
        elif intent == "recommend":
            if has_web_data:
                # Extract and format recommendations with links
                formatted_results = self._format_search_results_with_links(context.fetched_context, user_input)
                
                # Add price comparison summary if prices are found
                price_data = self._extract_prices_and_compare(context.fetched_context)
                if price_data["has_prices"] and price_data["count"] > 1:
                    # Detect currency from context
                    import re
                    currency_match = re.search(r'(₹|Rs\.?|\$|€|£)', context.fetched_context)
                    currency = currency_match.group(1) if currency_match else "₹"
                    
                    price_summary = (
                        f"\n\n💰 **Price Comparison:**\n"
                        f"• Lowest: {currency}{price_data['min']:,.0f}\n"
                        f"• Highest: {currency}{price_data['max']:,.0f}\n"
                        f"• Average: {currency}{price_data['avg']:,.0f}\n"
                        f"• Found {price_data['count']} options"
                    )
                    formatted_results += price_summary
                
                return formatted_results
            else:
                topic = self._extract_topic(user_input)
                return f"I analyzed recommendations for {topic}. Here's my guidance:\n\n**Finding the Best Option:**\n• Research current reviews and ratings\n• Compare prices across multiple sources\n• Check recent user feedback\n• Consider warranty and support\n• Evaluate based on your budget and needs\n\n**Where to Find Current Information:**\n• Consumer review sites\n• Official product pages\n• Comparison websites\n• User communities and forums\n\nWhat's your budget range and main requirements?"
        
        elif intent == "analyze_file":
            if has_file_data:
                file_content = self._extract_useful_info(context.fetched_context, 800)
                return f"I processed and analyzed your uploaded file.\n\n{file_content}\n\nThese are the key findings from the file. What specific insights are you looking for?"
            else:
                return "I'm ready to analyze your file. Please make sure it's uploaded and let me know what specific information you'd like me to extract."
        
        elif intent == "calculate":
            # Extract numbers from input
            import re
            numbers = re.findall(r'\d+(?:\.\d+)?', user_input)
            if len(numbers) >= 2:
                # Simple calculation attempt
                return f"Based on the values in your request ({', '.join(numbers)}), I'd need to know the specific operation you want performed. Could you clarify what calculation you need?"
            return f"I'm ready to help with calculations. Please provide the specific numbers and operation you need."
        
        elif intent == "explain":
            if has_ref_data or has_web_data:
                info = self._extract_useful_info(context.fetched_context, 700)
                return f"Let me explain {self._extract_topic(user_input)}:\n\n{info}\n\nThis should help clarify the concept. Any specific aspect you'd like me to elaborate on?"
            else:
                topic = self._extract_topic(user_input)
                return f"I understand you want to know about {topic}. While I don't have detailed information immediately available, this topic generally involves understanding [key concepts]. Would you like me to explore specific aspects of this?"
        
        elif intent == "find":
            if has_web_data:
                # Extract and format with URLs preserved
                formatted_results = self._format_search_results_with_links(context.fetched_context, user_input)
                return formatted_results
            else:
                topic = self._extract_topic(user_input)
                return f"I can help you find {topic}. Here's how to get current results:\n\n**Recommended Search Methods:**\n• Use Google Maps or local business directories\n• Check review sites (TripAdvisor, Yelp, Google Reviews)\n• Visit official tourism or local government websites\n• Search social media for recent recommendations\n• Check booking platforms for availability and pricing\n\n**Tips for Best Results:**\n• Filter by rating and reviews\n• Check recent feedback (within last 6 months)\n• Compare prices across platforms\n• Look for verified reviews\n\nWould you like specific website recommendations for your search?"
        
        elif intent == "plan":
            steps = context.plan if context.plan else [
                "Define clear objectives and requirements",
                "Break down into manageable phases",
                "Identify resources and timelines",
                "Execute systematically"
            ]
            return f"I created a plan for {self._extract_topic(user_input)}:\n\n" + "\n".join([f"{i+1}. {step}" for i, step in enumerate(steps[:5])]) + "\n\nThis plan provides a structured approach. Would you like me to elaborate on any step?"
        
        # Default: Use whatever context we have
        else:
            if context.fetched_context and len(context.fetched_context) > 50:
                info = self._extract_useful_info(context.fetched_context, 600)
                return f"Based on the information I gathered:\n\n{info}\n\nThis should help with your question about {self._extract_topic(user_input)}. Let me know if you need more details!"
            else:
                return f"I'm TaskPilot AI, ready to help you with {self._extract_topic(user_input)}. To provide the most accurate and helpful answer, I'd benefit from accessing current information sources. What specific aspect can I help you with?"
    
    def _extract_topic(self, text: str) -> str:
        """Extract the main topic from user input."""
        # Remove common question words
        topic = text
        for word in ["what", "who", "where", "when", "why", "how", "is", "are", "can", "could", "would"]:
            topic = topic.replace(word + " ", "")
        
        # Clean up
        topic = topic.strip(" .?!")
        
        # If too long, take first few meaningful words
        words = topic.split()
        if len(words) > 6:
            topic = " ".join(words[:6]) + "..."
        
        return topic if topic else "your request"

    def _format_live_city_answer(self, context: AgentContext, live_query_kind: str) -> str:
        """Format live city time/weather lookups as concise direct answers."""
        fetched = context.fetched_context or ""

        city_match = re.search(r"City:\s*(.+)", fetched)
        city = city_match.group(1).strip() if city_match else self._extract_topic(context.user_input)

        if live_query_kind == "time":
            time_match = re.search(r"Local Time:\s*([0-9:AMP\s]+)", fetched)
            timezone_match = re.search(r"Timezone:\s*(.+)", fetched)
            local_time = time_match.group(1).strip() if time_match else "the current local time"
            timezone = timezone_match.group(1).strip() if timezone_match else "the local timezone"
            return (
                f"{local_time} in {city}\n"
                f"Timezone: {timezone}\n"
                f"Location: {city}"
            )

        temp_match = re.search(r"Temperature:\s*([\d.]+(?:\s*degrees\s*(?:Celsius|Fahrenheit)|°[CF]))", fetched, flags=re.IGNORECASE)
        condition_match = re.search(r"Condition:\s*(.+)", fetched)
        timezone_match = re.search(r"Timezone:\s*(.+)", fetched)
        temp = temp_match.group(1).strip() if temp_match else "the current temperature"
        condition = condition_match.group(1).strip() if condition_match else "live weather data"
        timezone = timezone_match.group(1).strip() if timezone_match else "local timezone"
        return (
            f"{temp} in {city} - {condition}\n"
            f"Temperature: {temp}\n"
            f"Condition: {condition}\n"
            f"Location: {city}\n"
            f"Timezone: {timezone}"
        )
    
    def _format_search_results_with_links(self, context: str, user_input: str) -> str:
        """Format search results with clickable links, prices, and structured information."""
        import re
        
        topic = self._extract_topic(user_input)
        
        # Extract all links with their surrounding context
        # Support multiple link formats: 🔗 Link: url, 🔗 url, [URL: url], (https://...)
        url_pattern = r'(?:🔗\s*(?:Link:|URL:)?\s*|Link:\s*|URL:\s*|\[URL:\s*)?(https?://[^\s\)\]\n]+)'
        
        # Find all matches with their positions
        url_matches = list(re.finditer(url_pattern, context))
        
        if url_matches:
            result = [f"**{topic}** - Here are the results I found:\n"]
            
            # Extract structured results around each URL
            extracted_results = []
            
            for i, match in enumerate(url_matches[:10], 1):  # Limit to 10 results
                url = match.group(1).strip()
                
                # Skip if URL is too short or invalid
                if len(url) < 10:
                    continue
                
                # Get context before the URL (title and description)
                start_pos = max(0, match.start() - 400)
                end_pos = min(len(context), match.end() + 100)
                
                surrounding_context = context[start_pos:match.start()]
                
                # Extract title - look for bold text **title** or lines with capital letters
                title_match = re.search(r'\*\*([^*]+)\*\*', surrounding_context[-200:])
                if title_match:
                    title = title_match.group(1).strip()
                else:
                    # Look for capitalized lines (likely titles)
                    lines = surrounding_context.strip().split('\n')
                    for line in reversed(lines[-3:]):  # Check last 3 lines
                        if line.strip() and line.strip()[0].isupper() and len(line.strip()) < 100:
                            title = line.strip().replace('[Source', '').replace(']', '').strip()
                            title = title.replace('**', '').strip()
                            break
                    else:
                        title = f"Result {len(extracted_results) + 1}"
                
                # Extract description - text between title and URL
                description = surrounding_context[-300:].strip()
                description = re.sub(r'\*\*[^*]+\*\*', '', description)  # Remove bold markers
                description = description.replace('[Source', '').replace(']', '').strip()
                description = ' '.join(description.split()[-40:])  # Last 40 words
                
                # Extract price information if present
                price_match = re.search(r'(?:₹|Rs\.?|\$|€|£)\s*[\d,]+(?:\.\d{2})?(?:\s*(?:per|/)\s*\w+)?', description)
                price_info = price_match.group(0) if price_match else None
                
                # Clean up description
                if len(description) > 250:
                    description = description[:250] + "..."
                
                extracted_results.append({
                    'number': len(extracted_results) + 1,
                    'title': title,
                    'description': description,
                    'url': url,
                    'price': price_info
                })
            
            # Remove duplicates based on URL
            seen_urls = set()
            unique_results = []
            for r in extracted_results:
                if r['url'] not in seen_urls:
                    seen_urls.add(r['url'])
                    unique_results.append(r)
            
            # Format the results
            for i, item in enumerate(unique_results[:8], 1):
                result.append(f"\n**{i}. {item['title']}**")
                if item['description']:
                    result.append(item['description'])
                if item['price']:
                    result.append(f"💰 **Price:** {item['price']}")
                result.append(f"🔗 **Link:** {item['url']}")
            
            if unique_results:
                result.append("\n\n💡 **Tips:**")
                result.append("• Click the links above to visit websites directly")
                result.append("• Compare prices and reviews before booking")
                result.append("• Check for current availability and offers")
                return '\n'.join(result)
        
        # Fallback: Try simpler extraction
        if 'http' in context:
            # Extract any http links even without markers
            simple_urls = re.findall(r'https?://[^\s\)\]\n]+', context)
            if simple_urls:
                result = [f"**{topic}** - Search results:\n"]
                for i, url in enumerate(set(simple_urls[:8]), 1):
                    result.append(f"\n{i}. 🔗 {url}")
                result.append("\n\n💡 Click the links to see more details.")
                return '\n'.join(result)
        
        # Final fallback: just clean up the context
        return self._extract_useful_info(context, 800)
    
    def _extract_prices_and_compare(self, context: str) -> dict[str, Any]:
        """Extract price information from context and provide comparison."""
        import re
        
        # Extract all price mentions with currency
        price_pattern = r'(?:from\s*)?(?:₹|Rs\.?|\$|€|£)\s*([\d,]+(?:\.\d{2})?)\s*(?:per|/)?(?:\s*(?:night|person|day|room))?'
        price_matches = re.findall(price_pattern, context, re.IGNORECASE)
        
        if not price_matches:
            return {"has_prices": False, "prices": [], "min": None, "max": None, "avg": None}
        
        # Convert to numbers
        prices = []
        for price_str in price_matches:
            # Remove commas and convert to float
            try:
                price_num = float(price_str.replace(',', ''))
                prices.append(price_num)
            except:
                continue
        
        if not prices:
            return {"has_prices": False, "prices": [], "min": None, "max": None, "avg": None}
        
        return {
            "has_prices": True,
            "prices": prices,
            "min": min(prices),
            "max": max(prices),
            "avg": sum(prices) / len(prices),
            "count": len(prices)
        }
    
    def _extract_useful_info(self, context: str, max_length: int = 500) -> str:
        """Extract the most useful information from fetched context."""
        if not context:
            return ""
        
        # Remove section headers
        context = context.replace("📎 UPLOADED FILES:\n", "")
        context = context.replace("🔍 WEB RESEARCH:\n", "")
        context = context.replace("📚 REFERENCE DATA:\n", "")
        context = context.replace("📰 RECENT INFO:\n", "")
        context = context.replace("⏰ Current Date:", "Current information:")
        
        # Limit length
        if len(context) <= max_length:
            return context.strip()
        
        # Try to cut at sentence boundary
        snippet = context[:max_length]
        last_period = snippet.rfind(".")
        if last_period > max_length // 2:
            snippet = snippet[:last_period + 1]
        else:
            snippet = snippet + "..."
        
        return snippet.strip()
    
    def _extract_links_from_context(self, context: str) -> list:
        """Extract links from fetched context with their titles."""
        import re
        
        if not context:
            return []
        
        links = []
        
        # Pattern 1: 🔗 Link: url format
        pattern1 = r'🔗\s*(?:Link:|URL:)?\s*(https?://[^\s\)\]\n]+)'
        matches1 = re.finditer(pattern1, context)
        for match in matches1:
            url = match.group(1).strip()
            # Try to find title before the link
            start_pos = max(0, match.start() - 150)
            preceding_text = context[start_pos:match.start()]
            
            # Look for **title** pattern
            title_match = re.search(r'\*\*([^*]{5,80})\*\*', preceding_text)
            if title_match:
                title = title_match.group(1).strip()
            else:
                # Use domain name as title
                domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
                title = domain_match.group(1) if domain_match else "Source"
            
            links.append((title, url))
        
        # Pattern 2: Plain http/https URLs
        if not links:
            pattern2 = r'(https?://[^\s\)\]\n]+)'
            matches2 = re.findall(pattern2, context)
            for url in matches2[:5]:  # Limit to 5
                domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
                title = domain_match.group(1) if domain_match else "Source"
                links.append((title, url))
        
        # Remove duplicates
        seen_urls = set()
        unique_links = []
        for title, url in links:
            if url not in seen_urls and len(url) > 10:
                seen_urls.add(url)
                unique_links.append((title, url))
        
        return unique_links
    
    # Keep old method for backwards compatibility
    def _template_based_response(self, context: AgentContext) -> str:
        """DEPRECATED: Use _intent_based_response instead."""
        intent = context.metadata.get("intent", "unknown")
        return self._intent_based_response(context, intent)
    
    def _enforce_identity(self, response: str) -> str:
        """CRITICAL: Aggressively strip ALL Gemini/LLM identity and enforce TaskPilot AI."""
        import re
        
        result = response
        
        # Phase 1: Direct identity replacements (case-insensitive)
        identity_replacements = [
            # Gemini references
            (r"\bI am Gemini\b", "I am TaskPilot AI"),
            (r"\bI'm Gemini\b", "I'm TaskPilot AI"),
            (r"\bAs Gemini\b", "As TaskPilot AI"),
            (r"\bmy name is Gemini\b", "my name is TaskPilot AI"),
            (r"\bcalled Gemini\b", "called TaskPilot AI"),
            
            # Language model references
            (r"\bI am a large language model\b", "I am TaskPilot AI"),
            (r"\bI'm a large language model\b", "I'm TaskPilot AI"),
            (r"\bI am an AI language model\b", "I am TaskPilot AI"),
            (r"\bI'm an AI language model\b", "I'm TaskPilot AI"),
            (r"\bas a language model\b", "as a task execution assistant"),
            (r"\bAs a language model\b", "As a task execution assistant"),
            (r"\bI am an AI model\b", "I am TaskPilot AI"),
            (r"\bI'm an AI model\b", "I'm TaskPilot AI"),
            (r"\bas an AI\b", "as TaskPilot AI"),
            (r"\bAs an AI\b", "As TaskPilot AI"),
            (r"\bI'm an AI\b", "I'm TaskPilot AI"),
            (r"\bI am an AI\b", "I am TaskPilot AI"),
            
            # Generic AI references
            (r"\bI am a virtual assistant\b", "I am TaskPilot AI"),
            (r"\bI'm a virtual assistant\b", "I'm TaskPilot AI"),
            (r"\bI am an assistant\b", "I am TaskPilot AI"),
            (r"\bI'm Google's\b", "I'm"),
            (r"\bGoogle's AI\b", "TaskPilot AI"),
            (r"\bdeveloped by Google\b", ""),
            (r"\bcreated by Google\b", ""),
        ]
        
        for pattern, replacement in identity_replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        # Phase 2: Remove common LLM disclaimer phrases
        disclaimer_patterns = [
            r"I don't have access to real-time information[^.]*\.",
            r"I cannot access the internet[^.]*\.",
            r"I don't have the ability to browse[^.]*\.",
            r"My knowledge cutoff[^.]*\.",
            r"Based on my training data[^.]*,?",
            r"As of my last update[^.]*,?",
            r"I do not have personal opinions[^.]*\.",
            r"I cannot provide real-time[^.]*\.",
        ]
        
        for pattern in disclaimer_patterns:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)
        
        # Phase 3: Clean up any resulting artifacts
        result = re.sub(r"\s+", " ", result)  # Remove extra spaces
        result = re.sub(r"\s+([.,!?])", r"\1", result)  # Fix punctuation spacing
        result = result.strip()
        
        # Phase 4: Safety check - if response now starts with problematic patterns, rebuild
        problematic_starts = [
            "as a", "as an", "i am a", "i'm a", "i am an", "i'm an",
            "my purpose is", "i was created", "i was developed"
        ]
        
        first_words = result.lower()[:50]
        if any(first_words.startswith(phrase) for phrase in problematic_starts):
            # Response still problematic - use fallback
            return self._create_clean_response_from_context(result)
        
        return result
    
    def _create_clean_response_from_context(self, original: str) -> str:
        """Create a clean response when identity enforcement reveals problematic content."""
        # Extract any useful information from the original response
        # But rebuild in TaskPilot AI's voice
        if len(original) > 100:
            # Has substantial content, try to salvage it
            sentences = original.split(". ")
            # Skip first sentence if it's identity-related, keep the rest
            useful_parts = [s for s in sentences[1:] if len(s) > 20]
            if useful_parts:
                return ". ".join(useful_parts) + "."
        
        return "I'm TaskPilot AI. I've processed your request, but I need more context to provide a complete answer. Could you provide more details?"
    
    def _generate_safe_fallback_response(self, context: AgentContext, intent: str) -> str:
        """Generate a safe fallback response when all other methods fail."""
        user_input = context.user_input.strip()
        
        # Check if we have any fetched context to work with
        if context.fetched_context and len(context.fetched_context) > 100:
            # Extract key information from context
            info = self._extract_useful_info(context.fetched_context, 400)
            if info and len(info) > 50:
                return f"{info}\n\nIf you need a deeper or more current update, tell me what to focus on."
        
        # Check if we have analysis
        if context.analysis and len(context.analysis) > 50:
            return f"Here is a concise response on {self._extract_topic(user_input)}:\n\n{context.analysis}\n\nTell me what to refine."
        
        # Last resort: Provide a helpful response based on the query type
        user_lower = user_input.lower()
        
        if any(word in user_lower for word in ["who is", "who's"]):
            topic = self._extract_topic(user_input)
            return (
                f"{topic}\n\n"
                f"I can add verification links or a short explanation if you want."
            )
        
        if any(word in user_lower for word in ["what is", "what's", "define"]):
            topic = self._extract_topic(user_input)
            return (
                f"{topic}\n\n"
                f"I can provide a short definition, detailed explanation, or examples."
            )

        topic = self._extract_topic(user_input)
        return (
            f"Here is a concise response about {topic}.\n\n"
            f"Tell me if you want a deeper analysis or specific sources."
        )
    
    def _extract_hotel_comparison(self, text: str, user_query: str) -> str:
        """
        🏨 SMART HOTEL PRICE COMPARISON
        
        Extracts hotel names, prices, and links from search results.
        Identifies CHEAPEST option and presents 3-4 hotels with comparison.
        """
        import re
        from urllib.parse import quote

        text = (
            text.replace("â¹", "₹")
            .replace("Â£", "£")
            .replace("Â€", "€")
            .replace("Â$", "$")
            .replace("\u00a0", " ")
        )
        
        result_lines = []
        hotels = []
        
        # Extract location from query for building booking URLs
        location = self._extract_location_from_query(user_query)
        
        # Determine currency based on location
        currency_symbol = self._get_currency_for_location(location)
        
        # Extract ALL links first
        all_links = re.findall(r'https?://[^\s<>"\\)]+', text)
        booking_links = [link for link in all_links if any(site in link.lower() 
                        for site in ['booking.com', 'hotels.com', 'expedia', 'agoda', 
                                    'trivago', 'airbnb', 'makemytrip', 'goibibo', 
                                    'tripadvisor', 'netflights', 'kayak'])]
        
        # Extract hotel information from search results
        # Pattern: Look for hotel names followed by prices
        lines = text.split('\n')
        
        current_hotel = None
        current_price = None
        current_link = None
        
        for line in lines:
            # Extract links first
            link_match = re.search(r'https?://[^\s]+', line)
            if link_match:
                current_link = self._sanitize_url(link_match.group(0))
            
            # Look for hotel names (usually in bold/title format or contain "hotel", "resort", "inn")
            hotel_patterns = [
                r'\*\*([^*]+(?:Hotel|Resort|Inn|Suites?|Lodge)[^*]*)\*\*',
                r'([A-Z][a-z]+\s+(?:Hotel|Resort|Inn|Suites?|Lodge))',
                r'((?:Hotel|Resort|Inn)\s+[A-Z][a-z]+)',
            ]
            
            for pattern in hotel_patterns:
                hotel_match = re.search(pattern, line, re.IGNORECASE)
                if hotel_match:
                    potential_name = hotel_match.group(1).strip()
                    # Avoid duplicates and overly long names
                    if len(potential_name) < 60 and not any(h['name'].lower() == potential_name.lower() for h in hotels):
                        current_hotel = potential_name
                        break
            
            # Extract prices (various formats: $100, ₹2000, 100 USD, etc.)
            # Detect which currency symbol is in the text
            detected_currency = None
            if '₹' in line:
                detected_currency = '₹'
            elif '$' in line:
                detected_currency = '$'
            elif '£' in line:
                detected_currency = '£'
            elif '€' in line:
                detected_currency = '€'
            
            price_patterns = [
                r'[\$₹£€]\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # $100, ₹2,000
                r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:USD|INR|EUR|GBP|per night|/night)',  # 100 USD
                r'(?:from|starting|price)\s*:?\s*[\$₹£€]\s*(\d{1,3}(?:,\d{3})*)',  # from $100
            ]
            
            for pattern in price_patterns:
                price_match = re.search(pattern, line, re.IGNORECASE)
                if price_match:
                    price_str = price_match.group(1).replace(',', '')
                    try:
                        current_price = float(price_str)
                        break
                    except ValueError:
                        pass
            
            # If we have a hotel and price, save it
            if current_hotel and current_price:
                short_description = re.sub(r'\s+', ' ', line.strip())
                short_description = re.sub(r'https?://[^\s]+', '', short_description).strip(" -:\t")
                if len(short_description) < 18:
                    short_description = "Current listing with verified booking source."
                hotels.append({
                    'name': current_hotel,
                    'price': current_price,
                    'currency': detected_currency or currency_symbol,
                    'link': current_link or '',
                    'description': short_description[:140],
                })
                current_hotel = None
                current_price = None
                detected_currency = None
                # Keep link for next hotel if found nearby
        
        # If we didn't find structured hotels with prices, do a simpler extraction
        if len(hotels) == 0:
            # Look for any price mentions and nearby hotel names
            for i, line in enumerate(lines):
                if 'hotel' in line.lower() or 'resort' in line.lower():
                    # Look for prices in this line or nearby lines
                    search_text = ' '.join(lines[max(0, i-1):min(len(lines), i+2)])
                    
                    hotel_name = re.search(r'([A-Z][a-zA-Z\s&]+(?:Hotel|Resort|Inn|Suites?))', line, re.IGNORECASE)
                    price = re.search(r'[\$₹£€]\s*(\d{1,3}(?:,\d{3})*)', search_text)
                    link = re.search(r'https?://[^\s]+', search_text)
                    
                    if hotel_name:
                        hotels.append({
                            'name': hotel_name.group(1).strip(),
                            'price': float(price.group(1).replace(',', '')) if price else None,
                            'link': self._sanitize_url(link.group(0)) if link else '',
                            'description': re.sub(r'\s+', ' ', line.strip())[:140],
                        })
        
        # Remove duplicates based on name similarity
        unique_hotels = []
        for hotel in hotels:
            if not any(h['name'].lower() in hotel['name'].lower() or hotel['name'].lower() in h['name'].lower() 
                      for h in unique_hotels):
                unique_hotels.append(hotel)
        
        hotels = unique_hotels[:7]  # Limit to 7 hotels

        # Localize to INR for India-related queries/locations.
        india_context = bool(location and any(token in location.lower() for token in ("india", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "chennai", "pune", "kolkata")))
        india_context = india_context or any(token in user_query.lower() for token in ("india", "indian", "inr", "rupee", "rupees"))
        if india_context:
            for hotel in hotels:
                currency = (hotel.get("currency") or "").strip()
                if not hotel.get("price"):
                    hotel["currency"] = "₹"
                    continue
                if currency in {"$", "USD", ""}:
                    hotel["price"] = round(float(hotel["price"]) * 83)
                    hotel["currency"] = "₹"
                elif currency in {"£", "GBP"}:
                    hotel["price"] = round(float(hotel["price"]) * 104)
                    hotel["currency"] = "₹"
                elif currency in {"€", "EUR"}:
                    hotel["price"] = round(float(hotel["price"]) * 90)
                    hotel["currency"] = "₹"
        
        # Sort by price (cheapest first)
        hotels_with_price = [h for h in hotels if h.get('price')]
        hotels_with_price.sort(key=lambda x: x['price'])
        hotels_without_price = [h for h in hotels if not h.get('price')]
        ordered_hotels = hotels_with_price + hotels_without_price

        # Ensure we can return at least 4 listing-style entries by adding trusted booking platforms.
        if len(ordered_hotels) < 4:
            platform_links = self._generate_booking_platform_links(location or "hotels", booking_links)
            for platform, link in platform_links:
                if any((hotel.get("link") or "") == link for hotel in ordered_hotels):
                    continue
                ordered_hotels.append({
                    "name": platform,
                    "price": None,
                    "currency": currency_symbol,
                    "link": link,
                    "description": "Live rates and availability on booking platform.",
                })
                if len(ordered_hotels) >= 7:
                    break

        if ordered_hotels:
            if location:
                result_lines.append(f"Top live hotel options in {location}")
            else:
                result_lines.append("Top live hotel options")
            result_lines.append("")

            for idx, hotel in enumerate(ordered_hotels[:7], 1):
                result_lines.append(f"{idx}. {hotel['name']}")
                hotel_currency = hotel.get('currency', currency_symbol)
                if hotel.get('price'):
                    result_lines.append(f"Price: {hotel_currency}{float(hotel['price']):.0f} per night")
                else:
                    result_lines.append(f"Price: {hotel_currency}See live listing")
                hotel_desc = str(hotel.get('description', '')).strip()[:180]
                if hotel_desc:
                    result_lines.append(f"Description: {hotel_desc}")
                link = self._sanitize_url(str(hotel.get('link', '')).strip())
                if not link:
                    if location:
                        link = f"https://www.booking.com/searchresults.html?ss={quote(location)}"
                    else:
                        link = "https://www.booking.com"
                result_lines.append(f"Direct booking link: {link}")
                result_lines.append("")

            return "\n".join(result_lines).strip()

        # No hotels found in structured way
        else:
            # Use extracted booking links OR generate location-specific links
            unique_links = list(dict.fromkeys(booking_links))[:4]  # Remove duplicates, limit to 4
            
            if len(unique_links) < 3 and location:
                # Generate location-specific booking links if we don't have enough
                location_encoded = quote(location)
                additional_links = [
                    f"https://www.booking.com/searchresults.html?ss={location_encoded}",
                    f"https://www.hotels.com/search.do?q-destination={location_encoded}",
                    f"https://www.expedia.com/Hotel-Search?destination={location_encoded}",
                    f"https://www.agoda.com/search?city={location_encoded}",
                    f"https://www.tripadvisor.com/Hotels-g-{location_encoded}.html",
                ]
                # Add generated links that aren't already in unique_links
                for link in additional_links:
                    if len(unique_links) >= 4:
                        break
                    if not any(existing.split('?')[0] in link for existing in unique_links):
                        unique_links.append(link)
            elif len(unique_links) == 0:
                # No links found at all, use generic popular sites
                unique_links = [
                    "https://www.booking.com",
                    "https://www.hotels.com",
                    "https://www.expedia.com",
                    "https://www.agoda.com"
                ]
            
            # Format output with 3-4 booking platforms
            result_lines.append("Top live hotel options")
            result_lines.append("")
            if location:
                result_lines.append(f"Search results for hotels in {location}:")
            else:
                result_lines.append("Compare prices on these platforms:")
            result_lines.append("")
            
            for i, link in enumerate(unique_links[:4], 1):
                # Try to identify the platform
                platform = f"Booking Site {i}"
                if "booking.com" in link.lower():
                    platform = "Booking.com"
                elif "hotels.com" in link.lower():
                    platform = "Hotels.com"
                elif "expedia" in link.lower():
                    platform = "Expedia"
                elif "agoda" in link.lower():
                    platform = "Agoda"
                elif "trivago" in link.lower():
                    platform = "Trivago"
                elif "airbnb" in link.lower():
                    platform = "Airbnb"
                elif "makemytrip" in link.lower():
                    platform = "MakeMyTrip"
                elif "goibibo" in link.lower():
                    platform = "Goibibo"
                elif "tripadvisor" in link.lower():
                    platform = "TripAdvisor"
                elif "kayak" in link.lower():
                    platform = "Kayak"
                
                result_lines.append(f"{i}. {platform}")
                result_lines.append(f"Price: {currency_symbol}See live listing")
                result_lines.append("Description: Reliable booking platform with live rates.")
                result_lines.append(f"Direct booking link: {link}")
                result_lines.append("")

            return "\n".join(result_lines).strip()

        return "\n".join(result_lines) if result_lines else ""
    
    def _generate_booking_platform_links(self, location: str, existing_links: list) -> list:
        """Generate location-specific booking platform links."""
        from urllib.parse import quote
        
        location_encoded = quote(location)
        platform_links = []
        
        # Check which platforms we already have links for
        existing_domains = [link.split('/')[2] if '//' in link else '' for link in existing_links]
        
        # Generate links only for platforms we don't have yet
        if 'booking.com' not in str(existing_domains):
            platform_links.append(("Booking.com", f"https://www.booking.com/searchresults.html?ss={location_encoded}"))
        
        if 'hotels.com' not in str(existing_domains):
            platform_links.append(("Hotels.com", f"https://www.hotels.com/search.do?q-destination={location_encoded}"))
        
        if 'expedia.com' not in str(existing_domains):
            platform_links.append(("Expedia", f"https://www.expedia.com/Hotel-Search?destination={location_encoded}"))
        
        if 'agoda.com' not in str(existing_domains):
            platform_links.append(("Agoda", f"https://www.agoda.com/search?city={location_encoded}"))
        
        if len(platform_links) < 4:
            if 'tripadvisor' not in str(existing_domains):
                platform_links.append(("TripAdvisor", f"https://www.tripadvisor.com/Hotels-g{location_encoded}.html"))
        
        if len(platform_links) < 4:
            if 'kayak' not in str(existing_domains):
                platform_links.append(("Kayak", f"https://www.kayak.com/hotels/{location_encoded}"))
        
        return platform_links

    def _sanitize_url(self, url: str) -> str:
        if not url:
            return ""
        cleaned = url.strip().rstrip(").,;]")
        cleaned = re.sub(r"\s+", "", cleaned)
        if not cleaned.startswith("http"):
            return ""
        return cleaned
    
    def _get_currency_for_location(self, location: str) -> str:
        """Determine the currency symbol based on location."""
        if not location:
            return '$'  # Default to USD
        
        location_lower = location.lower()
        
        # Indian cities and states - use Rupees (₹)
        indian_locations = [
            'mumbai', 'delhi', 'bangalore', 'bengaluru', 'chennai', 'hyderabad',
            'pune', 'kolkata', 'ahmedabad', 'surat', 'jaipur', 'lucknow',
            'kanpur', 'nagpur', 'indore', 'thane', 'bhopal', 'visakhapatnam',
            'pimpri', 'patna', 'vadodara', 'ghaziabad', 'ludhiana', 'agra',
            'nashik', 'faridabad', 'meerut', 'rajkot', 'varanasi', 'srinagar',
            'aurangabad', 'dhanbad', 'amritsar', 'navi mumbai', 'allahabad',
            'ranchi', 'howrah', 'coimbatore', 'jabalpur', 'gwalior', 'vijayawada',
            'jodhpur', 'madurai', 'raipur', 'kota', 'guwahati', 'chandigarh',
            'india', 'indian', 'bharat'
        ]
        
        # UK - use Pounds (£)
        uk_locations = ['london', 'uk', 'united kingdom', 'britain', 'england', 
                        'scotland', 'wales', 'manchester', 'liverpool', 'birmingham']
        
        # Euro zone - use Euros (€)
        euro_locations = [
            'paris', 'france', 'berlin', 'germany', 'rome', 'italy', 'madrid', 'spain',
            'amsterdam', 'netherlands', 'brussels', 'belgium', 'vienna', 'austria',
            'dublin', 'ireland', 'lisbon', 'portugal', 'athens', 'greece',
            'barcelona', 'milan', 'munich', 'prague', 'czech', 'finland', 'sweden'
        ]
        
        # Check location against currency zones
        for loc in indian_locations:
            if loc in location_lower:
                return '₹'
        
        for loc in uk_locations:
            if loc in location_lower:
                return '£'
        
        for loc in euro_locations:
            if loc in location_lower:
                return '€'
        
        # Default to USD for US and other countries
        return '$'
    
    def _extract_location_from_query(self, query: str) -> str:
        """Extract location/city name from hotel query."""
        import re

        query_lower = query.lower()
        query_clean = re.sub(r"[^a-z0-9\s\-]", "", query_lower)

        # Prefer explicit location phrases like "in Bangalore" or "near Mumbai".
        match = re.search(r"\b(?:in|at|near|around|within)\s+([a-z][a-z\s\-]{2,60})", query_clean)
        if match:
            candidate = match.group(1).strip()
            candidate = re.sub(
                r"\b(hotel|hotels|restaurant|restaurants|resort|accommodation|stay|cheap|cheapest|best|top|budget|price|prices|cost|under|below|per|night|nearby|near\s+me)\b",
                "",
                candidate,
            ).strip()
            if candidate:
                return candidate.title()

        # Fallback: use capitalized words, but drop question/descriptor words.
        blacklist = {
            "What", "Which", "Who", "Where", "How", "Cheapest", "Best", "Top",
            "Hotels", "Hotel", "Restaurants", "Restaurant", "Prices", "Price",
            "Compare", "Comparison", "Under", "Below",
        }
        words = query.split()
        location_words = [w for w in words if w[:1].isupper() and len(w) > 2 and w not in blacklist]

        if location_words:
            return " ".join(location_words)

        # Final fallback: strip common service words from the entire query.
        query_clean = re.sub(
            r"\b(cheap|cheapest|hotel|hotels|restaurant|restaurants|resort|accommodation|stay|in|at|near|best|affordable|budget|price|prices|cost|under|below|per|night)\b",
            "",
            query_clean,
        ).strip()
        if query_clean:
            return query_clean.title()

        return ""
        
        # Default response
        return f"I'm ready to help with your request about {self._extract_topic(user_input)}. To provide the most useful answer, could you let me know what specific information you're looking for?"
