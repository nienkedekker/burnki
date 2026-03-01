"""The main sync logic. Fetches burned stuff from WaniKani in a
background thread, then creates/updates Anki notes on the main thread"""


from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from . import wanikani
from .wanikani import Subject

DECK_NAME = "Burnki"


@dataclass
class NoteData:
    """Everything needed to create or update a single note"""

    subject_id: int
    characters: str
    subject_type: str
    meanings: str
    readings: str
    user_meanings: str
    meaning_note: str
    reading_note: str
    audio_filename: str
    audio_bytes: Optional[bytes]
    context_sentences: str
    level: str
    srs_stage: str


@dataclass
class SyncResult:
    notes: list[NoteData] = field(default_factory=list)
    error: Optional[str] = None
    total_fetched: int = 0


# -- formatting helpers --

def _format_meanings(subject: Subject) -> str:
    return ", ".join(subject.meanings)


def _format_readings(subject: Subject) -> str:
    if subject.object == "radical":
        return ""

    if subject.object == "kanji":
        onyomi = [r["reading"] for r in subject.readings if r.get("type") == "onyomi" and r.get("reading")]
        kunyomi = [r["reading"] for r in subject.readings if r.get("type") == "kunyomi" and r.get("reading")]
        parts = []
        if onyomi:
            parts.append(f"On: {', '.join(onyomi)}")
        if kunyomi:
            parts.append(f"Kun: {', '.join(kunyomi)}")
        return " · ".join(parts)

    # vocab / kana vocab
    readings = [r["reading"] for r in subject.readings if r.get("reading")]
    return ", ".join(readings)


def _format_sentences(subject: Subject) -> str:
    if not subject.context_sentences:
        return ""
    parts = []
    for s in subject.context_sentences:
        ja = s.get("ja", "")
        en = s.get("en", "")
        parts.append(f"{ja}<br>{en}")
    return "<br><br>".join(parts)


def _pick_audio(subject: Subject) -> Optional[str]:
    """Prefer male MP3, fall back to any MP3."""
    mp3s = [a for a in subject.audio if "mpeg" in a.content_type]
    male = [a for a in mp3s if a.voice_actor_gender == "male"]
    if male:
        return male[0].url
    if mp3s:
        return mp3s[0].url
    return None


def _audio_filename(subject: Subject, reading: str) -> str:
    safe_reading = re.sub(r"[^\w]", "_", reading) if reading else "audio"
    return f"burnki_{subject.id}_{safe_reading}.mp3"


def _build_characters(subject: Subject) -> str:
    """Some radicals don't have unicode chars, just use the slug for those"""
    if subject.characters:
        return subject.characters
    return subject.slug.replace("-", " ").title()


# -- background fetch --

def fetch_sync_data(
    token: str,
    updated_after: Optional[str] = None,
    progress: Optional[callable] = None,
    download_audio: bool = True,
) -> SyncResult:
    """Runs in a background thread. Grabs everything from WaniKani and
    builds NoteData objects, but doesn't touch Anki's collection yet"""
    result = SyncResult()

    def _progress(msg: str) -> None:
        if progress is not None:
            progress(msg)

    try:
        _progress("Fetching burned assignments…")
        assignments = wanikani.fetch_burned_assignments(token, updated_after)
        if not assignments:
            return result

        subject_ids = [a.subject_id for a in assignments]
        result.total_fetched = len(subject_ids)

        _progress(f"Fetching {len(subject_ids)} subjects…")
        subjects = wanikani.fetch_subjects(token, subject_ids)

        _progress("Fetching study materials…")
        materials = wanikani.fetch_study_materials(token, subject_ids)

        total = len(subject_ids)
        for i, sid in enumerate(subject_ids):
            subject = subjects.get(sid)
            if subject is None:
                continue

            display = subject.characters or subject.slug
            _progress(f"Processing {i + 1}/{total}: {display}")

            mat = materials.get(sid)

            audio_url = _pick_audio(subject) if download_audio and subject.object in ("vocabulary", "kana_vocabulary") else None
            audio_bytes = None
            fname = ""
            if audio_url:
                primary_reading = subject.readings[0]["reading"] if subject.readings else ""
                fname = _audio_filename(subject, primary_reading)
                _progress(f"Downloading audio {i + 1}/{total}: {display}")
                try:
                    audio_bytes = wanikani.download_audio(audio_url)
                except Exception:
                    audio_bytes = None  # card still works without it

            note = NoteData(
                subject_id=subject.id,
                characters=_build_characters(subject),
                subject_type=subject.object.replace("_", " ").capitalize(),
                meanings=_format_meanings(subject),
                readings=_format_readings(subject),
                user_meanings=", ".join(mat.meaning_synonyms) if mat else "",
                meaning_note=mat.meaning_note or "" if mat else "",
                reading_note=mat.reading_note or "" if mat else "",
                audio_filename=fname,
                audio_bytes=audio_bytes,
                context_sentences=_format_sentences(subject),
                level=str(subject.level),
                srs_stage="Burned",
            )
            result.notes.append(note)

    except Exception as e:
        result.error = str(e)

    return result


# -- main thread: apply to Anki --

def apply_sync_result(col, result: SyncResult) -> tuple[int, int]:  # noqa: ANN001
    """Takes the fetched data and actually creates/updates notes.
    Has to run on the main thread"""
    from .models import ensure_notetype

    deck_id = col.decks.id_for_name(DECK_NAME)
    if not deck_id:
        deck_id = col.decks.add_normal_deck_with_name(DECK_NAME).id

    model = ensure_notetype(col)

    # make sure new cards end up in the right deck
    if model["did"] != deck_id:
        model["did"] = deck_id
        col.models.update_dict(model)

    created = 0
    updated = 0

    for nd in result.notes:
        if nd.audio_bytes and nd.audio_filename:
            col.media.write_data(nd.audio_filename, nd.audio_bytes)

        # check if we already have this subject
        existing_ids = col.find_notes(f'"SubjectId:{nd.subject_id}"')

        if existing_ids:
            note = col.get_note(existing_ids[0])
            _set_note_fields(note, nd)
            col.update_note(note)
            updated += 1
        else:
            note = col.new_note(model)
            _set_note_fields(note, nd)
            col.add_note(note, deck_id)
            created += 1

    return created, updated


def _set_note_fields(note, nd: NoteData) -> None:  # noqa: ANN001
    note["SubjectId"] = str(nd.subject_id)
    note["Characters"] = nd.characters
    note["SubjectType"] = nd.subject_type
    note["Meanings"] = nd.meanings
    note["Readings"] = nd.readings
    note["UserMeanings"] = nd.user_meanings
    note["MeaningNote"] = nd.meaning_note
    note["ReadingNote"] = nd.reading_note
    note["Audio"] = f"[sound:{nd.audio_filename}]" if nd.audio_filename else ""
    note["ContextSentences"] = nd.context_sentences
    note["Level"] = nd.level
    note["SrsStage"] = nd.srs_stage
