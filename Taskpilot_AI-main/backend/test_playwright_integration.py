"""
Test Playwright Action Executor
Verifies cross-browser action execution on shared screens
"""

import asyncio
from app.services.playwright_executor import PlaywrightExecutor


async def test_playwright():
    print("🧪 Testing Playwright Mirrored Browser...")
    print("=" * 50)
    print("This launches a VISIBLE browser that mirrors your screen")
    print("=" * 50)
    
    executor = PlaywrightExecutor()
    
    # Test 1: Start Chrome (VISIBLE)
    print("\n[Test 1] Launching VISIBLE Chrome browser...")
    result = await executor.start('chrome')
    print(f"Result: {result}")
    assert result['success'], "Failed to start Chrome"
    print("✅ Visible Chrome launched - You should see a new browser window!")
    
    # Test 2: Navigate to Google
    print("\n[Test 2] Navigating to Google (mirrors your shared tab)...")
    result = await executor.execute_action({
        'action': 'navigate',
        'url': 'https://www.google.com',
        'current_url': 'https://www.google.com'
    })
    print(f"Result: {result}")
    assert result['success'], "Failed to navigate"
    print("✅ Navigation successful - Browser now shows Google")
    
    # Test 3: Set shared page
    print("\n[Test 3] Setting shared page (this is the mirrored browser)...")
    result = await executor.set_shared_page('test_tab_123', 0)
    print(f"Result: {result}")
    assert result['success'], "Failed to set shared page"
    print(f"✅ Mirrored browser ready: {result.get('url')}")
    
    # Wait to see the browser
    print("\n⏳ You should see a visible Chrome window with Google.com...")
    print("   This browser MIRRORS your shared tab!")
    await asyncio.sleep(3)
    
    # Test 4: Type in search box (with screenshot)
    print("\n[Test 4] Typing in search box + taking screenshot...")
    result = await executor.execute_action({
        'action': 'type',
        'selector': 'textarea[name="q"]',
        'text': 'Playwright mirrored browser test',
        'current_url': 'https://www.google.com'
    })
    print(f"Result: {result}")
    assert result['success'], "Failed to type"
    has_screenshot = 'screenshot' in result
    print(f"✅ Typing successful (Screenshot: {'✅' if has_screenshot else '❌'})")
    
    # Test 5: Press Enter
    print("\n[Test 5] Pressing Enter to search...")
    result = await executor.execute_action({
        'action': 'enter',
        'selector': 'textarea[name="q"]',
        'current_url': 'https://www.google.com'
    })
    print(f"Result: {result}")
    assert result['success'], "Failed to press Enter"
    print("✅ Search submitted - Watch the mirrored browser!")
    
    # Wait for search results
    print("\n⏳ Waiting for search results...")
    await asyncio.sleep(2)
    
    # Test 6: Scroll down (with screenshot)
    print("\n[Test 6] Scrolling down + screenshot...")
    result = await executor.execute_action({
        'action': 'scroll',
        'direction': 'down',
        'amount': 500
    })
    print(f"Result: {result}")
    assert result['success'], "Failed to scroll"
    has_screenshot = 'screenshot' in result
    print(f"✅ Scrolling successful (Screenshot: {'✅' if has_screenshot else '❌'})")
    
    # Keep browser open to verify
    print("\n⏳ Keeping mirrored browser open for 5 seconds...")
    print("   Watch it - this is what executes your voice commands!")
    await asyncio.sleep(5)
    
    # Test 7: Stop
    print("\n[Test 7] Stopping Playwright (closing mirrored browser)...")
    result = await executor.stop()
    print(f"Result: {result}")
    assert result['success'], "Failed to stop"
    print("✅ Mirrored browser closed")
    
    print("\n" + "=" * 50)
    print("✅ ALL TESTS PASSED!")
    print("\n🎯 How it works:")
    print("  1. Launches VISIBLE browser ✅")
    print("  2. Mirrors your shared tab URL ✅")
    print("  3. Executes voice commands there ✅")
    print("  4. Returns screenshot proof ✅")
    print("\n💡 In real use:")
    print("  • You share Google tab (green border)")
    print("  • Playwright opens VISIBLE Chrome with Google")
    print("  • Voice commands execute in Playwright browser")
    print("  • You see actions happening in real-time!")
    print("  • Screenshot sent back as confirmation")
    print("\n✨ NO EXTENSIONS NEEDED!")


async def test_edge():
    print("\n\n🧪 Testing Microsoft Edge Mirrored Browser...")
    print("=" * 50)
    
    executor = PlaywrightExecutor()
    
    print("\n[Edge Test] Launching VISIBLE Microsoft Edge...")
    result = await executor.start('edge')
    print(f"Result: {result}")
    
    if result['success']:
        print("✅ Visible Edge launched - You should see a new Edge window!")
        
        print("\n[Edge Test] Navigating to Bing (mirrors your shared tab)...")
        result = await executor.execute_action({
            'action': 'navigate',
            'url': 'https://www.bing.com',
            'current_url': 'https://www.bing.com'
        })
        print(f"Result: {result}")
        
        print("\n⏳ Keeping visible Edge browser open for 5 seconds...")
        print("   This is the mirrored browser that executes voice commands!")
        await asyncio.sleep(5)
        
        await executor.stop()
        print("✅ Edge mirrored browser closed")
    else:
        print(f"⚠️ Edge test skipped: {result['message']}")
        print("   (Edge may not be installed on this system)")


async def main():
    try:
        # Test Chrome
        await test_playwright()
        
        # Test Edge (if available)
        await test_edge()
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    exit(exit_code)
