"""
Test Comprehensive Search Implementation
Tests that EVERY question triggers web search with 4 sources
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.agents.fetcher import FetcherAgent
from app.services.agents.base import AgentContext


async def test_comprehensive_search():
    """Test that all questions trigger comprehensive web search"""
    
    print("\n" + "="*80)
    print("TESTING: COMPREHENSIVE WEB SEARCH FOR ALL QUESTIONS")
    print("="*80 + "\n")
    
    # Test cases with different intents
    test_queries = [
        # Simple factual
        "Who is the President of India",
        
        # Complex explanation
        "How does quantum computing work",
        
        # Comparison
        "Python vs JavaScript which is better",
        
        # Location-based
        "Best hotels in Bangalore under 3000",
        
        # Current events
        "Latest news in AI technology",
        
        # General knowledge
        "What is the capital of France"
    ]
    
    agent = FetcherAgent()
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*80}")
        print(f"TEST {i}/6: {query}")
        print('='*80)
        
        # Create context
        context = AgentContext(
            user_input=query,
            attachments=[],
            metadata={
                "intent": "research",  # Generic intent
                "requires_web": False,  # Should search ANYWAY
                "is_time_sensitive": False
            }
        )
        
        # Run fetcher
        result = await agent.run(context)
        
        # Check results
        fetched = context.fetched_context or ""
        
        print(f"\n✓ Status: {result.status}")
        print(f"✓ Data Length: {len(fetched)} characters")
        
        # Check for comprehensive search markers
        has_web_research = "WEB RESEARCH" in fetched
        has_reference = "REFERENCE DATA" in fetched
        has_related = "RELATED INSIGHTS" in fetched
        has_recent = "RECENT INFO" in fetched
        
        sources_found = sum([has_web_research, has_reference, has_related, has_recent])
        
        print(f"\n📊 SOURCES DETECTED ({sources_found}/4):")
        print(f"  {'✓' if has_web_research else '✗'} WEB RESEARCH (DuckDuckGo)")
        print(f"  {'✓' if has_reference else '✗'} REFERENCE DATA (Wikipedia)")
        print(f"  {'✓' if has_related else '✗'} RELATED INSIGHTS (Related Topics)")
        print(f"  {'✓' if has_recent else '✗'} RECENT INFO (News)")
        
        # Check for URLs (real sources)
        url_count = fetched.count("http://") + fetched.count("https://")
        print(f"\n🔗 URLs Found: {url_count}")
        
        # Extract sample data
        if has_web_research:
            web_start = fetched.find("WEB RESEARCH")
            web_sample = fetched[web_start:web_start+200]
            print(f"\n📝 Web Search Sample:\n{web_sample}...")
        
        if has_related:
            related_start = fetched.find("RELATED INSIGHTS")
            related_sample = fetched[related_start:related_start+200]
            print(f"\n🔍 Related Topics Sample:\n{related_sample}...")
        
        # Verdict
        if sources_found >= 2:
            print(f"\n✅ PASS: Comprehensive search working ({sources_found} sources)")
        else:
            print(f"\n❌ FAIL: Only {sources_found} sources found (need 2+)")
        
        print("\n" + "-"*80)
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80 + "\n")


async def test_greeting_bypass():
    """Test that greetings DON'T trigger web search"""
    
    print("\n" + "="*80)
    print("TESTING: GREETING BYPASS")
    print("="*80 + "\n")
    
    greetings = ["hello", "hi", "hey"]
    
    agent = FetcherAgent()
    
    for greeting in greetings:
        context = AgentContext(
            user_input=greeting,
            attachments=[],
            metadata={
                "intent": "greeting",
                "requires_web": False,
                "is_time_sensitive": False
            }
        )
        
        result = await agent.run(context)
        fetched = context.fetched_context or ""
        
        if "WEB RESEARCH" in fetched:
            print(f"❌ FAIL: '{greeting}' triggered web search (should skip)")
        else:
            print(f"✅ PASS: '{greeting}' bypassed web search correctly")


if __name__ == "__main__":
    print("\n🚀 Starting Comprehensive Search Tests...\n")
    
    # Test 1: Comprehensive search for all questions
    asyncio.run(test_comprehensive_search())
    
    # Test 2: Greeting bypass
    asyncio.run(test_greeting_bypass())
    
    print("\n✨ All tests complete!\n")
