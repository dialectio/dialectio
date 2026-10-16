"use client";

import { useLocale, useTranslations } from "next-intl";
import { useMemo } from "react";

import { InfoNav } from "@/components/InfoPage";
import { useConceptOnMap } from "@/components/MapShell";
import { familyColors, wordFamilies } from "@/components/OriginTools";
import { Link, useRouter } from "@/i18n/navigation";
import { type ConceptDetail, type FeaturedConcept, localized } from "@/lib/api";
import { DIALECT_BOUNDS } from "@/lib/visitor";

const EXAMPLES_SHOWN = 5;

/**
 * Home page panel: what the site is, the word of the day (also shown on the map), dialect
 * examples. Every word links to its own page.
 */
export default function HomePanel({
  featured,
  preview,
  language,
}: {
  featured: FeaturedConcept[];
  /** The word of the day with its map data. */
  preview: ConceptDetail | null;
  /** Whose regional words are featured ("ukr", "deu" ...): the map opens over their area */
  language: string;
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
    DIALECT_BOUNDS[language] ?? null,
  );

  return (
    <aside className="space-y-6 p-4">
      <p className="text-sm opacity-80">{t("intro")}</p>

      {wordOfDay && (
        <section className="rounded-lg border border-violet-500/30 bg-violet-500/5 p-4">
          <h2 className="text-xs font-medium tracking-wide uppercase opacity-60">
            {t("wordOfDay")}
          </h2>
          <p className="mt-1 font-serif text-2xl font-semibold">
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

      {/* The check game: where visitors help, right under the word of the day */}
      <Link
        href="/check"
        className="flex items-center gap-3 rounded-lg border border-amber-500/40 bg-amber-400/10 p-4 !no-underline hover:bg-amber-400/20"
      >
        <span aria-hidden="true" className="text-3xl">
          🎯
        </span>
        <span className="min-w-0 flex-1">
          <span className="block font-semibold">{t("gameTitle")}</span>
          <span className="block text-sm opacity-80">{t("gameText")}</span>
        </span>
        <span className="shrink-0 rounded-md bg-amber-500 px-3 py-1.5 text-sm font-medium text-amber-950">
          {t("gamePlay")}
        </span>
      </Link>

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

      <InfoNav />
    </aside>
  );
}
