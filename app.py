"""Makan Buddy - a Singapore food recommendation chatbot (Streamlit UI).

Ties together the dataset (recommender), the OpenAI conversation logic (chatbot),
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
    """Create the OpenAI client once; returns (client, error_message)."""
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
    """Render one recommendation card (a live web result or a dataset fallback place)."""
    if card["kind"] == "verified":  # offline dataset fallback
        p = card["place"]
        badges = []
        if p.get("halal"):
            badges.append("🟢 Halal")
        if p.get("vegetarian_options"):
            badges.append("🥬 Veg options")
        if p.get("no_pork_no_lard"):
            badges.append("🚫🐖 No pork/lard")
        with st.container(border=True):
            st.markdown(f"**{p['name']}** &nbsp; 📒 *From local guide*")
            st.caption(
                f"{p['type'].replace('_', ' ').title()} · {p['cuisine']} · {p['area']} "
                f"(MRT: {p['mrt']}) · {esc_money(p['price'])}"
            )
            st.write(f"🍽️ {p['signature_dish']}")
            if badges:
                st.write(" · ".join(badges))
            st.markdown(f"[📍 Open in Google Maps]({recommender.maps_link(p)})")
    else:  # live web result (structured pick from the model)
        p = card["pick"]
        meta = " · ".join(x for x in [
            (p.get("type") or "").replace("_", " ").title() or None,
            p.get("cuisine") or None,
            p.get("area") or None,
            (f"MRT: {p['mrt']}" if p.get("mrt") else None),
            (esc_money(p["price"]) if p.get("price") else None),
        ] if x)
        with st.container(border=True):
            st.markdown(f"**{p.get('name', 'Unknown')}** &nbsp; 🌐 *Live web result*")
            if meta:
                st.caption(meta)
            if p.get("rating"):
                st.write(f"⭐ {p['rating']}")
            if p.get("why"):
                st.write(f"🍽️ {p['why']}")
            links = [f"[📍 Maps]({recommender.maps_link({'name': p.get('name', ''), 'area': p.get('area', '')})})"]
            if p.get("source_url"):
                links.append(f"[🔗 Source]({p['source_url']})")
            st.markdown(" &nbsp; ".join(links))


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


def remember(names):
    """Add newly recommended place names to memory (no repeats) and persist."""
    for name in names:
        if name and name not in st.session_state.past_recommendations:
            st.session_state.past_recommendations.append(name)
    memory_store.save_memory(st.session_state.prefs, st.session_state.past_recommendations)


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


def constraints_note(prefs, past_recs):
    """Describe the user's preferences and already-suggested places for the model prompt."""
    bits = []
    if prefs.get("area"):
        bits.append(f"near {prefs['area']} (MRT/area)")
    if prefs.get("cuisine"):
        bits.append(f"cuisine: {prefs['cuisine']}")
    if prefs.get("venue_type"):
        bits.append(f"venue type: {prefs['venue_type'].replace('_', ' ')}")
    if prefs.get("budget"):
        bits.append(f"budget around {prefs['budget']}")
    diet = [d for d, k in (("halal", "halal"), ("vegetarian options", "vegetarian_options"),
                           ("no pork/lard", "no_pork_no_lard")) if prefs.get(k)]
    if diet:
        bits.append("dietary (must satisfy): " + ", ".join(diet))

    note = ""
    if bits:
        note += ("USER PREFERENCES (dietary needs are mandatory; honour area/cuisine/budget but "
                 "you may relax the area if nothing fits, saying so honestly): "
                 + "; ".join(bits) + ". ")
    if past_recs:
        note += ("Do NOT repeat these already-suggested places: "
                 + ", ".join(past_recs[-15:]) + ". ")
    return note.strip()


def offline_recommend(prefs, intro):
    """Append a recommendation drawn from the local dataset (used when web search fails)."""
    candidates, _ = recommender.build_candidates(
        get_places(), prefs, st.session_state.past_recommendations
    )
    picks = candidates[:3]
    if not picks:
        return False
    remember([p["name"] for p in picks])
    st.session_state.messages.append({
        "role": "assistant", "content": intro,
        "cards": [{"kind": "verified", "place": p} for p in picks],
    })
    return True


def handle_turn(user_msg):
    """Process a user message: web-search for live recommendations, with a dataset fallback."""
    st.session_state.messages.append({"role": "user", "content": user_msg, "cards": []})

    prefs = current_prefs(user_msg)
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[:-1]
        if m["content"]
    ][-MAX_HISTORY_TURNS:]

    # Web-first (default). The sidebar toggle lets the user switch to offline dataset mode.
    if not st.session_state.get("web_toggle", True):
        if not offline_recommend(prefs, "Here are some picks from my local guide 📒:"):
            st.session_state.messages.append({
                "role": "assistant",
                "content": "Hmm, nothing in my local guide matches those filters — try loosening them!",
                "cards": [],
            })
        return

    note = constraints_note(prefs, st.session_state.past_recommendations)
    with st.spinner("Searching the web for the latest makan..."):
        result = chatbot.get_response(get_client()[0], history, user_msg, note)

    if result["error"]:
        # Web search failed (quota/network) — fall back to the offline dataset.
        if not offline_recommend(
            prefs, f"⚠️ {result['error']}\n\nMeanwhile, here are some picks from my local guide 📒:"
        ):
            st.session_state.messages.append(
                {"role": "assistant", "content": f"⚠️ {result['error']}", "cards": []}
            )
        return

    if not result["picks"]:
        # Clarifying question or off-topic redirect — show the reply, no cards.
        st.session_state.messages.append(
            {"role": "assistant", "content": result["reply"], "cards": []}
        )
        return

    remember([p.get("name") for p in result["picks"]])
    st.session_state.messages.append({
        "role": "assistant", "content": result["reply"],
        "cards": [{"kind": "web", "pick": p} for p in result["picks"]],
        "sources": result["sources"],
    })


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
    remember([pick["name"]])
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
st.caption("Your friendly Singapore food guide — hawker, food court, cafe, restaurant, or street food.")

client, client_error = get_client()
if client_error:
    st.error(
        f"⚠️ {client_error}\n\nThe app loaded, but recommendations need a working OpenAI API key. "
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
    st.toggle("Live web search (latest info)", key="web_toggle", value=True,
              help="On: search the web for the latest, real places. Off: use the offline "
                   "local guide only (no API cost).")

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
