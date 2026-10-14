"""Translate English texts with Argos Translate (offline machine translation).

Runs in its own environment, not the project's (Argos pulls in torch):
    uvx --from argostranslate python argos_translate.py <in.json> <out.json>
in.json: {"to": ["uk", "pl"], "texts": ["...", ...]}; out.json: {"uk": [...], "pl": [...]}
Language models are downloaded on first use.
"""

import json
import sys

import argostranslate.package
import argostranslate.translate


def ensure_model(to: str) -> None:
    installed = {(p.from_code, p.to_code) for p in argostranslate.package.get_installed_packages()}
    if ("en", to) in installed:
        return
    argostranslate.package.update_package_index()
    package = next(
        p
        for p in argostranslate.package.get_available_packages()
        if p.from_code == "en" and p.to_code == to
    )
    argostranslate.package.install_from_path(package.download())


def main(source: str, target: str) -> None:
    request = json.load(open(source, encoding="utf-8"))
    result = {}
    for to in request["to"]:
        ensure_model(to)
        translation = argostranslate.translate.get_translation_from_codes("en", to)
        result[to] = []
        for i, text in enumerate(request["texts"]):
            result[to].append(translation.translate(text))
            if i % 500 == 499:
                print(f"{to}: {i + 1}/{len(request['texts'])}", flush=True)
    json.dump(result, open(target, "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
