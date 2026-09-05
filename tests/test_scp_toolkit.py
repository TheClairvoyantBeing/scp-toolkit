#!/usr/bin/env python3
"""
Unit Test Suite for scp-toolkit Core Functions
"""

import unittest
import os
import gzip
import tempfile
import shutil
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from downloader_core import (
    is_gzip_compressed,
    decompress_payload,
    load_proxies,
    calculate_backoff_delay,
    deduplicate_failure_log,
    get_random_headers
)
from fix_gzip import fix_compressed_html_files

ROOT_DIR = Path(__file__).parent.parent


class TestSCPToolkit(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_gzip_detection_and_decompression(self):
        raw_text = b"<html><body>Item #: SCP-001</body></html>"
        compressed = gzip.compress(raw_text)

        self.assertTrue(is_gzip_compressed(compressed))
        self.assertFalse(is_gzip_compressed(raw_text))

        decompressed = decompress_payload(compressed)
        self.assertEqual(decompressed, raw_text)

        # Uncompressed passthrough
        self.assertEqual(decompress_payload(raw_text), raw_text)

    def test_proxy_loader(self):
        proxy_file = os.path.join(self.test_dir, "proxies.txt")
        with open(proxy_file, "w", encoding="utf-8") as f:
            f.write("# Webshare proxies\n")
            f.write("192.168.1.1:8080:user:pass\n")
            f.write("http://proxy.example.com:3128\n")
            f.write("10.0.0.1:9090\n")

        proxies = load_proxies(proxy_file)
        self.assertEqual(len(proxies), 3)
        self.assertEqual(proxies[0], "http://user:pass@192.168.1.1:8080")
        self.assertEqual(proxies[1], "http://proxy.example.com:3128")
        self.assertEqual(proxies[2], "http://10.0.0.1:9090")

    def test_backoff_delay_calculation(self):
        for attempt in range(1, 6):
            delay = calculate_backoff_delay(attempt, base_delay=1.0, max_delay=16.0)
            self.assertGreater(delay, 0)
            self.assertLessEqual(delay, 16.0)

    def test_failure_log_deduplication(self):
        log_file = os.path.join(self.test_dir, "failed.txt")
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("https://scp-wiki.wikidot.com/scp-100\n")
            f.write("https://scp-wiki.wikidot.com/scp-101\n")
            f.write("https://scp-wiki.wikidot.com/scp-100\n")
            f.write("https://scp-wiki.wikidot.com/scp-102\n")
            f.write("https://scp-wiki.wikidot.com/scp-101\n")

        unique_count = deduplicate_failure_log(log_file)
        self.assertEqual(unique_count, 3)

        with open(log_file, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f]
        self.assertEqual(lines, [
            "https://scp-wiki.wikidot.com/scp-100",
            "https://scp-wiki.wikidot.com/scp-101",
            "https://scp-wiki.wikidot.com/scp-102"
        ])

    def test_fix_gzip_utility(self):
        articles_dir = os.path.join(self.test_dir, "html_articles")
        os.makedirs(articles_dir)

        # Write a compressed file and a normal file
        file1 = os.path.join(articles_dir, "scp-001.html")
        with open(file1, "wb") as f:
            f.write(gzip.compress(b"Compressed Article 001"))

        file2 = os.path.join(articles_dir, "scp-002.html")
        with open(file2, "wb") as f:
            f.write(b"Normal Article 002")

        # Dry run
        dry_count = fix_compressed_html_files(articles_dir, dry_run=True)
        self.assertEqual(dry_count, 1)

        # Actual execution
        fixed_count = fix_compressed_html_files(articles_dir, dry_run=False)
        self.assertEqual(fixed_count, 1)

        with open(file1, "rb") as f:
            self.assertEqual(f.read(), b"Compressed Article 001")

    def test_random_headers(self):
        headers = get_random_headers()
        self.assertIn("User-Agent", headers)
        self.assertIn("Accept", headers)

    def test_license_and_anonymity(self):
        lic_file = ROOT_DIR / "LICENSE"
        self.assertTrue(lic_file.exists(), "LICENSE missing")

        readme_file = ROOT_DIR / "README.md"
        with open(readme_file, "r", encoding="utf-8") as f:
            readme = f.read()
            self.assertNotIn("Evion", readme)
            self.assertNotIn("Cutinha", readme)


if __name__ == "__main__":
    unittest.main()
