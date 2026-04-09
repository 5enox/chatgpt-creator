import json

import openpyxl

from .config import ACCOUNTS_XLSX, CREATED_ACCOUNTS_FILE


def load_email_stock(xlsx_path: str = ACCOUNTS_XLSX) -> list[dict]:
    """
    Parse accounts.xlsx rows formatted as:
        email----password----client_id----refresh_token
    Returns list of dicts with those four keys.
    """
    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    ws = wb.active
    accounts = []
    for (cell,) in ws.iter_rows(min_row=4, min_col=1, max_col=1, values_only=True):
        if not cell or "----" not in str(cell):
            continue
        parts = str(cell).split("----")
        if len(parts) != 4:
            continue
        accounts.append({
            "email": parts[0].strip(),
            "password": parts[1].strip(),
            "client_id": parts[2].strip(),
            "refresh_token": parts[3].strip(),
        })
    wb.close()
    return accounts


def load_created_accounts(path: str = CREATED_ACCOUNTS_FILE) -> list[dict]:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_created_account(account: dict, path: str = CREATED_ACCOUNTS_FILE):
    accounts = load_created_accounts(path)
    accounts.append(account)
    with open(path, "w") as f:
        json.dump(accounts, f, indent=2)
