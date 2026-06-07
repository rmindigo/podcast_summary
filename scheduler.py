"""
Weekly digest runner. Can be called directly (python scheduler.py) or via APScheduler.
Runs every Saturday at 12:00 PM UTC.
"""
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

from database import SessionLocal
from models import User, Digest
from services.transcripts import fetch_week_transcripts
from services.summarizer import summarize_episode, build_weekly_digest
from services.email_service import send_digest, _parse_aggregate, _parse_episode_summary


def _build_storage_payload(digest: dict, sent_at: datetime) -> dict:
    """Convert the raw digest dict into a clean JSON-serialisable structure for storage."""
    week_start = sent_at - timedelta(days=7)
    week_label = f"{week_start.strftime('%b %d')} - {sent_at.strftime('%b %d, %Y')}"

    agg = _parse_aggregate(digest["aggregate"])

    def bullets(text: str) -> list:
        return [l.lstrip("- ").strip() for l in text.splitlines() if l.strip().startswith("-")]

    episodes = []
    for ep in digest["episodes"]:
        parsed = _parse_episode_summary(ep["summary"])
        episodes.append({
            "channel": ep["channel"],
            "title": ep["title"],
            "url": ep["url"],
            "published": ep.get("published", ""),
            "summary": parsed["summary"].strip(),
            "key_points": parsed["points"],
        })

    return {
        "week_label": week_label,
        "aggregate": {
            "overview": agg["overview"],
            "themes": bullets(agg["themes"]),
            "calls": bullets(agg["calls"]),
        },
        "episodes": episodes,
        "assets": digest.get("assets", []),
    }


def run_digest_for_user(user: User, db) -> bool:
    active_channels = [c for c in user.channels if c.active]
    if not active_channels:
        print(f"[digest] {user.email} — no active channels, skipping")
        return False

    all_episodes = []
    for channel in active_channels:
        print(f"[digest] Fetching {channel.name} for {user.email}...")
        try:
            episodes = fetch_week_transcripts(channel.url, channel.name)
            all_episodes.extend(episodes)
            print(f"[digest]   -> {len(episodes)} episode(s) with transcripts")
        except Exception as e:
            print(f"[digest]   -> Error fetching {channel.name}: {e}")

    if not all_episodes:
        print(f"[digest] {user.email} — no new transcripts this week, skipping")
        return False

    print(f"[digest] Summarizing {len(all_episodes)} episode(s) for {user.email}...")
    summarized = []
    for ep in all_episodes:
        try:
            summarized.append(summarize_episode(ep))
        except Exception as e:
            print(f"[digest]   -> Error summarizing '{ep['title']}': {e}")

    if not summarized:
        print(f"[digest] {user.email} — all summaries failed, skipping")
        return False

    print(f"[digest] Building aggregate digest for {user.email}...")
    try:
        digest = build_weekly_digest(summarized)
    except Exception as e:
        print(f"[digest] {user.email} — aggregate failed: {e}")
        return False

    sent_at = datetime.utcnow()
    payload = _build_storage_payload(digest, sent_at)
    db_digest = Digest(
        user_id=user.id,
        sent_at=sent_at,
        episode_count=len(payload["episodes"]),
        content_json=json.dumps(payload),
    )
    db.add(db_digest)
    db.commit()
    print(f"[digest] Saved digest #{db_digest.id} for {user.email}")

    sent = send_digest(user.email, user.access_token, digest)
    print(f"[digest] Email {'sent' if sent else 'FAILED (check FROM_EMAIL in .env)'}: {user.email}")
    return True


def run_weekly_digest():
    print("[digest] Starting weekly digest run...")
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.active == True).all()
        print(f"[digest] Processing {len(users)} active user(s)")
        success, failed = 0, 0
        for user in users:
            try:
                if run_digest_for_user(user, db):
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"[digest] Uncaught error for {user.email}: {e}")
                failed += 1
        print(f"[digest] Done. Sent: {success}, Skipped/Failed: {failed}")
    finally:
        db.close()


if __name__ == "__main__":
    run_weekly_digest()
