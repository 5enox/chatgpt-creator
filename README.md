# chatgpt-creator

Automated ChatGPT account signup using Outlook email stock with IMAP OTP retrieval.

## Installation

```bash
pip install chatgpt-creator
```

Or install from source:

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

## CLI Usage

```bash
# Create 1 account (default)
chatgpt-creator

# Create multiple accounts
chatgpt-creator -n 5

# Custom stock file
chatgpt-creator --stock my_emails.xlsx

# With proxy
chatgpt-creator --proxy socks5://user:pass@host:port

# All options
chatgpt-creator -n 3 --stock emails.xlsx --output results.json --proxy socks5://host:port
```

## Library Usage

```python
from chatgpt_signup import signup, load_email_stock

# Load accounts from xlsx
stock = load_email_stock("accounts.xlsx")

# Sign up a single account
result = signup(
    email=stock[0]["email"],
    password="MyPassword123!",
    name="John Doe",
    birthday="1995-06-15",
    client_id=stock[0]["client_id"],
    refresh_token=stock[0]["refresh_token"],
    proxy="socks5://user:pass@host:port",  # optional
)

print(result["status"])        # "success" or "failed"
print(result["access_token"])  # ChatGPT access token
```

## Environment Variables

| Variable | Description |
|---|---|
| `SIGNUP_PROXY` | Default proxy URL |
| `ACCOUNTS_XLSX` | Default stock file path |
| `CREATED_ACCOUNTS_FILE` | Default output file path |

## Output

Created accounts are saved to `created_accounts.json` with email, password, name, birthday, and access token.

## Contributing

Contributions are welcome! Feel free to open an issue or submit a pull request.

1. Fork the repo
2. Create your branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

## License

[MIT](LICENSE)
