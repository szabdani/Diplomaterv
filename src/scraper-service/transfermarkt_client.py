import os
import time
import random
import requests
from pathlib import Path
from typing import Any, Optional

from name_matcher import SLUG_QUERY_OVERRIDES, score_club_candidate

# Base configuration
DEFAULT_TM_API_URL = "http://localhost:8000"
TM_API_URL = os.getenv("TM_API_URL", DEFAULT_TM_API_URL).rstrip("/")

# =====================================================================
# Client Utilities
# =====================================================================

def requests_get_retry(
    url: str,
    headers: Optional[dict] = None,
    retries: int = 5,
    backoff: float = 30.0,
    polite_delay: tuple[float, float] = (2.0, 4.0),
) -> Optional[requests.Response]:
    """
    Executes a GET request with exponential backoff and rate-limit handling.
    """
    # Polite delay before every request to avoid triggering Transfermarkt 403 WAF blocks
    time.sleep(random.uniform(*polite_delay))

    for i in range(retries):
        try:
            response = requests.get(url, headers=headers)
            if response.status_code in [200, 404]: # 404 is a valid response, but has no data
                print(f"[OK] HTTP {response.status_code} at {url}")
                return response
            elif response.status_code in [403, 405, 429]:
                wait_time = backoff * (1.5 ** i) + random.uniform(10.0, 20.0)
                print(f"[RATE LIMIT / WAF] HTTP {response.status_code} at {url}. Waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
            elif response.status_code >= 500:
                wait_time = backoff * (i) + random.uniform(5.0, 10.0)
                print(f"[SERVER ERROR] HTTP {response.status_code} at {url}. Retrying after {wait_time:.1f}s...")
                time.sleep(wait_time)
            else:
                print(f"[RETRY] ({i+1}/{retries}) HTTP {response.status_code} at {url}. Retrying after {backoff}s...")
                time.sleep(backoff)
        except requests.RequestException as e:
            wait_time = backoff * (1.5 ** i) + random.uniform(5.0, 10.0)
            print(f"[ERROR] ({i+1}/{retries}) Connection failed for {url}: {e}")
            time.sleep(wait_time)

    return None

# =====================================================================
# Fetching Transfermarkt API Data
# =====================================================================

def fetch_tm_competition_clubs(competition_id: str, season_year: int = 2017) -> list[dict[str, Any]]:
    """
    Fetches all clubs participating in a competition for a specific season.
    """
    try:
        url = f"{TM_API_URL}/competitions/{competition_id}/clubs?season_id={season_year}"
        resp = requests_get_retry(url)
        if resp and resp.status_code == 200:
            clubs = resp.json().get("clubs", [])
            print(f"[OK] Loaded {len(clubs)} clubs for competition {competition_id} (Season {season_year})")
            return clubs
        print(f"[WARN] Competition clubs endpoint unavailable upstream (500/404): {competition_id}")
    except Exception as e:
        print(f"[ERROR] TM API Competition Clubs Error ({competition_id}): {e}")
    return []

def fetch_tm_team_data_search(
    team_name: str,
    short_name: Optional[str] = None,
    expected_countries: Optional[list[str]] = None,
) -> Optional[dict[str, Any]]:
    """
    Searches for a club and selects the best senior-team candidate matching country and name tokens.
    """
    base_queries = [short_name, team_name] if short_name and short_name != team_name else [team_name]
    queries: list[str] = []

    for q in base_queries:
        if not q:
            continue
        q_clean = q.lower().strip()
        if q_clean in SLUG_QUERY_OVERRIDES:
            queries.append(SLUG_QUERY_OVERRIDES[q_clean])
        if q_clean.startswith("st "):
            queries.append("saint-" + q_clean[3:])
        if q not in queries:
            queries.append(q)

    for query in queries:
        try:
            url = f"{TM_API_URL}/clubs/search/{query}"
            resp = requests_get_retry(url)
            if resp and resp.status_code == 200:
                results = resp.json().get("results", [])
                best_candidate = None
                best_score = -1

                for candidate in results:
                    score = score_club_candidate(candidate, query, expected_countries)
                    if score > best_score:
                        best_score = score
                        best_candidate = candidate

                if best_candidate and best_score >= 0:
                    print(
                        f"[OK] Club found by '{query}': {best_candidate.get('name')} "
                        f"(ID: {best_candidate.get('id')}, Country: {best_candidate.get('country')})"
                    )
                    return best_candidate
        except Exception as e:
            print(f"[ERROR] TM API Club Search Error ({query}): {e}")

    print(f"[NOT FOUND] Club not found: {team_name}")
    return None

def fetch_tm_players_from_team(tm_team_id: int | str, season_year: int = 2017) -> list[dict[str, Any]]:
    """
    Fetches all players in a club's squad for a specific season.
    """
    try:
        url = f"{TM_API_URL}/clubs/{tm_team_id}/players?season_id={season_year}"
        resp = requests_get_retry(url)
        if resp and resp.status_code == 200:
            players = resp.json().get("players", [])
            print(f"[OK] Loaded {len(players)} players for club {tm_team_id} (Season {season_year})")
            return players
        print(f"[NOT FOUND] Squad not found for club: {tm_team_id} (Season {season_year})")
    except Exception as e:
        print(f"[ERROR] TM API Get Club Players Error ({tm_team_id}): {e}")
    return []

def fetch_tm_player_search(tm_id: int | str, player_name: str) -> Optional[dict[str, Any]]:
    """
    Searches for a player and matches against their known Transfermarkt ID.
    """
    try:
        url = f"{TM_API_URL}/players/search/{player_name}"
        resp = requests_get_retry(url)
        if resp and resp.status_code == 200:
            for result in resp.json().get("results", []):
                if str(result.get("id")) == str(tm_id):
                    print(f"[OK] Player found: {result.get('name')} (ID: {result.get('id')})")
                    return result
        print(f"[NOT FOUND] Player ID {tm_id} matching '{player_name}' not found")
    except Exception as e:
        print(f"[ERROR] TM API Player Search Error ({player_name}): {e}")
    return None

def fetch_tm_player_profile(tm_player_id: int | str) -> Optional[dict[str, Any]]:
    """
    Fetches detailed player biographical data.
    """
    try:
        url = f"{TM_API_URL}/players/{tm_player_id}/profile"
        resp = requests_get_retry(url)
        if resp and resp.status_code == 200:
            print(f"[OK] Player profile found: {tm_player_id}")
            return resp.json()
        print(f"[NOT FOUND] Player profile not found: {tm_player_id}")
    except Exception as e:
        print(f"[ERROR] TM API Player Profile Error ({tm_player_id}): {e}")
    return None

def fetch_tm_market_value(tm_player_id: int | str) -> Optional[dict[str, Any]]:
    """
    Fetches complete historical market valuations for a player.
    """
    try:
        url = f"{TM_API_URL}/players/{tm_player_id}/market_value"
        resp = requests_get_retry(url)
        if resp and resp.status_code == 200:
            print(f"[OK] Market value history found: {tm_player_id}")
            return resp.json()
        print(f"[NOT FOUND] Market value history not found: {tm_player_id}")
    except Exception as e:
        print(f"[ERROR] TM API Market Value Error ({tm_player_id}): {e}")
    return None

def fetch_tm_transfers(tm_player_id: int | str) -> Optional[dict[str, Any]]:
    """
    Fetches career transfer history with fees and clubs for a player.
    """
    try:
        url = f"{TM_API_URL}/players/{tm_player_id}/transfers"
        resp = requests_get_retry(url)
        if resp and resp.status_code == 200:
            print(f"[OK] Transfer history found: {tm_player_id}")
            return resp.json()
        print(f"[NOT FOUND] Transfer history not found: {tm_player_id}")
    except Exception as e:
        print(f"[ERROR] TM API Transfers Error ({tm_player_id}): {e}")
    return None

def fetch_tm_injuries(tm_player_id: int | str) -> Optional[dict[str, Any]]:
    """
    Fetches the injury history of a player.
    """
    try:
        url = f"{TM_API_URL}/players/{tm_player_id}/injuries"
        resp = requests_get_retry(url)
        if resp and resp.status_code == 200:
            print(f"[OK] Injury history found: {tm_player_id}")
            return resp.json()
        print(f"[NOT FOUND] Injury history not found: {tm_player_id}")
    except Exception as e:
        print(f"[ERROR] TM API Injuries Error ({tm_player_id}): {e}")
    return None

def fetch_tm_player_season_appearances(tm_player_id: int | str, season_year: int = 2017) -> int:
    """
    Fetches competition stats for a player and sums total appearances 
    across all competitions for the given season year.
    """
    try:
        url = f"{TM_API_URL}/players/{tm_player_id}/stats"
        resp = requests_get_retry(url)
        if resp and resp.status_code == 200:
            data = resp.json()
            stats_list = data.get("stats", []) or []
            
            total_apps = 0
            for item in stats_list:
                # Matches format like "17/18", "2017", or integer 2017
                item_season = str(item.get("seasonID", item.get("season", "")))
                short_year = str(season_year)[-2:]  # "17"
                
                if str(season_year) in item_season or f"{short_year}/" in item_season:
                    # Appearances can be string ("5") or int (5) or "-" (0)
                    apps = item.get("appearances", 0)
                    if isinstance(apps, str):
                        apps = int(apps) if apps.isdigit() else 0
                    total_apps += (apps or 0)
                    
            return total_apps
    except Exception as e:
        print(f"[ERROR] Could not fetch stats for player {tm_player_id}: {e}")
        
    return 0

if __name__ == "__main__":
    print(f"Target TM API URL: {TM_API_URL}")
    print("=" * 60)

    # 1. Test Club Search (Arsenal)
    print("1. Testing Club Search...")
    club = fetch_tm_team_data_search("Arsenal FC", short_name="Arsenal")
    assert club is not None, "Failed to find Arsenal FC"
    club_id = club["id"]

    # 2. Test Squad retrieval for the 2017/18 season (Wyscout alignment)
    print(f"\n2. Testing 2017 Squad retrieval for club ID: {club_id}...")
    squad = fetch_tm_players_from_team(club_id, season_year=2017)
    assert len(squad) > 0, "Squad returned empty for 2017 season"

    # Pick the first player from the squad to test individual endpoints
    sample_player = squad[0]
    player_id = sample_player["id"]
    player_name = sample_player.get("name", "Unknown")
    print(f"\nSelected sample player from 2017 squad: {player_name} (ID: {player_id})")

    # 3. Test Player Profile
    print(f"\n3. Testing Player Profile...")
    profile = fetch_tm_player_profile(player_id)
    assert profile is not None, "Failed to fetch player profile"

    # 4. Test Player Search Matching
    print(f"\n4. Testing Player Search Match...")
    search_res = fetch_tm_player_search(player_id, player_name)

    # 5. Test Market Value History
    print(f"\n5. Testing Market Value History...")
    mv_history = fetch_tm_market_value(player_id)
    assert mv_history is not None, "Failed to fetch market value history"

    # 6. Test Transfer History
    print(f"\n6. Testing Transfer History...")
    transfers = fetch_tm_transfers(player_id)
    assert transfers is not None, "Failed to fetch transfers"

    # 7. Test Injury History
    print(f"\n7. Testing Injury History...")
    injuries = fetch_tm_injuries(player_id)
    assert injuries is not None, "Failed to fetch injuries"

    # 8. Test Clubs in a Competition
    print(f"\n8. Testing Clubs in Competition...")
    competition_id = "GB1"
    clubs_in_competition = fetch_tm_competition_clubs(competition_id, season_year=2017)
    assert len(clubs_in_competition) > 0, f"No clubs found for competition {competition_id}"

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED: Streamlined Transfermarkt client is fully functional!")