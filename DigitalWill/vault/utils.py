"""
Utility functions for the vault app.

Includes:
  - encrypt(text)     → encrypts plaintext using Fernet
  - decrypt(token)    → decrypts Fernet token back to plaintext
  - generate_otp()    → creates a 6-digit random OTP
  - log_activity()    → creates an ActivityLog entry
"""

import random
from cryptography.fernet import Fernet
from django.conf import settings
from vault.models import ActivityLog


# ─────────────────────────────────────────────────────────
# Fernet cipher — symmetric encryption/decryption
# The key is loaded from settings.py (FERNET_KEY)
# ─────────────────────────────────────────────────────────
_cipher = Fernet(settings.FERNET_KEY)


def encrypt(plaintext: str) -> str:
    """
    Encrypt a plaintext string.
    Returns a base64-encoded encrypted string (safe to store in DB).
    """
    return _cipher.encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """
    Decrypt a previously encrypted token.
    Returns the original plaintext string.
    """
    try:
        return _cipher.decrypt(token.encode()).decode()
    except Exception:
        return "[Decryption Error]"


def generate_otp() -> str:
    """Generate a secure 6-digit OTP for nominee verification."""
    return str(random.randint(100000, 999999))


def log_activity(user, action: str):
    """
    Record an activity in the ActivityLog table.
    Call this whenever a significant action happens
    (asset created, nominee added, login, etc.)
    """
    ActivityLog.objects.create(user=user, action=action)
