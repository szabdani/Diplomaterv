import json
import pandas as pd
from pathlib import Path
from typing import Any

from name_matcher import is_player_in_wyscout, load_wyscout_index
from transfermarkt_client import fetch_tm_players_from_team

# Resolve paths
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = REPO_ROOT / "data" / "transfermarkt"
RAW_SQUADS_DIR = OUTPUT_DIR / "squads_2017_2018"
DISCOVERED_TM_CLUBS_FILE = OUTPUT_DIR / "discovered_tm_clubs_2017_2018.json"
WYSCOUT_PLAYERS_FILE = REPO_ROOT / "data" / "wyscout" / "players.json"

FILTERED_SQUADS_FILE = OUTPUT_DIR / "filtered_squads_2017_2018.json"
MATCH_AUDIT_CSV = OUTPUT_DIR / "wyscout_squad_audit_2017_2018.csv"


def get_or_fetch_squad(club_id: str, club_name: str, season_year: int = 2017) -> list[dict[str, Any]]:
    """Loads a club squad from local JSON cache if present; otherwise fetches via API."""
    squad_file = RAW_SQUADS_DIR / f"{club_id}.json"
    if squad_file.exists():
        with open(squad_file, "r", encoding="utf-8") as f:
            return json.load(f)

    print(f"[FETCHING] Squad for {club_name} (ID: {club_id})...")
    squad = fetch_tm_players_from_team(club_id, season_year=season_year)
    if squad:
        with open(squad_file, "w", encoding="utf-8") as f:
            json.dump(squad, f, ensure_ascii=False, indent=2)
    return squad


def sync_and_check_squads(season_year: int = 2017):
    """
    1. Loads all 98 discovered clubs across the Top 5 leagues.
    2. Ensures each club squad is retrieved and saved locally.
    3. Cross-checks every squad player against Wyscout players.json.
    4. Exports retained active squads and an audit log of matched vs. skipped players.
    """
    RAW_SQUADS_DIR.mkdir(parents=True, exist_ok=True)

    if not DISCOVERED_TM_CLUBS_FILE.exists():
        raise FileNotFoundError(
            f"Club registry file '{DISCOVERED_TM_CLUBS_FILE.name}' not found. "
            "Run discovery first or verify file path."
        )

    with open(DISCOVERED_TM_CLUBS_FILE, "r", encoding="utf-8") as f:
        league_clubs_map: dict[str, list[dict[str, Any]]] = json.load(f)

    # Build reference lookup index from Wyscout
    wy_index = load_wyscout_index(WYSCOUT_PLAYERS_FILE)

    filtered_squads_by_club: dict[str, list[dict[str, Any]]] = {}
    audit_rows: list[dict[str, Any]] = []

    total_tm_players = 0
    total_matched_players = 0
    total_skipped_players = 0

    club_count = sum(len(clubs) for clubs in league_clubs_map.values())
    processed_count = 0

    print(f"\n[*] Starting squad evaluation across {club_count} clubs for season {season_year}...")

    for league_name, clubs in league_clubs_map.items():
        print(f"\n{'='*25} {league_name} ({len(clubs)} clubs) {'='*25}")

        for club in clubs:
            processed_count += 1
            club_id = str(club["id"])
            club_name = club["name"]

            squad = get_or_fetch_squad(club_id, club_name, season_year=season_year)
            retained_squad: list[dict[str, Any]] = []

            for player in squad:
                p_id = str(player.get("id"))
                p_name = player.get("name", "Unknown")
                p_dob = player.get("dateOfBirth")
                p_pos = player.get("position", "")
                p_mv = player.get("marketValue")

                is_active = is_player_in_wyscout(player, wy_index)

                audit_rows.append({
                    "league": league_name,
                    "club_id": club_id,
                    "club_name": club_name,
                    "tm_player_id": p_id,
                    "player_name": p_name,
                    "date_of_birth": p_dob,
                    "position": p_pos,
                    "market_value": p_mv,
                    "in_wyscout_dataset": is_active,
                })

                if is_active:
                    retained_squad.append(player)
                    total_matched_players += 1
                else:
                    total_skipped_players += 1

                total_tm_players += 1

            filtered_squads_by_club[club_id] = retained_squad

            print(
                f"[{processed_count:2d}/{club_count}] {club_name:<28} "
                f"Total: {len(squad):2d} | Matched: {len(retained_squad):2d} | "
                f"Cut: {len(squad) - len(retained_squad):2d}"
            )

    # 1. Export filtered squads JSON
    with open(FILTERED_SQUADS_FILE, "w", encoding="utf-8") as f:
        json.dump(filtered_squads_by_club, f, ensure_ascii=False, indent=2)

    # 2. Export detailed CSV audit report
    df_audit = pd.DataFrame(audit_rows)
    df_audit.to_csv(MATCH_AUDIT_CSV, index=False, encoding="utf-8-sig")

    # Overall Summary
    print("\n" + "=" * 65)
    print(f"Total Transfermarkt squad records scanned: {total_tm_players}")
    print(f"Matched in Wyscout (Senior / Active):       {total_matched_players} ({total_matched_players / total_tm_players * 100:.1f}%)")
    print(f"Cut (Youth / Inactive / 0 Apps):        {total_skipped_players} ({total_skipped_players / total_tm_players * 100:.1f}%)")
    print(f"Active squads saved to: {FILTERED_SQUADS_FILE}")
    print(f"Detailed audit log:     {MATCH_AUDIT_CSV}")
    print("=" * 65)

if __name__ == "__main__":
    sync_and_check_squads(season_year=2017)