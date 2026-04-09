"""Automated ChatGPT account signup using Outlook email stock."""

__version__ = "0.2.0"

from .signup import signup
from .async_signup import async_signup, async_signup_batch
from .storage import load_email_stock, save_created_account
from .retry import retry, async_retry

__all__ = [
    "signup",
    "async_signup",
    "async_signup_batch",
    "load_email_stock",
    "save_created_account",
    "retry",
    "async_retry",
]
