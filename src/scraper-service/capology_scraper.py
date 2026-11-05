import json
import os
import random
import time
import pandas as pd
import undetected_chromedriver as uc
import re
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Resolve paths: <repo_root>/data/capology
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = REPO_ROOT / "data" / "capology"
RAW_CLUBS_DIR = OUTPUT_DIR / "clubs_2017_2018"
DISCOVERED_TEAMS_FILE = OUTPUT_DIR / "discovered_clubs_2017_2018.json"

# Capology League Payroll Pages for the 2017/18 season
LEAGUE_PAYROLL_URLS_2017_18 = {
    "Premier League": "https://www.capology.com/uk/premier-league/payrolls/2017-2018/",
    "La Liga": "https://www.capology.com/es/la-liga/payrolls/2017-2018/",
    "Serie A": "https://www.capology.com/it/serie-a/payrolls/2017-2018/",
    "Bundesliga": "https://www.capology.com/de/1-bundesliga/payrolls/2017-2018/",
    "Ligue 1": "https://www.capology.com/fr/ligue-1/payrolls/2017-2018/",
}

# =====================================================================
# Scraper Utilities
# =====================================================================

def get_installed_chrome_major_version() -> int | None:
    """Detects the major version of Google Chrome installed on Windows."""
    try:
        # Query Windows Registry for Chrome version
        cmd = r'reg query "HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon" /v version'
        output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
        match = re.search(r"version\s+REG_SZ\s+(\d+)\.", output)
        if match:
            return int(match.group(1))
    except Exception:
        pass

    try:
        # Fallback to HKLM
        cmd = r'reg query "HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Google\Update\Clients\{8A69D345-D564-463c-AFF1-A69D9E530F96}" /v pv'
        output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
        match = re.search(r"pv\s+REG_SZ\s+(\d+)\.", output)
        if match:
            return int(match.group(1))
    except Exception:
        pass

    return None

def create_driver():
    """
    Initializes undetected Chrome browser to bypass Cloudflare challenges.
    """
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    chrome_bin = os.getenv("CHROME_BIN")
    chromedriver_path = os.getenv("CHROMEDRIVER_PATH")
    major_version = get_installed_chrome_major_version() or 156

    if chrome_bin:
        options.binary_location = chrome_bin
        return uc.Chrome(
            options=options,
            driver_executable_path=chromedriver_path,
            version_main=major_version,
            headless=False,  # Xvfb provides a virtual display in Docker so Cloudflare doesn't block headless
        )

    return uc.Chrome(options=options, version_main=major_version)

# =====================================================================
# Helpers for Club Discovery and Salary Scraping
# =====================================================================

def get_league_club_slugs(driver, league_name: str, payroll_url: str) -> list[str]:
    """
    Visits the league payroll page and dynamically extracts all club slugs.
    """
    print(f"\n[DISCOVERY] Loading league page for {league_name}: {payroll_url}")
    driver.get(payroll_url)

    try:
        # Wait up to 20s for Cloudflare and DOM table to render
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table#table tbody tr"))
        )
    except Exception:
        print(f"[ERROR] Timed out waiting for table on {payroll_url}.")
        print(f"[WARNING] Proceeding to parse available DOM for {league_name}...")

    soup = BeautifulSoup(driver.page_source, "html.parser")
    table = soup.select_one("table#table")
    if not table:
        print(f"[ERROR] Could not find the payrolls table for {league_name}.")
        return []

    # Find all anchor tags pointing to /club/<slug>/
    slugs = []
    for a in table.find_all("a", href=True):
        match = re.search(r"/club/([^/]+)/", a["href"])
        if match:
            slug = match.group(1).lower()
            if slug not in slugs:
                slugs.append(slug)

    print(f"[OK] Dynamically discovered {len(slugs)} clubs for {league_name}: {', '.join(slugs[:5])}...")
    return slugs

