"""
WebSocket endpoint for real-time browser action execution via Playwright
Supports Chrome, Edge, and any browser with green border indicating shared screen
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Any
import json
import logging

from app.services.playwright_executor import get_executor, cleanup_executor

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections"""
    
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"🔌 WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"🔌 WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_message(self, websocket: WebSocket, message: Dict[str, Any]):
        await websocket.send_json(message)


manager = ConnectionManager()


@router.websocket("/ws/actions")
async def websocket_action_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for browser action execution
    
    Message Format:
    {
        "type": "START" | "STOP" | "ACTION" | "SET_SHARED_TAB",
        "browser": "chrome" | "edge" | "firefox",
        "cdpUrl": "ws://localhost:9222" (optional),
        "tabId": "shared_tab_123",
        "action": {
            "action": "click" | "type" | "scroll" | "enter" | "search",
            "selector": "#search-box",
            "text": "search query",
            "direction": "up" | "down",
            "amount": 500
        }
    }
    """
    await manager.connect(websocket)
    executor = await get_executor()
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            msg_type = message.get('type', '').upper()
            logger.info(f"📨 Received message: {msg_type}")
            
            response = await handle_message(executor, message)
            
            # Send response back
            await manager.send_message(websocket, response)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("🔌 Client disconnected")
    
    except Exception as e:
        logger.error(f"❌ WebSocket error: {e}")
        try:
            await manager.send_message(websocket, {
                'type': 'ERROR',
                'success': False,
                'message': str(e)
            })
        except:
            pass
        manager.disconnect(websocket)


async def handle_message(executor, message: Dict[str, Any]) -> Dict[str, Any]:
    """Handle different message types"""
    msg_type = message.get('type', '').upper()
    
    try:
        if msg_type == 'START':
            # Start Playwright and connect to browser
            browser = message.get('browser', 'chrome')
            cdp_url = message.get('cdpUrl')
            
            result = await executor.start(browser, cdp_url)
            return {
                'type': 'START_RESPONSE',
                **result
            }
        
        elif msg_type == 'STOP':
            # Stop Playwright
            result = await executor.stop()
            return {
                'type': 'STOP_RESPONSE',
                **result
            }
        
        elif msg_type == 'SET_SHARED_TAB':
            # Set which tab is the shared screen (with green border)
            tab_id = message.get('tabId')
            page_index = message.get('pageIndex', 0)
            
            if not tab_id:
                return {
                    'type': 'SET_SHARED_TAB_RESPONSE',
                    'success': False,
                    'message': 'No tabId provided'
                }
            
            result = await executor.set_shared_page(tab_id, page_index)
            return {
                'type': 'SET_SHARED_TAB_RESPONSE',
                **result
            }
        
        elif msg_type == 'ACTION':
            # Execute action on shared screen
            action = message.get('action', {})
            tab_id = message.get('tabId')
            
            if not action:
                return {
                    'type': 'ACTION_RESPONSE',
                    'success': False,
                    'message': 'No action provided'
                }
            
            # Verify we're controlling the shared tab
            if tab_id and executor.shared_tab_id != tab_id:
                logger.warning(f"⚠️ Tab ID mismatch! Expected {executor.shared_tab_id}, got {tab_id}")
            
            result = await executor.execute_action(action)
            return {
                'type': 'ACTION_RESPONSE',
                'tabId': tab_id,
                **result
            }
        
        elif msg_type == 'PING':
            # Health check
            return {
                'type': 'PONG',
                'success': True,
                'connected': executor.is_connected,
                'browser': executor.browser_type,
                'sharedTabId': executor.shared_tab_id
            }
        
        else:
            return {
                'type': 'ERROR',
                'success': False,
                'message': f'Unknown message type: {msg_type}'
            }
    
    except Exception as e:
        logger.error(f"❌ Error handling message: {e}")
        return {
            'type': 'ERROR',
            'success': False,
            'message': str(e)
        }


@router.get("/actions/status")
async def get_action_status():
    """Get status of Playwright executor"""
    executor = await get_executor()
    
    return {
        'connected': executor.is_connected,
        'browser': executor.browser_type,
        'sharedTabId': executor.shared_tab_id,
        'hasSharedPage': executor.shared_page is not None
    }


@router.post("/actions/start")
async def start_playwright(browser: str = "chrome", cdp_url: str | None = None):
    """Start Playwright connection"""
    executor = await get_executor()
    result = await executor.start(browser, cdp_url)
    return result


@router.post("/actions/stop")
async def stop_playwright():
    """Stop Playwright connection"""
    executor = await get_executor()
    result = await executor.stop()
    return result
