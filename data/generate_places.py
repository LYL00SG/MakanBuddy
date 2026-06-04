"""Generate a large offline fallback dataset of Singapore food places.

Anchors on a curated list of REAL Singapore venues (hawker centres, malls/food
courts, and food streets — each with an accurate area, nearest MRT, and region)
and produces representative eateries per venue using realistic cuisine/dish
archetypes with sensible dietary flags. The hand-curated `places_curated.json`
(real, individually named places) is kept as a frozen base and merged in first.

Run:  python data/generate_places.py
Output: data/places.json  (curated entries first, then generated, de-duplicated)

Note: generated entries describe representative stalls/eateries at real venues
(e.g. "Hainanese Chicken Rice — Maxwell Food Centre"); the venue and its location
are real, the individual stall is representative. This is the offline fallback
only — the app's primary path is live web search.
"""

import json
import os
import random

random.seed(42)

HERE = os.path.dirname(__file__)
CURATED_PATH = os.path.join(HERE, "places_curated.json")
OUT_PATH = os.path.join(HERE, "places.json")

# --- Real venues: (name, kind, area, mrt, region) -------------------------------
# kind: "hawker" | "mall" | "street". area/mrt/region are real.
VENUES = [
    # ---------------- CENTRAL: hawker centres ----------------
    ("Maxwell Food Centre", "hawker", "Chinatown", "Maxwell / Tanjong Pagar", "Central"),
    ("Chinatown Complex Food Centre", "hawker", "Chinatown", "Chinatown", "Central"),
    ("People's Park Food Centre", "hawker", "Chinatown", "Chinatown", "Central"),
    ("People's Park Complex Food Centre", "hawker", "Chinatown", "Chinatown", "Central"),
    ("Hong Lim Market & Food Centre", "hawker", "Chinatown", "Chinatown / Telok Ayer", "Central"),
    ("Amoy Street Food Centre", "hawker", "Telok Ayer", "Telok Ayer / Tanjong Pagar", "Central"),
    ("Lau Pa Sat (Telok Ayer Market)", "hawker", "Raffles Place", "Telok Ayer / Raffles Place", "Central"),
    ("Tanjong Pagar Plaza Market & Food Centre", "hawker", "Tanjong Pagar", "Tanjong Pagar", "Central"),
    ("Tekka Centre", "hawker", "Little India", "Little India / Jalan Besar", "Central"),
    ("Tiong Bahru Market", "hawker", "Tiong Bahru", "Tiong Bahru", "Central"),
    ("Newton Food Centre", "hawker", "Newton", "Newton", "Central"),
    ("Adam Road Food Centre", "hawker", "Bukit Timah", "Botanic Gardens", "Central"),
    ("Whampoa Makan Place", "hawker", "Whampoa", "Boon Keng", "Central"),
    ("Pek Kio Market & Food Centre", "hawker", "Farrer Park", "Farrer Park", "Central"),
    ("Berseh Food Centre", "hawker", "Jalan Besar", "Jalan Besar / Lavender", "Central"),
    ("Golden Mile Food Centre", "hawker", "Beach Road", "Nicoll Highway / Lavender", "Central"),
    ("Beo Crescent Market", "hawker", "Tiong Bahru", "Havelock / Tiong Bahru", "Central"),
    ("Albert Centre Market & Food Centre", "hawker", "Bugis", "Bugis / Rochor", "Central"),
    ("North Bridge Road Market & Food Centre", "hawker", "Bugis", "Bugis / Lavender", "Central"),
    ("Maxwell-adjacent Kreta Ayer (Smith Street)", "hawker", "Chinatown", "Chinatown", "Central"),
    # ---------------- CENTRAL: malls ----------------
    ("ION Orchard", "mall", "Orchard", "Orchard", "Central"),
    ("Ngee Ann City (Takashimaya)", "mall", "Orchard", "Orchard", "Central"),
    ("Paragon", "mall", "Orchard", "Orchard", "Central"),
    ("Wisma Atria", "mall", "Orchard", "Orchard", "Central"),
    ("Orchard Central", "mall", "Somerset", "Somerset", "Central"),
    ("313@Somerset", "mall", "Somerset", "Somerset", "Central"),
    ("Plaza Singapura", "mall", "Dhoby Ghaut", "Dhoby Ghaut", "Central"),
    ("Bugis Junction", "mall", "Bugis", "Bugis", "Central"),
    ("Bugis+", "mall", "Bugis", "Bugis", "Central"),
    ("Suntec City", "mall", "Marina Centre", "Esplanade / Promenade", "Central"),
    ("Marina Bay Sands (The Shoppes)", "mall", "Marina Bay", "Bayfront", "Central"),
    ("Raffles City", "mall", "City Hall", "City Hall / Esplanade", "Central"),
    ("Funan", "mall", "City Hall", "City Hall", "Central"),
    ("Marina Square", "mall", "Marina Centre", "Esplanade / City Hall", "Central"),
    ("Great World", "mall", "Great World", "Great World", "Central"),
    ("Clarke Quay Central", "mall", "Clarke Quay", "Clarke Quay", "Central"),
    ("City Square Mall", "mall", "Farrer Park", "Farrer Park", "Central"),
    ("United Square", "mall", "Novena", "Novena", "Central"),
    ("Velocity@Novena Square", "mall", "Novena", "Novena", "Central"),
    # ---------------- CENTRAL: food streets ----------------
    ("Club Street & Ann Siang", "street", "Chinatown", "Telok Ayer / Maxwell", "Central"),
    ("Amoy Street & Telok Ayer Street", "street", "Telok Ayer", "Telok Ayer", "Central"),
    ("Smith Street (Chinatown Food Street)", "street", "Chinatown", "Chinatown", "Central"),
    ("Haji Lane & Arab Street", "street", "Kampong Glam", "Bugis", "Central"),
    ("Bussorah Street (Kampong Glam)", "street", "Kampong Glam", "Bugis", "Central"),
    ("Serangoon Road (Little India)", "street", "Little India", "Little India", "Central"),
    ("Tiong Bahru Estate", "street", "Tiong Bahru", "Tiong Bahru", "Central"),
    ("Robertson Quay", "street", "Robertson Quay", "Fort Canning / Clarke Quay", "Central"),
    ("Boat Quay", "street", "Boat Quay", "Raffles Place / Clarke Quay", "Central"),
    ("Dempsey Hill", "street", "Dempsey", "Napier / Botanic Gardens", "Central"),
    ("Tanjong Pagar (Korean enclave)", "street", "Tanjong Pagar", "Tanjong Pagar", "Central"),
    ("Balestier Road", "street", "Balestier", "Boon Keng / Novena", "Central"),

    # ---------------- EAST: hawker centres ----------------
    ("Old Airport Road Food Centre", "hawker", "Old Airport Road", "Dakota / Mountbatten", "East"),
    ("Geylang Serai Market", "hawker", "Geylang Serai", "Paya Lebar / Eunos", "East"),
    ("Haig Road Market & Food Centre", "hawker", "Haig Road", "Dakota / Paya Lebar", "East"),
    ("Dunman Food Centre", "hawker", "Dunman", "Dakota", "East"),
    ("Marine Parade Central Market & Food Centre", "hawker", "Marine Parade", "Marine Parade", "East"),
    ("Marine Terrace (Block 50A) Market", "hawker", "Marine Parade", "Marine Parade", "East"),
    ("Bedok 85 Fengshan Market", "hawker", "Bedok", "Bedok / Kembangan", "East"),
    ("Bedok Interchange Hawker Centre", "hawker", "Bedok", "Bedok", "East"),
    ("Bedok South (Block 16) Market", "hawker", "Bedok", "Bedok", "East"),
    ("Kaki Bukit 511 Market & Food Centre", "hawker", "Kaki Bukit", "Ubi / Kaki Bukit", "East"),
    ("Eunos Crescent Market & Food Centre", "hawker", "Eunos", "Eunos", "East"),
    ("Tampines Round Market & Food Centre", "hawker", "Tampines", "Tampines", "East"),
    ("Our Tampines Hub Hawker Centre", "hawker", "Tampines", "Tampines", "East"),
    ("Tampines Street 11 (Block 137) Market", "hawker", "Tampines", "Tampines", "East"),
    ("Pasir Ris Central Hawker Centre", "hawker", "Pasir Ris", "Pasir Ris", "East"),
    ("Changi Village Hawker Centre", "hawker", "Changi Village", "Tampines (then bus)", "East"),
    ("East Coast Lagoon Food Village", "hawker", "East Coast Park", "Bedok (then bus)", "East"),
    ("Simei (Block 248) Market", "hawker", "Simei", "Simei", "East"),
    # ---------------- EAST: malls ----------------
    ("Parkway Parade", "mall", "Marine Parade", "Marine Parade", "East"),
    ("i12 Katong", "mall", "Katong", "Marine Parade", "East"),
    ("Tampines Mall", "mall", "Tampines", "Tampines", "East"),
    ("Tampines One", "mall", "Tampines", "Tampines", "East"),
    ("Century Square", "mall", "Tampines", "Tampines", "East"),
    ("Bedok Mall", "mall", "Bedok", "Bedok", "East"),
    ("White Sands", "mall", "Pasir Ris", "Pasir Ris", "East"),
    ("Eastpoint Mall", "mall", "Simei", "Simei", "East"),
    ("Changi City Point", "mall", "Expo", "Expo", "East"),
    ("Jewel Changi Airport", "mall", "Changi Airport", "Changi Airport", "East"),
    ("Paya Lebar Quarter (PLQ)", "mall", "Paya Lebar", "Paya Lebar", "East"),
    ("KINEX", "mall", "Paya Lebar", "Paya Lebar", "East"),
    # ---------------- EAST: food streets ----------------
    ("East Coast Road & Katong", "street", "Katong", "Marine Parade", "East"),
    ("Joo Chiat Road", "street", "Joo Chiat", "Paya Lebar / Eunos", "East"),
    ("Geylang Lorongs", "street", "Geylang", "Aljunied / Kallang", "East"),
    ("Siglap Village", "street", "Siglap", "Bedok / Marine Parade", "East"),
    ("Frankel Avenue", "street", "Frankel", "Kembangan", "East"),

    # ---------------- WEST: hawker centres ----------------
    ("ABC Brickworks Food Centre", "hawker", "Bukit Merah", "Redhill / Tiong Bahru", "West"),
    ("Alexandra Village Food Centre", "hawker", "Alexandra", "Redhill / Labrador Park", "West"),
    ("Bukit Merah View Market & Food Centre", "hawker", "Bukit Merah", "Redhill", "West"),
    ("Redhill Food Centre", "hawker", "Redhill", "Redhill", "West"),
    ("Mei Ling Market & Food Centre", "hawker", "Queenstown", "Queenstown", "West"),
    ("Margaret Drive Hawker Centre", "hawker", "Queenstown", "Queenstown / Commonwealth", "West"),
    ("Commonwealth Crescent Market", "hawker", "Commonwealth", "Commonwealth", "West"),
    ("Tanglin Halt Market", "hawker", "Tanglin Halt", "Commonwealth", "West"),
    ("Ghim Moh Market & Food Centre", "hawker", "Ghim Moh", "Buona Vista / Holland Village", "West"),
    ("Holland Drive Market & Food Centre", "hawker", "Holland Village", "Buona Vista / Holland Village", "West"),
    ("Holland Village Market & Food Centre", "hawker", "Holland Village", "Holland Village", "West"),
    ("Clementi 448 Market & Food Centre", "hawker", "Clementi", "Clementi", "West"),
    ("Clementi Avenue 2 (Block 352) Market", "hawker", "Clementi", "Clementi", "West"),
    ("West Coast Market Square", "hawker", "West Coast", "Clementi / Jurong East", "West"),
    ("Taman Jurong Market & Food Centre", "hawker", "Jurong", "Lakeside (then bus)", "West"),
    ("Boon Lay Place Food Village", "hawker", "Boon Lay", "Boon Lay", "West"),
    ("Jurong West 505 Market & Food Centre", "hawker", "Jurong West", "Boon Lay / Pioneer", "West"),
    ("Yuhua Market & Hawker Centre", "hawker", "Jurong East", "Chinese Garden / Jurong East", "West"),
    ("Bukit Batok West Market & Food Centre", "hawker", "Bukit Batok", "Bukit Gombak", "West"),
    ("Bukit Batok Central (Block 630) Market", "hawker", "Bukit Batok", "Bukit Batok", "West"),
    ("Teban Gardens Market & Food Centre", "hawker", "Teban Gardens", "Jurong East", "West"),
    # ---------------- WEST: malls ----------------
    ("VivoCity", "mall", "HarbourFront", "HarbourFront", "West"),
    ("Jurong Point", "mall", "Boon Lay", "Boon Lay", "West"),
    ("JEM", "mall", "Jurong East", "Jurong East", "West"),
    ("Westgate", "mall", "Jurong East", "Jurong East", "West"),
    ("IMM", "mall", "Jurong East", "Jurong East", "West"),
    ("The Star Vista", "mall", "Buona Vista", "Buona Vista", "West"),
    ("Clementi Mall", "mall", "Clementi", "Clementi", "West"),
    ("West Mall", "mall", "Bukit Batok", "Bukit Batok", "West"),
    ("Lot One Shoppers' Mall", "mall", "Choa Chu Kang", "Choa Chu Kang", "West"),
    ("HillV2", "mall", "Hillview", "Hillview", "West"),
    ("Bukit Panjang Plaza", "mall", "Bukit Panjang", "Bukit Panjang", "West"),
    # ---------------- WEST: food streets ----------------
    ("Holland Village", "street", "Holland Village", "Holland Village", "West"),
    ("The Rail Mall", "street", "Hillview", "Hillview", "West"),
    ("Cheong Chin Nam Road (Beauty World)", "street", "Bukit Timah", "Beauty World", "West"),

    # ---------------- NORTH: hawker centres ----------------
    ("Chong Pang Market & Food Centre", "hawker", "Yishun", "Yishun / Sembawang", "North"),
    ("Yishun Park Hawker Centre", "hawker", "Yishun", "Yishun / Khatib", "North"),
    ("Yishun Block 925 Market", "hawker", "Yishun", "Yishun", "North"),
    ("Yishun Block 105 Market", "hawker", "Yishun", "Yishun", "North"),
    ("Kampung Admiralty Hawker Centre", "hawker", "Admiralty", "Admiralty", "North"),
    ("Marsiling Mall Hawker Centre", "hawker", "Woodlands", "Marsiling", "North"),
    ("888 Plaza Food Centre", "hawker", "Woodlands", "Woodlands South / Marsiling", "North"),
    ("Sembawang Hills Food Centre", "hawker", "Sembawang Hills", "Lentor / Ang Mo Kio", "North"),
    # ---------------- NORTH: malls ----------------
    ("Causeway Point", "mall", "Woodlands", "Woodlands", "North"),
    ("Northpoint City", "mall", "Yishun", "Yishun", "North"),
    ("Sun Plaza", "mall", "Sembawang", "Sembawang", "North"),
    ("Canberra Plaza", "mall", "Canberra", "Canberra", "North"),
    ("Woods Square", "mall", "Woodlands", "Woodlands", "North"),
    # ---------------- NORTH: food streets ----------------
    ("Upper Thomson Road", "street", "Upper Thomson", "Upper Thomson / Marymount", "North"),
    ("Sembawang Road (Sembawang Hills)", "street", "Sembawang Hills", "Lentor", "North"),

    # ---------------- NORTH-EAST: hawker centres ----------------
    ("Chomp Chomp Food Centre", "hawker", "Serangoon Gardens", "Serangoon (then bus)", "North-East"),
    ("Serangoon Garden Market (Hainanese Village)", "hawker", "Serangoon Gardens", "Serangoon (then bus)", "North-East"),
    ("Kovan 209 Market & Food Centre", "hawker", "Kovan", "Kovan", "North-East"),
    ("Ci Yuan Hawker Centre", "hawker", "Hougang", "Buangkok", "North-East"),
    ("Hougang Block 21 Market", "hawker", "Hougang", "Hougang", "North-East"),
    ("Hougang Block 681 Market", "hawker", "Hougang", "Hougang / Kovan", "North-East"),
    ("Ang Mo Kio 628 Market & Food Centre", "hawker", "Ang Mo Kio", "Ang Mo Kio (then bus)", "North-East"),
    ("Ang Mo Kio 724 Market & Food Centre", "hawker", "Ang Mo Kio", "Ang Mo Kio", "North-East"),
    ("Ang Mo Kio 453 Market", "hawker", "Ang Mo Kio", "Ang Mo Kio", "North-East"),
    ("Mayflower Market & Food Centre", "hawker", "Ang Mo Kio", "Mayflower", "North-East"),
    ("Toa Payoh Lorong 1 Market", "hawker", "Toa Payoh", "Braddell / Toa Payoh", "North-East"),
    ("Toa Payoh Lorong 4 Market", "hawker", "Toa Payoh", "Toa Payoh", "North-East"),
    ("Toa Payoh Lorong 5 Market", "hawker", "Toa Payoh", "Toa Payoh", "North-East"),
    ("Toa Payoh Lorong 8 Market & Food Centre", "hawker", "Toa Payoh", "Braddell / Toa Payoh", "North-East"),
    ("Toa Payoh West Market & Food Centre", "hawker", "Toa Payoh", "Toa Payoh", "North-East"),
    ("Anchorvale Village Hawker Centre", "hawker", "Sengkang", "Sengkang / Cheng Lim", "North-East"),
    ("Kampung Kampong Senang (Sengkang)", "hawker", "Sengkang", "Sengkang", "North-East"),
    ("Oasis Terraces Hawker (Punggol)", "hawker", "Punggol", "Punggol (then bus)", "North-East"),
    # ---------------- NORTH-EAST: malls ----------------
    ("NEX", "mall", "Serangoon", "Serangoon", "North-East"),
    ("AMK Hub", "mall", "Ang Mo Kio", "Ang Mo Kio", "North-East"),
    ("Junction 8", "mall", "Bishan", "Bishan", "North-East"),
    ("Compass One", "mall", "Sengkang", "Sengkang", "North-East"),
    ("Waterway Point", "mall", "Punggol", "Punggol", "North-East"),
    ("Hougang Mall", "mall", "Hougang", "Hougang", "North-East"),
    ("Heartland Mall Kovan", "mall", "Kovan", "Kovan", "North-East"),
    ("The Seletar Mall", "mall", "Sengkang", "Fernvale", "North-East"),
    ("myVillage at Serangoon Gardens", "mall", "Serangoon Gardens", "Serangoon (then bus)", "North-East"),
    ("Toa Payoh HDB Hub", "mall", "Toa Payoh", "Toa Payoh", "North-East"),
    # ---------------- NORTH-EAST: food streets ----------------
    ("Serangoon Gardens Circus", "street", "Serangoon Gardens", "Serangoon (then bus)", "North-East"),
    ("Upper Serangoon Road (Kovan)", "street", "Kovan", "Kovan", "North-East"),
]

