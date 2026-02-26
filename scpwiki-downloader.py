# ============================================================
# SCP Wiki Parallel Downloader
# Downloads SCP-001 to SCP-9999 across 10 proxy IPs in parallel.
# Failed pages are logged to failed_downloads.txt and skipped.
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

# -----------------------------------------------------------
# CONFIGURE YOUR 10 PROXIES HERE
# Format: "http://ip:port" or "http://user:pass@ip:port"
# If you have no proxies, set USE_PROXIES = False to run
# single-thread with just the randomised headers/delays.
# -----------------------------------------------------------
USE_PROXIES = True  # Set to True once you have proxies

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

# Randomised browser fingerprints
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/122.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Android 14; Mobile; rv:123.0) Gecko/123.0 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
]

ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.8,en-US;q=0.7",
    "en-CA,en;q=0.9",
    "en-AU,en;q=0.8",
    "en;q=0.7",
]

# Tracking globals for progress reporting
progress_lock = threading.Lock()
total_pages = 9999
completed_pages = 0
failed_pages = 0
start_time = 0

# Thread-safe lock for writing to the shared error log
log_lock = threading.Lock()
FAIL_LOG = "failed_downloads.txt"


# -----------------------------------------------------------
# Helpers
# -----------------------------------------------------------

def format_scp(i):
    if i < 10:   return f"scp-00{i}"
    if i < 100:  return f"scp-0{i}"
    return f"scp-{i}"


def random_headers():
    return {
        "User-Agent":      random.choice(USER_AGENTS),
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": random.choice(ACCEPT_LANGUAGES),
        "Accept-Encoding": "gzip, deflate",
        "Connection":      "keep-alive",
        "DNT":             str(random.randint(0, 1)),      # random Do-Not-Track
        "Cache-Control":   random.choice(["no-cache", "max-age=0"]),
    }


def log_failure(page, reason):
    with log_lock:
        with open(FAIL_LOG, 'a', encoding='utf-8') as f:
            f.write(f"{page}\t{reason}\n")


# -----------------------------------------------------------
# Core download function
# -----------------------------------------------------------

def download_page(i, proxy_url=None):
    """Download one SCP page. Returns (page_name, success, content_or_None)."""
    page = format_scp(i)
    url  = BASE_URL + page

    # Random human-like delay (0.4 – 1.5 seconds)
    time.sleep(random.uniform(0.4, 1.5))

    try:
        req = urllib.request.Request(url, headers=random_headers())

        if proxy_url and USE_PROXIES:
            proxy_handler = urllib.request.ProxyHandler({"http": proxy_url})
            opener = urllib.request.build_opener(proxy_handler)
            response = opener.open(req, timeout=20)
        else:
            response = urllib.request.urlopen(req, timeout=20)

        with response:
            content = response.read()
            if content.startswith(b'\x1f\x8b'):
                import gzip
                content = gzip.decompress(content)

        return (page, True, content)

    except Exception as e:
        reason = getattr(e, 'reason', str(e))
        log_failure(page, reason)
        return (page, False, None)


# -----------------------------------------------------------
# Batch worker — one proxy handles one chunk of ~1000 pages
# -----------------------------------------------------------

def download_batch(batch_id, indices, proxy_url, zip_path):
    global completed_pages, failed_pages
    tag = f"[Batch {batch_id:02d}]"
    ok_count = fail_count = 0

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for i in indices:
            page, success, content = download_page(i, proxy_url)
            if success:
                zf.writestr(page + ".html", content)
                print(f"  {tag} {page} ✓")
                ok_count += 1
            else:
                print(f"  {tag} {page} ✗  (logged)")
                fail_count += 1
                with progress_lock:
                    failed_pages += 1

    print(f"\n{tag} Done → {zip_path}  ({ok_count} OK, {fail_count} failed)")
    return (zip_path, batch_id, ok_count, fail_count)


# -----------------------------------------------------------
# Progress Monitor
# -----------------------------------------------------------

