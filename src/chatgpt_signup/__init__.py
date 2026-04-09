"""Automated ChatGPT account signup using Outlook email stock."""

__version__ = "0.1.0"

from .signup import signup
from .storage import load_email_stock, save_created_account

__all__ = ["signup", "load_email_stock", "save_created_account"]
