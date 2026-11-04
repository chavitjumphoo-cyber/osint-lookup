"""Fuentes OSINT (scanners concretos).

Por qué un paquete:
- Agrupa módulos por fuente (GitHub, Sherlock-like, etc.).
- Cada módulo implementará `core.interfaces.scanner.OSINTScanner`.
"""

from vendor.osint_d2.adapters.osint_sources.aboutme import AboutMeScanner
from vendor.osint_d2.adapters.osint_sources.behance import BehanceScanner
from vendor.osint_d2.adapters.osint_sources.devto import DevToScanner
from vendor.osint_d2.adapters.osint_sources.dribbble import DribbbleScanner
from vendor.osint_d2.adapters.osint_sources.facebook import FacebookScanner
from vendor.osint_d2.adapters.osint_sources.gist_github import GitHubGistScanner
from vendor.osint_d2.adapters.osint_sources.github import GitHubScanner
from vendor.osint_d2.adapters.osint_sources.gitlab import GitLabScanner
from vendor.osint_d2.adapters.osint_sources.instagram import InstagramScanner
from vendor.osint_d2.adapters.osint_sources.kaggle import KaggleScanner
from vendor.osint_d2.adapters.osint_sources.keybase import KeybaseScanner
from vendor.osint_d2.adapters.osint_sources.medium import MediumScanner
from vendor.osint_d2.adapters.osint_sources.npm import NpmScanner
from vendor.osint_d2.adapters.osint_sources.pinterest import PinterestScanner
from vendor.osint_d2.adapters.osint_sources.producthunt import ProductHuntScanner
from vendor.osint_d2.adapters.osint_sources.reddit import RedditScanner
from vendor.osint_d2.adapters.osint_sources.soundcloud import SoundCloudScanner
from vendor.osint_d2.adapters.osint_sources.telegram import TelegramScanner
from vendor.osint_d2.adapters.osint_sources.twitch import TwitchScanner
from vendor.osint_d2.adapters.osint_sources.x import XScanner

__all__ = [
    "AboutMeScanner",
    "BehanceScanner",
    "DevToScanner",
    "DribbbleScanner",
    "FacebookScanner",
    "GitHubScanner",
    "GitHubGistScanner",
    "GitLabScanner",
    "InstagramScanner",
    "KaggleScanner",
    "KeybaseScanner",
    "MediumScanner",
    "NpmScanner",
    "PinterestScanner",
    "ProductHuntScanner",
    "RedditScanner",
    "SoundCloudScanner",
    "TelegramScanner",
    "TwitchScanner",
    "XScanner",
]
