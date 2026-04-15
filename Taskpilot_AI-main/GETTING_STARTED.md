# 🚀 GETTING STARTED - Enable Voice Commands

## ⚠️ CURRENT ISSUE YOU'RE EXPERIENCING:

**Problem:** AI says "OK" but doesn't actually type, click, or search  
**Reason:** Browser extension is not loaded  
**Solution:** Follow the 5-minute setup below ⬇️

---

## 🎯 WHAT YOU WANT TO ACCOMPLISH:

✅ Say "Search YouTube" → AI opens YouTube and searches  
✅ Say "Type hello world" → AI types for you  
✅ Say "Click the button" → AI clicks it  
✅ Say "Scroll down" → AI scrolls the page  

**This requires a 1-time setup (5 minutes):**

---

## 📦 STEP-BY-STEP: Load the Extension

### For Google Chrome:

#### Step 1: Open Extensions Page
1. Open Google Chrome
2. Click the **3 dots** menu (top-right)
3. Go to: **More tools** → **Extensions**  
   OR  
   Type in address bar: `chrome://extensions/` and press Enter

#### Step 2: Enable Developer Mode
1. Look at **top-right corner** of the extensions page
2. Find the toggle: **"Developer mode"**
3. **Click it to turn it ON** (should turn blue)

#### Step 3: Load the Extension
1. You'll see new buttons appear
2. Click **"Load unpacked"** (top-left area)
3. A file browser opens
4. Navigate to: `C:\Users\sanke\OneDrive\Desktop\Taskpilot AI\extension`
5. **Select the `extension` folder** (not a file inside it!)
6. Click **"Select Folder"**

#### Step 4: Verify It Loaded
You should see:
```
🎯 TaskPilot Companion
Version 1.2
Description: Enables TaskPilot AI to interact with browser tabs...
[ON] ← Make sure toggle is ON (blue)
```

#### Step 5: Refresh TaskPilot
1. Go back to your TaskPilot tab: `http://localhost:3002/`
2. Press `Ctrl + Shift + R` (hard refresh)
3. Press `F12` to open console
4. Look for: `✅ TaskPilot Extension detected and ready!`

---

### For Microsoft Edge:

#### Step 1: Open Extensions Page
1. Open Microsoft Edge
2. Click the **3 dots** menu (top-right)
3. Go to: **Extensions**  
   OR  
   Type in address bar: `edge://extensions/` and press Enter

#### Step 2: Enable Developer Mode
1. Look at **left sidebar**
2. Find the toggle: **"Developer mode"**
3. **Click it to turn it ON**

#### Step 3: Load the Extension
1. Click **"Load unpacked"** button
2. Navigate to: `C:\Users\sanke\OneDrive\Desktop\Taskpilot AI\extension`
3. **Select the `extension` folder**
4. Click **"Select Folder"**

#### Step 4: Verify and Refresh
Same as Chrome steps 4-5 above

---

## ✅ TEST IF IT'S WORKING:

### Test 1: Check Console
1. Open TaskPilot: `http://localhost:3002/`
2. Press `F12` (open console)
3. Look for: `[ScreenContext] ✅ TaskPilot Extension detected and ready!`

**If you see this ✅ = Extension is loaded correctly!**

### Test 2: Try Voice Commands
1. Click the **Live AI Robot** (bottom-right)
2. Select **"Live Voice"**
3. Wait for "Active" status
4. Click **"Share Screen"**
5. Choose "Entire Screen" and click Share

**Now say:**
- "What do you see?" → AI describes screen ✅
- "Scroll down" → Page scrolls ✅
- "Type hello" → AI types in active field ✅

**If actions work ✅ = Everything is set up correctly!**

---

## 🐛 TROUBLESHOOTING:

### Issue: Extension doesn't appear in chrome://extensions/

**Solution:**
1. Make sure you selected the `extension` FOLDER, not a file inside it
2. The folder should contain: `manifest.json`, `content.js`, `background.js`
3. Try again: "Load unpacked" → select extension folder

