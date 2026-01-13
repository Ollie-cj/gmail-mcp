"""OAuth 2.0 authentication for Gmail API."""

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Gmail API scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]

# Default paths for credentials
DEFAULT_CREDENTIALS_DIR = Path.home() / ".gmail-mcp"
DEFAULT_CREDENTIALS_PATH = DEFAULT_CREDENTIALS_DIR / "credentials.json"
DEFAULT_TOKEN_PATH = DEFAULT_CREDENTIALS_DIR / "token.json"


def get_credentials(
    credentials_path: Path | None = None,
    token_path: Path | None = None,
) -> Credentials:
    """
    Get valid Gmail API credentials.

    On first run, opens a browser for OAuth consent.
    Subsequent runs use the saved refresh token.

    Args:
        credentials_path: Path to OAuth client credentials JSON
        token_path: Path to store/load the user's access token

    Returns:
        Valid Credentials object for Gmail API

    Raises:
        FileNotFoundError: If credentials.json is missing
    """
    credentials_path = credentials_path or DEFAULT_CREDENTIALS_PATH
    token_path = token_path or DEFAULT_TOKEN_PATH

    # Ensure directory exists
    token_path.parent.mkdir(parents=True, exist_ok=True)

    creds = None

    # Load existing token if available
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # If no valid credentials, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                raise FileNotFoundError(
                    f"OAuth credentials not found at {credentials_path}\n"
                    "Download from Google Cloud Console:\n"
                    "1. Go to https://console.cloud.google.com/\n"
                    "2. APIs & Services > Credentials\n"
                    "3. Create OAuth 2.0 Client ID (Desktop app)\n"
                    "4. Download JSON and save to ~/.gmail-mcp/credentials.json"
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save token for future use
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return creds
