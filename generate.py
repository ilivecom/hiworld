#!/usr/bin/env python3
"""
hiworld daily — AI & Tech Briefing Generator

Automated daily briefing for European & North American tech professionals.
https://hiworld.uk

Usage:
    ANTHROPIC_API_KEY=sk-ant-... python generate.py
"""

import anthropic
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import markdown as md_lib
except ImportError:
    print("❌ Missing 'markdown' package. Run: pip install markdown", file=sys.stderr)
    sys.exit(1)

# ── Date (UK time: BST in summer, GMT in winter) ──────────────────────────────
try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Europe/London")
except ImportError:
    # Python < 3.9 fallback — assumes BST (UTC+1)
    _TZ = timezone(timedelta(hours=1))

NOW        = datetime.now(_TZ)
TODAY_ISO  = NOW.strftime("%Y-%m-%d")       # e.g. "2026-06-10"
TODAY_LONG = NOW.strftime("%A, %B %-d, %Y") # e.g. "Wednesday, June 10, 2026"

# ── Deduplication helpers ─────────────────────────────────────────────────────
# Own domains — links here are never counted as "already covered" articles.
_SKIP_DOMAINS = {"hiworld.uk"}


def get_recent_article_urls(archive_dir: Path, days: int = 2) -> list:
    """Return external article URLs found in the last `days` archived HTML files.

    Passed to the prompt so Claude avoids re-reporting the same stories.
    """
    urls: set = set()
    html_files = sorted(archive_dir.glob("????-??/????-??-??.html"), reverse=True)[:days]
    for html_file in html_files:
        text = html_file.read_text("utf-8")
        for url in re.findall(r'href="(https?://[^"]+)"', text):
            if not any(d in url for d in _SKIP_DOMAINS):
                # Normalise: strip query strings and trailing slashes
                urls.add(re.sub(r"\?.*$", "", url).rstrip("/"))
    return sorted(urls)


# ── Prompts ───────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are the Chief Technology Strategy Analyst serving a tier-one global macro hedge fund, "
    "top-quartile Silicon Valley VC firms, and C-suite executives at multinational technology "
    "companies. Your mandate is to produce a daily intelligence briefing modelled on the "
    "analytical rigour of an FT deep-dive or a Goldman Sachs sector note — not a press release "
    "digest. Tone: precise, unsentimental, commercially driven. Every sentence must earn its "
    "place: lead with the business consequence, support with hard data, and cut any observation "
    "that does not change how a decision-maker should act or invest. Never disclose how the "
    "briefing was produced or reference any AI system."
)

# Patterns that flag editorial guideline violations (geopolitical conflict framing)
_EDITORIAL_VIOLATION_PATTERNS = [
    r"\bUS[- ]China\b.{0,80}\b(war|conflict|tension|rivalry|sanction|ban)\b",
    r"\b(chip\s*war|tech\s*war|trade\s*war)\b",
]


def contains_editorial_violation(text: str) -> bool:
    """Return True if the text contains disallowed geopolitical conflict framing."""
    return any(re.search(p, text, re.IGNORECASE) for p in _EDITORIAL_VIOLATION_PATTERNS)


