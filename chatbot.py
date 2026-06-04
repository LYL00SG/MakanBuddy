"""OpenAI-powered conversation logic for Makan Buddy.

Holds the named system prompt, the OpenAI client setup, the main response call
(with optional web search for newer places), lightweight preference extraction,
and the session-summary helper. All network calls are wrapped so a failure
returns a friendly message instead of crashing the app.
"""

import json
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env as soon as the module is imported.
load_dotenv()

MODEL_NAME = "gpt-4o-mini"

# Built-in web-search tool name(s) to try, in order, for the "newer places" feature.
WEB_SEARCH_TOOLS = ["web_search", "web_search_preview"]

# --- The designed system prompt (named constant, per the capstone spec) ---------
SYSTEM_PROMPT = """You are "Makan Buddy", a warm, friendly Singaporean food guide who helps people \
decide where to eat across Singapore. You recommend specific, real food PLACES — hawker centres, \
food courts, cafes, restaurants, and street-food spots / food streets (e.g. Haji Lane, Joo Chiat \
Road, a satay street) of all cuisines.

PERSONALITY & TONE
- Speak like a friendly local makan kaki. Use light, natural Singlish sprinkles (lah, can, shiok, \
sedap, steady) but stay clear and easy to read. Do not overdo it.
- Be encouraging and concise. No long essays.

THE REPLY FIELD (very important)
- The `reply` is just a SHORT, friendly intro of ONE or TWO sentences (e.g. "Craving Japanese near \
Serangoon? Here are a few good ones:").
- Do NOT list the places, their details, ratings, addresses, opening hours, or descriptions in the \
reply. ALL of that belongs ONLY in the `picks`. Never duplicate pick details in the reply.

HOW TO RECOMMEND
- ALWAYS use web search to find REAL, CURRENT places. Never invent names or details — every pick \
must come from a source you actually found.
- Return EXACTLY 2-3 picks (unless the user asks for just one). The number of picks must match what \
your intro implies — do not mention more places than you put in `picks`.
- For each pick, fill every field accurately from your source. The `area` MUST be the SPECIFIC real \
location of THAT outlet (building/mall name and street if known, plus neighbourhood), and `mrt` the \
nearest station — never just copy the area the user asked for. Many eateries are chains with many \
outlets: only recommend the outlet that genuinely matches the user's requested location.
- Include the `rating` (with review count) when your source shows one, so the user can gauge \
credibility. If there is no rating, leave it empty — never make one up.
- If you cannot confirm a place actually exists at the user's requested mall/area, either recommend \
the nearest real outlet you DID find (and make the real location clear in `area`), or say so in the \
reply — do not fake the location.
- Respect dietary needs strictly. If the user says halal, vegetarian, or no pork, only suggest \
places that genuinely satisfy it, and set the `dietary` field to confirm it from your source. If \
you cannot confirm a place meets the dietary need, do NOT present it as meeting it — leave `dietary` \
empty or pick a place you can confirm.
- The `why` is one short, vivid reason (signature dish, vibe, or why it fits). Do not put opening \
hours or "Closed/Open" status in any field.

ASKING QUESTIONS (when the request is vague)
- If you do not yet know enough to recommend well, ask ONE most-useful question at a time — usually \
location (which area or MRT?), then dietary needs, then craving or budget. In that case, return an \
empty picks list and put your question in the reply. Do not interrogate with many questions at once.

MEMORY
- You are given the user's saved preferences and places already recommended this session. Refer back \
to them naturally and do NOT repeat a place you already suggested.

STAYING ON TOPIC
- You only talk about Singapore food and where to eat. If asked anything off-topic, politely and \
playfully steer back to food (return an empty picks list).
"""


