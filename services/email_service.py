import os
import resend
from datetime import datetime, timedelta

resend.api_key = os.getenv("RESEND_API_KEY", "")

FROM_EMAIL = os.getenv("FROM_EMAIL", "digest@example.com")
FROM_NAME = os.getenv("FROM_NAME", "Investing Digest")
APP_URL = os.getenv("APP_URL", "http://localhost:8000")

SENTIMENT_COLORS = {
    "Bullish": "#22c55e",
    "Bearish": "#ef4444",
    "Mixed": "#f59e0b",
    "Neutral": "#94a3b8",
}


def _sentiment_badge(sentiment: str) -> str:
    color = SENTIMENT_COLORS.get(sentiment, "#94a3b8")
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;letter-spacing:0.5px;">{sentiment.upper()}</span>'


def _parse_aggregate(text: str) -> dict:
    """Split aggregate Claude output into sections."""
    sections = {"overview": "", "themes": "", "calls": ""}
    current = None
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("WEEKLY OVERVIEW:"):
            current = "overview"
            continue
        elif stripped.startswith("KEY THEMES:"):
            if current == "overview":
                sections["overview"] = "\n".join(lines).strip()
            current = "themes"
            lines = []
            continue
        elif stripped.startswith("NOTABLE CALLS"):
            if current == "themes":
                sections["themes"] = "\n".join(lines).strip()
            current = "calls"
            lines = []
            continue
        if current:
            lines.append(line)
    if current and lines:
        sections[current] = "\n".join(lines).strip()
    return sections


def _parse_episode_summary(text: str) -> dict:
    """Split per-episode Claude output into sections."""
    sections = {"summary": "", "points": [], "assets_raw": ""}
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("SUMMARY:"):
            current = "summary"
            continue
        elif stripped.startswith("KEY POINTS:"):
            current = "points"
            continue
        elif stripped.startswith("ASSETS MENTIONED:"):
            current = "assets"
            continue
        if current == "summary" and stripped:
            sections["summary"] += stripped + " "
        elif current == "points" and stripped.startswith("-"):
            sections["points"].append(stripped[1:].strip())
        elif current == "assets":
            sections["assets_raw"] += line + "\n"
    return sections


