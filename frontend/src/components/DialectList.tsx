"use client";

import { useLocale, useTranslations } from "next-intl";
import { useMemo } from "react";

import { UKRAINE_BOUNDS, useMapView } from "@/components/MapShell";
import { Link, useRouter } from "@/i18n/navigation";
import { capitalize, type DialectSummary, localized } from "@/lib/api";

/** A list of dialects or regional languages, each with its word count. */
function VarietyLinks({ varieties }: { varieties: DialectSummary[] }) {
  const locale = useLocale();
  const t = useTranslations("Dialects");
  return (
    <ul className="space-y-0.5">
      {varieties.map((d) => (
        <li key={d.code}>
          <Link
            href={`/dialects/${d.code}`}
            className="flex justify-between rounded-md px-2 py-1 hover:bg-black/5 dark:hover:bg-white/10"
          >
            <span>
              {capitalize(localized(locale, d.name_en, d.name_uk, d.names))}
            </span>
            <span className="text-sm opacity-60">
              {t("words", { count: d.words })}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

/**
 * The dialect index: Ukrainian dialect groups with their dialects (shown on the map), then
 * other languages' dialect areas (German ...) and regional languages by country.
 */
export default function DialectList({
  dialects,
}: {
  dialects: DialectSummary[];
}) {
  const locale = useLocale();
  const t = useTranslations("Dialects");
  const router = useRouter();
  const byName = (a: string, b: string) => a.localeCompare(b, locale);
  const name = (d: DialectSummary) =>
    localized(locale, d.name_en, d.name_uk, d.names);

  const isUkrainian = (d: DialectSummary) => d.code.startsWith("ukr-");
  const groups = dialects.filter((d) => d.kind === "dialect_group");
  const members = (group: string) =>
    dialects.filter((d) => d.parent_code === group);
  const ukrainian = useMemo(
    () =>
      dialects.filter((d) => d.kind === "dialect" && d.code.startsWith("ukr-")),
    [dialects],
  );

  // Regional languages by country, countries and languages in alphabetical order
  const countries = new Map<
    string,
    { name: string; languages: DialectSummary[] }
  >();
  for (const d of dialects.filter((d) => d.kind === "regional")) {
    const key = d.country_code ?? "";
    const country = localized(
      locale,
      d.country_en ?? "",
      d.country_uk ?? null,
      d.country_names ?? undefined,
    );
    if (!countries.has(key))
      countries.set(key, { name: country, languages: [] });
    countries.get(key)!.languages.push(d);
  }
  const regional = [...countries.values()].sort((a, b) =>
    byName(a.name, b.name),
  );

  const highlightCodes = useMemo(
    () => [...new Set(ukrainian.flatMap((d) => d.region_codes))],
    [ukrainian],
  );
  // A click on a region opens the first Ukrainian dialect spoken there.
  useMapView({
    highlightCodes,
    labels: null,
    selectedCode: null,
    bounds: UKRAINE_BOUNDS,
    onSelectRegion: (region) => {
      const dialect = ukrainian.find((d) =>
        d.region_codes.includes(region.code),
      );
      if (dialect) router.push(`/dialects/${dialect.code}`);
    },
  });

  const otherGroups = groups.filter((g) => !isUkrainian(g));

  return (
    <article className="space-y-5 p-4">
      <h1 className="font-serif text-2xl font-semibold">{t("title")}</h1>
      <p className="text-sm leading-relaxed">{t("intro")}</p>
      {groups.filter(isUkrainian).map((group) => (
        <section key={group.code}>
          <h2 className="mb-1 font-medium">{capitalize(name(group))}</h2>
          <VarietyLinks varieties={members(group.code)} />
        </section>
      ))}

      {otherGroups.length > 0 && (
        <section className="space-y-3 border-t border-black/10 pt-4 dark:border-white/15">
          <h2 className="font-serif text-xl font-semibold">
            {t("otherDialectsTitle")}
          </h2>
          <p className="text-sm leading-relaxed">{t("otherDialectsIntro")}</p>
          {otherGroups.map((group) => (
            <div key={group.code}>
              <h3 className="mb-1 font-medium">{capitalize(name(group))}</h3>
              <VarietyLinks varieties={members(group.code)} />
            </div>
          ))}
        </section>
      )}

      {regional.length > 0 && (
        <section className="border-t border-black/10 pt-4 dark:border-white/15">
          <h2 className="font-serif text-xl font-semibold">
            {t("regionalTitle")}
          </h2>
          <p className="mb-2 text-sm leading-relaxed">{t("regionalIntro")}</p>
          {regional.map((country) => (
            <div key={country.name} className="mb-2">
              <h3 className="text-xs font-medium uppercase tracking-wide opacity-60">
                {country.name}
              </h3>
              <VarietyLinks
                varieties={[...country.languages].sort((a, b) =>
                  byName(name(a), name(b)),
                )}
              />
            </div>
          ))}
        </section>
      )}
    </article>
  );
}
