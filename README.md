# 🍜 Makan Buddy — Singapore Food Recommendation Chatbot

## 1. Project Title and Description

**Makan Buddy** is a conversational AI chatbot that recommends where to eat in Singapore —
hawker centres, food courts, cafes, and restaurants across many cuisines. It asks about your
craving, your location (area/MRT), and any dietary needs, then uses **live web search** to suggest
real, up-to-date places (including recently opened spots), remembers what it has recommended, and
shows each pick as a card with a Maps link and a source. It is for anyone in Singapore who is
hungry and can't decide where to makan.

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
- **Data:** a curated local `data/places.json` of ~100 real Singapore food places, used as an
  offline fallback when web search is unavailable

## 4. Setup Instructions

1. **Clone the repository.**
   ```bash
   git clone <your-repo-url>
   cd Capstone
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

**Example 1 — vague request, the bot asks one question at a time**
```
You:  I'm hungry but can't decide
Bot:  No worries lah! Which area or MRT are you near?
You:  Bugis, and I need halal
Bot:  Steady! Here are some halal options around there (from a live web search):
      [🌐 Zam Zam Restaurant] — Bugis · Indian-Muslim · famous murtabak   📍 Maps · 🔗 Source
      [🌐 Islamic Restaurant]  — Bugis · Indian-Muslim · classic biryani   📍 Maps · 🔗 Source
```

**Example 2 — specific craving, recently opened spots**
```
You:  any new cafes that opened recently near Tiong Bahru?
Bot:  Wah, Tiong Bahru always got new spots! Here are a couple of fresh finds:
      [🌐 <cafe name>] — Tiong Bahru · Cafe · opened 2024, known for ...   📍 Maps · 🔗 Source
      [🌐 <cafe name>] — Tiong Bahru · Bakery cafe · sourdough & sandos    📍 Maps · 🔗 Source
```

Every recommendation is a live web result shown as a 🌐 card with a Maps link and a source you can
verify. You can also click **🎲 Surprise me** for a random pick from the local guide, toggle
dietary/budget filters or **Live web search** in the sidebar, and click **📋 Session summary** for
a recap of everything recommended.

## 6. Known Limitations

- **Web results are not guaranteed accurate.** Recommendations come from a live web search, so a
  place may occasionally be outdated (e.g. since closed), mis-categorised, or missing details.
  Each card includes a source link so you can verify.
- **Requires connectivity and API credit.** Every recommendation makes an OpenAI web-search call,
  so it needs internet and uses your API quota. If search is unavailable, the bot falls back to the
  offline local guide (~100 curated places), which is smaller and not live-updated.
- **Preference detection is keyword-based.** Location, cuisine, and dietary needs are parsed with
  simple keywords, so unusual phrasing may be missed (the sidebar toggles let you set them manually).

## 7. Future Improvements

- Add real-time opening hours and live crowd/queue estimates per place.
- Expand the dataset and let users contribute their own favourite stalls, with a richer
  map-based view of recommendations.

---

### Project structure
```
app.py            # Streamlit UI: chat loop, cards, sidebar, surprise, summary
chatbot.py        # SYSTEM_PROMPT, OpenAI client, web search + structured recommendations
recommender.py    # Offline fallback dataset: load / filter, surprise pick, Maps links
memory_store.py   # Persist preferences + past recommendations across runs
data/places.json  # Curated ~100-place dataset (offline fallback)
.env.example      # Template for your OPENAI_API_KEY
requirements.txt  # Python dependencies
```
