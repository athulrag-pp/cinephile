# Cinephile — AI & Worldwide Streaming Movie Discovery Engine

An AI-powered multi-language movie discovery and recommendation platform built with **FastAPI** (Python backend) and modern **HTML/CSS/JS** (frontend). Integrates real-time IMDb movie metadata, live poster hydration, multi-language catalog support, and official streaming platform finder (**Netflix**, **Amazon Prime Video**, **Disney+ Hotstar**, **Apple TV+**, **Max**, **JioCinema**).

---

## 🌟 Key Features

- **AI & Multi-Language Movie Recommendations**: Intelligent mood & multi-genre recommendations powered by Anthropic Claude & IMDb.
- **Regional & Global Cinema**: Supports **Malayalam 🌴**, **Hindi 🇮🇳**, **Tamil 🎬**, **Korean 🇰🇷**, **Japanese 🇯🇵**, **Spanish 🇪🇸**, **French 🇫🇷**, and **English 🇺🇸**.
- **Verified Streaming Platforms ("Where to Watch")**: Direct 1-click links to stream on official platforms (*Netflix*, *Prime Video*, *Hotstar*, *JioCinema*, *Apple TV+*).
- **Interactive Card Redirect**: Click any movie card to open full movie detail pages directly on IMDb in your web browser.
- **Instant IMDb Live Search**: Query any worldwide movie title in real-time.
- **Personal Watchlist**: Save and manage favorite movies with poster thumbnails.

---

## 📁 Project Structure

```
cinephile/
├── backend/
│   ├── main.py              # FastAPI backend & IMDb data fetcher
│   ├── requirements.txt     # Python dependencies
│   └── .env.example         # Environment template
└── frontend/
    └── index.html           # Cinematic dark theme UI
```

---

## 🚀 Setup & Run Locally

### 1. Set up backend
```bash
cd backend
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --port 8005 --reload
```

### 2. Access the Application
Open `http://localhost:8005` in your browser!

---

*Built with passion by Athul Rag P P · B.Tech AI & Data Science*
