# 🍜 Makan Buddy — Singapore Food Recommendation Chatbot

## 1. Project Title and Description

**Makan Buddy** is a conversational AI chatbot that recommends where to eat in Singapore —
hawker centres, food courts, cafes, restaurants, and street-food spots across many cuisines. It asks about your
craving, your location (area/MRT), and any dietary needs, then uses **live web search** to suggest
real, up-to-date places (including recently opened spots), remembers what it has recommended, and
shows each pick as a structured card — specific address, cuisine, price, review rating, a one-line
reason, and Maps + source links. It is for anyone in Singapore who is hungry and can't decide where
to makan.

## 2. Problem Statement

Deciding where to eat in Singapore is surprisingly hard: there are thousands of hawker stalls,
food courts, cafes, and restaurants, the scene changes constantly (places open and close), and the
"best" choice depends on where you are, what you're craving, and your dietary needs (halal,
vegetarian, no pork). Makan Buddy narrows it down through a natural conversation backed by live web
search, so the suggestions are current and come with sources — with a curated local dataset as an
offline fallback if search is unavailable.

## 3. Technology Stack

- **Language:** Python 3.10+
- **AI API:** OpenAI (`gpt-4o-mini`) via the **openai** Python SDK (Responses API), using the
  built-in **web-search tool** plus **structured (JSON-schema) outputs** for the recommendation cards
- **UI:** Streamlit (chat interface with sidebar filters and rich cards)
- **Config:** python-dotenv (loads the API key from a `.env` file)
- **Data:** a hand-curated local `data/places.json` of ~340 real, well-known Singapore food
  places, used as an offline fallback when web search is unavailable

## 4. Setup Instructions

1. **Clone the repository.**
   ```bash
   git clone https://github.com/LYL00SG/MakanBuddy.git
   cd MakanBuddy
   ```
2. **Install dependencies.**
   ```bash
   pip install -r requirements.txt
   ```
3. **Add your API key.** Copy the example env file and paste in your OpenAI key
   (create one at <https://platform.openai.com/api-keys>):
   ```bash
   cp .env.example .env      # on Windows: copy .env.example .env
   ```
   Then edit `.env` and set `OPENAI_API_KEY=...`.
4. **Run the application.**
   ```bash
   streamlit run app.py
   ```
   If the `streamlit` command isn't on your PATH, use `python -m streamlit run app.py`.
   The app opens in your browser at <http://localhost:8501>.

## 5. Usage Examples

The reply is always a short one-line intro; the recommendations themselves are 3+ structured
🌐 cards (at least 3 when enough suitable options exist), each with name, specific address,
cuisine·type·price, ⭐ rating, 🟢 dietary confirmation, 🕒 opening hours, a one-line "why", and
Maps + Source links that open in a new tab. The Maps link goes to the place's Google Maps page,
where you can see live "Popular times" / busyness. After each set of results, **quick-refine
buttons** (🔄 More options · 💲 Cheaper · ✨ Fancier) let you iterate without typing.

**Example 1 — specific craving at a mall**
```
You:  japanese food at nex mall
Bot:  Craving Japanese food at NEX Mall? Here are some options you might enjoy:

      ┌ TORI-Q  🌐 Live web result ──────────────────────────────┐
      │ Restaurant · Japanese · NEX Mall, 23 Serangoon Central · MRT: Serangoon · ~$10
      │ ⭐ 4.3 (932 reviews)   🟢 No pork
      │ 🕒 11am–10pm daily — hours as listed, verify before going
      │ 🍽️ Authentic yakitori with a special 'tare' sauce.
      │ 📍 Maps · live busy times   🔗 sethlui.com
      └──────────────────────────────────────────────────────────┘
      (plus 2 more cards: Pepper Lunch NEX, &JOY Japanese Food Street NEX)
```

**Example 2 — vague request, the bot asks one question at a time**
```
You:  I'm hungry but can't decide
Bot:  No worries lah! Which area or MRT are you near?
You:  Bugis, and I need halal
Bot:  Craving halal food near Bugis? Here are some good ones:
      (3 🌐 cards of real halal spots near Bugis, each with a specific address, rating, and source)
```

The sidebar lets you switch the **Mode** (Live web search vs offline guide), set **Filters**
(halal / vegetarian / no-pork, venue type, budget), see and **remove** the area/cuisine the bot
inferred from your chat ("Active for your next search"), and review past recommendations. You can also click **🎲 Surprise me** for a random pick from the local
guide, **📋 Session summary** for a recap grouped by cuisine (with each place's area, rating, and
a top-rated highlight), **🧽 Clear preferences** to forget the detected
area/cuisine, or **🧹 Reset memory** to wipe everything.

## 6. Known Limitations

- **Web results are not guaranteed accurate.** Recommendations come from a live web search, so a
  place may occasionally be outdated (e.g. since closed), mis-categorised, or missing details.
  Each card includes a source link so you can verify. The 🕒 opening hours are "as listed" by the
  source and may be stale — verify before heading down.
- **Requires connectivity and API credit.** Every recommendation makes an OpenAI web-search call,
  so it needs internet and uses your API quota. If search is unavailable, the bot falls back to the
  offline local guide (~340 hand-curated real places), which is smaller and not live-updated.
- **Preference detection is keyword-based.** Location, cuisine, and dietary needs are parsed with
  simple keywords, so unusual phrasing may be missed (the sidebar toggles let you set them manually).

## 7. Future Improvements

- Integrate the Google Places API for accurate verified opening hours, a true "Open now" flag, and
  a **real photo** of each place (live crowd/busyness isn't in any official API — the Maps link is
  used for both photos and busyness today, since those are real on Google Maps).
- Expand the dataset and let users contribute their own favourite stalls, with a richer
  map-based view of recommendations.

---

### Project structure
```
app.py            # Streamlit UI: chat loop, cards, sidebar, surprise, summary
chatbot.py        # SYSTEM_PROMPT, OpenAI client, web search + structured recommendations
recommender.py    # Offline fallback dataset: load / filter, surprise pick, Maps links
memory_store.py   # Persist preferences + past recommendations across runs
data/places.json  # Hand-curated ~340-place real dataset (offline fallback)
.env.example      # Template for your OPENAI_API_KEY
requirements.txt  # Python dependencies
```
