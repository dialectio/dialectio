"use client";

import { useLocale, useTranslations } from "next-intl";
import { useMemo } from "react";

import { useMapView } from "@/components/MapShell";
import { Link, useRouter } from "@/i18n/navigation";
import { capitalize, type DialectSummary, localized } from "@/lib/api";
import { DIALECT_BOUNDS, ownLanguage } from "@/lib/visitor";

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

// ISO 639-3 -> 639-1 for Intl.DisplayNames (the dialect languages we have)
const ISO1: Record<string, string> = {
  ukr: "uk",
  eng: "en",
  deu: "de",
  fra: "fr",
  ita: "it",
  pol: "pl",
  por: "pt",
  spa: "es",
};

/**
 * The dialect index: each language's dialects, the visitor's own language first (its areas
 * shown on the map), then regional languages by country.
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
  const own = ownLanguage(locale);

  // Dialect languages: the visitor's own first, the rest alphabetically
  const languageName = (code: string) => {
    try {
      return (
        new Intl.DisplayNames([locale], { type: "language" }).of(
          ISO1[code] ?? code,
        ) ?? code
      );
    } catch {
      return code;
    }
  };
  const languages = [
    ...new Set(
      dialects
        .filter((d) => d.kind === "dialect_group")
        .map((d) => d.code.split("-")[0]),
    ),
  ].sort((a, b) =>
    a === own ? -1 : b === own ? 1 : byName(languageName(a), languageName(b)),
  );
  const groupsOf = (language: string) =>
    dialects.filter(
      (d) => d.kind === "dialect_group" && d.code.split("-")[0] === language,
    );
  const members = (group: string) =>
    dialects.filter((d) => d.parent_code === group);

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

  // The map shows the areas of the visitor's own language's dialects
  const ownDialects = useMemo(
    () =>
      dialects.filter(
        (d) => d.kind === "dialect" && d.code.split("-")[0] === own,
      ),
    [dialects, own],
  );
  const highlightCodes = useMemo(
    () => [...new Set(ownDialects.flatMap((d) => d.region_codes))],
    [ownDialects],
  );
  // A click on a region opens the first of those dialects spoken there.
  useMapView({
    highlightCodes,
    labels: null,
    selectedCode: null,
    bounds: DIALECT_BOUNDS[own] ?? null,
    onSelectRegion: (region) => {
      const dialect = ownDialects.find((d) =>
        d.region_codes.includes(region.code),
      );
      if (dialect) router.push(`/dialects/${dialect.code}`);
    },
  });

  return (
    <article className="space-y-5 p-4">
      <h1 className="font-serif text-2xl font-semibold">{t("title")}</h1>
      <p className="text-sm leading-relaxed">{t("intro")}</p>
      {languages.map((language) => {
        const groups = groupsOf(language);
        return (
          <section key={language}>
            <h2 className="mb-1 font-serif text-xl font-semibold">
              {capitalize(languageName(language))}
            </h2>
            {groups.length === 1 ? (
              <VarietyLinks varieties={members(groups[0].code)} />
            ) : (
              groups.map((group) => (
                <div key={group.code} className="mb-2">
                  <h3 className="text-xs font-medium uppercase tracking-wide opacity-60">
                    {name(group)}
                  </h3>
                  <VarietyLinks varieties={members(group.code)} />
                </div>
              ))
            )}
          </section>
        );
      })}

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
