import os
import urllib.request
import json

SPIDER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spider_data")
os.makedirs(SPIDER_DIR, exist_ok=True)
os.makedirs(os.path.join(SPIDER_DIR, "databases"), exist_ok=True)

FILES = {
    "dev.json": "https://raw.githubusercontent.com/taoyds/spider/master/dev.json",
    "tables.json": "https://raw.githubusercontent.com/taoyds/spider/master/tables.json"
}

DATABASES = {
    "concert_singer": "https://github.com/taoyds/spider/raw/master/database/concert_singer/concert_singer.sqlite",
    "pets_1": "https://github.com/taoyds/spider/raw/master/database/pets_1/pets_1.sqlite",
    "car_1": "https://github.com/taoyds/spider/raw/master/database/car_1/car_1.sqlite",
    "flight_1": "https://github.com/taoyds/spider/raw/master/database/flight_1/flight_1.sqlite"
}

def download_file(url, dest):
    print(f"Downloading {url} to {dest}...")
    try:
        urllib.request.urlretrieve(url, dest)
        print("Success.")
    except Exception as e:
        print(f"Failed to download: {e}")

def main():
    # Download JSON metadata
    for filename, url in FILES.items():
        dest = os.path.join(SPIDER_DIR, filename)
        if not os.path.exists(dest):
            download_file(url, dest)
        else:
            print(f"{filename} already exists, skipping.")

    # Download database files
    for db_id, url in DATABASES.items():
        db_dir = os.path.join(SPIDER_DIR, "databases", db_id)
        os.makedirs(db_dir, exist_ok=True)
        dest = os.path.join(db_dir, f"{db_id}.sqlite")
        if not os.path.exists(dest):
            download_file(url, dest)
        else:
            print(f"{db_id}.sqlite already exists, skipping.")

    print("Spider subset download complete.")

if __name__ == "__main__":
    main()
