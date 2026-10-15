"use client";

import { useLocale, useTranslations } from "next-intl";

import { type ReactNode, useState } from "react";

import ContributeDialog from "@/components/ContributeDialog";
import WordCheck, { type Counts, TrustMark } from "@/components/WordCheck";
import { RelatedWords, WordIntro } from "@/components/WordSummary";
import { Link } from "@/i18n/navigation";
import { LANGUAGE_FLAGS } from "@/lib/flags";
import type { SelectedRegion } from "@/components/WorldMap";
import {
  type Audio as AudioInfo,
  API_URL,
  type ConceptDetail,
  type LanguageForms,
  inLocale,
  localized,
} from "@/lib/api";

function playAudio(url: string) {
  // Generated audio is served by the API under a relative /media/... path.
  const src = url.startsWith("/") ? `${API_URL}${url}` : url;
  new Audio(src).play().catch((e: unknown) => console.error(e));
}

const LATIN = /^[\p{Script=Latin}\p{Script=Common}\p{Mark}]+$/u;
const CYRILLIC = /\p{Script=Cyrillic}/u;

/** Romanization for words in other scripts ("辞書" -> "jisho"); Cyrillic only in English. */
function showTransliteration(
  spelling: string,
  transliteration: string | null,
  locale: string,
) {
  if (!transliteration || LATIN.test(spelling)) return false;
  return locale !== "uk" || !CYRILLIC.test(spelling);
}

/** ▶ buttons: recordings of real speakers stand out (amber, 🎙), synthetic voices stay plain. */
export function AudioButtons({ audio }: { audio: AudioInfo[] }) {
  const t = useTranslations("Panel");
  const live = audio.filter((a) => !a.is_synthetic);
  return (
    <span className="inline-flex gap-1">
      {audio.map((a) => (
        <button
          key={a.url}
          type="button"
          onClick={() => playAudio(a.url)}
          title={[
            a.speaker,
            a.license,
            a.is_synthetic ? t("synthetic") : t("liveRecording"),
          ]
            .filter(Boolean)
            .join(" · ")}
          aria-label={
            a.is_synthetic
              ? t("playSynthetic")
              : t("play", { n: live.indexOf(a) + 1 })
          }
          className={
            a.is_synthetic
              ? "rounded-full border border-dashed border-current/30 px-2 text-sm opacity-70 hover:bg-black/5 dark:hover:bg-white/10"
              : "rounded-full bg-amber-400/90 px-2 text-sm font-medium text-amber-950 shadow-sm hover:bg-amber-400"
          }
        >
          {a.is_synthetic ? "▶" : "🎙 ▶"}
          {live.length > 1 && !a.is_synthetic ? ` ${live.indexOf(a) + 1}` : ""}
          {a.is_synthetic && (
            <span className="ml-1 text-[10px] uppercase">{t("tts")}</span>
          )}
        </button>
      ))}
    </span>
  );
}

// The page's language among the word's languages: the word a visitor reads first
const LOCALE_LANGUAGES: Record<string, string> = {
  uk: "ukr",
  en: "eng",
  pl: "pol",
  de: "deu",
  es: "spa",
  fr: "fra",
};

