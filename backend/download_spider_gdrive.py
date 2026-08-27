import os
import requests
import zipfile

SPIDER_DRIVE_ID = "1TqleXec_OykOYFREKKtschzY29dUcVAQ"
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
SPIDER_DIR = os.path.join(BACKEND_DIR, "spider_data")

def get_confirm_token(response):
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            return value
    return None

def save_response_content(response, destination):
    CHUNK_SIZE = 32768
    with open(destination, "wb") as f:
        for chunk in response.iter_content(CHUNK_SIZE):
            if chunk:
                f.write(chunk)

def download_file_from_google_drive(id, destination):
    url = "https://docs.google.com/uc?export=download"
    session = requests.Session()

    print("Sending request to Google Drive...")
    response = session.get(url, params={'id': id}, stream=True, verify=False)
    html = response.text
    
    import re
    uuid_match = re.search(r'name="uuid"\s+value="([^"]+)"', html)
    if uuid_match:
        uuid = uuid_match.group(1)
        print(f"Parsed uuid from warning page: {uuid}")
        download_url = "https://drive.usercontent.com/download"
        params = {
            'id': id,
            'export': 'download',
            'confirm': 't',
            'uuid': uuid
        }
        print("Downloading raw file from drive.usercontent.com...")
        response = session.get(download_url, params=params, stream=True, verify=False)
    else:
        print("No uuid found, attempting direct download with confirm=t...")
        params = {'id': id, 'confirm': 't'}
        response = session.get(url, params=params, stream=True, verify=False)
        
    print(f"Saving content to {destination}...")
    save_response_content(response, destination)
    print("Download completed.")

def main():
    os.makedirs(SPIDER_DIR, exist_ok=True)
    zip_path = os.path.join(SPIDER_DIR, "spider.zip")
    
    if not os.path.exists(zip_path):
        print(f"Downloading Spider dataset zip (ID: {SPIDER_DRIVE_ID}) from Google Drive...")
        try:
            download_file_from_google_drive(SPIDER_DRIVE_ID, zip_path)
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
    main()