_USER_PROMPT_TEMPLATE = f"""Produce today's ({TODAY_LONG}) edition of the **Hiworld Executive Briefing** — a daily intelligence briefing for C-suite executives, senior VC partners, and portfolio managers.

## Search Strategy

Use **aggregated keyword searches** to cover multiple sources per query — do not search site by site:

1. `AI news today {TODAY_ISO} site:openai.com OR site:anthropic.com OR site:deepmind.google OR site:ai.meta.com`
2. `AI model release OR AI product launch OR LLM benchmark {TODAY_ISO}`
3. `AI funding OR AI acquisition OR AI partnership {TODAY_ISO}`
4. `AI news {TODAY_ISO} site:techcrunch.com OR site:theverge.com OR site:bloomberg.com OR site:reuters.com`
5. `AI research breakthrough OR open-source model {TODAY_ISO}`
6. Use remaining searches to fill any gaps from the Tier 1 and Tier 2 source lists below.

## Source Priorities

### Tier 1 — Primary (must cover)
- OpenAI Blog · Anthropic News · Google DeepMind Blog · Meta AI Blog
- Mistral, xAI, Perplexity, Cohere official blogs
- Stratechery (Ben Thompson) · Platformer (Casey Newton) · Import AI (Jack Clark) · Latent Space

### Tier 2 — Deep-dive coverage
- TechCrunch AI · The Verge AI · Bloomberg Technology · Financial Times Tech
- The Information (public excerpts) · Ars Technica · Wired · Reuters Technology
- IEEE Spectrum · Semafor Tech · MIT Technology Review

### Tier 3 — Signal sources
- Hacker News Top 20 (AI items only) · Ben's Bites · The Batch (Andrew Ng)

## Selection Criteria

Only include items qualifying under at least one of:
1. **Capital / market signal** — funding rounds, acquisitions, valuation shifts, major partnerships with financial weight
2. **Competitive dynamics** — product launches or benchmarks that measurably shift market position
3. **Technical inflection** — architectural breakthroughs or efficiency gains with quantifiable impact
4. **Regulatory / macro** — policy developments with direct near-term commercial consequence

**Exclude:**
- Marketing announcements with no commercial substance
- News older than 24 hours
- Unverified rumours
- Content whose primary framing is geopolitical conflict, partisan politics, or US–China rivalry
  (chip war, tech war, trade war, sanctions narratives); neutral government or enterprise
  deployments and policy discussions are acceptable

## Output Format

Begin the briefing immediately with the first section heading. No preamble, title line, or date header — those are rendered separately.

### 💡 Executive Alpha

Two to three sentences surfacing the single most important non-consensus insight from today's news cycle — the kind of observation that would change a portfolio allocation or competitive strategy. Lead with the commercial conclusion; use hard data wherever available.

**Key Data:** [one critical metric, valuation, or benchmark figure that anchors the insight]
**Strategic Takeaway:** [one sentence on what a decision-maker should act on or monitor as a result]

### 🚀 Top Strategic Moves

The three highest-signal developments today. For each:

**1. [Headline — lead with commercial or technical substance, not the company name]**
- **The Signal:** One sentence on the core fact.
- **Strategic Impact:** Two to three sentences. Which sector wins or loses? Does this shift competitive dynamics? What is the threat or opportunity for existing business models or revenue streams?
- **Source:** [Publication](URL) · YYYY-MM-DD

**2. [Headline]**
- **The Signal:**
- **Strategic Impact:**
- **Source:**

**3. [Headline]**
- **The Signal:**
- **Strategic Impact:**
- **Source:**

### 📡 Radar

Five to eight edge signals worth tracking. One sentence each: state the fact and its directional implication in the same breath. No source attribution needed.

- **[Domain / Sector]:** [fact + directional implication]

### ⚠️ Source Notes
- List publications that directly contributed content
- Mark any URL that could not be fully confirmed: append `⚠️ URL unconfirmed` after the source name

## Hard Rules
- All URLs must be **real, clickable source URLs** — never fabricate
- If a search result shows only a root domain without a full article path, use the root domain as a placeholder and mark it `⚠️ URL unconfirmed`; do not drop a significant story
- Never include content whose primary narrative is geopolitical conflict, US–China rivalry, or partisan politics
- Total length: under 900 words — every sentence must earn its place
- Do not append word counts, self-evaluations, or any statement about how this briefing was produced"""


def build_user_prompt(recent_urls=None) -> str:
    """Build the user prompt, optionally injecting the deduplication URL block."""
    prompt = _USER_PROMPT_TEMPLATE
    if recent_urls:
        url_list = "\n".join(f"- {u}" for u in recent_urls)
        dedup_block = (
            "\n\n## Already Covered — Do Not Repeat\n\n"
            "The URLs below appeared in **briefings from the last 2 days**. "
            "Do **not** cover these stories or any other report on the same underlying event "
            "(even under a different headline or angle):\n\n"
            f"{url_list}"
        )
        # Insert the block just before the Output Format section
        prompt = prompt.replace("## Output Format", dedup_block + "\n\n## Output Format")
    return prompt


