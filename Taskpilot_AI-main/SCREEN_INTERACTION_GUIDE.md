# TaskPilot AI - Screen Interaction System
## Complete Implementation Documentation

## 🎯 Overview

TaskPilot AI now has a complete screen interaction system powered by Google Gemini AI, allowing it to control browser tabs through voice or text commands.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      USER INTERFACE                          │
│                    (LiveAssistant.tsx)                       │
│          Voice Input → Gemini Live API → Commands            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   GEMINI BRAIN LAYER                         │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  GeminiScreenController (Orchestrator)               │   │
│  │  - Receives commands                                 │   │
│  │  - Coordinates parsing & execution                   │   │
│  │  - Returns results                                   │   │
│  └────────────────┬─────────────────────────────────────┘   │
│                   │                                          │
│  ┌────────────────▼──────────────┐   ┌──────────────────┐   │
│  │  GeminiActionParser           │   │  ScreenContext   │   │
│  │  - Parses natural language    │   │  Manager         │   │
│  │  - Converts to structured     │   │  - Tracks state  │   │
│  │    actions                    │   │  - Security      │   │
│  └────────────────┬───────────────┘   └──────────────────┘   │
└───────────────────┼──────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                  EXECUTION LAYER                             │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  ActionExecutor                                      │   │
│  │  - Validates permissions                             │   │
│  │  - Sends actions to extension                        │   │
│  │  - Receives results                                  │   │
│  └────────────────┬─────────────────────────────────────┘   │
└───────────────────┼──────────────────────────────────────────┘
                    │
                    ▼ (window.postMessage)
┌─────────────────────────────────────────────────────────────┐
│                BROWSER EXTENSION LAYER                       │
│                                                              │
│  ┌───────────────────────┐  ┌───────────────────────────┐   │
│  │  Content Script       │  │  Background Script        │   │
│  │  (content.js)         │  │  (background.js)          │   │
│  │  - Receives actions   │  │  - Security enforcement   │   │
│  │  - Executes on DOM    │  │  - State management       │   │
│  │  - Returns results    │  │  - Tab tracking           │   │
│  └───────────────────────┘  └───────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Visual Overlay (overlay.css)                        │   │
│  │  - Green border indicator                            │   │
│  │  - Shows sharing mode                                │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 📋 Components

### 1. **GeminiScreenController** (`services/live/geminiScreenController.ts`)
The main orchestrator that coordinates all screen interaction operations.

**Key Methods:**
- `processCommand(command: string)` - Process natural language commands
- `processVoiceCommand(transcript: string)` - Handle voice input
- `executeAction(action: ScreenAction)` - Execute pre-parsed actions
- `quickScroll()`, `quickClick()`, `quickType()`, `quickRead()` - Convenience methods

### 2. **GeminiActionParser** (`services/live/geminiActionParser.ts`)
Converts natural language commands into structured actions using Gemini AI.

**Supported Actions:**
- `CLICK` - Click elements by text or selector
- `TYPE` - Type text into focused input
- `SCROLL` - Scroll page up/down
- `READ` - Read page content
- `WAIT` - Wait for duration
- `FOCUS` - Focus on input field
- `NONE` - Conversational (no action)

**Example:**
```typescript
"Click the submit button" → { type: 'CLICK', target: 'submit' }
"Scroll down"             → { type: 'SCROLL', direction: 'down', amount: 300 }
"Type hello world"        → { type: 'TYPE', text: 'hello world' }
```

### 3. **ScreenContextManager** (`services/live/screenContext.ts`)
Tracks screen sharing state and enforces security rules.

**Security Features:**
- Only allows actions when screen sharing is active
- Tracks sharing mode (`tab`, `window`, `entire-screen`)
- Prevents actions immediately after sharing starts (500ms cooldown)
- Automatically clears permissions when sharing stops

### 4. **ActionExecutor** (`services/live/actionExecutor.ts`)
Executes validated actions on the shared screen via the browser extension.

**Key Features:**
- Security validation before every action
- Bidirectional communication with extension
- Action result tracking
- Error handling with timeouts

### 5. **Browser Extension**

#### Content Script (`extension/content.js`)
Runs on every page and executes DOM manipulations.

