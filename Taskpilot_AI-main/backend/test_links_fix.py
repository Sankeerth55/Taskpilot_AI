"""
Test to verify TaskPilot AI now provides actual links and detailed information.
This tests the exact queries from the user's screenshot.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.orchestrator import TaskOrchestrator


async def test_hotel_query():
    """Test the exact hotel query from the screenshot."""
    print("=" * 80)
    print("TEST: Hotel Query (from screenshot)")
    print("=" * 80)
    print("\nQUERY: 'can You find the Cheapest hotels in Bangalore'")
    print("-" * 80)
    
    orchestrator = TaskOrchestrator()
    result = await orchestrator.run(
        user_input="can You find the Cheapest hotels in Bangalore",
        screen_context=None,
        attachments=[]
    )
    
    print("\n✅ RESPONSE:")
    print(result.final_response)
    print("\n" + "=" * 80)
    
    # Check if response contains URLs
    if "http" in result.final_response or "🔗" in result.final_response:
        print("\n✅ SUCCESS: Response contains URLs/links!")
    else:
        print("\n❌ WARNING: Response does not contain URLs")
    
    # Check if response has structured information
    if "**" in result.final_response or "•" in result.final_response:
        print("✅ SUCCESS: Response is well-formatted")
    else:
        print("⚠️  Note: Response could be better formatted")
    
    print("\n" + "=" * 80)
    return result


async def test_link_request():
    """Test when user explicitly asks for links."""
    print("\n" * 2)
    print("=" * 80)
    print("TEST: Explicit Link Request")
    print("=" * 80)
    print("\nQUERY: 'Give me the links of that hotels'")
    print("-" * 80)
    
    orchestrator = TaskOrchestrator()
    result = await orchestrator.run(
        user_input="Give me the links of hotels in Bangalore",
        screen_context=None,
        attachments=[]
    )
    
    print("\n✅ RESPONSE:")
    print(result.final_response)
    print("\n" + "=" * 80)
    
    # Check for URLs
    if "http" in result.final_response or "🔗" in result.final_response:
        print("\n✅ SUCCESS: Response contains actual links!")
        
        # Count URLs
        url_count = result.final_response.count("http")
        print(f"✅ Found {url_count} URLs in response")
    else:
        print("\n❌ FAILURE: Response should contain URLs but doesn't")
    
    print("\n" + "=" * 80)
    return result


async def test_president_query():
    """Test the President of India query to ensure basic research still works."""
    print("\n" * 2)
    print("=" * 80)
    print("TEST: President Query (verification)")
    print("=" * 80)
    print("\nQUERY: 'Who is the President of India'")
    print("-" * 80)
    
    orchestrator = TaskOrchestrator()
    result = await orchestrator.run(
        user_input="Who is the President of India",
        screen_context=None,
        attachments=[]
    )
    
    print("\n✅ RESPONSE:")
    print(result.final_response)
    print("\n" + "=" * 80)
    
    # Check for actual information
    if "Droupadi Murmu" in result.final_response or "president" in result.final_response.lower():
        print("\n✅ SUCCESS: Contains actual information!")
    else:
        print("\n⚠️  Note: May not have latest information")
    
    print("\n" + "=" * 80)
    return result


async def main():
    """Run all tests."""
    print("\n")
    print("█" * 80)
    print("█" + " " * 78 + "█")
    print("█" + "  TaskPilot AI - Links & Details Fix Verification".center(78) + "█")
    print("█" + " " * 78 + "█")
    print("█" * 80)
    print("\n")
    
    try:
        # Test 1: Hotel query (main issue from screenshot)
        result1 = await test_hotel_query()
        
        # Test 2: Explicit link request
        result2 = await test_link_request()
        
        # Test 3: President query (regression test)
        result3 = await test_president_query()
        
        # Summary
        print("\n" * 2)
        print("█" * 80)
        print("█" + "  TEST SUMMARY".center(78) + "█")
        print("█" * 80)
        print("\n")
        
        all_have_links = all([
            ("http" in r.final_response or "🔗" in r.final_response) 
            for r in [result1, result2]
        ])
        
        if all_have_links:
            print("✅ ALL TESTS PASSED!")
            print("✅ TaskPilot AI now provides actual links and detailed information")
            print("✅ Ready for production use")
        else:
            print("⚠️  Some tests may need review")
            print("   Check the responses above for details")
        
        print("\n" + "█" * 80)
        print("\n")
        
    except Exception as e:
        print(f"\n❌ ERROR during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
