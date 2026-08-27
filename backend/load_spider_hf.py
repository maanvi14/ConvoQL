import os
from datasets import load_dataset
import shutil

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
SPIDER_DIR = os.path.join(BACKEND_DIR, "spider_data")
os.makedirs(SPIDER_DIR, exist_ok=True)

def main():
    print("Loading xlangai/spider dataset from HF...")
    try:
        ds = load_dataset("xlangai/spider")
        print("Dataset loaded successfully.")
        print(ds)
        
        # Let's inspect where HF cached the files
        # Specifically, we want the SQLite databases.
        # HF datasets downloads raw files and extracts them. Let's see if we can find them.
        import inspect
        import datasets
        print("HF Datasets cache dir:", datasets.config.HF_DATASETS_CACHE)
        
        # Let's write the validation split queries into a local dev.json
        validation_split = ds["validation"]
        dev_data = []
        for row in validation_split:
            # Check structure of each row
            dev_data.append({
                "question": row["question"],
                "query": row["query"],
                "db_id": row["db_id"]
            })
            
        dev_json_path = os.path.join(SPIDER_DIR, "dev.json")
        import json
        with open(dev_json_path, "w", encoding="utf-8") as f:
            json.dump(dev_data, f, indent=2, ensure_ascii=False)
        print(f"Wrote {len(dev_data)} validation queries to {dev_json_path}")
        
    except Exception as e:
        print(f"Failed to load dataset: {e}")

if __name__ == "__main__":
    main()
