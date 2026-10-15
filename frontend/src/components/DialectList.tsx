"use client";

import { useLocale, useTranslations } from "next-intl";
import { useMemo } from "react";

import { UKRAINE_BOUNDS, useMapView } from "@/components/MapShell";
import { Link, useRouter } from "@/i18n/navigation";
import { capitalize, type DialectSummary, localized } from "@/lib/api";

/** The dialect index: groups with their dialects; the map shows all dialect areas. */
export default function DialectList({
  dialects,
}: {
  dialects: DialectSummary[];
}) {
  const locale = useLocale();
  const t = useTranslations("Dialects");
  const router = useRouter();
  const groups = dialects.filter((d) => d.kind === "dialect_group");
  const ukrainian = useMemo(
    () => dialects.filter((d) => d.kind !== "regional"),
    [dialects],
  );
  // Regional languages by country, countries and languages in alphabetical order
  const byName = (a: string, b: string) => a.localeCompare(b, locale);
  const countries = new Map<
    string,
    { name: string; languages: DialectSummary[] }
  >();
  for (const d of dialects.filter((d) => d.kind === "regional")) {
    const key = d.country_code ?? "";
    const name = localized(
      locale,
      d.country_en ?? "",
      d.country_uk ?? null,
      d.country_names ?? undefined,
    );
    if (!countries.has(key)) countries.set(key, { name, languages: [] });
    countries.get(key)!.languages.push(d);
  }
  const regional = [...countries.values()].sort((a, b) =>
    byName(a.name, b.name),
  );
  const members = (group: string) =>
    dialects.filter((d) => d.parent_code === group);

  const highlightCodes = useMemo(
    () => [...new Set(ukrainian.flatMap((d) => d.region_codes))],
    [ukrainian],
  );
  // A click on a region opens the first dialect spoken there.
  useMapView({
    highlightCodes,
    labels: null,
    selectedCode: null,
    bounds: UKRAINE_BOUNDS,
    onSelectRegion: (region) => {
      const dialect = ukrainian.find(
        (d) => d.kind === "dialect" && d.region_codes.includes(region.code),
      );
      if (dialect) router.push(`/dialects/${dialect.code}`);
    },
  });

  return (
    <article className="space-y-5 p-4">
      <h1 className="font-serif text-2xl font-semibold">{t("title")}</h1>
      <p className="text-sm leading-relaxed">{t("intro")}</p>
      {groups.map((group) => (
        <section key={group.code}>
          <h2 className="mb-1 font-medium">
            {capitalize(
              localized(locale, group.name_en, group.name_uk, group.names),
            )}
          </h2>
          <ul className="space-y-0.5">
            {members(group.code).map((dialect) => (
              <li key={dialect.code}>
                <Link
                  href={`/dialects/${dialect.code}`}
                  className="flex justify-between rounded-md px-2 py-1 hover:bg-black/5 dark:hover:bg-white/10"
                >
                  <span>
                    {capitalize(
                      localized(
                        locale,
                        dialect.name_en,
                        dialect.name_uk,
                        dialect.names,
                      ),
                    )}
                  </span>
                  <span className="text-sm opacity-60">
                    {t("words", { count: dialect.words })}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
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
              <ul className="space-y-0.5">
                {country.languages
                  .map((d) => ({
                    d,
                    name: capitalize(
                      localized(locale, d.name_en, d.name_uk, d.names),
                    ),
                  }))
                  .sort((a, b) => byName(a.name, b.name))
                  .map(({ d, name }) => (
                    <li key={d.code}>
                      <Link
                        href={`/dialects/${d.code}`}
                        className="flex justify-between rounded-md px-2 py-1 hover:bg-black/5 dark:hover:bg-white/10"
                      >
                        <span>{name}</span>
                        <span className="text-sm opacity-60">
                          {t("words", { count: d.words })}
                        </span>
                      </Link>
                    </li>
                  ))}
              </ul>
            </div>
          ))}
        </section>
      )}
    </article>
  );
}
