"""
Playwright Action Executor
Executes browser actions on shared screen in Chrome/Edge/ANY browser.

SUPPORTS:
- Chrome: chromium.launch(channel='chrome')
- Edge:   chromium.launch(channel='msedge')
- CDP:    chromium.connect_over_cdp("ws://localhost:9222")

ACTIONS work on SHARED SCREEN (the one with green border), not active tab!
"""

import asyncio
from typing import Dict, Any, Optional, List
from playwright.async_api import async_playwright, Browser, Page, BrowserContext, Playwright
import logging

logger = logging.getLogger(__name__)


class PlaywrightExecutor:
    """Execute actions on shared browser screen using Playwright"""
    
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.shared_page: Optional[Page] = None  # 🎯 The shared screen page
        self.shared_tab_id: Optional[str] = None
        self.browser_type: str = 'chrome'  # 'chrome', 'edge', or 'firefox'
        self.is_connected: bool = False
        
    async def start(self, browser: str = 'chrome', cdp_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Start Playwright and launch VISIBLE browser that mirrors your screen
        
        Args:
            browser: 'chrome', 'edge', or 'firefox'
            cdp_url: Optional CDP endpoint (IGNORED - we launch new visible browser)
        
        Returns:
            {success: bool, message: str}
        """
        try:
            logger.info(f"🚀 Starting Playwright - Launching VISIBLE {browser} browser")
            
            self.playwright = await async_playwright().start()
            self.browser_type = browser.lower()
            
            # 🎯 ALWAYS launch NEW VISIBLE browser (mirrors your screen)
            if self.browser_type == 'edge':
                logger.info("🌐 Launching VISIBLE Microsoft Edge...")
                self.browser = await self.playwright.chromium.launch(
                    channel='msedge',
                    headless=False  # ⭐ Visible browser
                )
            elif self.browser_type == 'chrome':
                logger.info("🌐 Launching VISIBLE Google Chrome...")
                self.browser = await self.playwright.chromium.launch(
                    channel='chrome',
                    headless=False  # ⭐ Visible browser
                )
            elif self.browser_type == 'firefox':
                logger.info("🦊 Launching VISIBLE Firefox...")
                self.browser = await self.playwright.firefox.launch(
                    headless=False  # ⭐ Visible browser
                )
            else:
                logger.info("🌐 Launching VISIBLE Chromium...")
                self.browser = await self.playwright.chromium.launch(
                    headless=False  # ⭐ Visible browser
                )
            
            # Create context
            self.context = await self.browser.new_context()
            self.is_connected = True
            
            logger.info(f"✅ Visible {browser} browser launched - Ready to mirror your screen")
            return {
                'success': True,
                'message': f'Visible {browser} launched',
                'browser': self.browser_type
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to start Playwright: {e}")
            return {
                'success': False,
                'message': f'Failed to connect: {str(e)}'
            }
    
    async def set_shared_page(self, tab_id: str, page_index: int = 0) -> Dict[str, Any]:
        """
        Set which page is the shared screen (the one with green border)
        
        Args:
            tab_id: Unique ID for the shared tab
            page_index: Index of the page to control (0 = first page)
        
        Returns:
            {success: bool, message: str}
        """
        try:
            if not self.context:
                return {'success': False, 'message': 'Browser not connected'}
            
            pages = self.context.pages
            if not pages or page_index >= len(pages):
                # Create new page if needed
                self.shared_page = await self.context.new_page()
                logger.info(f"📄 Created new page as shared screen")
            else:
                self.shared_page = pages[page_index]
            
            self.shared_tab_id = tab_id
            
            logger.info(f"🎯 SHARED SCREEN LOCKED: {tab_id}")
            logger.info(f"   Actions will execute on THIS page (page index: {page_index})")
            
            return {
                'success': True,
                'message': f'Shared screen set to page {page_index}',
                'tabId': tab_id,
                'url': self.shared_page.url
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to set shared page: {e}")
            return {'success': False, 'message': str(e)}
    
    async def get_shared_page(self) -> Optional[Page]:
        """Get the shared screen page (the one with green border)"""
        if not self.shared_page:
            # Fallback to first page if shared page not set
            if self.context and self.context.pages:
                self.shared_page = self.context.pages[0]
                logger.warning("⚠️ Using first page as shared screen (not explicitly set)")
        return self.shared_page
    
    async def execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute action on MIRRORED browser (matches your shared screen URL)
        
        Args:
            action: {
                'action': 'click' | 'type' | 'scroll' | 'enter' | 'search' | 'navigate',
                'selector': CSS selector (for click/type/enter),
                'text': Text to type (for type/search),
                'direction': 'up' | 'down' (for scroll),
                'url': URL (for navigate),
                'current_url': Current URL of shared tab (to mirror)
            }
        
        Returns:
            {success: bool, message: str, data?: any, screenshot?: base64}
        """
        try:
            page = await self.get_shared_page()
            if not page:
                return {'success': False, 'message': 'No shared page available'}
            
            # 🎯 Mirror the shared tab URL
            current_url = action.get('current_url')
            if current_url and page.url != current_url:
                logger.info(f"🔄 Mirroring shared tab URL: {current_url}")
                await page.goto(current_url, wait_until='domcontentloaded')
                # Give page a moment to load
                await page.wait_for_timeout(500)
            
            action_type = action.get('action', '').lower()
            logger.info(f"🎯 Executing '{action_type}' on MIRRORED browser")
            
            result = await self._execute_action_internal(page, action)
            
            # 📸 Take screenshot as proof
            try:
                screenshot_bytes = await page.screenshot()
                import base64
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                result['screenshot'] = screenshot_b64
                logger.info(f"📸 Screenshot captured ({len(screenshot_bytes)} bytes)")
            except Exception as e:
                logger.warning(f"⚠️ Could not capture screenshot: {e}")
            
            if result.get('success'):
                logger.info(f"✅ Action '{action_type}' completed on mirrored browser")
            else:
                logger.error(f"❌ Action '{action_type}' failed: {result.get('message')}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Action execution failed: {e}")
            return {
                'success': False,
                'message': f'Action failed: {str(e)}'
            }
    
    async def _execute_action_internal(self, page: Page, action: Dict[str, Any]) -> Dict[str, Any]:
        """Internal action execution logic"""
        action_type = action.get('action', '').lower()
        
        try:
            if action_type == 'click':
                selector = action.get('selector') or action.get('target')
                if not selector:
                    return {'success': False, 'message': 'No selector provided'}
                
                # Try to find element by text if selector fails
                try:
                    await page.click(selector, timeout=3000)
                except:
                    # Try as text content
                    await page.get_by_text(selector).click(timeout=3000)
                
                return {'success': True, 'message': f'Clicked: {selector}'}
            
            elif action_type == 'type':
                selector = action.get('selector')
                text = action.get('text', '')
                
                if selector:
                    await page.fill(selector, text)
                else:
                    # Type in focused element
                    await page.keyboard.type(text)
                
                return {'success': True, 'message': f'Typed: {text[:50]}...'}
            
            elif action_type == 'scroll':
                direction = action.get('direction', 'down')
                amount = action.get('amount', 500)
                
                scroll_y = amount if direction == 'down' else -amount
                await page.evaluate(f"window.scrollBy(0, {scroll_y})")
                
                return {'success': True, 'message': f'Scrolled {direction} {amount}px'}
            
            elif action_type == 'enter':
                selector = action.get('selector')
                
                if selector:
                    await page.press(selector, 'Enter')
                else:
                    await page.keyboard.press('Enter')
                
                return {'success': True, 'message': 'Pressed Enter'}
            
            elif action_type == 'search':
                selector = action.get('selector')
                text = action.get('text', '')
                
                if not selector:
                    return {'success': False, 'message': 'No selector for search'}
                
                # Type text and press Enter
                await page.fill(selector, text)
                await page.press(selector, 'Enter')
                
                return {'success': True, 'message': f'Searched: {text}'}
            
            elif action_type == 'navigate':
                url = action.get('url')
                if not url:
                    return {'success': False, 'message': 'No URL provided'}
                
                await page.goto(url)
                return {'success': True, 'message': f'Navigated to: {url}'}
            
            elif action_type == 'get_text':
                # Get visible text from page
                text = await page.evaluate("document.body.innerText")
                return {
                    'success': True,
                    'message': 'Retrieved page text',
                    'data': text[:5000]  # Limit to 5000 chars
                }
            
            elif action_type == 'screenshot':
                # Take screenshot of shared screen
                screenshot = await page.screenshot()
                return {
                    'success': True,
                    'message': 'Screenshot captured',
                    'data': screenshot
                }
            
            else:
                return {'success': False, 'message': f'Unknown action: {action_type}'}
                
        except Exception as e:
            return {'success': False, 'message': f'Action failed: {str(e)}'}
    
    async def stop(self) -> Dict[str, Any]:
        """Stop Playwright and close browser"""
        try:
            logger.info("🔴 Stopping Playwright...")
            
            if self.browser:
                await self.browser.close()
            
            if self.playwright:
                await self.playwright.stop()
            
            self.is_connected = False
            self.shared_page = None
            self.shared_tab_id = None
            
            logger.info("✅ Playwright stopped")
            return {'success': True, 'message': 'Playwright stopped'}
            
        except Exception as e:
            logger.error(f"❌ Failed to stop Playwright: {e}")
            return {'success': False, 'message': str(e)}


# Global executor instance
_executor: Optional[PlaywrightExecutor] = None


async def get_executor() -> PlaywrightExecutor:
    """Get or create global Playwright executor"""
    global _executor
    if _executor is None:
        _executor = PlaywrightExecutor()
    return _executor


async def cleanup_executor():
    """Cleanup global executor"""
    global _executor
    if _executor:
        await _executor.stop()
        _executor = None
