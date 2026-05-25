"""Binary-search the exact corpus size between 110K and 200K."""
import os, time, httpx
from dotenv import load_dotenv
load_dotenv()
API_KEY = os.environ["CARVER_API_KEY"]
URL = "https://app.carveragents.ai/api/v1/artifacts/dags/7f61eee4-1c56-44cc-b7fb-bbfcbda6a5ad/artifacts"

def count_at(offset):
    t = time.time()
    r = httpx.get(URL, params={"dag_ids_in": "7f61eee4-1c56-44cc-b7fb-bbfcbda6a5ad",
                                "state": "completed", "limit": 10000, "offset": offset},
                  headers={"X-API-Key": API_KEY}, timeout=120.0)
    n = len(r.json()) if r.status_code == 200 else -1
    print(f"  offset={offset:>7}  count={n:>5}  elapsed={time.time()-t:.1f}s")
    return n

# Probe spread offsets
for off in [110000, 130000, 150000, 170000, 180000, 190000]:
    count_at(off)
