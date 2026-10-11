import { getTranslations } from "next-intl/server";

import { OG_SIZE, renderCard } from "@/lib/og";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "Dialectio";

/** Default preview for every page without its own (home, dialects, about...). */
export default async function Image({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Og" });
  return renderCard({
    kicker: t("site"),
    title: t("exampleTitle"),
    highlight: ["бараболя", "бульба", "компера", "крумплі", "бандурка"],
    secondary: ["potato", "Kartoffel", "pomme de terre", "ziemniak", "patata"],
    footer: "dialectio",
  });
}
