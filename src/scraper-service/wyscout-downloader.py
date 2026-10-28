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

def ensure_wyscout_data(data_dir: Path | str = DEFAULT_DATA_DIR):
    """
    Downloads and extracts the Wyscout dataset from Figshare if not already present locally.
    """
    base_path = Path(data_dir).resolve()
    base_path.mkdir(parents=True, exist_ok=True)

    print(f"Target data directory: {base_path}")

    for filename, url in WYSCOUT_URLS.items():
        target_path = base_path / filename

        # Skip if already downloaded or extracted
        if filename == "matches.zip" and (base_path / "matches" / "matches_England.json").exists():
            continue
        if filename == "events.zip" and (base_path / "events" / "events_England.json").exists():
            continue
        if target_path.exists():
            continue

        print(f"Downloading {filename} from Figshare...")
        urllib.request.urlretrieve(url, target_path)

        # If it's a zip file (matches.zip or events.zip), extract into a subfolder and delete the zip
        if filename.endswith(".zip"):
            folder_name = filename.replace(".zip", "")
            extract_dir = base_path / folder_name
            extract_dir.mkdir(exist_ok=True)
            print(f"Extracting {filename} to {extract_dir}...")
            with zipfile.ZipFile(target_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)
            target_path.unlink()  # Remove the .zip file after extraction

    print("Wyscout dataset is ready.")

if __name__ == "__main__":
    ensure_wyscout_data()