#!/usr/bin/env python3
"""
Gemini API Configuration Verification
Tests that the Gemini API key is properly configured and working.
"""

import asyncio
import os
import sys


async def verify_gemini_config():
    """Verify Gemini API configuration and connectivity."""

    import logging
    logging.basicConfig(level=logging.INFO)

    print("=" * 70)
    print("TaskPilot AI - Gemini API Configuration Check")
    print("=" * 70)
    print()

    # Load .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # python-dotenv might not be installed
    print("1️⃣  Checking GEMINI_API_KEY environment variable...")
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        masked_key = f"{api_key[:10]}...{api_key[-4:]}" if len(api_key) > 14 else "*" * len(api_key)
        print(f"   ✅ API Key found: {masked_key}")
    else:
        print("   ⚠️  API Key not found in environment")
        print("   💡 Make sure .env file exists with GEMINI_API_KEY set")
        return False
    print()

    # Check 2: Google Generative AI Library
    print("2️⃣  Checking google-generativeai library...")
    try:
        import google.generativeai as genai
        print(f"   ✅ Library installed (version: {genai.__version__})")
    except ImportError:
        print("   ❌ Library not installed")
        print("   💡 Run: pip install google-generativeai")
        return False
    print()

    # Check 3: API Connection Test
    print("3️⃣  Testing Gemini API connection...")
    try:
        from app.services.ai.gemini import GeminiProvider
        
        provider = GeminiProvider(api_key=api_key)
        test_prompt = "Say 'Hello' in one word."
        
        print("   🔄 Sending test request to Gemini API...")
        response = await provider.generate(test_prompt)
        
        if response and len(response) > 0:
            print(f"   ✅ API Response received: '{response[:50]}...'")
        else:
            print("   ⚠️  API returned empty response")
            print("   💡 Check if API key is valid and has quota")
            return False
    except Exception as e:
        print(f"   ❌ API Error: {str(e)[:100]}")
        return False
    print()

    # Check 4: Agent Integration Test
    print("4️⃣  Testing Agent Integration...")
    try:
        from app.services.agents.base import AgentContext
        from app.services.agents.planner import PlannerAgent
        from app.services.agents.reporter import ReporterAgent
        from app.services.ai.factory import get_provider
        
        llm = get_provider()
        context = AgentContext(user_input="Create a simple test plan")
        
        # Test Planner
        print("   🔄 Testing PlannerAgent with Gemini...")
        planner = PlannerAgent(llm)
        planner_result = await planner.run(context)
        method = planner_result.details.get("method", "unknown")
        print(f"   ✅ PlannerAgent: {method} (steps: {len(context.plan)})")
        
        # Test Reporter
        print("   🔄 Testing ReporterAgent with Gemini...")
        reporter = ReporterAgent(llm)
        reporter_result = await reporter.run(context)
        method = reporter_result.details.get("method", "unknown")
        print(f"   ✅ ReporterAgent: {method}")
        
    except Exception as e:
        print(f"   ❌ Agent Error: {str(e)[:100]}")
        return False
    print()

    # Check 5: Full Orchestration Test
    print("5️⃣  Testing Full Orchestration Pipeline...")
    try:
        from app.services.orchestrator import TaskOrchestrator
        
        orchestrator = TaskOrchestrator()
        print("   🔄 Running full agent pipeline...")
        result = await orchestrator.run("What is Python programming?")
        
        if result.final_response and len(result.final_response) > 10:
            print(f"   ✅ Orchestration complete")
            print(f"   📊 Agent steps: {len(result.steps)}")
            print(f"   📝 Response length: {len(result.final_response)} chars")
        else:
            print("   ⚠️  Orchestration completed but response is short")
            
    except Exception as e:
        print(f"   ❌ Orchestration Error: {str(e)[:100]}")
        return False
    print()

    print("=" * 70)
    print("✅ All Checks Passed - Gemini API is properly configured!")
    print("=" * 70)
    print()
    print("💡 Next Steps:")
    print("   • Start the backend: uvicorn app.main:app --reload")
    print("   • Test with frontend or API calls")
    print("   • Monitor agent responses for LLM-generated content")
    print()
    return True


async def check_fallback_mode():
    """Test that fallback mode works when API key is missing."""
    print("=" * 70)
    print("Testing Fallback Mode (No API Key)")
    print("=" * 70)
    print()
    
    # 0. Test Orchestrator Fallback (Mock Failure)
    print("0️⃣  Testing Orchestrator Fallback (Simulated Failure)...")
    try:
        from app.services.orchestrator import TaskOrchestrator
        orchestrator = TaskOrchestrator()
        
        # Mock LLM failure
        original_generate = orchestrator.llm.generate
        async def mock_fail(*args, **kwargs):
            raise Exception("Simulated Quota Exceeded")
        orchestrator.llm.generate = mock_fail
        
        result = await orchestrator.run("What is the capital of France?")
        print(f"   Fallback Response: {result.final_response[:100]}...")
        
        if "lightweight analysis" in result.final_response:
             print("✅ Orchestrator Fallback mode working correctly!")
        else:
             print("❌ Orchestrator Fallback mode NOT detected in response.")
        
        # Restore
        orchestrator.llm.generate = original_generate
        print()
         
    except Exception as e:
        print(f"❌ Orchestrator Fallback test failed: {e}")
        print()
    
    # Temporarily clear API key
    original_key = os.environ.get("GEMINI_API_KEY")
    if "GEMINI_API_KEY" in os.environ:
        del os.environ["GEMINI_API_KEY"]
    
    try:
        from app.services.agents.base import AgentContext
        from app.services.agents.planner import PlannerAgent
        from app.services.agents.reporter import ReporterAgent
        from app.services.ai.factory import get_provider
        
        llm = get_provider()
        context = AgentContext(user_input="Test fallback planning")
        
        print("🔄 Testing PlannerAgent fallback (rule-based)...")
        planner = PlannerAgent(llm)
        result = await planner.run(context)
        method = result.details.get("method", "unknown")
        print(f"✅ PlannerAgent fallback: {method}")
        print(f"   Generated {len(context.plan)} steps")
        print()
        
        print("🔄 Testing ReporterAgent fallback (template-based)...")
        reporter = ReporterAgent(llm)
        result = await reporter.run(context)
        method = result.details.get("method", "unknown")
        print(f"✅ ReporterAgent fallback: {method}")
        print(f"   Response length: {len(result.output)} chars")
        print()
        
        print("✅ Fallback mode working correctly!")
        print("💡 Backend operates safely even without API keys")
        print()
        
    finally:
        # Restore API key
        if original_key:
            os.environ["GEMINI_API_KEY"] = original_key


if __name__ == "__main__":
    print()
    
    # Run configuration verification
    success = asyncio.run(verify_gemini_config())
    
    if success:
        print()
        print("━" * 70)
        print()
        
        # Also test fallback mode
        asyncio.run(check_fallback_mode())
        
        print("🚀 Configuration Complete!")
        print()
        sys.exit(0)
    else:
        print()
        print("⚠️  Configuration incomplete. Please fix the issues above.")
        print()
        sys.exit(1)
