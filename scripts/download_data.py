"""Download the ULB credit-card fraud dataset."""

from __future__ import annotations

import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from config import CREDITCARD_DIR, CREDITCARD_PATH  # noqa: E402

TF_URL = "https://storage.googleapis.com/download.tensorflow.org/data/creditcard.csv"


def download() -> Path:
    CREDITCARD_DIR.mkdir(parents=True, exist_ok=True)
    if CREDITCARD_PATH.exists() and CREDITCARD_PATH.stat().st_size > 1_000_000:
        print(f"Already present: {CREDITCARD_PATH}")
        return CREDITCARD_PATH

    try:
        import kagglehub

        print("Trying kagglehub: mlg-ulb/creditcardfraud")
        cache = Path(kagglehub.dataset_download("mlg-ulb/creditcardfraud"))
        csvs = list(cache.rglob("creditcard.csv"))
        if csvs:
            shutil.copy(csvs[0], CREDITCARD_PATH)
            print(f"Copied from kagglehub → {CREDITCARD_PATH}")
            return CREDITCARD_PATH
    except Exception as exc:  # noqa: BLE001
        print(f"kagglehub unavailable ({exc}); falling back to public mirror")

    print(f"Downloading {TF_URL}")
    try:
        import requests

        resp = requests.get(TF_URL, timeout=180)
        resp.raise_for_status()
        CREDITCARD_PATH.write_bytes(resp.content)
        print(f"Saved {CREDITCARD_PATH} ({CREDITCARD_PATH.stat().st_size:,} bytes)")
        return CREDITCARD_PATH
    except Exception as exc:  # noqa: BLE001
        print(f"Download failed ({exc}); writing a schema-compatible synthetic table")

    from data_loader import synthesize_creditcard

    df = synthesize_creditcard()
    df.to_csv(CREDITCARD_PATH, index=False)
    print(f"Saved synthetic {CREDITCARD_PATH} ({CREDITCARD_PATH.stat().st_size:,} bytes)")
    return CREDITCARD_PATH


if __name__ == "__main__":
    download()