# --- Archetype pools: (label, cuisine, dish, halal, veg, no_pork, price) ---------
HAWKER = [
    ("Hainanese Chicken Rice", "Chinese", "Hainanese chicken rice", False, False, True, "$"),
    ("Char Kway Teow", "Chinese", "Char kway teow", False, False, False, "$"),
    ("Fried Hokkien Mee", "Chinese", "Hokkien prawn mee", False, False, False, "$"),
    ("Bak Chor Mee", "Chinese", "Minced pork noodles", False, False, False, "$"),
    ("Wanton Mee", "Chinese", "Wanton noodles", False, False, False, "$"),
    ("Fishball Noodles", "Chinese", "Teochew fishball noodles", False, False, True, "$"),
    ("Lor Mee", "Chinese", "Lor mee", False, False, False, "$"),
    ("Prawn Noodles", "Chinese", "Prawn mee soup", False, False, False, "$"),
    ("Sliced Fish Soup", "Chinese", "Sliced fish bee hoon soup", False, False, True, "$"),
    ("Duck Rice", "Chinese", "Braised duck rice", False, False, False, "$"),
    ("Roasted Meats", "Chinese", "Char siew & roast pork rice", False, False, False, "$"),
    ("Economy Rice (Cai Png)", "Chinese", "Mixed vegetable rice", False, True, False, "$"),
    ("Claypot Rice", "Chinese", "Claypot rice", False, False, False, "$"),
    ("Carrot Cake", "Chinese", "Fried carrot cake", False, True, False, "$"),
    ("Yong Tau Foo", "Chinese", "Yong tau foo", False, True, True, "$"),
    ("Ban Mian", "Chinese", "Ban mian", False, False, False, "$"),
    ("Laksa", "Peranakan", "Laksa", False, False, True, "$"),
    ("Hokkien Satay Bee Hoon", "Chinese", "Satay bee hoon", False, False, False, "$"),
    ("Popiah", "Chinese", "Popiah", False, True, True, "$"),
    ("Nasi Lemak", "Malay", "Nasi lemak", True, False, True, "$"),
    ("Mee Rebus", "Malay", "Mee rebus", True, False, True, "$"),
    ("Mee Soto", "Malay", "Mee soto", True, False, True, "$"),
    ("Lontong", "Malay", "Lontong", True, True, True, "$"),
    ("Nasi Padang", "Malay", "Nasi padang", True, True, True, "$"),
    ("Satay", "Malay", "Chicken & mutton satay", True, False, True, "$"),
    ("Roti Prata", "Indian", "Roti prata", False, True, True, "$"),
    ("Briyani", "Indian", "Chicken briyani", True, False, True, "$"),
    ("Thosai", "Indian", "Masala thosai", False, True, True, "$"),
    ("Indian Rojak", "Indian", "Indian rojak", True, True, True, "$"),
    ("Vegetarian Bee Hoon", "Chinese", "Vegetarian bee hoon", False, True, True, "$"),
    ("Western Hawker", "Western", "Chicken chop & fries", False, False, True, "$"),
    ("Chendol & Ice Kachang", "Dessert", "Chendol", False, True, True, "$"),
    ("Soya Beancurd & Tau Huay", "Dessert", "Tau huay", False, True, True, "$"),
    ("Kaya Toast & Kopi", "Chinese", "Kaya toast set", False, True, True, "$"),
]

