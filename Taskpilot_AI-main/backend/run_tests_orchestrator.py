import asyncio
import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.orchestrator import TaskOrchestrator
from app.services.chat_preprocessor import classify_query, greeting_reply, is_instant_greeting

async def test_query(orchestrator, query_text):
    print("=" * 80)
    print(f"TESTING QUERY: {query_text}")
    
    if is_instant_greeting(query_text):
        print(f"ROUTING: Instant Greeting")
        print(f"RESPONSE: {greeting_reply()}")
        return

    routing = classify_query(query_text)
    print(f"ROUTING DECISION: {routing}")
    
    result = await orchestrator.run(
        user_input=query_text,
        screen_context=None,
        attachments=None,
        conversation_history=[],
        routing_hint=routing
    )
    
    print("-" * 40)
    if result.final_response:
        print("RESPONSE (final_response):")
        print(result.final_response)
    elif result.structured:
        print(f"RESPONSE (structured - {result.structured.get('type')}):")
        for k, v in result.structured.items():
            if k not in ['type', 'raw_data'] and v:
                print(f"[{k.upper()}]:\n{v}")
    elif result.summary:
        print("RESPONSE (summary):")
        print(result.summary)
    
    print("\nAGENT STEPS:")
    for step in result.steps:
        print(f"  - [{step.name}] {step.status}: {step.output}")
    print("=" * 80 + "\n")

async def main():
    if not os.getenv("GEMINI_API_KEY") and not os.getenv("GEMINI_API_KEY", ""):
        # Fallback for local testing to read .env
        from dotenv import load_dotenv
        load_dotenv(".env")
        
    orchestrator = TaskOrchestrator()
    
    queries = [
        "hello",
        "who is the current prime minister of India",
        "what are the cheapest hotels in bangalore?",
        "what is the time and weather in mumbai right now?",
        "what is the latest news about AI and trading?",
        "what is the meaning of machine learning?"
    ]
    
    for q in queries:
        await test_query(orchestrator, q)

if __name__ == "__main__":
    asyncio.run(main())