/** The word in the page's language, big: transcription and a round ▶ button. */
function Headword({
  concept,
  locale,
}: {
  concept: ConceptDetail;
  locale: string;
}) {
  const t = useTranslations("Panel");
  const own = concept.languages.find((l) => l.code === LOCALE_LANGUAGES[locale])
    ?.forms[0];
  // Prefer a real speaker's recording
  const audio = own?.audio.find((a) => !a.is_synthetic) ?? own?.audio[0];
  return (
    <div className="flex items-center gap-3">
      <h1 className="font-serif text-3xl font-semibold leading-tight">
        {localized(locale, concept.gloss_en, concept.gloss_uk, concept.glosses)}
      </h1>
      {audio && (
        <button
          type="button"
          onClick={() => playAudio(audio.url)}
          aria-label={
            audio.is_synthetic ? t("playSynthetic") : t("play", { n: 1 })
          }
          title={audio.is_synthetic ? t("synthetic") : t("liveRecording")}
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-lg text-white shadow-md transition hover:scale-105 ${
            audio.is_synthetic
              ? "bg-gradient-to-br from-indigo-600 to-violet-600"
              : "bg-gradient-to-br from-amber-400 to-amber-500 text-amber-950"
          }`}
        >
          ▶
        </button>
      )}
      {own?.ipa && (
        <span className="font-mono text-base opacity-70">{own.ipa}</span>
      )}
    </div>
  );
}

function LanguageCard({ language }: { language: LanguageForms }) {
  const locale = useLocale();
  const t = useTranslations("Panel");
  const [primary, ...others] = language.forms;
  // Updated when the visitor votes, so the trust mark changes right away.
  const [counts, setCounts] = useState<Counts>();

  return (
    <li
      className={`border-b border-black/10 py-3 dark:border-white/10 ${
        language.kind === "dialect"
          ? "ml-3 border-l-2 border-l-violet-400 pl-3"
          : ""
      }`}
    >
      <div className="flex items-center gap-1.5 text-xs uppercase tracking-wide">
        {LANGUAGE_FLAGS[language.code] && (
          <span
            aria-hidden="true"
            className={`fi fi-${LANGUAGE_FLAGS[language.code]} shrink-0 rounded-[2px] shadow-sm`}
          />
        )}
        <span className="opacity-60">
          {language.kind === "dialect" ? (
            <Link
              href={`/dialects/${language.code}`}
              className="hover:underline"
            >
              {localized(
                locale,
                language.name_en,
                language.name_uk,
                language.names,
              )}
            </Link>
          ) : (
            localized(
              locale,
              language.name_en,
              language.name_uk,
              language.names,
            )
          )}
        </span>
      </div>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="font-serif text-xl font-semibold">
          {primary.spelling}
        </span>
        {showTransliteration(
          primary.spelling,
          primary.transliteration,
          locale,
        ) && (
          <span className="text-sm italic opacity-70">
            {primary.transliteration}
          </span>
        )}
        <TrustMark form={primary} counts={counts} />
        {primary.ipa && (
          <span className="font-mono text-sm opacity-80">{primary.ipa}</span>
        )}
        <AudioButtons audio={primary.audio} />
      </div>
      {others.length > 0 && (
        <div className="mt-1 text-sm opacity-70">
          {t("alsoSaid")}{" "}
          {others.map((form, i) => (
            <span key={form.spelling}>
              {i > 0 && ", "}
              {form.spelling}
              {form.ipa && <span className="font-mono"> {form.ipa}</span>}
              {form.audio.length > 0 && (
                <>
                  {" "}
                  <AudioButtons audio={form.audio} />
                </>
              )}
            </span>
          ))}
        </div>
      )}
      <WordCheck
        form={primary}
        onCounts={setCounts}
        // Where Ukrainian and dialect words are really used is worth collecting.
        askUsage={language.code === "ukr" || language.kind === "dialect"}
      />
    </li>
  );
}

/** Credit for a description from Wiktionary, or a note that it was machine-translated. */
function DescriptionOrigin({
  concept,
  locale,
}: {
  concept: ConceptDetail;
  locale: string;
}) {
  const t = useTranslations("Panel");
  const origin = concept.description_origins?.[locale];
  if (origin === "machine") {
    return (
      <span className="ml-1 text-xs italic">({t("machineTranslation")})</span>
    );
  }
  if (origin === "wiktionary") {
    // The concept's name in this language is its main word, maybe with a hint in brackets
    const word = (concept.glosses?.[locale] ?? "").replace(/\s*\(.*\)$/, "");
    return (
      <a
        href={`https://${locale}.wiktionary.org/wiki/${encodeURIComponent(word)}`}
        target="_blank"
        rel="noopener"
        className="ml-1 text-xs underline-offset-2 hover:underline"
      >
        ({t("wiktionary")})
      </a>
    );
  }
  return null;
}

export default function ConceptPanel({
  concept,
  region,
  onClearRegion,
  tools,
}: {
  concept: ConceptDetail;
  region: SelectedRegion | null;
  onClearRegion: () => void;
  /** Extra controls under the heading (colour by origin, save as image) */
  tools?: ReactNode;
}) {
  const locale = useLocale();
  const t = useTranslations("Panel");
  const description = inLocale(
    locale,
    concept.description_en,
    concept.description_uk,
    concept.descriptions,
  );
  const [contributing, setContributing] = useState(false);
  const dialects = concept.languages.filter((l) => l.kind === "dialect").length;
  const liveRecordings = concept.languages
    .flatMap((l) => l.forms)
    .flatMap((f) => f.audio)
    .filter((a) => !a.is_synthetic).length;

  // A region shows its own varieties (dialects, regional languages) and its country's languages.
  const languages = region
    ? concept.languages.filter(
        (lang) =>
          lang.region_codes.includes(region.code) ||
          (region.parentCode !== null &&
            lang.region_codes.includes(region.parentCode)),
      )
    : concept.languages;

  return (
    <aside className="flex h-full flex-col overflow-hidden">
      <div className="border-b border-black/10 p-4 dark:border-white/10">
        <Headword concept={concept} locale={locale} />
        {description && (
          <p className="mt-1 text-sm opacity-70">
            {description}
            <DescriptionOrigin concept={concept} locale={locale} />
          </p>
        )}
        <p className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs">
          <span className="opacity-60">
            {t("languageCount", {
              count: concept.languages.filter((l) => l.kind === "language")
                .length,
            })}
          </span>
          {dialects > 0 && (
            <span className="text-violet-700 dark:text-violet-300">
              {t("dialectCount", { count: dialects })}
            </span>
          )}
          {liveRecordings > 0 && (
            <span className="font-medium text-amber-700 dark:text-amber-300">
              🎙 {t("liveCount", { count: liveRecordings })}
            </span>
          )}
        </p>
        {region && (
          <button
            type="button"
            onClick={onClearRegion}
            className="mt-2 rounded-md bg-blue-500/10 px-2 py-1 text-sm"
          >
            {region.name} ✕
          </button>
        )}
        {tools}
      </div>
      <button
        type="button"
        onClick={() => setContributing(true)}
        className="mx-4 mt-3 rounded-md border border-dashed border-blue-500/60 px-3 py-2 text-left text-sm text-blue-700 hover:bg-blue-500/10 dark:text-blue-300"
      >
        {t("contribute")}
      </button>
      {contributing && (
        <ContributeDialog
          conceptId={concept.id}
          conceptName={localized(
            locale,
            concept.gloss_en,
            concept.gloss_uk,
            concept.glosses,
          )}
          regionCode={region?.code ?? null}
          onClose={() => setContributing(false)}
        />
      )}
      <div className="flex-1 overflow-y-auto px-4">
        {!region && <WordIntro concept={concept} />}
        <ul>
          {languages.length === 0 && (
            <li className="py-3 text-sm opacity-60">{t("noWords")}</li>
          )}
          {languages.map((language) => (
            <LanguageCard key={language.variety_id} language={language} />
          ))}
        </ul>
        <RelatedWords concept={concept} />
      </div>
      <p className="border-t border-black/10 p-3 text-xs opacity-60 dark:border-white/10">
        {t.rich("attribution", {
          wikidata: (chunks) => (
            <a
              className="underline"
              href="https://www.wikidata.org/wiki/Wikidata:Lexicographical_data"
            >
              {chunks}
            </a>
          ),
          wiktionary: (chunks) => (
            <a className="underline" href="https://en.wiktionary.org/">
              {chunks}
            </a>
          ),
          commons: (chunks) => (
            <a className="underline" href="https://commons.wikimedia.org/">
              {chunks}
            </a>
          ),
        })}
      </p>
    </aside>
  );
}
