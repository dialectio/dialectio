"use client";

import { useLocale, useTranslations } from "next-intl";
import { useMemo } from "react";

import { useMapView } from "@/components/MapShell";
import { Link, useRouter } from "@/i18n/navigation";
import { capitalize, type DialectSummary, localized } from "@/lib/api";

// Ukrainian dialects and the neighbouring areas where they are spoken.
const UKRAINE_BOUNDS = [19, 44, 41, 53];

/** The dialect index: groups with their dialects; the map shows all dialect areas. */
export default function DialectList({ dialects }: { dialects: DialectSummary[] }) {
  const locale = useLocale();
  const t = useTranslations("Dialects");
  const router = useRouter();
  const groups = dialects.filter((d) => d.kind === "dialect_group");
  const members = (group: string) => dialects.filter((d) => d.parent_code === group);

  const highlightCodes = useMemo(
    () => [...new Set(dialects.flatMap((d) => d.region_codes))],
    [dialects],
  );
  // A click on a region opens the first dialect spoken there.
  useMapView({
    highlightCodes,
    labels: null,
    selectedCode: null,
    bounds: UKRAINE_BOUNDS,
    onSelectRegion: (region) => {
      const dialect = dialects.find(
        (d) => d.kind === "dialect" && d.region_codes.includes(region.code),
      );
      if (dialect) router.push(`/dialects/${dialect.code}`);
    },
  });

  return (
    <article className="space-y-5 p-4">
      <h1 className="text-2xl font-semibold">{t("title")}</h1>
      <p className="text-sm leading-relaxed">{t("intro")}</p>
      {groups.map((group) => (
        <section key={group.code}>
          <h2 className="mb-1 font-medium">{capitalize(localized(locale, group.name_en, group.name_uk))}</h2>
          <ul className="space-y-0.5">
            {members(group.code).map((dialect) => (
              <li key={dialect.code}>
                <Link
                  href={`/dialects/${dialect.code}`}
                  className="flex justify-between rounded-md px-2 py-1 hover:bg-black/5 dark:hover:bg-white/10"
                >
                  <span>{capitalize(localized(locale, dialect.name_en, dialect.name_uk))}</span>
                  <span className="text-sm opacity-60">{t("words", { count: dialect.words })}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </article>
  );
}
