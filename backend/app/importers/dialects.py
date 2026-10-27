"""Dialect varieties (Stage 2): Ukrainian dialect groups (наріччя) and dialects (говори), and
the regional areas of German (a pilot for dialects of other languages).

Territories are approximated by oblasts (ISO 3166-2 codes); an oblast can host several
dialects, e.g. Ivano-Frankivsk: Hutsul, Pokuttia-Bukovyna and Boyko. Lemko, Nadsian, Hutsul
and Bukovynian territories extend into Poland, Slovakia and Romania.

Run from backend/ after the regions importers:  uv run python -m app.importers.dialects
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Region, Variety


@dataclass(frozen=True)
class Dialect:
    code: str
    parent: str  # variety code
    kind: str  # "dialect_group" or "dialect"
    name_en: str
    name_uk: str
    regions: tuple[str, ...] = ()


DIALECTS: tuple[Dialect, ...] = (
    # Dialect groups (наріччя); their territory is the union of their dialects'.
    Dialect("ukr-north", "ukr", "dialect_group", "Northern Ukrainian dialects", "північне наріччя"),
    Dialect(
        "ukr-southwest",
        "ukr",
        "dialect_group",
        "South-Western Ukrainian dialects",
        "південно-західне наріччя",
    ),
    Dialect(
        "ukr-southeast",
        "ukr",
        "dialect_group",
        "South-Eastern Ukrainian dialects",
        "південно-східне наріччя",
    ),
    # Northern (Polissian) dialects
    Dialect(
        "ukr-polissia-west",
        "ukr-north",
        "dialect",
        "West Polissian dialect",
        "західнополіський говір",
        ("UA-07", "UA-56"),
    ),
    Dialect(
        "ukr-polissia-central",
        "ukr-north",
        "dialect",
        "Central Polissian dialect",
        "середньополіський говір",
        ("UA-18", "UA-32"),
    ),
    Dialect(
        "ukr-polissia-east",
        "ukr-north",
        "dialect",
        "East Polissian dialect",
        "східнополіський говір",
        ("UA-74", "UA-59"),
    ),
    # South-Western dialects
    Dialect(
        "ukr-volhynian",
        "ukr-southwest",
        "dialect",
        "Volhynian dialect",
        "волинський говір",
        ("UA-07", "UA-56", "UA-68"),
    ),
    Dialect(
        "ukr-podillian",
        "ukr-southwest",
        "dialect",
        "Podillian dialect",
        "подільський говір",
        ("UA-05", "UA-68"),
    ),
    Dialect(
        "ukr-dniester",
        "ukr-southwest",
        "dialect",
        "Dniester dialect",
        "наддністрянський говір",
        ("UA-46", "UA-61"),
    ),
    Dialect(
        "ukr-pokuttia-bukovyna",
        "ukr-southwest",
        "dialect",
        "Pokuttia-Bukovyna dialect",
        "покутсько-буковинський говір",
        ("UA-77", "UA-26", "RO-SV"),
    ),
    Dialect(
        "ukr-hutsul",
        "ukr-southwest",
        "dialect",
        "Hutsul dialect",
        "гуцульський говір",
        ("UA-26", "UA-77", "UA-21", "RO-MM"),
    ),
    Dialect(
        "ukr-boyko",
        "ukr-southwest",
        "dialect",
        "Boyko dialect",
        "бойківський говір",
        ("UA-46", "UA-26"),
    ),
    Dialect(
        "ukr-transcarpathian",
        "ukr-southwest",
        "dialect",
        "Transcarpathian dialect",
        "закарпатський говір",
        ("UA-21",),
    ),
    Dialect(
        "ukr-lemko",
        "ukr-southwest",
        "dialect",
        "Lemko dialect",
        "лемківський говір",
        ("PL-MA", "PL-PK", "SK-PV"),
    ),
    Dialect(
        "ukr-nadsian",
        "ukr-southwest",
        "dialect",
        "Nadsian (San) dialect",
        "надсянський говір",
        ("UA-46", "PL-PK"),
    ),
    # South-Eastern dialects
    Dialect(
        "ukr-middle-dnieper",
        "ukr-southeast",
        "dialect",
        "Middle Dnieper dialect",
        "середньонаддніпрянський говір",
        ("UA-32", "UA-30", "UA-71", "UA-53"),
    ),
    Dialect(
        "ukr-slobozhan",
        "ukr-southeast",
        "dialect",
        "Slobozhan dialect",
        "слобожанський говір",
        ("UA-63", "UA-59", "UA-09"),
    ),
    Dialect(
        "ukr-steppe",
        "ukr-southeast",
        "dialect",
        "Steppe dialect",
        "степовий говір",
        ("UA-51", "UA-48", "UA-65", "UA-23", "UA-12", "UA-14", "UA-35"),
    ),
    # German: regional everyday words (Brötchen / Schrippe / Semmel ...), by areas of states.
    # A pilot for dialects of other languages; words are drafts checked by speakers.
    Dialect("deu-regional", "deu", "dialect_group", "Regional German", "регіональна німецька"),
    Dialect(
        "deu-north",
        "deu-regional",
        "dialect",
        "German (Northern Germany)",
        "німецька — Північна Німеччина",
        ("DE-SH", "DE-HH", "DE-HB", "DE-NI"),
    ),
    Dialect(
        "deu-northeast",
        "deu-regional",
        "dialect",
        "German (Berlin, Brandenburg, Mecklenburg)",
        "німецька — Берлін, Бранденбург, Мекленбург",
        ("DE-BE", "DE-BB", "DE-MV"),
    ),
    Dialect(
        "deu-central-east",
        "deu-regional",
        "dialect",
        "German (Saxony, Thuringia, Saxony-Anhalt)",
        "німецька — Саксонія, Тюрингія, Саксонія-Ангальт",
        ("DE-SN", "DE-TH", "DE-ST"),
    ),
    Dialect(
        "deu-northrhine",
        "deu-regional",
        "dialect",
        "German (North Rhine-Westphalia)",
        "німецька — Північний Рейн — Вестфалія",
        ("DE-NW",),
    ),
    Dialect(
        "deu-central-west",
        "deu-regional",
        "dialect",
        "German (Hesse, Rhineland-Palatinate, Saarland)",
        "німецька — Гессен, Рейнланд-Пфальц, Саар",
        ("DE-HE", "DE-RP", "DE-SL"),
    ),
    Dialect(
        "deu-swabian",
        "deu-regional",
        "dialect",
        "German (Baden-Württemberg)",
        "німецька — Баден-Вюртемберг",
        ("DE-BW",),
    ),
    Dialect(
        "deu-bavarian",
        "deu-regional",
        "dialect",
        "German (Bavaria)",
        "німецька — Баварія",
        ("DE-BY",),
    ),
    Dialect(
        "deu-austria",
        "deu-regional",
        "dialect",
        "German (Austria)",
        "німецька — Австрія",
        tuple(f"AT-{n}" for n in range(1, 10)),
    ),
    Dialect(
        "deu-switzerland",
        "deu-regional",
        "dialect",
        "German (Switzerland)",
        "німецька — Швейцарія",
        tuple(f"CH-{c}" for c in "AG AI AR BE BL BS GL LU NW OW SG SH SO SZ TG UR ZG ZH".split()),
    ),
    # Italian: regional everyday Italian (anguria / cocomero / melone d'acqua ...), by areas of
    # regions; the regional languages (Sicilian, Neapolitan ...) are separate varieties.
    Dialect("ita-regional", "ita", "dialect_group", "Regional Italian", "регіональна італійська"),
    Dialect(
        "ita-northwest",
        "ita-regional",
        "dialect",
        "Italian (Piedmont, Liguria, Aosta Valley)",
        "італійська — П'ємонт, Лігурія, Валле-д'Аоста",
        ("IT-21", "IT-42", "IT-23"),
    ),
    Dialect(
        "ita-lombardy",
        "ita-regional",
        "dialect",
        "Italian (Lombardy)",
        "італійська — Ломбардія",
        ("IT-25",),
    ),
    Dialect(
        "ita-northeast",
        "ita-regional",
        "dialect",
        "Italian (Veneto, Trentino, Friuli)",
        "італійська — Венето, Трентіно, Фріулі",
        ("IT-34", "IT-32", "IT-36"),
    ),
    Dialect(
        "ita-emilia",
        "ita-regional",
        "dialect",
        "Italian (Emilia-Romagna)",
        "італійська — Емілія-Романья",
        ("IT-45",),
    ),
    Dialect(
        "ita-tuscany",
        "ita-regional",
        "dialect",
        "Italian (Tuscany)",
        "італійська — Тоскана",
        ("IT-52",),
    ),
    Dialect(
        "ita-center",
        "ita-regional",
        "dialect",
        "Italian (Lazio, Umbria, Marche, Abruzzo)",
        "італійська — Лаціо, Умбрія, Марке, Абруццо",
        ("IT-62", "IT-55", "IT-57", "IT-65"),
    ),
    Dialect(
        "ita-south",
        "ita-regional",
        "dialect",
        "Italian (Campania, Apulia, Calabria, Basilicata, Molise)",
        "італійська — Кампанія, Апулія, Калабрія, Базиліката, Молізе",
        ("IT-72", "IT-75", "IT-78", "IT-77", "IT-67"),
    ),
    Dialect(
        "ita-sicily",
        "ita-regional",
        "dialect",
        "Italian (Sicily)",
        "італійська — Сицилія",
        ("IT-82",),
    ),
    Dialect(
        "ita-sardinia",
        "ita-regional",
        "dialect",
        "Italian (Sardinia)",
        "італійська — Сардинія",
        ("IT-88",),
    ),
    # English: regional everyday words of the United States (soda / pop / coke) and of Britain
    # (bap / barm / cob / batch), by areas of states and regions.
    Dialect("eng-regional", "eng", "dialect_group", "Regional English", "регіональна англійська"),
    Dialect(
        "eng-us-newengland",
        "eng-regional",
        "dialect",
        "English (New England)",
        "англійська — Нова Англія",
        ("US-ME", "US-NH", "US-VT", "US-MA", "US-RI", "US-CT"),
    ),
    Dialect(
        "eng-us-midatlantic",
        "eng-regional",
        "dialect",
        "English (Mid-Atlantic US)",
        "англійська — Середньоатлантичні штати США",
        ("US-NY", "US-NJ", "US-PA", "US-DE", "US-MD", "US-DC"),
    ),
    Dialect(
        "eng-us-south",
        "eng-regional",
        "dialect",
        "English (Southern US)",
        "англійська — Південь США",
        (
            "US-VA",
            "US-WV",
            "US-NC",
            "US-SC",
            "US-GA",
            "US-FL",
            "US-AL",
            "US-MS",
            "US-TN",
            "US-KY",
            "US-AR",
            "US-LA",
            "US-TX",
            "US-OK",
        ),
    ),
    Dialect(
        "eng-us-midwest",
        "eng-regional",
        "dialect",
        "English (Midwestern US)",
        "англійська — Середній Захід США",
        (
            "US-OH",
            "US-IN",
            "US-IL",
            "US-MI",
            "US-WI",
            "US-MN",
            "US-IA",
            "US-MO",
            "US-ND",
            "US-SD",
            "US-NE",
            "US-KS",
        ),
    ),
    Dialect(
        "eng-us-west",
        "eng-regional",
        "dialect",
        "English (Western US)",
        "англійська — Захід США",
        (
            "US-MT",
            "US-WY",
            "US-CO",
            "US-NM",
            "US-AZ",
            "US-UT",
            "US-NV",
            "US-ID",
            "US-WA",
            "US-OR",
            "US-CA",
            "US-AK",
            "US-HI",
        ),
    ),
    Dialect(
        "eng-uk-northeast",
        "eng-regional",
        "dialect",
        "English (North East England)",
        "англійська — Північно-Східна Англія",
        ("GB-NE",),
    ),
    Dialect(
        "eng-uk-northwest",
        "eng-regional",
        "dialect",
        "English (North West England)",
        "англійська — Північно-Західна Англія",
        ("GB-NW",),
    ),
    Dialect(
        "eng-uk-yorkshire",
        "eng-regional",
        "dialect",
        "English (Yorkshire)",
        "англійська — Йоркшир",
        ("GB-YH",),
    ),
    Dialect(
        "eng-uk-eastmidlands",
        "eng-regional",
        "dialect",
        "English (East Midlands)",
        "англійська — Східний Мідленд",
        ("GB-EM",),
    ),
    Dialect(
        "eng-uk-westmidlands",
        "eng-regional",
        "dialect",
        "English (West Midlands)",
        "англійська — Західний Мідленд",
        ("GB-WM",),
    ),
    Dialect(
        "eng-uk-south",
        "eng-regional",
        "dialect",
        "English (London and South East England)",
        "англійська — Лондон і південний схід Англії",
        ("GB-LN", "GB-SE", "GB-EE"),
    ),
    Dialect(
        "eng-uk-southwest",
        "eng-regional",
        "dialect",
        "English (South West England)",
        "англійська — Південно-Західна Англія",
        ("GB-SW",),
    ),
    Dialect(
        "eng-uk-scotland",
        "eng-regional",
        "dialect",
        "English (Scotland)",
        "англійська — Шотландія",
        ("GB-SCT",),
    ),
    # Spanish: everyday words by country (palomitas / pochoclo / cabritas / canchita ...).
    Dialect("spa-regional", "spa", "dialect_group", "Regional Spanish", "регіональна іспанська"),
    Dialect(
        "spa-spain",
        "spa-regional",
        "dialect",
        "Spanish (Spain)",
        "іспанська — Іспанія",
        ("ESP",),
    ),
    Dialect(
        "spa-mexico",
        "spa-regional",
        "dialect",
        "Spanish (Mexico)",
        "іспанська — Мексика",
        ("MEX",),
    ),
    Dialect(
        "spa-caribbean",
        "spa-regional",
        "dialect",
        "Spanish (Cuba, Dominican Republic, Puerto Rico)",
        "іспанська — Куба, Домініканська Республіка, Пуерто-Рико",
        ("CUB", "DOM", "PRI"),
    ),
    Dialect(
        "spa-centralamerica",
        "spa-regional",
        "dialect",
        "Spanish (Central America)",
        "іспанська — Центральна Америка",
        ("GTM", "HND", "SLV", "NIC", "CRI", "PAN"),
    ),
    Dialect(
        "spa-colombia",
        "spa-regional",
        "dialect",
        "Spanish (Colombia)",
        "іспанська — Колумбія",
        ("COL",),
    ),
    Dialect(
        "spa-venezuela",
        "spa-regional",
        "dialect",
        "Spanish (Venezuela)",
        "іспанська — Венесуела",
        ("VEN",),
    ),
    Dialect(
        "spa-andes",
        "spa-regional",
        "dialect",
        "Spanish (Peru, Bolivia, Ecuador)",
        "іспанська — Перу, Болівія, Еквадор",
        ("PER", "BOL", "ECU"),
    ),
    Dialect(
        "spa-chile",
        "spa-regional",
        "dialect",
        "Spanish (Chile)",
        "іспанська — Чилі",
        ("CHL",),
    ),
    Dialect(
        "spa-rioplatense",
        "spa-regional",
        "dialect",
        "Spanish (Argentina, Uruguay, Paraguay)",
        "іспанська — Аргентина, Уругвай, Парагвай",
        ("ARG", "URY", "PRY"),
    ),
    # French: everyday words of France, Belgium, Switzerland and Quebec (septante, natel, char).
    Dialect("fra-regional", "fra", "dialect_group", "Regional French", "регіональна французька"),
    Dialect(
        "fra-france",
        "fra-regional",
        "dialect",
        "French (France)",
        "французька — Франція",
        ("FRA",),
    ),
    Dialect(
        "fra-southwest",
        "fra-regional",
        "dialect",
        "French (South-West France)",
        "французька — південний захід Франції",
        ("FR-NAQ", "FR-OCC"),
    ),
    Dialect(
        "fra-belgium",
        "fra-regional",
        "dialect",
        "French (Belgium)",
        "французька — Бельгія",
        ("BE-WAL", "BE-BRU"),
    ),
    Dialect(
        "fra-switzerland",
        "fra-regional",
        "dialect",
        "French (Switzerland)",
        "французька — Швейцарія",
        ("CH-GE", "CH-VD", "CH-NE", "CH-JU", "CH-FR", "CH-VS"),
    ),
    Dialect(
        "fra-quebec",
        "fra-regional",
        "dialect",
        "French (Quebec)",
        "французька — Квебек",
        ("CA-QC",),
    ),
    # Polish: regional everyday words (pyra, żymła, na polu / na dworze).
    Dialect("pol-regional", "pol", "dialect_group", "Regional Polish", "регіональна польська"),
    Dialect(
        "pol-mazovia",
        "pol-regional",
        "dialect",
        "Polish (Mazovia and Łódź)",
        "польська — Мазовія й Лодзь",
        ("PL-MZ", "PL-LD"),
    ),
    Dialect(
        "pol-greater-poland",
        "pol-regional",
        "dialect",
        "Polish (Greater Poland)",
        "польська — Велика Польща",
        ("PL-WP",),
    ),
    Dialect(
        "pol-lesser-poland",
        "pol-regional",
        "dialect",
        "Polish (Lesser Poland)",
        "польська — Мала Польща",
        ("PL-MA",),
    ),
    Dialect(
        "pol-silesia",
        "pol-regional",
        "dialect",
        "Polish (Silesia)",
        "польська — Сілезія",
        ("PL-SL", "PL-OP"),
    ),
    # Portuguese: everyday words of Portugal and Brazil (autocarro / ônibus).
    Dialect(
        "por-regional", "por", "dialect_group", "Regional Portuguese", "регіональна португальська"
    ),
    Dialect(
        "por-portugal",
        "por-regional",
        "dialect",
        "Portuguese (Portugal)",
        "португальська — Португалія",
        ("PRT",),
    ),
    Dialect(
        "por-brazil",
        "por-regional",
        "dialect",
        "Portuguese (Brazil)",
        "португальська — Бразилія",
        ("BRA",),
    ),
)


def upsert_dialects(session: Session) -> int:
    regions = {r.code: r for r in session.scalars(select(Region))}
    varieties = {v.code: v for v in session.scalars(select(Variety))}
    for dialect in DIALECTS:  # parents come first in DIALECTS
        variety = varieties.get(dialect.code)
        if variety is None:
            variety = Variety(code=dialect.code)
            session.add(variety)
            varieties[dialect.code] = variety
        variety.name_en = dialect.name_en
        variety.name_uk = dialect.name_uk
        variety.kind = dialect.kind
        variety.iso639_3 = None
        variety.parent = varieties[dialect.parent]
        missing = [code for code in dialect.regions if code not in regions]
        if missing:
            print(f"  warning: no region for {dialect.code}: {missing}")
        variety.regions = [regions[code] for code in dialect.regions if code in regions]
    session.flush()
    return len(DIALECTS)


def main() -> None:
    with SessionLocal() as session:
        count = upsert_dialects(session)
        session.commit()
    print(f"Upserted {count} dialect varieties.")


if __name__ == "__main__":
    main()
