"""WaniKani API client. Uses only stdlib (urllib) so we don't need
any external dependencies. Handles pagination, rate limiting, and
batching."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional
from urllib.request import Request, urlopen

API_BASE = "https://api.wanikani.com/v2"
BATCH_SIZE = 500  # keep URLs from getting too long


@dataclass
class Assignment:
    subject_id: int
    srs_stage: int


@dataclass
class AudioEntry:
    url: str
    content_type: str
    voice_actor_gender: str


@dataclass
class Subject:
    id: int
    object: str  # "radical", "kanji", "vocabulary", "kana_vocabulary"
    characters: Optional[str]
    slug: str
    meanings: list[str]
    readings: list[dict[str, Any]]
    level: int
    audio: list[AudioEntry]
    context_sentences: list[dict[str, str]]


@dataclass
class StudyMaterial:
    subject_id: int
    meaning_synonyms: list[str]
    meaning_note: Optional[str]
    reading_note: Optional[str]


def _make_request(url: str, token: str) -> tuple[dict[str, Any], dict[str, str]]:
    req = Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Wanikani-Revision", "20170710")

    resp = urlopen(req, timeout=30)
    headers = {k.lower(): v for k, v in resp.headers.items()}
    body = json.loads(resp.read().decode("utf-8"))
    return body, headers


def _respect_rate_limit(headers: dict[str, str]) -> None:
    """Back off if we're about to hit the rate limit."""
    remaining = headers.get("ratelimit-remaining")
    reset = headers.get("ratelimit-reset")
    if remaining is not None and int(remaining) < 5 and reset is not None:
        wait = max(0, int(reset) - int(time.time())) + 1
        time.sleep(wait)


def _paginate(
    url: str,
    token: str,
    on_page: Callable[[dict[str, Any]], None],
    progress: Optional[Callable[[str], None]] = None,
) -> None:
    """Follow next_url until there are no more pages."""
    next_url: Optional[str] = url
    while next_url is not None:
        body, headers = _make_request(next_url, token)
        on_page(body)
        _respect_rate_limit(headers)
        next_url = body.get("pages", {}).get("next_url")


def _batch_ids(ids: list[int]) -> list[list[int]]:
    return [ids[i : i + BATCH_SIZE] for i in range(0, len(ids), BATCH_SIZE)]


# -- parsing --

def _parse_subject(data: dict[str, Any]) -> Subject:
    obj = data["object"]
    d = data["data"]

    meanings = [
        m["meaning"]
        for m in d.get("meanings", [])
        if m.get("accepted_answer", True)
    ]

    readings = d.get("readings") or []

    audio_entries: list[AudioEntry] = []
    for a in d.get("pronunciation_audios", []):
        meta = a.get("metadata", {})
        audio_entries.append(
            AudioEntry(
                url=a["url"],
                content_type=a.get("content_type", "audio/mpeg"),
                voice_actor_gender=meta.get("gender", ""),
            )
        )

    sentences = d.get("context_sentences") or []

    return Subject(
        id=data["id"],
        object=obj,
        characters=d.get("characters"),
        slug=d.get("slug", ""),
        meanings=meanings,
        readings=readings,
        level=d.get("level", 0),
        audio=audio_entries,
        context_sentences=sentences,
    )


def _parse_study_material(data: dict[str, Any]) -> StudyMaterial:
    d = data["data"]
    return StudyMaterial(
        subject_id=d["subject_id"],
        meaning_synonyms=d.get("meaning_synonyms") or [],
        meaning_note=d.get("meaning_note"),
        reading_note=d.get("reading_note"),
    )


# -- public API --

def fetch_burned_assignments(
    token: str,
    updated_after: Optional[str] = None,
    progress: Optional[Callable[[str], None]] = None,
) -> list[Assignment]:
    """Get all burned assignments (SRS stage 9). Pass updated_after
    to only get ones that changed since the last sync."""
    url = f"{API_BASE}/assignments?srs_stages=9"
    if updated_after:
        url += f"&updated_after={updated_after}"

    assignments: list[Assignment] = []

    def collect(body: dict[str, Any]) -> None:
        for item in body.get("data", []):
            d = item["data"]
            assignments.append(
                Assignment(subject_id=d["subject_id"], srs_stage=d["srs_stage"])
            )

    _paginate(url, token, collect, progress)
    return assignments


def fetch_subjects(
    token: str,
    subject_ids: list[int],
    progress: Optional[Callable[[str], None]] = None,
) -> dict[int, Subject]:
    """Fetch subjects by ID, returns {subject_id: Subject}."""
    subjects: dict[int, Subject] = {}

    for batch in _batch_ids(subject_ids):
        ids_param = ",".join(str(i) for i in batch)
        url = f"{API_BASE}/subjects?ids={ids_param}"

        def collect(body: dict[str, Any]) -> None:
            for item in body.get("data", []):
                s = _parse_subject(item)
                subjects[s.id] = s

        _paginate(url, token, collect, progress)

    return subjects


def fetch_study_materials(
    token: str,
    subject_ids: list[int],
    progress: Optional[Callable[[str], None]] = None,
) -> dict[int, StudyMaterial]:
    """Fetch user's study materials (synonyms, notes) for the given subjects."""
    materials: dict[int, StudyMaterial] = {}

    for batch in _batch_ids(subject_ids):
        ids_param = ",".join(str(i) for i in batch)
        url = f"{API_BASE}/study_materials?subject_ids={ids_param}"

        def collect(body: dict[str, Any]) -> None:
            for item in body.get("data", []):
                m = _parse_study_material(item)
                materials[m.subject_id] = m

        _paginate(url, token, collect, progress)

    return materials


def download_audio(url: str) -> bytes:
    req = Request(url)
    resp = urlopen(req, timeout=30)
    return resp.read()
