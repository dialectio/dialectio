import { getTranslations } from "next-intl/server";

import { getConceptBySlug, localized } from "@/lib/api";
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

  const own = locale === "uk" ? "ukr" : "eng";
  const standard = new Set(
    concept.languages.filter((l) => l.code === own).flatMap((l) => l.forms.map((f) => f.spelling)),
  );
  const dialectWords = [
    ...new Set(
      concept.languages
        .filter((l) => l.kind === "dialect")
        .flatMap((l) => l.forms.map((f) => f.spelling.toLowerCase()))
        .filter((w) => !standard.has(w)),
    ),
  ];
  const world = WORLD_LANGUAGES.filter((code) => code !== own)
    .map((code) => concept.languages.find((l) => l.code === code)?.forms[0]?.spelling)
    .filter((w): w is string => !!w && isDrawable(w));

  return renderCard({
    kicker: t("wordKicker"),
    title: localized(locale, concept.gloss_en, concept.gloss_uk),
    highlight: dialectWords.slice(0, SHOWN),
    secondary: world.slice(0, SHOWN),
    footer: t("footer", { count: concept.languages.filter((l) => l.kind === "language").length }),
  });
}
