import re
import unicodedata
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