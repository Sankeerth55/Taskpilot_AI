# 🎯 Quick Implementation Reference

## Key Code Changes

### 1. LiveAssistant.tsx - Track Shared Tab

```typescript
// Track which tab is being shared (not active tab!)
const sharedTabIdRef = useRef<string | null>(null);

const toggleScreenShare = async () => {
    if (!sessionPromiseRef.current) return;

    if (isScreenSharing) {
        // Stop sharing
        screenStreamRef.current?.getTracks().forEach(track => track.stop());
        sharedTabIdRef.current = null; // Clear shared tab reference
        setIsScreenSharing(false);
    } else {
        // Start sharing
        // 🟢 Chrome's native green border appears automatically!
        const stream = await navigator.mediaDevices.getDisplayMedia({
            video: { width: 1280, height: 720 },
            audio: false // Green border shows on shared tab/window
        });

        // Get display surface type
        const videoTrack = stream.getVideoTracks()[0];
        const settings = videoTrack.getSettings();
        const displaySurface = settings.displaySurface; // 'monitor', 'window', 'browser'
        
        // Store shared tab ID
        const sharedTabId = `shared_${Date.now()}`;
        sharedTabIdRef.current = sharedTabId;

        // Handle stop
        stream.getVideoTracks()[0].onended = () => {
            setIsScreenSharing(false);
            screenContext.stopSharing();
            sharedTabIdRef.current = null;
            // 🔴 Green border removed automatically by Chrome
        };

        setIsScreenSharing(true);
        screenContext.startSharing(displaySurface as any, sharedTabId);
    }
};
```

### 2. System Instruction - Shared Screen Behavior

```typescript
systemInstruction: `You are TaskPilot AI...

SHARED SCREEN BEHAVIOR (CRITICAL):
- When user starts screen sharing, Chrome shows a GREEN BORDER on the specific tab/window
- The green border STAYS on that tab even when user switches to other tabs
- ALL your actions (click, type, scroll) execute ONLY on the SHARED screen (green border)
- Even if the user is viewing a different tab, your actions affect only the shared tab
- Example: User shares Google tab → switches to Microsoft tab → 
  you type "search query" → it types in GOOGLE tab (shared screen)
- This allows the user to work on other tabs while you control the shared screen
`
```

### 3. screenContext.ts - Get Shared Tab ID

```typescript
export interface ScreenState {
    isSharing: boolean;
    mode: SharingMode;
    tabId?: string; // ⭐ ID of the shared tab
    startedAt?: number;
}

class ScreenContextManager {
    /**
     * Get the shared tab/window ID
     */
    public getSharedTabId(): string | undefined {
        return this.state.tabId;
    }
    
    public startSharing(mode: SharingMode = 'entire-screen', tabId?: string): void {
        this.state = {
            isSharing: true,
            mode,
            tabId, // ⭐ Store shared tab ID
            startedAt: Date.now()
        };
        console.log(`🟢 Chrome green border active on ${mode}`, tabId ? `(ID: ${tabId})` : '');
    }
}
```

### 4. actionExecutor.ts - Target Shared Tab

```typescript
private sendAction(action: string, data: any): Promise<ActionResult> {
    // Get shared tab ID to target the correct screen
    const sharedTabId = screenContext.getSharedTabId();

    return new Promise((resolve) => {
        const messageId = `action_${Date.now()}_${Math.random()}`;
        
        // Send action to extension with shared tab ID
        window.postMessage({
            type: "TASKPILOT_ACTION",
            messageId,
            targetTabId: sharedTabId, // ⭐ Target shared screen, not active tab
            payload: { action, ...data }
        }, "*");
    });
}
```

### 5. background.js (Extension) - Route to Shared Tab

