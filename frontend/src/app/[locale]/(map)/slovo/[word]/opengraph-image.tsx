import { getTranslations } from "next-intl/server";

import { getDialectWord, localized, meaningOf } from "@/lib/api";
import { OG_SIZE, renderCard } from "@/lib/og";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "Dialectio";

export default async function Image({
  params,
}: {
  params: Promise<{ locale: string; word: string }>;
}) {
  const { locale, word } = await params;
  const t = await getTranslations({ locale, namespace: "Og" });
  const entry = await getDialectWord(decodeURIComponent(word));
  if (!entry) return renderCard({ kicker: "", title: "Dialectio", footer: t("site") });

  const meaning = entry.meanings.map((m) => meaningOf(m, locale)).join(", ");
  const dialects = [
    ...new Set(
      entry.meanings.flatMap((m) => m.dialects.map((d) => localized(locale, d.name_en, d.name_uk))),
    ),
  ];
  return renderCard({
    kicker: t("dialectWordKicker", { meaning }),
    title: entry.word,
    highlight: entry.meanings.flatMap((m) => m.others.map((o) => o.word)).slice(0, 5),
    secondary: dialects.slice(0, 3),
    footer: t("site"),
  });
}