def build_digest_html(digest: dict, user_email: str, access_token: str) -> str:
    week_end = datetime.utcnow()
    week_start = week_end - timedelta(days=7)
    date_range = f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}"

    agg = _parse_aggregate(digest["aggregate"])

    # Build episode cards (chronological — already ordered by caller)
    episode_html = ""
    for ep in digest["episodes"]:
        parsed = _parse_episode_summary(ep["summary"])
        points_html = "".join(f'<li style="margin-bottom:6px;">{p}</li>' for p in parsed["points"])
        episode_html += f"""
        <div style="margin-bottom:32px;padding:24px;background:#1e293b;border-radius:10px;border-left:3px solid #3b82f6;">
            <div style="font-size:11px;color:#64748b;font-weight:600;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;">{ep['channel']} &middot; {ep.get('published','This week')}</div>
            <a href="{ep['url']}" style="color:#e2e8f0;font-size:17px;font-weight:700;text-decoration:none;line-height:1.3;">{ep['title']}</a>
            <p style="color:#94a3b8;font-size:14px;line-height:1.7;margin:12px 0 10px;">{parsed['summary']}</p>
            <ul style="color:#cbd5e1;font-size:14px;line-height:1.6;padding-left:18px;margin:0;">
                {points_html}
            </ul>
        </div>
        """

    # Build assets table
    assets = digest.get("assets", [])
    if assets:
        rows = ""
        for a in assets:
            badge = _sentiment_badge(a.get("sentiment", "Neutral"))
            rows += f"""
            <tr style="border-bottom:1px solid #1e293b;">
                <td style="padding:10px 12px;font-weight:700;color:#e2e8f0;font-size:14px;">{a.get('asset','')}</td>
                <td style="padding:10px 12px;color:#64748b;font-size:13px;">{a.get('type','')}</td>
                <td style="padding:10px 12px;">{badge}</td>
                <td style="padding:10px 12px;color:#94a3b8;font-size:13px;">{a.get('notes','')}</td>
            </tr>
            """
        assets_section = f"""
        <h2 style="color:#e2e8f0;font-size:18px;font-weight:700;margin:40px 0 16px;border-bottom:1px solid #334155;padding-bottom:10px;">Assets & Securities Mentioned</h2>
        <table style="width:100%;border-collapse:collapse;background:#0f172a;border-radius:10px;overflow:hidden;">
            <thead>
                <tr style="background:#1e293b;">
                    <th style="padding:10px 12px;text-align:left;color:#64748b;font-size:11px;letter-spacing:1px;text-transform:uppercase;">Asset</th>
                    <th style="padding:10px 12px;text-align:left;color:#64748b;font-size:11px;letter-spacing:1px;text-transform:uppercase;">Type</th>
                    <th style="padding:10px 12px;text-align:left;color:#64748b;font-size:11px;letter-spacing:1px;text-transform:uppercase;">Sentiment</th>
                    <th style="padding:10px 12px;text-align:left;color:#64748b;font-size:11px;letter-spacing:1px;text-transform:uppercase;">Notes</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
        """
    else:
        assets_section = ""

    # Format themes as HTML list items
    themes_lines = [l for l in agg["themes"].splitlines() if l.strip().startswith("-")]
    themes_html = "".join(
        f'<li style="margin-bottom:8px;color:#cbd5e1;font-size:14px;line-height:1.6;">{l.lstrip("- ").strip()}</li>'
        for l in themes_lines
    )

    # Format calls as HTML list items
    calls_lines = [l for l in agg["calls"].splitlines() if l.strip().startswith("-")]
    calls_html = "".join(
        f'<li style="margin-bottom:8px;color:#cbd5e1;font-size:14px;line-height:1.6;">{l.lstrip("- ").strip()}</li>'
        for l in calls_lines
    )

    overview_paragraphs = "".join(
        f'<p style="color:#94a3b8;font-size:15px;line-height:1.8;margin:0 0 14px;">{p.strip()}</p>'
        for p in agg["overview"].split("\n\n") if p.strip()
    )

    unsubscribe_url = f"{APP_URL}/unsubscribe?token={access_token}"
    dashboard_url = f"{APP_URL}/dashboard?token={access_token}"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0a0f1e;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<div style="max-width:680px;margin:0 auto;padding:32px 16px;">

  <!-- Header -->
  <div style="text-align:center;margin-bottom:40px;">
    <div style="display:inline-block;background:linear-gradient(135deg,#3b82f6,#8b5cf6);padding:8px 20px;border-radius:6px;margin-bottom:16px;">
      <span style="color:#fff;font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase;">Weekly Intelligence</span>
    </div>
    <h1 style="color:#e2e8f0;font-size:28px;font-weight:800;margin:0 0 6px;">Investing Podcast Digest</h1>
    <p style="color:#64748b;font-size:14px;margin:0;">{date_range}</p>
  </div>

  <!-- Section 1: Aggregate Overview -->
  <div style="background:#0f172a;border-radius:12px;padding:28px;margin-bottom:32px;border:1px solid #1e293b;">
    <h2 style="color:#3b82f6;font-size:13px;font-weight:700;letter-spacing:2px;text-transform:uppercase;margin:0 0 16px;">01 / Weekly Overview</h2>
    {overview_paragraphs}

    {"<h3 style='color:#e2e8f0;font-size:15px;font-weight:700;margin:24px 0 12px;'>Key Themes</h3><ul style='padding-left:18px;margin:0;'>" + themes_html + "</ul>" if themes_html else ""}
    {"<h3 style='color:#e2e8f0;font-size:15px;font-weight:700;margin:24px 0 12px;'>Notable Calls & Predictions</h3><ul style='padding-left:18px;margin:0;'>" + calls_html + "</ul>" if calls_html else ""}
  </div>

  <!-- Section 2: Per-Episode Breakdown -->
  <h2 style="color:#3b82f6;font-size:13px;font-weight:700;letter-spacing:2px;text-transform:uppercase;margin:0 0 20px;">02 / Episode Breakdown</h2>
  {episode_html}

  <!-- Section 3: Assets -->
  <div style="background:#0f172a;border-radius:12px;padding:28px;margin-bottom:32px;border:1px solid #1e293b;">
    <h2 style="color:#3b82f6;font-size:13px;font-weight:700;letter-spacing:2px;text-transform:uppercase;margin:0 0 4px;">03 / Market Mentions</h2>
    {assets_section if assets_section else '<p style="color:#64748b;font-size:14px;">No specific assets mentioned this week.</p>'}
  </div>

  <!-- Footer -->
  <div style="text-align:center;padding-top:24px;border-top:1px solid #1e293b;">
    <a href="{dashboard_url}" style="color:#3b82f6;font-size:13px;text-decoration:none;margin:0 12px;">Manage Channels</a>
    <span style="color:#334155;">|</span>
    <a href="{unsubscribe_url}" style="color:#64748b;font-size:13px;text-decoration:none;margin:0 12px;">Unsubscribe</a>
    <p style="color:#334155;font-size:12px;margin:16px 0 0;">You're receiving this because you subscribed at {APP_URL}</p>
  </div>

