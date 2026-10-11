"use client";

import { useLocale, useTranslations } from "next-intl";
import { useMemo } from "react";

import { AudioButtons } from "@/components/ConceptPanel";
import { type MapLabels, useMapView } from "@/components/MapShell";
import { Link } from "@/i18n/navigation";
import { type DialectRef, type DialectWordDetail, localized, meaningOf } from "@/lib/api";

function DialectLinks({ dialects }: { dialects: DialectRef[] }) {
  const locale = useLocale();
  return (
    <>
      {dialects.map((dialect, i) => (
        <span key={dialect.code}>
          {i > 0 && ", "}
          <Link href={`/dialects/${dialect.code}`} className="underline-offset-2 hover:underline">
            {localized(locale, dialect.name_en, dialect.name_uk)}
          </Link>
        </span>
      ))}
    </>
  );
}

/** A dialect word page: meanings, where it is said (also on the map), other dialect names. */
export default function DialectWordView({ entry }: { entry: DialectWordDetail }) {
  const locale = useLocale();
  const t = useTranslations("DialectWord");

  // The word itself as a violet label in every region where it is said.
  const labels = useMemo<MapLabels>(
    () => ({
      type: "FeatureCollection",
      features: entry.regions.map((region, i) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [region.lon, region.lat] },
        properties: {
          code: region.code,
          level: "adm1",
          parent_code: null,
          dialect: true,
          text: entry.word,
          name_en: region.name_en,
          name_uk: region.name_uk,
          rank: i,
        },
      })),
    }),
    [entry],
  );
  const highlightCodes = useMemo(() => entry.regions.map((r) => r.code), [entry]);
  useMapView({
    highlightCodes,
    labels,
    selectedCode: null,
    onSelectRegion: () => {},
    bounds: entry.bounds,
  });

  return (
    <article className="space-y-6 p-4">
      <header>
        <p className="text-xs tracking-wide uppercase opacity-60">{t("kicker")}</p>
        <h1 className="text-3xl font-semibold text-violet-800 dark:text-violet-300">
          {entry.word}
        </h1>
      </header>

      {entry.meanings.map((meaning) => {
        const meaningText = meaningOf(meaning, locale);
        return (
          <section key={meaning.slug} className="space-y-3">
            <p className="flex flex-wrap items-baseline gap-x-2 text-lg">
              <span>{t("means", { meaning: meaningText })}</span>
              {meaning.unverified && <span className="text-sm opacity-60">≈</span>}
              {meaning.audio.length > 0 && <AudioButtons audio={meaning.audio} />}
            </p>
            <div className="text-sm">
              <h2 className="font-medium">{t("usedIn")}</h2>
              <p>
                <DialectLinks dialects={meaning.dialects} />
              </p>
            </div>
            {meaning.others.length > 0 && (
              <div className="text-sm">
                <h2 className="font-medium">{t("others")}</h2>
                <ul className="mt-1 space-y-1">
                  {meaning.others.map((other) => (
                    <li key={other.word}>
                      <Link
                        href={`/slovo/${encodeURIComponent(other.word)}`}
                        className="font-semibold text-violet-800 underline-offset-2 hover:underline dark:text-violet-300"
                      >
                        {other.word}
                      </Link>
                      <span className="opacity-70">
                        {" — "}
                        <DialectLinks dialects={other.dialects} />
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <Link
              href={`/word/${meaning.slug}`}
              className="inline-block text-sm text-blue-700 hover:underline dark:text-blue-300"
            >
              {t("allLanguages", { meaning: meaningText })}
            </Link>
            {meaning.unverified && <p className="text-xs opacity-60">{t("unverified")}</p>}
          </section>
        );
      })}
    </article>
  );
}
