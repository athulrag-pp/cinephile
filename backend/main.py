from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
import anthropic
import httpx
import json
import os

load_dotenv()

app = FastAPI(title="Cinephile API — Multi-Language & Genre-Matched Search Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key = os.getenv("ANTHROPIC_API_KEY", "")
client = anthropic.Anthropic(api_key=api_key) if api_key and api_key != "your_api_key_here" else None

OMDB_API_KEY = os.getenv("OMDB_API_KEY", "trilogy")


class RecommendRequest(BaseModel):
    mood: Optional[str] = ""
    genres: Optional[list[str]] = []
    custom: Optional[str] = ""
    language: Optional[str] = "any"
    count: Optional[int] = 6


class WatchlistItem(BaseModel):
    title: str
    year: int
    tags: list[str]
    poster: Optional[str] = ""
    imdb_rating: Optional[float] = 8.0
    imdb_url: Optional[str] = ""
    watch_providers: Optional[list[str]] = []
    language: Optional[str] = "English"


# In-memory watchlist
watchlist: list[dict] = []


def resolve_streaming_providers(title: str, genres: list[str], language: str = "English") -> list[str]:
    """Determine streaming platforms (Netflix, Prime Video, Disney+, Apple TV, Max, Hotstar, JioCinema) based on movie & language."""
    t_lower = title.lower()
    providers = []

    if language.lower() in ["malayalam", "tamil", "telugu", "hindi"]:
        if any(k in t_lower for k in ["manjummel", "premalu", "aavesham", "drishyam", "kumbalangi", "jawan", "pathaan"]):
            providers.extend(["Disney+", "Hotstar", "Netflix"])
        elif any(k in t_lower for k in ["kishkindha", "kannur squad", "bramayugam", "minnal", "minnal murali"]):
            providers.extend(["Netflix", "JioCinema"])
        else:
            providers.extend(["Hotstar", "Prime Video", "Netflix"])
    elif language.lower() in ["korean", "japanese"]:
        if any(k in t_lower for k in ["parasite", "squid", "train to busan", "spirited away", "your name"]):
            providers.extend(["Netflix", "Prime Video"])
        else:
            providers.extend(["Netflix", "Apple TV"])
    else:
        if any(k in t_lower for k in ["interstellar", "dark knight", "dune", "inception", "oppenheimer", "matrix"]):
            providers.extend(["Max", "Prime Video", "Apple TV"])
        elif "Sci-Fi" in genres or "Action" in genres:
            providers.extend(["Max", "Prime Video"])
        elif "Animation" in genres:
            providers.extend(["Disney+", "Netflix"])
        else:
            providers.extend(["Netflix", "Prime Video"])

    return list(dict.fromkeys(providers))[:3]


async def fetch_imdb_metadata(title: str, year: Optional[int] = None, requested_genres: Optional[list[str]] = None, language: str = "English") -> dict:
    """Fetch real-time IMDb metadata (poster, imdbID, rating, plot, genres) and streaming availability."""
    genres_list = requested_genres or []
    try:
        async with httpx.AsyncClient(timeout=4.0) as http_client:
            url = f"https://www.omdbapi.com/?t={httpx.URL(title).raw_path.decode()}&apikey={OMDB_API_KEY}"
            if year:
                url += f"&y={year}"
            
            res = await http_client.get(url)
            if res.status_code == 200:
                data = res.json()
                if data.get("Response") == "True":
                    imdb_id = data.get("imdbID", "")
                    rating_str = data.get("imdbRating", "N/A")
                    try:
                        imdb_rating = float(rating_str)
                    except ValueError:
                        imdb_rating = 8.0

                    poster = data.get("Poster", "")
                    if poster == "N/A" or not poster.startswith("http"):
                        poster = f"https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=600&q=80"

                    imdb_genres = [g.strip() for g in data.get("Genre", "").split(",") if g.strip()]
                    all_genres = list(dict.fromkeys(imdb_genres + genres_list))

                    imdb_url = f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else f"https://www.imdb.com/find/?q={httpx.URL(title).raw_path.decode()}"
                    trailer_url = f"https://www.youtube.com/results?search_query={httpx.URL(title + ' ' + str(year or '') + ' official trailer').raw_path.decode()}"
                    watch_providers = resolve_streaming_providers(title, all_genres, language)

                    return {
                        "imdb_id": imdb_id,
                        "poster": poster,
                        "imdb_rating": imdb_rating,
                        "imdb_url": imdb_url,
                        "trailer_url": trailer_url,
                        "plot": data.get("Plot", ""),
                        "director": data.get("Director", "Director"),
                        "genres": all_genres,
                        "watch_providers": watch_providers,
                        "year": data.get("Year", year or 2020)
                    }
    except Exception as e:
        print(f"IMDb fetch error for {title}: {e}")

    encoded_title = title.replace(' ', '+')
    watch_providers = resolve_streaming_providers(title, genres_list, language)
    return {
        "imdb_id": "",
        "poster": "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=600&q=80",
        "imdb_rating": 8.1,
        "imdb_url": f"https://www.imdb.com/find/?q={encoded_title}",
        "trailer_url": f"https://www.youtube.com/results?search_query={encoded_title}+official+trailer",
        "plot": "",
        "director": "Director",
        "genres": genres_list or ["Cinema"],
        "watch_providers": watch_providers,
        "year": year or 2020
    }


def calculate_match_score(movie_genres: list[str], req_genres: list[str], mood: str) -> int:
    score = 78
    if mood:
        score += 8
    
    if req_genres and movie_genres:
        overlap = set(g.lower() for g in movie_genres).intersection(set(g.lower() for g in req_genres))
        if overlap:
            score += min(len(overlap) * 6, 12)

    return min(score, 99)


def get_multi_language_catalog(language: str, mood: str, genres: list[str], count: int = 6) -> list[dict]:
    lang_lower = (language or "any").lower()
    
    malayalam_movies = [
        {"title": "Manjummel Boys", "year": 2024, "director": "Chidambaram", "rating": 8.5, "why": "A gripping survival thriller about brotherhood, bravery, and friendship set in Guna Caves.", "tags": ["Thriller", "Survival", "Drama"], "language": "Malayalam", "mood_match": 98},
        {"title": "Drishyam", "year": 2013, "director": "Jeethu Joseph", "rating": 8.6, "why": "A legendary suspense crime thriller about a family man protecting his loved ones.", "tags": ["Thriller", "Crime", "Drama"], "language": "Malayalam", "mood_match": 97},
        {"title": "Premalu", "year": 2024, "director": "Girish A.D.", "rating": 8.1, "why": "A hilarious and heartwarming romantic comedy that keeps you smiling throughout.", "tags": ["Comedy", "Romance"], "language": "Malayalam", "mood_match": 95},
        {"title": "Aavesham", "year": 2024, "director": "Jithu Madhavan", "rating": 8.0, "why": "An energetic action-comedy featuring Fahadh Faasil as an eccentric gangster.", "tags": ["Action", "Comedy"], "language": "Malayalam", "mood_match": 96},
        {"title": "Kishkindha Kaandam", "year": 2024, "director": "Dinjith Ayyathan", "rating": 8.4, "why": "A brilliant mystery drama packed with subtle suspense, monkeys, and hidden secrets.", "tags": ["Mystery", "Thriller", "Drama"], "language": "Malayalam", "mood_match": 96},
        {"title": "Kumbalangi Nights", "year": 2019, "director": "Madhu C. Narayanan", "rating": 8.5, "why": "A soulful, beautifully crafted masterpiece about four dysfunctional brothers.", "tags": ["Drama", "Comedy", "Romance"], "language": "Malayalam", "mood_match": 97},
        {"title": "Anjaam Pathiraa", "year": 2020, "director": "Midhun Manuel Thomas", "rating": 7.9, "why": "A chilling psychological serial killer thriller with relentless twists.", "tags": ["Thriller", "Crime", "Mystery"], "language": "Malayalam", "mood_match": 94},
        {"title": "Minnal Murali", "year": 2021, "director": "Basil Joseph", "rating": 7.8, "why": "A charming superhero tale rooted in a small Kerala village with heart and humor.", "tags": ["Action", "Sci-Fi", "Comedy"], "language": "Malayalam", "mood_match": 93}
    ]

    hindi_movies = [
        {"title": "3 Idiots", "year": 2009, "director": "Rajkumar Hirani", "rating": 8.4, "why": "An iconic comedy-drama questioning education systems while celebrating friendship.", "tags": ["Comedy", "Drama"], "language": "Hindi", "mood_match": 98},
        {"title": "Andhadhun", "year": 2018, "director": "Sriram Raghavan", "rating": 8.2, "why": "A dark thriller about a blind pianist caught in a murder conspiracy.", "tags": ["Thriller", "Crime", "Comedy"], "language": "Hindi", "mood_match": 96},
        {"title": "Tumbbad", "year": 2018, "director": "Rahi Anil Barve", "rating": 8.2, "why": "A visually stunning mythological horror thriller exploring greed and curse.", "tags": ["Horror", "Fantasy", "Thriller"], "language": "Hindi", "mood_match": 95},
        {"title": "Dangal", "year": 2016, "director": "Nitesh Tiwari", "rating": 8.3, "why": "An inspiring biographical sports drama about a father training his daughters.", "tags": ["Drama", "Biography", "Action"], "language": "Hindi", "mood_match": 97},
        {"title": "Stree", "year": 2018, "director": "Amar Kaushik", "rating": 7.5, "why": "A hilarious horror-comedy about a mysterious spirit haunting a town.", "tags": ["Comedy", "Horror"], "language": "Hindi", "mood_match": 93},
        {"title": "Chhichhore", "year": 2019, "director": "Nitesh Tiwari", "rating": 8.3, "why": "A heartwarming nostalgic college drama celebrating life and friendship.", "tags": ["Comedy", "Drama"], "language": "Hindi", "mood_match": 94}
    ]

    tamil_movies = [
        {"title": "Vikram", "year": 2022, "director": "Lokesh Kanagaraj", "rating": 8.3, "why": "A high-octane action thriller featuring Kamal Haasan, Vijay Sethupathi, and Fahadh Faasil.", "tags": ["Action", "Thriller", "Crime"], "language": "Tamil", "mood_match": 97},
        {"title": "Jai Bhim", "year": 2021, "director": "T. J. Gnanavel", "rating": 8.8, "why": "A powerful court drama fighting for tribal rights and justice.", "tags": ["Drama", "Crime"], "language": "Tamil", "mood_match": 98},
        {"title": "Super Deluxe", "year": 2019, "director": "Thiagarajan Kumararaja", "rating": 8.3, "why": "An eccentric multi-narrative masterpiece exploring life, destiny, and morality.", "tags": ["Comedy", "Drama", "Crime"], "language": "Tamil", "mood_match": 96},
        {"title": "Kaithi", "year": 2019, "director": "Lokesh Kanagaraj", "rating": 8.5, "why": "A relentless night-long action thriller about an ex-convict helping cops.", "tags": ["Action", "Thriller"], "language": "Tamil", "mood_match": 95}
    ]

    korean_movies = [
        {"title": "Parasite", "year": 2019, "director": "Bong Joon-ho", "rating": 8.5, "why": "A Oscar-winning dark social thriller with gripping twists and satire.", "tags": ["Thriller", "Drama", "Crime"], "language": "Korean", "mood_match": 98},
        {"title": "Train to Busan", "year": 2016, "director": "Yeon Sang-ho", "rating": 7.6, "why": "An intense, emotional zombie action thriller set aboard a speeding train.", "tags": ["Action", "Horror", "Thriller"], "language": "Korean", "mood_match": 95},
        {"title": "Memories of Murder", "year": 2003, "director": "Bong Joon-ho", "rating": 8.1, "why": "A masterclass crime investigation thriller based on real events.", "tags": ["Crime", "Drama", "Thriller"], "language": "Korean", "mood_match": 96},
        {"title": "Oldboy", "year": 2003, "director": "Park Chan-wook", "rating": 8.4, "why": "A neo-noir revenge thriller famous for its hallway fight and twist ending.", "tags": ["Action", "Mystery", "Thriller"], "language": "Korean", "mood_match": 97}
    ]

    english_movies = [
        {"title": "Interstellar", "year": 2014, "director": "Christopher Nolan", "rating": 8.7, "why": "A breathtaking sci-fi odyssey about space, gravity, and human love.", "tags": ["Sci-Fi", "Drama", "Adventure"], "language": "English", "mood_match": 98},
        {"title": "Inception", "year": 2010, "director": "Christopher Nolan", "rating": 8.8, "why": "A mind-bending heist thriller through subconscious dream levels.", "tags": ["Sci-Fi", "Action", "Thriller"], "language": "English", "mood_match": 97},
        {"title": "Spirited Away", "year": 2001, "director": "Hayao Miyazaki", "rating": 8.6, "why": "An enchanting Studio Ghibli fantasy offering rich atmosphere and warmth.", "tags": ["Animation", "Fantasy", "Adventure"], "language": "Japanese", "mood_match": 95},
        {"title": "Knives Out", "year": 2019, "director": "Rian Johnson", "rating": 7.9, "why": "A sharp, entertaining whodunit mystery packed with humor.", "tags": ["Comedy", "Mystery", "Thriller"], "language": "English", "mood_match": 91},
        {"title": "Dune: Part Two", "year": 2024, "director": "Denis Villeneuve", "rating": 8.6, "why": "An epic cinematic spectacle with grand visuals and intense sci-fi world-building.", "tags": ["Sci-Fi", "Action", "Adventure"], "language": "English", "mood_match": 97}
    ]

    if "malayalam" in lang_lower:
        results = malayalam_movies
    elif "hindi" in lang_lower:
        results = hindi_movies
    elif "tamil" in lang_lower:
        results = tamil_movies
    elif "korean" in lang_lower:
        results = korean_movies
    else:
        results = english_movies

    return results[:count]


@app.post("/api/recommend")
@app.post("/recommend")
async def recommend(req: RecommendRequest):
    parts = []
    if req.mood:
        parts.append(f"mood: {req.mood}")
    if req.genres:
        parts.append(f"genres: {', '.join(req.genres)}")
    if req.custom:
        parts.append(f"extra context: {req.custom}")
    if req.language and req.language != "any":
        parts.append(f"language preference: {req.language}")

    if not parts:
        raise HTTPException(status_code=400, detail="Provide at least one preference.")

    raw_movies = []
    target_count = req.count or 6

    if client:
        prompt = f"""Recommend exactly {target_count} movies worldwide matching these user preferences — {'; '.join(parts)}.

Return ONLY a valid JSON array, no markdown, no explanation:
[
  {{
    "title": "Movie Title",
    "year": 2020,
    "director": "Director Name",
    "rating": 8.2,
    "why": "One warm, specific sentence explaining why this fits perfectly.",
    "tags": ["tag1", "tag2", "tag3"],
    "language": "Language",
    "mood_match": 92
  }}
]

mood_match is an integer 0-100 representing how well the movie matches the given mood."""

        try:
            message = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )
            text = message.content[0].text
            clean = text.replace("```json", "").replace("```", "").strip()
            raw_movies = json.loads(clean)
        except Exception as e:
            print(f"API call error: {e}, falling back to multi-language catalog.")
            raw_movies = get_multi_language_catalog(req.language or "any", req.mood, req.genres, target_count)
    else:
        raw_movies = get_multi_language_catalog(req.language or "any", req.mood, req.genres, target_count)

    hydrated_movies = []
    for m in raw_movies:
        title = m.get("title", "")
        year = m.get("year", None)
        movie_tags = m.get("tags", [])
        movie_lang = m.get("language", req.language if req.language != "any" else "English")
        
        imdb_data = await fetch_imdb_metadata(title, year, req.genres, movie_lang)
        match_score = calculate_match_score(imdb_data["genres"] or movie_tags, req.genres, req.mood)
        
        movie_item = {
            **m,
            "poster": imdb_data["poster"],
            "imdb_id": imdb_data["imdb_id"],
            "imdb_rating": imdb_data["imdb_rating"] or m.get("rating", 8.0),
            "imdb_url": imdb_data["imdb_url"],
            "trailer_url": imdb_data["trailer_url"],
            "plot": imdb_data["plot"] or m.get("why", ""),
            "director": imdb_data["director"] if imdb_data["director"] != "Director" else m.get("director", "Director"),
            "tags": list(dict.fromkeys(movie_tags + imdb_data["genres"]))[:4],
            "language": movie_lang,
            "watch_providers": imdb_data["watch_providers"],
            "mood_match": match_score
        }
        hydrated_movies.append(movie_item)

    return {"movies": hydrated_movies}


