#!/usr/bin/env python3
"""
SCP Toolkit Core Library
Provides shared networking, proxy loading, compression recovery,
and rate-limiting utilities for SCP Wiki archival scrapers.
"""

import os
import gzip
import time
import random
from pathlib import Path
from typing import List, Dict, Any, Optional

DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]


def load_proxies(proxy_file: str) -> List[str]:
    """
    Loads proxy strings from a file in format IP:PORT:USER:PASS or URL.
    Returns formatted proxy URLs.
    """
    path = Path(proxy_file)
    if not path.exists():
        return []

    proxies = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) == 4:
                ip, port, user, pwd = parts
                proxies.append(f"http://{user}:{pwd}@{ip}:{port}")
            elif line.startswith("http://") or line.startswith("https://"):
                proxies.append(line)
            elif len(parts) == 2:
                ip, port = parts
                proxies.append(f"http://{ip}:{port}")
    return proxies


def is_gzip_compressed(data: bytes) -> bool:
    """
    Checks if a binary payload begins with the gzip magic byte header (\x1f\x8b).
    """
    return len(data) >= 2 and data.startswith(b"\x1f\x8b")


def decompress_payload(data: bytes) -> bytes:
    """
    Safely decompresses a gzip payload or returns the original data if not compressed.
    """
    if is_gzip_compressed(data):
        try:
            return gzip.decompress(data)
        except Exception:
            return data
    return data


def calculate_backoff_delay(attempt: int, base_delay: float = 1.0, max_delay: float = 30.0) -> float:
    """
    Calculates exponential backoff with full jitter to avoid thundering herd problem.
    """
    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
    return random.uniform(0.5 * delay, delay)


def deduplicate_failure_log(log_path: str) -> int:
    """
    Deduplicates URLs in the failure ledger in-place, preserving order.
    Returns count of unique URLs.
    """
    path = Path(log_path)
    if not path.exists():
        return 0

    with open(path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    seen = set()
    unique = []
    for url in lines:
        if url not in seen:
            seen.add(url)
            unique.append(url)

    with open(path, "w", encoding="utf-8") as f:
        for url in unique:
            f.write(f"{url}\n")

    return len(unique)


def get_random_headers() -> Dict[str, str]:
    """
    Generates realistic browser headers to mimic genuine requests.
    """
    return {
        "User-Agent": random.choice(DEFAULT_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
