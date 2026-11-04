"""Fuentes OSINT orientadas a email.

Estas fuentes operan sobre direcciones de email (no usernames).
"""

from vendor.osint_d2.adapters.email_sources.gravatar import GravatarScanner
from vendor.osint_d2.adapters.email_sources.gravatar_profile import GravatarProfileScanner
from vendor.osint_d2.adapters.email_sources.pgp_keys_openpgp import OpenPGPKeysScanner
from vendor.osint_d2.adapters.email_sources.pgp_ubuntu_keyserver import UbuntuKeyserverScanner

__all__ = [
    "GravatarScanner",
    "GravatarProfileScanner",
    "OpenPGPKeysScanner",
    "UbuntuKeyserverScanner",
]
