import difflib
import json
import re
import unicodedata
from pathlib import Path
from pathlib import Path
from typing import Any, Optional

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

# =====================================================================
# Wyscout Player Matching
# =====================================================================

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
            "full_name": decode_unicode_escapes(f"{first} {last}".strip()),
            "short_name": decode_unicode_escapes(short),
            "birth_date": dob,
            "tokens": tokens,
            "full_norm": full_norm,
            "short_norm": short_norm,
        }
        
        if full_norm and full_norm not in exact_names:
            exact_names.add(full_norm)
        if short_norm and short_norm not in exact_names:
            exact_names.add(short_norm)

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


def match_player_to_wyscout(
    tm_player: dict[str, Any], wy_index: dict[str, Any]
) -> Optional[dict[str, Any]]:
    """
    Attempts to link a Transfermarkt player to a Wyscout player record.
    Returns match metadata (wyscout_id, short_name, match_method, confidence)
    for downstream use in the data-processor, or None if no match is found.
    """
    tm_name = normalize_text(tm_player.get("name", ""))
    if not tm_name:
        return None

    expanded_alias = KNOWN_ALIASES.get(tm_name, "")
    names_to_check = [tm_name]
    if expanded_alias:
        names_to_check.append(expanded_alias)

    # 1. Exact Name Match
    for name in names_to_check:
        if name in wy_index.get("exact_names", {}):
            rec = wy_index["exact_names"][name]
            return {
                "wyscout_id": rec["wyscout_id"],
                "wyscout_name": rec["short_name"] or rec["full_name"],
                "match_method": "exact_name",
                "confidence": 1.0,
            }

    tm_tokens = set()
    for name in names_to_check:
        tm_tokens.update(t for t in name.split() if len(t) >= 3)
    if not tm_tokens:
        return None

    tm_collapsed = tm_name.replace(" ", "")

    # 2. Flexible Date of Birth + Token / Fuzzy Match
    tm_dob = tm_player.get("dateOfBirth")
    for dob_variant in get_dob_variants(tm_dob):
        for entry in wy_index.get("by_dob", {}).get(dob_variant, []):
            wy_toks = entry["tokens"]
            if tm_tokens & wy_toks:
                return {
                    "wyscout_id": entry["wyscout_id"],
                    "wyscout_name": entry["short_name"] or entry["full_name"],
                    "match_method": "dob_and_token",
                    "confidence": 0.95,
                }

            wy_full = entry["full_norm"]
            wy_short = entry["short_norm"]
            if tm_collapsed and (
                tm_collapsed in wy_full.replace(" ", "")
                or wy_full.replace(" ", "") in tm_collapsed
            ):
                return {
                    "wyscout_id": entry["wyscout_id"],
                    "wyscout_name": entry["short_name"] or entry["full_name"],
                    "match_method": "dob_collapsed_name",
                    "confidence": 0.90,
                }

            for candidate in (wy_full, wy_short):
                if not candidate:
                    continue
                ratio = difflib.SequenceMatcher(None, tm_name, candidate).ratio()
                if ratio >= 0.65:
                    return {
                        "wyscout_id": entry["wyscout_id"],
                        "wyscout_name": entry["short_name"] or entry["full_name"],
                        "match_method": "dob_fuzzy",
                        "confidence": round(ratio, 2),
                    }
                if expanded_alias:
                    alias_ratio = difflib.SequenceMatcher(None, expanded_alias, candidate).ratio()
                    if alias_ratio >= 0.65:
                        return {
                            "wyscout_id": entry["wyscout_id"],
                            "wyscout_name": entry["short_name"] or entry["full_name"],
                            "match_method": "dob_alias_fuzzy",
                            "confidence": round(alias_ratio, 2),
                        }

    # 3. DOB-independent token overlap
    for entry in wy_index.get("all_records", []):
        wy_toks = entry["tokens"]
        intersection = tm_tokens & wy_toks
        if len(intersection) >= 2:
            return {
                "wyscout_id": entry["wyscout_id"],
                "wyscout_name": entry["short_name"] or entry["full_name"],
                "match_method": "multi_token_overlap",
                "confidence": 0.80,
            }
        if len(intersection) == 1 and any(len(t) >= 6 for t in intersection):
            if tm_tokens.issubset(wy_toks) or wy_toks.issubset(tm_tokens):
                return {
                    "wyscout_id": entry["wyscout_id"],
                    "wyscout_name": entry["short_name"] or entry["full_name"],
                    "match_method": "long_token_subset",
                    "confidence": 0.75,
                }

    return None