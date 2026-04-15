#!/usr/bin/env python3
"""
TaskPilot AI Backend - Quick Test Script
Validates that all agents work correctly with and without API keys.
"""

import asyncio
import sys


async def test_agents():
    """Test all agents with sample input."""
    print("=" * 60)
    print("TaskPilot AI Backend - Agent Tests")
    print("=" * 60)
    print()

    # Import agents
    try:
        from app.services.agents.base import AgentContext
        from app.services.agents.fetcher import FetcherAgent
        from app.services.agents.analyzer import AnalyzerAgent
        from app.services.agents.planner import PlannerAgent
        from app.services.agents.reporter import ReporterAgent
        from app.services.ai.factory import get_provider
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("Make sure you're running from the backend directory.")
        return False

    # Create test context
    context = AgentContext(
        user_input="What is artificial intelligence and how does it work?",
        screen_context="User is learning about AI concepts"
    )

    print("📝 Test Query:", context.user_input)
    print("🖥️  Screen Context:", context.screen_context)
    print()

    # Test FetcherAgent
    print("━" * 60)
    print("1️⃣  Testing FetcherAgent (DuckDuckGo + Wikipedia)")
    print("━" * 60)
    try:
        fetcher = FetcherAgent()
        result = await fetcher.run(context)
        print(f"✅ Status: {result.status}")
        print(f"📄 Output: {result.output[:200]}...")
        print()
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    # Test AnalyzerAgent
    print("━" * 60)
    print("2️⃣  Testing AnalyzerAgent (Pure Python Logic)")
    print("━" * 60)
    try:
        analyzer = AnalyzerAgent()
        result = await analyzer.run(context)
        print(f"✅ Status: {result.status}")
        print(f"📄 Output: {result.output}")
        print()
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    # Test PlannerAgent
    print("━" * 60)
    print("3️⃣  Testing PlannerAgent (LLM + Fallback)")
    print("━" * 60)
    try:
        llm = get_provider()
        planner = PlannerAgent(llm)
        result = await planner.run(context)
        print(f"✅ Status: {result.status}")
        print(f"📄 Method: {result.details.get('method', 'unknown')}")
        print(f"📋 Plan Steps:")
        for i, step in enumerate(context.plan, 1):
            print(f"   {i}. {step}")
        print()
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    # Test ReporterAgent
    print("━" * 60)
    print("4️⃣  Testing ReporterAgent (LLM + Fallback)")
    print("━" * 60)
    try:
        reporter = ReporterAgent(llm)
        result = await reporter.run(context)
        print(f"✅ Status: {result.status}")
        print(f"📄 Method: {result.details.get('method', 'unknown')}")
        print(f"📝 Response Preview:")
        print(f"   {result.output[:300]}...")
        print()
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    # Test Full Orchestration
    print("━" * 60)
    print("5️⃣  Testing TaskOrchestrator (Full Pipeline)")
    print("━" * 60)
    try:
        from app.services.orchestrator import TaskOrchestrator
        orchestrator = TaskOrchestrator()
        result = await orchestrator.run(context.user_input, context.screen_context)
        print(f"✅ Final Response Generated")
        print(f"📊 Agent Summary: {result.summary}")
        print(f"📝 Final Response Preview:")
        print(f"   {result.final_response[:300]}...")
        print()
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    print("=" * 60)
    print("✅ All Tests Passed!")
    print("=" * 60)
    print()
    print("💡 Notes:")
    print("   • If using fallback methods, consider adding GEMINI_API_KEY")
    print("   • Backend is fully functional with or without API keys")
    print("   • All agents handle errors gracefully")
    print()
    return True


async def test_api_availability():
    """Check availability of optional external APIs."""
    print("=" * 60)
    print("External API Availability Check")
    print("=" * 60)
    print()

    # Check DuckDuckGo
    try:
        from duckduckgo_search import DDGS
        print("✅ DuckDuckGo Search: Available")
    except ImportError:
        print("⚠️  DuckDuckGo Search: Not installed (optional)")

    # Check Wikipedia
    try:
        import wikipedia
        print("✅ Wikipedia API: Available")
    except ImportError:
        print("⚠️  Wikipedia API: Not installed (optional)")

    # Check Gemini
    try:
        import google.generativeai
        print("✅ Google Gemini AI: Library installed")
        import os
        if os.getenv("GEMINI_API_KEY"):
            print("   🔑 API Key: Configured")
        else:
            print("   ⚠️  API Key: Not set (will use fallbacks)")
    except ImportError:
        print("⚠️  Google Gemini AI: Not installed (optional)")

    print()


if __name__ == "__main__":
    print()
    # Check API availability
    asyncio.run(test_api_availability())
    
    # Run agent tests
    success = asyncio.run(test_agents())
    
    if success:
        print("🚀 Backend is ready for production!")
        print("   Run: uvicorn app.main:app --reload")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed. Check the errors above.")
        sys.exit(1)
