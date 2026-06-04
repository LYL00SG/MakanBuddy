"""Makan Buddy - a Singapore food recommendation chatbot (Streamlit UI).

Ties together the dataset (recommender), the Gemini conversation logic (chatbot),
and cross-run memory (memory_store) into a chat interface with rich place cards,
sidebar filters, a "surprise me" pick, and a session summary.
"""

import streamlit as st

import chatbot
import memory_store
import recommender

# --- Page setup -----------------------------------------------------------------
st.set_page_config(page_title="Makan Buddy", page_icon="🍜", layout="centered")

MAX_HISTORY_TURNS = 12  # how many prior messages to send to the model for context

# Budget tiers. Values stay as "$"/"$$"/"$$$" for filtering; labels are escaped so
# Streamlit does not treat the dollar signs as LaTeX math delimiters.
BUDGET_OPTIONS = ["Any", "$", "$$", "$$$"]
BUDGET_LABELS = {"Any": "Any", "$": "\\$ cheap", "$$": "\\$\\$ mid", "$$$": "\\$\\$\\$ atas"}

# Friendly labels for the "What I know about you" panel.
PREF_LABELS = {"area": "📍 Area", "cuisine": "🍲 Cuisine", "venue_type": "🏠 Venue"}
DIET_LABELS = {
    "halal": "Halal", "vegetarian_options": "Vegetarian", "no_pork_no_lard": "No pork/lard",
}


def esc_money(text):
    """Escape dollar signs so Streamlit markdown renders them literally, not as LaTeX."""
    return str(text).replace("$", "\\$")


@st.cache_data
def get_places():
    """Load the curated places dataset once and cache it for the session."""
    return recommender.load_places()


@st.cache_data
def get_known_areas():
    """Return the set of area/region names used for location detection."""
    places = get_places()
    return {p["area"] for p in places} | {p["region"] for p in places}


@st.cache_resource
def get_client():
    """Create the Gemini client once; returns (client, error_message)."""
    try:
        return chatbot.init_client(), None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def init_state():
    """Initialise session state, rehydrating saved preferences and past recommendations."""
    if st.session_state.get("_initialised"):
        return
    saved = memory_store.load_memory()
    st.session_state.prefs = saved["preferences"]
    st.session_state.past_recommendations = saved["past_recommendations"]
    st.session_state.messages = []

    past = st.session_state.past_recommendations
    if past:
        greeting = (
            "Welcome back, makan kaki! 👋 Last time I pointed you to "
            f"**{', '.join(past[-3:])}**. Craving anything today?"
        )
    else:
        greeting = (
            "Hello! I'm **Makan Buddy** 🍜 — tell me what you're craving, which area "
            "or MRT you're near, and any dietary needs, and I'll suggest where to makan!"
        )
    st.session_state.messages.append({"role": "assistant", "content": greeting, "cards": []})
    st.session_state._initialised = True


def render_card(card):
    """Render one recommendation card (a verified dataset place or a newer web find)."""
    if card["kind"] == "verified":
        p = card["place"]
        badges = []
        if p.get("halal"):
            badges.append("🟢 Halal")
        if p.get("vegetarian_options"):
            badges.append("🥬 Veg options")
        if p.get("no_pork_no_lard"):
            badges.append("🚫🐖 No pork/lard")
        badge_str = " · ".join(badges) if badges else ""
        with st.container(border=True):
            st.markdown(f"**{p['name']}** &nbsp; ✅ *Verified*")
            st.caption(
                f"{p['type'].replace('_', ' ').title()} · {p['cuisine']} · {p['area']} "
                f"(MRT: {p['mrt']}) · {esc_money(p['price'])}"
            )
            st.write(f"🍽️ {p['signature_dish']}")
            if badge_str:
                st.write(badge_str)
            st.markdown(f"[📍 Open in Google Maps]({recommender.maps_link(p)})")
    else:  # newer find from web search
        with st.container(border=True):
            st.markdown(f"**{card['name']}** &nbsp; ✨ *Newer find*")
            if card.get("source"):
                st.markdown(f"[🔗 {card['source']['title']}]({card['source']['uri']})")
            else:
                st.caption("Suggested from a live web search.")