def _friendly_error(exc):
    """Turn a raw OpenAI/network exception into a short, in-character user message."""
    text = str(exc)
    low = text.lower()

    # Out of credits / billing (OpenAI insufficient_quota).
    if "insufficient_quota" in low or ("quota" in low and "billing" in low):
        return (
            "Aiyah, my OpenAI credits seem to have run out. 🍜 Please check the billing/credits "
            "on the OpenAI account for this API key, then try again."
        )

    # Rate limit (HTTP 429): try to surface a retry hint if present.
    if "429" in text or "rate limit" in low or "rate_limit" in low or "too many requests" in low:
        match = re.search(r"retry(?: again)? (?:in|after) ([0-9.]+)\s*s", low)
        when = f"in about {int(round(float(match.group(1))))} seconds" if match else "in a little while"
        return (
            "Aiyah, makan break! 🍜 I'm being rate-limited by OpenAI right now. "
            f"Please try again {when}."
        )

    # Authentication / API key problems.
    if any(k in low for k in ("invalid_api_key", "incorrect api key", "api key not valid",
                              "api_key_invalid", "permission_denied", "unauthenticated",
                              " 401", " 403")):
        return (
            "Aiyah, my API key got problem (invalid or not authorised). Please check "
            "OPENAI_API_KEY in your .env file and restart the app."
        )

    # Network / service availability.
    if any(k in low for k in ("deadline", "timeout", "timed out", "unavailable", "503",
                              "connection", "network", "getaddrinfo", "failed to establish")):
        return (
            "Aiyah, cannot reach OpenAI right now — looks like a network or service hiccup. "
            "Please check your connection and try again in a moment."
        )

    # Fallback: stay friendly and do not dump the raw exception.
    return "Aiyah, something went wrong reaching the food brain. Please try again in a moment."


def init_client():
    """Create and return an OpenAI client, or raise a clear error if the key is missing."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.strip() in ("", "your_openai_api_key_here"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key "
            "from https://platform.openai.com/api-keys"
        )
    return OpenAI(api_key=api_key)


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
    elif "street food" in msg or "food street" in msg or "street-food" in msg:
        prefs["venue_type"] = "street"
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


# JSON schema that forces the model to return a friendly reply plus structured picks,
# so we can render rich cards even while the web_search tool is active.
RECS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "reply": {
            "type": "string",
            "description": "A SHORT 1-2 sentence friendly intro only. Do NOT list places, details, "
                           "ratings, addresses, or descriptions here — those go in picks.",
        },
        "picks": {
            "type": "array",
            "description": "Exactly 2-3 recommended places (empty if asking a question or off-topic).",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "area": {"type": "string",
                             "description": "SPECIFIC real location of THIS outlet from your source "
                                            "— building/mall name and street if known, plus "
                                            "neighbourhood (e.g. 'NEX Mall, Serangoon Central' or "
                                            "'30 Seng Poh Road, Tiong Bahru'). Never just the area "
                                            "the user asked for."},
                    "mrt": {"type": "string",
                            "description": "Nearest MRT to this outlet's real location."},
                    "cuisine": {"type": "string"},
                    "type": {"type": "string",
                             "description": "One of: hawker, food court, cafe, restaurant, or "
                                            "street (a street-food cluster / food street)."},
                    "price": {"type": "string", "description": "Rough price range, e.g. $ or ~$15."},
                    "rating": {"type": "string",
                               "description": "Review rating with count if your source has one, "
                                              "e.g. '4.4 (278 reviews)'. Empty string if unknown — "
                                              "never invent a rating."},
                    "dietary": {"type": "string",
                                "description": "Dietary status confirmed from your source when "
                                               "relevant, e.g. 'Halal-certified', 'Halal', "
                                               "'Vegetarian-friendly', 'No pork'. Empty string if "
                                               "you cannot confirm — NEVER claim halal/vegetarian "
                                               "unless your source supports it."},
                    "why": {"type": "string",
                            "description": "One short, vivid reason. No opening hours or open/closed "
                                           "status."},
                    "source_url": {"type": "string", "description": "URL of the source you used."},
                },
                "required": ["name", "area", "mrt", "cuisine", "type", "price", "rating", "dietary",
                             "why", "source_url"],
            },
        },
    },
    "required": ["reply", "picks"],
}


def _build_input(history, user_msg, constraints_note=""):
    """Assemble the Responses API `input` list from prior turns and the current message."""
    items = []
    for turn in history:
        role = "assistant" if turn["role"] == "assistant" else "user"
        items.append({"role": role, "content": turn["content"]})

    note = f"{constraints_note}\n\n" if constraints_note else ""
    items.append({"role": "user", "content": f"{note}User message: {user_msg}"})
    return items


def _extract_sources(response):
    """Pull web source titles and URLs from the response's url_citation annotations."""
    sources, seen = [], set()
    try:
        for item in (response.output or []):
            if getattr(item, "type", None) != "message":
                continue
            for part in (getattr(item, "content", None) or []):
                for ann in (getattr(part, "annotations", None) or []):
                    if getattr(ann, "type", None) == "url_citation":
                        url = getattr(ann, "url", None)
                        if url and url not in seen:
                            seen.add(url)
                            sources.append({"title": getattr(ann, "title", "") or url, "uri": url})
    except (AttributeError, TypeError):
        pass
    return sources


