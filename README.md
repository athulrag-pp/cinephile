# CineMatch — AI Movie Recommender

An AI-powered movie recommendation web app built with **FastAPI** (Python backend) and vanilla **HTML/CSS/JS** (frontend). Uses the **Anthropic Claude API** for intelligent, mood-based recommendations.

---

## Project Structure

```
cinematch/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── requirements.txt     # Python dependencies
│   └── .env.example         # Environment variable template
└── frontend/
    └── index.html           # Full frontend (single file)
```

---

## Setup & Run

### 1. Clone / download this project

### 2. Get your Anthropic API Key
Sign up at https://console.anthropic.com and copy your API key.

### 3. Set up the backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set your API key
cp .env.example .env
# Now open .env and replace "your_api_key_here" with your real key

# Run the server
uvicorn main:app --reload
```

Server runs at: http://localhost:8000

### 4. Open the frontend

Just open `frontend/index.html` in your browser. That's it!

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/recommend` | Get AI movie recommendations |
| GET | `/api/watchlist` | Fetch saved watchlist |
| POST | `/api/watchlist` | Add a movie to watchlist |
| DELETE | `/api/watchlist/{title}` | Remove from watchlist |
| GET | `/api/health` | Health check |

### Example Request

```bash
curl -X POST http://localhost:8000/api/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "mood": "cozy",
    "genres": ["Comedy", "Romance"],
    "language": "English"
  }'
```

---

## Features

- Mood-based recommendations (6 moods)
- Genre filtering (10 genres)
- Language preference (English, Hindi, Tamil, Malayalam, Korean, etc.)
- Custom free-text input
- Mood match percentage per movie
- Watchlist (save/remove movies)
- Clean dark cinematic UI

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI, Uvicorn |
| AI | Anthropic Claude API |
| Frontend | HTML5, CSS3, Vanilla JS |
| Fonts | DM Serif Display + DM Sans |

---

## Deployment (for resume)

**Backend** → Deploy on [Render](https://render.com) (free tier) or [Railway](https://railway.app)  
**Frontend** → Deploy on [GitHub Pages](https://pages.github.com) or [Vercel](https://vercel.com)  

Update the `const API = 'http://localhost:8000'` line in `index.html` to your deployed backend URL.

---

## Resume Talking Points

- Integrated LLM (Claude) via REST API with structured JSON output
- Built RESTful backend with FastAPI + Pydantic validation
- Implemented CORS, error handling, and in-memory state management
- Designed mood-aware prompt engineering for consistent AI responses
- Deployed full-stack app with separate frontend/backend architecture

---

*Built as a portfolio project · B.Tech AI & Data Science*