</div>
</body>
</html>"""


def send_digest(user_email: str, access_token: str, digest: dict) -> bool:
    week_end = datetime.utcnow()
    subject = f"Your Investing Digest: Week of {week_end.strftime('%b %d, %Y')}"
    html = build_digest_html(digest, user_email, access_token)
    try:
        resend.Emails.send({
            "from": f"{FROM_NAME} <{FROM_EMAIL}>",
            "to": [user_email],
            "subject": subject,
            "html": html,
        })
        return True
    except Exception as e:
        print(f"[email] Failed to send to {user_email}: {e}")
        return False


def send_welcome(user_email: str, access_token: str) -> bool:
    dashboard_url = f"{APP_URL}/dashboard?token={access_token}"
    html = f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#0a0f1e;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<div style="max-width:560px;margin:0 auto;padding:48px 24px;text-align:center;">
    <div style="background:linear-gradient(135deg,#3b82f6,#8b5cf6);padding:8px 20px;border-radius:6px;display:inline-block;margin-bottom:24px;">
        <span style="color:#fff;font-size:12px;font-weight:700;letter-spacing:2px;">INVESTING DIGEST</span>
    </div>
    <h1 style="color:#e2e8f0;font-size:26px;font-weight:800;margin:0 0 12px;">You're in.</h1>
    <p style="color:#94a3b8;font-size:15px;line-height:1.7;margin:0 0 32px;">
        Every Saturday at noon you'll receive a curated intelligence briefing from the investing podcasts you follow.
        Add your first channels to get started.
    </p>
    <a href="{dashboard_url}" style="display:inline-block;background:linear-gradient(135deg,#3b82f6,#8b5cf6);color:#fff;font-size:15px;font-weight:700;padding:14px 32px;border-radius:8px;text-decoration:none;">
        Set Up My Channels &rarr;
    </a>
    <p style="color:#475569;font-size:13px;margin:32px 0 0;">
        Bookmark your dashboard link. You will use it every time you log in.<br>
        <a href="{dashboard_url}" style="color:#3b82f6;text-decoration:none;word-break:break-all;">{dashboard_url}</a>
    </p>
</div>
</body>
</html>"""
    try:
        resend.Emails.send({
            "from": f"{FROM_NAME} <{FROM_EMAIL}>",
            "to": [user_email],
            "subject": "Your Investing Digest is ready. Here is your dashboard link.",
            "html": html,
        })
        return True
    except Exception as e:
        print(f"[email] Failed to send welcome to {user_email}: {e}")
        return False


def send_magic_link(user_email: str, access_token: str) -> bool:
    dashboard_url = f"{APP_URL}/dashboard?token={access_token}"
    html = f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#0a0f1e;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<div style="max-width:560px;margin:0 auto;padding:48px 24px;text-align:center;">
    <h2 style="color:#e2e8f0;font-size:22px;font-weight:700;margin:0 0 12px;">Your dashboard link</h2>
    <p style="color:#94a3b8;font-size:15px;margin:0 0 28px;">Click below to access your Investing Digest dashboard.</p>
    <a href="{dashboard_url}" style="display:inline-block;background:linear-gradient(135deg,#3b82f6,#8b5cf6);color:#fff;font-size:15px;font-weight:700;padding:14px 32px;border-radius:8px;text-decoration:none;">
        Open My Dashboard &rarr;
    </a>
    <p style="color:#475569;font-size:13px;margin:28px 0 0;">
        <a href="{dashboard_url}" style="color:#3b82f6;text-decoration:none;word-break:break-all;">{dashboard_url}</a>
    </p>
</div>
</body>
</html>"""
    try:
        resend.Emails.send({
            "from": f"{FROM_NAME} <{FROM_EMAIL}>",
            "to": [user_email],
            "subject": "Your Investing Digest dashboard link",
            "html": html,
        })
        return True
    except Exception as e:
        print(f"[email] Failed to send magic link to {user_email}: {e}")
        return False
