import httpx
from pathlib import Path
import sys
import json
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import AIHW_MYHOSPITALS_API_BASE, DATA_RAW

API_BASE = AIHW_MYHOSPITALS_API_BASE
OUTPUT_DIR = DATA_RAW / "aihw" / "myhospitals_api"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def get_client() -> httpx.Client:
    return httpx.Client(base_url=API_BASE, headers={"User-Agent": "CasemixRevenueIntelligence/1.0", "Accept": "application/json"}, timeout=30.0, follow_redirects=True)

def fetch_datasets(client): return client.get("/DataSets").json()
def fetch_measures(client): return client.get("/Measures").json()
def fetch_reporting_units(client, unit_type_id=None):
    params = {}
    if unit_type_id: params["reportingUnitTypeId"] = unit_type_id
    return client.get("/ReportingUnits", params=params).json()

def fetch_reported_measures(client, measure_id=None, reporting_unit_code=None, data_set_id=None):
    params = {}
    if measure_id: params["measureId"] = measure_id
    if reporting_unit_code: params["reportingUnitCode"] = reporting_unit_code
    if data_set_id: params["dataSetId"] = data_set_id
    return client.get("/ReportedMeasures", params=params).json()

def fetch_flat_data(client, reported_measure_id, page=1, page_size=1000):
    return client.get("/FlatDataExtracts", params={"reportedMeasureId": reported_measure_id, "page": page, "pageSize": page_size}).json()

def save_json(data, filename):
    path = OUTPUT_DIR / filename
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  [SAVED] {filename}")
    return path

def run():
    print("=" * 60); print("MyHospitals API — Fetching metadata..."); print("=" * 60)
    with get_client() as client:
        save_json(fetch_datasets(client), "datasets.json")
        save_json(fetch_measures(client), "measures.json")
        save_json(fetch_reporting_units(client), "reporting_units.json")

if __name__ == "__main__":
    run()
