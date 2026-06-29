"""Fetch baseline.db on container boot (it's too big for Git).

The backend host (Render/Fly) sets DB_URL to a public link to a gzipped baseline.db
(e.g. a GitHub Release asset). This downloads + unzips it to data/db/baseline.db if
it isn't already there. See DEPLOY.md.
"""
import gzip
import os
import shutil
import sys
import urllib.request

DB = os.path.join("data", "db", "baseline.db")
url = os.environ.get("DB_URL")

if os.path.exists(DB) and os.path.getsize(DB) > 0:
    print(f"[db] baseline.db already present ({os.path.getsize(DB):,} bytes) — skipping download")
    sys.exit(0)

if not url:
    print("[db] WARNING: no baseline.db and DB_URL not set — the API will not work.")
    sys.exit(0)

os.makedirs(os.path.dirname(DB), exist_ok=True)
tmp = "/tmp/baseline.db.dl"
print(f"[db] downloading baseline.db from {url} ...")
urllib.request.urlretrieve(url, tmp)

if url.endswith(".gz"):
    with gzip.open(tmp, "rb") as f, open(DB, "wb") as g:
        shutil.copyfileobj(f, g)
    os.remove(tmp)
else:
    shutil.move(tmp, DB)

print(f"[db] baseline.db ready ({os.path.getsize(DB):,} bytes)")