FOOD_COURT = [
    ("Japanese Donburi Stall", "Japanese", "Chicken katsu don", False, False, True, "$"),
    ("Korean Stall", "Korean", "Bibimbap", False, False, True, "$"),
    ("Western Grill Stall", "Western", "Grilled chicken & fries", False, False, True, "$"),
    ("Thai Stall", "Thai", "Green curry rice", False, False, True, "$"),
    ("Vietnamese Stall", "Vietnamese", "Beef pho", False, False, True, "$"),
    ("Cooked Food (Zi Char) Stall", "Chinese", "Sweet & sour pork rice", False, False, False, "$"),
    ("Hong Kong Roast Stall", "Chinese", "Roast duck rice", False, False, False, "$"),
    ("Muslim Food Stall", "Malay", "Ayam penyet", True, False, True, "$"),
    ("Indian Cuisine Stall", "Indian", "Briyani set", True, True, True, "$"),
    ("Yong Tau Foo Stall", "Chinese", "Yong tau foo", False, True, True, "$"),
    ("Mixed Vegetable Rice Stall", "Chinese", "Economy rice", False, True, False, "$"),
    ("Taiwanese Stall", "Taiwanese", "Braised pork rice", False, False, False, "$"),
    ("Dim Sum Stall", "Chinese", "Assorted dim sum", False, True, False, "$"),
    ("Local Delights Stall", "Singaporean", "Laksa & lor mee", False, False, True, "$"),
]

