from __future__ import annotations

import unittest

from app.services.agents.base import AgentContext
from app.services.agents.fetcher import FetcherAgent
from app.services.agents.reporter import ReporterAgent
from app.services.chat_preprocessor import classify_query, normalize_text
from app.services.orchestrator import TaskOrchestrator


class ChatRoutingContractsTest(unittest.TestCase):
    def test_factual_realtime_routing(self) -> None:
        routing = classify_query("Who is the CEO of Google?")
        self.assertEqual(routing["query_type"], "factual_realtime")
        self.assertTrue(routing["requires_live_data"])

    def test_general_question_routing(self) -> None:
        routing = classify_query("What is machine learning?")
        self.assertEqual(routing["query_type"], "general")
        self.assertFalse(routing["requires_live_data"])

    def test_services_routing(self) -> None:
        routing = classify_query("cheapest hotels in Bangalore")
        self.assertEqual(routing["query_type"], "services")
        self.assertTrue(routing["requires_live_data"])

    def test_natural_time_phrase_routing(self) -> None:
        routing = classify_query("Can you tell me the present time in Baltimore")
        self.assertEqual(routing["query_type"], "factual_realtime")
        self.assertTrue(routing["requires_live_data"])

    def test_misspelled_cm_query_routing(self) -> None:
        routing = classify_query("who is the cheif ministor of tamilnadu")
        self.assertEqual(routing["query_type"], "factual_realtime")
        self.assertTrue(routing["requires_live_data"])

    def test_normalize_text_spelling(self) -> None:
        normalized = normalize_text("cheif ministor in Keralam")
        self.assertIn("chief minister", normalized)
        self.assertIn("kerala", normalized)


class FetcherLiveParsingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fetcher = FetcherAgent()

    def test_detect_present_time_phrase(self) -> None:
        kind = self.fetcher._detect_live_city_query_kind("Can you tell me the present time in Baltimore")
        self.assertEqual(kind, "time")

    def test_extract_city_from_present_time_phrase(self) -> None:
        city = self.fetcher._extract_city_from_live_query("Can you tell me the present time in Baltimore")
        self.assertEqual(city.lower(), "baltimore")


class OrchestratorInputNormalizationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.orchestrator = TaskOrchestrator.__new__(TaskOrchestrator)

    def test_followup_cm_query_infers_location(self) -> None:
        history = [
            {"role": "user", "content": "who is the cm in Karnataka"},
            {"role": "assistant", "content": "Siddaramaiah is the Chief Minister of Karnataka."},
        ]
        normalized = self.orchestrator._normalize_user_input("who is the cm", history)
        self.assertIn("in karnataka", normalized)

    def test_orchestrator_spell_correction(self) -> None:
        normalized = self.orchestrator._normalize_user_input("cheif ministor of keralam", [])
        self.assertIn("chief minister", normalized)
        self.assertIn("kerala", normalized)


class ReporterContractsTest(unittest.TestCase):
    def setUp(self) -> None:
        # Bypass heavy model loading for unit-level formatter checks.
        self.reporter = ReporterAgent.__new__(ReporterAgent)
        self.reporter.llm = None

    def test_factual_output_contract(self) -> None:
        context = AgentContext(
            user_input="Who is the Prime Minister of India",
            fetched_context=(
                "Sample source Narendra Modi is the Prime Minister of India. "
                "https://en.wikipedia.org/wiki/Prime_Minister_of_India\n"
                "https://www.britannica.com/biography/Narendra-Modi"
            ),
        )

        formatted = self.reporter._format_factual_response(
            context,
            "Narendra Modi\nHe is the Prime Minister of India.",
            "person",
        )

        lines = [line for line in formatted.splitlines() if line.strip()]
        self.assertGreaterEqual(len(lines), 6)
        self.assertIn("View on Wikipedia:", formatted)
        self.assertIn("Search More:", formatted)
        self.assertIn("Open Source:", formatted)

    def test_live_time_contract(self) -> None:
        context = AgentContext(
            user_input="current time in Tokyo",
            fetched_context=(
                "LIVE TIME\n"
                "City: Tokyo, Japan\n"
                "Local Time: 09:45 PM\n"
                "Timezone: Asia/Tokyo\n"
                "Source: Open-Meteo"
            ),
        )
        out = self.reporter._format_live_city_answer(context, "time")
        self.assertIn("Timezone:", out)
        self.assertIn("Location:", out)

    def test_service_output_shape(self) -> None:
        text = """
Budget Stay Hotel - from $50 per night
https://www.booking.com/hotel/example1

City Comfort Hotel - from $65 per night
https://www.expedia.com/hotel/example2
"""
        out = self.reporter._extract_hotel_comparison(text, "cheapest hotels in Bangalore")
        self.assertIn("Top live hotel options", out)
        self.assertIn("Direct booking link:", out)
        self.assertGreaterEqual(out.count("Direct booking link:"), 4)


if __name__ == "__main__":
    unittest.main()
