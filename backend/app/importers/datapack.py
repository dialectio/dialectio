"""Data packs: move words built on a workstation to the live site without touching its people.

The heavy imports (Wiktionary, machine translation, Piper voices) run on a workstation; the
live database also holds accounts, votes and the change log, so it can't be replaced by a
dump any more. A pack carries chosen concepts (or every word of chosen varieties) with their
words, sources, the varieties they need, recordings and our own audio files:

    python -m app.importers.datapack export pack.zip --concepts glasses --varieties pol-silesia
    python -m app.importers.datapack apply pack.zip       # on the server, in the backend
    python -m app.importers.datapack remove hmm huh eh    # drop concepts, here and there

Applying adds and updates, never deletes, and words made by people win: a word an editor or
member added (or approved) keeps its spelling, status and main-word choice. Concepts are
matched by slug (slugs are permanent), varieties by code, words by concept + variety +
spelling, so votes on existing words stay with them.
"""

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.api.word_actions import OWN_SOURCES
from app.config import MEDIA_DIR, MEDIA_URL_PREFIX
from app.db.session import SessionLocal
from app.models import (
    APPROVED,
    Audio,
    Concept,
    Form,
    Region,
    Report,
    Source,
    Variety,
    Vote,
    variety_region,
)

VERSION = 1
CONCEPT_FIELDS = (
    "gloss_en",
    "gloss_uk",
    "description_en",
    "description_uk",
    "glosses",
    "descriptions",
    "description_origins",
    "wikidata_id",
    "category",
)
VARIETY_FIELDS = ("name_en", "name_uk", "names", "kind", "iso639_3", "glottocode", "wikidata_id")
FORM_FIELDS = ("ipa", "transliteration", "note", "is_primary", "status", "external_id")


def own_media(url: str) -> Path | None:
    """The file behind one of our own audio URLs ("/media/tts/...")."""
    prefix = f"{MEDIA_URL_PREFIX}/"
    return MEDIA_DIR / url.removeprefix(prefix) if url.startswith(prefix) else None


# --- export ----------------------------------------------------------------------------


def export(path: Path, slugs: list[str], variety_codes: list[str]) -> None:
    with SessionLocal() as session:
        query = (
            select(Form)
            .join(Concept, Concept.id == Form.concept_id)
            .join(Variety, Variety.id == Form.variety_id)
            .options(
                selectinload(Form.concept),
                selectinload(Form.variety),
                selectinload(Form.source),
                selectinload(Form.audio).selectinload(Audio.form),
            )
        )
        forms: list[Form] = []
        if slugs:
            missing = set(slugs) - set(
                session.scalars(select(Concept.slug).where(Concept.slug.in_(slugs)))
            )
            if missing:
                sys.exit(f"Unknown concepts: {', '.join(sorted(missing))}")
            forms += session.scalars(query.where(Concept.slug.in_(slugs))).all()
        if variety_codes:
            forms += session.scalars(query.where(Variety.code.in_(variety_codes))).all()
        forms = list({f.id: f for f in forms}.values())
        if not forms and not slugs:
            sys.exit("Nothing to export")

        concepts = {f.concept.slug: f.concept for f in forms if f.concept.slug}
        concepts.update(
            {c.slug: c for c in session.scalars(select(Concept).where(Concept.slug.in_(slugs)))}
        )
        varieties = {f.variety.code: f.variety for f in forms}
        for code in variety_codes:  # a variety without words yet still travels
            variety = session.scalar(select(Variety).where(Variety.code == code))
            if variety:
                varieties[code] = variety
        # Parents first, so applying can link each variety to one that exists
        for variety in list(varieties.values()):
            parent = variety.parent
            while parent is not None and parent.code not in varieties:
                varieties[parent.code] = parent
                parent = parent.parent
        sources: dict[str, Source] = {}
        files: dict[str, Path] = {}
        pack_forms = []
        for form in forms:
            if not form.concept.slug:
                continue
            if form.source:
                sources[form.source.name] = form.source
            audio = []
            for a in form.audio:
                if a.source:
                    sources[a.source.name] = a.source
                file = own_media(a.url)
                if file is not None and file.exists():
                    files[a.url] = file
                audio.append(
                    {
                        "url": a.url,
                        "speaker": a.speaker,
                        "is_synthetic": a.is_synthetic,
                        "license": a.license,
                        "source": a.source.name if a.source else None,
                    }
                )
            pack_forms.append(
                {
                    "concept": form.concept.slug,
                    "variety": form.variety.code,
                    "spelling": form.spelling,
                    **{field: getattr(form, field) for field in FORM_FIELDS},
                    "source": form.source.name if form.source else None,
                    "audio": audio,
                }
            )
        regions = {v.code: sorted(r.code for r in v.regions) for v in varieties.values()}
        pack = {
            "version": VERSION,
            "concepts": [
                {"slug": slug, **{f: getattr(c, f) for f in CONCEPT_FIELDS}}
                for slug, c in sorted(concepts.items())
            ],
            "varieties": [
                {
                    "code": v.code,
                    "parent": v.parent.code if v.parent else None,
                    "regions": regions[v.code],
                    **{f: getattr(v, f) for f in VARIETY_FIELDS},
                }
                for v in sorted(varieties.values(), key=depth)
            ],
            "sources": [
                {"name": s.name, "url": s.url, "license": s.license}
                for s in sorted(sources.values(), key=lambda s: s.name)
            ],
            "forms": pack_forms,
        }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("pack.json", json.dumps(pack, ensure_ascii=False))
        for url, file in files.items():
            archive.write(file, f"media/{url.removeprefix(MEDIA_URL_PREFIX + '/')}")
    print(
        f"{path}: {len(pack['concepts'])} concepts, {len(pack['varieties'])} varieties, "
        f"{len(pack_forms)} words, {len(files)} audio files"
    )


