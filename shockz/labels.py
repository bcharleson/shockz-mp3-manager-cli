"""Filename and title helpers for spoken track intros."""

from __future__ import annotations

import re
from pathlib import Path


def to_spoken_label(text: str) -> str:
    """Turn a filename or title into a short spoken label."""
    name = Path(text).stem if "." in text else text
    label = re.sub(r"\bvol\.?\s*(\d+)", r"volume \1", name, flags=re.I)
    label = label.replace("_", " ")
    label = re.sub(r"\s+", " ", label).strip().lower()
    return label


def spoken_label_for_track(
    title: str,
    filename: str | None,
    custom_announce: str | None,
) -> str:
    if custom_announce:
        return custom_announce.strip()
    if filename:
        return to_spoken_label(filename)
    return to_spoken_label(title)
