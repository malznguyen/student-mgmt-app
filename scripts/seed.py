"""Load sample data into the MongoDB university database."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
ENV_PATH = BACKEND_DIR / ".env"
SEED_PATH = Path(__file__).resolve().parent / "seed.json"


def load_env() -> None:
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH)


def read_seed_file() -> Dict[str, List[Dict[str, Any]]]:
    with SEED_PATH.open("r", encoding="utf-8") as seed_file:
        data = json.load(seed_file)
    if not isinstance(data, dict):
        raise ValueError("Seed file must contain an object of collections")
    return data


def main() -> None:
    load_env()
    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise RuntimeError("MONGODB_URI is not set in backend/.env")

    client = MongoClient(uri)
    database = client["university"]

    seed_data = read_seed_file()

    for collection_name, documents in seed_data.items():
        if not isinstance(documents, list):
            raise ValueError(f"Seed data for collection '{collection_name}' must be a list")

        collection = database[collection_name]
        collection.delete_many({})
        if documents:
            collection.insert_many(documents)

        print(f"Loaded {len(documents)} document(s) into '{collection_name}' collection")

    print("Seeding complete for database 'university'.")


if __name__ == "__main__":
    main()
