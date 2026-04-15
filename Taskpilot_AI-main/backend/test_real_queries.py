"""Test real-world queries to verify TaskPilot AI works like Perplexity."""
import asyncio
from app.services.orchestrator import TaskOrchestrator


async def test_real_queries():
    """Test the exact queries from the screenshot."""
    orchestrator = TaskOrchestrator()
    
    test_queries = [
        "Who is the President of India",
        "Find the best hotels near Bangalore",
        "What is artificial intelligence",
    ]
    
    for query in test_queries:
        print("\n" + "="*70)
        print(f"QUERY: {query}")
        print("="*70)
        
        result = await orchestrator.run(query)
        
        print(f"\nRESPONSE:\n{result.final_response}")
        print("\n" + "-"*70)


if __name__ == "__main__":
    asyncio.run(test_real_queries())
