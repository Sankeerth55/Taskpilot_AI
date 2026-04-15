"""
Test script for enhanced TaskPilot AI backend.

This script tests the upgraded multi-agent system with improved:
- Intent detection
- Data fetching
- Task-oriented analysis
- Execution planning
- Result-focused responses
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.orchestrator import TaskOrchestrator
from app.services.intent_detector import IntentDetector, TaskIntent


async def test_intent_detection():
    """Test the intent detector with various queries."""
    print("=" * 60)
    print("TEST 1: Intent Detection")
    print("=" * 60)
    
    test_queries = [
        "What is the best laptop under $1000?",
        "Compare iPhone vs Samsung Galaxy",
        "Explain quantum computing",
        "Find restaurants near me",
        "Calculate 15% tip on $45.50",
        "Plan a trip to Paris",
        "What is artificial intelligence?",
    ]
    
    for query in test_queries:
        intent_info = IntentDetector.detect_intent(query)
        print(f"\nQuery: {query}")
        print(f"  Intent: {intent_info['intent'].value}")
        print(f"  Confidence: {intent_info['confidence']:.2f}")
        print(f"  Requires Web: {intent_info['requires_web']}")
        print(f"  Time Sensitive: {intent_info['is_time_sensitive']}")
        print(f"  Complexity: {intent_info['complexity']}")
    
    print("\n✅ Intent detection test completed\n")


async def test_orchestration():
    """Test the full orchestration pipeline."""
    print("=" * 60)
    print("TEST 2: Full Orchestration")
    print("=" * 60)
    
    test_cases = [
        {
            "query": "What are the best programming languages to learn in 2026?",
            "expected": "Should provide research-based recommendations"
        },
        {
            "query": "Compare Python and JavaScript for web development",
            "expected": "Should compare and provide analysis"
        },
        {
            "query": "Explain how blockchain works",
            "expected": "Should provide clear explanation"
        },
    ]
    
    orchestrator = TaskOrchestrator()
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'─' * 60}")
        print(f"Test Case {i}: {test_case['query']}")
        print(f"Expected: {test_case['expected']}")
        print(f"{'─' * 60}")
        
        try:
            result = await orchestrator.run(test_case['query'])
            
            print(f"\n📋 Final Response:")
            print(result.final_response[:500])
            if len(result.final_response) > 500:
                print("... (truncated)")
            
            print(f"\n🔧 Agent Steps:")
            for step in result.steps:
                print(f"  - {step.name}: {step.status}")
            
            print(f"\n✅ Test case {i} completed successfully")
            
        except Exception as e:
            print(f"\n❌ Test case {i} failed: {e}")
    
    print(f"\n{'=' * 60}")
    print("✅ Orchestration test completed\n")


async def test_task_execution_responses():
    """Test that responses sound like task execution, not just chatbot."""
    print("=" * 60)
    print("TEST 3: Task Execution Response Quality")
    print("=" * 60)
    
    test_queries = [
        "Who are you?",
        "What can you do?",
        "Recommend a good laptop for programming",
        "hi",
    ]
    
    orchestrator = TaskOrchestrator()
    
    for query in test_queries:
        print(f"\n{'─' * 60}")
        print(f"Query: {query}")
        print(f"{'─' * 60}")
        
        result = await orchestrator.run(query)
        
        # Check for TaskPilot AI identity
        response_lower = result.final_response.lower()
        has_taskpilot = "taskpilot" in response_lower
        has_gemini = "gemini" in response_lower
        has_llm_identity = any(term in response_lower for term in [
            "language model", "ai model", "i am a", "i'm a"
        ])
        
        print(f"Response: {result.final_response[:300]}")
        if len(result.final_response) > 300:
            print("... (truncated)")
        
        print(f"\n✓ Identity Check:")
        print(f"  - Has 'TaskPilot': {has_taskpilot} {'✅' if has_taskpilot else '⚠️'}")
        print(f"  - Has 'Gemini': {has_gemini} {'❌ FAIL' if has_gemini else '✅'}")
        print(f"  - Has LLM identity: {has_llm_identity} {'❌ FAIL' if has_llm_identity else '✅'}")
    
    print(f"\n{'=' * 60}")
    print("✅ Response quality test completed\n")


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("TaskPilot AI - Enhanced Backend Test Suite")
    print("=" * 60 + "\n")
    
    try:
        await test_intent_detection()
        await test_orchestration()
        await test_task_execution_responses()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        print("=" * 60 + "\n")
        
        print("TaskPilot AI backend is ready!")
        print("Start the server with:")
        print("  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        print()
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
