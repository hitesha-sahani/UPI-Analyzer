

import json
import re
import os
import pandas as pd
from pathlib import Path
from modules.user_overrides import get_override

# ── Load category config ───────────────────────────────────────────────────────
_CONFIG_PATH = Path(__file__).parent.parent / "config" / "categories.json"

def _load_categories() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

CATEGORIES = _load_categories()


# ── Keyword → Category reverse index ──────────────────────────────────────────
def _build_keyword_index(categories: dict) -> list:
    """Returns sorted list of (keyword, category) tuples, longest first."""
    index = []
    for cat, data in categories.items():
        for kw in data.get("keywords", []):
            index.append((kw.lower(), cat))
    # Sort by keyword length descending so "big basket" beats "basket"
    return sorted(index, key=lambda x: len(x[0]), reverse=True)

_KW_INDEX = _build_keyword_index(CATEGORIES)


def _clean_description(desc: str) -> str:
    """Remove noise from transaction description for better matching."""
    desc = str(desc).lower().strip()
    # Remove common transaction noise
    noise_patterns = [
        r"upi[/-]?\w*",
        r"ref\s*no[\s:]*\w+",
        r"txn\s*id[\s:]*\w+",
        r"order\s*#?\s*\w+",
        r"\b\d{6,}\b",        # Long numeric IDs
        r"payment\s+to",
        r"payment\s+from",
        r"transfer\s+to",
        r"transfer\s+from",
        r"@\w+",              # UPI handles like @okicici
    ]
    for pat in noise_patterns:
        desc = re.sub(pat, " ", desc, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", desc).strip()


 
 
def _categorize_single(description: str, upi_id: str = "", user_id: str | None = None) -> str:
    """
    Priority:
      1. user override keyed on upi_id  (e.g. "rahul@okaxis")
      2. user override keyed on cleaned description
      3. global keyword index
      4. "Others"
    """
    if user_id:
        # Try upi_id first — it's the most specific identifier
        uid_raw = str(upi_id).strip()
        uid = uid_raw.split("@", 1)[1].strip().lower() if "@" in uid_raw else ""
        if uid:
            override = get_override(user_id, uid)
            if override:
                return override
 
        # Fall back to description-based override
        override = get_override(user_id, description.strip().lower())
        if override:
            return override
 
    # Global keyword index — unchanged
    clean_desc  = _clean_description(description)
    search_text = clean_desc + " " + str(upi_id).lower()
 
    for keyword, category in _KW_INDEX:
        if keyword in search_text:
            return category
 
    return "Others"
 
 
# ── REPLACE categorize_transactions ─────────────────────────────────────────
 
def categorize_transactions(df, user_id: str | None = None):
    """
    user_id=None keeps full backward-compatibility.
    """
    df = df.copy()
 
    df["category"] = df.apply(
        lambda row: "Income" if row["type"] == "Credit" else _categorize_single(
            row["description"],
            row.get("upi_id", ""),
            user_id,
        ),
        axis=1,
    )
 
    df["merchant"] = df["description"].apply(_extract_merchant)
 
    return df

def _extract_merchant(description: str) -> str:
    """
    Best-effort merchant name extraction from raw description.
    Returns a cleaned, title-cased merchant name.
    """
    desc = str(description).strip()

    # Known brand patterns — return canonical name
    brand_map = {
    # ── Food & Dining ──────────────────────────────────────────────────────────
    "zomato":           "Zomato",
    "swiggy":           "Swiggy",
    "dominos":          "Domino's",
    "domino":           "Domino's",
    "kfc":              "KFC",
    "mcdonalds":        "McDonald's",
    "mcdonald":         "McDonald's",
    "subway":           "Subway",
    "starbucks":        "Starbucks",
    "pizza hut":        "Pizza Hut",
    "burger king":      "Burger King",
    "chaayos":          "Chaayos",
    "barbeque nation":  "Barbeque Nation",
    "bikanervala":      "Bikanervala",
    "haldirams":        "Haldiram's",
    "haldiram":         "Haldiram's",
    "wow momo":         "Wow! Momo",
    "behrouz":          "Behrouz Biryani",
    "faasos":           "Faasos",
    "box8":             "Box8",
    "freshmenu":        "FreshMenu",
    "eatfit":           "EatFit",
    "theobroma":        "Theobroma",
    "monginis":         "Monginis",
    "inner chef":       "Inner Chef",
    "rebel foods":      "Rebel Foods",
    "the good bowl":    "The Good Bowl",

    # ── Groceries ─────────────────────────────────────────────────────────────
    "bigbasket":        "BigBasket",
    "big basket":       "BigBasket",
    "zepto":            "Zepto",
    "blinkit":          "Blinkit",
    "grofers":          "Blinkit",
    "dmart":            "DMart",
    "d mart":           "DMart",
    "jiomart":          "JioMart",
    "reliance fresh":   "Reliance Fresh",
    "spencer":          "Spencer's",
    "nilgiris":         "Nilgiris",
    "lulu":             "LuLu Hypermarket",
    "heritage foods":   "Heritage Foods",
    "more supermarket": "More Supermarket",
    "nature basket":    "Nature's Basket",
    "swiggy instamart": "Swiggy Instamart",
    "country delight":  "Country Delight",
    "milkbasket":       "Milkbasket",
    "amazon fresh":     "Amazon Fresh",
    "star bazaar":      "Star Bazaar",
    "big bazaar":       "Big Bazaar",
    "hypercity":        "HyperCity",
    "supr daily":       "Supr Daily",
    "mother dairy":     "Mother Dairy",
    "amul":             "Amul",

    # ── Transport ─────────────────────────────────────────────────────────────
    "uber":             "Uber",
    "ola":              "Ola",
    "rapido":           "Rapido",
    "irctc":            "IRCTC",
    "indigo":           "IndiGo",
    "spicejet":         "SpiceJet",
    "air india":        "Air India",
    "vistara":          "Vistara",
    "akasa":            "Akasa Air",
    "go first":         "Go First",
    "air asia":         "AirAsia",
    "hpcl":             "HPCL",
    "bpcl":             "BPCL",
    "iocl":             "Indian Oil",
    "indian oil":       "Indian Oil",
    "bharat petroleum": "BPCL",
    "hp petrol":        "HPCL",
    "shell":            "Shell",
    "redbus":           "redBus",
    "makemytrip":       "MakeMyTrip",
    "goibibo":          "Goibibo",
    "yatra":            "Yatra",
    "cleartrip":        "Cleartrip",
    "fastag":           "FASTag",
    "namma yatri":      "Namma Yatri",
    "yulu":             "Yulu",
    "bounce":           "Bounce",
    "zoomcar":          "Zoomcar",
    "revv":             "Revv",
    "porter":           "Porter",
    "lalamove":         "Lalamove",
    "wefast":           "WeFast",

    # ── Shopping ──────────────────────────────────────────────────────────────
    "amazon":           "Amazon",
    "flipkart":         "Flipkart",
    "myntra":           "Myntra",
    "ajio":             "AJIO",
    "meesho":           "Meesho",
    "nykaa":            "Nykaa",
    "purplle":          "Purplle",
    "snapdeal":         "Snapdeal",
    "tata cliq":        "Tata CLiQ",
    "shopsy":           "Shopsy",
    "croma":            "Croma",
    "vijay sales":      "Vijay Sales",
    "decathlon":        "Decathlon",
    "pantaloons":       "Pantaloons",
    "westside":         "Westside",
    "max fashion":      "Max Fashion",
    "lifestyle":        "Lifestyle",
    "ikea":             "IKEA",
    "pepperfry":        "Pepperfry",
    "urban ladder":     "Urban Ladder",
    "firstcry":         "FirstCry",
    "lenskart":         "Lenskart",
    "reliance digital": "Reliance Digital",
    "poorvika":         "Poorvika",
    "sangeetha":        "Sangeetha Mobiles",
    "tanishq":          "Tanishq",
    "kalyan":           "Kalyan Jewellers",
    "malabar":          "Malabar Gold",
    "bata":             "Bata",
    "liberty":          "Liberty Shoes",
    "metro shoes":      "Metro Shoes",
    "mochi":            "Mochi",
    "woodland":         "Woodland",
    "nike":             "Nike",
    "adidas":           "Adidas",
    "puma":             "Puma",
    "reebok":           "Reebok",
    "fabindia":         "FabIndia",
    "biba":             "Biba",
    "w store":          "W",
    "aurelia":          "Aurelia",
    "ferns":            "Ferns N Petals",
    "igp":              "IGP",
    "winni":            "Winni",
    "sugar cosmetics":  "SUGAR Cosmetics",
    "mamaearth":        "Mamaearth",
    "plum":             "Plum",
    "mcaffeine":        "mCaffeine",
    "wow skin":         "WOW Skin Science",
    "forest essentials": "Forest Essentials",
    "kama ayurveda":    "Kama Ayurveda",
    "boat":             "boAt",
    "noise":            "Noise",

    # ── Subscriptions ─────────────────────────────────────────────────────────
    "netflix":          "Netflix",
    "spotify":          "Spotify",
    "youtube premium":  "YouTube Premium",
    "amazon prime":     "Amazon Prime",
    "hotstar":          "Disney+ Hotstar",
    "disney":           "Disney+ Hotstar",
    "zee5":             "ZEE5",
    "sonyliv":          "SonyLIV",
    "sony liv":         "SonyLIV",
    "apple music":      "Apple Music",
    "icloud":           "iCloud",
    "google one":       "Google One",
    "microsoft 365":    "Microsoft 365",
    "adobe":            "Adobe",
    "gaana":            "Gaana",
    "jiocinema":        "JioCinema",
    "mxplayer":         "MX Player",
    "voot":             "Voot",
    "alt balaji":       "ALTBalaji",
    "hungama":          "Hungama",
    "eros now":         "Eros Now",
    "discovery plus":   "Discovery+",
    "linkedin":         "LinkedIn",
    "canva":            "Canva",
    "grammarly":        "Grammarly",
    "duolingo":         "Duolingo",
    "headspace":        "Headspace",
    "calm":             "Calm",
    "notion":           "Notion",
    "dropbox":          "Dropbox",
    "zoom":             "Zoom",
    "slack":            "Slack",

    # ── Entertainment ─────────────────────────────────────────────────────────
    "bookmyshow":       "BookMyShow",
    "pvr":              "PVR Cinemas",
    "inox":             "INOX",
    "cinepolis":        "Cinepolis",
    "wonderla":         "Wonderla",
    "imagica":          "Imagica",
    "steam":            "Steam",
    "playstation":      "PlayStation",
    "xbox":             "Xbox",

    # ── Bills & Utilities ─────────────────────────────────────────────────────
    "airtel":           "Airtel",
    "jio":              "Jio",
    "vodafone":         "Vi (Vodafone Idea)",
    "vi ":              "Vi (Vodafone Idea)",
    "bsnl":             "BSNL",
    "idea":             "Vi (Vodafone Idea)",
    "bescom":           "BESCOM",
    "msedcl":           "MSEDCL",
    "tpddl":            "TPDDL",
    "cesc":             "CESC",
    "tata power":       "Tata Power",
    "bses":             "BSES",
    "mahanagar gas":    "Mahanagar Gas",
    "indraprastha gas": "IGL",
    "gujarat gas":      "Gujarat Gas",
    "act fibernet":     "ACT Fibernet",
    "hathway":          "Hathway",
    "jio fiber":        "JioFiber",
    "tata play":        "Tata Play",
    "dish tv":          "Dish TV",
    "sun direct":       "Sun Direct",
    "d2h":              "D2H",
    "hp gas":           "HP Gas",
    "bharat gas":       "Bharat Gas",
    "indane":           "Indane Gas",

    # ── Finance & Investment ───────────────────────────────────────────────────
    "zerodha":          "Zerodha",
    "groww":            "Groww",
    "upstox":           "Upstox",
    "paytm money":      "Paytm Money",
    "et money":         "ET Money",
    "kuvera":           "Kuvera",
    "smallcase":        "Smallcase",
    "angel broking":    "Angel One",
    "angel one":        "Angel One",
    "5paisa":           "5paisa",
    "sharekhan":        "Sharekhan",
    "motilal oswal":    "Motilal Oswal",
    "edelweiss":        "Edelweiss",
    "lic":              "LIC",
    "bajaj allianz":    "Bajaj Allianz",
    "max life":         "Max Life Insurance",
    "tata aia":         "Tata AIA",
    "wazirx":           "WazirX",
    "coindcx":          "CoinDCX",

    # ── Health & Medical ──────────────────────────────────────────────────────
    "apollo":           "Apollo",
    "medplus":          "MedPlus",
    "1mg":              "1mg",
    "netmeds":          "Netmeds",
    "practo":           "Practo",
    "healthkart":       "HealthKart",
    "thyrocare":        "Thyrocare",
    "dr lal":           "Dr. Lal PathLabs",
    "metropolis":       "Metropolis",
    "fortis":           "Fortis Hospital",
    "max hospital":     "Max Hospital",
    "manipal":          "Manipal Hospital",
    "cult":             "Cult.fit",
    "cultsport":        "Cult.fit",
    "anytime fitness":  "Anytime Fitness",
    "gold gym":         "Gold's Gym",
    "talwalkars":       "Talwalkars",
    "urban company":    "Urban Company",

    # ── Education ─────────────────────────────────────────────────────────────
    "udemy":            "Udemy",
    "coursera":         "Coursera",
    "unacademy":        "Unacademy",
    "byju":             "BYJU'S",
    "byjus":            "BYJU'S",
    "vedantu":          "Vedantu",
    "upgrad":           "upGrad",
    "skillshare":       "Skillshare",
    "edx":              "edX",
    "toppr":            "Toppr",
    "cuemath":          "Cuemath",
    "whitehat":         "WhiteHat Jr",
    "british council":  "British Council",

    # ── Travel & Stays ────────────────────────────────────────────────────────
    "oyo":              "OYO",
    "treebo":           "Treebo",
    "fabhotel":         "FabHotel",
    "airbnb":           "Airbnb",
    "zostel":           "Zostel",
    "taj hotel":        "Taj Hotels",
    "marriott":         "Marriott",
    "ibis":             "Ibis",
    "lemon tree":       "Lemon Tree",
    "thomas cook":      "Thomas Cook",

    # ── Personal Care ─────────────────────────────────────────────────────────
    "uclean":           "UClean",
    "cleanly":          "Cleanly",
    "urban company spa": "Urban Company",

    # ── BNPL & Credit ─────────────────────────────────────────────────────────
    "simpl":            "Simpl",
    "lazypay":          "LazyPay",
    "slice":            "Slice",
    "postpe":           "PostPe",
    "zestmoney":        "ZestMoney",
    "kreditbee":        "KreditBee",
    "bajaj finserv":    "Bajaj Finserv",
    "home credit":      "Home Credit",
    "early salary":     "EarlySalary",
    "moneyview":        "MoneyView",
    "nira":             "Nira Finance",
    "onecard":          "OneCard",
    "fi money":         "Fi Money",
    "jupiter":          "Jupiter",

    # ── P2P & Wallets ─────────────────────────────────────────────────────────
    "phonepe":          "PhonePe",
    "paytm":            "Paytm",
    "gpay":             "Google Pay",
    "google pay":       "Google Pay",
    "bhim":             "BHIM",
    "splitwise":        "Splitwise",

    # ── Charity ───────────────────────────────────────────────────────────────
    "giveindia":        "GiveIndia",
    "milaap":           "Milaap",
    "ketto":            "Ketto",
    "impact guru":      "ImpactGuru",
    "akshaya patra":    "Akshaya Patra",

    # ── Additional brands (auto-generated from categories.json) ───────────────

    # Food & Dining
    "behrouz biryani":      "Behrouz Biryani",
    "hunger box":           "HungerBox",
    "eat club":             "Eat Club",
    "scootsy":              "Scootsy",
    "dunzo food":           "Dunzo",
    "magic pin food":       "MagicPin",
    "ovenfresh":            "Ovenfresh",
    "britannia":            "Britannia",
    "parle":                "Parle",
    "le marche":            "Le Marche",

    # Groceries
    "spencer":              "Spencer's",
    "lulu hypermarket":     "LuLu Hypermarket",
    "daily basket":         "Daily Basket",
    "raw pressery":         "Raw Pressery",
    "bb daily":             "BB Daily",
    "creamline dairy":      "Creamline Dairy",
    "go organic":           "Go Organic",
    "24 mantra":            "24 Mantra Organic",
    "godrej nature":        "Godrej Nature's Basket",
    "easyday":              "Easyday",
    "spar":                 "SPAR",
    "metro cash":           "Metro Cash & Carry",

    # Transport
    "akasa air":            "Akasa Air",
    "bmtc":                 "BMTC",
    "dtc":                  "DTC",
    "best bus":             "BEST Bus",
    "ola electric":         "Ola Electric",
    "vogo":                 "Vogo",
    "drivezy":              "Drivezy",
    "blowhorn":             "Blowhorn",
    "dunzo delivery":       "Dunzo",

    # Shopping
    "h&m":                  "H&M",
    "zara":                 "Zara",
    "hopscotch":            "Hopscotch",
    "lot mobiles":          "Lot Mobiles",
    "univercell":           "Univercell",
    "waman hari pethe":     "Waman Hari Pethe",
    "pc jewellers":         "PC Jewellers",
    "under armour":         "Under Armour",
    "hush puppies":         "Hush Puppies",
    "good earth":           "Good Earth",
    "global desi":          "Global Desi",
    "soch":                 "Soch",
    "libas":                "Libas",
    "bakingo":              "Bakingo",

    # Subscriptions
    "manorama online":      "Manorama Online",
    "sun nxt":              "Sun NXT",
    "aha video":            "Aha",
    "figma":                "Figma",
    "fitpass":              "Fitpass",
    "times prime":          "Times Prime",
    "mxplayer pro":         "MX Player Pro",

    # Entertainment
    "carnival cinemas":     "Carnival Cinemas",
    "miraj cinemas":        "Miraj Cinemas",

    # Bills & Utilities
    "adani electricity":    "Adani Electricity",
    "uppcl":                "UPPCL",
    "bwssb":                "BWSSB",
    "excitel":              "Excitel",
    "you broadband":        "YOU Broadband",
    "tikona":               "Tikona",
    "indane gas":           "Indane Gas",

    # Housing & Rent
    "nobroker":             "NoBroker",
    "magicbricks":          "MagicBricks",
    "housing.com":          "Housing.com",
    "99acres":              "99acres",
    "commonfloor":          "CommonFloor",
    "nestaway":             "Nestaway",
    "stanza living":        "Stanza Living",
    "colive":               "Colive",
    "zolo":                 "Zolo",

    # Finance & Investment
    "coin by zerodha":      "Coin by Zerodha",
    "hdfc securities":      "HDFC Securities",
    "icici direct":         "ICICI Direct",
    "kotak securities":     "Kotak Securities",
    "nuvama":               "Nuvama",
    "nippon india":         "Nippon India MF",
    "mirae asset":          "Mirae Asset",
    "axis mutual fund":     "Axis Mutual Fund",
    "sbi mutual fund":      "SBI Mutual Fund",
    "hdfc mutual fund":     "HDFC Mutual Fund",
    "icici prudential":     "ICICI Prudential",
    "max life insurance":   "Max Life Insurance",
    "birla sun life":       "Aditya Birla Sun Life",
    "reliance nippon":      "Nippon India MF",
    "aditya birla":         "Aditya Birla",
    "taxmann":              "Taxmann",

    # BNPL & Credit
    "bajaj finserv emi":    "Bajaj Finserv",
    "stashfin":             "StashFin",
    "cashe":                "CASHe",
    "freopay":              "FreoPay",
    "fi money card":        "Fi Money",
    "jupiter card":         "Jupiter",
    "rbl credit card":      "RBL Bank",
    "indusind credit card": "IndusInd Bank",
    "yes bank credit card": "YES Bank",

    # Health & Medical
    "dr lal pathlabs":      "Dr. Lal PathLabs",
    "aiims":                "AIIMS",
    "nimhans":              "NIMHANS",
    "snap fitness":         "Snap Fitness",

    # Education
    "nptel":                "NPTEL",
    "ielts":                "IELTS",
    "toefl":                "TOEFL",
    "gre":                  "GRE",
    "gmat":                 "GMAT",
    "sat":                  "SAT",
    "cambridge":            "Cambridge",
    "alliance francaise":   "Alliance Française",
    "embibe":               "Embibe",
    "meritnation":          "Meritnation",
    "extramarks":           "Extramarks",
    "whitehat jr":          "WhiteHat Jr",
    "campk12":              "Camp K12",

    # Travel & Stays
    "agoda":                "Agoda",
    "trivago":              "Trivago",
    "holiday inn":          "Holiday Inn",
    "taj hotels":           "Taj Hotels",
    "oberoi":               "Oberoi Hotels",
    "ibis hotel":           "Ibis",
    "hostelworld":          "Hostelworld",
    "cox and kings":        "Cox & Kings",

    # Personal Care
    "dhobizone":            "DhobiZone",
    "laundrywala":          "Laundrywala",

    # Home & Maintenance
    "sulekha":              "Sulekha",
    "housejoy":             "Housejoy",

    # Charity & Donations
    "cry india":            "CRY India",
    "unicef":               "UNICEF",
    "red cross":            "Red Cross",
    "help age":             "HelpAge India",
    "smile foundation":     "Smile Foundation",
    "iskon":                "ISKCON",
    "tirupati":             "Tirupati Temple",
    "shirdi":               "Shirdi Sai Baba",
    "vaishno devi":         "Vaishno Devi Shrine",
    "amarnath":             "Amarnath Shrine",
    "golden temple":        "Golden Temple",
    "haji ali":             "Haji Ali Dargah",
    "ajmer sharif":         "Ajmer Sharif Dargah",
    }
    desc_lower = desc.lower()
    for key, canonical in brand_map.items():
        if key in desc_lower:
            return canonical

    # Generic: take first meaningful word(s), remove IDs and noise
    cleaned = re.sub(r"[#\-_]?\d{4,}", "", desc)   # Remove long numbers
    cleaned = re.sub(r"@\w+", "", cleaned)           # Remove UPI handles
    cleaned = re.sub(r"\b(upi|ref|txn|order|payment|transfer|debit|credit)\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    parts = cleaned.split()
    if parts:
        return " ".join(parts[:3]).title()

    return desc[:30].title()

def get_category_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a summary DataFrame with spend per category.
    Only includes Debit transactions.
    """
    debits = df[df["type"] == "Debit"].copy()

    summary = (
        debits.groupby("category")
        .agg(
            total_spent=("amount", "sum"),
            transaction_count=("amount", "count"),
            avg_transaction=("amount", "mean"),
            max_transaction=("amount", "max"),
        )
        .reset_index()
        .sort_values("total_spent", ascending=False)
    )

    total = summary["total_spent"].sum()
    summary["percentage"] = (summary["total_spent"] / total * 100).round(1)

    # Attach color and icon from config
    summary["color"] = summary["category"].apply(
        lambda c: CATEGORIES.get(c, {}).get("color", "#B2BEC3")
    )
    summary["icon"] = summary["category"].apply(
        lambda c: CATEGORIES.get(c, {}).get("icon", "📦")
    )

    return summary


def get_top_merchants(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Returns top N merchants by total spend."""
    debits = df[df["type"] == "Debit"].copy()
    return (
        debits.groupby("merchant")
        .agg(total_spent=("amount", "sum"), visits=("amount", "count"))
        .reset_index()
        .sort_values("total_spent", ascending=False)
        .head(n)
    )
