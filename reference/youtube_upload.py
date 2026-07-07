import os
import json

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _get_credentials() -> Credentials:
    token_path = os.environ.get("OAUTH_TOKEN_PATH", "token.json")

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_credentials(creds, token_path)
            return creds
        except Exception as e:
            raise RuntimeError(
                f"Token refresh failed: {e}. Delete '{token_path}' and re-run to go through the consent flow again."
            )

    client_id = os.environ["YOUTUBE_CLIENT_ID"]
    client_secret = os.environ["YOUTUBE_CLIENT_SECRET"]

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)
    _save_credentials(creds, token_path)
    return creds


def _save_credentials(creds: Credentials, path: str) -> None:
    with open(path, "w") as f:
        f.write(creds.to_json())


def upload_short(video_path: str, title: str, description: str) -> str:
    """
    Upload an MP4 as a public YouTube Short.
    Returns the YouTube video ID string on success.
    Raises RuntimeError with a human-readable message on:
      - token expiry that could not be refreshed
      - quota exhaustion (403 quotaExceeded)
      - unverified project locking video private
    """
    creds = _get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=256 * 1024)

    try:
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            _, response = request.next_chunk()

    except Exception as e:
        error_str = str(e)
        if "quotaExceeded" in error_str or (hasattr(e, "status_code") and getattr(e, "status_code", None) == 403):
            raise RuntimeError(
                f"YouTube API quota exceeded. Wait until quota resets (midnight Pacific) or request a quota increase in Google Cloud Console. Original error: {e}"
            )
        raise

    video_id = response["id"]
    returned_privacy = response.get("status", {}).get("privacyStatus")

    if returned_privacy != "public":
        raise RuntimeError(
            f"Video '{video_id}' was uploaded but is '{returned_privacy}' instead of 'public'. "
            "This usually means your Google Cloud project is unverified. "
            "See https://console.cloud.google.com/apis/credentials/consent to verify your project."
        )

    return video_id


def run_auth_flow() -> None:
    """Trigger the OAuth consent flow and save token.json. Run once before deploying."""
    _get_credentials()
    print(f"Auth complete. Token saved to: {os.environ.get('OAUTH_TOKEN_PATH', 'token.json')}")
