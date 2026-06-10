from pathlib import Path
import sys
import time
import importlib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def run():
    start = time.time()
    print("=" * 70)
    print("CASEMIX REVENUE INTELLIGENCE — Master Ingestion Pipeline")
    print("=" * 70)
    results = {}

    for step, name, module in [
        ("1/3", "IHACPA NHCDC", "ingestion.download_ihacpa"),
        ("2/3", "AIHW DRG Cubes", "ingestion.download_aihw"),
        ("3/3", "APRA PHI Stats", "ingestion.download_apra"),
    ]:
        print(f"\n{'='*70}\nSTEP {step}: {name}\n{'='*70}")
        try:
            importlib.import_module(module).run()
            results[name] = "SUCCESS"
        except Exception as e:
            print(f"  [FAILED] {e}")
            results[name] = f"FAILED: {e}"

    elapsed = time.time() - start
    print(f"\n{'='*70}\nSUMMARY\n{'='*70}")
    for src, status in results.items():
        print(f"  {'✓' if status=='SUCCESS' else '✗'} {src}: {status}")
    print(f"  Elapsed: {elapsed:.1f}s")

if __name__ == "__main__":
    run()
