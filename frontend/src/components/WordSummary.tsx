"use client";

import { useLocale, useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { type ConceptDetail, type LanguageForms, localized } from "@/lib/api";

// Languages quoted in the summary, in this order (the most searched ones).
const SUMMARY_LANGUAGES = ["eng", "ukr", "deu", "fra", "spa", "pol", "ita"];
const SUMMARY_EXAMPLES = 5;

type Variant = { word: string; dialects: string[] };

/** Dialect words that differ from standard Ukrainian, with the dialects that use them. */
function dialectVariants(concept: ConceptDetail, locale: string): Variant[] {
  const standard = new Set(
    concept.languages
      .filter((lang) => lang.code === "ukr")
      .flatMap((lang) => lang.forms.map((f) => f.spelling.toLowerCase())),
  );
  const dialects = new Map<string, string[]>();
  for (const lang of concept.languages) {
    if (lang.kind !== "dialect") continue;
    for (const form of lang.forms) {
      const word = form.spelling.toLowerCase();
      if (standard.has(word)) continue;
      const names = dialects.get(word) ?? [];
      names.push(localized(locale, lang.name_en, lang.name_uk));
      dialects.set(word, names);
    }
  }
  return [...dialects.entries()]
    .sort((a, b) => b[1].length - a[1].length)
    .map(([word, names]) => ({ word, dialects: names }));
}

/** The same word in the most searched languages, e.g. "potato (English)". */
function worldExamples(concept: ConceptDetail, locale: string): string[] {
  const own = locale === "uk" ? "ukr" : "eng";
  return SUMMARY_LANGUAGES.filter((code) => code !== own)
    .map((code) => concept.languages.find((lang) => lang.code === code))
    .filter((lang): lang is LanguageForms => lang !== undefined && lang.forms.length > 0)
    .slice(0, SUMMARY_EXAMPLES)
    .map((lang) => `${lang.forms[0].spelling} (${localized(locale, lang.name_en, lang.name_uk)})`);
}

/** Readable text about the word, rendered on the server for search engines and people. */
export function WordIntro({ concept }: { concept: ConceptDetail }) {
  const locale = useLocale();
  const t = useTranslations("Word");
  const word = localized(locale, concept.gloss_en, concept.gloss_uk);
  const variants = dialectVariants(concept, locale);
  const examples = worldExamples(concept, locale);

  return (
    <div className="space-y-2 pt-3 text-sm leading-relaxed">
      {variants.length > 0 && (
        <p>
          {t("dialectIntro", { word })}{" "}
          {variants.map((variant, i) => (
            <span key={variant.word}>
              {i > 0 && "; "}
              <Link
                href={`/slovo/${encodeURIComponent(variant.word)}`}
                className="font-semibold text-violet-800 underline-offset-2 hover:underline dark:text-violet-300"
              >
                {variant.word}
              </Link>{" "}
              ({variant.dialects.join(", ")})
            </span>
          ))}
          .
        </p>
      )}
      {examples.length > 0 && (
        <p className="opacity-80">{t("worldIntro", { list: examples.join(", ") })}</p>
      )}
    </div>
  );
}

/** Links to other word pages. */
export function RelatedWords({ concept }: { concept: ConceptDetail }) {
  const locale = useLocale();
  const t = useTranslations("Word");
  const related = concept.related ?? []; // missing from data cached before the API had it
  if (related.length === 0) return null;

  return (
    <nav className="py-4">
      <h2 className="mb-2 text-xs tracking-wide uppercase opacity-60">{t("related")}</h2>
      <ul className="flex flex-wrap gap-2">
        {related.map((link) => (
          <li key={link.slug}>
            <Link
              href={`/word/${link.slug}`}
              className="inline-block rounded-full border border-black/15 px-3 py-1 text-sm hover:bg-black/5 dark:border-white/20 dark:hover:bg-white/10"
            >
              {localized(locale, link.gloss_en, link.gloss_uk)}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
