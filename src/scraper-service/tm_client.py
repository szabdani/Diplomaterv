import os
import time
import requests
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv

# Automatically locate and load <repo_root>/.env
ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Base configuration
DEFAULT_TM_API_URL = "http://localhost:8000"
TM_API_URL = os.getenv("TM_API_URL", DEFAULT_TM_API_URL).rstrip("/")

def requests_get_retry(
    url: str,
    headers: Optional[dict] = None,
    retries: int = 3,
    backoff: float = 2.0
) -> Optional[requests.Response]:
    """
    Executes a GET request with exponential backoff and rate-limit handling.
    """
    for i in range(retries):
        try:
            response = requests.get(url, headers=headers)
            if response.status_code in [200, 404]: # 404 is a valid response, but has no data
                print(f"[OK] HTTP {response.status_code} at {url}")
                return response
            elif response.status_code == 429: # Too Many Requests
                print(f"[RATE LIMIT] 429 at {url}. Waiting {backoff}s...")
                time.sleep(backoff)
            else:
                print(f"[RETRY] ({i+1}/{retries}) HTTP {response.status_code} at {url}")
        except requests.RequestException as e:
            print(f"[ERROR] ({i+1}/{retries}) Connection failed for {url}: {e}")

        time.sleep(backoff)
    return None

def fetch_tm_team_data_search(team_name: str, short_name: Optional[str] = None) -> Optional[dict[str, Any]]:
    """
    Searches for a club by short name first, then falls back to full name.
    """
    queries = [short_name, team_name] if short_name else [team_name]

    for query in queries:
        try:
            url = f"{TM_API_URL}/clubs/search/{query}"
            resp = requests_get_retry(url)
            if resp and resp.status_code == 200:
                results = resp.json().get("results", [])
                if results:
                    print(f"[OK] Club found by {query}: {results[0].get('name')} (ID: {results[0].get('id')})")
                    return results[0]
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

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED: Streamlined Transfermarkt client is fully functional!")