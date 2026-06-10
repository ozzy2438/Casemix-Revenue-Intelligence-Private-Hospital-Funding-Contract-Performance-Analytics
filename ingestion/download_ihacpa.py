import requests
from bs4 import BeautifulSoup
from pathlib import Path
import sys
import re
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import IHACPA_NHCDC_PUBLIC_URL, IHACPA_NHCDC_PRIVATE_URL, DATA_RAW

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "CasemixRevenueIntelligence/1.0 (research; contact@example.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})
TARGET_EXTENSIONS = [".xlsx", ".xlsm", ".xls", ".csv", ".pdf"]

def find_download_links(page_url: str) -> list[dict]:
    resp = SESSION.get(page_url, timeout=60)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    links = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        text = a_tag.get_text(strip=True)
        if any(href.lower().endswith(ext) for ext in TARGET_EXTENSIONS):
            if not href.startswith("http"):
                href = f"https://www.ihacpa.gov.au{href}" if href.startswith("/") else f"https://www.ihacpa.gov.au/{href}"
            links.append({"url": href, "label": text})
    return links

def download_file(url: str, dest_dir: Path, label: str = "") -> Path:
    filename = url.split("/")[-1]
    filename = re.sub(r"[?#].*$", "", filename)
    if not filename: filename = "ihacpa_download"
    dest_path = dest_dir / filename
    if dest_path.exists():
        print(f"  [SKIP] Already exists: {filename}")
        return dest_path
    print(f"  [GET] {label or filename}...")
    resp = SESSION.get(url, timeout=120, stream=True)
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192): f.write(chunk)
    size_mb = dest_path.stat().st_size / (1024 * 1024)
    print(f"  [OK] {filename} ({size_mb:.1f} MB)")
    time.sleep(1)
    return dest_path

def download_nhcpd_cost_weights() -> list[Path]:
    ihacpa_dir = DATA_RAW / "ihacpa"
    ihacpa_dir.mkdir(parents=True, exist_ok=True)
    print("=" * 60)
    print("IHACPA NHCDC — Scanning public sector resources page...")
    print("=" * 60)
    all_links = find_download_links(IHACPA_NHCDC_PUBLIC_URL)
    cost_weight_links = [l for l in all_links if any(kw in l["label"].lower() or kw in l["url"].lower() for kw in ["cost weight", "cost_weight", "appendix", "ar-drg"])]
    if not cost_weight_links:
        print("  [WARN] No cost weight links found; downloading all spreadsheet links.")
        cost_weight_links = [l for l in all_links if any(l["url"].lower().endswith(ext) for ext in [".xlsx", ".xlsm", ".xls"])]
    print(f"  Found {len(cost_weight_links)} relevant files.")
    downloaded = []
    for link in cost_weight_links:
        try: downloaded.append(download_file(link["url"], ihacpa_dir, link["label"]))
        except Exception as e: print(f"  [ERROR] Failed: {e}")
    return downloaded

def download_nhcpd_private_report() -> Path | None:
    ihacpa_dir = DATA_RAW / "ihacpa"
    ihacpa_dir.mkdir(parents=True, exist_ok=True)
    print("=" * 60)
    print("IHACPA NHCDC — Private Sector Report 2022-23...")
    print("=" * 60)
    try: return download_file(IHACPA_NHCDC_PRIVATE_URL, ihacpa_dir, "NHCDC Private Sector Report 2022-23")
    except Exception as e: print(f"  [ERROR] Failed: {e}"); return None

def run():
    print("Starting IHACPA ingestion...")
    public_files = download_nhcpd_cost_weights()
    private_file = download_nhcpd_private_report()
    print(f"\nIHACPA ingestion complete: {len(public_files)} public sector files, {1 if private_file else 0} private sector file.")

if __name__ == "__main__":
    run()
