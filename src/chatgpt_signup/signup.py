import json
import time
import uuid
import random

from curl_cffi.requests import Session, BrowserType

from .config import BASE_URL, AUTH_URL, AUTH_API, BROWSER_HEADERS, PROXY
from .imap_otp import fetch_otp_imap


def _uuid() -> str:
    return str(uuid.uuid4())


def _delay(lo: float = 0.5, hi: float = 1.5):
    time.sleep(random.uniform(lo, hi))


def _auth_post(session: Session, path: str, payload: dict, referer: str = "/"):
    return session.post(
        f"{AUTH_API}/{path}",
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "origin": AUTH_URL,
            "referer": f"{AUTH_URL}{referer}",
        },
        json=payload,
        allow_redirects=False,
    )


def _follow_continue(session: Session, data: dict, referer: str = "/"):
    url = data.get("continue_url")
    if not url:
        return None
    method = data.get("method", "GET").upper()
    print(f"  -> Following continue_url: {url[:80]}...")
    headers = {
        "accept": "application/json",
        "referer": f"{AUTH_URL}{referer}",
    }
    if method == "POST":
        headers["content-type"] = "application/json"
        resp = session.post(url, headers=headers, allow_redirects=True)
    else:
        resp = session.get(url, headers=headers, allow_redirects=True)
    print(f"  -> Status: {resp.status_code}")
    return resp


# ── Public API ──────────────────────────────────────────────────────


def signup(
    email: str,
    password: str,
    name: str,
    birthday: str,
    client_id: str,
    refresh_token: str,
    proxy: str | None = None,
) -> dict:
    """
    Run the full ChatGPT signup flow for one account.

    Returns a dict with keys: email, password, name, birthday,
    access_token (str | None), status ("success" | "failed"), error (str | None).
    """
    result = {
        "email": email,
        "password": password,
        "name": name,
        "birthday": birthday,
        "access_token": None,
        "status": "failed",
        "error": None,
    }
    tag = f"[{email}]"
    effective_proxy = proxy or PROXY or None

    try:
        session = Session(
            impersonate=BrowserType.chrome131,
            proxy=effective_proxy,
        )
        session.headers.update(BROWSER_HEADERS)

        oai_did = _uuid()
        auth_session_id = _uuid()

        # Step 1 — Homepage
        print(f"{tag} Step 1: Visiting homepage...")
        resp = session.get(BASE_URL, allow_redirects=True)
        if resp.status_code != 200:
            result["error"] = f"Homepage returned {resp.status_code}"
            print(f"{tag} [!] {result['error']}")
            return result
        _delay()

        # Step 2 — CSRF token
        print(f"{tag} Step 2: Getting CSRF token...")
        resp = session.get(f"{BASE_URL}/api/auth/csrf", headers={"accept": "application/json"})
        csrf_token = resp.json().get("csrfToken") if resp.status_code == 200 else None
        if not csrf_token:
            result["error"] = f"CSRF request failed ({resp.status_code})"
            print(f"{tag} [!] {result['error']}")
            return result
        print(f"{tag} CSRF: {csrf_token[:24]}...")
        _delay(0.5, 1.0)

        # Step 3 — Initiate OAuth signup
        print(f"{tag} Step 3: Initiating OAuth signup...")
        signin_resp = session.post(
            f"{BASE_URL}/api/auth/signin/openai",
            data={
                "callbackUrl": "/",
                "csrfToken": csrf_token,
                "json": "true",
            },
            params={
                "prompt": "login",
                "ext-oai-did": oai_did,
                "auth_session_logging_id": auth_session_id,
                "screen_hint": "signup",
                "login_hint": email,
            },
            headers={
                "content-type": "application/x-www-form-urlencoded",
                "accept": "*/*",
                "origin": BASE_URL,
                "referer": f"{BASE_URL}/",
            },
            allow_redirects=False,
        )
        if signin_resp.status_code != 200:
            result["error"] = f"Signin initiation failed ({signin_resp.status_code})"
            print(f"{tag} [!] {result['error']}")
            return result

        authorize_url = signin_resp.json().get("url")
        if not authorize_url:
            result["error"] = "No authorize URL in signin response"
            print(f"{tag} [!] {result['error']}")
            return result
        print(f"{tag} Authorize URL obtained")
        _delay()

        # Step 4 — Follow authorize URL
        print(f"{tag} Step 4: Following authorize URL...")
        auth_resp = session.get(
            authorize_url,
            headers={
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "referer": f"{BASE_URL}/",
            },
            allow_redirects=True,
        )
        final_url = str(auth_resp.url)
        print(f"{tag} Landed on: {final_url[:80]}...")

        # Passwordless flow — straight to email verification
        if "/email-verification" in final_url:
            print(f"{tag} Passwordless flow — OTP sent to {email}")
            return _handle_otp_and_profile(
                session, result, tag, name, birthday, client_id, refresh_token,
            )

        if "/create-account/password" not in final_url:
            result["error"] = f"Unexpected page: {final_url}"
            print(f"{tag} [!] {result['error']}")
            return result
        _delay()

        # Step 5 — Register (set password)
        print(f"{tag} Step 5: Registering account...")
        reg_resp = _auth_post(
            session, "user/register",
            {"password": password, "username": email},
            referer="/create-account/password",
        )
        if reg_resp.status_code != 200:
            result["error"] = f"Registration failed ({reg_resp.status_code}): {reg_resp.text[:200]}"
            print(f"{tag} [!] {result['error']}")
            return result

        reg_data = reg_resp.json()
        print(f"{tag} Page type: {reg_data.get('page', {}).get('type', '')}")

        # Follow continue_url (triggers OTP email send)
        follow_resp = _follow_continue(session, reg_data, referer="/create-account/password")
        if follow_resp is None:
            result["error"] = "No continue_url after registration"
            print(f"{tag} [!] {result['error']}")
            return result

        try:
            send_data = follow_resp.json()
            if send_data.get("continue_url"):
                _follow_continue(session, send_data, referer="/email-verification")
        except Exception:
            pass
        _delay(1.0, 2.0)

        # Step 6+7 — OTP + profile
        print(f"{tag} Step 6: OTP verification...")
        return _handle_otp_and_profile(
            session, result, tag, name, birthday, client_id, refresh_token,
        )

    except Exception as e:
        result["error"] = str(e)
        print(f"{tag} [!] ERROR: {e}")
        return result


