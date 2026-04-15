# TaskPilot AI Backend

Production-grade FastAPI backend with multi-agent task orchestration system.

## 🏗️ Architecture

```
TaskOrchestrator
 ├── FetcherAgent     → Data collection (DuckDuckGo, Wikipedia)
 ├── AnalyzerAgent    → Pure Python analysis (no LLM)
 ├── PlannerAgent     → LLM-based planning + rule-based fallback
 └── ReporterAgent    → LLM-based response + template fallback
```

### Agent Responsibilities

**FetcherAgent**
- Uses free, no-auth APIs (DuckDuckGo Search, Wikipedia)
- Normalizes external data into structured text
- Gracefully handles API failures
- NO LLM required

**AnalyzerAgent**
- Pure Python logic only
- Entity extraction, relevance scoring, question type detection
- Deterministic and explainable
- NO LLM required

**PlannerAgent**
- LLM-based task decomposition (Google Gemini)
- Falls back to rule-based planning if API unavailable
- Generates 3-6 ordered steps

**ReporterAgent**
- LLM-based response generation (Google Gemini)
- Falls back to template-based responses if API unavailable
- Always returns a valid response

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment (Optional)

```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY if you have one
```

**Note:** The backend works without any API keys. It will use fallback logic.

### 3. Run the Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Server will start at: `http://localhost:8000`

### 4. Run Chat Contract Quality Gate (Recommended)

Before shipping or deploying, run the regression suite for routing and response contracts:

```bash
cd backend
python -m unittest -v test_chat_response_contracts.py
```

This validates strict routing for factual/general/services queries and output formatting contracts.

## 📡 API Endpoints

### Sessions

- `POST /sessions` - Create new chat session
- `GET /sessions` - List all sessions
- `GET /sessions/{id}` - Get session with messages

### Messages

- `POST /messages` - Send text message
- `POST /voice` - Send voice transcript with optional screen context
- `POST /screen-context` - Store screen context for session

## 🔧 Configuration

All settings use `TASKPILOT_` prefix for environment variables:

```bash
TASKPILOT_APP_NAME=TaskPilot AI Backend
TASKPILOT_ENVIRONMENT=development
TASKPILOT_DATABASE_URL=sqlite+aiosqlite:///./taskpilot.db
TASKPILOT_LLM_PROVIDER=gemini
TASKPILOT_LLM_TIMEOUT_SECONDS=30
TASKPILOT_ORCHESTRATION_TIMEOUT_SECONDS=45
```

## 🔑 API Keys (Optional)

### Google Gemini

1. Get API key: https://makersuite.google.com/app/apikey
2. Set environment variable: `GEMINI_API_KEY=your_key_here`

**Without API key:** Planner and Reporter agents use rule-based and template-based fallbacks.

## 🗄️ Database

- **Development:** SQLite (default)
- **Location:** `./taskpilot.db`
- **Auto-init:** Tables created automatically on startup

### Models

- `UserSession` - Chat sessions
- `Message` - User and assistant messages
- `AgentStep` - Individual agent execution records
- `AgentResult` - Orchestration summaries

## 🧪 Testing the API

### Create Session

```bash
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Session"}'
```

### Send Message

```bash
curl -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your_session_id",
    "content": "What is artificial intelligence?"
  }'
```

### Send Voice Message

```bash
curl -X POST http://localhost:8000/voice \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your_session_id",
    "transcript": "Tell me about Python",
    "screen_context": "User is viewing Python documentation"
  }'
```

## 🔒 Error Handling

- **Timeout:** Orchestration has 45s timeout (configurable)
- **Failures:** Returns graceful fallback responses
- **No Stack Traces:** Client receives clean error messages
- **Agent Failures:** Individual agents fail silently, orchestration continues

## 📦 Dependencies

### Core
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `pydantic` - Data validation
- `sqlalchemy` - Database ORM
- `aiosqlite` - Async SQLite driver

### Agents
- `duckduckgo-search` - Web search (free, no auth)
- `wikipedia-api` - Wikipedia access (free, no auth)
- `google-generativeai` - Gemini API (optional)

## 🏭 Production Considerations

### Database Migration

Replace SQLite with PostgreSQL:

```python
TASKPILOT_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/taskpilot
```

All models are PostgreSQL-compatible.

### Environment Variables

Set all required variables in production environment:
- `GEMINI_API_KEY` (if using Gemini)
- `TASKPILOT_ENVIRONMENT=production`
- `TASKPILOT_DATABASE_URL=<production_db>`

### Rate Limiting

Add rate limiting middleware for production deployments.

### Logging

Configure structured logging for production observability.

## 🛠️ Development

### Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app entry
│   ├── api/
│   │   └── routes/          # API endpoints
│   ├── core/
│   │   └── config.py        # Settings
│   ├── db/                  # Database layer
│   │   ├── base.py
│   │   ├── session.py
│   │   └── init_db.py
│   ├── models/
│   │   └── db_models.py     # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   │   ├── messages.py
│   │   └── sessions.py
│   └── services/
│       ├── orchestrator.py  # Main orchestration
│       ├── agents/          # Agent implementations
│       │   ├── base.py
│       │   ├── fetcher.py
│       │   ├── analyzer.py
│       │   ├── planner.py
│       │   └── reporter.py
│       └── ai/              # LLM providers
│           ├── base.py
│           ├── factory.py
│           └── gemini.py
├── requirements.txt
└── .env.example
```

### Adding New Agents

1. Extend `BaseAgent` in `app/services/agents/`
2. Implement `async def run(self, context: AgentContext) -> AgentResultData`
3. Add to `TaskOrchestrator` pipeline in `orchestrator.py`

### Adding New LLM Providers

1. Extend `LLMProvider` in `app/services/ai/`
2. Implement `async def generate(self, prompt: str) -> str`
3. Update `get_provider()` in `factory.py`

## 📝 License

Part of TaskPilot AI project.
