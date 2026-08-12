# PDF Pages to Images Web App

A simple Streamlit web app that:
- uploads and processes multiple PDF files in one batch
- converts portfolio detail pages into PNG images
- skips cover or welcome pages, how-to or instruction pages, performance
  pages, disclaimers, and ending or thank-you pages by only including pages
  with a Research Analyst or Investment Advisor label
- names pages with a Research Analyst or Investment Advisor in the format
  `<title> by <manager name>`
- creates a separate ZIP download for every uploaded PDF
- creates one master ZIP containing all successful per-PDF ZIP files
- reports total, converted, and skipped page counts for each PDF
- optionally connects to Google Drive and replaces a selected folder with all
  PNGs from the latest conversion batch

## Setup

```bash
cd /path/to/pdf_to_image-main
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

## Run

```bash
cd /path/to/pdf_to_image-main
source .venv/bin/activate
streamlit run app.py
```

Then open the local URL shown by Streamlit in your browser.

## Optional Google Drive sync

Drive sync appears in the sidebar after the app has converted at least one
eligible page. It lets you connect a Google account, select a destination
folder, and replace that folder's direct contents with the latest PNG files.
Existing items are moved to Google Drive Trash, not permanently deleted.

### Google Cloud setup

1. Create or select a project in Google Cloud.
2. Enable the Google Drive API.
3. Configure the OAuth consent screen. While the app is in testing, add every
   Google account that will use the app as a test user.
4. Create an OAuth client with the application type **Web application**.
5. Add this authorized redirect URI, replacing the app name:

   ```text
   https://your-app-name.streamlit.app/component/streamlit_oauth.authorize_button
   ```

6. In the deployed Streamlit app, open **Settings → Secrets** and add:

   ```toml
   [google_drive]
   client_id = "your-client-id.apps.googleusercontent.com"
   client_secret = "your-client-secret"
   redirect_uri = "https://your-app-name.streamlit.app/component/streamlit_oauth.authorize_button"
   ```

Never upload or commit a real `secrets.toml` file. The included
`.streamlit/secrets.toml.example` contains placeholders only.

### Permission note

The folder browser and replacement workflow require the full Google Drive
scope so the app can list folders and move their existing contents to Trash.
Google classifies this as a restricted scope. A personal/testing app can use
test users; a public app may require Google's OAuth verification process.
