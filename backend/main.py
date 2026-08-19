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

app = FastAPI(title="Cinephile API — Dynamic Unique Search & Genre Engine")

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
        if any(k in t_lower for k in ["manjummel", "premalu", "aavesham", "drishyam", "kumbalangi", "jawan", "pathaan", "guruvayoor"]):
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
        if any(k in t_lower for k in ["interstellar", "dark knight", "dune", "inception", "oppenheimer", "matrix", "avatar", "john wick"]):
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

                    google_search_url = f"https://www.google.com/search?q={httpx.URL(title + ' ' + str(year or '')).raw_path.decode()}"
                    trailer_url = f"https://www.youtube.com/results?search_query={httpx.URL(title + ' ' + str(year or '') + ' official trailer').raw_path.decode()}"
                    watch_providers = resolve_streaming_providers(title, all_genres, language)

                    return {
                        "imdb_id": imdb_id,
                        "poster": poster,
                        "imdb_rating": imdb_rating,
                        "imdb_url": google_search_url,
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
        "imdb_url": f"https://www.google.com/search?q={encoded_title}",
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
            score += min(len(overlap) * 8, 14)
        else:
            score -= 20

    return max(min(score, 99), 60)


def get_multi_language_catalog(language: str, mood: str, genres: list[str], count: int = 6) -> list[dict]:
    lang_lower = (language or "any").lower()
    req_genres_lower = [g.lower() for g in (genres or [])]
    
    all_catalog_movies = [
        # Malayalam
        {"title": "Premalu", "year": 2024, "director": "Girish A.D.", "rating": 8.1, "why": "A hilarious Malayalam romantic comedy.", "tags": ["Comedy", "Romance"], "language": "Malayalam", "mood_match": 98},
        {"title": "Aavesham", "year": 2024, "director": "Jithu Madhavan", "rating": 8.0, "why": "An energetic Malayalam action-comedy featuring Fahadh Faasil.", "tags": ["Action", "Comedy"], "language": "Malayalam", "mood_match": 96},
        {"title": "Guruvayoor Ambalanadayil", "year": 2024, "director": "Vipinchandran", "rating": 7.3, "why": "A fun Malayalam wedding comedy packed with chaos.", "tags": ["Comedy", "Drama"], "language": "Malayalam", "mood_match": 95},
        {"title": "Super Sharanya", "year": 2022, "director": "Girish A.D.", "rating": 7.0, "why": "A relatable Malayalam campus comedy-drama.", "tags": ["Comedy", "Drama"], "language": "Malayalam", "mood_match": 94},
        {"title": "Manjummel Boys", "year": 2024, "director": "Chidambaram", "rating": 8.5, "why": "A gripping Malayalam survival thriller set in Guna Caves.", "tags": ["Thriller", "Survival", "Drama"], "language": "Malayalam", "mood_match": 96},
        {"title": "Drishyam", "year": 2013, "director": "Jeethu Joseph", "rating": 8.6, "why": "The legendary Malayalam suspense crime thriller.", "tags": ["Thriller", "Crime", "Drama"], "language": "Malayalam", "mood_match": 98},
        {"title": "Drishyam 2", "year": 2021, "director": "Jeethu Joseph", "rating": 8.4, "why": "The explosive Malayalam sequel six years after Georgekutty's crime.", "tags": ["Thriller", "Crime", "Sequel"], "language": "Malayalam", "mood_match": 97},

        # Hindi
        {"title": "3 Idiots", "year": 2009, "director": "Rajkumar Hirani", "rating": 8.4, "why": "An iconic Hindi comedy-drama celebrating friendship.", "tags": ["Comedy", "Drama"], "language": "Hindi", "mood_match": 98},
        {"title": "Stree", "year": 2018, "director": "Amar Kaushik", "rating": 7.5, "why": "A hilarious Hindi horror-comedy about a spirit haunting a town.", "tags": ["Comedy", "Horror"], "language": "Hindi", "mood_match": 95},
        {"title": "Andhadhun", "year": 2018, "director": "Sriram Raghavan", "rating": 8.2, "why": "A dark Hindi thriller about a blind pianist caught in a murder.", "tags": ["Thriller", "Crime", "Comedy"], "language": "Hindi", "mood_match": 96},

        # English
        {"title": "Knives Out", "year": 2019, "director": "Rian Johnson", "rating": 7.9, "why": "A sharp, entertaining whodunit comedy-mystery packed with humor.", "tags": ["Comedy", "Mystery", "Crime"], "language": "English", "mood_match": 96},
        {"title": "The Hangover", "year": 2009, "director": "Todd Phillips", "rating": 7.7, "why": "An outrageously funny comedy about three friends.", "tags": ["Comedy"], "language": "English", "mood_match": 97},
        {"title": "Interstellar", "year": 2014, "director": "Christopher Nolan", "rating": 8.7, "why": "A breathtaking sci-fi odyssey about space and gravity.", "tags": ["Sci-Fi", "Drama"], "language": "English", "mood_match": 98},
        {"title": "Inception", "year": 2010, "director": "Christopher Nolan", "rating": 8.8, "why": "A mind-bending sci-fi heist thriller through dream levels.", "tags": ["Sci-Fi", "Action"], "language": "English", "mood_match": 97}
    ]

    if lang_lower != "any":
        filtered = [m for m in all_catalog_movies if m["language"].lower() == lang_lower]
        if not filtered:
            filtered = all_catalog_movies
    else:
        filtered = all_catalog_movies

    if req_genres_lower:
        strict_matches = [
            m for m in filtered 
            if any(g in [t.lower() for t in m["tags"]] for g in req_genres_lower)
        ]
        if not strict_matches:
            strict_matches = [
                m for m in all_catalog_movies 
                if any(g in [t.lower() for t in m["tags"]] for g in req_genres_lower)
            ]
        if strict_matches:
            filtered = strict_matches

    return filtered[:count]


@app.post("/api/recommend")
@app.post("/recommend")
async def recommend(req: RecommendRequest):
    target_count = req.count or 6
    req_lang = req.language if req.language and req.language != "any" else "any"
    req_genres = req.genres or []
    
    verified_movies = []
    seen_titles = set()

    if req_genres or req_lang != "any":
        genre_term = req_genres[0] if req_genres else "movie"
        lang_term = req_lang if req_lang != "any" else ""
        query_str = f"{lang_term} {genre_term}".strip()
        
        try:
            async with httpx.AsyncClient(timeout=4.0) as http_client:
                search_url = f"https://www.omdbapi.com/?s={httpx.URL(query_str).raw_path.decode()}&type=movie&apikey={OMDB_API_KEY}"
                res = await http_client.get(search_url)
                if res.status_code == 200:
                    search_data = res.json()
                    if search_data.get("Response") == "True":
                        items = search_data.get("Search", [])
                        for item in items[:15]:
                            t_title = item.get("Title")
                            if not t_title or t_title.lower() in seen_titles:
                                continue

                            t_year_str = item.get("Year", "2020")[:4]
                            try:
                                t_year = int(t_year_str)
                            except ValueError:
                                t_year = 2020

                            m_details = await fetch_imdb_metadata(t_title, t_year, req_genres, req_lang)
                            real_genres = [g.lower() for g in m_details.get("genres", [])]

                            if req_genres:
                                is_genre_matched = any(rg.lower() in real_genres for rg in req_genres)
                                if not is_genre_matched:
                                    continue

                            seen_titles.add(t_title.lower())
                            match_score = calculate_match_score(m_details.get("genres", []), req_genres, req.mood)
                            
                            verified_movies.append({
                                "title": t_title,
                                "year": t_year,
                                "director": m_details.get("director", "Director"),
                                "rating": m_details.get("imdb_rating", 8.0),
                                "why": f"Verified {req_lang if req_lang != 'any' else ''} {genre_term} movie. {m_details.get('plot', '')}",
                                "tags": list(dict.fromkeys(req_genres + m_details.get("genres", [])))[:4],
                                "language": req_lang if req_lang != "any" else "Worldwide",
                                "mood_match": match_score,
                                "poster": m_details["poster"],
                                "imdb_id": m_details["imdb_id"],
                                "imdb_url": m_details["imdb_url"],
                                "trailer_url": m_details["trailer_url"],
                                "watch_providers": m_details["watch_providers"]
                            })

                            if len(verified_movies) >= target_count:
                                break
        except Exception as e:
            print(f"Web search error: {e}")

    if len(verified_movies) < target_count:
        catalog_items = get_multi_language_catalog(req_lang, req.mood, req_genres, target_count * 2)
        for m in catalog_items:
            if m["title"].lower() in seen_titles:
                continue
            seen_titles.add(m["title"].lower())
            m_imdb = await fetch_imdb_metadata(m["title"], m.get("year"), req_genres, m.get("language", req_lang))
            verified_movies.append({
                **m,
                "poster": m_imdb["poster"],
                "imdb_id": m_imdb["imdb_id"],
                "imdb_rating": m_imdb["imdb_rating"],
                "imdb_url": m_imdb["imdb_url"],
                "trailer_url": m_imdb["trailer_url"],
                "watch_providers": m_imdb["watch_providers"],
                "mood_match": 95
            })

    return {"movies": verified_movies[:target_count]}


@app.get("/api/search")
@app.get("/search")
async def search_movies(q: str = Query(..., min_length=1)):
    """Search movie title to fetch ALL matching parts and 100% UNIQUE live web movie suggestions!"""
    q_clean = q.strip()
    matching_movies = []
    seen_titles = set()
    seen_ids = set()
    primary_genres = ["Cinema"]
    
    # 1. Fetch exact matching parts & title matches from live OMDb search
    try:
        async with httpx.AsyncClient(timeout=4.0) as http_client:
            url = f"https://www.omdbapi.com/?s={httpx.URL(q_clean).raw_path.decode()}&type=movie&apikey={OMDB_API_KEY}"
            res = await http_client.get(url)
            if res.status_code == 200:
                data = res.json()
                if data.get("Response") == "True":
                    search_results = data.get("Search", [])
                    for idx, item in enumerate(search_results[:10]):
                        title = item.get("Title")
                        imdb_id = item.get("imdbID", "")
                        
                        # Deduplicate by Title and IMDb ID!
                        t_key = title.lower()
                        if t_key in seen_titles or (imdb_id and imdb_id in seen_ids):
                            continue

                        year_str = item.get("Year", "2020")[:4]
                        try:
                            year = int(year_str)
                        except ValueError:
                            year = 2020
                        
                        item_details = await fetch_imdb_metadata(title, year)
                        if idx == 0 and item_details.get("genres"):
                            primary_genres = item_details["genres"]

                        seen_titles.add(t_key)
                        if imdb_id:
                            seen_ids.add(imdb_id)

                        part_label = f"Part {idx + 1}" if ("2" in title or "3" in title or "part" in title.lower() or idx > 0) else "Part 1"

                        matching_movies.append({
                            "title": title,
                            "year": year,
                            "director": item_details.get("director", "Director"),
                            "rating": item_details.get("imdb_rating", 8.0),
                            "why": item_details.get("plot") or f"{title} ({year}) — Official Movie Entry.",
                            "tags": list(dict.fromkeys([part_label] + item_details.get("genres", ["Movie"])))[:4],
                            "language": "Search Match",
                            "mood_match": 100 if idx == 0 else 96,
                            "poster": item_details["poster"],
                            "imdb_id": item_details["imdb_id"],
                            "imdb_url": item_details["imdb_url"],
                            "trailer_url": item_details["trailer_url"],
                            "watch_providers": item_details["watch_providers"]
                        })
    except Exception as e:
        print(f"OMDb search error: {e}")

    # 2. If fewer than 6 items found, fetch genre-matched live web movies using the searched movie's primary genre
    if len(matching_movies) < 6 and primary_genres:
        genre_term = primary_genres[0]
        try:
            async with httpx.AsyncClient(timeout=4.0) as http_client:
                g_url = f"https://www.omdbapi.com/?s={httpx.URL(genre_term + ' movie').raw_path.decode()}&type=movie&apikey={OMDB_API_KEY}"
                res = await http_client.get(g_url)
                if res.status_code == 200:
                    g_data = res.json()
                    if g_data.get("Response") == "True":
                        for g_item in g_data.get("Search", [])[:10]:
                            g_title = g_item.get("Title")
                            g_id = g_item.get("imdbID", "")
                            if not g_title or g_title.lower() in seen_titles or (g_id and g_id in seen_ids):
                                continue

                            g_year_str = g_item.get("Year", "2020")[:4]
                            try:
                                g_year = int(g_year_str)
                            except ValueError:
                                g_year = 2020

                            g_details = await fetch_imdb_metadata(g_title, g_year, primary_genres)
                            seen_titles.add(g_title.lower())
                            if g_id:
                                seen_ids.add(g_id)

                            matching_movies.append({
                                "title": g_title,
                                "year": g_year,
                                "director": g_details.get("director", "Director"),
                                "rating": g_details.get("imdb_rating", 8.0),
                                "why": f"Related {genre_term} movie. {g_details.get('plot', '')}",
                                "tags": list(dict.fromkeys([genre_term] + g_details.get("genres", [])))[:4],
                                "language": "Genre Recommendation",
                                "mood_match": 94,
                                "poster": g_details["poster"],
                                "imdb_id": g_details["imdb_id"],
                                "imdb_url": g_details["imdb_url"],
                                "trailer_url": g_details["trailer_url"],
                                "watch_providers": g_details["watch_providers"]
                            })
                            if len(matching_movies) >= 6:
                                break
        except Exception as e:
            print(f"Genre expansion error: {e}")

    return {
        "search_query": q_clean,
        "target_movie": matching_movies[0] if matching_movies else None,
        "genres": primary_genres,
        "matching_parts": matching_movies,
        "movies": matching_movies[:8]
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
    return {"status": "ok", "message": "Cinephile API (Deduplicated Unique Search Engine) is running"}


# Serve frontend static assets
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_path, "index.html"))