# ── Claude API ────────────────────────────────────────────────────────────────
def fetch_briefing(user_prompt: str) -> str:
    """Call Claude with web_search and return the briefing markdown.

    The web_search tool (type: "web_search_20260209") is server-side:
    Anthropic executes searches and injects results back into the conversation.
    Claude may search multiple times before finishing, so we run an agentic
    loop until stop_reason == "end_turn".
    If the server-side loop hits its iteration limit it returns "pause_turn";
    we re-send the conversation to resume.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY environment variable is not set")

    client = anthropic.Anthropic(api_key=api_key)

    messages: list = [{"role": "user", "content": user_prompt}]
    system = SYSTEM_PROMPT

    print(f"📡 Calling Claude API for {TODAY_ISO}...")

    for turn in range(8):  # safety cap
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=4000,
            system=system,
            tools=[{"type": "web_search_20260209", "name": "web_search", "allowed_callers": ["direct"]}],
            messages=messages,
        )

        print(
            f"  turn {turn + 1} | stop_reason={response.stop_reason} | "
            f"blocks={[b.type for b in response.content]}"
        )

        text = "\n".join(
            b.text for b in response.content if getattr(b, "type", "") == "text" and b.text
        )

        if response.stop_reason == "end_turn":
            cleaned = clean_briefing(text) or "(No content generated — please check API configuration)"
            if contains_editorial_violation(cleaned):
                print("  ⚠️  Editorial violation detected; requesting rewrite")
                messages.append({"role": "assistant", "content": response.content})
                messages.append({
                    "role": "user",
                    "content": (
                        "Your previous output contained content that violates editorial guidelines "
                        "(geopolitical conflict framing, US–China rivalry, or partisan politics). "
                        "Please completely rewrite the briefing. Keep only items about AI products, "
                        "engineering, research, and business. Neutral government or enterprise "
                        "deployments and policy discussions are acceptable, but remove anything "
                        "whose primary narrative is geopolitical conflict, chip war, tech war, "
                        "trade war, or US–China tensions."
                    ),
                })
                continue
            return cleaned

        if response.stop_reason == "pause_turn":
            # Server-side search hit its iteration limit — resume by re-sending
            messages.append({"role": "assistant", "content": response.content})
            continue

        # stop_reason == "max_tokens" or other — return whatever text we have
        return text or "(Output truncated — consider increasing max_tokens)"

    return "(Exceeded maximum turns — please check configuration)"


# ── Markdown → HTML ───────────────────────────────────────────────────────────
def clean_briefing(text: str) -> str:
    """Strip LLM preamble and fix common markdown formatting issues."""
    # 0. Strip trailing whitespace on every line first.
    #    Markdown treats "line  \n" (two trailing spaces) as a hard <br>.
    text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)

    # 0b. Ensure field labels start new paragraphs (covers both old and new format names).
    text = re.sub(
        r'(?m)(?<!\n)\n(\*\*(?:Source|Summary|The\s+Signal|Strategic\s+Impact|Key\s+Data|Strategic\s+Takeaway|Technical\s*/\s*Product\s*angle|Technical\s*angle)\*\*\s*:)',
        r'\n\n\1',
        text,
    )

    # 0c. Ensure a blank line between **Summary**: and the first bullet item.
    text = re.sub(
        r'(\*\*Summary\*\*\s*:)\n(-\s)',
        r'\1\n\n\2',
        text,
    )

    # 1. Drop everything before the first heading
    match = re.search(r'^#{1,3}\s', text, re.MULTILINE)
    if match:
        text = text[match.start():]

    # 1b. Remove redundant "hiworld daily — DATE" title heading that Claude
    #     sometimes generates — it duplicates the hero-meta breadcrumb on screen.
    text = re.sub(
        r'^#{1,3}\s+[^\n]*hiworld\s+daily[^\n]*\n+',
        '',
        text,
        flags=re.MULTILINE | re.IGNORECASE,
    )

    # 2. Fix broken bold spanning newlines: **\ntext\n** → **text**
    text = re.sub(
        r'\*\*\s*\n([^\n*]{1,200})\n\s*\*\*',
        lambda m: f'**{m.group(1).strip()}**',
        text,
    )

    # 3. Remove standalone semicolons used as sentence separators
    text = re.sub(r'^\s*[;]\s*$', '', text, flags=re.MULTILINE)

    # 4. Remove standalone single-dash lines
    text = re.sub(r'^\s*-\s*$', '', text, flags=re.MULTILINE)

    # 5. Collapse 3+ blank lines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 6. Strip word-count / self-evaluation lines
    text = re.sub(r'^[Tt]otal\s+[Ww]ord\s*[Cc]ount.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def md_to_html(text: str) -> str:
    """Convert markdown briefing to HTML."""
    html = md_lib.markdown(
        text,
        extensions=["extra", "sane_lists"],
    )
    # Fix <br> + field label combos that markdown sometimes produces
    html = re.sub(
        r'<br\s*/?>\s*\n(<strong>(?:Source|Summary|The\s+Signal)</strong>\s*:)',
        r'</p>\n<p>\1',
        html,
    )
    html = re.sub(
        r'\n(<strong>(?:Strategic\s+Impact|Technical\s*/?\s*Product\s*angle)</strong>\s*:)',
        r'</p>\n<p>\1',
        html,
    )
    return html


def build_archive_nav(entries: list) -> str:
    """Build archive nav HTML grouped by month, collapsible via <details>.

    Last 3 months shown as collapsed <details>; older months inside "Older editions".
    URL format: /archive/YYYY-MM/YYYY-MM-DD.html
    """
    if not entries:
        return '<p class="no-archive">No archive entries yet</p>'

    # Group by YYYY-MM, newest first
    months: dict = {}
    for entry in sorted(entries, key=lambda e: e["date"], reverse=True):
        month = entry["date"][:7]
        months.setdefault(month, []).append(entry["date"])

    def render_month(month: str, dates: list) -> str:
        count = len(dates)
        label = "edition" if count == 1 else "editions"
        items = "\n".join(
            f'    <li data-date="{d}"><a href="/archive/{month}/{d}.html">{d}</a></li>'
            for d in sorted(dates, reverse=True)
        )
        return (
            f'<details class="month-item">\n'
            f'  <summary>{month} <span class="month-count">{count} {label}</span></summary>\n'
            f'  <ul class="day-list">\n{items}\n  </ul>\n'
            f'</details>'
        )

    month_keys = sorted(months.keys(), reverse=True)
    recent = month_keys[:3]
    older  = month_keys[3:]

    parts = [render_month(m, months[m]) for m in recent]

    if older:
        older_html = "\n".join(render_month(m, months[m]) for m in older)
        parts.append(
            f'<details class="older-archive">\n'
            f'  <summary>Older editions</summary>\n'
            f'  <div class="older-months">\n{older_html}\n  </div>\n'
            f'</details>'
        )

    return '<div class="archive-nav">' + "\n".join(parts) + "</div>"


# ── HTML Template ─────────────────────────────────────────────────────────────
# Uses [[PLACEHOLDER]] substitution (not .format() / f-string) to avoid
# escaping the CSS { } braces.
#
# Logo: CSS wordmark using Outfit ExtraBold (Google Fonts)
#   "hi" in brand teal (#00C2B3), "world" in near-black (#1a1a1a)
HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>hiworld daily · [[DATE_LONG]]</title>
  <meta name="description" content="Executive AI &amp; technology intelligence briefing — [[DATE_LONG]]" />
  <link rel="icon" type="image/x-icon" href="/favicon.ico?v=1" />
  <!-- Outfit ExtraBold: geometric sans-serif for the wordmark logo -->
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@800&display=swap" rel="stylesheet" />
  <style>
    /* ── Reset ── */
    *, *::before, *::after { box-sizing: border-box; }

    /* ── Base ── */
    body {
      margin: 0;
      padding: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
        Helvetica, Arial, sans-serif;
      font-size: 17px;
      line-height: 1.82;
      background-color: #f5f5f7;
      color: #1d1d1f;
      -webkit-text-size-adjust: 100%;
      text-size-adjust: 100%;
      overflow-wrap: break-word;
      word-break: break-word;
    }

    /* ── Logo — CSS wordmark, fixed top-left ── */
    #logo {
      position: fixed;
      top: 18px;
      left: 20px;
      z-index: 9999;
      display: inline-flex;
      align-items: center;
      text-decoration: none;
      outline: none;
      border: none;
      -webkit-tap-highlight-color: transparent;
      font-family: 'Outfit', -apple-system, "Helvetica Neue", sans-serif;
      font-weight: 800;
      font-size: 22px;
      letter-spacing: -0.4px;
      line-height: 1;
      user-select: none;
      transition: opacity 0.2s;
    }
    #logo:hover { opacity: 0.78; }
    #logo .logo-hi    { color: #00C2B3; }
    #logo .logo-world { color: #1a1a1a; }

    /* ── Content card ── */
    #content {
      margin-top: 80px;
      margin-left: auto;
      margin-right: auto;
      width: min(90%, 840px);
      padding: 40px 42px 34px;
      background-color: rgba(255, 255, 255, 0.94);
      border: 1px solid rgba(15, 23, 42, 0.05);
      box-shadow: 0 14px 40px rgba(15, 23, 42, 0.06);
      border-radius: 24px;
      margin-bottom: 26px;
      backdrop-filter: saturate(180%) blur(18px);
    }

    /* ── Headings ── */
    h1, h2, h3 {
      position: relative;
      padding-left: 15px;
      font-weight: bold;
      line-height: 1.2;
      color: #1a1a1a;
    }
    h1::before {
      content: "";
      position: absolute;
      left: 0; top: 50%;
      transform: translateY(-50%);
      width: 4px; height: 26px;
      background-color: #00C2B3;
      border-radius: 2px;
    }
    h2::before {
      content: "";
      position: absolute;
      left: 0; top: 50%;
      transform: translateY(-50%);
      width: 2px; height: 18px;
      background-color: rgba(0, 194, 179, 0.35);
      border-radius: 1px;
    }
    h3::before {
      content: "";
      position: absolute;
      left: 0; top: 50%;
      transform: translateY(-50%);
      width: 2px; height: 14px;
      background-color: rgba(0, 194, 179, 0.35);
      border-radius: 1px;
    }

    h1 { font-size: 32px; margin-top: 0; }
    h2 { font-size: 24px; margin-top: 35px; }
    h3 { font-size: 19px; margin-top: 28px; margin-bottom: 6px; }

    h4, h5, h6 {
      position: relative;
      padding-left: 15px;
      font-weight: 600;
      line-height: 1.4;
      color: #333;
      margin-top: 20px;
      margin-bottom: 6px;
    }
    h4 { font-size: 16px; }
    h5, h6 { font-size: 15px; }

    /* ── Body text & links ── */
    p {
      line-height: 1.7;
      margin-top: 10px;
      margin-bottom: 16px;
      color: #333;
    }
    a { color: #008F84; text-decoration: none; transition: opacity 0.2s; }
    a:hover { opacity: 0.7; }
    strong { font-weight: 700; color: #1a1a1a; }
    em { font-style: italic; color: #555; }

    /* ── Lists ── */
    ul, ol { padding-left: 1.5em; margin: 8px 0 16px; }
    li { line-height: 1.7; color: #333; margin: 4px 0; }

    /* ── Inline code ── */
    code {
      font-family: "SF Mono", "Fira Code", monospace;
      font-size: .85em;
      background: #f3f4f6;
      padding: .1em .35em;
      border-radius: 4px;
      color: #1a1a1a;
    }

    /* ── Blockquote ── */
    blockquote {
      border-left: 3px solid rgba(0, 194, 179, 0.5);
      margin: 16px 0;
      padding: 8px 16px;
      background: #f9fefe;
      border-radius: 0 8px 8px 0;
      color: #555;
    }

    /* ── HR ── */
    hr { border: none; border-top: 1px solid #eee; margin: 28px 0; }

    /* ── Hero block ── */
    .hero { margin-bottom: 12px; }

    .hero-meta {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0 4px;
      padding-left: 15px;
      font-size: 15px;
      line-height: 1.72;
      color: #6e6e73;
    }
    .hero-meta a { color: #008F84; text-decoration: none; }
    .hero-divider { margin: 0 2px; color: #8e8e93; }
    .hero-date { margin-left: 8px; color: #6e6e73; white-space: nowrap; }
    .hero h1 { margin-top: 20px; margin-bottom: 0; }

    /* ── Archive section ── */
    .archive-section { margin-top: 40px; }
    .archive-nav { margin: 0; }

    details.month-item,
    details.older-archive {
      border-bottom: 1px solid #eee;
    }
    details.month-item:last-child,
    details.older-archive:last-child { border-bottom: none; }

    details.month-item > summary,
    details.older-archive > summary {
      list-style: none;
      display: flex;
      align-items: center;
      padding: 11px 5px;
      font-size: 15px;
      color: #555;
      cursor: pointer;
      user-select: none;
      transition: background-color 0.15s;
    }
    details.month-item > summary::-webkit-details-marker,
    details.older-archive > summary::-webkit-details-marker { display: none; }

    details.month-item > summary::before {
      content: "▶";
      font-size: 10px;
      margin-right: 8px;
      color: #bbb;
      transition: transform 0.2s;
      flex-shrink: 0;
    }
    details.month-item[open] > summary::before { transform: rotate(90deg); }

    details.older-archive > summary {
      color: #008F84;
      font-size: 14px;
    }
    details.older-archive > summary::before {
      content: "▶";
      font-size: 10px;
      margin-right: 8px;
      color: #00c2b3;
      transition: transform 0.2s;
      flex-shrink: 0;
    }
    details.older-archive[open] > summary::before { transform: rotate(90deg); }

    details.month-item > summary:hover,
    details.older-archive > summary:hover { background-color: #fafafa; }

    .month-count {
      font-size: 12px;
      color: #bbb;
      margin-left: 6px;
    }

    .day-list { list-style: none; padding: 0; margin: 0; }
    .day-list li { border-top: 1px solid #f5f5f5; }
    .day-list li a {
      display: block;
      padding: 9px 5px 9px 22px;
      font-size: 14px;
      color: #555;
      text-decoration: none;
      transition: padding-left 0.2s ease, background-color 0.2s ease;
      font-variant-numeric: tabular-nums;
    }
    .day-list li a:hover {
      background-color: #fafafa;
      padding-left: 28px;
    }
    .day-list li.active a { color: #008F84; font-weight: 600; }
    .older-months { padding-bottom: 4px; }

    .today-tag {
      font-size: 11px;
      background: rgba(0,194,179,.12);
      color: #00a396;
      padding: 1px 6px;
      border-radius: 4px;
      margin-left: 6px;
      vertical-align: middle;
    }
    .no-archive { font-size: 14px; color: #999; }

    /* ── Footer ── */
    #footer {
      width: min(90%, 840px);
      margin: 0 auto 28px;
      padding: 0 8px 8px;
      text-align: center;
      font-size: 13px;
      line-height: 1.65;
      color: #8e8e93;
    }
    #footer a { color: #008F84; }
    .footer-meta { margin-bottom: 4px; }

    /* ── Responsive ── */
    @media (max-width: 1150px) {
      #logo {
        position: absolute !important;
        top: 14px;
        left: 16px;
        font-size: 20px;
      }
      #content { margin-top: 60px; padding: 34px 28px 28px; }
    }
    @media (max-width: 767px) {
      #logo { font-size: 19px; }
      #content {
        margin-top: 56px;
        width: calc(100% - 32px);
        padding: 28px 18px 24px;
        border-radius: 20px;
      }
      .hero { margin-bottom: 14px; }
      h1 { font-size: 28px; }
      h2 { font-size: 22px; }
      h3 { font-size: 18px; margin-top: 20px; }
      p, li { line-height: 1.82; }
    }
  </style>
</head>
<body>

  <!-- CSS wordmark logo — "hi" in teal, "world" in near-black, Outfit ExtraBold -->
  <a href="https://hiworld.uk/" id="logo" aria-label="hiworld home">
    <span class="logo-hi">hi</span><span class="logo-world">world</span>
  </a>

  <div id="content">

    <div class="hero">
      <div class="hero-meta">
        <a href="https://hiworld.uk/">hiworld</a>
        <span class="hero-divider">·</span>
        <a href="/">daily</a>
        <span class="hero-date">[[DATE_LONG]]</span>
      </div>
      <h1>Executive Briefing</h1>
    </div>

    <!-- Briefing body -->
    [[CONTENT]]

    <!-- Archive -->
    <div class="archive-section">
      <h2>Archive</h2>
      [[ARCHIVE]]
    </div>

  </div>

  <div id="footer">
    <div>© 2026 hiworld · <a href="https://hiworld.uk/">hiworld.uk</a></div>
  </div>

  <script>
    // Highlight today's entry in the archive nav using UK local time.
    // en-CA locale produces YYYY-MM-DD format natively — no manual reformatting needed.
    (function () {
      var today = new Date().toLocaleDateString('en-CA', { timeZone: 'Europe/London' });
      var li = document.querySelector('[data-date="' + today + '"]');
      if (!li) return;
      li.classList.add('active');
      var a = li.querySelector('a');
      if (a) a.innerHTML = today + ' <span class="today-tag">today</span>';
    })();
  </script>

</body>
</html>
"""


