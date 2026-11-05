import os
import json
import pika
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

# Import database and message broker connections
from connections import get_mongo_connection, get_rabbitmq_connection, IS_DOCKER

# Import the three scraper pipelines
from wyscout_downloader import ensure_wyscout_data, EXPECTED_MATCH_FILES, EXPECTED_EVENT_FILES
from capology_scraper import scrape_all_top5_leagues
from transfermarkt_scraper import scrape_all_top5_transfermarkt

# Resolve paths: <repo_root>
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"

# Explicitly load .env from repository root
load_dotenv(dotenv_path=REPO_ROOT / ".env")

# Transfermarkt API configuration
DEFAULT_TM_HOST = "transfermarkt-api" if IS_DOCKER else "localhost"
TM_API_URL = os.getenv("TM_API_URL", f"http://{DEFAULT_TM_HOST}:8000").rstrip("/")

# Establish Connections
mongo_client, raw_collection = get_mongo_connection()
rabbit_conn, channel, RABBITMQ_QUEUE = get_rabbitmq_connection()

# =====================================================================
# Claim-Check Pattern Implementation
# =====================================================================

def save_and_publish_claim_check(
        channel,
        source: str,
        entity_type: str,
        raw_payload: dict,
        unique_key: str,
        metadata: dict | None = None,
) -> None:
    """
    Implements the Claim-Check pattern
    - Saves the heavy raw JSON payload in MongoDB.
    - Publishes a lightweight reference message to RabbitMQ.
    """
    doc_id = f"{source}:{entity_type}:{unique_key}"
    now_iso = datetime.now(timezone.utc).isoformat()
    document = {
        "_id": doc_id,
        "source": source,             # e.g., 'wyscout', 'transfermarkt', 'capology'
        "entity_type": entity_type,   # e.g., 'match_events', 'team_squad', 'player_wage'
        "unique_key": unique_key,
        "metadata": metadata or {},
        "loaded_at": now_iso,
        "payload": raw_payload,
    }
    
    # Store in MongoDB
    raw_collection.replace_one({"_id": doc_id}, document, upsert=True)

    # Send lightweight Claim-Check to RabbitMQ
    claim_check_msg = {
        "document_id": doc_id,
        "source": source,
        "entity_type": entity_type,
        "unique_key": unique_key,
        "metadata": metadata or {},
        "timestamp": document["loaded_at"]
    }
    channel.basic_publish(
        exchange="",
        routing_key=RABBITMQ_QUEUE,
        body=json.dumps(claim_check_msg),
        properties=pika.BasicProperties(delivery_mode=2)  # Persistent message
    )
    print(f"[Claim-Check Sent] {source}:{entity_type} -> Mongo ID: {doc_id}")

# =====================================================================
# Loading Functions for Each Data Source
# =====================================================================

def load_wyscout_to_datapipeline(wyscout_dir: Path, channel) -> None:
    """
    Reads local Wyscout JSON files and dispatches them via Claim-Check.
    Splits large match/event files into manageable chunks.
    """
    # 1. Competitions & Teams
    for name, entity_type in [("competitions.json", "competitions"), ("teams.json", "teams")]:
        file_path = wyscout_dir / name
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            save_and_publish_claim_check(
                channel=channel,
                source="wyscout",
                entity_type=entity_type,
                raw_payload={"items": data},
                unique_key=entity_type,
            )

    # 2. Players
    players_file = wyscout_dir / "players.json"
    if players_file.exists():
        with open(players_file, "r", encoding="utf-8") as f:
            players = json.load(f)
        batch_size = 500
        for i in range(0, len(players), batch_size):
            batch = players[i : i + batch_size]
            batch_key = f"players_batch_{i // batch_size}"
            save_and_publish_claim_check(
                channel=channel,
                source="wyscout",
                entity_type="players_batch",
                raw_payload={"players": batch},
                unique_key=batch_key,
                metadata={"count": len(batch)},
            )

    # 3. Matches per competition file
    matches_dir = wyscout_dir / "matches"
    for match_filename in EXPECTED_MATCH_FILES:
        file_path = matches_dir / match_filename
        if file_path.exists():
            competition_label = match_filename.replace("matches_", "").replace(".json", "")
            with open(file_path, "r", encoding="utf-8") as f:
                matches = json.load(f)
            save_and_publish_claim_check(
                channel=channel,
                source="wyscout",
                entity_type="matches",
                raw_payload={"competition": competition_label, "matches": matches},
                unique_key=f"matches_{competition_label}",
                metadata={"competition": competition_label, "match_count": len(matches)},
            )

    # 4. Spatial Events grouped by matchId
    events_dir = wyscout_dir / "events"
    for event_filename in EXPECTED_EVENT_FILES:
        file_path = events_dir / event_filename
        if not file_path.exists():
            continue

        competition_label = event_filename.replace("events_", "").replace(".json", "")
        print(f"[WYSCOUT] Grouping spatial events by matchId from {event_filename}...")
        with open(file_path, "r", encoding="utf-8") as f:
            all_events = json.load(f)

        events_by_match: dict[int | str, list[dict[str, Any]]] = defaultdict(list)
        for ev in all_events:
            events_by_match[ev.get("matchId", "Unknown")].append(ev)

        for match_id, match_events in events_by_match.items():
            save_and_publish_claim_check(
                channel=channel,
                source="wyscout",
                entity_type="match_events",
                raw_payload={
                    "competition": competition_label,
                    "matchId": match_id,
                    "events": match_events,
                },
                unique_key=f"match_{match_id}",
                metadata={
                    "competition": competition_label,
                    "match_id": match_id,
                    "event_count": len(match_events),
                },
            )

