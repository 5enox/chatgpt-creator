# chatgpt-creator

Automated ChatGPT account signup using Outlook email stock with IMAP OTP retrieval.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Outlook email accounts in `accounts.xlsx`

## Setup

```bash
git clone https://github.com/5enox/chatgpt-creator.git
cd chatgpt-creator
uv sync
```

## accounts.xlsx Format

Rows starting from row 4, column A. Each cell formatted as:

```
email----password----client_id----refresh_token
```

## Usage

```bash
# Create 1 account (default)
uv run chatgpt-signup

# Create multiple accounts
uv run chatgpt-signup -n 5

# Custom stock file
uv run chatgpt-signup --stock my_emails.xlsx

# With proxy
uv run chatgpt-signup --proxy socks5://user:pass@host:port

# All options
uv run chatgpt-signup -n 3 --stock emails.xlsx --output results.json --proxy socks5://host:port
```

## Environment Variables

| Variable | Description |
|---|---|
| `SIGNUP_PROXY` | Default proxy URL |
| `ACCOUNTS_XLSX` | Default stock file path |
| `CREATED_ACCOUNTS_FILE` | Default output file path |

## Output

Created accounts are saved to `created_accounts.json` with email, password, name, birthday, and access token.

## License

[MIT](LICENSE)
