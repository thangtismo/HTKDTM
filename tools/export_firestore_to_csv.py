"""
Export Firestore collection to CSV.

- Uses Firebase Admin SDK (service account JSON).
- Writes a CSV file with a stable header from document keys.
- Converts datetime-like values to ISO strings.

Usage:
    python tools/export_firestore_to_csv.py --collection seasons --out exports/seasons.csv
"""

from __future__ import annotations

import argparse
import csv
import os
from datetime import datetime
from typing import Any, Dict, List, Set

import firebase_admin
from firebase_admin import credentials, firestore


def init_firestore(service_account_path: str) -> firestore.Client:
    """Initialize Firebase Admin SDK once and return a Firestore client."""
    if not os.path.isfile(service_account_path):
        raise FileNotFoundError(
            f"Service account JSON not found: {service_account_path}\n"
            f"Tip: Put firebase_config.json next to app.py (project root)."
        )

    # Avoid: ValueError: The default Firebase app already exists
    if not firebase_admin._apps:
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)

    return firestore.client()


def normalize_value(v: Any) -> Any:
    """Normalize Firestore values to CSV-friendly format."""
    # Datetime / Firestore timestamp-like
    if isinstance(v, datetime):
        return v.isoformat()

    # Some Firestore timestamp objects have isoformat()
    if hasattr(v, "isoformat"):
        try:
            return v.isoformat()
        except Exception:
            pass

    return v


def export_collection_to_csv(
    db: firestore.Client,
    collection_name: str,
    out_csv_path: str,
) -> str:
    """Export one Firestore collection to CSV and return output path."""
    out_dir = os.path.dirname(out_csv_path) or "."
    os.makedirs(out_dir, exist_ok=True)

    try:
        docs = db.collection(collection_name).stream()
    except Exception as e:
        raise RuntimeError(f"Failed to stream collection '{collection_name}': {e}") from e

    rows: List[Dict[str, Any]] = []
    keys: Set[str] = set()

    try:
        for doc in docs:
            data = doc.to_dict() or {}
            data["_id"] = doc.id  # keep document id
            normalized = {k: normalize_value(v) for k, v in data.items()}
            rows.append(normalized)
            keys.update(normalized.keys())
    except Exception as e:
        raise RuntimeError(f"Failed while reading documents: {e}") from e

    if not rows:
        raise ValueError(f"No documents found in collection '{collection_name}'.")

    fieldnames = sorted(keys)

    try:
        with open(out_csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
    except Exception as e:
        raise RuntimeError(f"Failed to write CSV '{out_csv_path}': {e}") from e

    return out_csv_path


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--service-account", default="firebase_config.json", help="Path to service account JSON")
    parser.add_argument("--collection", required=True, help="Firestore collection name, e.g. seasons")
    parser.add_argument("--out", default="exports/seasons.csv", help="Output CSV path")
    args = parser.parse_args()

    db = init_firestore(args.service_account)
    out = export_collection_to_csv(db, args.collection, args.out)
    print(f"Exported CSV: {out}")


if __name__ == "__main__":
    main()