def load_capology_to_datapipeline(capology_clubs_dir: Path, channel) -> None:
    """
    Reads cached Capology club salary JSONs and dispatches one Claim-Check per club.
    """
    for club_file in sorted(capology_clubs_dir.glob("*.json")):
        with open(club_file, "r", encoding="utf-8") as f:
            salaries = json.load(f)

        if not salaries:
            print(f"[WARNING] No salaries found in {club_file.name}.")
            continue

        club_slug = club_file.stem
        league = salaries[0].get("league", "Unknown")
        season = salaries[0].get("season", "Unknown")

        save_and_publish_claim_check(
            channel=channel,
            source="capology",
            entity_type="club_salaries",
            raw_payload={
                "club": club_slug, 
                "league": league,
                "season": season,
                "salaries": salaries,
            },
            unique_key=f"{season}_{club_slug}",
            metadata={"club": club_slug, "league": league, "player_count": len(salaries)},
        )

def load_transfermarkt_to_datapipeline(transfermarkt_players_dir: Path, channel) -> None:
    """
    Reads cached Transfermarkt player JSONs and dispatches one Claim-Check per player.
    """
    for player_file in sorted(transfermarkt_players_dir.glob("*.json")):
        with open(player_file, "r", encoding="utf-8") as f:
            player_data = json.load(f)

        if not player_data:
            print(f"[WARNING] No data found in {player_file.name}.")
            continue

        player_id_value = player_data.get("player_id")
        player_id = str(player_id_value) if player_id_value is not None else player_file.stem

        save_and_publish_claim_check(
            channel=channel,
            source="transfermarkt",
            entity_type="player_details",
            raw_payload=player_data,
            unique_key=f"player_{player_id}",
            metadata={
                "player_id": player_id, 
                "player_name": player_data.get("player_name"),
                "league": player_data.get("league"),
                "club_name": player_data.get("club_name"),
                },
        )

# =====================================================================
# Main Pipeline: Extract, Load, and Claim-Check
# =====================================================================

def run_pipeline():
    """
    Full extraction and Claim-Check loading pipeline:
    1. Ensures Wyscout dataset is downloaded & extracted.
    2. Scrapes Capology 2017/18 salaries (uses local cache if already scraped).
    3. Scrapes Transfermarkt 2017/18 squads & player histories (uses local cache if already scraped).
    4. Stores all raw JSON documents in MongoDB and publishes Claim-Check tickets to RabbitMQ.
    """
    try:
        print("\n" + "=" * 60)
        print("STEP 1: Ensuring Wyscout 2017/18 Dataset")
        print("=" * 60)
        wyscout_dir = DATA_DIR / "wyscout"
        ensure_wyscout_data(wyscout_dir)

        print("\n" + "=" * 60)
        print("STEP 2: Scraping Capology 2017/18 Club Salaries")
        print("=" * 60)
        scrape_all_top5_leagues(season="2017-2018")

        print("\n" + "=" * 60)
        print("STEP 3: Scraping Transfermarkt 2017/18 Players")
        print("=" * 60)
        scrape_all_top5_transfermarkt(season_year=2017, TM_API_URL=TM_API_URL)

        print("\n" + "=" * 60)
        print("STEP 4A: Loading Wyscout Data into MongoDB & RabbitMQ")
        print("=" * 60)
        load_wyscout_to_datapipeline(wyscout_dir, channel)

        print("\n" + "=" * 60)
        print("STEP 4B: Loading Capology Data into MongoDB & RabbitMQ")
        print("=" * 60)
        load_capology_to_datapipeline(DATA_DIR / "capology" / "clubs_2017_2018", channel)

        print("\n" + "=" * 60)
        print("STEP 4C: Loading Transfermarkt Player Data into MongoDB & RabbitMQ")
        print("=" * 60)
        load_transfermarkt_to_datapipeline(DATA_DIR / "transfermarkt" / "players_2017_2018", channel)

        print("\n" + "=" * 60)
        print("[PIPELINE COMPLETE] All sources scraped, stored in MongoDB, and queued in RabbitMQ!")
        print("=" * 60)

    finally:
        if rabbit_conn and rabbit_conn.is_open:
            rabbit_conn.close()
        if mongo_client:
            mongo_client.close()


if __name__ == "__main__":
    run_pipeline()