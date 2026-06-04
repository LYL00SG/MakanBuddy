"""Persistent memory for Makan Buddy.

Saves only the user's preferences and the list of places already recommended, so
the bot can greet returning users and avoid repeating itself across app restarts.
The chat transcript itself is not persisted. The file is git-ignored.
"""

import json
import os

MEMORY_PATH = os.path.join(os.path.dirname(__file__), "memory.json")

# Shape returned when no saved memory exists or the file is unreadable.
EMPTY_MEMORY = {"preferences": {}, "past_recommendations": []}


def load_memory(path=MEMORY_PATH):
    """Load saved preferences and past recommendations, returning empty defaults on any failure."""
    if not os.path.exists(path):
        return dict(EMPTY_MEMORY, preferences={}, past_recommendations=[])
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Guard against a malformed file by ensuring both keys exist with the right types.
        return {
            "preferences": dict(data.get("preferences", {})),
            "past_recommendations": list(data.get("past_recommendations", [])),
        }
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return {"preferences": {}, "past_recommendations": []}


def save_memory(preferences, past_recommendations, path=MEMORY_PATH):
    """Write preferences and past recommendations to disk; ignore write errors silently."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {"preferences": preferences, "past_recommendations": past_recommendations},
                f, indent=2, ensure_ascii=False,
            )
    except OSError:
        pass  # Persistence is best-effort; never crash the app over it.


def clear_memory(path=MEMORY_PATH):
    """Delete the saved memory file if it exists (used by the Reset button)."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