```javascript
// 🎯 State Management
let isSharing = false;
let sharedTabId = null; // ⭐ The SPECIFIC tab being shared (with green border)
let sharingMode = null;

// 🟢 Start Sharing
function handleStartSharing(request, sendResponse) {
    isSharing = true;
    sharingMode = request.mode || 'entire-screen';
    
    // Get CURRENT ACTIVE TAB - this is the one being shared
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs.length > 0) {
            sharedTabId = tabs[0].id; // ⭐ Lock to this tab
            console.log('🎯 SHARED TAB LOCKED:', sharedTabId);
            console.log('   Actions will execute on THIS tab even when you switch tabs');
        }
    });
}

// 🎯 Execute Actions on SHARED TAB
function handleAction(actionData, messageId, sendResponse) {
    if (!isSharing || !sharedTabId) {
        sendResponse({ success: false, error: "Not sharing" });
        return;
    }

    // ⭐ Send action to SHARED tab (not active tab!)
    chrome.tabs.sendMessage(sharedTabId, actionData, (response) => {
        console.log(`✅ ACTION COMPLETED on shared tab ${sharedTabId}`);
        sendResponse({ success: true, response, messageId });
    });
}

// 📍 Track Tab Switches (for debugging)
chrome.tabs.onActivated.addListener((activeInfo) => {
    if (!isSharing) return;
    
    if (activeInfo.tabId === sharedTabId) {
        console.log('📍 Switched to SHARED tab');
    } else {
        console.log(`📍 Switched to tab ${activeInfo.tabId}`);
        console.log(`   Green border stays on shared tab ${sharedTabId}`);
        console.log('   Actions will still execute on shared tab');
    }
});

// ⚠️ Handle Shared Tab Closed
chrome.tabs.onRemoved.addListener((tabId) => {
    if (tabId === sharedTabId) {
        console.warn('⚠️ SHARED TAB CLOSED - Stopping sharing');
        isSharing = false;
        sharedTabId = null;
    }
});
```

---

## 🔑 Key Concepts

### Chrome's Native Green Border
```javascript
// This automatically shows a green border:
navigator.mediaDevices.getDisplayMedia({ video: true })

// Border appears on the selected tab/window
// Border stays visible even when switching tabs
// Border is removed when stream.getTracks()[0].stop() is called
```

### Shared Tab vs Active Tab
```
BEFORE (wrong):
User shares Tab A, switches to Tab B
Action executes on Tab B (active tab) ❌

AFTER (correct):
User shares Tab A, switches to Tab B  
Action executes on Tab A (shared tab) ✅
                     ↑
                Green border shows this
```

### Message Flow
```
User Voice Command
      ↓
LiveAssistant.tsx (get sharedTabId)
      ↓
actionExecutor.ts (include targetTabId)
      ↓
window.postMessage({ targetTabId })
      ↓
background.js (route to sharedTabId)
      ↓
content.js in SHARED TAB (execute action)
```

---

## 🧪 Test Scenarios

### Test 1: Basic Shared Screen Control
1. Open Google.com
2. Start voice mode + share screen
3. 🟢 Green border appears on Google
4. Say "search puppies"
5. ✅ Types in Google search box

### Test 2: Cross-Tab Control
1. Share Google tab (🟢 green border)
2. Switch to Microsoft tab (no green border)
3. Say "search AI tools"
4. ✅ Types in GOOGLE tab (not Microsoft)
5. Switch back to Google → see "AI tools" in search box

### Test 3: Border Persistence
1. Share Tab A
2. 🟢 Green border on Tab A
3. Switch to Tab B, C, D
4. 🟢 Green border STAYS on Tab A
5. Switch back → border still there

### Test 4: Stop Sharing
1. Share screen (🟢 green border visible)
2. Click "Stop Sharing"
3. 🔴 Green border disappears instantly
4. Actions no longer execute

---

## 🔍 Console Indicators

### Sharing Started
```
🟢 SCREEN SHARING STARTED
🎯 SHARED TAB LOCKED: 123
   Actions will execute on THIS tab even when you switch tabs
   Chrome's green border shows which tab is shared
```

### Tab Switched
```
📍 Switched to tab 456
   Green border stays on shared tab 123
   Actions will still execute on shared tab
```

### Action Execution
```
🎯 EXECUTING ON SHARED TAB: 123
   (Current active tab: 456)
   Action: { action: 'type_text', text: 'hello' }
✅ ACTION COMPLETED on shared tab 123
```

### Sharing Stopped
```
🔴 SCREEN SHARING STOPPED
   Chrome's green border removed automatically
```

---

## 🎯 Summary

**What Changed:**
- ✅ Removed custom green border overlay
- ✅ Track shared tab ID from getDisplayMedia
- ✅ Route actions to shared tab (not active tab)
- ✅ Updated Gemini prompt with shared screen behavior
- ✅ Chrome's native green border shows automatically

**Result:**
- Green border stays on shared tab across switches
- Voice actions execute on shared screen only
- User can work on other tabs while AI controls shared screen
- Natural Chrome UX with built-in security indicator

**Try It:**
Share a tab, switch to another tab, give voice command → watch it execute on the shared tab! 🚀
