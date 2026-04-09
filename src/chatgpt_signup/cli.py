import argparse
import asyncio
import logging
import random
import string
import sys
from datetime import date, timedelta

from faker import Faker

from .config import ACCOUNTS_XLSX, CREATED_ACCOUNTS_FILE
from .signup import signup
from .async_signup import async_signup_batch
from .storage import load_email_stock, save_created_account

fake = Faker()


def _rand_str(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def _random_birthday() -> str:
    today = date.today()
    return fake.date_between(
        start_date=today - timedelta(days=49 * 365),
        end_date=today - timedelta(days=20 * 365),
    ).isoformat()


def _prepare_accounts(selected: list[dict]) -> list[dict]:
    """Attach generated name/password/birthday to each stock account."""
    prepared = []
    for acct in selected:
        prepared.append({
            **acct,
            "name": f"{fake.first_name()} {fake.last_name()}",
            "password": "SuperSecure" + _rand_str() + "!1",
            "birthday": _random_birthday(),
        })
    return prepared


def _setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    parser = argparse.ArgumentParser(description="ChatGPT account signup")
    parser.add_argument(
        "-n", "--count", type=int, default=1,
        help="Number of accounts to create (default: 1)",
    )
    parser.add_argument(
        "--stock", default=ACCOUNTS_XLSX,
        help=f"Path to Outlook accounts xlsx (default: {ACCOUNTS_XLSX})",
    )
    parser.add_argument(
        "--output", default=CREATED_ACCOUNTS_FILE,
        help=f"Path to save created accounts (default: {CREATED_ACCOUNTS_FILE})",
    )
    parser.add_argument(
        "--proxy", default=None,
        help="SOCKS5/HTTP proxy URL (overrides SIGNUP_PROXY env var)",
    )
    parser.add_argument(
        "--async", dest="use_async", action="store_true",
        help="Run signups concurrently using async",
    )
    parser.add_argument(
        "--max-concurrent", type=int, default=5,
        help="Max concurrent signups in async mode (default: 5)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="Only show errors",
    )
    args = parser.parse_args()

    if args.quiet:
        logging.basicConfig(level=logging.ERROR)
    else:
        _setup_logging(args.verbose)

    log = logging.getLogger("chatgpt_signup.cli")

    log.info("Loading email stock from %s", args.stock)
    stock = load_email_stock(args.stock)
    if not stock:
        log.error("No accounts found in stock file.")
        sys.exit(1)
    log.info("Loaded %d account(s)", len(stock))

    if args.count > len(stock):
        log.error("Requested %d but only %d accounts available.", args.count, len(stock))
        sys.exit(1)

    selected = random.sample(stock, args.count)
    prepared = _prepare_accounts(selected)

    if args.use_async:
        log.info("Running %d signup(s) concurrently (max %d)", args.count, args.max_concurrent)
        results = asyncio.run(
            async_signup_batch(prepared, proxy=args.proxy, max_concurrent=args.max_concurrent)
        )
        for result in results:
            save_created_account(result, args.output)
    else:
        results = []
        for i, acct in enumerate(prepared, 1):
            log.info("Account %d/%d: %s", i, args.count, acct["email"])
            result = signup(
                email=acct["email"],
                password=acct["password"],
                name=acct["name"],
                birthday=acct["birthday"],
                client_id=acct["client_id"],
                refresh_token=acct["refresh_token"],
                proxy=args.proxy,
            )
            save_created_account(result, args.output)
            results.append(result)

    succeeded = sum(1 for r in results if r["status"] == "success")
    failed = len(results) - succeeded
    log.info("Done: %d succeeded, %d failed — saved to %s", succeeded, failed, args.output)


if __name__ == "__main__":
    main()