def _is_tool_error(exc):
    """Return True if the exception looks like an unsupported/invalid web-search tool error."""
    low = str(exc).lower()
    tool_words = any(w in low for w in ("web_search", "tool", "tools"))
    fault_words = any(w in low for w in ("unsupported", "not supported", "invalid", "unknown",
                                         "not allowed", "does not support"))
    return tool_words and fault_words


def _create_structured(client, input_items):
    """Call the Responses API with web search + structured JSON output.

    Tries the web-search tool variants, degrading to no tool only on tool-related
    errors. Returns (response, used_search); quota/auth/network errors propagate.
    """
    base = {
        "model": MODEL_NAME,
        "instructions": SYSTEM_PROMPT,
        "input": input_items,
        "temperature": 0.5,
        "text": {"format": {"type": "json_schema", "name": "recommendations",
                             "schema": RECS_SCHEMA, "strict": True}},
    }
    for tool in WEB_SEARCH_TOOLS:
        try:
            return client.responses.create(**base, tools=[{"type": tool}]), True
        except Exception as exc:  # noqa: BLE001
            if not _is_tool_error(exc):
                raise  # real error (quota/auth/network) — let the caller handle it
            continue  # this tool name not supported; try the next variant
    # No web-search variant worked; answer from the model's own knowledge instead.
    return client.responses.create(**base), False


def get_response(client, history, user_msg, constraints_note=""):
    """Recommend live places via OpenAI web search, returning a structured result dict.

    Returns keys: reply, picks (list of dicts with name/area/mrt/cuisine/type/price/
    why/source_url), sources (list of {title,uri}), used_search (bool), and error
    (None or a user-facing message).
    """
    input_items = _build_input(history, user_msg, constraints_note)

    try:
        response, used_search = _create_structured(client, input_items)
    except Exception as exc:  # noqa: BLE001 - surface any API/network error gracefully
        return {"reply": "", "picks": [], "sources": [], "used_search": True,
                "error": _friendly_error(exc)}

    text = (getattr(response, "output_text", None) or "").strip()
    if not text:
        return {"reply": "", "picks": [], "sources": [], "used_search": used_search,
                "error": "Hmm, I got an empty reply from the model. Try rephrasing your request."}

    try:
        data = json.loads(text)
        picks = data.get("picks", []) or []
        reply = (data.get("reply", "") or "").strip()
    except (json.JSONDecodeError, AttributeError):
        # Structured output failed to parse; show the raw text and no cards.
        return {"reply": text, "picks": [], "sources": _extract_sources(response),
                "used_search": used_search, "error": None}

    return {
        "reply": reply,
        "picks": picks,
        "sources": _extract_sources(response),
        "used_search": used_search,
        "error": None,
    }


def session_summary(client, history, past_recs, prefs):
    """Generate a short end-of-session recap of recommendations and detected preferences."""
    pref_bits = [f"{k}: {v}" for k, v in prefs.items() if v]
    summary_request = (
        "Write a short, friendly session summary for the user. List the places you recommended "
        f"this session: {', '.join(past_recs) if past_recs else 'none yet'}. "
        f"Detected preferences: {', '.join(pref_bits) if pref_bits else 'none noted'}. "
        "End with one cheerful line inviting them back."
    )
    try:
        response = client.responses.create(
            model=MODEL_NAME,
            instructions=SYSTEM_PROMPT,
            input=[{"role": "user", "content": summary_request}],
            temperature=0.6,
        )
        text = (getattr(response, "output_text", None) or "").strip()
        return text if text else "No summary available right now."
    except Exception as exc:  # noqa: BLE001
        return _friendly_error(exc)
