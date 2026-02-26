# SCP Wiki Downloader

Downloads SCP articles from the official SCP Foundation wiki (`scp-wiki.wikidot.com`).

Currently designed to download SCP-001 through SCP-9999 and archive them into daily `.zip` files.

## Features

- Downloads up to 9,999 articles.
- Native multi-threading using 10 concurrent workers.
- Designed to route traffic through 10 separate proxies to balance load and prevent rate-limiting by Wikidot.
- Randomizes user-agent, headers, and delays to mimic human traffic.
- Saves progress and logs any failed downloads to `failed_downloads.txt`.

## Getting Started

### 1. Prerequisites

- Python 3.x

### 2. Setting up Proxies (Required for parallel downloading)

To prevent IP bans from Wikidot, this script uses 10 different proxy IPs.
The easiest way to get 10 free proxies is via Webshare:

1. Create a free account at [Webshare.io](https://www.webshare.io/).
2. **IMPORTANT:** Verify your email address to unlock the full 10 free proxy IPs.
3. Once verified, go to your Proxy List.
4. Create a file named `Webshare 10 proxies.txt` in this root directory.
5. Paste your 10 credentials in the format: `IP:Port:Username:Password`
6. Edit `scpwiki-downloader.py` and ensure the `USE_PROXIES` variable is set to `True` and the `PROXIES` list is populated with your proxy URLs (e.g. `http://user:pass@ip:port`).

### 3. Usage

Run the downloader:

```bash
python scpwiki-downloader.py
```

The script will chunk the 9,999 pages across your 10 proxies and download them into 10 separate ZIP files (e.g. `SCPWiki_25-February-2026_part1.zip`).

If any files fail to download (due to rate limits, drops, or missing pages), they will be logged in `failed_downloads.txt`.

### 4. Troubleshooting

#### Corrupted HTML Files (GZIP payload issues)

If you ever open a downloaded `.html` file and it looks like corrupted binary gibberish instead of text, it means Wikidot's server caching layer unexpectedly enforced `gzip` compression on the fly.
This occurs because our script spoofs browser `User-Agent` headers. When Wikidot sees a modern Chrome/Firefox user-agent, it assumes the client can handle automatic payload compression.

**Fix:** The current versions of `scpwiki-downloader.py` and `scpwiki-retry.py` have been patched to detect the `\x1f\x8b` magic byte header and automatically decompress these strings on the fly. If you encounter older files that were affected by this bug, you can run a script to manually decompress them using Python's `gzip` module.

## Acknowledgements

Special thanks to **Junaid Ali Rasheed**, the original creator of this repository and the foundational downloading script from which this parallelized version is derived.