CAFE = [
    ("Brunch Cafe", "Western", "All-day big breakfast", False, True, False, "$$"),
    ("Specialty Coffee Bar", "Western", "Flat white & pastries", False, True, True, "$$"),
    ("Artisan Bakery Cafe", "Western", "Sourdough & croissants", False, True, True, "$$"),
    ("Dessert Cafe", "Dessert", "Cakes & soft serve", False, True, True, "$$"),
    ("Matcha Cafe", "Japanese", "Matcha latte & dessert", False, True, True, "$$"),
    ("Bubble Tea Shop", "Taiwanese", "Brown sugar bubble tea", False, True, True, "$"),
    ("Toast & Kopi Cafe", "Singaporean", "Kaya toast set", False, True, True, "$"),
]

RESTAURANT = [
    ("Cantonese Dim Sum Restaurant", "Chinese", "Dim sum & roast meats", False, True, False, "$$"),
    ("Sichuan Restaurant", "Chinese", "Mala xiang guo", False, False, False, "$$"),
    ("Steamboat & Hotpot Restaurant", "Chinese", "Mala hotpot", False, True, False, "$$"),
    ("Zi Char Seafood Restaurant", "Chinese", "Chilli crab & cereal prawn", False, False, False, "$$$"),
    ("Japanese Sushi Restaurant", "Japanese", "Sushi & sashimi platter", False, False, True, "$$"),
    ("Japanese Ramen Bar", "Japanese", "Tonkotsu ramen", False, False, False, "$$"),
    ("Korean BBQ Restaurant", "Korean", "Samgyeopsal BBQ", False, False, False, "$$"),
    ("Korean Fried Chicken", "Korean", "Yangnyeom fried chicken", False, False, True, "$$"),
    ("Thai Restaurant", "Thai", "Tom yum & pad thai", False, True, False, "$$"),
    ("Vietnamese Restaurant", "Vietnamese", "Pho & banh mi", False, False, True, "$$"),
    ("North Indian Restaurant", "Indian", "Butter chicken & naan", False, True, True, "$$"),
    ("Italian Trattoria", "Western", "Wood-fired pizza & pasta", False, True, False, "$$"),
    ("Western Steakhouse", "Western", "Ribeye steak", False, False, False, "$$$"),
    ("Peranakan Restaurant", "Peranakan", "Ayam buah keluak", False, True, False, "$$"),
    ("Halal Local Restaurant", "Malay", "Nasi padang & rendang", True, True, True, "$$"),
    ("Mookata BBQ", "Thai", "Mookata steamboat BBQ", False, False, False, "$$"),
    ("Vegetarian Restaurant", "Chinese", "Mock-meat vegetarian set", False, True, True, "$$"),
    ("Seafood Restaurant", "Chinese", "Black pepper crab", False, False, False, "$$$"),
]


