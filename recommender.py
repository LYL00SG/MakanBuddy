"""Loads and filters the curated Singapore food-places dataset.

This module is the data layer for Makan Buddy: it reads the local JSON of real
food places, narrows them down by the user's preferences, formats the shortlist
as grounding context for Gemini, and provides helper utilities (a random
"surprise" pick and a Google Maps link builder).
"""

import json
import os
import random
from urllib.parse import quote_plus

# Path to the curated dataset, resolved relative to this file so the app runs
# from any working directory.
DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "places.json")

# Venue types and dietary keys we support, kept here so the UI and filter logic
# stay in sync.
VENUE_TYPES = ["hawker", "food_court", "cafe", "restaurant"]
DIETARY_KEYS = ["halal", "vegetarian_options", "no_pork_no_lard"]


def load_places(path=DATA_PATH):
    """Read the curated food-places dataset from disk and return it as a list."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _matches_text(place, query, fields):
    """Return True if the lowercased query appears in any of the place's fields."""
    if not query:
        return True
    query = query.lower()
    return any(query in str(place.get(field, "")).lower() for field in fields)


def filter_places(places, prefs, exclude_names=None):
    """Narrow the dataset by venue type, cuisine, area/MRT, dietary flags, and budget.

    `prefs` is a dict that may contain: venue_type, cuisine, area, budget (one of
    '$','$$','$$$'), and the dietary booleans in DIETARY_KEYS. Any already
    recommended names in `exclude_names` are dropped so the bot does not repeat
    itself.
    """
    exclude_names = {n.lower() for n in (exclude_names or [])}
    results = []
    for place in places:
        if place["name"].lower() in exclude_names:
            continue
        if prefs.get("venue_type") and place["type"] != prefs["venue_type"]:
            continue
        if not _matches_text(place, prefs.get("cuisine"), ["cuisine", "signature_dish"]):
            continue
        if not _matches_text(place, prefs.get("area"), ["area", "mrt", "region"]):
            continue
        if prefs.get("budget") and place["price"] != prefs["budget"]:
            continue
        # Dietary flags are strict: if the user requires one, the place must have it.
        if any(prefs.get(key) and not place.get(key) for key in DIETARY_KEYS):
            continue
        results.append(place)
    return results


def format_for_prompt(places, limit=25):
    """Render a (filtered) place list as a compact text block for the model prompt."""
    if not places:
        return "(No places in the dataset match the current preferences.)"
    lines = []
    for p in places[:limit]:
        diet = []
        if p.get("halal"):
            diet.append("halal")
        if p.get("vegetarian_options"):
            diet.append("vegetarian options")
        if p.get("no_pork_no_lard"):
            diet.append("no pork/lard")
        diet_str = f" [{', '.join(diet)}]" if diet else ""
        lines.append(
            f"- {p['name']} | {p['type']} | {p['cuisine']} | {p['area']} "
            f"(MRT: {p['mrt']}) | {p['price']} | {p['signature_dish']}{diet_str}"
        )
    return "\n".join(lines)


def surprise_pick(places, prefs, exclude_names=None):
    """Return one random place matching the current preferences, or None if none fit."""
    candidates = filter_places(places, prefs, exclude_names)
    return random.choice(candidates) if candidates else None


def maps_link(place):
    """Build a Google Maps search URL for a place using its name and area."""
    query = quote_plus(f"{place['name']} {place.get('area', '')} Singapore")
    return f"https://www.google.com/maps/search/?api=1&query={query}"


def find_by_name(places, name):
    """Return the dataset record whose name best matches `name`, or None."""
    name_l = name.lower().strip()
    for place in places:
        if place["name"].lower() == name_l:
            return place
    # Fall back to a loose contains-match so minor wording differences still resolve.
    for place in places:
        if name_l in place["name"].lower() or place["name"].lower() in name_l:
            return place
    return None
