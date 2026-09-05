#!/usr/bin/env python3
"""
SCP Gzip Payload Recovery Tool
Scans an HTML article directory, detects accidental gzip-compressed files
sent by Wikidot's caching layer, and decompresses them in-place.
"""

import os
import argparse
from pathlib import Path
from downloader_core import is_gzip_compressed, decompress_payload


def fix_compressed_html_files(directory: str, dry_run: bool = False) -> int:
    dir_path = Path(directory)
    if not dir_path.exists():
        print(f"Directory not found: {directory}")
        return 0

    count = 0
    print(f"Scanning '{directory}' for compressed HTML files...")
    for entry in dir_path.glob("*.html"):
        if not entry.is_file():
            continue
        try:
            with open(entry, "rb") as f:
                content = f.read()

            if is_gzip_compressed(content):
                count += 1
                if dry_run:
                    print(f"[DRY-RUN] Would decompress: {entry.name} ({len(content)} bytes)")
                else:
                    uncompressed = decompress_payload(content)
                    with open(entry, "wb") as f:
                        f.write(uncompressed)
                    print(f"Decompressed: {entry.name} ({len(content)} -> {len(uncompressed)} bytes)")
        except Exception as e:
            print(f"Error processing {entry.name}: {e}")

    print(f"Scan complete. Fixed {count} compressed files in '{directory}'.")
    return count


def main():
    parser = argparse.ArgumentParser(description="Fix GZIP-compressed HTML articles from Wikidot cache")
    parser.add_argument("--dir", default="html_articles", help="Path to directory containing HTML articles")
    parser.add_argument("--dry-run", action="store_true", help="Scan without modifying files")
    args = parser.parse_args()

    fix_compressed_html_files(args.dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
