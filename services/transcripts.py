import re
from typing import Optional
import scrapetube
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled


def normalize_channel_url(url: str) -> str:
    """Strip trailing slashes and normalize the URL."""
    url = url.strip().rstrip("/")
    # If someone pastes just a handle like @chamath, turn it into a full URL
    if url.startswith("@"):
        url = f"https://www.youtube.com/{url}"
    return url


def get_channel_display_name(url: str) -> str:
    """Extract a readable name from the channel URL."""
    url = normalize_channel_url(url)
    for pattern in [r"@([^/]+)$", r"/c/([^/]+)$", r"/user/([^/]+)$", r"/channel/([^/]+)$"]:
        match = re.search(pattern, url)
        if match:
            name = match.group(1).replace("-", " ").replace("_", " ")
            return name.title()
    return url


def _is_within_days(published_text: str, days: int = 7) -> bool:
    """Parse YouTube's relative time string and check if it falls within the window."""
    if not published_text:
        return True
    text = published_text.lower()
    # Always include if very recent
    if any(unit in text for unit in ("hour", "minute", "second", "just now")):
        return True
    match = re.search(r"(\d+)\s+(day|week|month|year)", text)
    if not match:
        return True
    num, unit = int(match.group(1)), match.group(2)
    if unit == "day":
        return num <= days
    if unit == "week":
        return num * 7 <= days
    return False  # months/years are always too old


def get_channel_videos(channel_url: str, days: int = 7) -> list[dict]:
    """Return recent videos from a YouTube channel URL."""
    url = normalize_channel_url(channel_url)
    try:
        raw_videos = scrapetube.get_channel(channel_url=url, limit=30, sort_by="newest")
    except Exception as e:
        raise ValueError(f"Could not fetch videos from channel: {e}")

    videos = []
    for v in raw_videos:
        published = (v.get("publishedTimeText") or {}).get("simpleText", "")
        if not _is_within_days(published, days):
            break  # Videos are newest-first; once we hit old ones we can stop
        title_runs = (v.get("title") or {}).get("runs", [{}])
        title = title_runs[0].get("text", "Untitled") if title_runs else "Untitled"
        video_id = v.get("videoId", "")
        if video_id:
            videos.append({"id": video_id, "title": title, "published": published})
    return videos


def get_transcript(video_id: str) -> Optional[str]:
    """Fetch and flatten a YouTube video transcript. Returns None if unavailable."""
    try:
        entries = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US", "en-GB"])
        return " ".join(e["text"] for e in entries).strip()
    except (NoTranscriptFound, TranscriptsDisabled):
        return None
    except Exception:
        return None


def fetch_week_transcripts(channel_url: str, channel_name: str) -> list[dict]:
    """
    For a given channel, return a list of dicts with title, url, and transcript
    for all videos published in the last 7 days that have transcripts available.
    """
    videos = get_channel_videos(channel_url, days=7)
    results = []
    for video in videos:
        transcript = get_transcript(video["id"])
        if transcript:
            results.append({
                "channel": channel_name,
                "title": video["title"],
                "published": video["published"],
                "url": f"https://www.youtube.com/watch?v={video['id']}",
                "transcript": transcript,
            })
    return results
