import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { cache } from "react";

import InfoPage from "@/components/InfoPage";
import { Link } from "@/i18n/navigation";
import { capitalize, type FalseFriendWord, getFalseFriends, localized } from "@/lib/api";
import { LANGUAGE_FLAGS } from "@/lib/flags";
import { pageMetadata } from "@/lib/metadata";

const DESCRIPTION_EXAMPLES = 4;

// generateMetadata and the page both need the pairs; fetch them once per request.
const loadPairs = cache(getFalseFriends);

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/false-friends/[code]">): Promise<Metadata> {
  const { locale, code } = await params;
  const data = await loadPairs(code);
  if (!data) return {};
  const t = await getTranslations({ locale, namespace: "FalseFriends" });
  const language = localized(locale, data.name_en, data.name_uk, data.names);
  const examples = data.pairs
    .slice(0, DESCRIPTION_EXAMPLES)
    .map((p) => `${p.foreign.spelling} ≠ ${p.ukrainian.spelling}`)
    .join(", ");
  return pageMetadata(
    locale,
    `/false-friends/${code}`,
    t("langTitle", { language: capitalize(language) }),
    t("langDescription", { examples }),
  );
}

function WordCell({
  word,
  flag,
  locale,
  meansLabel,
  inLanguageLabel,
}: {
  word: FalseFriendWord;
  flag: string | undefined;
  locale: string;
  meansLabel: (meaning: string) => string;
  inLanguageLabel: (word: string) => string;
}) {
  const meaning = localized(locale, word.gloss_en, word.gloss_uk, word.glosses);
  return (
    <div className="min-w-0 flex-1">
      <div className="flex items-center gap-1.5">
        {flag && <span aria-hidden="true" className={`fi fi-${flag} shrink-0`} />}
        <Link href={`/word/${word.slug}`} className="text-lg font-semibold">
          {word.spelling}
        </Link>
      </div>
      {meaning.toLowerCase() !== word.spelling.toLowerCase() && (
        <div className="text-sm">{meansLabel(meaning)}</div>
      )}
      {word.translation && word.translation.toLowerCase() !== meaning.toLowerCase() && (
        <div className="text-xs opacity-60">{inLanguageLabel(word.translation)}</div>
      )}
    </div>
  );
}

/** One language's false friends with Ukrainian: "lis" (fox) ≠ "ліс" (forest). */
export default async function FalseFriendsLanguagePage({
  params,
}: PageProps<"/[locale]/false-friends/[code]">) {
  const { locale, code } = await params;
  setRequestLocale(locale);
  const data = await loadPairs(code);
  if (!data) notFound();
  const t = await getTranslations("FalseFriends");
  const tNav = await getTranslations("Nav");
  const language = localized(locale, data.name_en, data.name_uk, data.names);
  const ukrainian = t("ukrainian");

  return (
    <InfoPage title={t("langTitle", { language: capitalize(language) })}>
      <p>
        <Link href="/false-friends">← {t("allLanguages")}</Link>
      </p>
      <p>{t("langIntro", { language })}</p>
      <ul className="space-y-2">
        {data.pairs.map((pair) => (
          <li
            key={`${pair.foreign.spelling}-${pair.ukrainian.spelling}`}
            className="flex items-start gap-3 rounded-md border border-black/10 p-3 dark:border-white/15"
          >
            <WordCell
              word={pair.foreign}
              flag={LANGUAGE_FLAGS[code]}
              locale={locale}
              meansLabel={(meaning) => t("means", { meaning })}
              // The foreign word's concept in Ukrainian
              inLanguageLabel={(w) => t("inLanguage", { language: ukrainian, word: w })}
            />
            <span aria-hidden="true" className="self-center text-xl opacity-40">
              ≠
            </span>
            <WordCell
              word={pair.ukrainian}
              flag="ua"
              locale={locale}
              meansLabel={(meaning) => t("means", { meaning })}
              inLanguageLabel={(w) => t("inLanguage", { language, word: w })}
            />
          </li>
        ))}
      </ul>
      <p className="text-sm opacity-60">
        <Link href="/dialects">{tNav("dialects")}</Link> ·{" "}
        <Link href="/check">{tNav("check")}</Link>
      </p>
    </InfoPage>
  );
}