def progress_monitor_thread():
    global completed_pages, failed_pages, start_time, total_pages
    
    countdown_triggered = False
    
    while True:
        time.sleep(5)
        
        with progress_lock:
            done = completed_pages
            fails = failed_pages
            
        total_processed = done + fails
        if total_processed >= total_pages:
            break
            
        elapsed = time.time() - start_time
        pages_per_sec = total_processed / elapsed if elapsed > 0 else 0
        remaining_pages = total_pages - total_processed
        
        est_remaining_sec = remaining_pages / pages_per_sec if pages_per_sec > 0 else 0
        
        # 5-minute interval check
        if int(elapsed) > 0 and int(elapsed) % 300 < 5:
            print(f"\n[PROGRESS REPORT] {total_processed}/{total_pages} processed ... "
                  f"(Elapsed: {elapsed/60:.1f}m, OK: {done}, Failed: {fails}, "
                  f"Est. Remaining: {est_remaining_sec/60:.1f}m)")
            time.sleep(5) # Prevent multiple prints within the 5 sec window
            
        # 1-minute countdown
        if not countdown_triggered and 0 < est_remaining_sec <= 60:
            print(f"\n[COUNTDOWN] Less than 1 minute remaining! (ETA: ~{int(est_remaining_sec)} seconds)\n")
            countdown_triggered = True

# -----------------------------------------------------------
# Main
# -----------------------------------------------------------

def main():
    global start_time, total_pages
    start_time = time.time()
    date_str  = datetime.date.today().strftime("%d-%B-%Y")
    num_workers = len(PROXIES) if USE_PROXIES else 1

    # Clear/create the fail log
    with open(FAIL_LOG, 'w', encoding='utf-8') as f:
        f.write(f"# Failed downloads — {date_str}\n")
        f.write("# page\treason\n")

    all_indices = list(range(1, 10000))
    total_pages = len(all_indices)

    # Split pages evenly across workers
    chunk_size = (len(all_indices) + num_workers - 1) // num_workers
    batches = [all_indices[i:i+chunk_size] for i in range(0, len(all_indices), chunk_size)]

    # Tasks: (batch_id, indices, proxy, output_zip)
    tasks = []
    for idx, batch in enumerate(batches):
        proxy   = PROXIES[idx] if USE_PROXIES else None
        zip_out = f"SCPWiki_{date_str}_part{idx+1}.zip"
        tasks.append((idx + 1, batch, proxy, zip_out))

    mode = f"{num_workers} parallel workers" if USE_PROXIES else "single-thread (no proxies)"
    print(f"Starting SCP downloader — {mode}")
    print(f"Pages: 1–9999  |  Chunks: {len(tasks)}  |  Fail log: {FAIL_LOG}\n")

    # Start progress monitor
    monitor = threading.Thread(target=progress_monitor_thread, daemon=True)
    monitor.start()

    batch_stats = []

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(download_batch, *t): t[3] for t in tasks}
        for future in as_completed(futures):
            zip_name = futures[future]
            try:
                result = future.result()
                batch_stats.append(result) # (zip_path, batch_id, ok, fail)
            except Exception as exc:
                print(f"  !! Batch for {zip_name} crashed: {exc}")

    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # -------------------------------------------------------
    # Final Statistics Report
    # -------------------------------------------------------
    print("\n============================================================")
    print("                    FINAL STATISTICS                        ")
    print("============================================================")
    print(f"Total Time:        {elapsed_time/60:.2f} minutes")
    print(f"Total Processed:   {completed_pages + failed_pages} pages")
    print(f"Total OK:          {completed_pages}")
    print(f"Total Failed:      {failed_pages}")
    print(f"Average Speed:     {(completed_pages+failed_pages)/elapsed_time:.2f} pages/sec")
    print("\nBatch Breakdown:")
    
    # Sort by batch ID for clean output
    batch_stats.sort(key=lambda x: x[1])
    for stat in batch_stats:
        print(f"  Batch {stat[1]:02d}: {stat[2]} passed, {stat[3]} failed")
        
    print("============================================================\n")
    print(f"Check {FAIL_LOG} for any pages that couldn't be downloaded.")


if __name__ == '__main__':
    main()
