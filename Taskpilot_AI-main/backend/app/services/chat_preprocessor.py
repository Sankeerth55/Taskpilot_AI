from __future__ import annotations

import difflib
import re
from typing import TypedDict


class QueryRouting(TypedDict):
    query_type: str
    intent: str
    complexity: str
    requires_live_data: bool
    reason: str
    region_hint: str
    currency_hint: str
    include_news: bool


_GREETING_PATTERNS = {
    "hi",
    "hello",
    "hey",
    "good morning",
    "good evening",
    "good afternoon",
    "hola",
}

_INDIA_HINTS = (
    "india",
    "indian",
    "inr",
    "rupee",
    "rupees",
    "bangalore",
    "bengaluru",
    "mumbai",
    "delhi",
    "hyderabad",
    "chennai",
    "pune",
    "kolkata",
    "nifty",
    "sensex",
    "bse",
    "nse",
)

# News / Trading / Market triggers — must fire BEFORE general/factual checks
_NEWS_TRADING_TERMS = (
    "latest news",
    "ai news",
    "tech news",
    "today news",
    "current news",
    "breaking news",
    "news",
    "past week news",
    "past day news",
    "past one day news",
    "past 1 day news",
    "last 24 hours",
    "yesterday news",
    "past month news",
    "last week news",
    "last month news",
    "weekly news",
    "monthly news",
    "news about",
    "news on",
    "what is happening",
    "market news",
    "stock market",
    "stock price",
    "share price",
    "nifty",
    "sensex",
    "nasdaq",
    "dow jones",
    "s&p",
    "s and p",
    "crypto",
    "bitcoin",
    "ethereum",
    "trading",
    "market update",
    "market today",
    "market analysis",
    "investing",
    "investment update",
    "hedge fund",
    "ipo",
    "bull market",
    "bear market",
    "forex",
    "currency rate",
    "exchange rate",
    "commodity",
    "gold price",
    "silver price",
    "oil price",
    "crude oil",
    "commodity price",
)


def normalize_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip().lower())
    # Normalize common location misspellings and joined state names.
    replacements = {
        "tamilnadu": "tamil nadu",
        "tamilnado": "tamil nadu",
        "keralam": "kerala",
        "kerla": "kerala",
        "andhrapradesh": "andhra pradesh",
        "uttarpradesh": "uttar pradesh",
        "madhyapradesh": "madhya pradesh",
        "maharastra": "maharashtra",
        "gujrat": "gujarat",
        "telegana": "telangana",
        "karnatka": "karnataka",
        "cheif": "chief",
        "ministar": "minister",
        "ministor": "minister",
        "cm": "cm",
        "pm": "pm",
    }
    for wrong, right in replacements.items():
        cleaned = cleaned.replace(wrong, right)
    cleaned = re.sub(r"[^a-z0-9\s&]", "", cleaned)
    cleaned = _correct_spelling_tokens(cleaned)
    return cleaned


def _correct_spelling_tokens(text: str) -> str:
    """Lightweight token spell-correction for common factual/query terms."""
    if not text:
        return text

    explicit_map = {
        "cheif": "chief",
        "ministar": "minister",
        "ministor": "minister",
        "priminister": "prime minister",
        "primeminister": "prime minister",
        "presedent": "president",
        "president": "president",
        "wether": "weather",
        "temprature": "temperature",
        "tempratue": "temperature",
        "currnt": "current",
        "curent": "current",
        "latset": "latest",
        "tody": "today",
        "yesturday": "yesterday",
        "newz": "news",
        "restarant": "restaurant",
        "restaurent": "restaurant",
        "resturant": "restaurant",
        "hotle": "hotel",
        "bookig": "booking",
        "capitol": "capital",
        "popultion": "population",
        "fouder": "founder",
        "ceo": "ceo",
        "cm": "cm",
        "pm": "pm",
        "tamilnadu": "tamil nadu",
        "keralam": "kerala",
        "andhrapradesh": "andhra pradesh",
        "uttarpradesh": "uttar pradesh",
        "madhyapradesh": "madhya pradesh",
        "maharastra": "maharashtra",
        "gujrat": "gujarat",
        "telegana": "telangana",
        "karnatka": "karnataka",
    }

    vocab = {
        "chief",
        "minister",
        "prime",
        "president",
        "founder",
        "ceo",
        "chief minister",
        "prime minister",
        "president",
        "weather",
        "temperature",
        "current",
        "latest",
        "today",
        "yesterday",
        "news",
        "market",
        "trading",
        "hotel",
        "hotels",
        "restaurant",
        "restaurants",
        "booking",
        "capital",
        "population",
        "tamil",
        "nadu",
        "kerala",
        "andhra",
        "pradesh",
        "uttar",
        "madhya",
        "maharashtra",
        "gujarat",
        "telangana",
        "karnataka",
        "india",
        "cm",
        "pm",
    }

    tokens = text.split()
    corrected: list[str] = []
    for token in tokens:
        if token.isdigit() or len(token) < 4:
            corrected.append(token)
            continue

        if token in explicit_map:
            corrected.append(explicit_map[token])
            continue

        if token in vocab:
            corrected.append(token)
            continue

        match = difflib.get_close_matches(token, vocab, n=1, cutoff=0.88)
        corrected.append(match[0] if match else token)

    return " ".join(corrected)


