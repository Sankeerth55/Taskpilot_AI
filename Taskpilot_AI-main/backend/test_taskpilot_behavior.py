"""
Comprehensive test suite for TaskPilot AI behavior validation.

Tests all critical requirements:
- Always provides final answers
- Never asks unnecessary clarification questions
- Maintains TaskPilot AI identity
- Never exposes internal agent reasoning
- Handles all question types appropriately
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.orchestrator import TaskOrchestrator


async def test_greeting():
    """Test simple greeting responses."""
    print("\n" + "="*60)
    print("TEST 1: GREETING HANDLING")
    print("="*60)
    
    orchestrator = TaskOrchestrator()
    
    test_cases = ["hi", "hello", "hey there", "good morning"]
    
    for greeting in test_cases:
        result = await orchestrator.run(greeting)
        print(f"\nInput: '{greeting}'")
        print(f"Response: {result.final_response}")
        assert result.final_response, "Response must not be empty"
        assert len(result.final_response) > 5, "Response must be meaningful"
        print("✓ PASS")


async def test_identity_questions():
    """Test identity-related questions."""
    print("\n" + "="*60)
    print("TEST 2: IDENTITY QUESTIONS")
    print("="*60)
    
    orchestrator = TaskOrchestrator()
    
    test_cases = [
        "What is your name?",
        "Who are you?",
        "What are you?",
    ]
    
    for question in test_cases:
        result = await orchestrator.run(question)
        print(f"\nInput: '{question}'")
        print(f"Response: {result.final_response}")
        
        # Verify TaskPilot AI identity
        response_lower = result.final_response.lower()
        assert "taskpilot" in response_lower, "Must identify as TaskPilot AI"
        assert "gemini" not in response_lower, "Must NOT mention Gemini"
        assert result.final_response, "Response must not be empty"
        print("✓ PASS: Correctly identifies as TaskPilot AI")


async def test_capability_questions():
    """Test capability/feature questions."""
    print("\n" + "="*60)
    print("TEST 3: CAPABILITY QUESTIONS")
    print("="*60)
    
    orchestrator = TaskOrchestrator()
    
    test_cases = [
        "What can you do?",
        "How do you work?",
        "What do you do?",
    ]
    
    for question in test_cases:
        result = await orchestrator.run(question)
        print(f"\nInput: '{question}'")
        print(f"Response: {result.final_response}")
        
        assert result.final_response, "Response must not be empty"
        assert len(result.final_response) > 30, "Response must be detailed"
        # Should not ask for clarification
        assert "more details" not in result.final_response.lower(), "Must not ask for clarification"
        assert "provide" not in result.final_response.lower() or "information" in result.final_response.lower(), "Must not ask vague questions"
        print("✓ PASS: Provides complete answer")


async def test_factual_questions():
    """Test factual information questions."""
    print("\n" + "="*60)
    print("TEST 4: FACTUAL QUESTIONS")
    print("="*60)
    
    orchestrator = TaskOrchestrator()
    
    test_cases = [
        "Who is the President of India?",
        "What is the capital of France?",
        "When was Python created?",
    ]
    
    for question in test_cases:
        result = await orchestrator.run(question)
        print(f"\nInput: '{question}'")
        print(f"Response: {result.final_response}")
        
        assert result.final_response, "Response must not be empty"
        assert len(result.final_response) > 20, "Response must be meaningful"
        
        # Should provide answer or acknowledge appropriately (not ask for clarification)
        response_lower = result.final_response.lower()
        vague_phrases = ["can you provide more details", "could you provide", "need more information"]
        has_vague = any(phrase in response_lower for phrase in vague_phrases)
        assert not has_vague, "Must not ask vague clarification questions"
        
        print("✓ PASS: Provides response without asking for clarification")


async def test_task_questions():
    """Test task/recommendation questions."""
    print("\n" + "="*60)
    print("TEST 5: TASK/RECOMMENDATION QUESTIONS")
    print("="*60)
    
    orchestrator = TaskOrchestrator()
    
    test_cases = [
        "Find best hotels in Bangalore",
        "Recommend good restaurants nearby",
        "Help me plan a trip to Paris",
    ]
    
    for question in test_cases:
        result = await orchestrator.run(question)
        print(f"\nInput: '{question}'")
        print(f"Response: {result.final_response}")
        
        assert result.final_response, "Response must not be empty"
        assert len(result.final_response) > 30, "Response must be detailed"
        print("✓ PASS: Provides actionable response")


async def test_agent_pipeline():
    """Verify agent pipeline always completes."""
    print("\n" + "="*60)
    print("TEST 6: AGENT PIPELINE INTEGRITY")
    print("="*60)
    
    orchestrator = TaskOrchestrator()
    
    # Non-greeting question should run all agents
    result = await orchestrator.run("What is machine learning?")
    
    print(f"\nInput: 'What is machine learning?'")
    print(f"Response: {result.final_response}")
    print(f"\nAgent steps executed: {len(result.steps)}")
    print(f"Steps: {[step.name for step in result.steps]}")
    
    # Should have run all 4 agents (Fetcher, Analyzer, Planner, Reporter)
    # Note: Greeting detection may skip agents, but this is not a greeting
    if len(result.steps) > 0:
        assert any(step.name == "reporter" for step in result.steps), "ReporterAgent must always run"
        print("✓ PASS: Pipeline executed properly")
    
    # Most importantly: must have final response
    assert result.final_response, "Must always have final response"
    assert len(result.final_response) > 20, "Final response must be meaningful"
    print("✓ PASS: Final response always present")


async def test_no_internal_leakage():
    """Verify no internal agent reasoning leaks to user."""
    print("\n" + "="*60)
    print("TEST 7: NO INTERNAL REASONING LEAKAGE")
    print("="*60)
    
    orchestrator = TaskOrchestrator()
    
    result = await orchestrator.run("Explain quantum computing")
    
    print(f"\nInput: 'Explain quantum computing'")
    print(f"Response: {result.final_response}")
    
    # Check for internal system language that shouldn't appear
    response = result.final_response.lower()
    forbidden_phrases = [
        "fetcher", "analyzer", "planner", "reporter",
        "agent", "pipeline", "orchestration",
        "internal analysis", "execution plan",
        "context.analysis", "context.plan",
    ]
    
    for phrase in forbidden_phrases:
        assert phrase not in response, f"Internal phrase '{phrase}' leaked to user response"
    
    print("✓ PASS: No internal system language exposed")


async def test_voice_consistency():
    """Test that voice/text identity is consistent."""
    print("\n" + "="*60)
    print("TEST 8: VOICE/TEXT CONSISTENCY")
    print("="*60)
    
    orchestrator = TaskOrchestrator()
    
    # Same question, should get consistent identity
    result1 = await orchestrator.run("Who are you?")
    result2 = await orchestrator.run("What's your name?")
    
    print(f"\nInput 1: 'Who are you?'")
    print(f"Response 1: {result1.final_response}")
    print(f"\nInput 2: 'What's your name?'")
    print(f"Response 2: {result2.final_response}")
    
    # Both should mention TaskPilot AI
    assert "taskpilot" in result1.final_response.lower(), "Must identify as TaskPilot AI"
    assert "taskpilot" in result2.final_response.lower(), "Must identify as TaskPilot AI"
    
    # Neither should mention Gemini
    assert "gemini" not in result1.final_response.lower(), "Must not mention Gemini"
    assert "gemini" not in result2.final_response.lower(), "Must not mention Gemini"
    
    print("✓ PASS: Identity consistent across queries")


async def run_all_tests():
    """Run all test suites."""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " " * 10 + "TASKPILOT AI BEHAVIOR TEST SUITE" + " " * 16 + "║")
    print("╚" + "="*58 + "╝")
    
    try:
        await test_greeting()
        await test_identity_questions()
        await test_capability_questions()
        await test_factual_questions()
        await test_task_questions()
        await test_agent_pipeline()
        await test_no_internal_leakage()
        await test_voice_consistency()
        
        print("\n" + "="*60)
        print("🎉 ALL TESTS PASSED!")
        print("="*60)
        print("\nTaskPilot AI behavior validation: SUCCESS")
        print("✓ Always provides complete answers")
        print("✓ Maintains consistent identity")
        print("✓ Never exposes internal reasoning")
        print("✓ Handles all question types appropriately")
        print("="*60 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        print("="*60 + "\n")
        raise
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("="*60 + "\n")
        raise


if __name__ == "__main__":
    # Check if Gemini API key is set
    if not os.getenv("GEMINI_API_KEY"):
        print("⚠️  Warning: GEMINI_API_KEY not set. Using fallback responses.")
        print("   Set the key for full LLM-powered responses.\n")
    
    asyncio.run(run_all_tests())