def render_page(briefing_md: str, archive_entries: list) -> str:
    """Render the complete HTML page from markdown briefing and archive entries."""
    content_html = md_to_html(briefing_md)
    archive_html  = build_archive_nav(archive_entries)

    return (
        HTML_TEMPLATE
        .replace("[[DATE_LONG]]",    TODAY_LONG)
        .replace("[[DATE_ISO]]",     TODAY_ISO)
        .replace("[[CONTENT]]",      content_html)
        .replace("[[ARCHIVE]]",      archive_html)
    )


# ── One-time archive migration ────────────────────────────────────────────────
def migrate_archive(docs_dir: Path) -> None:
    """Move any flat archive/YYYY-MM-DD.html files into archive/YYYY-MM/ subdirs.

    Updates all internal /archive/DATE.html links in each file.
    Skips automatically if no flat files are found.
    """
    archive_dir = docs_dir / "archive"
    old_files   = list(archive_dir.glob("????-??-??.html"))
    if not old_files:
        return

    print(f"🔄 Migrating {len(old_files)} archive files to monthly subdirs...")
    link_re = re.compile(r'/archive/(\d{4}-\d{2}-\d{2})\.html')

    def rewrite_links(html: str) -> str:
        return link_re.sub(lambda m: f'/archive/{m.group(1)[:7]}/{m.group(1)}.html', html)

    for old_file in sorted(old_files):
        date      = old_file.stem
        month     = date[:7]
        month_dir = archive_dir / month
        month_dir.mkdir(parents=True, exist_ok=True)
        new_file  = month_dir / f"{date}.html"
        html      = rewrite_links(old_file.read_text("utf-8"))
        new_file.write_text(html, encoding="utf-8")
        old_file.unlink()
        print(f"  ✅ archive/{date}.html → archive/{month}/{date}.html")

    index_file = docs_dir / "index.html"
    if index_file.exists():
        html    = index_file.read_text("utf-8")
        updated = rewrite_links(html)
        if updated != html:
            index_file.write_text(updated, encoding="utf-8")
            print("  ✅ Updated links in docs/index.html")

    print("✅ Migration complete")


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    docs        = Path("docs")
    archive_dir = docs / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    # One-time migration: move flat archive files into monthly subdirs
    migrate_archive(docs)

    # Ensure GitHub Pages serves raw files (no Jekyll processing)
    (docs / ".nojekyll").touch()

    # Load existing archive index
    archive_json    = docs / "archive.json"
    archive_entries: list = []
    if archive_json.exists():
        try:
            archive_entries = json.loads(archive_json.read_text("utf-8"))
        except json.JSONDecodeError:
            archive_entries = []

    # Collect recently-covered article URLs for deduplication (before generation)
    recent_urls = get_recent_article_urls(archive_dir)
    if recent_urls:
        print(f"🔍 Loaded {len(recent_urls)} recent URLs for deduplication")

    # Build prompt and call Claude
    user_prompt = build_user_prompt(recent_urls)
    briefing_md = fetch_briefing(user_prompt)
    print(f"✅ Received {len(briefing_md)} chars from Claude")

    # Add today to archive entries BEFORE rendering so it appears in the nav
    archive_updated = not any(e["date"] == TODAY_ISO for e in archive_entries)
    if archive_updated:
        archive_entries.append({"date": TODAY_ISO})
        archive_entries.sort(key=lambda e: e["date"])

    # Render full HTML page
    page_html = render_page(briefing_md, archive_entries)

    # Save archive copy (monthly subdir: docs/archive/YYYY-MM/YYYY-MM-DD.html)
    month_dir    = archive_dir / TODAY_ISO[:7]
    month_dir.mkdir(parents=True, exist_ok=True)
    archive_file = month_dir / f"{TODAY_ISO}.html"
    archive_file.write_text(page_html, encoding="utf-8")
    print(f"✅ Saved  → docs/archive/{TODAY_ISO[:7]}/{TODAY_ISO}.html")

    # Update index (latest briefing = homepage)
    (docs / "index.html").write_text(page_html, encoding="utf-8")
    print(f"✅ Updated → docs/index.html")

    # Persist archive index only when a new entry was added
    if archive_updated:
        archive_json.write_text(
            json.dumps(archive_entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"✅ Updated → docs/archive.json")


if __name__ == "__main__":
    main()
