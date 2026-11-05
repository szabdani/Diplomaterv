import difflib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Optional

# Regex to filter out youth, reserve, and women's teams from club search results
YOUTH_OR_RESERVE_PATTERN = re.compile(
    r"\b(u\d{2}|under\s*\d{2}|primavera|weitere|youth|reserves?|reserve|juv\.|uefa|women|fem\.|femenino|amateur\w*)\b|"
    r"(?: (atletico|b|c|ii|iii)$)",
    re.IGNORECASE,
)

# Common slug expansions for Transfermarkt search compatibility
SLUG_QUERY_OVERRIDES = {
    # Spain
    "atletico madrid": "atletico de madrid",
    "las palmas": "ud las palmas",
    "sevilla": "sevilla fc",
    "celta vigo": "celta de vigo",
    "athletic club": "athletic bilbao",
    "espanyol": "rcd espanyol",
    "alaves": "deportivo alaves",
    "deportivo": "deportivo la coruna",

    # Italy
    "napoli": "ssc napoli",
    "roma": "as roma",
    "lazio": "ss lazio",
    "sampdoria": "uc sampdoria",
    "fiorentina": "acf fiorentina",
    "sassuolo": "us sassuolo",
    "crotone": "fc crotone",
    "spal": "s.p.a.l",

    # Germany
    "hamburg": "hamburger sv",
    "monchengladbach": "borussia monchengladbach",
    "schalke 04": "fc schalke 04",
    "mainz": "1.fsv mainz 05",
    "koln": "1 fc koln",

    # France
    "psg": "paris saint-germain",
    "monaco": "as monaco",
    "marseille": "olympique marseille",
    "lyon": "olympique lyon",
    "toulouse": "fc toulouse",
    "rennes": "stade rennais",
    "st etienne": "as saint-etienne",
    "saint etienne": "as saint-etienne",
    "bordeaux": "girondins bordeaux",
    "angers": "angers sco",
}

# Common player name aliases for Transfermarkt search compatibility
KNOWN_ALIASES = {
    "chicharito": "javier hernandez",
    "zanka": "mathias jorgensen",
    "cote": "jose angel valdes",
    "pedro rocha": "pedro",
    "gabigol": "gabriel barbosa",
    "kepa": "kepa arrizabalaga",
    "adrian": "adrian san miguel",
    "jese": "jese rodriguez",
    "raul": "raul gonzalez",
    "michu": "miguel perez cuesta",
    "morata": "alvaro morata",
    "vitolo": "victor machin perez",
    "ibai": "ibai gomez",
    "rober pier": "roberto suarez pier",
}

# =====================================================================
# Text Normalization & Decoding
# =====================================================================

def decode_unicode_escapes(text: Any) -> str:
    """
    Decodes literal unicode escape sequences
    """
    if not text:
        return ""
    return re.sub(
        r"\\u([0-9a-fA-F]{4})",
        lambda m: chr(int(m.group(1), 16)),
        str(text)
    )

def normalize_text(text: str) -> str:
    """
    Strips accents and lowercases text for reliable token comparison.
    """
    if not text:
        return ""
    decoded = decode_unicode_escapes(text)
    decomposed = unicodedata.normalize("NFKD", decoded)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9\s]", " ", stripped.lower()).strip()

def get_dob_variants(dob: Any) -> list[str]:
    """
    Generates standard 'YYYY-MM-DD' and transposed 'YYYY-DD-MM' variants
    to accommodate day/month inversions between upstream data sources.
    """
    if not dob:
        return []
    s = str(dob).strip()
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if not match:
        return [s]

    year, m_str, d_str = match.groups()
    primary = f"{year}-{m_str}-{d_str}"
    variants = [primary]

    m_val, d_val = int(m_str), int(d_str)
    # If the day is a valid month (1-12) and month is a valid day (1-31), add transposed variant
    if 1 <= d_val <= 12 and 1 <= m_val <= 31 and m_val != d_val:
        variants.append(f"{year}-{d_val:02d}-{m_val:02d}")

    return variants

# =====================================================================
# Club Search Candidate Scoring
# =====================================================================

def score_club_candidate(
    candidate: dict[str, Any],
    raw_query: str,
    expected_countries: Optional[list[str]] = None,
) -> int:
    """
    Scores a Transfermarkt club search result to prevent mismatches.
    Returns -1 if the candidate is invalid.
    """
    club_name = candidate.get("name", "")
    country = candidate.get("country", "")

    # Reject if country does not match the league's allowed countries
    if expected_countries and country:
        if country.lower() not in [c.lower() for c in expected_countries]:
            return -1

    norm_club = normalize_text(club_name)
    norm_query = normalize_text(raw_query)

    # Reject youth and reserve teams
    if YOUTH_OR_RESERVE_PATTERN.search(norm_club):
        return -1

    club_tokens = set(norm_club.split())
    query_tokens = [t for t in norm_query.split() if len(t) > 1]

    score = 0

    # High reward for exact whole-word token matches in club name
    matched_tokens = sum(1 for qt in query_tokens if qt in club_tokens)
    score += matched_tokens * 50

    # Bonus if the club name starts with or equals the query
    if norm_club == norm_query:
        score += 100
    elif norm_club.startswith(norm_query):
        score += 40
    elif norm_query in norm_club:
        score += 20

    # Penalize if zero query tokens matched as whole words
    if query_tokens and matched_tokens == 0:
        return -1

    return score

# =====================================================================
# Wyscout Player Matching
# =====================================================================

