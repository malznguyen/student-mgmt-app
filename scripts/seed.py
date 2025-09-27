import json, os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join("backend",".env"))
uri = os.getenv("MONGODB_URI","mongodb://localhost:27017/university")
client = MongoClient(uri)
db_name = uri.rsplit("/",1)[-1].split("?",1)[0] if "/" in uri else "university"
db = client[db_name]

with open(os.path.join("scripts","seed.json"), "r", encoding="utf-8") as f:
    data = json.load(f)

for coll, docs in data.items():
    db[coll].delete_many({})
    if docs: db[coll].insert_many(docs)

print("Seed OK ->", db_name)
