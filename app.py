"""Makan Buddy - a Singapore food recommendation chatbot (Streamlit UI).

Ties together the dataset (recommender), the OpenAI conversation logic (chatbot),
and cross-run memory (memory_store) into a chat interface with rich place cards,
sidebar filters, a "surprise me" pick, and a session summary.
"""

import re
from urllib.parse import urlparse

import streamlit as st

import chatbot
import memory_store
import recommender

# --- Page setup -----------------------------------------------------------------
st.set_page_config(page_title="Makan Buddy", page_icon="🍜", layout="centered")

MAX_HISTORY_TURNS = 12  # how many prior messages to send to the model for context

# Asked when the user gives no location — keep "which area or mrt" so we don't re-ask in a loop.
LOCATION_QUESTION = "I'd love to help you find good makan! 🍜 Which area or MRT are you near?"

# Budget tiers. Values stay as "$"/"$$"/"$$$" for filtering; labels are escaped so
# Streamlit does not treat the dollar signs as LaTeX math delimiters.
BUDGET_OPTIONS = ["Any", "$", "$$", "$$$"]
BUDGET_LABELS = {"Any": "Any", "$": "\\$ cheap", "$$": "\\$\\$ mid", "$$$": "\\$\\$\\$ atas"}

# Chat-inferred preferences shown as removable chips (dietary/venue/budget live in Filters).
PREF_LABELS = {"area": "📍 Area", "cuisine": "🍲 Cuisine"}

# Venue-type filter (values map to the dataset "type" field; "Any" means no filter).
VENUE_FILTER = {
    "Any": "Any", "hawker": "🍜 Hawker", "food_court": "🍱 Food court", "cafe": "☕ Cafe",
    "restaurant": "🍽️ Restaurant", "street": "🌃 Street food",
}
VENUE_FILTER_OPTIONS = list(VENUE_FILTER)


def esc_money(text):
    """Escape dollar signs so Streamlit markdown renders them literally, not as LaTeX."""
    return str(text).replace("$", "\\$")


# Hosts that indicate a fabricated / placeholder source URL (never rendered).
PLACEHOLDER_HOSTS = {
    "example.com", "example.org", "example.net", "test.com", "domain.com",
    "website.com", "yoursite.com", "placeholder.com", "url.com", "link.com",
}


