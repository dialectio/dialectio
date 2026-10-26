"use client";

import { useLocale, useTranslations } from "next-intl";
import { useMemo } from "react";

import {
  EUROPE_BOUNDS,
  UKRAINE_BOUNDS,
  useMapView,
} from "@/components/MapShell";
import { Link } from "@/i18n/navigation";
import {
  capitalize,
  type Community,
  type CommunityActivity,
  localized,
} from "@/lib/api";

// Map fill from few to many votes (violet, as the dialects)
const SHADES = ["#ddd6fe", "#c4b5fd", "#a78bfa", "#8b5cf6", "#6d28d9"];
const TOP_REGIONS = 10;
// Community numbers are shown once they say something: a tile with "1 vote" doesn't
const MIN_SHOWN = 20;

function shade(votes: number, max: number) {
  const i = Math.floor(
    (Math.log(votes + 1) / Math.log(max + 1)) * (SHADES.length - 1),
  );
  return SHADES[Math.min(SHADES.length - 1, Math.max(0, i))];
}

/** "Community" page: what visitors have checked and added, and where they live. */
export default function CommunityView({ community }: { community: Community }) {
  const locale = useLocale();
  const t = useTranslations("Community");
  const { totals } = community;
  const name = (a: CommunityActivity) =>
    capitalize(localized(locale, a.name_en, a.name_uk, a.names));

  const colors = useMemo(() => {
    const max = Math.max(1, ...community.regions.map((r) => r.votes));
    return Object.fromEntries(
      community.regions.map((r) => [r.code, shade(r.votes, max)]),
    );
  }, [community]);
  const regionCodes = useMemo(
    () => community.regions.map((r) => r.code),
    [community],
  );
  useMapView({
    // The map paints only highlighted regions, in their colours
    highlightCodes: regionCodes,
    labels: null,
    selectedCode: null,
    onSelectRegion: () => {},
    // Ukraine while all voters are there, Europe once people from elsewhere join
    bounds: community.regions.every((r) => r.code.startsWith("UA-"))
      ? UKRAINE_BOUNDS
      : EUROPE_BOUNDS,
    colors,
  });

  const numbers = (
    [
      ["votes", totals.votes],
      ["voters", totals.voters],
      ["confirmed", totals.confirmed],
      ["words", totals.words],
      ["recordings", totals.recordings],
      ["reports", totals.reports],
    ] as [string, number][]
  ).filter(([, value]) => value >= MIN_SHOWN);
  // Older API answers had no map numbers or unchecked dialects: show the rest then
  const map = community.map;
  const mapNumbers: [string, number][] = map
    ? [
        ["words", map.words],
        ["languages", map.languages],
        ["dialects", map.dialects],
        ["pages", map.pages],
        ["recordings", map.recordings],
      ]
    : [];
  const needsHelp = community.needs_help ?? [];
  const maxDialect = Math.max(1, ...community.dialects.map((d) => d.votes));
  const dialectVotes = community.dialects.reduce((sum, d) => sum + d.votes, 0);

  return (
    <article className="space-y-5 p-4">
      <h1 className="font-serif text-2xl font-semibold">{t("title")}</h1>
      <p className="text-sm leading-relaxed">{t("intro")}</p>

      <section className="empty:hidden">
        {mapNumbers.length > 0 && (
          <h2 className="mb-1 font-medium">{t("mapTitle")}</h2>
        )}
        <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {mapNumbers.map(([key, value]) => (
            <div
              key={key}
              className="rounded-md bg-violet-500/5 p-2 ring-1 ring-violet-500/20"
            >
              <dd className="text-xl font-semibold">
                {value.toLocaleString(locale)}
              </dd>
              <dt className="text-xs opacity-70">{t(`map.${key}`)}</dt>
            </div>
          ))}
        </dl>
      </section>

      <h2 className="font-medium">{t("communityTitle")}</h2>
      {numbers.length === 0 && <p className="text-sm">{t("communityStart")}</p>}
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3 empty:hidden">
        {numbers.map(([key, value]) => (
          <div
            key={key}
            className="rounded-md border border-black/10 p-2 dark:border-white/15"
          >
            <dd className="text-xl font-semibold">
              {value.toLocaleString(locale)}
            </dd>
            <dt className="text-xs opacity-70">{t(`totals.${key}`)}</dt>
          </div>
        ))}
      </dl>
      {totals.recent_votes >= MIN_SHOWN && (
        <p className="text-sm opacity-80">
          {t("recent", {
            count: totals.recent_votes,
            days: community.recent_days,
          })}
        </p>
      )}

      <section>
        <h2 className="mb-1 font-medium">{t("regionsTitle")}</h2>
        {community.regions.length === 0 ? (
          <p className="text-sm opacity-70">{t("noRegions")}</p>
        ) : (
          <>
            <ol className="space-y-0.5 text-sm">
              {community.regions.slice(0, TOP_REGIONS).map((region) => (
                <li key={region.code} className="flex items-center gap-2">
                  <span
                    aria-hidden="true"
                    className="inline-block h-3 w-3 shrink-0 rounded-sm"
                    style={{ background: colors[region.code] }}
                  />
                  <span>{name(region)}</span>
                  <span className="ml-auto opacity-60">
                    {t("votes", { count: region.votes })}
                  </span>
                </li>
              ))}
            </ol>
            <p className="mt-1 text-xs opacity-60">{t("regionsNote")}</p>
          </>
        )}
      </section>

      {needsHelp.length > 0 && (
        <section>
          <h2 className="mb-1 font-medium">{t("needsHelpTitle")}</h2>
          <p className="mb-1 text-sm opacity-80">{t("needsHelpIntro")}</p>
          <ul className="space-y-0.5 text-sm">
            {needsHelp.map((dialect) => (
              <li key={dialect.code}>
                <Link
                  href={`/check?deck=${dialect.code}`}
                  className="flex justify-between gap-2 hover:underline"
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
                  <span className="shrink-0 opacity-60">
                    {t("unchecked", { count: dialect.words })}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {dialectVotes >= MIN_SHOWN && (
        <section>
          <h2 className="mb-1 font-medium">{t("dialectsTitle")}</h2>
          <ul className="space-y-1 text-sm">
            {community.dialects.map((dialect) => (
              <li key={dialect.code}>
                <Link
                  href={`/check?deck=${dialect.code}`}
                  className="block hover:underline"
                >
                  <span className="flex justify-between">
                    <span>{name(dialect)}</span>
                    <span className="opacity-60">
                      {t("votes", { count: dialect.votes })}
                    </span>
                  </span>
                  <span
                    aria-hidden="true"
                    className="mt-0.5 block h-1.5 rounded-full bg-violet-500/70"
                    style={{ width: `${(dialect.votes / maxDialect) * 100}%` }}
                  />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h2 className="mb-1 font-medium">{t("thanksTitle")}</h2>
        {community.contributors.length === 0 ? (
          <p className="text-sm opacity-70">{t("noContributors")}</p>
        ) : (
          <>
            <p className="mb-1 text-sm opacity-80">{t("thanksIntro")}</p>
            <ul className="flex flex-wrap gap-1.5 text-sm">
              {community.contributors.map((person) => (
                <li
                  key={person.name}
                  className="rounded-full bg-violet-500/10 px-2.5 py-0.5"
                  title={t("contribution", {
                    words: person.words,
                    recordings: person.recordings,
                  })}
                >
                  {person.name}
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <p className="flex flex-wrap gap-2">
        <Link
          href="/check"
          className="inline-block rounded-md bg-violet-600 px-3 py-1.5 text-sm font-medium text-white !no-underline hover:bg-violet-700"
        >
          {t("ctaCheck")}
        </Link>
        <Link
          href="/dialects"
          className="inline-block rounded-md border border-violet-500/40 px-3 py-1.5 text-sm text-violet-800 hover:bg-violet-500/10 dark:text-violet-300"
        >
          {t("ctaAdd")}
        </Link>
      </p>
    </article>
  );
}
