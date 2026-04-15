# 🔧 HOW TO LOAD THE CHROME EXTENSION

## ⚠️ Current Issue:
The warning "Chrome Extension Not Detected" appears because the extension hasn't been loaded into Chrome yet.

## ✅ SOLUTION - Load the Extension:

### Step 1: Open Chrome Extension Management
1. Open Google Chrome
2. Type in the address bar: `chrome://extensions/`
3. Press Enter

### Step 2: Enable Developer Mode
1. Look at the **top-right corner** of the page
2. Find the toggle switch labeled **"Developer mode"**
3. **Turn it ON** (it should turn blue)

### Step 3: Load the Extension
1. Click the **"Load unpacked"** button (appears on the left after enabling Developer mode)
2. A file browser window will open
3. Navigate to: `C:\Users\sanke\OneDrive\Desktop\Taskpilot AI\extension`
4. Select the `extension` folder
5. Click **"Select Folder"**

### Step 4: Verify Extension is Loaded
You should now see:
- **"TaskPilot Companion"** in your extensions list
- Version: 1.1
- Status: **Enabled** (toggle should be ON/blue)
- Extension ID (a random string of letters)

### Step 5: Refresh Your TaskPilot Page
1. Go back to your TaskPilot tab: `http://localhost:3002/`
2. Press `Ctrl + Shift + R` (hard refresh)
3. Open browser console (Press `F12`)
4. Look for these messages:
   ```
   [TaskPilot Extension] Announced presence to webpage
   [ScreenContext] ✅ TaskPilot Extension detected and ready!
   ```

### Step 6: Test Live Voice Mode
1. Click the **Live AI Robot** (bottom-right)
2. Select **"Live Voice"**
3. The yellow warning should now be **GONE**!
4. Click **"Share Screen"** button (should not be disabled anymore)
5. Select what to share and click Share

---

## 🐛 Troubleshooting:

### Issue: "Load unpacked" button is grayed out
**Solution:** Make sure "Developer mode" toggle is turned ON

### Issue: Extension loads but still shows "Not Detected"
**Solution:**
1. Refresh the extension at `chrome://extensions/` (click the circular arrow icon)
2. Hard refresh the TaskPilot page: `Ctrl + Shift + R`
3. Check browser console for errors

### Issue: Extension shows errors in red
**Solution:**
1. Check that all these files exist in the extension folder:
   - `manifest.json`
   - `content.js`
   - `background.js`
   - `overlay.css`
2. Click "Errors" button to see what's wrong
3. Fix the file and click the refresh button on the extension

### Issue: Warning still appears after loading extension
**Solution:**
1. Close and reopen the TaskPilot tab
2. Or wait 1-2 seconds after page loads (extension needs time to inject)

---

## ✨ What Happens After Loading:

✅ Yellow warning disappears
✅ "Share Screen" button becomes clickable
✅ Voice commands work: "scroll down", "click button", "type text"
✅ Green border appears when screen sharing
✅ Border follows active tab when you switch tabs

---

## 📸 Visual Guide:

### What You'll See at chrome://extensions/:
```
┌─────────────────────────────────────────┐
│ Extensions                              │
│ ┌──────────────────────────┐            │
│ │ Developer mode     [ON]  │ ← Turn ON  │
│ └──────────────────────────┘            │
│                                         │
│ [Load unpacked] [Pack extension] [...]  │
│  ↑ Click here                           │
│                                         │
│ ┌─────────────────────────────────────┐ │
│ │ 🎯 TaskPilot Companion              │ │
│ │ Version 1.1                         │ │
│ │ Enables TaskPilot AI to interact... │ │
│ │                          [ON]       │ │
│ │ Details  Remove  Errors             │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

---

## 🎯 Quick Command Summary:

1. Open: `chrome://extensions/`
2. Toggle: Developer mode **ON**
3. Click: **"Load unpacked"**
4. Select: `C:\Users\sanke\OneDrive\Desktop\Taskpilot AI\extension`
5. Refresh: TaskPilot page (`Ctrl + Shift + R`)
6. Test: Click robot → Live Voice → Share Screen

**Done!** The warning will be gone and all features will work! 🚀
