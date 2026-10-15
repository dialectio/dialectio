"""Translators' notes are removed from Wiktionary translations (app.importers.wiktionary)."""

import pytest

from app.importers.wiktionary import clean_translation


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("banować (on the internet)", "banować"),
        ("acordarse/arrecordarse/alcordarse de", "acordarse"),
        ("sentir saudade(s) de", "sentir saudade de"),
        ("발표(發表)하다", "발표하다"),
        ("(-analyste) programmeur", "programmeur"),
        ("aus) bestehen", "bestehen"),
        ("(voor) altijd", "altijd"),
        ("kokrriz (gheg)", "kokrriz"),
        ("Brötchen", "Brötchen"),
    ],
)
def test_notes_are_removed(raw: str, clean: str) -> None:
    assert clean_translation(raw) == clean


@pytest.mark.parametrize("raw", ["orquestra (disused)", "damnado (desus.)", 'bokmål" tinn', "()"])
def test_unusable_translations_are_dropped(raw: str) -> None:
    assert clean_translation(raw) is None
