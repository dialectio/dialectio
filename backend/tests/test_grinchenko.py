"""Reading entries of Hrinchenko's dictionary (app.importers.grinchenko)."""

from app.importers.grinchenko import parse


def test_regional_entry() -> None:
    entry = parse("верстак", "'''Верста́к, ка́,''' ''м.'' Ровесникъ. Шух. I. 32.")
    assert entry is not None
    assert entry.word == "Верста́к" and entry.plain == "верстак"
    assert entry.meanings == ["ровесник"]
    assert entry.dialects == {"ukr-hutsul"} and not entry.other_sources


def test_entry_also_cited_from_literature_is_not_regional() -> None:
    entry = parse("гай", "'''Га́й, га́ю,''' ''м.'' Роща, небольшой лѣсъ. Вас. 206. Шух. I. 5.")
    assert entry is not None and entry.other_sources


def test_place_outside_our_list_makes_it_not_regional() -> None:
    entry = parse("рихтик", "'''Ри́хтик,''' ''нар.'' Совершенно. Уман. у. Черниг. у.")
    assert entry is not None and entry.other_sources


def test_descriptions_and_several_meanings_are_not_matched() -> None:
    described = parse("джуфо", "'''Джуфо́, фа́,''' ''м.'' Парень, хорошо играющій. Шух. I. 33.")
    several = parse("бухтіти", "'''Бухті́ти,''' ''гл.'' 1) Пылать. Харьк. 2) Звучать. Харьк.")
    assert described is not None and described.meanings == []
    assert several is not None and several.meanings == []


def test_cross_references_are_skipped() -> None:
    assert parse("гайвір", "'''Га́йвір, ру,''' ''м.'' = '''Гав'яр'''. Св. Л. 271.") is None