**Actions:**
- `scroll` - Smooth scrolling
- `click` - Smart element clicking (by text or selector)
- `type_text` - Input text with event triggering
- `focus_element` - Focus inputs by label or placeholder
- `read` - Extract page content
- `toggle_border` - Show/hide visual indicator

#### Background Script (`extension/background.js`)
Manages state and enforces security policies.

**Features:**
- Screen sharing state management
- Tab tracking and switching support
- Action validation and routing
- Visual indicator coordination

#### Visual Overlay (`extension/overlay.css`)
Provides clear visual feedback when screen sharing is active.

**Features:**
- Persistent green border (6px)
- Animated badge with sharing mode label
- Pulsing animation
- Corner indicators
- Responsive design

## 🔒 Security Implementation

### 1. **Multi-Layer Protection**

```typescript
// Layer 1: Screen Context Check
if (!screenContext.canPerformAction()) {
    return { error: 'Screen sharing not active' };
}

// Layer 2: Extension State Check
if (!isSharing) {
    return { error: 'Not authorized' };
}

// Layer 3: Minimum Duration Check
if (Date.now() - sharingStartTime < 500) {
    return { error: 'Too soon after sharing started' };
}
```

### 2. **Automatic Cleanup**
When screen sharing stops:
- All permissions are immediately revoked
- Visual indicators removed from all tabs
- Action queues cleared
- AI informed it cannot see the screen

### 3. **Visual Confirmation**
Users always see:
- Green border around controlled tab
- Badge showing what's being shared
- Pulsing animation indicating active control

## 🚀 Usage Examples

### From React Component (LiveAssistant.tsx)

```typescript
import { geminiScreenController } from '../services/live/geminiScreenController';
import { screenContext } from '../services/live/screenContext';

// Start screen sharing
screenContext.startSharing('tab');

// Process voice command
const result = await geminiScreenController.processCommand(
    "Click the login button and type my email"
);

// Quick actions
await geminiScreenController.quickScroll('down', 500);
await geminiScreenController.quickClick('Submit');
await geminiScreenController.quickType('user@example.com');

// Read page content
const readResult = await geminiScreenController.quickRead();
console.log(readResult.result); // Page text

// Stop sharing
screenContext.stopSharing();
```

### Command Examples

| User Says | Action Generated | What Happens |
|-----------|------------------|--------------|
| "Scroll down" | `SCROLL` down 300px | Page scrolls smoothly |
| "Click submit" | `CLICK` target="submit" | Finds and clicks button |
| "Type hello" | `TYPE` text="hello" | Types into focused input |
| "What's on this page?" | `READ` | Returns page content |
| "Wait 2 seconds" | `WAIT` 2000ms | Pauses execution |
| "Focus on email field" | `FOCUS` target="email" | Focuses email input |

## 🔧 Integration with Gemini Live API

### In LiveAssistant Component

```typescript
// When Gemini speaks a command
const handleGeminiCommand = async (transcript: string) => {
    if (!screenContext.canPerformAction()) {
        return "I cannot see your screen. Please share it first.";
    }

    const result = await geminiScreenController.processCommand(transcript);
    
    if (result.success) {
        return `Done! ${result.message}`;
    } else {
        return `Sorry, I couldn't do that: ${result.error}`;
    }
};

// During screen capture
setupScreenProcessing(stream);
screenContext.startSharing('entire-screen');

// When stream ends
track.onended = () => {
    screenContext.stopSharing();
};
```

## 📦 Installation & Setup

### 1. Install Browser Extension

1. Open Chrome/Edge
2. Navigate to `chrome://extensions/`
3. Enable "Developer mode"
4. Click "Load unpacked"
5. Select the `extension/` folder

### 2. Configure Environment

```env
# .env.local
VITE_GEMINI_API_KEY=your_api_key_here
VITE_API_BASE_URL=http://127.0.0.1:8000
```

### 3. Start Application

```bash
# Backend
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
npm run dev
```

### 4. Test Screen Interaction