def render_message(msg):
    """Render a chat message bubble plus any attached cards or sources."""
    with st.chat_message(msg["role"]):
        if msg["content"]:
            st.markdown(msg["content"])
        for card in msg.get("cards", []):
            render_card(card)
        if msg.get("sources"):
            with st.expander("Sources"):
                for s in msg["sources"]:
                    st.markdown(f"- [{s['title']}]({s['uri']})")


def build_cards(picks, sources):
    """Turn model-picked names into cards: verified if in the dataset, else newer finds."""
    places = get_places()
    cards, new_verified_names = [], []
    leftover_sources = list(sources)
    for name in picks:
        place = recommender.find_by_name(places, name)
        if place:
            cards.append({"kind": "verified", "place": place})
            new_verified_names.append(place["name"])
        else:
            source = leftover_sources.pop(0) if leftover_sources else None
            cards.append({"kind": "newer", "name": name, "source": source})
    return cards, new_verified_names


def current_prefs(user_msg=None):
    """Merge saved prefs, message-derived prefs, and sidebar toggles into one dict."""
    prefs = dict(st.session_state.prefs)
    if user_msg:
        prefs = chatbot.extract_prefs(user_msg, prefs, get_known_areas())
    # Sidebar toggles force a requirement on when enabled (they override).
    if st.session_state.get("halal_toggle"):
        prefs["halal"] = True
    if st.session_state.get("veg_toggle"):
        prefs["vegetarian_options"] = True
    if st.session_state.get("nopork_toggle"):
        prefs["no_pork_no_lard"] = True
    budget = st.session_state.get("budget_choice", "Any")
    if budget != "Any":
        prefs["budget"] = budget
    st.session_state.prefs = prefs
    return prefs


def relax_note(dropped, prefs):
    """Build an honesty note telling the model which constraints were loosened."""
    parts = []
    if "area" in dropped and prefs.get("area"):
        parts.append(f"no places exactly in/around '{prefs['area']}'")
    if "budget" in dropped and prefs.get("budget"):
        parts.append("none at the requested budget")
    if "venue_type" in dropped and prefs.get("venue_type"):
        parts.append(f"none of the venue type '{prefs['venue_type'].replace('_', ' ')}'")
    if not parts:
        return ""
    return (
        "NOTE TO YOU (not the user): the candidate list was widened because "
        + ", and ".join(parts)
        + ". Be upfront that these picks may not exactly match — e.g. a few MRT stops away "
        "or a different budget — and do not overstate how near or perfect they are."
    )


def handle_turn(user_msg):
    """Process a user message: filter candidates, call Gemini, render reply and cards."""
    st.session_state.messages.append({"role": "user", "content": user_msg, "cards": []})

    prefs = current_prefs(user_msg)
    candidates, dropped = recommender.build_candidates(
        get_places(), prefs, st.session_state.past_recommendations
    )
    use_search = (
        st.session_state.get("newer_toggle", False)
        or chatbot.wants_newer(user_msg)
        or not candidates
    )
    context = recommender.format_for_prompt(candidates)
    note = relax_note(dropped, prefs)
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[:-1]
        if m["content"]
    ][-MAX_HISTORY_TURNS:]

    with st.spinner("Finding good makan..."):
        result = chatbot.get_response(
            get_client()[0], history, user_msg, context, use_search, note
        )

    if result["error"]:
        st.session_state.messages.append(
            {"role": "assistant", "content": f"⚠️ {result['error']}", "cards": []}
        )
        return

    cards, new_names = build_cards(result["picks"], result["sources"])
    for name in new_names:
        if name not in st.session_state.past_recommendations:
            st.session_state.past_recommendations.append(name)
    memory_store.save_memory(st.session_state.prefs, st.session_state.past_recommendations)
    st.session_state.messages.append(
        {"role": "assistant", "content": result["reply"], "cards": cards,
         "sources": result["sources"]}
    )


