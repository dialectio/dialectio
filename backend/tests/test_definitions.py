"""Picking a word's meaning from another language's Wiktionary (app.importers.definitions)."""

from app.importers.definitions import clean, entry_definitions, sense_numbers


def test_sense_numbers() -> None:
    assert sense_numbers("1.1") == ["1.1"]
    assert sense_numbers(2) == ["2"]
    assert sense_numbers("1,3") == ["1", "3"]
    assert sense_numbers("4–5") == ["4", "5"]


def test_numbered_senses_are_matched_by_english_translation() -> None:
    zamek = {
        "senses": [
            {"glosses": ["budynek warowny"], "sense_index": "1.1"},
            {"glosses": ["mechanizm zamykający drzwi"], "sense_index": "1.2"},
        ],
        "translations": [
            {"lang_code": "en", "word": "castle", "sense_index": "1.1"},
            {"lang_code": "en", "word": "lock", "sense_index": "1.2"},
        ],
    }
    assert entry_definitions(zamek, {"lock"})[0] == ["mechanizm zamykający drzwi"]
    assert entry_definitions(zamek, {"castle"})[0] == ["budynek warowny"]
    assert entry_definitions(zamek, {"key"})[0] == []


def test_french_senses_are_matched_by_the_translation_label() -> None:
    # French numbers translation groups, not senses: sense_index 2 is not the second sense
    creche = {
        "senses": [
            {"glosses": ["Mangeoire des bœufs."]},
            {"glosses": ["Mangeoire où Jésus-Christ aurait été mis."]},
            {"glosses": ["Établissement accueillant les enfants qui ne sont pas scolarisés."]},
        ],
        "translations": [
            {
                "lang_code": "en",
                "word": "nursery",
                "sense": "Établissement pour les très jeunes enfants",
                "sense_index": 2,
            }
        ],
    }
    assert entry_definitions(creche, {"nursery"})[0] == [
        "Établissement accueillant les enfants qui ne sont pas scolarisés."
    ]


def test_inflected_forms_are_not_definitions() -> None:
    entry = {"senses": [{"glosses": ["Participio de atemorizar"]}], "translations": []}
    assert entry_definitions(entry, {"frightened"}) == ([], [])


def test_clean() -> None:
    assert clean("samiec psa (1.1).") == "samiec psa"
    assert clean("…podkreślająca, że coś minęło") == "podkreślająca, że coś minęło"
    assert clean("zob. zamek błyskawiczny") is None
    long = "Erste Erklärung des Wortes, " + "sehr lang " * 40
    assert len(clean(long) or "") <= 300
