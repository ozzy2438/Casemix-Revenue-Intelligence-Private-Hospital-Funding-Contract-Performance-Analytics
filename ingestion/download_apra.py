import requests
from bs4 import BeautifulSoup
from pathlib import Path
import sys
import re
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import APRA_PHI_QUARTERLY_URL, DATA_RAW

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
                href = f"https://www.apra.gov.au{href}" if href.startswith("/") else f"https://www.apra.gov.au/{href}"
            if keyword_filter:
                combined = (text + " " + href).lower()
                if not any(kw.lower() in combined for kw in keyword_filter): continue
            links.append({"url": href, "label": text})
    return links

def download_file(url: str, dest_dir: Path, label: str = "") -> Path:
    filename = url.split("/")[-1]
    filename = re.sub(r"[?#].*$", "", filename)
    if not filename: filename = "apra_download"
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

def download_phi_statistics() -> list[Path]:
    apra_dir = DATA_RAW / "apra"; apra_dir.mkdir(parents=True, exist_ok=True)
    print("=" * 60); print("APRA — Scanning Quarterly PHI Statistics..."); print("=" * 60)
    all_links = find_download_links(APRA_PHI_QUARTERLY_URL, keyword_filter=["private health insurance", "phi", "hospital treatment", "benefit", "membership"])
    if not all_links: all_links = find_download_links(APRA_PHI_QUARTERLY_URL)
    downloaded = []
    for link in all_links:
        try: downloaded.append(download_file(link["url"], apra_dir, link["label"]))
        except Exception as e: print(f"  [ERROR] Failed: {e}")
    return downloaded

def run():
    print("Starting APRA ingestion...")
    phi_files = download_phi_statistics()
    print(f"\nAPRA ingestion complete: {len(phi_files)} PHI statistics files.")

if __name__ == "__main__":
    run()
