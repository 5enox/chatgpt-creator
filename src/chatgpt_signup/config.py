import logging
import os

BASE_URL = "https://chatgpt.com"
AUTH_URL = "https://auth.openai.com"
AUTH_API = f"{AUTH_URL}/api/accounts"

IMAP_HOST = "outlook.office365.com"
IMAP_PORT = 993
OAUTH_TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"

PROXY = os.environ.get("SIGNUP_PROXY", "")

ACCOUNTS_XLSX = os.environ.get("ACCOUNTS_XLSX", "accounts.xlsx")
CREATED_ACCOUNTS_FILE = os.environ.get("CREATED_ACCOUNTS_FILE", "created_accounts.json")

BROWSER_HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "sec-ch-ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
}


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"chatgpt_signup.{name}")
