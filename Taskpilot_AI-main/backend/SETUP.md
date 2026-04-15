# 🚀 Quick Setup Guide - TaskPilot AI Backend

## Step 1: Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

This installs all required packages including:
- FastAPI, Uvicorn (API framework)
- SQLAlchemy, aiosqlite (database)
- DuckDuckGo Search, Wikipedia (free data sources)
- Google Generative AI (Gemini API)

## Step 2: Verify Gemini API Configuration

The `.env` file is already configured with the development API key.

Run the verification script:

```bash
python verify_gemini.py
```

Expected output:
```
✅ API Key found: AIzaSyBwYp...xbM
✅ Library installed
✅ API Response received
✅ PlannerAgent: llm
✅ ReporterAgent: llm
✅ All Checks Passed!
```

## Step 3: Start the Backend Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Server will start at: `http://localhost:8000`

## Step 4: Test the API

### Create a Session

```bash
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d "{\"title\": \"Test Session\"}"
```

Copy the `session_id` from the response.

### Send a Message

```bash
curl -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"<your_session_id>\",
    \"content\": \"What is artificial intelligence?\"
  }"
```

You should receive an AI-generated response using:
- **FetcherAgent**: DuckDuckGo + Wikipedia search results
- **AnalyzerAgent**: Pure Python analysis of the query
- **PlannerAgent**: Gemini-powered task planning
- **ReporterAgent**: Gemini-powered response generation

## Step 5: Integrate with Frontend

Update frontend API base URL to point to `http://localhost:8000`

The backend is now fully operational with:
✅ Real Gemini AI integration
✅ External data fetching (DuckDuckGo, Wikipedia)
✅ Intelligent analysis and planning
✅ Structured response generation

---

## Troubleshooting

### "Library not installed" Error

```bash
pip install google-generativeai duckduckgo-search wikipedia-api
```

### "API Key not found" Error

Check that `.env` file exists in the backend directory with:
```
GEMINI_API_KEY=AIzaSyBwYp31i-pWcQy1qqts1UeKvFjm6WzAxbM
```

### "API Error" or Empty Responses

1. Check internet connection
2. Verify API key is valid
3. Check Gemini API quota/limits
4. Backend will automatically use fallback logic if API fails

### Agents Use Fallback Instead of Gemini

If you see "method": "rule-based" or "template" in responses:
- Gemini API key may be invalid or expired
- API quota may be exceeded
- Network issues preventing API access
- Backend still functions with fallback logic

---

## What's Running?

When the backend starts, you have:

1. **FastAPI Server** on port 8000
2. **SQLite Database** at `./taskpilot.db`
3. **4 AI Agents**:
   - FetcherAgent (DuckDuckGo + Wikipedia)
   - AnalyzerAgent (Python logic)
   - PlannerAgent (Gemini LLM + fallback)
   - ReporterAgent (Gemini LLM + fallback)

---

## API Endpoints

- `POST /sessions` - Create new session
- `GET /sessions` - List all sessions
- `GET /sessions/{id}` - Get session details
- `POST /messages` - Send text message
- `POST /voice` - Send voice transcript
- `POST /screen-context` - Store screen context

---

## Development Notes

- **Hot Reload**: Server auto-restarts on code changes
- **Database**: Auto-created on first run
- **Logs**: View in terminal with `--reload` flag
- **API Docs**: Visit `http://localhost:8000/docs`

---

## Security Note

The `.env` file contains a development API key for testing.
**DO NOT commit this file to public repositories.**

The `.gitignore` file is configured to prevent accidental commits.

---

Need help? Check:
- [README.md](README.md) - Full documentation
- [IMPLEMENTATION.md](IMPLEMENTATION.md) - Technical details
- [test_agents.py](test_agents.py) - Agent tests
