import requests
from bs4 import BeautifulSoup
from pathlib import Path
import sys
import re
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import AIHW_DRG_CUBES_URL, AIHW_MYHOSPITALS_DOWNLOADS_URL, DATA_RAW

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "CasemixRevenueIntelligence/1.0 (research; contact@example.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})
TARGET_EXTENSIONS = [".xlsx", ".xlsm", ".xls", ".csv"]

def find_download_links(page_url: str, keyword_filter: list[str] | None = None) -> list[dict]:
    resp = SESSION.get(page_url, timeout=60)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    links = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]; text = a_tag.get_text(strip=True)
        if any(href.lower().endswith(ext) for ext in TARGET_EXTENSIONS):
            if not href.startswith("http"):
                href = f"https://www.aihw.gov.au{href}" if href.startswith("/") else f"https://www.aihw.gov.au/{href}"
            if keyword_filter:
                combined = (text + " " + href).lower()
                if not any(kw.lower() in combined for kw in keyword_filter): continue
            links.append({"url": href, "label": text})
    return links

def download_file(url: str, dest_dir: Path, label: str = "") -> Path:
    filename = url.split("/")[-1]
    filename = re.sub(r"[?#].*$", "", filename)
    if not filename: filename = "aihw_download"
    dest_path = dest_dir / filename
    if dest_path.exists():
        print(f"  [SKIP] Already exists: {filename}"); return dest_path
    print(f"  [GET] {label or filename}...")
    resp = SESSION.get(url, timeout=120, stream=True)
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192): f.write(chunk)
    size_mb = dest_path.stat().st_size / (1024 * 1024)
    print(f"  [OK] {filename} ({size_mb:.1f} MB)"); time.sleep(1)
    return dest_path

def download_drg_cubes() -> list[Path]:
    aihw_dir = DATA_RAW / "aihw"; aihw_dir.mkdir(parents=True, exist_ok=True)
    print("=" * 60); print("AIHW — Scanning AR-DRG data cubes page..."); print("=" * 60)
    all_links = find_download_links(AIHW_DRG_CUBES_URL, keyword_filter=["ar-drg", "drg", "data cube", "separation"])
    if not all_links:
        all_links = find_download_links(AIHW_DRG_CUBES_URL)
    print(f"  Found {len(all_links)} relevant files.")
    downloaded = []
    for link in all_links:
        try: downloaded.append(download_file(link["url"], aihw_dir, link["label"]))
        except Exception as e: print(f"  [ERROR] Failed: {e}")
    return downloaded

def download_myhospitals_data() -> list[Path]:
    aihw_dir = DATA_RAW / "aihw" / "myhospitals"; aihw_dir.mkdir(parents=True, exist_ok=True)
    print("=" * 60); print("AIHW — Scanning MyHospitals data downloads..."); print("=" * 60)
    all_links = find_download_links(AIHW_MYHOSPITALS_DOWNLOADS_URL, keyword_filter=["admitted patient", "elective surgery", "emergency department"])
    if not all_links: all_links = find_download_links(AIHW_MYHOSPITALS_DOWNLOADS_URL)
    downloaded = []
    for link in all_links:
        try: downloaded.append(download_file(link["url"], aihw_dir, link["label"]))
        except Exception as e: print(f"  [ERROR] Failed: {e}")
    return downloaded

def run():
    print("Starting AIHW ingestion...")
    drg_files = download_drg_cubes()
    myhospitals_files = download_myhospitals_data()
    print(f"\nAIHW ingestion complete: {len(drg_files)} DRG cube files, {len(myhospitals_files)} MyHospitals files.")

if __name__ == "__main__":
    run()
