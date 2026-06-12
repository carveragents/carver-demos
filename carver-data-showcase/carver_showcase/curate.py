"""External-facing curation for the public gallery and the downloadable deck.

The external showcase (``apps/gallery.py``) and the deck it generates
(``carver_showcase/deck.py``) drop ``update_type`` "noise" so the public view
isn't cluttered by crawl artifacts and a long tail of one-off values. The
internal Data-Quality Cockpit (``apps/cockpit.py``) does **NOT** call this — it
must see the full, uncurated sprawl to do its job.

There is exactly ONE rule set (here), applied identically by the gallery and the
deck, so the two can never disagree on what's shown.
"""

from __future__ import annotations

import pandas as pd

from carver_showcase.config import (
    GALLERY_UPDATE_TYPE_DENYLIST,
    GALLERY_UPDATE_TYPE_MIN_SHARE,
)


def drop_noise_update_types(
    df: pd.DataFrame,
    min_share: float = GALLERY_UPDATE_TYPE_MIN_SHARE,
    denylist=GALLERY_UPDATE_TYPE_DENYLIST,
) -> pd.DataFrame:
    """Return ``df`` without records whose ``update_type`` is external-facing noise.

    A record is dropped when its ``update_type`` value either:

    1. contributes **less than ``min_share``** of total volume (the long tail), or
    2. is in ``denylist`` — named crawl-junk that sits above the threshold but is
       not a real regulatory update type (e.g. the ~12%-volume ``"website error"``).

    Records with a NULL ``update_type`` are **kept** — a missing value isn't a
    noisy *value*. The share denominator is the total record count (``len(df)``).
    Pure function: never mutates the input; returns a new frame.
    """
    if df.empty or "update_type" not in df.columns:
        return df

    n = len(df)
    counts = df["update_type"].value_counts(dropna=True)
    rare = {value for value, count in counts.items() if (count / n) < min_share}
    norm_deny = {str(d).strip().lower() for d in denylist}

    ut = df["update_type"]
    is_rare = ut.isin(rare).to_numpy()
    is_denied = (
        ut.astype("string").str.strip().str.lower().isin(norm_deny).fillna(False).to_numpy()
    )
    drop_mask = is_rare | is_denied
    return df.loc[~drop_mask].copy()
