import json
import time
import pandas as pd
from pathlib import Path
from typing import Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from transfermarkt_client import (
    fetch_tm_competition_clubs,
    fetch_tm_team_data_search,
    fetch_tm_players_from_team,
    fetch_tm_player_profile,
    fetch_tm_market_value,
    fetch_tm_transfers,
    fetch_tm_injuries,
)
from name_matcher import load_wyscout_index, is_player_in_wyscout, build_profile_from_squad_summary

# Resolve paths: <repo_root>/data/transfermarkt
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = REPO_ROOT / "data" / "transfermarkt"
RAW_SQUADS_DIR = OUTPUT_DIR / "squads_2017_2018"
RAW_PLAYERS_DIR = OUTPUT_DIR / "players_2017_2018"
DISCOVERED_TM_CLUBS_FILE = OUTPUT_DIR / "discovered_tm_clubs_2017_2018.json"
CAPOLOGY_DISCOVERED_FILE = REPO_ROOT / "data" / "capology" / "discovered_clubs_2017_2018.json"
WYSCOUT_PLAYERS_FILE = REPO_ROOT / "data" / "wyscout" / "players.json"

# Direct CDN URLs for https://github.com/dcaribou/transfermarkt-datasets fallback
DCARIBOU_R2_BASE = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data"

# Transfermarkt Competition IDs for the Top 5 European Leagues
TOP5_LEAGUE_TM_IDS = {
    "Premier League": "GB1",
    "La Liga": "ES1",
    "Serie A": "IT1",
    "Bundesliga": "L1",
    "Ligue 1": "FR1",
}

# Allowed Transfermarkt countries per league
LEAGUE_COUNTRIES = {
    "Premier League": ["England", "Wales"],
    "La Liga": ["Spain"],
    "Serie A": ["Italy"],
    "Bundesliga": ["Germany"],
    "Ligue 1": ["France", "Monaco"],
}

# =====================================================================
# Helpers for Caching and Validating Player Data
# =====================================================================

def is_cached_player_complete(cached_record: dict[str, Any]) -> bool:
    """
    Checks whether a cached player file is complete.
    """
    if cached_record.get("profile") is None:
        return False
    if not cached_record.get("fetch_complete", False):
        return False
    return True

