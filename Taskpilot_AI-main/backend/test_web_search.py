"""Quick test to verify web search is working."""
import asyncio
from app.services.agents.fetcher import FetcherAgent
from app.services.agents.base import AgentContext


async def test_web_search():
    print("Testing DuckDuckGo web search...")
    
    fetcher = FetcherAgent()
    context = AgentContext(user_input="Who is the President of India")
    
    result = await fetcher.run(context)
    
    print("\n" + "="*60)
    print("FETCH RESULT:")
    print("="*60)
    print(result.output[:500])
    print("\n" + "="*60)
    
    if "DuckDuckGo search not available" in result.output:
        print("❌ Web search is NOT working")
        return False
    elif len(context.fetched_context or "") > 100:
        print("✅ Web search is working!")
        return True
    else:
        print("⚠️ Web search incomplete")
        return False


if __name__ == "__main__":
    asyncio.run(test_web_search())
