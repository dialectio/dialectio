import { getTranslations } from "next-intl/server";

import { getConceptBySlug, LOCALE_LANGUAGE, localized } from "@/lib/api";
import { isDrawable, OG_SIZE, renderCard } from "@/lib/og";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "Dialectio";

const WORLD_LANGUAGES = ["eng", "deu", "fra", "spa", "pol", "ita", "ces", "ukr"];
const SHOWN = 5;

export default async function Image({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug } = await params;
  const t = await getTranslations({ locale, namespace: "Og" });
  const concept = await getConceptBySlug(slug);
  if (!concept) return renderCard({ kicker: "", title: "Dialectio", footer: t("site") });

  const own = LOCALE_LANGUAGE[locale] ?? "eng";
  // Dialect words that differ from their own language's standard word (ukr-hutsul vs ukr),
  // the interface language's dialects first (the image is made per locale)
  const languageOf = (code: string) => code.split("-")[0];
  const standard = (language: string) =>
    new Set(
      concept.languages
        .filter((l) => l.code === language)
        .flatMap((l) => l.forms.map((f) => f.spelling.toLowerCase())),
    );
  const dialects = concept.languages
    .filter((l) => l.kind === "dialect")
    .sort(
      (a, b) =>
        Number(languageOf(b.code) === own) - Number(languageOf(a.code) === own),
    );
  // Each language's distinct dialect words, then taken in turns: бараболя, Grumbeer, бульба ...
  const byLanguage = new Map<string, string[]>();
  for (const l of dialects) {
    const language = languageOf(l.code);
    const main = standard(language);
    const words = byLanguage.get(language) ?? [];
    for (const f of l.forms) {
      const w = f.spelling.toLowerCase();
      if (!main.has(w) && !words.includes(w) && isDrawable(w)) words.push(w);
    }
    byLanguage.set(language, words);
  }
  const dialectWords: string[] = [];
  const lists = [...byLanguage.values()];
  for (let i = 0; lists.some((words) => i < words.length); i++)
    for (const words of lists)
      if (i < words.length && !dialectWords.includes(words[i])) dialectWords.push(words[i]);
  const world = WORLD_LANGUAGES.filter((code) => code !== own)
    .map((code) => concept.languages.find((l) => l.code === code)?.forms[0]?.spelling)
    .filter((w): w is string => !!w && isDrawable(w));

  return renderCard({
    kicker: t("wordKicker"),
    title: localized(locale, concept.gloss_en, concept.gloss_uk, concept.glosses),
    highlight: dialectWords.slice(0, SHOWN),
    secondary: world.slice(0, SHOWN),
    footer: t("footer", { count: concept.languages.filter((l) => l.kind === "language").length }),
  });
}
