# pipeline/fetch.py
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Snapshot:
    timestamp: str
    digest: str
    original: str


def enumerate_versions(cdx_rows: list[list[str]]) -> list[Snapshot]:
    """Dedupe CDX rows by digest, keeping the earliest timestamp. Skip warc/revisit."""
    if not cdx_rows:
        return []
    header, *data = cdx_rows
    cols = {name: i for i, name in enumerate(header)}
    seen: dict[str, Snapshot] = {}
    for row in data:
        if row[cols["mimetype"]] == "warc/revisit":
            continue
        if row[cols["statuscode"]] != "200":
            continue
        digest = row[cols["digest"]]
        if digest not in seen:
            seen[digest] = Snapshot(
                timestamp=row[cols["timestamp"]],
                digest=digest,
                original=row[cols["original"]] if "original" in cols else "",
            )
    return list(seen.values())


def raw_url(snapshot: Snapshot) -> str:
    return f"https://web.archive.org/web/{snapshot.timestamp}id_/{snapshot.original}"


def fetch_cdx(target_url: str, *, max_attempts: int = 5) -> list[list[str]]:
    """Hit the Wayback CDX API via curl. Returns parsed JSON rows.

    Retries on empty response or JSON parse failures — Wayback CDX has occasional
    transient failures that return 200 with an empty body.
    """
    import time
    cdx = (
        "https://web.archive.org/cdx/search/cdx?"
        f"url={target_url}&output=json"
        "&fl=timestamp,digest,statuscode,mimetype,original"
    )
    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        out = subprocess.run(
            ["curl", "-sL", "--max-time", "30", cdx],
            capture_output=True, text=True, check=False,
        )
        body = out.stdout.strip()
        if body:
            try:
                return json.loads(body)
            except json.JSONDecodeError as e:
                last_err = e
        if attempt < max_attempts:
            time.sleep(2 ** attempt)  # 2, 4, 8, 16 s
    raise RuntimeError(
        f"Wayback CDX returned empty/unparseable body after {max_attempts} attempts"
        + (f"; last error: {last_err}" if last_err else "")
    )


def download(snapshot: Snapshot, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest
    subprocess.run(
        ["curl", "-sL", "-o", str(dest), raw_url(snapshot)],
        check=True,
    )
    return dest