### Issue: "Developer mode" option is grayed out

**Solution:**
1. You might be using a managed/work browser
2. Try using personal Chrome/Edge instead
3. Or ask IT admin to enable developer mode

### Issue: Extension loads but AI still says "OK" without action

**Solution:**
1. **Reload the extension:**
   - Go to `chrome://extensions/`
   - Find TaskPilot Companion
   - Click the **circular arrow icon** (reload)

2. **Hard refresh TaskPilot:**
   - Go to `http://localhost:3002/`
   - Press `Ctrl + Shift + R`

3. **Check console (F12):**
   - Should see: `✅ TaskPilot Extension detected and ready!`
   - If not, wait 2-3 seconds and check again

### Issue: AI says "extension_required" in console

**This is the exact issue you're experiencing!**

**Solution:**
1. Extension is not loaded or not detected
2. Follow all steps above carefully
3. Make sure to hard refresh TaskPilot page after loading extension
4. Check for green checkbox at `chrome://extensions/`

### Issue: Extension shows errors

**Solution:**
1. Click "Errors" button on the extension
2. Read the error message
3. Common fix: Click "Reload" button on extension
4. Make sure all files exist in extension folder

---

## 📋 QUICK CHECKLIST:

Before reporting "AI doesn't do actions", verify:

- [ ] Extension loaded at `chrome://extensions/` or `edge://extensions/`
- [ ] Extension toggle is ON (blue/enabled)
- [ ] Developer mode is ON
- [ ] TaskPilot page refreshed with `Ctrl + Shift + R`
- [ ] Console shows: `✅ TaskPilot Extension detected and ready!`
- [ ] Orange warning is NOT visible during screen sharing
- [ ] You're sharing "Entire Screen" (not just a tab)

**If all checked ✅ → Voice commands should work perfectly!**

---

## 🎯 WHAT COMMANDS WORK:

Once extension is loaded, you can say:

### Navigation:
- "Open YouTube"
- "Go to Google"
- "Navigate to Twitter"

### Typing:
- "Type hello world"
- "Search for cats"
- "Enter my email address"

### Clicking:
- "Click the submit button"
- "Click the first link"
- "Press the login button"

### Scrolling:
- "Scroll down"
- "Scroll up"
- "Scroll to the bottom"
- "Start auto scrolling"

### Reading:
- "What do you see?"
- "Read the page"
- "What website am I on?"

---

## 💡 PRO TIPS:

1. **Always share "Entire Screen"** - This lets AI see all tabs and windows
2. **Keep extension enabled** - Only needs to be loaded once
3. **Use specific commands** - "Click the blue button" works better than "click button"
4. **Check the orange warning** - If visible = extension not detected
5. **Watch the console** - Press F12 to see what's happening

---

## 🎊 AFTER SETUP:

Once extension is loaded correctly:
- **AI stops saying "OK" without action** ✅
- **Actions actually execute** ✅
- **Typing, clicking, scrolling all work** ✅
- **No orange warning shows** ✅
- **You can control Chrome with voice** ✅

**This is a ONE-TIME setup. Extension stays loaded until you remove it!**

---

## 📞 STILL NOT WORKING?

If you followed ALL steps and it's still not working:

1. **Close and reopen Chrome/Edge completely**
2. **Restart both servers:**
   ```
   Stop: Ctrl+C in both terminals
   Start Backend: cd backend; python -m uvicorn app.main:app --reload
   Start Frontend: npm run dev
   ```
3. **Check extension console for errors:**
   - Go to `chrome://extensions/`
   - Click "service worker" link under TaskPilot Companion
   - Check for red errors
4. **Try the test pages:**
   - Open: `C:\Users\sanke\OneDrive\Desktop\Taskpilot AI\extension\test-tab-1.html`
   - Commands should work on test pages

---

*Setup Time: 5 minutes*  
*Works On: Chrome, Edge, Brave, Opera, Vivaldi*  
*Status: Required for click/type/scroll actions*
