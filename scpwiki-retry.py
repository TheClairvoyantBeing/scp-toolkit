# ============================================================
# SCP Wiki Retry Downloader
# Parses failed_downloads.txt and retries those specific pages.
# Handles proxy rate limits and Wikidot Placeholder pages.
# ============================================================

import urllib.request
import urllib.error
import os
import zipfile
import datetime
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://scp-wiki.wikidot.com/"
FAIL_LOG = "failed_downloads.txt"
RETRY_LOG = "resolved_downloads.txt"

# -----------------------------------------------------------
# Proxies
# -----------------------------------------------------------
USE_PROXIES = True

PROXIES = [
    "http://nnfyjnym:2bzuoy9xzek5@31.59.20.176:6754",
    "http://nnfyjnym:2bzuoy9xzek5@23.95.150.145:6114",
    "http://nnfyjnym:2bzuoy9xzek5@198.23.239.134:6540",
    "http://nnfyjnym:2bzuoy9xzek5@45.38.107.97:6014",
    "http://nnfyjnym:2bzuoy9xzek5@107.172.163.27:6543",
    "http://nnfyjnym:2bzuoy9xzek5@198.105.121.200:6462",
    "http://nnfyjnym:2bzuoy9xzek5@64.137.96.74:6641",
    "http://nnfyjnym:2bzuoy9xzek5@216.10.27.159:6837",
    "http://nnfyjnym:2bzuoy9xzek5@142.111.67.146:5611",
    "http://nnfyjnym:2bzuoy9xzek5@23.26.53.37:6003",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
]

# Track proxy health locally
proxy_health_lock = threading.Lock()
proxy_timeouts = {p: 0 for p in PROXIES}
log_lock = threading.Lock()

def random_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "keep-alive"
    }

def log_resolved(page):
    with log_lock:
        with open(RETRY_LOG, 'a', encoding='utf-8') as f:
            f.write(f"{page}\n")

def get_healthy_proxy(preferred_proxy):
    """If a proxy is in a timeout block (status 402/429), find another."""
    with proxy_health_lock:
        now = time.time()
        if proxy_timeouts[preferred_proxy] < now:
            return preferred_proxy
        
        # Look for any healthy proxy
        for p in PROXIES:
            if proxy_timeouts[p] < now:
                return p
        return None # All proxies are burned!

def set_proxy_timeout(proxy, seconds):
    with proxy_health_lock:
        proxy_timeouts[proxy] = time.time() + seconds

# -----------------------------------------------------------
# Download Logic
# -----------------------------------------------------------

def download_retry(page, start_proxy):
    url = BASE_URL + page
    time.sleep(random.uniform(0.5, 2.0)) # Polite base delay

    # 1. Grab a proxy that isn't currently banned
    proxy = get_healthy_proxy(start_proxy)
    if not proxy:
        return (page, False, "All proxies are timed out. Wait a few minutes.")

    try:
        req = urllib.request.Request(url, headers=random_headers())
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy}))
        
        with opener.open(req, timeout=15) as response:
            content = response.read()
            if content.startswith(b'\x1f\x8b'):
                import gzip
                content = gzip.decompress(content)

            # Check if it's actually just a placeholder page disguised as a 200 OK
            html_text = content.decode('utf-8', errors='ignore').lower()
            if "this page doesn't exist yet" in html_text or "does not exist" in html_text:
                return (page, False, "Confirmed missing (Placeholder)")
            
            return (page, True, content)

    except urllib.error.HTTPError as e:
        if e.code == 429:
            # Too many requests. Ban this proxy for 60 seconds.
            set_proxy_timeout(proxy, 60)
            return (page, False, "Rate Limited (429)")
        elif e.code == 402:
            # Payment Required (Webshare blocked due to bandwidth/concurrency limits)
            # Ban this proxy for 5 minutes
            set_proxy_timeout(proxy, 300)
            return (page, False, "Proxy Limit Reached (402)")
        elif e.code == 404:
            return (page, False, "Confirmed missing (404)")
        else:
            return (page, False, f"HTTP {e.code}")
    except Exception as e:
        return (page, False, getattr(e, 'reason', str(e)))

# -----------------------------------------------------------
# Main
# -----------------------------------------------------------

def main():
    if not os.path.exists(FAIL_LOG):
        print(f"No {FAIL_LOG} found. Nothing to retry!")
        return

    # Parse failed list
    to_retry = []
    with open(FAIL_LOG, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith("#"): continue
            parts = line.strip().split('\t')
            if len(parts) >= 1:
                to_retry.append(parts[0])
    
    # Remove duplicates and already resolved ones
    to_retry = list(set(to_retry))
    if os.path.exists(RETRY_LOG):
        with open(RETRY_LOG, 'r', encoding='utf-8') as f:
            resolved = set(line.strip() for line in f)
        to_retry = [p for p in to_retry if p not in resolved]
    
    if not to_retry:
        print("All failed downloads have already been resolved.")
        return

    print(f"Found {len(to_retry)} pages to retry. Launching {len(PROXIES)} workers...")
    
    zip_name = "SCPWiki_Retries_" + datetime.date.today().strftime("%d-%B-%Y") + ".zip"
    
    # Simple chunking to map chunks to proxies
    chunk_size = (len(to_retry) + len(PROXIES) - 1) // len(PROXIES)
    batches = [to_retry[i:i+chunk_size] for i in range(0, len(to_retry), chunk_size)]

    with zipfile.ZipFile(zip_name, 'a', zipfile.ZIP_DEFLATED) as zf:
        lock = threading.Lock()
        
        def process_batch(indices, proxy):
            for page in indices:
                # Keep trying up to 3 times per page if it's a rate limit error
                for attempt in range(3):
                    p, success, content = download_retry(page, proxy)
                    if success:
                        print(f" [✓] {page}    (Recovered)")
                        with lock:
                            zf.writestr(page + ".html", content)
                        log_resolved(page)
                        break
                    else:
                        if "Confirmed missing" in content:
                            print(f" [-] {page}    (Actually doesn't exist)")
                            log_resolved(page) # Mark as resolved so we don't try again
                            break
                        else:
                            print(f" [x] {page}    ({content}) (Attempt {attempt+1}/3)")
                            if attempt == 2:
                                print(f"     => Giving up on {page}")
                            time.sleep(2) # Brief pause before retry
    
        with ThreadPoolExecutor(max_workers=len(PROXIES)) as executor:
            for idx, batch in enumerate(batches):
                executor.submit(process_batch, batch, PROXIES[idx])

    print(f"\nDone! Saved recovered files to: {zip_name}")

if __name__ == '__main__':
    main()