def make_entry(venue, arche, vtype, name):
    """Build one place record from a venue and an archetype tuple."""
    name_label, cuisine, dish, halal, veg, no_pork, price = arche
    vname, _kind, area, mrt, region = venue
    return {
        "name": name,
        "type": vtype,
        "cuisine": cuisine,
        "region": region,
        "area": f"{vname}, {area}",
        "mrt": mrt,
        "signature_dish": dish,
        "price": price,
        "halal": halal,
        "vegetarian_options": veg,
        "no_pork_no_lard": no_pork,
        "notes": f"{vname} ({area})",
    }


def generate():
    """Generate representative eateries across all venues."""
    out = []
    for venue in VENUES:
        _vname, kind, _area, _mrt, _region = venue
        if kind == "hawker":
            picks = random.sample(HAWKER, random.randint(7, 9))
            for a in picks:
                name = f"{a[0]} — {venue[0]}"
                out.append(make_entry(venue, a, "hawker", name))
        elif kind == "mall":
            for a in random.sample(FOOD_COURT, random.randint(3, 4)):
                name = f"{a[0]} @ {venue[0]} Food Court"
                out.append(make_entry(venue, a, "food_court", name))
            for a in random.sample(RESTAURANT, random.randint(3, 5)):
                name = f"{a[0]} ({venue[0]})"
                out.append(make_entry(venue, a, "restaurant", name))
            for a in random.sample(CAFE, random.randint(2, 3)):
                name = f"{a[0]} ({venue[0]})"
                out.append(make_entry(venue, a, "cafe", name))
        else:  # street
            for a in random.sample(RESTAURANT, random.randint(4, 6)):
                name = f"{a[0]} ({venue[0]})"
                out.append(make_entry(venue, a, "restaurant", name))
            for a in random.sample(CAFE, random.randint(2, 3)):
                name = f"{a[0]} ({venue[0]})"
                out.append(make_entry(venue, a, "cafe", name))
    return out


def main():
    """Merge frozen curated entries with generated ones and write places.json."""
    with open(CURATED_PATH, "r", encoding="utf-8") as f:
        curated = json.load(f)

    merged, seen = [], set()
    for entry in curated + generate():
        key = entry["name"].lower()
        if key not in seen:
            seen.add(key)
            merged.append(entry)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(merged)} places ({len(curated)} curated + "
          f"{len(merged) - len(curated)} generated) to {OUT_PATH}")


if __name__ == "__main__":
    main()
