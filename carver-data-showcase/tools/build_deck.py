"""Render the downloadable "State of Carver Data" PDF deck on demand.

Loads the full, unfiltered snapshot and writes data/carver-state-of-data.pdf —
the same artifact the gallery serves and that tools/pull_full.py regenerates
after every data refresh.

Run: .venv/bin/python tools/build_deck.py
"""

import logging
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from carver_showcase.deck import build_deck  # noqa: E402


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    path = build_deck()
    size_kb = os.path.getsize(path) / 1024
    print(f"Deck written: {path} ({size_kb:,.0f} KB)")


if __name__ == "__main__":
    main()
