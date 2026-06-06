import anthropic

client = anthropic.Anthropic()

EPISODE_PROMPT = """\
You are an expert investment analyst. Below is the full transcript of a podcast or interview.

Your job is to extract what matters to an investor. Be specific — names, numbers, predictions, and reasoning.

Return your analysis in this exact format:

SUMMARY:
[2-4 sentences capturing the main investment thesis or perspective of this episode]

KEY POINTS:
- [Key point 1 — include specific data, names, or claims where present]
- [Key point 2]
- [Key point 3]
- [Add more as needed, min 3 max 8]

ASSETS MENTIONED:
- TICKER_OR_NAME | Bullish / Bearish / Mixed / Neutral | [One sentence on what was said]
[List every stock, ETF, crypto, commodity, or macro asset mentioned. If none, write NONE.]

---
PODCAST: {title}
CHANNEL: {channel}

TRANSCRIPT:
{transcript}
"""

AGGREGATE_PROMPT = """\
You are an expert investment analyst writing a weekly briefing for sophisticated investors.

Below are individual episode summaries from the past week across multiple investing podcasts.
Your job is to synthesize them into a high-level intelligence report.

Write for someone who wants to quickly understand:
- What are the dominant themes and narratives this week?
- Where do commentators agree or disagree?
- What specific data points, predictions, or risks were raised?
- Who said what (attribute claims to channels/guests where known)?

Return your report in this exact format:

WEEKLY OVERVIEW:
[3-5 paragraphs. Write with authority. Include who said what. Surface tensions and consensus.
 Focus on actionable insight — macro trends, sector rotations, risk factors, opportunities flagged.]

KEY THEMES:
- [Theme 1]: [1-2 sentences with attribution]
- [Theme 2]: [1-2 sentences with attribution]
- [Theme 3]: [Continue as needed, min 3 max 7]

NOTABLE CALLS & PREDICTIONS:
- [Channel/Guest]: [Specific call or prediction made]
[List the most concrete, quotable statements made this week]

---
EPISODE SUMMARIES:
{episode_summaries}
"""

ASSETS_PROMPT = """\
You are compiling a master list of all investable assets mentioned across multiple podcast summaries this week.

From the episode summaries below, extract EVERY stock, ETF, cryptocurrency, commodity, index, or other investment vehicle mentioned.
Consolidate duplicates. For each asset, note the overall sentiment and what was said.

Return ONLY a JSON array with no markdown formatting, like this:
[
  {{"asset": "NVDA", "type": "Stock", "sentiment": "Bullish", "notes": "Called the dominant AI infrastructure play for next 3 years"}},
  {{"asset": "Bitcoin", "type": "Crypto", "sentiment": "Mixed", "notes": "Some see it as digital gold hedge; others concerned about regulatory risk"}}
]

Types should be one of: Stock, ETF, Crypto, Commodity, Index, Real Estate, Other

EPISODE SUMMARIES:
{episode_summaries}
"""


def _truncate_transcript(transcript: str, max_chars: int = 80_000) -> str:
    """Truncate very long transcripts to stay within context limits."""
    if len(transcript) <= max_chars:
        return transcript
    return transcript[:max_chars] + "\n\n[Transcript truncated due to length]"


def summarize_episode(episode: dict) -> dict:
    """Summarize a single episode transcript. Returns the episode dict with 'summary' added."""
    prompt = EPISODE_PROMPT.format(
        title=episode["title"],
        channel=episode["channel"],
        transcript=_truncate_transcript(episode["transcript"]),
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    episode_with_summary = dict(episode)
    episode_with_summary["summary"] = response.content[0].text
    return episode_with_summary


def build_weekly_digest(episodes: list[dict]) -> dict:
    """
    Takes a list of episode dicts (each with 'summary' field).
    Returns a dict with aggregate_overview, key_themes, assets.
    """
    summaries_text = "\n\n" + "=" * 60 + "\n\n".join(
        f"CHANNEL: {ep['channel']}\nEPISODE: {ep['title']}\nPUBLISHED: {ep.get('published', 'This week')}\nURL: {ep['url']}\n\n{ep['summary']}"
        for ep in episodes
    )

    # Aggregate overview + themes
    agg_response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2500,
        messages=[{"role": "user", "content": AGGREGATE_PROMPT.format(episode_summaries=summaries_text)}],
    )
    aggregate_text = agg_response.content[0].text

    # Assets list
    assets_response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": ASSETS_PROMPT.format(episode_summaries=summaries_text)}],
    )
    assets_raw = assets_response.content[0].text.strip()

    import json
    try:
        # Strip any accidental markdown code fences
        if "```" in assets_raw:
            assets_raw = assets_raw.split("```")[1]
            if assets_raw.startswith("json"):
                assets_raw = assets_raw[4:]
        assets = json.loads(assets_raw)
    except Exception:
        assets = []

    return {
        "aggregate": aggregate_text,
        "episodes": episodes,
        "assets": assets,
    }
