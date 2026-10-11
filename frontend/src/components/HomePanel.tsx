"use client";

import { useLocale, useTranslations } from "next-intl";

import { InfoNav } from "@/components/InfoPage";
import { useMapView } from "@/components/MapShell";
import { Link, useRouter } from "@/i18n/navigation";
import { type ConceptDetail, type FeaturedConcept, localized } from "@/lib/api";

const EXAMPLES_SHOWN = 5;

/**
 * Home page panel: what the site is, the word of the day (also shown on the map), dialect
 * examples. Every word links to its own page.
 */
export default function HomePanel({
  featured,
  preview,
}: {
  featured: FeaturedConcept[];
  /** The word of the day with its map data. */
  preview: ConceptDetail | null;
}) {
  const locale = useLocale();
  const t = useTranslations("Home");
  const router = useRouter();
  const wordOfDay = featured.find((c) => c.id === preview?.id) ?? null;
  const others = featured.filter((c) => c.id !== wordOfDay?.id);

  // A click on the map opens the word of the day, filtered to that region.
  useMapView({
    concept: preview,
    selectedCode: null,
    onSelectRegion: (region) => {
      if (preview?.slug) router.push(`/word/${preview.slug}?region=${region.code}`);
    },
  });

  return (
    <aside className="space-y-6 p-4">
      <p className="text-sm opacity-80">{t("intro")}</p>

      {wordOfDay && (
        <section className="rounded-lg border border-violet-500/30 bg-violet-500/5 p-4">
          <h2 className="text-xs font-medium tracking-wide uppercase opacity-60">
            {t("wordOfDay")}
          </h2>
          <p className="mt-1 text-2xl font-semibold">
            {localized(locale, wordOfDay.gloss_en, wordOfDay.gloss_uk)}
          </p>
          <p className="mt-1 text-sm">
            <span className="opacity-70">{t("inDialects")} </span>
            <span className="text-violet-700 dark:text-violet-300">
              {wordOfDay.examples.slice(0, EXAMPLES_SHOWN).join(", ")}
            </span>
          </p>
          <Link
            href={`/word/${wordOfDay.slug}`}
            className="mt-3 inline-block rounded-md bg-violet-600 px-3 py-1.5 text-sm text-white hover:bg-violet-700"
          >
            {t("open")}
          </Link>
        </section>
      )}

      {others.length > 0 && (
        <section>
          <h2 className="font-medium">{t("dialectsTitle")}</h2>
          <p className="mb-2 text-sm opacity-70">{t("dialectsHint")}</p>
          <ul className="space-y-1">
            {others.map((concept) => (
              <li key={concept.id}>
                <Link
                  href={`/word/${concept.slug}`}
                  className="block rounded-md px-2 py-1.5 hover:bg-black/5 dark:hover:bg-white/10"
                >
                  <span className="font-medium">
                    {localized(locale, concept.gloss_en, concept.gloss_uk)}
                  </span>
                  <span className="text-sm opacity-70">
                    {" — "}
                    {concept.examples.slice(0, EXAMPLES_SHOWN).join(", ")}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <InfoNav />
    </aside>
  );
}
