# 📦 TaskPilot AI - Complete Installation Guide

> **For users who received this project as a ZIP file**

This guide will walk you through setting up and running TaskPilot AI on your local machine from scratch.

---

## 📋 Table of Contents

1. [Prerequisites](#-prerequisites)
2. [Installation Steps](#-installation-steps)
3. [Configuration](#-configuration)
4. [Running the Application](#-running-the-application)
5. [Browser Extension Setup](#-browser-extension-setup)
6. [Testing](#-testing)
7. [Troubleshooting](#-troubleshooting)

---

## 🔧 Prerequisites

Before you begin, make sure you have the following installed:

### Required Software:

1. **Node.js** (v18 or higher)
   - Download: https://nodejs.org/
   - Verify installation: `node --version`

2. **Python** (v3.9 or higher)
   - Download: https://www.python.org/downloads/
   - Verify installation: `python --version` or `python3 --version`
   - ⚠️ **Important**: During installation, check "Add Python to PATH"

3. **Google Chrome** or **Microsoft Edge** browser
   - For the browser extension functionality

### Required API Key:

4. **Google Gemini API Key** (FREE)
   - Get it from: https://makersuite.google.com/app/apikey
   - Sign in with your Google account
   - Click "Create API Key"
   - Copy the key (starts with `AIza...`)

---

## 📥 Installation Steps

### Step 1: Extract the ZIP File

1. Right-click the ZIP file
2. Select "Extract All..." or use 7-Zip/WinRAR
3. Extract to a location like: `C:\TaskpilotAI\` or `Desktop\TaskpilotAI\`
4. Open the extracted folder

### Step 2: Open Terminal/Command Prompt

**Windows:**
- Press `Win + R`
- Type `cmd` or `powershell`
- Press Enter
- Navigate to the project: `cd "C:\path\to\TaskpilotAI"`

**Mac/Linux:**
- Open Terminal
- Navigate to the project: `cd /path/to/TaskpilotAI`

### Step 3: Install Frontend Dependencies

```bash
# Make sure you're in the root directory (TaskpilotAI folder)
npm install
```

**Expected output:** Packages installed successfully (may take 2-5 minutes)

### Step 4: Install Backend Dependencies

```bash
# Navigate to backend folder
cd backend

# Install Python packages
pip install -r requirements.txt
```

**Alternative commands if above doesn't work:**
```bash
# Try pip3
pip3 install -r requirements.txt

# Or use Python directly
python -m pip install -r requirements.txt
```

**Expected output:** All packages installed successfully (may take 5-10 minutes)

### Step 5: Install Playwright Browsers (Required for screen interaction)

```bash
# Still in backend folder
playwright install chromium
```

**Expected output:** Chromium browser downloaded successfully

---

## ⚙️ Configuration

### Backend Configuration (.env file)

1. **Navigate to backend folder** (if not already there)
   ```bash
   cd backend
   ```

2. **Create .env file from template**
   
   **Option A - Manual (Recommended):**
   - Open the `backend` folder in File Explorer
   - Find `.env.example` file
   - Copy it and rename the copy to `.env` (no .txt extension!)
   - Open `.env` in Notepad or any text editor

   **Option B - Command Line:**
   ```bash
   # Windows
   copy .env.example .env
   
   # Mac/Linux
   cp .env.example .env
   ```

3. **Add your Gemini API Key**
   
   Open `.env` and replace this line:
   ```
   GEMINI_API_KEY=your_gemini_api_key_here
   ```
   
   With your actual API key:
   ```
   GEMINI_API_KEY=AIzaSyBwYp31i-pWcQy1qqts1UeKvFjm6WzAxbM
   ```

4. **Save the file**

### Frontend Configuration (.env.local file)

1. **Navigate back to root folder**
   ```bash
   cd ..
   ```

2. **Create .env.local file**
   
   Create a new file named `.env.local` in the root directory with:
   ```
   VITE_GEMINI_API_KEY=your_gemini_api_key_here
   ```

3. **Add your Gemini API Key**
   
   Replace `your_gemini_api_key_here` with your actual key:
   ```
   VITE_GEMINI_API_KEY=AIzaSyBwYp31i-pWcQy1qqts1UeKvFjm6WzAxbM
   ```

---

## 🚀 Running the Application

You need to run **TWO servers** simultaneously: Backend + Frontend

### Terminal 1: Start Backend Server

```bash
# Navigate to backend folder
cd backend

# Start the server
python start_server.py
```

**Alternative commands:**
```bash
# If above doesn't work, try:
python3 start_server.py

# Or directly with uvicorn:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Windows batch file:
start_server.bat
```

**Expected output:**
```
✅ .env file found with API key configured
✅ Dependencies installed
✅ Starting TaskPilot AI Backend...
💡 Server running at: http://localhost:8000
```

**✅ Keep this terminal window open!**

### Terminal 2: Start Frontend Server

Open a **NEW terminal window/tab** and:

```bash
# Navigate to root folder (not backend!)
cd "C:\path\to\TaskpilotAI"

# Start the frontend
npm run dev
```

**Expected output:**
```
VITE v6.2.0  ready in 500 ms

➜  Local:   http://localhost:5173/
➜  Network: use --host to expose
```

**✅ Keep this terminal window open!**

### Access the Application

Open your browser and go to:
```
http://localhost:5173/
```

You should see the TaskPilot AI interface! 🎉

---

## 🔌 Browser Extension Setup (Optional but Recommended)

The extension enables advanced features like:
- Voice commands to control the browser
- Screen interaction (click, type, scroll)
- Tab management

### For Google Chrome:

1. **Open Extensions Page**
   - Go to: `chrome://extensions/`
   - Or: Menu (⋮) → More tools → Extensions

2. **Enable Developer Mode**
   - Toggle "Developer mode" **ON** (top-right corner)

3. **Load the Extension**
   - Click "Load unpacked" button
   - Navigate to: `TaskpilotAI\extension` folder
   - Select the `extension` folder
   - Click "Select Folder"

4. **Verify Installation**
   - You should see: **🎯 TaskPilot Companion**
   - Make sure the toggle is **ON** (blue)

### For Microsoft Edge:

1. **Open Extensions Page**
   - Go to: `edge://extensions/`

2. **Enable Developer Mode**
   - Toggle "Developer mode" **ON** (left sidebar)

3. **Load the Extension**
   - Click "Load unpacked"
   - Select the `TaskpilotAI\extension` folder

4. **Verify Installation**
   - Extension should appear in the list

### Refresh TaskPilot

After loading the extension:
1. Go back to TaskPilot tab: `http://localhost:5173/`
2. Press `Ctrl + Shift + R` (hard refresh)
3. Press `F12` to open Developer Console
4. Look for: `✅ TaskPilot Extension detected and ready!`

---

## ✅ Testing

### Test 1: Basic Chat

1. Open TaskPilot: `http://localhost:5173/`
2. Type a message: "What is artificial intelligence?"
3. Press Enter or click Send
4. You should get an AI-powered response

### Test 2: Extension Detection (if installed)

1. Press `F12` to open browser console
2. Look for messages containing:
   - `✅ TaskPilot Extension detected and ready!`
   - `[ScreenContext] Extension connected`

### Test 3: Voice Commands (if extension installed)

1. Click the **Live AI Robot** icon (bottom-right)
2. Select **"Live Voice"**
3. Wait for "Active" status
4. Try saying: "Search YouTube"
5. AI should respond and open YouTube

---

## 🔧 Troubleshooting

### Problem: "npm: command not found" or "node: command not found"

**Solution:** Install Node.js from https://nodejs.org/

**Verify:**
```bash
node --version
npm --version
```

### Problem: "python: command not found"

**Solution:** 
- Windows: Reinstall Python and check "Add to PATH"
- Mac/Linux: Try `python3` instead of `python`

### Problem: "pip: command not found"

**Solution:**
```bash
# Windows
python -m pip install -r requirements.txt

# Mac/Linux
python3 -m pip install -r requirements.txt
```

### Problem: Backend won't start

**Check:**
1. Is `.env` file created in `backend` folder?
2. Does it contain your Gemini API key?
3. Are you in the correct folder? (`backend` folder)

**Fix:**
```bash
cd backend
python verify_gemini.py
```

This will show what's missing.

### Problem: Frontend shows "Cannot connect to server"

**Check:**
1. Is backend server running? (Terminal 1)
2. Is it running on port 8000?
3. Check browser console (F12) for errors

**Fix:** Make sure backend is running at `http://localhost:8000`

### Problem: Extension not working

**Check:**
1. Extension loaded in `chrome://extensions/`?
2. Developer mode enabled?
3. Extension toggle is ON?
4. Did you refresh TaskPilot page after loading extension?

**Fix:**
1. Remove and reload extension
2. Hard refresh TaskPilot: `Ctrl + Shift + R`

### Problem: Voice commands not working

**Check:**
1. Browser has microphone permissions?
2. Extension installed and active?
3. "Live Voice" mode activated?

**Fix:**
1. Check browser settings → Privacy → Microphone
2. Reload extension
3. Refresh TaskPilot page

### Problem: Playwright Error

**Solution:**
```bash
cd backend
playwright install chromium
```

### Problem: Port already in use

**Backend (port 8000):**
```bash
# Windows - Kill process on port 8000
netstat -ano | findstr :8000
taskkill /PID <PID_NUMBER> /F

# Mac/Linux
lsof -ti:8000 | xargs kill -9
```

**Frontend (port 5173):**
```bash
# Windows
netstat -ano | findstr :5173
taskkill /PID <PID_NUMBER> /F

# Mac/Linux
lsof -ti:5173 | xargs kill -9
```

---

## 📝 Quick Reference

### Start Everything (Quick Commands)

**Terminal 1 - Backend:**
```bash
cd backend
python start_server.py
```

**Terminal 2 - Frontend:**
```bash
npm run dev
```

**Access App:**
```
http://localhost:5173/
```

### Stop Everything

- Press `Ctrl + C` in both terminal windows
- Or close the terminal windows

### Project Structure

```
TaskpilotAI/
├── backend/              # Python backend server
│   ├── .env             # Your API keys (create this!)
│   ├── .env.example     # Template
│   └── requirements.txt # Python dependencies
├── extension/           # Chrome/Edge extension
├── components/          # React components
├── services/            # Frontend services
├── .env.local          # Frontend API key (create this!)
└── package.json        # Node.js dependencies
```

### Important Files to Configure

1. `backend/.env` - Backend API key
2. `.env.local` - Frontend API key (root folder)

Both need your Gemini API key!

---

## 🎓 What This Application Does

**TaskPilot AI** is an intelligent assistant that can:

✅ Answer questions using AI (Google Gemini)  
✅ Search the web (DuckDuckGo, Wikipedia)  
✅ Control your browser with voice commands (with extension)  
✅ Click, type, scroll on web pages  
✅ Manage browser tabs  
✅ Perform complex multi-step tasks  

---

## 🆘 Need Help?

If you're still stuck:

1. **Check the documentation files:**
   - `README.md` - Project overview
   - `GETTING_STARTED.md` - Quick start guide
   - `backend/SETUP.md` - Backend setup details

2. **Open an issue** with:
   - Your operating system (Windows/Mac/Linux)
   - Error messages (copy the full text)
   - What step you're stuck on

3. **Console logs:**
   - Backend: Check Terminal 1 output
   - Frontend: Press F12 in browser, check Console tab

---

## ✨ You're All Set!

Once both servers are running and you can access `http://localhost:5173/`, you're ready to use TaskPilot AI!

Try asking questions, giving commands, or exploring the interface.

**Happy Tasking! 🚀**
