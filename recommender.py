"""Loads and filters the curated Singapore food-places dataset (offline fallback).

This module is the offline data layer for Makan Buddy: it reads the local JSON of
real food places and narrows them down by the user's preferences for the dataset
fallback and the "Surprise me" pick, plus a Google Maps link builder. The app's
primary recommendations come from live web search (see chatbot.py).
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
VENUE_TYPES = ["hawker", "food_court", "cafe", "restaurant", "street"]
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


def build_candidates(places, prefs, exclude_names=None):
    """Return candidate places, relaxing soft constraints until some are found.

    Dietary flags are never dropped; budget then venue type then area are dropped
    in turn only if the stricter filter yields nothing. Returns (candidates,
    dropped) where `dropped` is the list of constraint keys that had to be loosened
    (empty when there was an exact match), so callers can be honest about it.
    """
    strict = filter_places(places, prefs, exclude_names)
    if strict:
        return strict, []

    # Drop budget, then venue type, then area — but never the dietary requirements.
    for drop in (["budget"], ["budget", "venue_type"], ["budget", "venue_type", "area"]):
        relaxed_prefs = {k: v for k, v in prefs.items() if k not in drop}
        candidates = filter_places(places, relaxed_prefs, exclude_names)
        if candidates:
            # Only report constraints the user had actually set.
            return candidates, [k for k in drop if prefs.get(k)]
    return [], [k for k in ("budget", "venue_type", "area") if prefs.get(k)]


def surprise_pick(places, prefs, exclude_names=None):
    """Return one random place for the current preferences, relaxing soft constraints.

    Uses build_candidates so dietary needs stay strict but budget/venue/area are
    loosened rather than returning nothing. If every match has already been
    recommended, it allows a repeat instead of giving up.
    """
    candidates, _ = build_candidates(places, prefs, exclude_names)
    if not candidates:
        candidates, _ = build_candidates(places, prefs, None)  # allow repeats as a fallback
    return random.choice(candidates) if candidates else None


def maps_link(place):
    """Build a Google Maps search URL for a place using its name and area."""
    query = quote_plus(f"{place['name']} {place.get('area', '')} Singapore")
    return f"https://www.google.com/maps/search/?api=1&query={query}"
