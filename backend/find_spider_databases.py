import os
import glob
import zipfile

HF_CACHE = os.path.expanduser("~/.cache/huggingface")

def main():
    print(f"Searching for Spider databases/zips in HuggingFace cache: {HF_CACHE}...")
    
    # 1. Search for SQLite files in HF cache
    sqlite_files = glob.glob(os.path.join(HF_CACHE, "**", "*.sqlite"), recursive=True)
    sqlite_files += glob.glob(os.path.join(HF_CACHE, "**", "*.db"), recursive=True)
    
    if sqlite_files:
        print(f"Found {len(sqlite_files)} database files:")
        for f in sqlite_files[:10]:
            print("  -", f)
        return

    # 2. Search for zip files in HF cache
    zip_files = glob.glob(os.path.join(HF_CACHE, "**", "*.zip"), recursive=True)
    print(f"Found {len(zip_files)} zip files:")
    for f in zip_files:
        print("  -", f)
        # Check if zip contains 'database' or 'sqlite'
        try:
            with zipfile.ZipFile(f, 'r') as zip_ref:
                names = zip_ref.namelist()
                has_sqlite = any(".sqlite" in n for n in names)
                print(f"    Contains SQLite: {has_sqlite} (size: {len(names)} files)")
                if has_sqlite:
                    # Let's extract it to C:\Users\maanv\ConvoQL\backend\spider_data
                    dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spider_data")
                    print(f"    Extracting to {dest}...")
                    zip_ref.extractall(dest)
                    print("    Extraction completed.")
        except Exception as e:
            print("    Error reading zip:", e)

if __name__ == "__main__":
    main()
