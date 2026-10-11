"""Interface languages beyond Ukrainian and English.

Ukrainian and English names live in the `*_uk` / `*_en` columns; names in these languages
in the JSON `names` / `glosses` / `descriptions` columns, keyed by the locale code.
"""

# Interface locale -> the variety whose words name a concept in that language
EXTRA_LOCALES: dict[str, str] = {"pl": "pol", "de": "deu", "es": "spa", "fr": "fra"}
