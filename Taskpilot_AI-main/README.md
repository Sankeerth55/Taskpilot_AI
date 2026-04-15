# 🤖 TaskPilot AI

<div align="center">

**An intelligent AI-powered task assistant with multi-agent orchestration, voice interaction, and screen awareness**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![React](https://img.shields.io/badge/React-19.2.4-blue.svg)](https://reactjs.org/)
[![Python](https://img.shields.io/badge/Python-3.8+-green.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-teal.svg)](https://fastapi.tiangolo.com/)

</div>

---

## 📋 Overview

TaskPilot AI is a sophisticated AI assistant that combines multiple intelligent agents to help users complete tasks through natural language conversation, voice interaction, and screen-aware context. Built with React for the frontend and FastAPI for the backend, it leverages Google's Gemini AI for advanced natural language understanding.

### ✨ Key Features

- **🎙️ Voice Assistant**: Real-time voice interaction with continuous conversation support
- **💬 Text Chat**: Full-featured chat interface with session management
- **👁️ Screen Awareness**: Capture and analyze screen context for context-aware assistance
- **🤝 Multi-Agent System**: Orchestrated task execution with specialized agents:
  - **FetcherAgent**: Data collection from web sources (DuckDuckGo, Wikipedia)
  - **AnalyzerAgent**: Pure Python analysis and entity extraction
  - **PlannerAgent**: AI-powered task planning with rule-based fallback
  - **ReporterAgent**: Intelligent response generation with templates
- **📁 File Processing**: Upload and process PDFs, DOCX, Excel files
- **🔍 Web Search Integration**: Real-time information retrieval
- **🌐 Browser Automation**: Playwright integration for automated tasks
- **📊 Document Summarization**: BART-based document analysis

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (React + TypeScript)            │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐   │
│  │ Chat UI     │  │ Voice UI    │  │ Screen Capture   │   │
│  └─────────────┘  └─────────────┘  └──────────────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST API / WebSocket
┌───────────────────────────┴─────────────────────────────────┐
│                  BACKEND (FastAPI + Python)                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           TaskOrchestrator (Coordinator)             │   │
│  └────┬────────────┬────────────┬────────────┬─────────┘   │
│       │            │            │            │               │
│  ┌────▼────┐  ┌───▼────┐  ┌───▼─────┐  ┌──▼────────┐     │
│  │ Fetcher │  │Analyzer│  │ Planner │  │ Reporter  │     │
│  │ Agent   │  │ Agent  │  │ Agent   │  │ Agent     │     │
│  └─────────┘  └────────┘  └─────────┘  └───────────┘     │
│       │            │            │            │               │
│  ┌────▼────────────┴────────────┴────────────▼─────────┐   │
│  │    DuckDuckGo | Wikipedia | Gemini AI | Playwright  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- **Node.js** (v16 or higher)
- **Python** 3.8+
- **Google Gemini API Key** (get it from [Google AI Studio](https://makersuite.google.com/app/apikey))

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/Sankeerth55/Taskpilot_AI.git
cd Taskpilot_AI
```

### 2️⃣ Frontend Setup

```bash
# Install dependencies
npm install

# Create .env.local file
echo VITE_GEMINI_API_KEY=your_gemini_api_key_here > .env.local

# Start development server (stable)
npm run dev -- --host 127.0.0.1 --port 3000
```

The frontend will start at `http://127.0.0.1:3000`

### 3️⃣ Backend Setup

```bash
# Navigate to backend directory
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Create .env file (optional - works without API key using fallbacks)
echo GEMINI_API_KEY=your_gemini_api_key_here > .env

# Install Playwright browsers
playwright install

# Start the backend server (stable, no auto-reload)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The backend will start at `http://localhost:8000`

### 4️⃣ Access the Application

Open your browser and navigate to `http://127.0.0.1:3000`

### ✅ Verified Local Links
- Frontend: http://127.0.0.1:3000
- Backend: http://127.0.0.1:8000
- API Docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/api/health/ping

### 🛠️ If Port 8000 Is Busy
Sometimes a stale process blocks the port. Free it, then restart the backend:

```powershell
Get-NetTCPConnection -LocalPort 8000 | Select-Object -First 5 | Format-Table -AutoSize
Stop-Process -Id <PID> -Force
```

---

## 📦 Tech Stack

### Frontend
- **React 19** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **Lucide React** - Icons
- **Google Generative AI** - Gemini integration

### Backend
- **FastAPI** - Web framework
- **SQLAlchemy** - ORM
- **Playwright** - Browser automation
- **Google Generative AI** - LLM integration
- **DuckDuckGo Search** - Web search
- **Wikipedia API** - Knowledge retrieval
- **Transformers (BART)** - Document summarization
- **PyTorch** - ML inference

---

## 🎯 Usage

### Text Chat
1. Click "Start Task" on the landing page
2. Type your query or request
3. TaskPilot will orchestrate agents to fulfill your request
4. View results with clickable links and formatted responses

### Voice Assistant
1. Click the microphone icon
2. Grant microphone permissions
3. Speak naturally to TaskPilot
4. Get real-time AI responses

### Screen Sharing
1. Click "Share Screen" button
2. Select the screen/window to share
3. TaskPilot can now see your screen for context-aware help

### File Upload
1. Click the attachment icon
2. Upload PDF, DOCX, or Excel files
3. TaskPilot will process and analyze the content

---

## 🔧 Configuration

### Frontend Environment Variables (.env.local)
```env
VITE_GEMINI_API_KEY=your_gemini_api_key
VITE_BACKEND_URL=http://localhost:8000
```

### Backend Environment Variables (.env)
```env
GEMINI_API_KEY=your_gemini_api_key
TASKPILOT_APP_NAME=TaskPilot AI Backend
TASKPILOT_ENVIRONMENT=development
TASKPILOT_DATABASE_URL=sqlite+aiosqlite:///./taskpilot.db
```

---

## 📚 API Documentation

Once the backend is running, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Key Endpoints

- `POST /sessions` - Create new chat session
- `GET /sessions` - List all sessions
- `POST /messages` - Send text message
- `POST /voice` - Send voice transcript
- `POST /screen-context` - Store screen context

---

## 🧪 Testing

### Backend Tests
```bash
cd backend
python test_agents.py
python test_gemini_connection.py
python test_real_queries.py
```

---

## 📖 Documentation

- [Getting Started Guide](GETTING_STARTED.md)
- [Architecture Documentation](COLLEGE_PROJECT_ARCHITECTURE.md)
- [Backend README](backend/README.md)
- [Quick Reference](QUICK_REFERENCE.md)

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Author

**Sankeerth55**
- GitHub: [@Sankeerth55](https://github.com/Sankeerth55)

---

## 🙏 Acknowledgments

- Google Gemini AI for powerful language models
- FastAPI for the excellent web framework
- React team for the amazing UI library
- Open source community for various tools and libraries

---

<div align="center">

**Made with ❤️ for smarter task automation**

⭐ Star this repo if you find it helpful!

</div>
