import argparse
import random
import string
import sys
from datetime import date, timedelta

from faker import Faker

from .config import ACCOUNTS_XLSX, CREATED_ACCOUNTS_FILE
from .signup import signup
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
    args = parser.parse_args()

    print(f"[*] Loading email stock from {args.stock}...")
    stock = load_email_stock(args.stock)
    if not stock:
        print("[!] No accounts found in stock file.")
        sys.exit(1)
    print(f"  Loaded {len(stock)} account(s)")

    if args.count > len(stock):
        print(f"[!] Requested {args.count} but only {len(stock)} accounts available.")
        sys.exit(1)

    selected = random.sample(stock, args.count)
    succeeded = 0
    failed = 0

    for i, acct in enumerate(selected, 1):
        email = acct["email"]
        first = fake.first_name()
        last = fake.last_name()
        name = f"{first} {last}"
        password = "SuperSecure" + _rand_str() + "!1"
        birthday = _random_birthday()

        print(f"\n{'#' * 60}")
        print(f"  Account {i}/{args.count}: {email}")
        print(f"  Name: {name}  Birthday: {birthday}")
        print(f"{'#' * 60}")

        result = signup(
            email=email,
            password=password,
            name=name,
            birthday=birthday,
            client_id=acct["client_id"],
            refresh_token=acct["refresh_token"],
            proxy=args.proxy,
        )

        save_created_account(result, args.output)

        if result["status"] == "success":
            succeeded += 1
            print(f"[+] Saved to {args.output}")
        else:
            failed += 1
            print(f"[!] Signup failed: {result['error']}")

    print(f"\n{'=' * 60}")
    print(f"  Done: {succeeded} succeeded, {failed} failed")
    print(f"  Results saved to {args.output}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
