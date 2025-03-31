# PDF Scraper and Google Drive Sync

This script:
- Fetches all `en-US` pages from a sitemap
- Extracts all PDF links from each page
- Downloads each PDF temporarily
- Uploads them to a Google Drive folder
- Deletes files in the Drive folder that no longer exist on the site

This ensures Google Drive is always a clean, up-to-date mirror of available PDFs.

---

## Requirements

- Python 3.7+
- Google Cloud Project with Drive API enabled
- OAuth 2.0 Client credentials (downloaded as `credentials.json`)

Install required packages:
```bash
pip install requests beautifulsoup4 lxml google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

---

## Initial Google Drive Authentication

1. Go to https://console.cloud.google.com/
2. Select or create a project
3. Enable the **Google Drive API**
4. Go to `APIs & Services > Credentials`
5. Create **OAuth Client ID**
    - Application type: `Desktop`
    - Download the JSON file as `credentials.json`
6. On first run, the script will:
    - Open a browser for login
    - Cache credentials to `token.pickle` (used for future runs)

---

## Configuration

In the script, you can modify:

| Variable              | Purpose                                            |
|----------------------|----------------------------------------------------|
| `SITEMAP_URL`        | URL of the sitemap XML                             |
| `LOCAL_SAVE_DIR`     | Temporary download path for PDFs                   |
| `CREDENTIALS_PATH`   | Path to your OAuth client file                     |
| `TOKEN_PATH`         | Where token gets stored after login                |
| `DRIVE_FOLDER_NAME`  | Name of the Google Drive folder to upload to       |

---

## Hosting / Automation

Run this script on any environment that supports Python:

### Linux / macOS
Schedule using `cron`:
```bash
crontab -e
```
```
0 6 * * * /usr/bin/python3 /path/to/script.py
```

### Windows Server
Use Task Scheduler to schedule a daily Python run.

### Cloud Options (optional)
- Google Cloud Functions + Scheduler
- GitHub Actions (with secrets for credentials)
- Docker (for containerized deployments)

---

## Daily Sync Behavior

Each day:
1. All PDFs on all relevant pages are downloaded and uploaded
2. The Drive folder is compared to the scraped list
3. Any PDF not found in the current scrape is deleted from Drive

This creates a clean, mirrored archive of what’s currently live.

---

## Replacing or Resetting Auth

To re-authorize with a different account:
1. Delete `token.pickle`
2. Re-run the script and log in with the new Google account

---