def discover_all_clubs(driver) -> dict[str, list[str]]:
    """
    Loads clubs from local cache if present, otherwise scrapes the 5 league pages.
    """
    if DISCOVERED_TEAMS_FILE.exists():
        print(f"[CACHE HIT] Loaded discovered clubs from {DISCOVERED_TEAMS_FILE.name}")
        with open(DISCOVERED_TEAMS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    discovered = {}
    for league, url in LEAGUE_PAYROLL_URLS_2017_18.items():
        slugs = get_league_club_slugs(driver, league, url)
        if slugs:
            discovered[league] = slugs

    # Save to disk so we only discover once
    with open(DISCOVERED_TEAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(discovered, f, ensure_ascii=False, indent=2)

    return discovered

def fetch_capology_club_salaries(driver, club_slug: str, league_name: str, season: str = "2017-2018"):
    """
    Scrapes salary table for one club. Checks local JSON cache first.
    """
    club_cache_file = RAW_CLUBS_DIR / f"{club_slug}.json"
    
    # Skip network request if already cached locally
    if club_cache_file.exists():
        print(f"[CACHE HIT] Loaded {club_slug} ({league_name}) from disk.")
        with open(club_cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    # Polite jitter delay between requests
    time.sleep(random.uniform(1.0, 3.0))
    
    url = f"https://www.capology.com/club/{club_slug}/salaries/{season}/"
    print(f"[FETCHING] {club_slug} ({league_name}) -> {url}")
    driver.get(url)

    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table#table tbody tr"))
        )
    except Exception:
        print(f"[ERROR] Timed out waiting for table on {club_slug}.")
        return []

    soup = BeautifulSoup(driver.page_source, "html.parser")
    table = soup.select_one("table#table")
    if not table:
        print(f"[ERROR] Could not find the salary table for {club_slug}.")
        return []

    tbody = table.select_one("tbody")
    rows = tbody.find_all("tr") if tbody else []

    squad_salaries = []
    for row in rows:
        columns = row.find_all("td")
        if len(columns) > 4:
            squad_salaries.append({
                "league": league_name,
                "club": club_slug,
                "season": season,
                "player": columns[0].get_text(strip=True),
                "weekly_wage": columns[2].get_text(strip=True),
                "annual_wage": columns[3].get_text(strip=True),
            })

    print(f"[OK] {club_slug}: extracted {len(squad_salaries)} player contracts.")

    # Persist individual club result immediately
    if squad_salaries:
        with open(club_cache_file, "w", encoding="utf-8") as f:
            json.dump(squad_salaries, f, ensure_ascii=False, indent=2)

    return squad_salaries

# =====================================================================
# Main Pipeline: Discover Clubs, Fetch Salaries, Save Dataset
# =====================================================================

def scrape_all_top5_leagues(season: str = "2017-2018"):
    """
    Main pipeline to scrape salary data for all clubs in the Top 5 leagues.
    """
    # Ensure destination directories exist
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_CLUBS_DIR.mkdir(parents=True, exist_ok=True)

    all_data = []
    failed_clubs = []
    driver = create_driver()

    try:
        # Discover all clubs across the 5 leagues (or load from cache)
        league_clubs_map = discover_all_clubs(driver)
        total_clubs = sum(len(clubs) for clubs in league_clubs_map.values())
        processed_count = 0

        # Scrape each discovered club
        for league, clubs in league_clubs_map.items():
            print(f"\n{'='*20} Scraping {league} ({len(clubs)} clubs) {'='*20}")
            for club in clubs:
                processed_count += 1
                print(f"[{processed_count}/{total_clubs}] Processing {club}...")

                club_data = fetch_capology_club_salaries(driver, club, league, season)
                if club_data:
                    all_data.extend(club_data)
                else:
                    failed_clubs.append((league, club))

    finally:
        # Prevent the Windows WinError 6 double-quit crash on GC
        if hasattr(driver, "__del__"):
            setattr(driver.__class__, "__del__", lambda self: None)
        driver.quit()

    # Save consolidated dataset
    csv_file = OUTPUT_DIR / f"capology_salaries_{season.replace('-', '_')}.csv"
    json_file = OUTPUT_DIR / f"capology_salaries_{season.replace('-', '_')}.json"

    df = pd.DataFrame(all_data)
    df.to_csv(csv_file, index=False, encoding="utf-8-sig")

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"[DONE] Successfully saved {len(all_data)} player wage records.")
    print(f"CSV file:  {csv_file}")
    print(f"JSON file: {json_file}")

    if failed_clubs:
        print(f"\n[WARNING] {len(failed_clubs)} clubs could not be loaded:")
        for league, club in failed_clubs:
            print(f"  - {league}: {club}")

if __name__ == "__main__":
    scrape_all_top5_leagues(season="2017-2018")