def do_surprise():
    """Pick one random place matching current preferences and add it to the chat."""
    prefs = current_prefs()
    pick = recommender.surprise_pick(get_places(), prefs, st.session_state.past_recommendations)
    if not pick:
        st.session_state.messages.append(
            {"role": "assistant",
             "content": "Cannot find a fresh surprise for those filters lah — try loosening them!",
             "cards": []}
        )
        return
    st.session_state.past_recommendations.append(pick["name"])
    memory_store.save_memory(st.session_state.prefs, st.session_state.past_recommendations)
    st.session_state.messages.append(
        {"role": "assistant",
         "content": f"🎲 Surprise pick — go try **{pick['name']}**! {pick['signature_dish']}, shiok one.",
         "cards": [{"kind": "verified", "place": pick}]}
    )


def do_summary():
    """Generate and append an end-of-session summary."""
    with st.spinner("Wrapping up your makan session..."):
        text = chatbot.session_summary(
            get_client()[0],
            st.session_state.messages,
            st.session_state.past_recommendations,
            st.session_state.prefs,
        )
    st.session_state.messages.append({"role": "assistant", "content": text, "cards": []})


def do_reset():
    """Clear saved memory and reset the session to a fresh start."""
    memory_store.clear_memory()
    for key in ("_initialised", "prefs", "past_recommendations", "messages"):
        st.session_state.pop(key, None)


# --- App body -------------------------------------------------------------------
st.title("🍜 Makan Buddy")
st.caption("Your friendly Singapore food guide — hawker, food court, cafe, or restaurant.")

client, client_error = get_client()
if client_error:
    st.error(
        f"⚠️ {client_error}\n\nThe app loaded, but recommendations need a working Gemini API key. "
        "Copy `.env.example` to `.env`, add your key, and restart."
    )
    st.stop()

init_state()

# --- Sidebar --------------------------------------------------------------------
with st.sidebar:
    st.header("Filters")
    st.toggle("Halal only", key="halal_toggle")
    st.toggle("Vegetarian options", key="veg_toggle")
    st.toggle("No pork / no lard", key="nopork_toggle")
    st.radio(
        "Budget", BUDGET_OPTIONS, horizontal=True, key="budget_choice",
        format_func=lambda v: BUDGET_LABELS[v],
    )
    st.toggle("Include newer places (web search)", key="newer_toggle",
              help="Let Makan Buddy search the web for newer or trending spots.")

    st.divider()
    st.header("What I know about you")
    prefs = st.session_state.prefs
    has_any = False

    # Simple single-value prefs (area, cuisine, venue type).
    for key, label in PREF_LABELS.items():
        value = prefs.get(key)
        if value:
            shown = value.replace("_", " ").title() if key == "venue_type" else value
            st.markdown(f"{label}: **{shown}**")
            has_any = True

    # Budget, with escaped dollar signs.
    if prefs.get("budget"):
        st.markdown(f"💵 Budget: **{esc_money(prefs['budget'])}**")
        has_any = True

    # Dietary needs collapsed into one line of badges.
    active_diet = [DIET_LABELS[k] for k in DIET_LABELS if prefs.get(k)]
    if active_diet:
        st.markdown("🥗 Dietary: " + " · ".join(f"**{d}**" for d in active_diet))
        has_any = True

    if not has_any:
        st.caption("Tell me your area, craving, and dietary needs in the chat.")

    st.divider()
    st.header("Past recommendations")
    if st.session_state.past_recommendations:
        for name in st.session_state.past_recommendations:
            st.markdown(f"🍽️ {name}")
    else:
        st.caption("None yet.")

    st.divider()
    surprise_clicked = st.button("🎲 Surprise me", use_container_width=True)
    summary_clicked = st.button("📋 Session summary", use_container_width=True)
    reset_clicked = st.button("🧹 Reset memory", use_container_width=True)

# Sidebar button actions (handled before rendering the chat).
if reset_clicked:
    do_reset()
    st.rerun()
if surprise_clicked:
    do_surprise()
if summary_clicked:
    do_summary()

# --- Chat history ---------------------------------------------------------------
for msg in st.session_state.messages:
    render_message(msg)

# --- Chat input -----------------------------------------------------------------
user_msg = st.chat_input("What are you craving? (e.g. spicy noodles near Bugis, halal)")
if user_msg:
    handle_turn(user_msg)
    st.rerun()
