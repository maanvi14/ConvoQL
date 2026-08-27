import os
import urllib.request
import zipfile

SPIDER_ZIP_URL = "https://huggingface.co/datasets/xlangai/spider/resolve/main/spider.zip"
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
SPIDER_DIR = os.path.join(BACKEND_DIR, "spider_data")

def download_and_extract():
    os.makedirs(SPIDER_DIR, exist_ok=True)
    zip_path = os.path.join(SPIDER_DIR, "spider.zip")
    
    if not os.path.exists(zip_path):
        print(f"Downloading spider.zip from {SPIDER_ZIP_URL}...")
        try:
            req = urllib.request.Request(
                SPIDER_ZIP_URL, 
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
                out_file.write(response.read())
            print("Download successful.")
        except Exception as e:
            print(f"Download failed: {e}")
            return
    else:
        print("spider.zip already exists.")
            
    print("Extracting spider.zip...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # We want to extract it inside SPIDER_DIR
            zip_ref.extractall(SPIDER_DIR)
        print("Extraction successful.")
    except Exception as e:
        print(f"Extraction failed: {e}")

if __name__ == "__main__":
    download_and_extract()
