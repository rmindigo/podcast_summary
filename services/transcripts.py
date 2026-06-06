import re
from typing import Optional
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi


def normalize_channel_url(url: str) -> str:
    url = url.strip().rstrip("/")
    # Strip /videos, /streams, etc. suffixes — yt-dlp handles the base URL
    url = re.sub(r"/(videos|streams|shorts|playlists|community)$", "", url)
    if url.startswith("@"):
        url = f"https://www.youtube.com/{url}"
    return url


def get_channel_display_name(url: str) -> str:
    url = normalize_channel_url(url)
    for pattern in [r"@([^/]+)$", r"/c/([^/]+)$", r"/user/([^/]+)$", r"/channel/([^/]+)$"]:
        match = re.search(pattern, url)
        if match:
            name = match.group(1).replace("-", " ").replace("_", " ")
            return name.title()
    return url


def get_channel_videos(channel_url: str, limit: int = 10) -> list[dict]:
    """Return the most recent `limit` video IDs and titles from a YouTube channel."""
    url = normalize_channel_url(channel_url)
    videos_url = url if url.endswith("/videos") else f"{url}/videos"

    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "playlistend": limit,
        "ignoreerrors": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(videos_url, download=False)
            entries = (info or {}).get("entries") or []
            return [
                {"id": e["id"], "title": e.get("title", "Untitled")}
                for e in entries
                if e and e.get("id")
            ]
    except Exception as e:
        raise ValueError(f"Could not fetch videos from channel: {e}")


def get_transcript(video_id: str) -> Optional[str]:
    """Fetch and flatten a YouTube video transcript. Returns None if unavailable."""
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id)
        return " ".join(s.text for s in fetched.snippets).strip()
    except Exception:
        return None


def fetch_week_transcripts(channel_url: str, channel_name: str) -> list[dict]:
    """
    Return the most recent videos from a channel that have transcripts available.
    Grabs up to 10 videos (a week's worth for most investing channels).
    """
    videos = get_channel_videos(channel_url, limit=10)
    results = []
    for video in videos:
        transcript = get_transcript(video["id"])
        if transcript:
            results.append({
                "channel": channel_name,
                "title": video["title"],
                "published": "",
                "url": f"https://www.youtube.com/watch?v={video['id']}",
                "transcript": transcript,
            })
    return results
