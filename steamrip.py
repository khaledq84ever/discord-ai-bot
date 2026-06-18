"""SteamRIP game scraper — fetches game listings + Steam images.

Data source: the public GitHub JSON mirror (updated regularly).
Images: Steam Store search API -> CDN header image.
"""

import re
import json
import logging
from typing import Optional

import aiohttp

GAMES_JSON_URL = (
    "https://raw.githubusercontent.com/7ROBE/SteamRip-Json/main/steamrip_games.json"
)
STEAM_SEARCH_URL = "https://store.steampowered.com/api/storesearch"
STEAM_CDN = "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg"

log = logging.getLogger("steamrip")


def _clean_title(title: str) -> str:
    """Strip version/download suffix from a game title for Steam search."""
    cleaned = re.sub(
        r"\s*(Free Download|\(.*?\)|v[\d.]+\w*|Build\s+\w+|\[.*?\])\s*",
        "", title, flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+-\s+.*", "", cleaned)
    return cleaned.strip()


async def fetch_games(session: aiohttp.ClientSession) -> list[dict]:
    """Download and parse the SteamRIP games JSON."""
    async with session.get(GAMES_JSON_URL, timeout=aiohttp.ClientTimeout(total=20)) as resp:
        if resp.status != 200:
            raise RuntimeError(f"Failed to fetch games JSON: HTTP {resp.status}")
        data = json.loads(await resp.text())
    return data.get("downloads", [])


async def search_steam_image(session: aiohttp.ClientSession, title: str) -> Optional[str]:
    """Search Steam store for a game and return its header image URL."""
    cleaned = _clean_title(title)
    if not cleaned:
        return None
    params = {"term": cleaned, "l": "en", "cc": "US"}
    try:
        async with session.get(STEAM_SEARCH_URL, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return None
            data = json.loads(await resp.text())
            items = data.get("items", [])
            if not items:
                return None
            appid = items[0].get("id")
            if appid:
                return STEAM_CDN.format(appid=appid)
    except Exception:
        log.warning("Steam search failed for '%s'", cleaned, exc_info=True)
    return None


async def search_web_image(session: aiohttp.ClientSession, title: str) -> Optional[str]:
    """Fallback: search DuckDuckGo for a game image (no API key needed)."""
    query = f"{title} game"
    url = "https://duckduckgo.com/i.js"
    params = {"q": query, "o": "json"}
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return None
            data = json.loads(await resp.text())
            results = data.get("results", [])
            if results:
                return results[0].get("image")
    except Exception:
        log.warning("DDG image fallback failed for '%s'", title, exc_info=True)
    return None


def _format_size(size_str: str) -> str:
    size = size_str.strip()
    if size.lower().startswith("torrent") or not size:
        return "—"
    return size


def _normalize(g: dict) -> dict:
    return {
        "title": _clean_title(g.get("title", "Unknown")),
        "version": g.get("version", ""),
        "size": _format_size(g.get("file_size", "")),
        "genre": g.get("genre", ""),
        "upload_date": g.get("upload_date", ""),
        "image_url": None,
        "download_urls": g.get("download_urls", []),
    }


async def list_all_games() -> list[dict]:
    """Every game sorted newest-first, WITHOUT Steam images (cheap).
    Use attach_images() to add images only for the few you actually show."""
    async with aiohttp.ClientSession(headers={"User-Agent": "discord-bot/1.0"}) as session:
        games = await fetch_games(session)
        games.sort(key=lambda g: g.get("upload_date", ""), reverse=True)
        return [_normalize(g) for g in games]


async def attach_images(games: list[dict]) -> None:
    """Fetch game header images for the given games, in place.
    
    Tries Steam search first, falls back to DuckDuckGo if no result."""
    if not games:
        return
    async with aiohttp.ClientSession(headers={"User-Agent": "discord-bot/1.0"}) as session:
        for g in games:
            g["image_url"] = await search_steam_image(session, g.get("title", ""))
            if not g["image_url"]:
                g["image_url"] = await search_web_image(session, g.get("title", ""))


async def search_games(query: str, limit: int = 5) -> list[dict]:
    """Search games by title in the SteamRIP dataset and attach Steam images."""
    q = query.lower().strip()
    async with aiohttp.ClientSession(headers={"User-Agent": "discord-bot/1.0"}) as session:
        games = await fetch_games(session)
        matches = [g for g in games if q in g.get("title", "").lower()]
        matches.sort(key=lambda g: g.get("upload_date", ""), reverse=True)
        matches = matches[:limit]
        out = []
        for g in matches:
            title = _clean_title(g.get("title", "Unknown"))
            image_url = await search_steam_image(session, g.get("title", ""))
            if not image_url:
                image_url = await search_web_image(session, title)
            out.append({
                "title": title,
                "version": g.get("version", ""),
                "size": _format_size(g.get("file_size", "")),
                "genre": g.get("genre", ""),
                "upload_date": g.get("upload_date", ""),
                "image_url": image_url,
                "download_urls": g.get("download_urls", []),
            })
        return out