def _handle_otp_and_profile(
    session: Session,
    result: dict,
    tag: str,
    name: str,
    birthday: str,
    client_id: str,
    refresh_token: str,
) -> dict:
    email = result["email"]

    print(f"{tag} Waiting for OTP via IMAP...")
    time.sleep(5)
    otp_code = fetch_otp_imap(email, client_id, refresh_token)

    if not otp_code:
        otp_code = input(f"\n>>> Enter 6-digit OTP for [{email}]: ").strip()
        if len(otp_code) != 6 or not otp_code.isdigit():
            print("  [!] Warning: OTP should be 6 digits")

    print(f"{tag} Validating OTP: {otp_code}")
    validate_resp = _auth_post(
        session, "email-otp/validate",
        {"code": otp_code},
        referer="/email-verification",
    )

    if validate_resp.status_code == 401:
        result["error"] = "Incorrect OTP code"
        print(f"{tag} [!] {result['error']}")
        return result
    if validate_resp.status_code == 429:
        result["error"] = "Too many OTP attempts"
        print(f"{tag} [!] {result['error']}")
        return result
    if validate_resp.status_code != 200:
        result["error"] = f"OTP validation failed ({validate_resp.status_code})"
        print(f"{tag} [!] {result['error']}")
        return result

    validate_data = validate_resp.json()
    page_type = validate_data.get("page", {}).get("type", "")
    print(f"{tag} Page type: {page_type}")

    follow_resp = _follow_continue(session, validate_data, referer="/email-verification")

    if page_type == "about_you" or (follow_resp and "/about-you" in str(follow_resp.url)):
        return _complete_profile(session, result, tag, name, birthday)
    if page_type == "external_url" or (follow_resp and "chatgpt.com" in str(follow_resp.url)):
        return _get_session_token(session, result, tag)

    # Fallback: try profile completion
    print(f"{tag} Unexpected page type '{page_type}', attempting profile...")
    return _complete_profile(session, result, tag, name, birthday)


def _complete_profile(
    session: Session, result: dict, tag: str, name: str, birthday: str,
) -> dict:
    _delay()
    print(f"{tag} Completing profile (name={name}, birthday={birthday})...")

    resp = _auth_post(
        session, "create_account",
        {"name": name, "birthdate": birthday},
        referer="/about-you",
    )
    if resp.status_code != 200:
        result["error"] = f"Profile submission failed ({resp.status_code})"
        print(f"{tag} [!] {result['error']}")
        return result

    profile_data = resp.json()
    print(f"{tag} Page type: {profile_data.get('page', {}).get('type', '')}")

    follow_resp = _follow_continue(session, profile_data, referer="/about-you")
    if follow_resp and "chatgpt.com" in str(follow_resp.url):
        print(f"{tag} Landed on: {follow_resp.url}")
    elif profile_data.get("continue_url"):
        print(f"{tag} Following final OAuth callback...")
        session.get(
            profile_data["continue_url"],
            headers={
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "referer": f"{AUTH_URL}/about-you",
            },
            allow_redirects=True,
        )

    _delay(0.5, 1.0)
    return _get_session_token(session, result, tag)


def _get_session_token(session: Session, result: dict, tag: str) -> dict:
    print(f"{tag} Getting session token...")
    resp = session.get(
        f"{BASE_URL}/api/auth/session",
        headers={"accept": "application/json", "referer": f"{BASE_URL}/"},
    )
    if resp.status_code != 200:
        result["error"] = f"Session request failed ({resp.status_code})"
        print(f"{tag} [!] {result['error']}")
        return result

    session_data = resp.json()
    access_token = session_data.get("accessToken")
    user = session_data.get("user", {})

    if access_token:
        result["access_token"] = access_token
        result["status"] = "success"
        print(f"{tag} SIGNUP SUCCESS — {user.get('name', 'N/A')} / {user.get('email', 'N/A')}")
        print(f"{tag} Token: {access_token[:40]}...")
    else:
        result["error"] = "No access token in session response"
        print(f"{tag} [!] {result['error']}")
        print(f"{tag} Response: {json.dumps(session_data, indent=2)[:500]}")

    return result
