from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
from typing import Optional


@dataclasses.dataclass
class Source:
    id: Optional[int]
    name: str
    type: str
    feed_url: str
    enabled: bool = True
    last_run_at: Optional[str] = None


@dataclasses.dataclass
class Job:
    id: Optional[int]
    title: str
    company: str
    location: str
    description: str
    source_url: str
    source_name: str
    posted_at: str
    ingested_at: str
    normalized_hash: str

    @staticmethod
    def compute_hash(title: str, company: str, location: str, source_url: str) -> str:
        normalized = f"{title.strip().lower()}|{company.strip().lower()}|{location.strip().lower()}|{source_url.strip().lower()}"
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def now_iso() -> str:
        return dt.datetime.utcnow().isoformat()
