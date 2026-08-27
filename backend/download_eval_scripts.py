import os
import urllib.request

SPIDER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spider_data", "spider")
os.makedirs(SPIDER_DIR, exist_ok=True)

FILES = {
    "evaluation.py": "https://raw.githubusercontent.com/taoyds/spider/master/evaluation.py",
    "process_sql.py": "https://raw.githubusercontent.com/taoyds/spider/master/process_sql.py"
}

def main():
    for name, url in FILES.items():
        dest = os.path.join(SPIDER_DIR, name)
        print(f"Downloading {url} to {dest}...")
        try:
            # Bypass SSL certificate verification if needed
            import ssl
            context = ssl._create_unverified_context()
            with urllib.request.urlopen(url, context=context) as response, open(dest, 'wb') as out_file:
                out_file.write(response.read())
            print("Download successful.")
        except Exception as e:
            print(f"Failed to download: {e}")

if __name__ == "__main__":
    main()
