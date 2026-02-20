"""Note type definition for Burnki. Handles creating and updating
the note type with all the fields, card templates, and styling."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anki.models import NotetypeDict

MODEL_NAME = "Burnki"

FIELDS = [
    "SubjectId",
    "Characters",
    "SubjectType",
    "Meanings",
    "Readings",
    "UserMeanings",
    "MeaningNote",
    "ReadingNote",
    "Audio",
    "ContextSentences",
    "Level",
    "SrsStage",
]

FRONT_TEMPLATE = """\
<div class="card-front">
  <div class="characters">{{Characters}}</div>
  <div class="type-badge {{SubjectType}}">{{SubjectType}}</div>
</div>
"""

BACK_TEMPLATE = """\
<div class="card-back">
  {{FrontSide}}
  <hr id="answer">
  <div class="meanings">{{Meanings}}</div>
  {{#UserMeanings}}<div class="user-meanings">User: {{UserMeanings}}</div>{{/UserMeanings}}
  {{#Readings}}<div class="readings">{{Readings}}</div>{{/Readings}}
  {{#Audio}}<div class="audio">{{Audio}}</div>{{/Audio}}
  {{#ContextSentences}}<div class="sentences">{{ContextSentences}}</div>{{/ContextSentences}}
  {{#MeaningNote}}<div class="note"><span class="note-label">Meaning note:</span> {{MeaningNote}}</div>{{/MeaningNote}}
  {{#ReadingNote}}<div class="note"><span class="note-label">Reading note:</span> {{ReadingNote}}</div>{{/ReadingNote}}
  <div class="meta">Level {{Level}} · {{SrsStage}}</div>
</div>
"""

CSS = """\
.card {
  font-family: "Hiragino Kaku Gothic Pro", "Noto Sans JP", "Meiryo", sans-serif;
  text-align: center;
  background: #303030;
  color: #fff;
  padding: 20px;
}

.characters {
  font-size: 4em;
  font-weight: bold;
  margin: 0.3em 0;
  line-height: 1.2;
}

.type-badge {
  display: inline-block;
  padding: 4px 16px;
  border-radius: 4px;
  font-size: 0.8em;
  text-transform: capitalize;
  color: #fff;
  background: #888;
}

/* WaniKani colors */
.type-badge.radical { background: #00aaff; }
.type-badge.kanji { background: #ff00aa; }
.type-badge.vocabulary,
.type-badge.kana_vocabulary { background: #aa00ff; }

hr#answer {
  border: none;
  border-top: 1px solid #555;
  margin: 16px 0;
}

.meanings {
  font-size: 1.6em;
  font-weight: bold;
  margin-bottom: 8px;
}

.user-meanings {
  font-size: 1.1em;
  color: #aaa;
  margin-bottom: 8px;
}

.readings {
  font-size: 1.4em;
  margin-bottom: 12px;
}

.audio {
  margin: 12px 0;
}

.sentences {
  text-align: left;
  font-size: 0.95em;
  line-height: 1.6;
  margin: 12px auto;
  max-width: 500px;
  color: #ccc;
}

.note {
  text-align: left;
  font-size: 0.9em;
  line-height: 1.5;
  margin: 8px auto;
  max-width: 500px;
  color: #bbb;
  background: #3a3a3a;
  padding: 8px 12px;
  border-radius: 4px;
}

.note-label {
  font-weight: bold;
  color: #ddd;
}

.meta {
  font-size: 0.75em;
  color: #777;
  margin-top: 16px;
}
"""


def ensure_notetype(col) -> NotetypeDict:  # noqa: ANN001
    """Get or create the Burnki note type."""
    model = col.models.by_name(MODEL_NAME)
    if model is not None:
        return _update_if_needed(col, model)
    return _create_notetype(col)


def _create_notetype(col) -> NotetypeDict:  # noqa: ANN001
    model = col.models.new(MODEL_NAME)

    for name in FIELDS:
        field = col.models.new_field(name)
        col.models.add_field(model, field)

    tmpl = col.models.new_template("Recognition")
    tmpl["qfmt"] = FRONT_TEMPLATE
    tmpl["afmt"] = BACK_TEMPLATE
    col.models.add_template(model, tmpl)

    model["css"] = CSS

    col.models.add(model)
    return model


def _update_if_needed(col, model: NotetypeDict) -> NotetypeDict:  # noqa: ANN001
    """Add any missing fields and update templates/css if they changed.
    This way we can add new fields in future versions without breaking
    existing installs."""
    existing_names = {f["name"] for f in model["flds"]}
    changed = False

    for name in FIELDS:
        if name not in existing_names:
            field = col.models.new_field(name)
            col.models.add_field(model, field)
            changed = True

    if model["css"] != CSS:
        model["css"] = CSS
        changed = True

    if model["tmpls"][0]["qfmt"] != FRONT_TEMPLATE:
        model["tmpls"][0]["qfmt"] = FRONT_TEMPLATE
        changed = True

    if model["tmpls"][0]["afmt"] != BACK_TEMPLATE:
        model["tmpls"][0]["afmt"] = BACK_TEMPLATE
        changed = True

    if changed:
        col.models.update_dict(model)

    return model