def is_instant_greeting(user_input: str) -> bool:
    normalized = normalize_text(user_input)
    if not normalized:
        return False
    if normalized in _GREETING_PATTERNS:
        return True
    # Accept compact social greetings like "hi there", "hey bot".
    return bool(re.fullmatch(r"(hi|hello|hey)(\s+[a-z0-9]+){0,2}", normalized))


def greeting_reply() -> str:
    return "Hello! I'm TaskPilot AI. How can I assist you today? I can help with real-time information, news, research, and much more!"


def classify_query(user_input: str) -> QueryRouting:
    text = normalize_text(user_input)
    words = text.split()

    region_hint = "india" if any(hint in text for hint in _INDIA_HINTS) else "global"
    currency_hint = "INR" if region_hint == "india" else "AUTO"

    service_terms = (
        "hotel",
        "hotels",
        "restaurant",
        "restaurants",
        "near me",
        "nearby",
        "booking",
        "book",
        "cheap hotel",
        "cheapest hotel",
        "accommodation",
        "resort",
        "motel",
        "hostel",
        "airbnb",
    )

    comparison_terms = (
        "compare",
        "vs",
        "difference",
        "better",
        "best",
        "cheapest",
        "top",
        "pros and cons",
    )

    explanation_terms = (
        "explain",
        "how does",
        "why does",
        "what is",
        "whats",
        "define",
        "definition",
        "meaning",
        "summary",
        "summarize",
        "guide",
        "tutorial",
        "step by step",
        "architecture",
    )

    general_definition_terms = (
        "define",
        "definition",
        "meaning",
        "summary",
        "summarize",
        "what is",
        "what's",
        "whats",
    )

    factual_live_terms = (
        "who is",
        "who founded",
        "founder",
        "ceo",
        "president",
        "prime minister",
        " pm ",
        "cm",
        "chief minister",
        "where is",
        "which country",
        "which city",
        "capital of",
        "population",
        "time in",
        "current time",
        "local time",
        "weather in",
        "temperature in",
    )

    live_time_weather = any(token in text for token in (
        "time in",
        "current time",
        "local time",
        "weather in",
        "temperature in",
        "temperature at",
        "weather at",
    ))

    # ─────────────────────────────────────────────────────────────
    # PRIORITY 1: NEWS / TRADING / MARKET queries — must go first
    # These need multi-source live news fetching, not just web search
    # ─────────────────────────────────────────────────────────────
    if any(term in text for term in _NEWS_TRADING_TERMS):
        return {
            "query_type": "news_trading",
            "intent": "research",
            "complexity": "high",
            "requires_live_data": True,
            "reason": "News/trading/market query requires live multi-source news fetch.",
            "region_hint": region_hint,
            "currency_hint": currency_hint,
            "include_news": True,
        }

    # ─────────────────────────────────────────────────────────────
    # PRIORITY 2: SERVICE queries (hotels, restaurants, bookings)
    # ─────────────────────────────────────────────────────────────
    if any(term in text for term in service_terms):
        return {
            "query_type": "services",
            "intent": "research",
            "complexity": "high" if any(t in text for t in ["best", "cheapest", "compare"]) else "medium",
            "requires_live_data": True,
            "reason": "Service/booking query requires live listings and pricing.",
            "region_hint": region_hint,
            "currency_hint": currency_hint,
            "include_news": False,
        }

    # ─────────────────────────────────────────────────────────────
    # PRIORITY 3: Live time / weather
    # ─────────────────────────────────────────────────────────────
    if live_time_weather:
        return {
            "query_type": "factual_realtime",
            "intent": "research",
            "complexity": "simple",
            "requires_live_data": True,
            "reason": "Live time/weather query requires real-time data fetch.",
            "region_hint": region_hint,
            "currency_hint": currency_hint,
            "include_news": False,
        }

    # ─────────────────────────────────────────────────────────────
    # PRIORITY 4: Factual / real-time person/position queries
    # ─────────────────────────────────────────────────────────────
    is_latest_or_current = any(token in text for token in ("latest", "current", "today", "now", "recent", "present"))
    if (
        any(term in text for term in factual_live_terms)
        or any(text.startswith(prefix) for prefix in ("who", "where", "when", "which"))
    ):
        return {
            "query_type": "factual_realtime",
            "intent": "factual",
            "complexity": "simple" if len(words) <= 14 else "medium",
            "requires_live_data": True,
            "reason": "Factual/real-time query routed to live web + reference fetch.",
            "region_hint": region_hint,
            "currency_hint": currency_hint,
            "include_news": is_latest_or_current,
        }

    # ─────────────────────────────────────────────────────────────
    # PRIORITY 5: Comparison queries
    # ─────────────────────────────────────────────────────────────
    if any(token in text for token in comparison_terms):
        return {
            "query_type": "comparison",
            "intent": "compare",
            "complexity": "medium",
            "requires_live_data": True,
            "reason": "Comparison-style query should be analyzed and ranked.",
            "region_hint": region_hint,
            "currency_hint": currency_hint,
            "include_news": is_latest_or_current,
        }

    # ─────────────────────────────────────────────────────────────
    # PRIORITY 6: General explanatory — Gemini direct, no web
    # ─────────────────────────────────────────────────────────────
    if any(token in text for token in explanation_terms):
        # But if "current" / "latest" / "today" is also present, it's factual
        if is_latest_or_current:
            return {
                "query_type": "factual_realtime",
                "intent": "factual",
                "complexity": "medium",
                "requires_live_data": True,
                "reason": "Explanatory query with current/latest keyword — fetching live data.",
                "region_hint": region_hint,
                "currency_hint": currency_hint,
                "include_news": True,
            }
        return {
            "query_type": "general",
            "intent": "explain",
            "complexity": "medium" if len(words) <= 22 else "high",
            "requires_live_data": False,
            "reason": "General explanatory query should use Gemini directly — no web fetch needed.",
            "region_hint": region_hint,
            "currency_hint": currency_hint,
            "include_news": False,
        }

    # ─────────────────────────────────────────────────────────────
    # PRIORITY 6.5: Definition/meaning/summarize should stay GENERAL
    # ─────────────────────────────────────────────────────────────
    if any(token in text for token in general_definition_terms):
        if any(term in text for term in ("capital", "population")):
            pass
        else:
            return {
                "query_type": "general",
                "intent": "explain",
                "complexity": "simple" if len(words) <= 18 else "medium",
                "requires_live_data": False,
                "reason": "Definition/meaning/summary query should use Gemini directly — no web fetch needed.",
                "region_hint": region_hint,
                "currency_hint": currency_hint,
                "include_news": False,
            }

    # ─────────────────────────────────────────────────────────────
    # PRIORITY 7: Factual starts / current info
    # ─────────────────────────────────────────────────────────────
    factual_starts = ("who", "what", "when", "where", "which", "capital of", "president of")
    factual_phrases = ("current", "latest", "population", "price", "cost", "under", "pm of", "ceo of")

    complex_phrases = (
        "compare",
        "plan",
        "analyze",
        "research",
        "best",
        "recommend",
        "step by step",
    )

    if any(text.startswith(prefix) for prefix in factual_starts) or any(token in text for token in factual_phrases):
        if text.startswith("what is") or text.startswith("what's") or text.startswith("whats"):
            if not any(term in text for term in ("capital", "population", "president", "prime minister", "pm", "cm", "ceo", "founder")):
                return {
                    "query_type": "general",
                    "intent": "explain",
                    "complexity": "simple" if len(words) <= 18 else "medium",
                    "requires_live_data": False,
                    "reason": "General definition query routed to Gemini direct response.",
                    "region_hint": region_hint,
                    "currency_hint": currency_hint,
                    "include_news": False,
                }
        return {
            "query_type": "factual_realtime",
            "intent": "factual",
            "complexity": "simple" if len(words) <= 16 else "medium",
            "requires_live_data": True,
            "reason": "Factual query routed to live data sources.",
            "region_hint": region_hint,
            "currency_hint": currency_hint,
            "include_news": is_latest_or_current,
        }

    if any(token in text for token in complex_phrases) or len(words) > 16:
        return {
            "query_type": "complex_task",
            "intent": "research",
            "complexity": "high" if len(words) > 24 else "medium",
            "requires_live_data": True,
            "reason": "Complex query routed to full multi-agent pipeline.",
            "region_hint": region_hint,
            "currency_hint": currency_hint,
            "include_news": is_latest_or_current,
        }

    return {
        "query_type": "general",
        "intent": "explain",
        "complexity": "simple" if len(words) <= 14 else "medium",
        "requires_live_data": False,
        "reason": "General query handled directly by Gemini response mode.",
        "region_hint": region_hint,
        "currency_hint": currency_hint,
        "include_news": False,
    }