def depth(variety: Variety) -> int:
    level, parent = 0, variety.parent
    while parent is not None:
        level, parent = level + 1, parent.parent
    return level


# --- apply -----------------------------------------------------------------------------


def apply(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        pack = json.loads(archive.read("pack.json"))
        if pack.get("version") != VERSION:
            sys.exit(f"Pack version {pack.get('version')}, expected {VERSION}")
        copied = 0
        for name in archive.namelist():
            if name.startswith("media/") and not name.endswith("/"):
                target = MEDIA_DIR / name.removeprefix("media/")
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(name))
                    copied += 1
    with SessionLocal() as session:
        counts = apply_pack(session, pack)
        session.commit()
    print(f"{path}: {counts}, {copied} new audio files")


def apply_pack(session: Session, pack: dict[str, Any]) -> dict[str, int]:
    counts = dict.fromkeys(("concepts", "varieties", "added", "updated", "kept", "audio"), 0)
    sources = {}
    for item in pack["sources"]:
        source = session.scalar(select(Source).where(Source.name == item["name"]))
        if source is None:
            source = Source(name=item["name"])
            session.add(source)
        source.url, source.license = item["url"], item["license"]
        sources[item["name"]] = source

    varieties: dict[str, Variety] = {}
    for item in pack["varieties"]:
        variety = session.scalar(select(Variety).where(Variety.code == item["code"]))
        if variety is None:
            variety = Variety(code=item["code"])
            session.add(variety)
            counts["varieties"] += 1
        for field in VARIETY_FIELDS:
            setattr(variety, field, item[field])
        variety.parent = varieties.get(item["parent"]) or (
            session.scalar(select(Variety).where(Variety.code == item["parent"]))
            if item["parent"]
            else None
        )
        session.flush()
        if item["regions"]:
            region_ids = session.scalars(
                select(Region.id).where(Region.code.in_(item["regions"]))
            ).all()
            session.execute(delete(variety_region).where(variety_region.c.variety_id == variety.id))
            session.execute(
                variety_region.insert(),
                [{"variety_id": variety.id, "region_id": r} for r in set(region_ids)],
            )
        varieties[item["code"]] = variety

    concepts: dict[str, Concept] = {}
    for item in pack["concepts"]:
        concept = session.scalar(select(Concept).where(Concept.slug == item["slug"]))
        if concept is None and item["wikidata_id"]:
            concept = session.scalar(
                select(Concept).where(Concept.wikidata_id == item["wikidata_id"])
            )
            if concept is not None and concept.slug:
                print(f"skipped {item['slug']}: its Wikidata item has the page {concept.slug}")
                continue
        if concept is None:
            concept = Concept(slug=item["slug"])
            session.add(concept)
            counts["concepts"] += 1
        concept.slug = concept.slug or item["slug"]
        for field in CONCEPT_FIELDS:
            setattr(concept, field, item[field])
        concepts[item["slug"]] = concept
    session.flush()

    for item in pack["forms"]:
        concept, variety = concepts.get(item["concept"]), varieties.get(item["variety"])
        if concept is None or variety is None:
            continue
        others = session.scalars(
            select(Form)
            .where(Form.concept_id == concept.id, Form.variety_id == variety.id)
            .options(selectinload(Form.source), selectinload(Form.audio))
        ).all()
        form = next((f for f in others if f.spelling == item["spelling"]), None)
        own = form is not None and form.source is not None and form.source.name in OWN_SOURCES
        if own and form.status == APPROVED:
            counts["kept"] += 1  # an editor's or member's word: theirs to change
        else:
            if form is None:
                form = Form(concept=concept, variety=variety, spelling=item["spelling"])
                session.add(form)
                counts["added"] += 1
            else:
                counts["updated"] += 1
            for field in FORM_FIELDS:
                if field != "is_primary":
                    setattr(form, field, item[field])
            form.source = sources.get(item["source"])
            # The main word: only where no person chose one
            chosen = any(
                o.is_primary and o.source is not None and o.source.name in OWN_SOURCES
                for o in others
                if o is not form
            )
            if item["is_primary"] and not chosen:
                for other in others:
                    if other is not form:
                        other.is_primary = False
                form.is_primary = True
            elif not item["is_primary"]:
                form.is_primary = False
        session.flush()
        known = {a.url for a in form.audio}
        for a in item["audio"]:
            if a["url"] not in known:
                form.audio.append(
                    Audio(
                        url=a["url"],
                        speaker=a["speaker"],
                        is_synthetic=a["is_synthetic"],
                        license=a["license"],
                        source=sources.get(a["source"]),
                    )
                )
                counts["audio"] += 1
    return counts


