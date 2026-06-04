"""Gemini-powered conversation logic for Makan Buddy.

Holds the named system prompt, the Gemini client setup, the main response call
(with optional Google Search grounding for newer places), lightweight preference
extraction, and the session-summary helper. All network calls are wrapped so a
failure returns a friendly message instead of crashing the app.
"""

import os
import re

from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables from .env as soon as the module is imported.
load_dotenv()

MODEL_NAME = "gemini-2.5-flash"

# Delimiter the model uses to list the exact place names it recommended this turn,
# on a final "PICKS:" line that the app parses out of the visible reply.
PICKS_DELIM = "||"

# --- The designed system prompt (named constant, per the capstone spec) ---------
SYSTEM_PROMPT = """You are "Makan Buddy", a warm, friendly Singaporean food guide who helps people \
decide where to eat across Singapore. You recommend specific food PLACES — hawker centres, food \
courts, cafes, and restaurants of all cuisines.

PERSONALITY & TONE
- Speak like a friendly local makan kaki. Use light, natural Singlish sprinkles (lah, can, shiok, \
sedap, steady) but stay clear and easy to read. Do not overdo it.
- Be encouraging and concise. No long essays.

HOW TO RECOMMEND
- You will be given a CANDIDATE LIST of real places that already match the user's stated \
preferences. Recommend ONLY places from that list. Never invent stall names, addresses, or details.
- Recommend a shortlist of 2-3 places per turn so the user can choose, unless they ask for just one.
- For each pick, give one short, vivid reason (signature dish, vibe, or why it fits their craving / \
location / dietary need).
- Respect dietary needs strictly. If the user says halal, vegetarian, or no pork, only suggest \
places that satisfy it.

ASKING QUESTIONS (when the request is vague)
- If you do not yet know enough to recommend well, ask ONE most-useful question at a time — usually \
in this order: location (which area or MRT?), then dietary needs, then craving or budget. Do not \
interrogate with many questions at once.

MEMORY
- You are given the user's saved preferences and places already recommended this session. Refer back \
to them naturally ("since you liked laksa earlier...") and do NOT repeat a place you already suggested.

NEWER / WEB RESULTS
- If web search results are provided, you may use them ONLY for genuinely newer or trending places, \
or when nothing in the candidate list fits. Make clear these are newer finds.

STAYING ON TOPIC
- You only talk about Singapore food and where to eat. If asked anything off-topic, politely and \
playfully steer back to food.

OUTPUT FORMAT (important)
- Write your friendly reply first.
- Then, on the very LAST line, output exactly: PICKS: Name 1 || Name 2 || Name 3
  listing the exact names of the places you recommended this turn, separated by "||".
- If you are only asking a clarifying question and recommended nothing, output exactly: PICKS:
- Never mention the PICKS line in your prose; it is for the app to read.
"""

# Hints that suggest the user wants newer/trending places, which auto-enables search.
_NEWER_HINTS = [
    "new ", "newer", "just opened", "recently opened", "latest", "trending",
    "hidden gem", "viral", "this year", "2024", "2025", "2026", "newly",
]


