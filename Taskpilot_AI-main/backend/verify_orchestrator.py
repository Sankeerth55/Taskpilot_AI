import asyncio
import os
import sys
import logging

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.services.orchestrator import TaskOrchestrator

logging.basicConfig(level=logging.INFO)

async def test_orchestrator():
    print("--- STARTING ORCHESTRATOR VERIFICATION ---")
    orchestrator = TaskOrchestrator()
    
    test_cases = [
        {
            "input": "Who is the CEO of Google?",
            "expected_decision": "needs_data=True (or False if it knows, but likely True for facts)",
            "desc": "Simple Factual"
        },
        {
            "input": "Hello, how are you?",
            "expected_decision": "needs_data=False",
            "desc": "Greeting"
        },
        {
            "input": "Compare the iPhone 15 Pro and Galaxy S24 Ultra prices.",
            "expected_decision": "needs_data=True",
            "desc": "Complex Comparison"
        }
    ]
    
    for test in test_cases:
        print(f"\n\nTest Case: {test['desc']}")
        print(f"Input: {test['input']}")
        try:
            result = await orchestrator.run(test['input'])
            print(f"Summary: {result.summary}")
            print(f"Deep Structure (Decision): {result.structured.get('decision')}")
            print(f"Final Response: {result.final_response[:150]}...")
            
            # Validation logic
            decision = result.structured.get('decision', {})
            needs_data = decision.get('needs_data')
            print(f"Needs Data: {needs_data}")
            
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_orchestrator())
