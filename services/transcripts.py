import re
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Optional
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi


def normalize_channel_url(url: str) -> str:
    url = url.strip().rstrip("/")
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


def get_channel_videos(channel_url: str, limit: int = 15) -> list[dict]:
    """Return the most recent `limit` video IDs and titles from a YouTube channel."""
    url = normalize_channel_url(channel_url)
    videos_url = f"{url}/videos"
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


def get_video_publish_date(video_id: str) -> Optional[datetime]:
    """Fetch a video's publish date by parsing YouTube's page metadata."""
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
        )
        html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8")
        match = re.search(r'"publishDate":"(\d{4}-\d{2}-\d{2})', html)
        if match:
            return datetime.strptime(match.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        pass
    return None


def get_transcript(video_id: str) -> Optional[str]:
    """Fetch and flatten a YouTube video transcript. Returns None if unavailable."""
    try:
        fetched = YouTubeTranscriptApi().fetch(video_id)
        return " ".join(s.text for s in fetched.snippets).strip()
    except Exception:
        return None


def fetch_week_transcripts(channel_url: str, channel_name: str, days: int = 7) -> list[dict]:
    """
    Return videos from the past `days` days that have transcripts available.
    Fetches the last 15 videos, checks their publish date, then pulls transcripts
    only for those within the window.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    videos = get_channel_videos(channel_url, limit=15)

    results = []
    for video in videos:
        pub_date = get_video_publish_date(video["id"])

        # If we can't get a date, include it (safe default)
        if pub_date is not None and pub_date < cutoff:
            # Videos are newest-first; once we hit one older than cutoff, stop
            break

        transcript = get_transcript(video["id"])
        if transcript:
            published_label = pub_date.strftime("%b %d, %Y") if pub_date else ""
            results.append({
                "channel": channel_name,
                "title": video["title"],
                "published": published_label,
                "url": f"https://www.youtube.com/watch?v={video['id']}",
                "transcript": transcript,
            })

    return results
