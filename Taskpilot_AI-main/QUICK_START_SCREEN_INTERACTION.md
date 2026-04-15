# 🚀 Quick Start Guide - Screen Interaction System

## ⚡ Get Running in 5 Minutes

### Step 1: Install Browser Extension (1 min)

1. **Open Chrome or Edge**
2. Go to: `chrome://extensions/` (or `edge://extensions/`)
3. Toggle **"Developer mode"** ON (top right)
4. Click **"Load unpacked"**
5. Select folder: `extension/`
6. ✅ You should see **"TaskPilot Companion"** installed

### Step 2: Test Extension (1 min)

1. Right-click the extension icon → **Inspect background page** (to see logs)
2. Open `extension/test-page.html` in a new tab
3. Click **"Check Extension"** → Should show ✅ Extension loaded
4. Click **"Start Screen Share"** → Green border should appear
5. Try test buttons:
   - Click **"Test Scroll Down"**
   - Click **"Test Click Submit"**
   - Click **"Test Type"**

If all works, **extension is ready!** ✅

### Step 3: Start Application (2 min)

```bash
# Terminal 1 - Backend
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 - Frontend  
npm run dev
```

Backend: http://127.0.0.1:8000  
Frontend: http://localhost:3000

### Step 4: Test Screen Interaction (1 min)

1. **Open http://localhost:3000**
2. Click the **floating assistant button** (bottom right)
3. Click **"Start Screen Share"** (or use voice mode)
4. Select **"This Tab"** or **"Entire Screen"**
5. **Green border should appear** around the page
6. Badge should show: "🎯 TaskPilot Controlling: This Tab"

### Step 5: Try Commands

**Voice Commands** (if using voice mode):
- "Scroll down"
- "Click the login button"
- "Type hello world"
- "What's on this page?"
- "Focus on the search box"

**Or use programmatically:**
```typescript
import { geminiScreenController } from './services/live/geminiScreenController';

await geminiScreenController.quickScroll('down');
await geminiScreenController.quickClick('Submit');
await geminiScreenController.quickType('hello@example.com');
const content = await geminiScreenController.quickRead();
```

---

## 🎯 Visual Confirmation

**When everything is working, you'll see:**

1. ✅ **Green pulsing border** around the browser tab
2. ✅ **Animated badge** at top: "TaskPilot Controlling: This Tab"
3. ✅ **Corner indicators** (small green boxes)
4. ✅ **Smooth animations** when actions execute
5. ✅ **Console logs** showing action execution

---

## 🔧 Integration into LiveAssistant

### Quick Integration (Copy & Paste)

```typescript
// 1. Add imports at top of LiveAssistant.tsx
import { geminiScreenController } from '../services/live/geminiScreenController';
import { screenContext } from '../services/live/screenContext';

// 2. When screen capture starts
const setupScreenProcessing = (stream: MediaStream) => {
    // Your existing video processing code...
    
    // ADD THIS:
    screenContext.startSharing('entire-screen');
    
    // Track when stream ends
    stream.getVideoTracks()[0].addEventListener('ended', () => {
        screenContext.stopSharing();
    });
};

// 3. When Gemini speaks (transcript received)
const handleGeminiTranscript = async (transcript: string) => {
    if (!screenContext.canPerformAction()) {
        return "Please share your screen first.";
    }
    
    const result = await geminiScreenController.processCommand(transcript);
    
    if (result.success) {
        return result.message || "Done!";
    } else {
        return `Sorry: ${result.error}`;
    }
};
```

---

## 🎓 Example Commands & Results

| Command | What Happens |
|---------|-------------|
| "Scroll down" | Page scrolls 300px smoothly |
| "Click submit" | Finds button with "submit" text, clicks it |
| "Type my email" | Types into currently focused input |
| "What's on this page?" | Extracts and returns page content |
| "Click login then type password" | Executes sequence |
| "Focus on search box" | Finds and focuses search input |

---

## 🐛 Troubleshooting

### Border Not Showing?

```bash
# Check extension is loaded
chrome://extensions/

# Check console (F12)
# Should see: "[TaskPilot Companion] Content script loaded."

# Reload page
Ctrl+R or Cmd+R
```

### Actions Not Working?

1. **Check screen sharing is active** (green border visible)
2. **Check console logs** (F12 → Console)
3. **Try test page first** (`extension/test-page.html`)
4. **Verify extension permissions** (should have `<all_urls>`)

### Extension Not Loading?

```bash
# Ensure manifest.json is valid
# Check background worker
chrome://extensions/ → TaskPilot Companion → "Inspect views: background page"

# Should see: "[TaskPilot Companion] Background service worker started."
```

---

## 📚 Full Documentation

- **Complete Guide**: `SCREEN_INTERACTION_GUIDE.md`
- **Implementation Details**: `IMPLEMENTATION_COMPLETE.md`
- **Integration Examples**: `services/live/screenIntegrationExample.tsx`
- **Test Page**: `extension/test-page.html`

---

## ✅ Success Checklist

After setup, you should be able to:

- [ ] Extension loads in browser
- [ ] Test page shows green border on "Start Share"
- [ ] Test page actions work (scroll, click, type)
- [ ] Application starts (backend + frontend)
- [ ] LiveAssistant shows floating button
- [ ] Screen share shows green border
- [ ] Voice commands execute actions
- [ ] Border disappears on stop sharing
- [ ] Actions blocked when not sharing

---

## 🎉 You're Ready!

**Your TaskPilot AI now has:**
- ✅ Gemini AI brain for command understanding
- ✅ Browser extension for DOM control
- ✅ Multi-layer security
- ✅ Visual feedback system
- ✅ Voice & text command support

**Start giving commands and watch the magic happen!** 🚀

---

## 📞 Need Help?

1. Check browser console (F12) for errors
2. Review `SCREEN_INTERACTION_GUIDE.md` for details
3. Test with `extension/test-page.html` first
4. Verify extension permissions in manifest

**Happy automating!** 🎯
