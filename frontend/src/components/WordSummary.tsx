"use client";

import { useLocale, useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import {
  capitalize,
  type ConceptDetail,
  type LanguageForms,
  LOCALE_LANGUAGE,
  localized,
} from "@/lib/api";

// Languages quoted in the summary, in this order (the most searched ones).
const SUMMARY_LANGUAGES = ["eng", "ukr", "deu", "fra", "spa", "pol", "ita"];
const SUMMARY_EXAMPLES = 5;

type Variant = { word: string; dialects: string[] };

/** Languages whose dialects use this concept ("ukr" for ukr-hutsul, "deu" for deu-north). */
function dialectLanguages(concept: ConceptDetail): string[] {
  const codes = concept.languages
    .filter((lang) => lang.kind === "dialect")
    .map((lang) => lang.code.split("-")[0]);
  // Ukrainian first, the others in the order they appear
  return [...new Set(codes)].sort(
    (a, b) => Number(b === "ukr") - Number(a === "ukr"),
  );
}

/** Dialect words of one language that differ from its standard word, with their areas. */
function dialectVariants(
  concept: ConceptDetail,
  locale: string,
  language: string,
): Variant[] {
  const standard = new Set(
    concept.languages
      .filter((lang) => lang.code === language)
      .flatMap((lang) => lang.forms.map((f) => f.spelling.toLowerCase())),
  );
  const dialects = new Map<string, Variant>();
  for (const lang of concept.languages) {
    if (lang.kind !== "dialect" || !lang.code.startsWith(`${language}-`))
      continue;
    // "німецька — Баварія", "German (Bavaria)" -> "Баварія", "Bavaria": the language is
    // said once, before the list
    const full = localized(locale, lang.name_en, lang.name_uk, lang.names);
    const area = full.match(/\((.+)\)$/)?.[1] ?? full.split(" — ").pop()!;
    for (const form of lang.forms) {
      const key = form.spelling.toLowerCase();
      if (standard.has(key)) continue;
      const variant = dialects.get(key) ?? {
        word: form.spelling,
        dialects: [],
      };
      variant.dialects.push(area);
      dialects.set(key, variant);
    }
  }
  return [...dialects.values()].sort(
    (a, b) => b.dialects.length - a.dialects.length,
  );
}

/** The same word in the most searched languages, e.g. "potato (English)". */
function worldExamples(concept: ConceptDetail, locale: string): string[] {
  const own = LOCALE_LANGUAGE[locale] ?? "eng";
  return SUMMARY_LANGUAGES.filter((code) => code !== own)
    .map((code) => concept.languages.find((lang) => lang.code === code))
    .filter(
      (lang): lang is LanguageForms =>
        lang !== undefined && lang.forms.length > 0,
    )
    .slice(0, SUMMARY_EXAMPLES)
    .map(
      (lang) =>
        `${lang.forms[0].spelling} (${localized(locale, lang.name_en, lang.name_uk, lang.names)})`,
    );
}

/** Readable text about the word, rendered on the server for search engines and people. */
export function WordIntro({ concept }: { concept: ConceptDetail }) {
  const locale = useLocale();
  const t = useTranslations("Word");
  const word = localized(
    locale,
    concept.gloss_en,
    concept.gloss_uk,
    concept.glosses,
  );
  const examples = worldExamples(concept, locale);
  const languageName = (code: string) => {
    const lang = concept.languages.find((l) => l.code === code);
    return lang
      ? capitalize(localized(locale, lang.name_en, lang.name_uk, lang.names))
      : code;
  };

  return (
    <div className="space-y-2 pt-3 text-sm leading-relaxed">
      {dialectLanguages(concept).map((language) => {
        const variants = dialectVariants(concept, locale, language);
        if (variants.length === 0) return null;
        return (
          <p key={language}>
            {language === "ukr"
              ? t("dialectIntro", { word })
              : t("regionalIntro", { language: languageName(language) })}{" "}
            {variants.map((variant, i) => (
              <span key={variant.word}>
                {i > 0 && "; "}
                <Link
                  href={`/slovo/${encodeURIComponent(variant.word.toLowerCase())}`}
                  className="font-semibold text-violet-800 underline-offset-2 hover:underline dark:text-violet-300"
                >
                  {variant.word}
                </Link>{" "}
                ({variant.dialects.join(", ")})
              </span>
            ))}
            .
          </p>
        );
      })}
      {examples.length > 0 && (
        <p className="opacity-80">
          {t("worldIntro", { list: examples.join(", ") })}
        </p>
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
      <h2 className="mb-2 text-xs tracking-wide uppercase opacity-60">
        {t("related")}
      </h2>
      <ul className="flex flex-wrap gap-2">
        {related.map((link) => (
          <li key={link.slug}>
            <Link
              href={`/word/${link.slug}`}
              className="inline-block rounded-full border border-black/15 px-3 py-1 text-sm hover:bg-black/5 dark:border-white/20 dark:hover:bg-white/10"
            >
              {localized(locale, link.gloss_en, link.gloss_uk, link.glosses)}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
