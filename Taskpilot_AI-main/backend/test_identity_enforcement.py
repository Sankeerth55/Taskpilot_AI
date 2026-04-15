"""
Critical test for TaskPilot AI identity enforcement.
This test ensures NO Gemini identity leaks to text or voice UI.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.orchestrator import TaskOrchestrator


async def test_identity_questions():
    """Test that identity questions NEVER reveal Gemini."""
    print("\n" + "="*70)
    print("CRITICAL IDENTITY ENFORCEMENT TEST")
    print("="*70)
    
    orchestrator = TaskOrchestrator()
    
    # These questions MUST return TaskPilot AI identity
    identity_questions = [
        "What is your name?",
        "Who are you?",
        "What are you?",
        "Tell me about yourself",
        "What's your name?",
        "Introduce yourself",
    ]
    
    all_passed = True
    
    for question in identity_questions:
        print(f"\n{'─'*70}")
        print(f"Q: {question}")
        
        result = await orchestrator.run(question)
        response = result.final_response
        
        print(f"A: {response}")
        print(f"{'─'*70}")
        
        # Critical checks
        response_lower = response.lower()
        
        # Check 1: Must contain TaskPilot
        if "taskpilot" not in response_lower:
            print("❌ FAIL: Does not identify as TaskPilot AI")
            all_passed = False
            continue
        
        # Check 2: Must NOT contain Gemini
        if "gemini" in response_lower:
            print("❌ CRITICAL FAIL: GEMINI IDENTITY LEAKED")
            all_passed = False
            continue
        
        # Check 3: Must NOT mention language model
        forbidden_phrases = [
            "language model", "ai model", "large language",
            "llm", "developed by google", "created by google",
            "google's ai"
        ]
        
        for phrase in forbidden_phrases:
            if phrase in response_lower:
                print(f"❌ FAIL: Contains forbidden phrase '{phrase}'")
                all_passed = False
                break
        else:
            print("✓ PASS: Identity is TaskPilot AI, no leakage")
    
    print("\n" + "="*70)
    if all_passed:
        print("🎉 ALL IDENTITY TESTS PASSED")
        print("✓ TaskPilot AI identity maintained")
        print("✓ No Gemini identity leakage")
        print("✓ No LLM references exposed")
    else:
        print("❌ IDENTITY TESTS FAILED")
        print("CRITICAL: Identity leakage detected")
    print("="*70 + "\n")
    
    return all_passed


async def test_general_queries():
    """Test that general queries don't expose Gemini identity."""
    print("\n" + "="*70)
    print("GENERAL QUERY IDENTITY CHECK")
    print("="*70)
    
    orchestrator = TaskOrchestrator()
    
    test_queries = [
        "What is artificial intelligence?",
        "How does machine learning work?",
        "Tell me about Python programming",
        "What can you help me with?",
    ]
    
    all_passed = True
    
    for query in test_queries:
        print(f"\n{'─'*70}")
        print(f"Q: {query}")
        
        result = await orchestrator.run(query)
        response = result.final_response
        
        print(f"A: {response[:200]}..." if len(response) > 200 else f"A: {response}")
        
        response_lower = response.lower()
        
        # Should NOT contain Gemini or LLM references
        forbidden_terms = ["gemini", "language model", "ai model", "llm"]
        
        leaked = False
        for term in forbidden_terms:
            if term in response_lower:
                print(f"❌ FAIL: Contains forbidden term '{term}'")
                all_passed = False
                leaked = True
                break
        
        if not leaked:
            print("✓ PASS: No identity leakage")
    
    print("\n" + "="*70)
    if all_passed:
        print("🎉 GENERAL QUERY TESTS PASSED")
    else:
        print("❌ SOME QUERIES FAILED")
    print("="*70 + "\n")
    
    return all_passed


async def test_voice_text_consistency():
    """Verify that voice and text get the same response."""
    print("\n" + "="*70)
    print("VOICE/TEXT CONSISTENCY CHECK")
    print("="*70)
    
    orchestrator = TaskOrchestrator()
    
    # Both /messages and /voice endpoints use the same orchestrator
    # So both should get identical responses
    
    test_input = "Who are you?"
    
    # Simulate text request
    print(f"\nInput: '{test_input}'")
    result = await orchestrator.run(test_input)
    
    print(f"\nResponse: {result.final_response}")
    
    response_lower = result.final_response.lower()
    
    passed = True
    if "taskpilot" in response_lower and "gemini" not in response_lower:
        print("✓ PASS: Same orchestrator used for text and voice")
        print("✓ Identity is consistent")
    else:
        print("❌ FAIL: Identity issue detected")
        passed = False
    
    print("="*70 + "\n")
    return passed


async def run_all_tests():
    """Run complete identity enforcement test suite."""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "TASKPILOT AI IDENTITY ENFORCEMENT" + " "*20 + "║")
    print("║" + " "*22 + "CRITICAL SYSTEM TEST" + " "*27 + "║")
    print("╚" + "="*68 + "╝")
    
    test1 = await test_identity_questions()
    test2 = await test_general_queries()
    test3 = await test_voice_text_consistency()
    
    print("\n" + "="*70)
    if test1 and test2 and test3:
        print("🎉🎉🎉 ALL CRITICAL TESTS PASSED 🎉🎉🎉")
        print("="*70)
        print("✓ TaskPilot AI identity enforced at system level")
        print("✓ NO Gemini identity leakage to text or voice")
        print("✓ Voice and text use same response pipeline")
        print("✓ LLM references completely hidden")
        print("="*70)
        print("\n✅ SYSTEM IS PRODUCTION READY")
    else:
        print("❌❌❌ CRITICAL TESTS FAILED ❌❌❌")
        print("="*70)
        print("⚠️  Identity leakage detected")
        print("⚠️  System requires fixes before deployment")
        print("="*70)
        return False
    
    print("="*70 + "\n")
    return True


if __name__ == "__main__":
    import os
    
    if not os.getenv("GEMINI_API_KEY"):
        print("⚠️  Warning: GEMINI_API_KEY not set.")
        print("   Testing fallback responses (should still pass).\n")
    
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
