# ⚡ TaskPilot AI - Quick Setup Summary

> **Copy this entire guide for sharing with others**

---

## 📋 Prerequisites Checklist

Before starting, install:
- ✅ Node.js (v18+) - https://nodejs.org/
- ✅ Python (v3.9+) - https://www.python.org/downloads/
- ✅ Get Gemini API Key (FREE) - https://makersuite.google.com/app/apikey

---

## 🚀 5-Step Installation

### 1️⃣ Extract & Navigate
```bash
# Extract ZIP file to any location
# Open terminal/command prompt
cd "path/to/TaskpilotAI"
```

### 2️⃣ Install Frontend
```bash
npm install
```

### 3️⃣ Install Backend
```bash
cd backend
pip install -r requirements.txt
playwright install chromium
```

### 4️⃣ Configure API Keys

**Create `backend/.env`:**
```env
GEMINI_API_KEY=AIzaSy___YOUR_KEY_HERE___
```

**Create `.env.local` in root:**
```env
VITE_GEMINI_API_KEY=AIzaSy___YOUR_KEY_HERE___
```

### 5️⃣ Run Both Servers

**Terminal 1 - Backend:**
```bash
cd backend
python start_server.py
# Should show: ✅ Server running at: http://localhost:8000
```

**Terminal 2 - Frontend:**
```bash
npm run dev
# Should show: ➜ Local: http://localhost:5173/
```

**Open browser:** `http://localhost:5173/`

---

## 🔌 Optional: Browser Extension (For Voice Commands)

1. Open `chrome://extensions/` or `edge://extensions/`
2. Enable **Developer mode** (toggle top-right)
3. Click **Load unpacked**
4. Select the `extension` folder from TaskpilotAI
5. Refresh TaskPilot page (`Ctrl + Shift + R`)

---

## 🔧 Common Issues & Fixes

| Problem | Solution |
|---------|----------|
| `npm: command not found` | Install Node.js from nodejs.org |
| `python: command not found` | Try `python3` or reinstall Python with "Add to PATH" |
| `pip: command not found` | Use `python -m pip install -r requirements.txt` |
| Backend won't start | Check `.env` exists in backend folder with API key |
| Frontend can't connect | Ensure backend is running on port 8000 |
| Port already in use | Kill process: `netstat -ano \| findstr :8000` (Windows) |
| Extension not working | Reload extension, hard refresh page (`Ctrl+Shift+R`) |

---

## 📂 What to Configure

**Required files to create:**

```
TaskpilotAI/
├── backend/
│   └── .env                    ← Create this! (Copy from .env.example)
│       GEMINI_API_KEY=...      ← Add your API key
└── .env.local                  ← Create this! (In root folder)
    VITE_GEMINI_API_KEY=...     ← Add your API key
```

**Both files need the same Gemini API key!**

---

## ✅ Verify Installation

1. **Backend Running:** Open `http://localhost:8000/docs` - Should see API documentation
2. **Frontend Running:** Open `http://localhost:5173/` - Should see TaskPilot UI
3. **Extension (Optional):** Press F12 in browser, look for: `✅ TaskPilot Extension detected`
4. **Test Chat:** Type "What is AI?" and press Enter - Should get AI response

---

## 🎯 What This App Does

- ✅ AI-powered chat (Google Gemini)
- ✅ Web search (DuckDuckGo, Wikipedia)
- ✅ Voice commands to control browser (with extension)
- ✅ Screen interaction: click, type, scroll
- ✅ Multi-step task automation

---

## 📞 Need More Help?

See detailed guide: **INSTALLATION_GUIDE.md**

Key documentation:
- `README.md` - Project overview
- `GETTING_STARTED.md` - Extension setup
- `backend/SETUP.md` - Backend details

---

## 📝 Share This Setup with Others

**Send them:**
1. The ZIP file of this project
2. This `QUICK_SETUP_SUMMARY.md` file
3. Tell them to get a Gemini API key first

**Or send this one-liner:**

> "Extract the ZIP, install Node.js & Python, get a free Gemini API key from makersuite.google.com, create `.env` files with your key, run `npm install`, then `cd backend && pip install -r requirements.txt`, then start both servers: `python start_server.py` (backend) and `npm run dev` (frontend). Open http://localhost:5173/"

---

**That's it! 🎉 Happy Tasking!**
