import re
import time
import email as email_lib
import imaplib

import requests

from .config import IMAP_HOST, IMAP_PORT, OAUTH_TOKEN_URL

OTP_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")


def _get_imap_access_token(client_id: str, refresh_token: str) -> str:
    resp = requests.post(
        OAUTH_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": refresh_token,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if "access_token" not in data:
        raise ValueError(f"Token error: {data.get('error_description', data)}")
    return data["access_token"]


def _extract_text(msg: email_lib.message.Message) -> str:
    parts = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() in ("text/plain", "text/html"):
                try:
                    parts.append(part.get_payload(decode=True).decode(errors="ignore"))
                except Exception:
                    pass
    else:
        try:
            parts.append(msg.get_payload(decode=True).decode(errors="ignore"))
        except Exception:
            pass
    return " ".join(parts)


def fetch_otp_imap(
    email_addr: str,
    client_id: str,
    refresh_token: str,
    max_retries: int = 20,
    delay: float = 5.0,
) -> str | None:
    """Poll Outlook IMAP for the latest email and extract a 6-digit OTP."""
    for attempt in range(1, max_retries + 1):
        print(f"  Polling IMAP for OTP... attempt {attempt}/{max_retries}")
        try:
            access_token = _get_imap_access_token(client_id, refresh_token)
            auth_string = f"user={email_addr}\x01auth=Bearer {access_token}\x01\x01"

            mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
            mail.authenticate("XOAUTH2", lambda x: auth_string.encode())
            mail.select("INBOX")

            _, data = mail.search(None, "ALL")
            mail_ids = data[0].split()
            if not mail_ids:
                mail.logout()
                time.sleep(delay)
                continue

            latest_id = mail_ids[-1]
            _, msg_data = mail.fetch(latest_id, "(RFC822)")
            mail.logout()

            raw = msg_data[0][1]
            msg = email_lib.message_from_bytes(raw)

            subject = msg.get("Subject", "")
            body = _extract_text(msg)
            plain = re.sub(r"<[^>]+>", " ", subject + " " + body)

            match = OTP_RE.search(plain)
            if match:
                code = match.group(1)
                print(f"  Found OTP: {code} (Subject: {subject[:60]})")
                return code

        except Exception as e:
            print(f"  [!] IMAP attempt {attempt} error: {e}")

        time.sleep(delay)

    return None
