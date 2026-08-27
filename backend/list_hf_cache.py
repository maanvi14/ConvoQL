import os

HF_CACHE = os.path.expanduser("~/.cache/huggingface")

def main():
    print(f"Recursively listing files in {HF_CACHE}...")
    for root, dirs, files in os.walk(HF_CACHE):
        for f in files:
            full_path = os.path.join(root, f)
            # Print only files larger than 1MB or interesting extensions
            size_mb = os.path.getsize(full_path) / (1024 * 1024)
            if size_mb > 1 or f.endswith(('.sqlite', '.db', '.zip', '.parquet')):
                print(f"  {f} ({size_mb:.2f} MB) at {full_path}")

if __name__ == "__main__":
    main()