def valid_source_url(url):
    """Return True only for a real-looking http(s) URL with a non-placeholder domain."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.netloc.lower().split(":")[0].replace("www.", "")
    if not host or "." not in host or host.startswith("example."):
        return False
    return host not in PLACEHOLDER_HOSTS


def link_row(maps_url, source_url=None, maps_label="📍 Maps"):
    """Render Maps (and optional Source) as links that open in a new tab.

    The source link is shown only when the URL is real (placeholder/invalid URLs
    like example.com are dropped), with its domain (e.g. "burpple.com") so the
    user knows what they're trusting before clicking.
    """
    links = [f'<a href="{maps_url}" target="_blank">{maps_label}</a>']
    if valid_source_url(source_url):
        domain = urlparse(source_url).netloc.replace("www.", "")
        links.append(f'<a href="{source_url}" target="_blank">🔗 {domain}</a>')
    st.markdown(" &nbsp;&nbsp; ".join(links), unsafe_allow_html=True)


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
    # Structured details of places recommended this session (for the summary recap).
    st.session_state.rec_details = []

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
            link_row(recommender.maps_link(p))
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
            extras = []
            if p.get("rating"):
                extras.append(f"⭐ {p['rating']}")
            if p.get("dietary"):
                extras.append(f"🟢 {p['dietary']}")
            if extras:
                st.write("  ".join(extras))
            if p.get("hours"):
                st.write(f"🕒 {p['hours']}  ·  _hours as listed — verify before going_")
            if p.get("why"):
                st.write(f"🍽️ {p['why']}")
            maps = recommender.maps_link({"name": p.get("name", ""), "area": p.get("area", "")})
            link_row(maps, p.get("source_url"), maps_label="📍 Maps · live busy times")


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


def record_recs(picks, source="web"):
    """Record recommended places: names (persisted, for memory) + details (for the summary).

    `picks` is a list of place dicts — web picks or dataset records — each with at
    least a name, plus optional area/cuisine/rating. `source` ("web" or "guide")
    is stored so the recap can explain why local-guide picks have no rating.
    """
    for p in picks:
        name = p.get("name")
        if not name:
            continue
        if not any(d["name"] == name for d in st.session_state.rec_details):
            st.session_state.rec_details.append({
                "name": name,
                "area": p.get("area", ""),
                "cuisine": p.get("cuisine", ""),
                "rating": p.get("rating", ""),
                "source": source,
            })
        if name not in st.session_state.past_recommendations:
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
    venue = st.session_state.get("venue_choice", "Any")
    if venue != "Any":
        prefs["venue_type"] = venue
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
    candidates, dropped = recommender.build_candidates(
        get_places(), prefs, st.session_state.past_recommendations
    )
    picks = candidates[:3]
    if not picks:
        return False
    # Be honest when the guide couldn't match the requested location/filters.
    if "area" in dropped and prefs.get("area"):
        intro += (f" (my local guide had nothing matching near **{prefs['area']}**, "
                  "so here are some from elsewhere — switch on Live web search for that area)")
    record_recs(picks, source="guide")
    st.session_state.messages.append({
        "role": "assistant", "content": intro,
        "cards": [{"kind": "verified", "place": p} for p in picks],
    })
    return True


def handle_turn(user_msg):
    """Process a user message: web-search for live recommendations, with a dataset fallback."""
    st.session_state.messages.append({"role": "user", "content": user_msg, "cards": []})

    prefs = current_prefs(user_msg)

    # A location is needed for useful local recommendations. If none is known, ask for it
    # once (no API call). We don't ask twice in a row, so an area our parser can't detect
    # (e.g. "Sentosa") still gets passed to the model on the user's next reply.
    prev = st.session_state.messages[-2] if len(st.session_state.messages) >= 2 else None
    asked_before = bool(prev and prev["role"] == "assistant"
                        and "which area or mrt" in prev["content"].lower())
    if not prefs.get("area") and not asked_before:
        st.session_state.messages.append(
            {"role": "assistant", "content": LOCATION_QUESTION, "cards": []}
        )
        return

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

    record_recs(result["picks"])
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
    record_recs([pick], source="guide")
    st.session_state.messages.append(
        {"role": "assistant",
         "content": f"🎲 Surprise pick — go try **{pick['name']}**! {pick['signature_dish']}, shiok one.",
         "cards": [{"kind": "verified", "place": pick}]}
    )


def _rating_value(rating):
    """Pull the leading numeric rating from a string like '4.4 (278 reviews)', or None."""
    match = re.search(r"[0-9]+(?:\.[0-9]+)?", rating or "")
    return float(match.group()) if match else None


def build_summary():
    """Build a grouped, detailed session recap from stored recommendation details."""
    details = st.session_state.rec_details
    if not details:
        return ("We haven't looked at any places yet this session — ask me for a makan spot "
                "first, then I'll recap them here! 🍜")
    prefs = st.session_state.prefs
    lines = ["**Here's your makan recap for this session** 🍜"]

    # Lead with what the user was looking for.
    wants = []
    if prefs.get("area"):
        wants.append(f"around **{prefs['area']}**")
    if prefs.get("cuisine"):
        wants.append(f"**{prefs['cuisine']}** food")
    diet = [d for d, k in (("halal", "halal"), ("vegetarian", "vegetarian_options"),
                           ("no pork", "no_pork_no_lard")) if prefs.get(k)]
    if diet:
        wants.append(" + ".join(diet))
    if wants:
        lines.append("You were looking for " + " · ".join(wants) + ".")

    # Group the places by cuisine.
    groups = {}
    for d in details:
        groups.setdefault(d["cuisine"] or "Other", []).append(d)
    for cuisine, items in groups.items():
        lines.append(f"\n**{cuisine}**")
        for d in items:
            if d.get("rating"):
                tag = f"⭐ {d['rating']}"
            elif d.get("source") == "guide":
                tag = "📒 local guide"
            else:
                tag = ""
            meta = [m for m in (d["area"], tag) if m]
            lines.append(f"- {d['name']}" + (f" — {' · '.join(meta)}" if meta else ""))

    # Highlight the top-rated place, if any have ratings.
    rated = [(d, _rating_value(d["rating"])) for d in details]
    rated = [(d, v) for d, v in rated if v is not None]
    if rated:
        top = max(rated, key=lambda t: t[1])[0]
        lines.append(f"\n⭐ **Top-rated:** {top['name']} ({top['rating']})")

    lines.append(f"\nThat's **{len(details)}** place(s) this session. Come back anytime, lah! 😊")
    return "\n".join(lines)


def do_summary():
    """Append a deterministic, grouped end-of-session recap (no API call)."""
    st.session_state.messages.append(
        {"role": "assistant", "content": build_summary(), "cards": []}
    )


def do_clear_prefs():
    """Drop chat-detected preferences (area/cuisine), keeping filter toggles and history."""
    st.session_state.prefs = {}
    current_prefs()  # rebuild from the sidebar filter widgets only
    memory_store.save_memory(st.session_state.prefs, st.session_state.past_recommendations)


def do_reset():
    """Clear saved memory and reset the session to a fresh start."""
    memory_store.clear_memory()
    for key in ("_initialised", "prefs", "past_recommendations", "messages", "rec_details"):
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
    # Mode — where recommendations come from (a mode switch, not a filter).
    st.header("Mode")
    web_on = st.toggle(
        "Live web search (latest info)", key="web_toggle", value=True,
        help="On: search the web for the latest, real places. Off: use the offline "
             "local guide only (no API cost).",
    )
    st.caption("🌐 **Live web** — latest real places from the web." if web_on
               else "📒 **Offline guide** — local dataset only, no API call.")

    st.divider()
    st.header("Filters")
    st.toggle("Halal only", key="halal_toggle")
    st.toggle("Vegetarian options", key="veg_toggle")
    st.toggle("No pork / no lard", key="nopork_toggle")
    st.selectbox("Venue", VENUE_FILTER_OPTIONS, key="venue_choice",
                 format_func=lambda v: VENUE_FILTER[v])
    st.radio(
        "Budget", BUDGET_OPTIONS, horizontal=True, key="budget_choice",
        format_func=lambda v: BUDGET_LABELS[v],
    )
    st.caption("Filters apply to your next message.")

    st.divider()
    # Active search context — the area/cuisine inferred from chat, each removable so the
    # user can correct a mis-parse or drop a stale constraint.
    st.header("Active for your next search")
    prefs = st.session_state.prefs
    active_keys = [k for k in PREF_LABELS if prefs.get(k)]
    if active_keys:
        st.caption("These shape your next recommendation — remove any that's off.")
        for key in active_keys:
            label_col, x_col = st.columns([5, 1])
            label_col.markdown(f"{PREF_LABELS[key]}: **{prefs[key]}**")
            if x_col.button("✕", key=f"rm_{key}", help=f"Remove {PREF_LABELS[key]}"):
                st.session_state.prefs.pop(key, None)
                memory_store.save_memory(
                    st.session_state.prefs, st.session_state.past_recommendations
                )
                st.rerun()
    else:
        st.caption("Tell me your area or what you're craving in the chat.")

    st.divider()
    # Past recommendations — collapsed so a long history doesn't dominate the sidebar.
    recs = st.session_state.past_recommendations
    with st.expander(f"Past recommendations ({len(recs)})", expanded=False):
        if recs:
            for name in reversed(recs):  # most recent first
                st.markdown(f"🍽️ {name}")
        else:
            st.caption("None yet.")

    st.divider()
    surprise_clicked = st.button("🎲 Surprise me", use_container_width=True)
    summary_clicked = st.button("📋 Session summary", use_container_width=True)
    clear_prefs_clicked = st.button(
        "🧽 Clear preferences", use_container_width=True,
        help="Forget the area/cuisine I picked up from chat. Keeps your filters and history.",
    )
    reset_clicked = st.button(
        "🧹 Reset memory", use_container_width=True,
        help="Wipe everything — preferences and past recommendations.",
    )

# Sidebar button actions (handled before rendering the chat).
if reset_clicked:
    do_reset()
    st.rerun()
if clear_prefs_clicked:
    do_clear_prefs()
    st.rerun()
if surprise_clicked:
    do_surprise()
if summary_clicked:
    do_summary()

# --- Chat history ---------------------------------------------------------------
for msg in st.session_state.messages:
    render_message(msg)

# --- Quick follow-up actions (only after the latest recommendation) -------------
msgs = st.session_state.messages
if msgs and msgs[-1]["role"] == "assistant" and msgs[-1].get("cards"):
    st.caption("Quick refine:")
    fu1, fu2, fu3 = st.columns(3)
    if fu1.button("🔄 More options", key="fu_more", use_container_width=True):
        handle_turn("Any other options?")
        st.rerun()
    if fu2.button("💲 Cheaper", key="fu_cheap", use_container_width=True):
        handle_turn("Something cheaper, please")
        st.rerun()
    if fu3.button("✨ Fancier", key="fu_fancy", use_container_width=True):
        handle_turn("Somewhere a bit more upscale")
        st.rerun()

# --- Chat input -----------------------------------------------------------------
user_msg = st.chat_input("What are you craving? (e.g. spicy noodles near Bugis, halal)")
if user_msg:
    handle_turn(user_msg)
    st.rerun()
