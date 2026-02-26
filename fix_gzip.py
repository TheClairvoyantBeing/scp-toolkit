import os
import gzip

dir_path = "html_articles"
count = 0
print("Scanning for compressed HTML files...")
for f in os.listdir(dir_path):
    if f.endswith(".html"):
        filepath = os.path.join(dir_path, f)
        with open(filepath, "rb") as file:
            content = file.read()
        
        if content.startswith(b'\x1f\x8b'):
            try:
                uncompressed = gzip.decompress(content)
                with open(filepath, "wb") as file:
                    file.write(uncompressed)
                count += 1
            except Exception as e:
                print(f"Error on {f}: {e}")

print(f"Decompressed and fixed {count} files in {dir_path}.")