# --- remove ----------------------------------------------------------------------------


def remove(slugs: list[str]) -> None:
    """Drop concepts with their words, recordings (and our audio files), votes and reports."""
    with SessionLocal() as session:
        for slug in slugs:
            concept = session.scalar(select(Concept).where(Concept.slug == slug))
            if concept is None:
                print(f"{slug}: not here")
                continue
            forms = session.scalars(
                select(Form).where(Form.concept_id == concept.id).options(selectinload(Form.audio))
            ).all()
            form_ids = [f.id for f in forms]
            files = [own_media(a.url) for f in forms for a in f.audio]
            session.execute(delete(Vote).where(Vote.form_id.in_(form_ids)))
            session.execute(delete(Report).where(Report.form_id.in_(form_ids)))
            for form in forms:
                session.delete(form)
            session.flush()
            session.delete(concept)
            session.commit()
            for file in files:
                if file is not None:
                    file.unlink(missing_ok=True)
            print(f"{slug}: removed with {len(forms)} words")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    out = commands.add_parser("export", help="pack concepts and varieties into a zip file")
    out.add_argument("pack", type=Path)
    out.add_argument("--concepts", nargs="*", default=[], help="concept slugs")
    out.add_argument("--varieties", nargs="*", default=[], help="variety codes: all their words")
    into = commands.add_parser("apply", help="add or update what a pack holds")
    into.add_argument("pack", type=Path)
    drop = commands.add_parser("remove", help="delete concepts by slug")
    drop.add_argument("slugs", nargs="+")
    args = parser.parse_args()
    if args.command == "export":
        export(args.pack, args.concepts, args.varieties)
    elif args.command == "apply":
        apply(args.pack)
    else:
        remove(args.slugs)


if __name__ == "__main__":
    main()