@app.get("/api/search")
@app.get("/search")
async def search_movies(q: str = Query(..., min_length=1)):
    """Search target movie AND auto-suggest related movies matching its exact genre!"""
    target_data = await fetch_imdb_metadata(q)
    target_title = q
    target_genres = target_data["genres"] or ["Cinema"]
    
    # Try fetching exact match metadata from OMDb
    try:
        async with httpx.AsyncClient(timeout=4.0) as http_client:
            res = await http_client.get(f"https://www.omdbapi.com/?t={httpx.URL(q).raw_path.decode()}&apikey={OMDB_API_KEY}")
            if res.status_code == 200:
                data = res.json()
                if data.get("Response") == "True":
                    target_title = data.get("Title", q)
                    g_raw = data.get("Genre", "")
                    if g_raw:
                        target_genres = [g.strip() for g in g_raw.split(",") if g.strip()]
    except Exception as e:
        print(f"Target movie search fetch error: {e}")

    # Build target movie response item
    target_movie = {
        "title": target_title,
        "year": target_data.get("year", 2020),
        "director": target_data.get("director", "Director"),
        "rating": target_data.get("imdb_rating", 8.2),
        "why": f"Exact match for '{target_title}'. {target_data.get('plot', '')}",
        "tags": target_genres,
        "language": "Exact Match",
        "mood_match": 100,
        "poster": target_data["poster"],
        "imdb_id": target_data["imdb_id"],
        "imdb_url": target_data["imdb_url"],
        "trailer_url": target_data["trailer_url"],
        "watch_providers": target_data["watch_providers"]
    }

    # Fetch 5 Related movies matching the target movie's exact genres!
    raw_related = []
    if client:
        prompt = f"""Target movie: "{target_title}" with genres: {', '.join(target_genres)}.
Recommend 5 top-rated worldwide movies that share the exact same genre ({', '.join(target_genres)}) and feel similar to "{target_title}".

Return ONLY a valid JSON array, no markdown:
[
  {{
    "title": "Movie Title",
    "year": 2020,
    "director": "Director Name",
    "rating": 8.3,
    "why": "One sentence explaining why it shares the exact genre and vibe of {target_title}.",
    "tags": ["{target_genres[0] if target_genres else 'Cinema'}"],
    "language": "English",
    "mood_match": 95
  }}
]"""
        try:
            message = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1200,
                messages=[{"role": "user", "content": prompt}]
            )
            text = message.content[0].text
            clean = text.replace("```json", "").replace("```", "").strip()
            raw_related = json.loads(clean)
        except Exception as e:
            print(f"AI related query error: {e}")
            raw_related = get_multi_language_catalog("any", "adventurous", target_genres, 5)
    else:
        raw_related = get_multi_language_catalog("any", "adventurous", target_genres, 5)

    # Hydrate related movies with posters & IMDb data
    related_movies = []
    for m in raw_related:
        r_title = m.get("title", "")
        r_year = m.get("year", None)
        if r_title.lower() == target_title.lower():
            continue
            
        r_imdb = await fetch_imdb_metadata(r_title, r_year, target_genres)
        related_movies.append({
            **m,
            "poster": r_imdb["poster"],
            "imdb_id": r_imdb["imdb_id"],
            "imdb_rating": r_imdb["imdb_rating"] or m.get("rating", 8.0),
            "imdb_url": r_imdb["imdb_url"],
            "trailer_url": r_imdb["trailer_url"],
            "plot": r_imdb["plot"] or m.get("why", ""),
            "director": r_imdb["director"] if r_imdb["director"] != "Director" else m.get("director", "Director"),
            "tags": list(dict.fromkeys((m.get("tags", []) + r_imdb["genres"] + target_genres)))[:4],
            "watch_providers": r_imdb["watch_providers"],
            "mood_match": 94
        })

    return {
        "target_movie": target_movie,
        "genres": target_genres,
        "movies": [target_movie] + related_movies
    }


@app.get("/api/watchlist")
@app.get("/watchlist")
async def get_watchlist():
    return {"watchlist": watchlist}


@app.post("/api/watchlist")
@app.post("/watchlist")
async def add_to_watchlist(item: WatchlistItem):
    if any(m["title"] == item.title for m in watchlist):
        return {"message": "Already in watchlist", "watchlist": watchlist}
    watchlist.append(item.dict())
    return {"message": "Added!", "watchlist": watchlist}


@app.delete("/api/watchlist/{title}")
@app.delete("/watchlist/{title}")
async def remove_from_watchlist(title: str):
    global watchlist
    watchlist = [m for m in watchlist if m["title"] != title]
    return {"message": "Removed", "watchlist": watchlist}


@app.get("/api/health")
@app.get("/health")
async def health():
    return {"status": "ok", "message": "Cinephile API (Genre-Matched Search Engine) is running"}


# Serve frontend static assets
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_path, "index.html"))
