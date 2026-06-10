from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_RAW = BASE_DIR / "data" / "raw"
DATA_BRONZE = BASE_DIR / "data" / "bronze"
DATA_SILVER = BASE_DIR / "data" / "silver"
DATA_GOLD = BASE_DIR / "data" / "gold"
WAREHOUSE_PATH = BASE_DIR / "warehouse" / "casemix.duckdb"

for d in [DATA_RAW, DATA_BRONZE, DATA_SILVER, DATA_GOLD, WAREHOUSE_PATH.parent]:
    d.mkdir(parents=True, exist_ok=True)

IHACPA_BASE_URL = "https://www.ihacpa.gov.au"
IHACPA_NHCDC_PUBLIC_URL = f"{IHACPA_BASE_URL}/resources/national-hospital-cost-data-collection-public-sector-2023-24"
IHACPA_NHCDC_PRIVATE_URL = f"{IHACPA_BASE_URL}/sites/default/files/2025-09/national_hospital_cost_data_collection_private_sector_report_2022-23.pdf"

AIHW_BASE_URL = "https://www.aihw.gov.au"
AIHW_DRG_CUBES_URL = f"{AIHW_BASE_URL}/reports/hospitals/ar-drg-data-cubes"
AIHW_MYHOSPITALS_DOWNLOADS_URL = f"{AIHW_BASE_URL}/reports-data/myhospitals/content/data-downloads"
AIHW_MYHOSPITALS_API_BASE = "https://myhospitalsapi.aihw.gov.au/api/v1"

APRA_BASE_URL = "https://www.apra.gov.au"
APRA_PHI_QUARTERLY_URL = f"{APRA_BASE_URL}/quarterly-private-health-insurance-statistics"

NWAU_PRICE_2023_24 = 6124.0
NWAU_PRICE_2022_23 = 5890.0
NWAU_PRICE_2021_22 = 5643.0

SYNTHETIC_EPISODE_COUNT = 50000
RANDOM_SEED = 42

CONTRACT_SCENARIOS = {
    "drg_based_3pct": {"type": "drg", "indexation": 0.03},
    "drg_based_5pct": {"type": "drg", "indexation": 0.05},
    "per_diem_3pct": {"type": "per_diem", "indexation": 0.03, "daily_rate": 1200},
    "per_diem_5pct": {"type": "per_diem", "indexation": 0.05, "daily_rate": 1200},
}

FORECAST_HORIZON_QUARTERS = 4
FORECAST_CONFIDENCE = 0.95
