from __future__ import annotations

import json
import sys
from pathlib import Path

from pymongo import MongoClient

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.config import settings  # noqa: E402


def load_seed_data(seed_path: Path) -> dict:
    with seed_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def apply_seed(client: MongoClient, data: dict) -> None:
    db = client[settings.mongodb_db_name]
    for collection_name, documents in data.items():
        collection = db[collection_name]
        collection.delete_many({})
        if documents:
            collection.insert_many(documents)


def main() -> None:
    seed_path = Path(__file__).with_name("seed.json")
    data = load_seed_data(seed_path)
    client = MongoClient(settings.mongodb_uri)
    apply_seed(client, data)
    print(f"Seeded {settings.mongodb_db_name} database with {len(data)} collections.")


if __name__ == "__main__":
    main()