def discover_all_tm_clubs(season_year: int = 2017) -> dict[str, list[dict[str, Any]]]:
    """
    Loads Top 5 league clubs from local cache if present, otherwise queries the TM API.
    Falls back to Capology discovered club slugs when a competition endpoint is unavailable.
    """
    if DISCOVERED_TM_CLUBS_FILE.exists():
        print(f"[CACHE HIT] Loaded discovered TM clubs from {DISCOVERED_TM_CLUBS_FILE.name}")
        with open(DISCOVERED_TM_CLUBS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    discovered: dict[str, list[dict[str, Any]]] = {}

    capology_leagues: dict[str, list[str]] = {}
    if CAPOLOGY_DISCOVERED_FILE.exists():
        print(f"[OK] Loaded Capology discovered clubs from {CAPOLOGY_DISCOVERED_FILE.name}")
        with open(CAPOLOGY_DISCOVERED_FILE, "r", encoding="utf-8") as f:
            capology_leagues = json.load(f)

    for league_name, comp_id in TOP5_LEAGUE_TM_IDS.items():
        print(f"\n[DISCOVERY] Fetching TM API for {league_name} ({comp_id}) clubs for season {season_year}...")
        clubs = fetch_tm_competition_clubs(comp_id, season_year=season_year)

        if clubs:
            discovered[league_name] = [
                {"id": str(c.get("id")), "name": c.get("name")} for c in clubs if c.get("id")
            ]
            continue

        slugs = capology_leagues.get(league_name, [])
        if not slugs:
            print(f"[WARNING] TM API failed and no Capology clubs are available for {league_name}.")
            continue

        print(f"[FALLBACK] Searching TM by Capology slugs for {league_name}: {len(slugs)} clubs.")
        expected_country_filters = LEAGUE_COUNTRIES.get(league_name, [])
        discovered[league_name] = []
        seen_ids: set[str] = set()

        for slug in slugs:
            search_name = slug.replace("-", " ")
            club_res = fetch_tm_team_data_search(
                search_name,
                short_name=search_name,
                expected_countries=expected_country_filters,
            )
            if club_res and club_res.get("id"):
                club_id = str(club_res["id"])
                if club_id in seen_ids:
                    print(f"[WARNING] Duplicate club ID ({club_id}) for {search_name} in {league_name}.")
                seen_ids.add(club_id)

                discovered[league_name].append({
                    "id": club_id,
                    "name": club_res.get("name", search_name),
                    "slug": slug,
                })
            else:
                print(f"[ERROR] No TM club found for Capology slug '{slug}' ({search_name}) in {league_name}.")

    # Save discovered clubs to disk so discovery only runs once
    with open(DISCOVERED_TM_CLUBS_FILE, "w", encoding="utf-8") as f:
        json.dump(discovered, f, ensure_ascii=False, indent=2)

    total_clubs = sum(len(clubs) for clubs in discovered.values())
    print(f"[OK] Discovered clubs ({total_clubs}) saved to {DISCOVERED_TM_CLUBS_FILE.name}")
    return discovered

# =====================================================================
# Caching Transfermarkt Squads and Player Data
# =====================================================================

def fetch_and_cache_club_squad(
        club_id: str,
        club_name: str,
        league_name: str,
        season_year: int = 2017
) -> list[dict[str, Any]]:
    """
    Fetches the 2017/18 squad for a single club. Checks local JSON cache first.
    """
    squad_cache_file = RAW_SQUADS_DIR / f"{club_id}.json"

    if squad_cache_file.exists():
        print(f"[CACHE HIT] Loaded squad for {club_name} (ID: {club_id}) from disk.")
        with open(squad_cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    print(f"[FETCHING] Squad for {club_name} ({league_name}, ID: {club_id})...")
    players = fetch_tm_players_from_team(club_id, season_year=season_year)

    if players:
        with open(squad_cache_file, "w", encoding="utf-8") as f:
            json.dump(players, f, ensure_ascii=False, indent=2)

    return players

def fetch_and_cache_player_details(
    player_summary: dict[str, Any],
    club_id: str,
    club_name: str,
    league_name: str,
    season_label: str = "2017-2018"
) -> Optional[dict[str, Any]]:
    """
    Fetches profile, market value history, transfers, and injuries for a single player.
    Uses local JSON cache per player ID to avoid duplicate calls on restarts or mid-season transfers.
    """
    player_id = str(player_summary.get("id", "")).strip()
    player_name = player_summary.get("name", "Unknown")

    if not player_id:
        return None

    player_cache_file = RAW_PLAYERS_DIR / f"{player_id}.json"
    cached_record: Optional[dict[str, Any]] = None

    if player_cache_file.exists():
        try:
            with open(player_cache_file, "r", encoding="utf-8") as f:
                cached_record = json.load(f)
        except Exception as e:
                    print(f"[ERROR] Failed to load cached player {player_name} (ID: {player_id}): {e}")
                    cached_record = None

        if cached_record and is_cached_player_complete(cached_record):
            print(f"[CACHE HIT] Loaded player {player_name} (ID: {player_id}) from disk.")
            return cached_record

    print(f"[FETCHING] Player details for {player_name} (ID: {player_id}, Club: {club_name})...")

    # Build profile from squad summary 
    if cached_record and cached_record.get("profile") is not None:
        profile = cached_record["profile"]
    else:
        profile = build_profile_from_squad_summary(player_summary)

    # Market value history
    if cached_record and cached_record.get("market_value_history") is not None:
        market_values = {"marketValueHistory": cached_record["market_value_history"]}
    else:
        market_values = fetch_tm_market_value(player_id)

    # Transfers history
    if cached_record and cached_record.get("transfers") is not None:
        transfers = {"transfers": cached_record["transfers"]}
    else:
        transfers = fetch_tm_transfers(player_id)

    # Injuries history
    if cached_record and cached_record.get("injuries") is not None:
        injuries = {"injuries": cached_record["injuries"]}
    else:
        injuries = fetch_tm_injuries(player_id)
    
    # Check if all 4 endpoints succeeded
    fetch_complete = all(x is not None for x in [profile, market_values, transfers, injuries])

    player_record = {
        "tm_player_id": player_id,
        "player_name": player_name,
        "season": season_label,
        "league": league_name,
        "tm_club_id": club_id,
        "club_name": club_name,
        "joined_on": player_summary.get("joinedOn"),
        "fetch_complete": fetch_complete,
        "profile": profile,
        "market_value_history": market_values.get("marketValueHistory", []) if market_values else [],
        "transfers": transfers.get("transfers", []) if transfers else [],
        "injuries": injuries.get("injuries", []) if injuries else [],
    }

    # Persist individual player record immediately
    with open(player_cache_file, "w", encoding="utf-8") as f:
        json.dump(player_record, f, ensure_ascii=False, indent=2)

    if not fetch_complete:
        print(f"[WARNING] Incomplete data saved for player {player_name} (ID: {player_id}).")

    return player_record

# =====================================================================
# Fallback Dataset:
# =====================================================================

def seed_players_from_dataset(
    target_player_map: dict[str, dict[str, Any]],
    wy_index: dict[str, Any],
    season_label: str = "2017-2018",
):
    """
    Fallback dataset using https://github.com/dcaribou/transfermarkt-datasets.
    Downloads players.csv.gz, player_valuations.csv.gz, and transfers.csv.gz in memory
    and populates RAW_PLAYERS_DIR/{player_id}.json for any missing/incomplete players.
    """
    missing_ids = {
        pid for pid in target_player_map
        if not (RAW_PLAYERS_DIR / f"{pid}.json").exists()
    }
    if not missing_ids:
        print("[DATASET SEEDER] All target players are already cached locally.")
        return

    print(f"[DATASET SEEDER] Seeding {len(missing_ids)} players from dcaribou/transfermarkt-datasets...")
    players_df = pd.read_csv(f"{DCARIBOU_R2_BASE}/players.csv.gz", dtype={"player_id": str})
    valuations_df = pd.read_csv(f"{DCARIBOU_R2_BASE}/player_valuations.csv.gz", dtype={"player_id": str})
    transfers_df = pd.read_csv(f"{DCARIBOU_R2_BASE}/transfers.csv.gz", dtype={"player_id": str})

    players_by_id = players_df[players_df["player_id"].isin(missing_ids)].set_index("player_id").to_dict("index")
    vals_by_id = {
        pid: grp.to_dict("records")
        for pid, grp in valuations_df[valuations_df["player_id"].isin(missing_ids)].groupby("player_id")
    }
    trans_by_id = {
        pid: grp.to_dict("records")
        for pid, grp in transfers_df[transfers_df["player_id"].isin(missing_ids)].groupby("player_id")
    }

    seeded_count = 0
    for pid in missing_ids:
        ctx = target_player_map[pid]
        player_summary = ctx["player_summary"]
        ds_profile = players_by_id.get(pid, {})

        profile = build_profile_from_squad_summary(player_summary)
        if ds_profile:
            profile["height"] = profile.get("height") or ds_profile.get("height_in_cm")
            profile["foot"] = profile.get("foot") or ds_profile.get("foot")
            profile["dateOfBirth"] = profile.get("dateOfBirth") or ds_profile.get("date_of_birth")

        player_record = {
            "tm_player_id": pid,
            "player_name": player_summary.get("name", ds_profile.get("name", "Unknown")),
            "season": season_label,
            "league": ctx["league_name"],
            "tm_club_id": ctx["club_id"],
            "club_name": ctx["club_name"],
            "joined_on": player_summary.get("joinedOn"),
            "fetch_complete": True,
            "profile": profile,
            "market_value_history": vals_by_id.get(pid, []),
            "transfers": trans_by_id.get(pid, []),
            "injuries": [],
        }

        with open(RAW_PLAYERS_DIR / f"{pid}.json", "w", encoding="utf-8") as f:
            json.dump(player_record, f, ensure_ascii=False, indent=2)
        seeded_count += 1

    print(f"[DATASET SEEDER] Seeded {seeded_count} player files into {RAW_PLAYERS_DIR.name}/.")


# =====================================================================
# Main Pipeline: Discover Clubs, Fetch Squads, Fetch Player Data
# =====================================================================

def scrape_all_top5_transfermarkt(
    season_year: int = 2017,
    max_workers: int = 4,
    use_dataset_fallback: bool = True,
):
    """
    Main pipeline to discover all 2017/18 Top 5 league clubs, retrieve their squads,
    and fetch complete Transfermarkt profiles, market values, transfers, and injuries.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_SQUADS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_PLAYERS_DIR.mkdir(parents=True, exist_ok=True)

    wy_index = load_wyscout_index(WYSCOUT_PLAYERS_FILE)
    season_label = f"{season_year}_{season_year + 1}"

    # Discover all clubs across the Top 5 leagues
    league_clubs_map = discover_all_tm_clubs(season_year=season_year)
    total_clubs = sum(len(clubs) for clubs in league_clubs_map.values())


    # Fetch all 98 club squads first 
    club_squads: list[tuple[str, str, str, list[dict[str, Any]]]] = []
    unique_players_map: dict[str, dict[str, Any]] = {}
    failed_clubs: list[tuple[str, str, str]] = []

    processed_clubs = 0
    # Iterate through each league and club
    for league_name, clubs in league_clubs_map.items():
        print(f"\n{'='*20} Fetching {league_name} ({len(clubs)} clubs) {'='*20}")

        for club in clubs:
            processed_clubs += 1
            club_id = str(club["id"])
            club_name = club["name"]
            print(f"\n[{processed_clubs}/{total_clubs}] Club: {club_name} (ID: {club_id})")

            squad = fetch_and_cache_club_squad(club_id, club_name, league_name, season_year=season_year)
            if not squad:
                failed_clubs.append((league_name, club_name, club_id))
                continue
            
            club_squads.append((league_name, club_id, club_name, squad))
            for player_summary in squad:
                pid = str(player_summary.get("id", "")).strip()
                if pid and pid not in unique_players_map:
                    unique_players_map[pid] = {
                        "player_summary": player_summary,
                        "club_id": club_id,
                        "club_name": club_name,
                        "league_name": league_name,
                    }
    print(f"\n[SQUADS READY] {len(club_squads)}/{total_clubs} clubs loaded ({len(unique_players_map)} unique players).")

    # Optional: Seed from dcaribou/transfermarkt-datasets if enabled
    if use_dataset_fallback:
        seed_players_from_dataset(
            target_player_map=unique_players_map,
            wy_index=wy_index,
            season_label=f"{season_year}-{season_year + 1}",
        )

    # Fetch unique players in parallel with ThreadPoolExecutor
    total_unique = len(unique_players_map)
    completed_count = 0

    print(f"[SCRAPING PLAYERS] Fetching details for {total_unique} unique players (workers={max_workers})...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_pid = {
            executor.submit(
                fetch_and_cache_player_details,
                player_summary=ctx["player_summary"],
                club_id=ctx["club_id"],
                club_name=ctx["club_name"],
                league_name=ctx["league_name"],
                season_label=f"{season_year}-{season_year + 1}",
            ): pid
            for pid, ctx in unique_players_map.items()
        }

        for future in as_completed(future_to_pid):
            completed_count += 1
            pid = future_to_pid[future]
            try:
                res = future.result()
                if completed_count % 50 == 0 or completed_count == total_unique:
                    status = "OK" if res and res.get("fetch_complete") else "PARTIAL"
                    print(f"  -> Progress: [{completed_count}/{total_unique}] (Last ID: {pid}, {status})")
            except Exception as e:
                print(f"  -> [ERROR] Player ID {pid} raised exception: {e}")

    # Consolidate JSON and summary CSV across all club squads
    all_players_data: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
   
    for league_name, club_id, club_name, squad in club_squads:
        for player_summary in squad:
            pid = str(player_summary.get("id", "")).strip()
            cache_file = RAW_PLAYERS_DIR / f"{pid}.json"
            if not cache_file.exists():
                continue

            with open(cache_file, "r", encoding="utf-8") as f:
                player_record = json.load(f)

            all_players_data.append(player_record)
            profile_data = player_record.get("profile", {}) or {}
            pos_data = profile_data.get("position", {}) or {}
            main_pos = pos_data.get("main") if isinstance(pos_data, dict) else pos_data

            summary_rows.append({
                "tm_player_id": player_record.get("tm_player_id"),
                "player_name": player_record.get("player_name"),
                "season": player_record.get("season"),
                "league": league_name,
                "tm_club_id": club_id,
                "club_name": club_name,
                "position": player_summary.get("position") or main_pos,
                "date_of_birth": player_summary.get("dateOfBirth") or profile_data.get("dateOfBirth"),
                "foot": player_summary.get("foot") or profile_data.get("foot"),
                "height": player_summary.get("height") or profile_data.get("height"),
                "joined_on": player_summary.get("joinedOn"),
                "market_value_entries_count": len(player_record.get("market_value_history", [])),
                "transfers_count": len(player_record.get("transfers", [])),
                "injuries_count": len(player_record.get("injuries", [])),
            })

    # Save consolidated datasets
    json_file = OUTPUT_DIR / f"transfermarkt_players_{season_label}.json"
    csv_file = OUTPUT_DIR / f"transfermarkt_players_summary_{season_label}.csv"

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(all_players_data, f, ensure_ascii=False, indent=2)

    df = pd.DataFrame(summary_rows)
    df.to_csv(csv_file, index=False, encoding="utf-8-sig")

    print("\n" + "=" * 60)
    print(f"[DONE] Successfully processed {len(all_players_data)} player-season records.")
    print(f"JSON file: {json_file}")
    print(f"CSV file:  {csv_file}")

    if failed_clubs:
        print(f"\n[WARNING] {len(failed_clubs)} clubs returned no squad data:")
        for league, c_name, c_id in failed_clubs:
            print(f"  - {league}: {c_name} (ID: {c_id})")

if __name__ == "__main__":
    scrape_all_top5_transfermarkt(season_year=2017)