1. Open TaskPilot AI (http://localhost:3000)
2. Click the floating assistant button
3. Start screen sharing (select "This Tab" or "Entire Screen")
4. Green border should appear
5. Give voice commands like "scroll down" or "click the button"

## 🧪 Testing

### Manual Testing Checklist

- [ ] Screen sharing starts → Green border appears
- [ ] Badge shows correct mode (Tab/Window/Screen)
- [ ] Scroll commands work smoothly
- [ ] Click finds buttons by text
- [ ] Type works in input fields
- [ ] Read returns page content
- [ ] Screen sharing stops → Border disappears
- [ ] Actions blocked when not sharing
- [ ] Works across tab switches
- [ ] Extension handles page reloads

### Test Commands

```typescript
// In browser console (when sharing)
window.postMessage({
    type: 'TASKPILOT_ACTION',
    messageId: 'test_1',
    payload: { action: 'scroll', direction: 'down', amount: 300 }
}, '*');
```

## 🎨 Customization

### Change Border Color

Edit `extension/overlay.css`:
```css
#taskpilot-overlay {
    border: 6px solid #3b82f6; /* Blue instead of green */
}
```

### Adjust Security Cooldown

Edit `services/live/screenContext.ts`:
```typescript
const MIN_DURATION = 1000; // 1 second instead of 500ms
```

### Add New Actions

1. Add action type to `geminiActionParser.ts`
2. Implement handler in `actionExecutor.ts`
3. Add DOM manipulation in `extension/content.js`

## 🐛 Troubleshooting

### Border Not Showing
- Check extension is loaded and enabled
- Verify content script injected (check DevTools > Sources)
- Ensure screen sharing started successfully

### Actions Not Working
- Confirm green border is visible
- Check browser console for errors
- Verify extension permissions in manifest
- Test with `chrome://extensions/` → Inspect background worker

### Commands Not Parsing
- Check Gemini API key is valid
- Try quickParse methods first (no API needed)
- Review command format in examples

### Cross-Origin Issues
- Ensure extension has `<all_urls>` permission
- Check `externally_connectable` in manifest.json
- Verify localhost URLs are whitelisted

## 📚 API Reference

### GeminiScreenController

```typescript
interface CommandResult {
    success: boolean;
    action?: ScreenAction;
    result?: any;
    message?: string;
    error?: string;
}

class GeminiScreenController {
    processCommand(command: string): Promise<CommandResult>
    processVoiceCommand(transcript: string): Promise<CommandResult>
    executeAction(action: ScreenAction): Promise<CommandResult>
    quickScroll(direction: 'up'|'down', amount?: number): Promise<CommandResult>
    quickClick(target: string): Promise<CommandResult>
    quickType(text: string): Promise<CommandResult>
    quickRead(): Promise<CommandResult>
    getHistory(): Array<{command, action, result}>
    clearHistory(): void
    canProcess(): boolean
    getStatus(): object
}
```

### ScreenContextManager

```typescript
type SharingMode = 'entire-screen' | 'window' | 'tab' | null;

interface ScreenState {
    isSharing: boolean;
    mode: SharingMode;
    tabId?: string;
    startedAt?: number;
}

class ScreenContextManager {
    startSharing(mode: SharingMode, tabId?: string): void
    stopSharing(): void
    getState(): ScreenState
    getIsSharing(): boolean
    getMode(): SharingMode
    getSharingLabel(): string
    canPerformAction(): boolean
    subscribe(callback: (state: ScreenState) => void): () => void
}
```

## 🎯 Best Practices

1. **Always check `canPerformAction()` before executing**
2. **Use `quickParse()` for common commands** (faster, no API call)
3. **Provide user feedback** when sharing starts/stops
4. **Clear history** when switching tasks
5. **Test with different screen sharing modes**
6. **Handle errors gracefully** with user-friendly messages
7. **Log actions** for debugging

## 🔮 Future Enhancements

- [ ] Multi-tab coordination
- [ ] Scheduled actions
- [ ] Action macros/recordings
- [ ] Visual feedback on target elements
- [ ] Screenshot analysis integration
- [ ] Form auto-fill intelligence
- [ ] Page navigation chains
- [ ] Error recovery strategies

## 📄 License

Part of TaskPilot AI - Enterprise Multi-Agent System

---

**Built with ❤️ using Google Gemini AI and Chrome Extensions API**
