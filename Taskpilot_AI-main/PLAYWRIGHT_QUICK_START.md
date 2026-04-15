# 🎭 Playwright Quick Start

## Install & Run (5 minutes)

### 1. **Backend Setup**
```bash
cd backend
setup_playwright.bat   # Windows
# OR
pip install playwright websockets
playwright install chromium msedge
```

### 2. **Start Server**
```bash
python -m uvicorn app.main:app --reload --port 8000
```
Server runs at: `http://localhost:8000`  
WebSocket at: `ws://localhost:8000/api/ws/actions`

### 3. **Test Backend**
```bash
python test_playwright_integration.py
```

---

## Frontend Usage

### **Option A: Console Test**
```javascript
// Open browser console on TaskPilot AI

// 1. Connect to Playwright
await playwrightService.connect();

// 2. Start browser (chrome, edge, or firefox)
await playwrightService.startBrowser('edge');

// 3. Switch to Playwright mode
actionExecutor.setExecutionMode('playwright');

// 4. Test action
await actionExecutor.typeText('Hello from Edge!');

// ✅ Now voice commands use Edge!
```

### **Option B: In LiveAssistant**
```typescript
// Add to LiveAssistant.tsx

import { playwrightService } from '../services/playwrightService';

// When starting session:
const startSession = async (mode: LiveMode) => {
    // ... existing code ...
    
    // Optional: Connect to Playwright
    if (await playwrightService.connect()) {
        await playwrightService.startBrowser('chrome');
        actionExecutor.setExecutionMode('playwright');
        console.log('✅ Using Playwright mode');
    } else {
        console.log('✅ Using Extension mode');
    }
    
    // ... rest of code ...
}
```

---

## Quick Commands

### **Extension Mode** (Default)
```typescript
actionExecutor.setExecutionMode('extension');
await actionExecutor.click('#button');
// → Uses Chrome extension
```

### **Playwright Mode** (Cross-browser)
```typescript
actionExecutor.setExecutionMode('playwright');
await actionExecutor.click('#button');
// → Uses Playwright backend
```

### **Check Status**
```typescript
// Check connection
playwrightService.isConnected(); // true/false

// Get current mode
actionExecutor.getExecutionMode(); // 'extension' or 'playwright'

// Backend status
fetch('http://localhost:8000/api/actions/status')
  .then(r => r.json())
  .then(console.log);
```

---

## Actions Supported

| Action | Code | Extension | Playwright |
|--------|------|-----------|------------|
| **Click** | `actionExecutor.click('#btn')` | ✅ | ✅ |
| **Type** | `actionExecutor.typeText('hello')` | ✅ | ✅ |
| **Scroll** | `actionExecutor.scroll('down', 500)` | ✅ | ✅ |
| **Read Text** | `actionExecutor.getVisibleText()` | ✅ | ✅ |

---

## Browser Support

```typescript
// Chrome
await playwrightService.startBrowser('chrome');

// Microsoft Edge
await playwrightService.startBrowser('edge');

// Firefox
await playwrightService.startBrowser('firefox');
```

---

## Green Border Flow

```
1. User starts screen sharing
   → Chrome shows green border on shared tab

2. Set shared tab in Playwright
   → playwrightService.setSharedTab(tabId, pageIndex)

3. Voice command: "search AI"
   → Gemini calls click/type tools

4. Action execution
   → Playwright executes on SHARED SCREEN (not active tab!)

5. Result
   → Action happens in tab with green border
```

---

## Troubleshooting

### **Backend not starting?**
```bash
# Check Python version
python --version  # Need 3.8+

# Reinstall dependencies
pip install -r requirements.txt
playwright install
```

### **WebSocket not connecting?**
```javascript
// Check backend is running
fetch('http://localhost:8000/api/actions/status')
  .then(r => r.json())
  .then(console.log);

// Check CORS - should allow localhost:5173
```

### **Actions not working?**
```javascript
// 1. Check connection
console.log('Connected:', playwrightService.isConnected());

// 2. Check mode
console.log('Mode:', actionExecutor.getExecutionMode());

// 3. Check backend logs
// See terminal running uvicorn

// 4. Check shared tab is set
await playwrightService.setSharedTab('tab123', 0);
```

---

## Example: Full Flow

```typescript
// 1. Connect to backend
await playwrightService.connect();
// ✅ Playwright WebSocket connected!

// 2. Start Edge browser
await playwrightService.startBrowser('edge');
// ✅ Connected to edge

// 3. Set execution mode
actionExecutor.setExecutionMode('playwright');
// 🔧 Action execution mode: playwright

// 4. Start voice session
// ... start Gemini Live session ...

// 5. Share screen
const stream = await navigator.mediaDevices.getDisplayMedia({...});
// 🟢 Green border appears

// 6. Tell Playwright which page
await playwrightService.setSharedTab('shared_123', 0);
// 🎯 Setting shared tab: shared_123

// 7. Voice command
// User: "search for AI tools"
// → Gemini calls tools
// → Playwright executes on Edge
// ✅ Types in SHARED EDGE TAB
```

---

## Files Reference

**Backend:**
- `backend/app/services/playwright_executor.py` - Action execution
- `backend/app/api/routes/actions.py` - WebSocket endpoint
- `backend/requirements.txt` - Dependencies
- `backend/setup_playwright.bat` - Setup script
- `backend/test_playwright_integration.py` - Tests

**Frontend:**
- `services/playwrightService.ts` - WebSocket client
- `services/live/actionExecutor.ts` - Dual-mode executor

---

## Next Steps

1. ✅ Backend running: `python -m uvicorn app.main:app --reload`
2. ✅ Test in console: `await playwrightService.connect()`
3. ✅ Try Edge: `await playwrightService.startBrowser('edge')`
4. ✅ Voice commands: Switch mode and test!

**You now have cross-browser voice control! 🎉**
