import asyncio
import json
import uuid
import random

from curl_cffi.requests import AsyncSession, BrowserType

from .config import BASE_URL, AUTH_URL, AUTH_API, BROWSER_HEADERS, PROXY, get_logger
from .imap_otp import async_fetch_otp_imap
from .retry import async_retry

log = get_logger("async_signup")


def _uuid() -> str:
    return str(uuid.uuid4())


async def _delay(lo: float = 0.5, hi: float = 1.5):
    await asyncio.sleep(random.uniform(lo, hi))


async def _auth_post(session: AsyncSession, path: str, payload: dict, referer: str = "/"):
    return await session.post(
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


async def _follow_continue(session: AsyncSession, data: dict, referer: str = "/"):
    url = data.get("continue_url")
    if not url:
        return None
    method = data.get("method", "GET").upper()
    log.debug("Following continue_url: %s", url[:80])
    headers = {
        "accept": "application/json",
        "referer": f"{AUTH_URL}{referer}",
    }
    if method == "POST":
        headers["content-type"] = "application/json"
        resp = await session.post(url, headers=headers, allow_redirects=True)
    else:
        resp = await session.get(url, headers=headers, allow_redirects=True)
    log.debug("continue_url status: %d", resp.status_code)
    return resp


def _make_result(email: str, password: str, name: str, birthday: str) -> dict:
    return {
        "email": email,
        "password": password,
        "name": name,
        "birthday": birthday,
        "access_token": None,
        "status": "failed",
        "error": None,
    }


def _fail(result: dict, error: str) -> dict:
    result["error"] = error
    log.error("[%s] %s", result["email"], error)
    return result


@async_retry(max_attempts=3, delay=3.0, exceptions=(ConnectionError, OSError))
async def _visit_homepage(session: AsyncSession):
    resp = await session.get(BASE_URL, allow_redirects=True)
    if resp.status_code != 200:
        raise ConnectionError(f"Homepage returned {resp.status_code}")
    return resp


# ── Public API ──────────────────────────────────────────────────────


async def async_signup(
    email: str,
    password: str,
    name: str,
    birthday: str,
    client_id: str,
    refresh_token: str,
    proxy: str | None = None,
) -> dict:
    """
    Async version of signup. Runs the full ChatGPT signup flow for one account.

    Returns a dict with keys: email, password, name, birthday,
    access_token (str | None), status ("success" | "failed"), error (str | None).
    """
    result = _make_result(email, password, name, birthday)
    effective_proxy = proxy or PROXY or None

    try:
        session = AsyncSession(
            impersonate=BrowserType.chrome131,
            proxy=effective_proxy,
        )
        session.headers.update(BROWSER_HEADERS)

        oai_did = _uuid()
        auth_session_id = _uuid()

        # Step 1 — Homepage
        log.info("[%s] Step 1: Visiting homepage", email)
        await _visit_homepage(session)
        await _delay()

        # Step 2 — CSRF token
        log.info("[%s] Step 2: Getting CSRF token", email)
        resp = await session.get(
            f"{BASE_URL}/api/auth/csrf", headers={"accept": "application/json"},
        )
        csrf_token = resp.json().get("csrfToken") if resp.status_code == 200 else None
        if not csrf_token:
            return _fail(result, f"CSRF request failed ({resp.status_code})")
        log.debug("[%s] CSRF: %s...", email, csrf_token[:24])
        await _delay(0.5, 1.0)

        # Step 3 — Initiate OAuth signup
        log.info("[%s] Step 3: Initiating OAuth signup", email)
        signin_resp = await session.post(
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
            return _fail(result, f"Signin initiation failed ({signin_resp.status_code})")

        authorize_url = signin_resp.json().get("url")
        if not authorize_url:
            return _fail(result, "No authorize URL in signin response")
        log.debug("[%s] Authorize URL obtained", email)
        await _delay()

        # Step 4 — Follow authorize URL
        log.info("[%s] Step 4: Following authorize URL", email)
        auth_resp = await session.get(
            authorize_url,
            headers={
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "referer": f"{BASE_URL}/",
            },
            allow_redirects=True,
        )
        final_url = str(auth_resp.url)
        log.debug("[%s] Landed on: %s", email, final_url[:80])

        # Passwordless flow
        if "/email-verification" in final_url:
            log.info("[%s] Passwordless flow — OTP sent", email)
            return await _handle_otp_and_profile(
                session, result, name, birthday, client_id, refresh_token,
            )

        if "/create-account/password" not in final_url:
            return _fail(result, f"Unexpected page: {final_url}")
        await _delay()

        # Step 5 — Register (set password)
        log.info("[%s] Step 5: Registering account", email)
        reg_resp = await _auth_post(
            session, "user/register",
            {"password": password, "username": email},
            referer="/create-account/password",
        )
        if reg_resp.status_code != 200:
            return _fail(result, f"Registration failed ({reg_resp.status_code}): {reg_resp.text[:200]}")

        reg_data = reg_resp.json()
        log.debug("[%s] Page type: %s", email, reg_data.get("page", {}).get("type", ""))

        follow_resp = await _follow_continue(session, reg_data, referer="/create-account/password")
        if follow_resp is None:
            return _fail(result, "No continue_url after registration")

        try:
            send_data = follow_resp.json()
            if send_data.get("continue_url"):
                await _follow_continue(session, send_data, referer="/email-verification")
        except Exception:
            pass
        await _delay(1.0, 2.0)

        # Step 6+7 — OTP + profile
        log.info("[%s] Step 6: OTP verification", email)
        return await _handle_otp_and_profile(
            session, result, name, birthday, client_id, refresh_token,
        )

    except Exception as e:
        result["error"] = str(e)
        log.error("[%s] ERROR: %s", email, e)
        return result


async def _handle_otp_and_profile(
    session: AsyncSession,
    result: dict,
    name: str,
    birthday: str,
    client_id: str,
    refresh_token: str,
) -> dict:
    email = result["email"]

    log.info("[%s] Waiting for OTP via IMAP", email)
    await asyncio.sleep(5)
    otp_code = await async_fetch_otp_imap(email, client_id, refresh_token)

    if not otp_code:
        otp_code = input(f"\n>>> Enter 6-digit OTP for [{email}]: ").strip()
        if len(otp_code) != 6 or not otp_code.isdigit():
            log.warning("OTP should be 6 digits")

    log.info("[%s] Validating OTP: %s", email, otp_code)
    validate_resp = await _auth_post(
        session, "email-otp/validate",
        {"code": otp_code},
        referer="/email-verification",
    )

    if validate_resp.status_code == 401:
        return _fail(result, "Incorrect OTP code")
    if validate_resp.status_code == 429:
        return _fail(result, "Too many OTP attempts")
    if validate_resp.status_code != 200:
        return _fail(result, f"OTP validation failed ({validate_resp.status_code})")

    validate_data = validate_resp.json()
    page_type = validate_data.get("page", {}).get("type", "")
    log.debug("[%s] Page type: %s", email, page_type)

    follow_resp = await _follow_continue(session, validate_data, referer="/email-verification")

    if page_type == "about_you" or (follow_resp and "/about-you" in str(follow_resp.url)):
        return await _complete_profile(session, result, name, birthday)
    if page_type == "external_url" or (follow_resp and "chatgpt.com" in str(follow_resp.url)):
        return await _get_session_token(session, result)

    log.warning("[%s] Unexpected page type '%s', attempting profile", email, page_type)
    return await _complete_profile(session, result, name, birthday)


async def _complete_profile(session: AsyncSession, result: dict, name: str, birthday: str) -> dict:
    email = result["email"]
    await _delay()
    log.info("[%s] Completing profile (name=%s, birthday=%s)", email, name, birthday)

    resp = await _auth_post(
        session, "create_account",
        {"name": name, "birthdate": birthday},
        referer="/about-you",
    )
    if resp.status_code != 200:
        return _fail(result, f"Profile submission failed ({resp.status_code})")

    profile_data = resp.json()
    log.debug("[%s] Page type: %s", email, profile_data.get("page", {}).get("type", ""))

    follow_resp = await _follow_continue(session, profile_data, referer="/about-you")
    if follow_resp and "chatgpt.com" in str(follow_resp.url):
        log.debug("[%s] Landed on: %s", email, follow_resp.url)
    elif profile_data.get("continue_url"):
        log.debug("[%s] Following final OAuth callback", email)
        await session.get(
            profile_data["continue_url"],
            headers={
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "referer": f"{AUTH_URL}/about-you",
            },
            allow_redirects=True,
        )

    await _delay(0.5, 1.0)
    return await _get_session_token(session, result)


async def _get_session_token(session: AsyncSession, result: dict) -> dict:
    email = result["email"]
    log.info("[%s] Getting session token", email)
    resp = await session.get(
        f"{BASE_URL}/api/auth/session",
        headers={"accept": "application/json", "referer": f"{BASE_URL}/"},
    )
    if resp.status_code != 200:
        return _fail(result, f"Session request failed ({resp.status_code})")

    session_data = resp.json()
    access_token = session_data.get("accessToken")
    user = session_data.get("user", {})

    if access_token:
        result["access_token"] = access_token
        result["status"] = "success"
        log.info("[%s] SIGNUP SUCCESS — %s / %s",
                 email, user.get("name", "N/A"), user.get("email", "N/A"))
    else:
        result["error"] = "No access token in session response"
        log.error("[%s] %s", email, result["error"])
        log.debug("[%s] Response: %s", email, json.dumps(session_data, indent=2)[:500])

    return result


async def async_signup_batch(
    accounts: list[dict],
    proxy: str | None = None,
    max_concurrent: int = 5,
) -> list[dict]:
    """
    Sign up multiple accounts concurrently.

    Args:
        accounts: List of dicts with keys: email, password, name, birthday,
                  client_id, refresh_token.
        proxy: Optional proxy URL.
        max_concurrent: Max number of concurrent signups.

    Returns list of result dicts.
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _limited(acct):
        async with semaphore:
            return await async_signup(
                email=acct["email"],
                password=acct["password"],
                name=acct["name"],
                birthday=acct["birthday"],
                client_id=acct["client_id"],
                refresh_token=acct["refresh_token"],
                proxy=proxy,
            )

    return await asyncio.gather(*[_limited(a) for a in accounts])
