import os
import json

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
SPIDER_DIR = os.path.join(BACKEND_DIR, "spider_data", "spider")
dev_json_path = os.path.join(SPIDER_DIR, "dev.json")

def main():
    if not os.path.exists(dev_json_path):
        print("dev.json not found.")
        return
        
    with open(dev_json_path, "r", encoding="utf-8") as f:
        dev_data = json.load(f)
        
    db_counts = {}
    for row in dev_data:
        db_id = row["db_id"]
        db_counts[db_id] = db_counts.get(db_id, 0) + 1
        
    target_dbs = ["concert_singer", "pets_1", "car_1", "flight_1"]
    total_target = 0
    print("Queries per database in dev.json:")
    for db, count in sorted(db_counts.items()):
        if db in target_dbs:
            print(f"  * {db}: {count}")
            total_target += count
        else:
            if count > 50: # only print major ones
                print(f"    {db}: {count}")
                
    print(f"Total target queries across {target_dbs}: {total_target}")

if __name__ == "__main__":
    main()
