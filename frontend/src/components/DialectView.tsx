"use client";

import { useLocale, useTranslations } from "next-intl";
import { useMemo } from "react";

import { type MapLabels, useMapView } from "@/components/MapShell";
import { Link } from "@/i18n/navigation";
import { capitalize, type DialectDetail, localized } from "@/lib/api";

/** Breadcrumbs: All dialects / group / this dialect. */
function Breadcrumbs({ dialect }: { dialect: DialectDetail }) {
  const locale = useLocale();
  const t = useTranslations("Dialects");
  // A dialect's group; for a regional language, its country
  const group =
    dialect.kind === "regional"
      ? localized(
          locale,
          dialect.country_en ?? "",
          dialect.country_uk ?? null,
          dialect.country_names ?? undefined,
        )
      : localized(
          locale,
          dialect.parent_name_en ?? "",
          dialect.parent_name_uk,
          dialect.parent_names,
        );
  return (
    <nav className="text-xs opacity-70">
      <Link href="/dialects" className="hover:underline">
        {t("allDialects")}
      </Link>
      {group && <> / {capitalize(group)}</>}
    </nav>
  );
}

/** A dialect page: its area on the map, description and words. */
export default function DialectView({ dialect }: { dialect: DialectDetail }) {
  const locale = useLocale();
  const t = useTranslations("Dialects");
  const tInfo = useTranslations("DialectInfo");
  const name = capitalize(
    localized(locale, dialect.name_en, dialect.name_uk, dialect.names),
  );

  // One violet label per region of the dialect's area, named after the region.
  const labels = useMemo<MapLabels>(
    () => ({
      type: "FeatureCollection",
      features: dialect.regions.map((region, i) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [region.lon, region.lat] },
        properties: {
          code: region.code,
          level: "adm1",
          parent_code: null,
          dialect: true,
          text: localized(locale, region.name_en, region.name_uk, region.names),
          name_en: region.name_en,
          name_uk: region.name_uk,
          rank: i,
        },
      })),
    }),
    [dialect, locale],
  );
  useMapView({
    highlightCodes: dialect.region_codes,
    labels,
    selectedCode: null,
    onSelectRegion: () => {},
    bounds: dialect.bounds,
  });

  const territory = dialect.regions.map((r) =>
    localized(locale, r.name_en, r.name_uk, r.names),
  );
  const regional = dialect.kind === "regional";

  return (
    <article className="space-y-4 p-4">
      <Breadcrumbs dialect={dialect} />
      <h1 className="font-serif text-2xl font-semibold">{name}</h1>
      {tInfo.has(dialect.code) && (
        <p className="text-sm leading-relaxed">{tInfo(dialect.code)}</p>
      )}

      <section className="text-sm">
        <h2 className="font-medium">{t("territory")}</h2>
        <p>{territory.join(", ")}</p>
        <p className="mt-1 text-xs opacity-60">{t("territoryNote")}</p>
      </section>

      <p>
        <Link
          href={`/check?deck=${dialect.code}`}
          className="inline-block rounded-md bg-violet-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-violet-700"
        >
          {regional ? t("checkCtaLanguage") : t("checkCta")}
        </Link>
      </p>

      <section>
        <h2 className="mb-2 font-medium">
          {regional ? t("languageWordsTitle") : t("wordsTitle")}{" "}
          <span className="text-sm font-normal opacity-60">
            ({t("words", { count: dialect.words })})
          </span>
        </h2>
        {dialect.words_list.length === 0 ? (
          <p className="text-sm opacity-70">{t("noWords")}</p>
        ) : (
          <>
            <table className="w-full text-left text-sm">
              <thead className="border-b border-black/15 dark:border-white/20">
                <tr>
                  <th className="py-1.5 pr-3 font-medium">
                    {regional ? t("regionalWord") : t("dialectWord")}
                  </th>
                  <th className="py-1.5 font-medium">
                    {regional ? t("meaning") : t("standardWord")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {dialect.words_list.map((word) => (
                  <tr
                    key={`${word.slug}-${word.spelling}`}
                    className="border-b border-black/5 dark:border-white/10"
                  >
                    <td className="py-1.5 pr-3 font-semibold text-violet-800 dark:text-violet-300">
                      {regional ? (
                        <Link
                          href={`/word/${word.slug}`}
                          className="underline-offset-2 hover:underline"
                        >
                          {word.spelling}
                        </Link>
                      ) : word.standard?.toLowerCase() ===
                        word.spelling.toLowerCase() ? (
                        word.spelling
                      ) : (
                        <Link
                          href={`/slovo/${encodeURIComponent(word.spelling.toLowerCase())}`}
                          className="underline-offset-2 hover:underline"
                        >
                          {word.spelling}
                        </Link>
                      )}
                      {word.unverified && (
                        <span className="ml-1 font-normal opacity-60">≈</span>
                      )}
                      {word.has_audio && (
                        <span
                          className="ml-1 font-normal opacity-60"
                          title={t("audio")}
                        >
                          ▶
                        </span>
                      )}
                    </td>
                    <td className="py-1.5">
                      <Link
                        href={`/word/${word.slug}`}
                        className="underline-offset-2 hover:underline"
                      >
                        {(!regional && word.standard) ||
                          localized(
                            locale,
                            word.gloss_en,
                            word.gloss_uk,
                            word.glosses,
                          )}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {dialect.words_list.length < dialect.words && (
              <p className="mt-2 text-xs opacity-60">
                {t("shownOf", {
                  shown: dialect.words_list.length,
                  total: dialect.words,
                })}
              </p>
            )}
            <p className="mt-2 text-xs opacity-60">{t("unverifiedNote")}</p>
          </>
        )}
      </section>
    </article>
  );
}