def load_wyscout_index(wyscout_file: Path) -> dict[str, Any]:
    """
    Builds in-memory lookup sets from Wyscout's players.json:
    - exact_names: normalized full and short names
    - by_dob: dictionary mapping 'YYYY-MM-DD' -> list of name token sets
    - all_tokens: list of player name token sets for containment fallback
    """
    if not wyscout_file.exists():
        print(f"[WARNING] Wyscout players file not found at: {wyscout_file}")
        return {"exact_names": set(), "by_dob": {}, "all_tokens": []}

    with open(wyscout_file, "r", encoding="utf-8") as f:
        wy_players = json.load(f)

    exact_names: set[str] = set()
    by_dob: dict[str, list[set[str]]] = {}
    all_tokens: list[set[str]] = []

    for p in wy_players:
        wy_id = p.get("wyId")
        first = p.get("firstName", "")
        last = p.get("lastName", "")
        short = p.get("shortName", "")
        dob = p.get("birthDate")  # Format: "YYYY-MM-DD"

        full_norm = normalize_text(f"{first} {last}")
        short_norm = normalize_text(short)

        # Retain tokens with length >= 3 to avoid noise
        tokens = set(t for t in f"{full_norm} {short_norm}".split() if len(t) >= 3)

        # Package tokens and normalized names into a record dict
        record = {
            "wyscout_id": wy_id,
            "short_name": decode_unicode_escapes(short),
            "full_name": decode_unicode_escapes(f"{first} {last}".strip()),
            "birth_date": dob,
            "tokens": tokens,
            "full_norm": full_norm,
            "short_norm": short_norm,
        }
        
        if full_norm and full_norm not in exact_names:
            exact_names[full_norm] = record
        if short_norm and short_norm not in exact_names:
            exact_names[short_norm] = record

        if tokens:
            all_tokens.append(tokens)

        # Index primary and transposed DOB variants
        for dob_var in get_dob_variants(dob):
            by_dob.setdefault(dob_var, []).append(record)

    print(f"[OK] Indexed {len(wy_players)} Wyscout players from {wyscout_file.name}")
    return {
        "exact_names": exact_names,
        "by_dob": by_dob,
        "all_tokens": all_tokens,
    }

# Use later in data-processor
def is_player_in_wyscout(tm_player: dict[str, Any], wy_index: dict[str, Any]) -> bool:
    """
    Checks if a TM squad player exists in the Wyscout reference index:
    1. Exact string match on full or short name.
    2. Exact 'YYYY-MM-DD' match + at least one common name/surname token.
    3. Token subset overlap for compound names.
    """
    tm_name = normalize_text(tm_player.get("name", ""))
    if not tm_name:
        return False

    # Apply alias expansion if present
    expanded_alias = KNOWN_ALIASES.get(tm_name, "")
    names_to_check = [tm_name]
    if expanded_alias:
        names_to_check.append(expanded_alias)

    # 1. Exact match
    for name in names_to_check:
        if name in wy_index["exact_names"]:
            return True

    tm_tokens = set()
    for name in names_to_check:
        tm_tokens.update(t for t in name.split() if len(t) >= 3)
   
    if not tm_tokens:
        return False

    tm_collapsed = tm_name.replace(" ", "")

    # 2. Flexible Date of Birth match
    tm_dob = tm_player.get("dateOfBirth")
    for dob_variant in get_dob_variants(tm_dob):
        if dob_variant in wy_index["by_dob"]:
            for entry in wy_index["by_dob"][dob_variant]:
                wy_toks = entry["tokens"]

                # Direct token intersection
                if tm_tokens & wy_toks:
                    return True

                # Spacing collapse & fuzzy similarity
                wy_full = entry["full_norm"]
                wy_short = entry["short_norm"]

                # Collapse spaces
                if tm_collapsed and (tm_collapsed in wy_full.replace(" ", "") or wy_full.replace(" ", "") in tm_collapsed):
                    return True

                # Fuzzy string similarity when DOB aligns
                for candidate in (wy_full, wy_short):
                    if not candidate:
                        continue
                    ratio = difflib.SequenceMatcher(None, tm_name, candidate).ratio()
                    if ratio >= 0.65:
                        return True
                    if expanded_alias:
                        alias_ratio = difflib.SequenceMatcher(None, expanded_alias, candidate).ratio()
                        if alias_ratio >= 0.65:
                            return True
            

    # 3. DOB-independent name token matching
    # Matches if:
    # - Two or more significant tokens match (e.g., 'nemanja' + 'matic')
    # - One distinct long token (>= 6 chars, e.g., 'ibrahimovic') matches and is a subset
    for wy_toks in wy_index["all_tokens"]:
        intersection = tm_tokens & wy_toks
        if len(intersection) >= 2:
            return True
        if len(intersection) == 1 and any(len(t) >= 6 for t in intersection):
            if tm_tokens.issubset(wy_toks) or wy_toks.issubset(tm_tokens):
                return True

    return False

# =====================================================================
# Profile Building
# =====================================================================
def build_profile_from_squad_summary(player_summary: dict[str, Any]) -> dict[str, Any]:
    """
    Synthesizes the player profile object directly from the club squad response.
    """
    return {
        "id": str(player_summary.get("id", "")),
        "name": player_summary.get("name"),
        "dateOfBirth": player_summary.get("dateOfBirth"),
        "age": player_summary.get("age"),
        "height": player_summary.get("height"),
        "foot": player_summary.get("foot"),
        "position": {"main": player_summary.get("position")},
        "citizenship": player_summary.get("nationality", []),
        "currentClub": {
            "joined": player_summary.get("joinedOn"),
            "contractExpires": player_summary.get("contract"),
        },
        "marketValue": player_summary.get("marketValue"),
        "status": player_summary.get("status"),
    }