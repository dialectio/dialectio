import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { cache } from "react";

import DialectWordView from "@/components/DialectWordView";
import { getDialectWord, localized, meaningOf } from "@/lib/api";
import { pageMetadata } from "@/lib/metadata";

// generateMetadata and the page both need the word; fetch it once per request.
const loadWord = cache(getDialectWord);

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/slovo/[word]">): Promise<Metadata> {
  const { locale, word } = await params;
  const entry = await loadWord(decodeURIComponent(word));
  if (!entry) return {};
  const t = await getTranslations({ locale, namespace: "DialectWord" });
  const meanings = entry.meanings.map((m) => meaningOf(m, locale)).join(", ");
  const dialects = [
    ...new Set(
      entry.meanings.flatMap((m) => m.dialects.map((d) => localized(locale, d.name_en, d.name_uk))),
    ),
  ].join(", ");
  return pageMetadata(
    locale,
    `/slovo/${encodeURIComponent(entry.word.toLowerCase())}`,
    t("pageTitle", { word: entry.word }),
    t("pageDescription", { word: entry.word, meaning: meanings, dialects }),
  );
}

export default async function DialectWordPage({ params }: PageProps<"/[locale]/slovo/[word]">) {
  const { locale, word } = await params;
  setRequestLocale(locale);
  const entry = await loadWord(decodeURIComponent(word));
  if (!entry) notFound();
  return <DialectWordView key={word} entry={entry} />;
}
