import os
import zipfile
import urllib.request
from pathlib import Path

# Calculates: <repo_root>/data/wyscout
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "wyscout"

# Official Figshare direct download URLs from Pappalardo et al. (2019)
WYSCOUT_URLS = {
    "competitions.json": "https://ndownloader.figshare.com/files/15073685",
    "teams.json": "https://ndownloader.figshare.com/files/15073697",
    "players.json": "https://ndownloader.figshare.com/files/15073721",
    "matches.zip": "https://ndownloader.figshare.com/files/14464622",
    "events.zip": "https://ndownloader.figshare.com/files/14464685",
}

# All files expected inside matches/ and events/ based on Pappalardo et al. (2019)
EXPECTED_MATCH_FILES = [
    "matches_England.json",
    "matches_France.json",
    "matches_Germany.json",
    "matches_Italy.json",
    "matches_Spain.json",
    "matches_European_Championship.json",
    "matches_World_Cup.json",
]

EXPECTED_EVENT_FILES = [
    "events_England.json",
    "events_France.json",
    "events_Germany.json",
    "events_Italy.json",
    "events_Spain.json",
    "events_European_Championship.json",
    "events_World_Cup.json",
]

def are_files_present(directory: Path, expected_filenames: list[str]) -> bool:
    """Checks if all expected files exist in the specified directory."""
    if not directory.exists() or not directory.is_dir():
        return False
    return all((directory / filename).is_file() for filename in expected_filenames)

def ensure_wyscout_data(data_dir: Path | str = DEFAULT_DATA_DIR):
    """
    Downloads and extracts the Wyscout dataset from Figshare if not already present locally.
    """
    base_path = Path(data_dir).resolve()
    base_path.mkdir(parents=True, exist_ok=True)

    print(f"Target data directory: {base_path}")

    # 1. Check & Download root JSON files (competitions, teams, players)
    for filename in ["competitions.json", "teams.json", "players.json"]:
        file_path = base_path / filename
        if file_path.is_file():
            print(f"[OK] {filename} is present.")
        else:
            print(f"[MISSING] Downloading {filename} from Figshare...")
            urllib.request.urlretrieve(WYSCOUT_URLS[filename], file_path)

    # 2. Check matches
    matches_dir = base_path / "matches"
    if are_files_present(matches_dir, EXPECTED_MATCH_FILES):
        print(f"[OK] All {len(EXPECTED_MATCH_FILES)} match files are present in {matches_dir.name}/.")
    else:
        print("[MISSING] One or more match files are missing. Downloading matches.zip...")
        zip_path = base_path / "matches.zip"
        urllib.request.urlretrieve(WYSCOUT_URLS["matches.zip"], zip_path)
        
        matches_dir.mkdir(exist_ok=True)
        print(f"Extracting matches.zip to {matches_dir}...")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(matches_dir)
        zip_path.unlink()

    # 3. Check events
    events_dir = base_path / "events"
    if are_files_present(events_dir, EXPECTED_EVENT_FILES):
        print(f"[OK] All {len(EXPECTED_EVENT_FILES)} event files are present in {events_dir.name}/.")
    else:
        print("[MISSING] One or more event files are missing. Downloading events.zip...")
        zip_path = base_path / "events.zip"
        urllib.request.urlretrieve(WYSCOUT_URLS["events.zip"], zip_path)
        
        events_dir.mkdir(exist_ok=True)
        print(f"Extracting events.zip to {events_dir}...")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(events_dir)
        zip_path.unlink()

    print("[OK] Wyscout dataset verification complete. All files are ready.")

if __name__ == "__main__":
    ensure_wyscout_data()