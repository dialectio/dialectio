"""Languages imported at country level (Stage 1).

`countries` are Natural Earth ADM0_A3 codes where the language is the main/official one,
or ISO 3166-2 codes of first-level regions for regional languages (e.g. Crimean Tatar).
`lemma_tag` is the Wikidata lemma language tag to use (filters out other scripts).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    wikidata_id: str
    iso639_3: str
    lemma_tag: str
    name_en: str
    name_uk: str
    countries: tuple[str, ...]


LANGUAGES: tuple[Language, ...] = (
    Language("Q8798", "ukr", "uk", "Ukrainian", "українська", ("UKR",)),
    Language(
        "Q1860", "eng", "en", "English", "англійська", ("GBR", "USA", "CAN", "AUS", "NZL", "IRL")
    ),
    Language("Q188", "deu", "de", "German", "німецька", ("DEU", "AUT", "CHE", "LIE")),
    Language("Q150", "fra", "fr", "French", "французька", ("FRA", "BEL", "CHE", "LUX", "MCO")),
    Language(
        "Q1321",
        "spa",
        "es",
        "Spanish",
        "іспанська",
        (
            "ESP",
            "MEX",
            "ARG",
            "COL",
            "PER",
            "VEN",
            "CHL",
            "ECU",
            "GTM",
            "CUB",
            "BOL",
            "DOM",
            "HND",
            "PRY",
            "SLV",
            "NIC",
            "CRI",
            "PAN",
            "URY",
        ),
    ),
    Language("Q652", "ita", "it", "Italian", "італійська", ("ITA", "SMR", "CHE")),
    Language("Q5146", "por", "pt", "Portuguese", "португальська", ("PRT", "BRA", "AGO", "MOZ")),
    Language("Q809", "pol", "pl", "Polish", "польська", ("POL",)),
    Language("Q9056", "ces", "cs", "Czech", "чеська", ("CZE",)),
    Language("Q9058", "slk", "sk", "Slovak", "словацька", ("SVK",)),
    Language("Q9091", "bel", "be", "Belarusian", "білоруська", ("BLR",)),
    Language("Q7737", "rus", "ru", "Russian", "російська", ("RUS",)),
    Language("Q7918", "bul", "bg", "Bulgarian", "болгарська", ("BGR",)),
    Language("Q9299", "srp", "sr", "Serbian", "сербська", ("SRB", "MNE")),
    Language("Q6654", "hrv", "hr", "Croatian", "хорватська", ("HRV",)),
    Language("Q9063", "slv", "sl", "Slovene", "словенська", ("SVN",)),
    Language("Q7913", "ron", "ro", "Romanian", "румунська", ("ROU", "MDA")),
    Language("Q9067", "hun", "hu", "Hungarian", "угорська", ("HUN",)),
    Language("Q7411", "nld", "nl", "Dutch", "нідерландська", ("NLD", "BEL")),
    Language("Q9027", "swe", "sv", "Swedish", "шведська", ("SWE",)),
    Language("Q25167", "nob", "nb", "Norwegian Bokmål", "норвезька (букмол)", ("NOR",)),
    Language("Q9035", "dan", "da", "Danish", "данська", ("DNK",)),
    Language("Q1412", "fin", "fi", "Finnish", "фінська", ("FIN",)),
    Language("Q9072", "est", "et", "Estonian", "естонська", ("EST",)),
    Language("Q9078", "lav", "lv", "Latvian", "латиська", ("LVA",)),
    Language("Q9083", "lit", "lt", "Lithuanian", "литовська", ("LTU",)),
    Language("Q36510", "ell", "el", "Greek", "грецька", ("GRC", "CYP")),
    Language("Q256", "tur", "tr", "Turkish", "турецька", ("TUR",)),
    Language("Q8108", "kat", "ka", "Georgian", "грузинська", ("GEO",)),
    Language("Q8785", "hye", "hy", "Armenian", "вірменська", ("ARM",)),
    Language("Q9288", "heb", "he", "Hebrew", "іврит", ("ISR",)),
    Language("Q9168", "fas", "fa", "Persian", "перська", ("IRN",)),
    Language("Q1568", "hin", "hi", "Hindi", "гінді", ("IND",)),
    Language("Q5287", "jpn", "ja", "Japanese", "японська", ("JPN",)),
    Language("Q9176", "kor", "ko", "Korean", "корейська", ("KOR", "PRK")),
    # European languages added later (mostly covered by concept labels, few lexemes)
    Language("Q8748", "sqi", "sq", "Albanian", "албанська", ("ALB",)),
    Language("Q9296", "mkd", "mk", "Macedonian", "македонська", ("MKD",)),
    Language("Q9303", "bos", "bs", "Bosnian", "боснійська", ("BIH",)),
    Language("Q294", "isl", "is", "Icelandic", "ісландська", ("ISL",)),
    Language("Q9142", "gle", "ga", "Irish", "ірландська", ("IRL",)),
    Language("Q9166", "mlt", "mt", "Maltese", "мальтійська", ("MLT",)),
    Language("Q9051", "ltz", "lb", "Luxembourgish", "люксембурзька", ("LUX",)),
    Language("Q7026", "cat", "ca", "Catalan", "каталанська", ("AND", "ES-CT", "ES-VC", "ES-IB")),
    Language("Q397", "lat", "la", "Latin", "латина", ("VAT",)),
    # Regional languages of Western Europe, mapped to their regions (approximate areas: the
    # regions where the language is traditionally spoken, not exact boundaries)
    Language("Q9309", "cym", "cy", "Welsh", "валлійська", ("GB-WLS",)),
    Language("Q9314", "gla", "gd", "Scottish Gaelic", "шотландська гельська", ("GB-SCT",)),
    Language("Q14549", "sco", "sco", "Scots", "шотландська (scots)", ("GB-SCT",)),
    Language("Q12107", "bre", "br", "Breton", "бретонська", ("FR-BRE",)),
    Language("Q14185", "oci", "oc", "Occitan", "окситанська", ("FR-OCC", "FR-PAC", "FR-NAQ")),
    Language("Q33111", "cos", "co", "Corsican", "корсиканська", ("FR-COR",)),
    Language("Q9307", "glg", "gl", "Galician", "галісійська", ("ES-GA",)),
    Language("Q8752", "eus", "eu", "Basque", "баскська", ("ES-PV", "ES-NC")),
    Language("Q29507", "ast", "ast", "Asturian", "астурійська", ("ES-AS",)),
    Language("Q8765", "arg", "an", "Aragonese", "арагонська", ("ES-AR",)),
    Language("Q33973", "scn", "scn", "Sicilian", "сицилійська", ("IT-82",)),
    Language("Q33845", "nap", "nap", "Neapolitan", "неаполітанська", ("IT-72",)),
    Language("Q32724", "vec", "vec", "Venetian", "венеційська", ("IT-34",)),
    Language("Q33754", "lmo", "lmo", "Lombard", "ломбардська", ("IT-25",)),
    Language("Q15085", "pms", "pms", "Piedmontese", "п'ємонтська", ("IT-21",)),
    Language("Q36106", "lij", "lij", "Ligurian", "лігурійська", ("IT-42",)),
    Language("Q33441", "fur", "fur", "Friulian", "фріульська", ("IT-36",)),
    Language("Q33976", "srd", "sc", "Sardinian", "сардинська", ("IT-88",)),
    Language("Q27175", "fry", "fy", "West Frisian", "західнофризька", ("NL-FR",)),
    Language("Q102172", "lim", "li", "Limburgish", "лімбурзька", ("NL-LI",)),
    Language(
        "Q25433",
        "nds",
        "nds",
        "Low German",
        "нижньонімецька",
        ("DE-SH", "DE-HH", "DE-HB", "DE-NI", "DE-MV"),
    ),
    Language("Q28224", "frr", "frr", "North Frisian", "північнофризька", ("DE-SH",)),
    Language(
        "Q29540",
        "bar",
        "bar",
        "Bavarian",
        "баварська",
        ("DE-BY", "AT-1", "AT-2", "AT-3", "AT-4", "AT-5", "AT-6", "AT-7", "AT-9"),
    ),
    Language(
        "Q131339",
        "gsw",
        "gsw",
        "Alemannic (Swiss German)",
        "алеманська (швейцарська німецька)",
        (
            "DE-BW",
            "AT-8",
            *(f"CH-{c}" for c in "AG AI AR BE BL BS GL LU NW OW SG SH SO SZ TG UR ZG ZH".split()),
        ),
    ),
    Language("Q13248", "hsb", "hsb", "Upper Sorbian", "верхньолужицька", ("DE-SN",)),
    Language("Q34219", "wln", "wa", "Walloon", "валлонська", ("BE-WAL",)),
    Language("Q13199", "roh", "rm", "Romansh", "ретороманська", ("CH-GR",)),
    Language("Q33690", "csb", "csb", "Kashubian", "кашубська", ("PL-PM",)),
    Language("Q30319", "szl", "szl", "Silesian", "сілезька", ("PL-SL",)),
    # Indigenous language of Ukraine, mapped to Crimea and Sevastopol
    Language("Q33357", "crh", "crh", "Crimean Tatar", "кримськотатарська", ("UA-43", "UA-40")),
    # Neighbouring regions
    Language("Q9252", "kaz", "kk", "Kazakh", "казахська", ("KAZ",)),
    Language("Q9292", "aze", "az", "Azerbaijani", "азербайджанська", ("AZE",)),
    Language("Q9264", "uzb", "uz", "Uzbek", "узбецька", ("UZB",)),
    Language("Q9267", "tuk", "tk", "Turkmen", "туркменська", ("TKM",)),
    Language("Q9255", "kir", "ky", "Kyrgyz", "киргизька", ("KGZ",)),
    Language("Q9260", "tgk", "tg", "Tajik", "таджицька", ("TJK",)),
    Language("Q9246", "mon", "mn", "Mongolian", "монгольська", ("MNG",)),
    Language(
        "Q13955",
        "ara",
        "ar",
        "Arabic",
        "арабська",
        tuple(
            "EGY SAU DZA MAR TUN LBY IRQ SYR JOR LBN YEM OMN ARE QAT KWT BHR SDN PSX MRT".split()
        ),
    ),
)
