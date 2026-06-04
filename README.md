# 🍜 Makan Buddy — Singapore Food Recommendation Chatbot

## 1. Project Title and Description

**Makan Buddy** is a conversational AI chatbot that recommends where to eat in Singapore —
hawker centres, food courts, cafes, and restaurants across many cuisines. It asks about your
craving, your location (area/MRT), and any dietary needs, then suggests specific places, remembers
what it has recommended, and can even search the web for newer or trending spots. It is for anyone
in Singapore who is hungry and can't decide where to makan.

## 2. Problem Statement

Deciding where to eat in Singapore is surprisingly hard: there are thousands of hawker stalls,
food courts, cafes, and restaurants, and the "best" choice depends on where you are, what you're
craving, and your dietary needs (halal, vegetarian, no pork). Makan Buddy narrows it down through a
natural conversation, grounding its picks in a curated dataset of real places so the suggestions
are concrete and trustworthy, while still being able to surface newer openings via live search.

## 3. Technology Stack

- **Language:** Python 3.10+
- **AI API:** OpenAI (`gpt-4o-mini`) via the **openai** Python SDK (Responses API), with the
  built-in web-search tool for newer places
- **UI:** Streamlit (chat interface with sidebar filters and rich cards)
- **Config:** python-dotenv (loads the API key from a `.env` file)
- **Data:** a curated local `data/places.json` of ~100 real Singapore food places

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
Bot:  Steady! Here are a couple of halal options around there:
      [✅ Zam Zam Restaurant] — murtabak and biryani near Sultan Mosque
      ...
```

**Example 2 — specific craving with dietary + budget filter**
```
You:  cheap vegetarian indian food near Little India
Bot:  Sedap choice! Try these:
      [✅ Komala Vilas] — pure-veg thali and masala dosa
      [✅ Ananda Bhavan] — halal-certified veg South Indian
      [✅ Gokul Vegetarian] — mock-meat North Indian
```

**Example 3 — newer places via web search**
```
You:  any new cafes that opened recently near Tiong Bahru?
Bot:  Let me check what's new... here's a fresh find:
      [✨ Newer find] <name> — with a source link from the web
```

You can also click **🎲 Surprise me** for a random pick, toggle dietary/budget filters in the
sidebar, and click **📋 Session summary** for a recap of everything recommended.

## 6. Known Limitations

- **Curated coverage is finite.** The local dataset has ~100 well-known places. For very specific
  or obscure requests the bot relaxes filters or falls back to web search, which can be less precise
  than the curated entries.
- **Web-sourced ("Newer find") results are not verified.** They come from a live web search and
  may occasionally be outdated (e.g. a place that has since closed) or lack full details. Always
  check the source link.
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
chatbot.py        # SYSTEM_PROMPT, OpenAI client, response + web search, summary
recommender.py    # Load / filter / format dataset, surprise pick, Maps links
memory_store.py   # Persist preferences + past recommendations across runs
data/places.json  # Curated dataset of ~100 Singapore food places
.env.example      # Template for your OPENAI_API_KEY
requirements.txt  # Python dependencies
```
