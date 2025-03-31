"""
PDF Scraper and Google Drive Sync Script

This script:
1. Fetches a sitemap containing page URLs.
2. Visits each URL and extracts PDF links.
3. Downloads each PDF to a local folder.
4. Uploads the PDFs to a designated Google Drive folder.
5. Deletes files from Drive that are no longer found on the website.

This script is designed for daily automated runs and should be hosted on a scheduled server or container environment.

Setup requirements:
- A Google Cloud project with the Drive API enabled.
- OAuth 2.0 Client credentials (`credentials.json`) downloaded.
- First-time interactive auth run (token is cached).
"""

import os
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import mimetypes
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

# === CONFIGURATION ===
SITEMAP_URL = "https://cirslinger.github.io/CepheidSitemap/sitemap.xml"
LOCAL_SAVE_DIR = "./downloads"  # Temporary local storage for PDF files
CREDENTIALS_PATH = "credentials.json"  # OAuth client secrets (download from Google Cloud Console)
TOKEN_PATH = "token.pickle"  # Cached auth tokens after first login
DRIVE_FOLDER_NAME = "Cepheid PDFs"  # Folder in Google Drive to sync files to

# === Setup local storage ===
os.makedirs(LOCAL_SAVE_DIR, exist_ok=True)

# === Step 1: Extract en-US URLs from sitemap ===
def get_sitemap_urls(sitemap_url):
    response = requests.get(sitemap_url)
    if response.status_code != 200:
        print(f"Failed to fetch sitemap: {response.status_code}")
        return []
    root = ET.fromstring(response.content)
    urls = [elem.text for elem in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    return [url for url in urls if "en-US" in url]

# === Step 2: Identify if a link is a PDF ===
def is_pdf_url(href, base_url):
    full_url = urljoin(base_url, href)
    if ".pdf" in full_url.lower():
        return True
    guessed_type, _ = mimetypes.guess_type(full_url)
    return guessed_type == "application/pdf"

# === Step 3: Scrape each page for PDF links ===
def find_pdf_links(page_url):
    try:
        response = requests.get(page_url)
        if response.status_code != 200:
            print(f"Failed to access {page_url}")
            return []
        soup = BeautifulSoup(response.text, "html.parser")
        pdf_links = [
            urljoin(page_url, a["href"])
            for a in soup.find_all("a", href=True)
            if is_pdf_url(a["href"], page_url)
        ]
        for tag in soup.find_all(["iframe", "embed"], src=True):
            if is_pdf_url(tag["src"], page_url):
                pdf_links.append(urljoin(page_url, tag["src"]))
        return list(set(pdf_links))
    except Exception as e:
        print(f"Error processing {page_url}: {e}")
        return []

# === Step 4: Authenticate to Google Drive ===
def authenticate_drive():
    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "wb") as token:
            pickle.dump(creds, token)
    return build("drive", "v3", credentials=creds)

# === Step 5: Create or locate the target Drive folder ===
def get_or_create_folder(service, folder_name):
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
    results = service.files().list(q=query, spaces='drive', fields="files(id, name)").execute()
    items = results.get("files", [])
    if items:
        return items[0]['id']  # Folder already exists
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    folder = service.files().create(body=file_metadata, fields='id').execute()
    return folder.get('id')

# === Step 6: List existing files in the Drive folder ===
def list_files_in_folder(service, folder_id):
    query = f"'{folder_id}' in parents and trashed=false"
    files = []
    page_token = None
    while True:
        response = service.files().list(q=query, spaces='drive', fields="nextPageToken, files(id, name)", pageToken=page_token).execute()
        files.extend(response.get('files', []))
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break
    return files

# === Step 7: Upload PDF to Google Drive folder ===
def upload_to_drive(service, filepath, folder_id):
    file_metadata = {'name': os.path.basename(filepath), 'parents': [folder_id]}
    media = MediaFileUpload(filepath, mimetype='application/pdf')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"Uploaded to Drive: {file.get('id')}")

# === Step 8: Download and upload a PDF ===
def download_and_upload_pdf(pdf_url, drive_service, folder_id, todays_filenames):
    try:
        filename = os.path.basename(pdf_url)
        local_path = os.path.join(LOCAL_SAVE_DIR, filename)
        response = requests.get(pdf_url, stream=True)
        if response.status_code == 200:
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            print(f"Downloaded: {pdf_url}")
            upload_to_drive(drive_service, local_path, folder_id)
            todays_filenames.add(filename)
            os.remove(local_path)
        else:
            print(f"Failed to download: {pdf_url}")
    except Exception as e:
        print(f"Error downloading {pdf_url}: {e}")

# === Step 9: Delete old PDFs from Drive ===
def clean_up_old_files(service, folder_id, todays_filenames):
    existing_files = list_files_in_folder(service, folder_id)
    for file in existing_files:
        if file['name'] not in todays_filenames:
            print(f"Deleting outdated file: {file['name']}")
            service.files().delete(fileId=file['id']).execute()

# === Main routine ===
def main():
    print("Fetching sitemap...")
    urls = get_sitemap_urls(SITEMAP_URL)
    print(f"Found {len(urls)} en-US URLs")

    drive_service = authenticate_drive()
    folder_id = get_or_create_folder(drive_service, DRIVE_FOLDER_NAME)

    todays_filenames = set()

    for url in urls:
        print(f"Checking: {url}")
        pdf_links = find_pdf_links(url)
        if pdf_links:
            print(f"Found {len(pdf_links)} PDFs on {url}")
            for pdf in pdf_links:
                download_and_upload_pdf(pdf, drive_service, folder_id, todays_filenames)

    clean_up_old_files(drive_service, folder_id, todays_filenames)

if __name__ == "__main__":
    main()
