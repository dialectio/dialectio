"use client";

import { useLocale, useTranslations } from "next-intl";
import { useMemo } from "react";

import { InfoNav } from "@/components/InfoPage";
import { useConceptOnMap } from "@/components/MapShell";
import { familyColors, wordFamilies } from "@/components/OriginTools";
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

  // The word of the day coloured by origin, when its words come from several families.
  const colors = useMemo(
    () =>
      preview && wordFamilies(preview).length > 1
        ? familyColors(preview)
        : null,
    [preview],
  );
  // A click on the map opens the word of the day, filtered to that region.
  useConceptOnMap(
    preview,
    null,
    (region) => {
      if (preview?.slug)
        router.push(`/word/${preview.slug}?region=${region.code}`);
    },
    colors,
  );

  return (
    <aside className="space-y-6 p-4">
      <p className="text-sm opacity-80">{t("intro")}</p>

      {wordOfDay && (
        <section className="rounded-lg border border-violet-500/30 bg-violet-500/5 p-4">
          <h2 className="text-xs font-medium tracking-wide uppercase opacity-60">
            {t("wordOfDay")}
          </h2>
          <p className="mt-1 text-2xl font-semibold">
            {localized(
              locale,
              wordOfDay.gloss_en,
              wordOfDay.gloss_uk,
              wordOfDay.glosses,
            )}
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
                    {localized(
                      locale,
                      concept.gloss_en,
                      concept.gloss_uk,
                      concept.glosses,
                    )}
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

      <Link
        href="/check"
        className="block rounded-lg border border-dashed border-green-600/50 px-3 py-2 text-sm text-green-800 hover:bg-green-600/10 dark:text-green-300"
      >
        {t("checkCta")}
      </Link>

      <InfoNav />
    </aside>
  );
}
