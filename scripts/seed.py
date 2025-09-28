"""Seed helper that loads sample documents into MongoDB."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from backend.src.config import ConfigError, get_db_name, get_mongo_uri

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
    try:
        uri = get_mongo_uri()
        db_name = get_db_name()
    except ConfigError as exc:  # pragma: no cover - simple CLI utility
        print(f"Configuration error: {exc}")
        raise SystemExit(1)

    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    database = client[db_name]

    try:
        seed_data = read_seed_file()

        for collection_name, documents in seed_data.items():
            if not isinstance(documents, list):
                raise ValueError(
                    f"Seed data for collection '{collection_name}' must be a list"
                )

            collection = database[collection_name]
            collection.delete_many({})
            if documents:
                collection.insert_many(documents)

            print(
                f"Loaded {len(documents)} document(s) into '{collection_name}' collection"
            )

        print(f"Seeding complete for database '{db_name}'.")
    except PyMongoError as exc:  # pragma: no cover - requires Mongo connection
        print(f"MongoDB error: {exc}")
        raise SystemExit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