def init_client():
    """Create and return a Gemini client, or raise a clear error if the key is missing."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key.strip() in ("", "your_gemini_api_key_here"):
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key "
            "from https://ai.google.dev"
        )
    return genai.Client(api_key=api_key)


def wants_newer(user_msg):
    """Return True if the message hints the user wants newer or trending places."""
    msg = user_msg.lower()
    return any(hint in msg for hint in _NEWER_HINTS)


def extract_prefs(user_msg, prefs, known_areas=None):
    """Update and return the preferences dict from simple keywords in the user's message.

    Deterministic keyword parsing (no API call) keeps it fast and easy to explain.
    `known_areas` is an optional iterable of area/MRT names (from the dataset) used
    to detect the user's location.
    """
    prefs = dict(prefs)
    msg = user_msg.lower()

    # Location: match the longest known area/MRT name that appears in the message.
    if known_areas:
        matched = [a for a in known_areas if a.lower() in msg]
        if matched:
            prefs["area"] = max(matched, key=len)

    # Venue type.
    if "hawker" in msg:
        prefs["venue_type"] = "hawker"
    elif "food court" in msg or "foodcourt" in msg:
        prefs["venue_type"] = "food_court"
    elif "cafe" in msg or "café" in msg or "brunch" in msg:
        prefs["venue_type"] = "cafe"
    elif "restaurant" in msg or "sit down" in msg or "sit-down" in msg:
        prefs["venue_type"] = "restaurant"

    # Dietary needs.
    if "halal" in msg:
        prefs["halal"] = True
    if "vegetarian" in msg or "veggie" in msg or "vegan" in msg or "no meat" in msg:
        prefs["vegetarian_options"] = True
    if "no pork" in msg or "without pork" in msg or "no lard" in msg:
        prefs["no_pork_no_lard"] = True

    # Budget from dollar-sign or words.
    if "$$$" in user_msg or "atas" in msg or "fine dining" in msg or "treat" in msg:
        prefs["budget"] = "$$$"
    elif "cheap" in msg or "budget" in msg or "affordable" in msg:
        prefs["budget"] = "$"

    # Cuisine keywords.
    for cuisine in ["chinese", "malay", "indian", "peranakan", "nyonya", "western",
                    "japanese", "korean", "thai", "dessert"]:
        if cuisine in msg:
            prefs["cuisine"] = "Peranakan" if cuisine == "nyonya" else cuisine.capitalize()
            break

    return prefs


def _build_contents(history, user_msg, candidate_context, relax_note=""):
    """Assemble the Gemini `contents` list from prior turns and the current message."""
    contents = []
    for turn in history:
        role = "model" if turn["role"] == "assistant" else "user"
        contents.append(types.Content(role=role, parts=[types.Part(text=turn["content"])]))

    note = f"{relax_note}\n\n" if relax_note else ""
    current = (
        "CANDIDATE LIST (recommend only from these unless using web results):\n"
        f"{candidate_context}\n\n"
        f"{note}"
        f"User message: {user_msg}"
    )
    contents.append(types.Content(role="user", parts=[types.Part(text=current)]))
    return contents


def _extract_sources(response):
    """Pull web source titles and URLs from grounding metadata, if any."""
    sources = []
    try:
        meta = response.candidates[0].grounding_metadata
        for chunk in (meta.grounding_chunks or []):
            web = getattr(chunk, "web", None)
            if web and getattr(web, "uri", None):
                sources.append({"title": getattr(web, "title", "") or web.uri, "uri": web.uri})
    except (AttributeError, IndexError, TypeError):
        pass
    return sources


def _split_picks(text):
    """Separate the visible reply from the trailing PICKS line; return (reply, picks)."""
    match = re.search(r"PICKS:\s*(.*)\s*$", text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return text.strip(), []
    reply = text[: match.start()].strip()
    raw = match.group(1).strip()
    picks = [p.strip() for p in raw.split(PICKS_DELIM) if p.strip()] if raw else []
    return reply, picks


def get_response(client, history, user_msg, candidate_context, use_search=False, relax_note=""):
    """Send the conversation to Gemini and return a structured result dict.

    `relax_note` is an optional honesty note (e.g. "no exact-area match, picks are
    a few stops away") injected so the bot does not overstate how well picks fit.
    Returns keys: reply, picks (list of place names), sources (list of {title,uri}),
    used_search (bool), and error (None or a user-facing message).
    """
    config_args = {
        "system_instruction": SYSTEM_PROMPT,
        "temperature": 0.7,
    }
    if use_search:
        config_args["tools"] = [types.Tool(google_search=types.GoogleSearch())]

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=_build_contents(history, user_msg, candidate_context, relax_note),
            config=types.GenerateContentConfig(**config_args),
        )
    except Exception as exc:  # noqa: BLE001 - surface any API/network error gracefully
        return {
            "reply": "", "picks": [], "sources": [], "used_search": use_search,
            "error": f"Aiyah, I couldn't reach the food brain right now ({exc}). "
                     "Please check your connection or API key and try again.",
        }

    text = (getattr(response, "text", None) or "").strip()
    if not text:
        return {
            "reply": "", "picks": [], "sources": [], "used_search": use_search,
            "error": "Hmm, I got an empty reply from the model. Try rephrasing your request.",
        }

    reply, picks = _split_picks(text)
    return {
        "reply": reply,
        "picks": picks,
        "sources": _extract_sources(response) if use_search else [],
        "used_search": use_search,
        "error": None,
    }


def session_summary(client, history, past_recs, prefs):
    """Generate a short end-of-session recap of recommendations and detected preferences."""
    pref_bits = [f"{k}: {v}" for k, v in prefs.items() if v]
    summary_request = (
        "Write a short, friendly session summary for the user. List the places you recommended "
        f"this session: {', '.join(past_recs) if past_recs else 'none yet'}. "
        f"Detected preferences: {', '.join(pref_bits) if pref_bits else 'none noted'}. "
        "End with one cheerful line inviting them back. Do NOT output a PICKS line."
    )
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[types.Content(role="user", parts=[types.Part(text=summary_request)])],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT, temperature=0.6
            ),
        )
        text = (getattr(response, "text", None) or "").strip()
        return _split_picks(text)[0] if text else "No summary available right now."
    except Exception as exc:  # noqa: BLE001
        return f"Couldn't generate a summary right now ({exc})."
