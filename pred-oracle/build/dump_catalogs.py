"""Dump Carver Feeds topics and categories catalog for Stage 1 analysis."""

import json
from pathlib import Path

from dotenv import load_dotenv
from carver_feeds import create_data_manager, get_client

# Load environment variables
load_dotenv()

# Initialize clients
dm = create_data_manager()
client = get_client()

# Create data directory if it doesn't exist
data_dir = Path(__file__).parent.parent / "data"
data_dir.mkdir(exist_ok=True)

# 1. Dump topics from DataManager
topics_df = dm.get_topics_df()
topics_records = topics_df.to_dict(orient="records")
with open(data_dir / "carver-topics.json", "w") as f:
    json.dump(topics_records, f, indent=2, default=str)

# 2. Dump topics with detailed info from client
topics_detailed = client.list_topics(details=True)
with open(data_dir / "carver-topics-detailed.json", "w") as f:
    json.dump(topics_detailed, f, indent=2, default=str)

# 3. Dump categories from DataManager
categories_df = dm.get_categories_df()
categories_records = categories_df.to_dict(orient="records")
with open(data_dir / "carver-categories.json", "w") as f:
    json.dump(categories_records, f, indent=2, default=str)

# Print summary to stdout
print("\n" + "=" * 70)
print("CARVER FEEDS CATALOG DUMP - STAGE 1 ANALYSIS")
print("=" * 70)

print(f"\nTOPICS: {len(topics_records)} records")
print(f"CATEGORIES: {len(categories_records)} records")

print("\nFirst 5 topic records (from DataManager):")
print("-" * 70)
for i, topic in enumerate(topics_records[:5], 1):
    print(f"{i}. {json.dumps(topic, indent=2, default=str)}")

print("\nFirst 3 category records (from DataManager):")
print("-" * 70)
for i, category in enumerate(categories_records[:3], 1):
    print(f"{i}. {json.dumps(category, indent=2, default=str)}")

print("\nRicher fields in list_topics(details=True):")
print("-" * 70)
if topics_detailed:
    first_detailed = topics_detailed[0]
    print(f"Keys: {list(first_detailed.keys())}")
    print(f"\nFirst record (sample):")
    print(json.dumps(first_detailed, indent=2, default=str)[:500] + "...")

print("\n" + "=" * 70)
print("Files written:")
print(f"  - {data_dir}/carver-topics.json")
print(f"  - {data_dir}/carver-topics-detailed.json")
print(f"  - {data_dir}/carver-categories.json")
print("=" * 70 + "\n")
